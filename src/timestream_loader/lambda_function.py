"""
Data Loader Lambda Function

This function loads processed Parquet data from S3 into the configured time series database.
It supports both Amazon Timestream and InfluxDB with traffic switching capabilities.
Handles batch loading with error handling and retries.
"""

import json
import logging
import os
import boto3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import time
import sys

# Add shared utilities to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from shared_utils import (
        InfluxDBHandler,
        should_use_influxdb_for_ingestion,
        DatabaseBackend,
        record_performance_metric
    )
    from shared_utils.logging_config import setup_logging
except ImportError:
    # Fallback for testing environment
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))
    from influxdb_client import InfluxDBHandler
    from traffic_switch import (
        should_use_influxdb_for_ingestion,
        DatabaseBackend,
        record_performance_metric
    )
    from logging_config import setup_logging

# Configure logging
try:
    setup_logging()
    logger = logging.getLogger(__name__)
except:
    # Fallback logging setup
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
timestream_client = boto3.client('timestream-write')
cloudwatch_client = boto3.client('cloudwatch')

# Environment variables - Timestream (legacy)
DATABASE_NAME = os.environ.get('TIMESTREAM_DATABASE_NAME', '')
GENERATION_TABLE = os.environ.get('GENERATION_TABLE_NAME', '')
CONSUMPTION_TABLE = os.environ.get('CONSUMPTION_TABLE_NAME', '')
TRANSMISSION_TABLE = os.environ.get('TRANSMISSION_TABLE_NAME', '')

# Environment variables - Common
MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', '1000'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))

# InfluxDB handler (lazy-loaded)
influxdb_handler = None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for loading data into the configured time series database.
    
    Args:
        event: Lambda event containing S3 object information
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    start_time = time.time()
    backend_used = None
    
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Extract S3 information from event
        s3_info = extract_s3_info(event)
        if not s3_info:
            return create_response(400, "Invalid event format")
        
        bucket_name = s3_info['bucket']
        object_key = s3_info['key']
        
        logger.info(f"Processing file: s3://{bucket_name}/{object_key}")
        
        # Determine dataset type from object key
        dataset_type = determine_dataset_type(object_key)
        if not dataset_type:
            return create_response(400, f"Unable to determine dataset type from key: {object_key}")
        
        # Load and process data
        df = load_parquet_from_s3(bucket_name, object_key)
        if df.empty:
            logger.warning(f"No data found in file: {object_key}")
            return create_response(200, "No data to process")
        
        # Validate data schema
        validation_result = validate_data_schema(df, dataset_type)
        if not validation_result['valid']:
            logger.error(f"Data validation failed: {validation_result['errors']}")
            return create_response(400, f"Data validation failed: {validation_result['errors']}")
        
        # Determine which backend to use for data ingestion
        use_influxdb = should_use_influxdb_for_ingestion()
        
        if use_influxdb:
            logger.info("Using InfluxDB for data ingestion")
            backend_used = DatabaseBackend.INFLUXDB
            load_result = load_data_to_influxdb(df, dataset_type)
        else:
            logger.info("Using Timestream for data ingestion")
            backend_used = DatabaseBackend.TIMESTREAM
            load_result = load_data_to_timestream(df, dataset_type)
        
        # Record performance metrics
        processing_time = (time.time() - start_time) * 1000
        record_performance_metric(backend_used, processing_time, True)
        
        # Send metrics to CloudWatch
        send_metrics(dataset_type, load_result, backend_used.value)
        
        logger.info(f"Successfully processed {load_result['records_processed']} records using {backend_used.value}")
        
        return create_response(200, "Data loaded successfully", {
            'records_processed': load_result['records_processed'],
            'batches_processed': load_result['batches_processed'],
            'dataset_type': dataset_type,
            'backend_used': backend_used.value,
            'processing_time_ms': processing_time
        })
        
    except Exception as e:
        # Record error metrics
        if backend_used:
            processing_time = (time.time() - start_time) * 1000
            record_performance_metric(backend_used, processing_time, False)
        
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        send_error_metrics(str(e), backend_used.value if backend_used else 'unknown')
        return create_response(500, f"Internal error: {str(e)}")


def extract_s3_info(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract S3 bucket and key from Lambda event."""
    try:
        # Handle direct S3 event
        if 'Records' in event:
            record = event['Records'][0]
            if 's3' in record:
                return {
                    'bucket': record['s3']['bucket']['name'],
                    'key': record['s3']['object']['key']
                }
        
        # Handle Step Functions input
        if 'bucket' in event and 'key' in event:
            return {
                'bucket': event['bucket'],
                'key': event['key']
            }
        
        return None
    except (KeyError, IndexError) as e:
        logger.error(f"Error extracting S3 info: {str(e)}")
        return None


def determine_dataset_type(object_key: str) -> Optional[str]:
    """Determine dataset type from S3 object key."""
    if 'dataset=generation' in object_key:
        return 'generation'
    elif 'dataset=consumption' in object_key:
        return 'consumption'
    elif 'dataset=transmission' in object_key:
        return 'transmission'
    return None


def load_parquet_from_s3(bucket_name: str, object_key: str) -> pd.DataFrame:
    """Load Parquet file from S3 into pandas DataFrame."""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        df = pd.read_parquet(response['Body'])
        logger.info(f"Loaded {len(df)} records from {object_key}")
        return df
    except Exception as e:
        logger.error(f"Error loading Parquet file: {str(e)}")
        raise


def validate_data_schema(df: pd.DataFrame, dataset_type: str) -> Dict[str, Any]:
    """Validate DataFrame schema for Timestream compatibility."""
    errors = []
    
    # Required columns for all dataset types
    required_columns = ['timestamp', 'region', 'value', 'unit']
    
    # Dataset-specific required columns
    if dataset_type == 'generation':
        required_columns.extend(['energy_source', 'measurement_type'])
    elif dataset_type == 'consumption':
        required_columns.extend(['consumer_type', 'measurement_type'])
    elif dataset_type == 'transmission':
        required_columns.extend(['line_id', 'measurement_type'])
    
    # Check for required columns
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
    
    # Validate timestamp column
    if 'timestamp' in df.columns:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        except Exception as e:
            errors.append(f"Invalid timestamp format: {str(e)}")
    
    # Validate numeric columns
    if 'value' in df.columns:
        if not pd.api.types.is_numeric_dtype(df['value']):
            errors.append("Value column must be numeric")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def load_data_to_influxdb(df: pd.DataFrame, dataset_type: str) -> Dict[str, int]:
    """Load DataFrame data into InfluxDB with batch processing and retries."""
    global influxdb_handler
    
    if influxdb_handler is None:
        influxdb_handler = InfluxDBHandler()
    
    records_processed = 0
    batches_processed = 0
    
    try:
        # Convert DataFrame to InfluxDB format and write
        result = influxdb_handler.write_parquet_to_influx(df, dataset_type)
        
        records_processed = result.get('records_written', len(df))
        batches_processed = result.get('batches_processed', 1)
        
        logger.info(f"Successfully wrote {records_processed} records to InfluxDB in {batches_processed} batches")
        
        return {
            'records_processed': records_processed,
            'batches_processed': batches_processed
        }
        
    except Exception as e:
        logger.error(f"Error writing data to InfluxDB: {str(e)}")
        raise


def load_data_to_timestream(df: pd.DataFrame, dataset_type: str) -> Dict[str, int]:
    """Load DataFrame data into Timestream with batch processing and retries."""
    if not DATABASE_NAME:
        raise ValueError("Timestream database name not configured")
        
    table_name = get_table_name(dataset_type)
    records_processed = 0
    batches_processed = 0
    
    # Convert DataFrame to Timestream records
    records = convert_to_timestream_records(df, dataset_type)
    
    # Process in batches
    for i in range(0, len(records), MAX_BATCH_SIZE):
        batch = records[i:i + MAX_BATCH_SIZE]
        
        # Retry logic for batch processing
        for attempt in range(MAX_RETRIES):
            try:
                response = timestream_client.write_records(
                    DatabaseName=DATABASE_NAME,
                    TableName=table_name,
                    Records=batch
                )
                
                records_processed += len(batch)
                batches_processed += 1
                
                logger.info(f"Successfully wrote batch {batches_processed} with {len(batch)} records")
                break
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ThrottlingException' and attempt < MAX_RETRIES - 1:
                    # Exponential backoff for throttling
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Throttling detected, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error writing batch to Timestream: {str(e)}")
                    raise
    
    return {
        'records_processed': records_processed,
        'batches_processed': batches_processed
    }


def convert_to_timestream_records(df: pd.DataFrame, dataset_type: str) -> List[Dict[str, Any]]:
    """Convert DataFrame to Timestream record format."""
    records = []
    
    for _, row in df.iterrows():
        # Base dimensions for all dataset types
        dimensions = [
            {'Name': 'region', 'Value': str(row['region'])},
            {'Name': 'dataset_type', 'Value': dataset_type}
        ]
        
        # Add dataset-specific dimensions
        if dataset_type == 'generation' and 'energy_source' in row:
            dimensions.append({'Name': 'energy_source', 'Value': str(row['energy_source'])})
        elif dataset_type == 'consumption' and 'consumer_type' in row:
            dimensions.append({'Name': 'consumer_type', 'Value': str(row['consumer_type'])})
        elif dataset_type == 'transmission' and 'line_id' in row:
            dimensions.append({'Name': 'line_id', 'Value': str(row['line_id'])})
        
        if 'measurement_type' in row:
            dimensions.append({'Name': 'measurement_type', 'Value': str(row['measurement_type'])})
        
        # Create record
        record = {
            'Time': str(int(pd.Timestamp(row['timestamp']).timestamp() * 1000)),
            'TimeUnit': 'MILLISECONDS',
            'Dimensions': dimensions,
            'MeasureName': 'value',
            'MeasureValue': str(row['value']),
            'MeasureValueType': 'DOUBLE'
        }
        
        # Add quality flag if present
        if 'quality_flag' in row and pd.notna(row['quality_flag']):
            record['Dimensions'].append({
                'Name': 'quality_flag', 
                'Value': str(row['quality_flag'])
            })
        
        records.append(record)
    
    return records


def get_table_name(dataset_type: str) -> str:
    """Get Timestream table name for dataset type."""
    table_mapping = {
        'generation': GENERATION_TABLE,
        'consumption': CONSUMPTION_TABLE,
        'transmission': TRANSMISSION_TABLE
    }
    return table_mapping.get(dataset_type, GENERATION_TABLE or 'generation_data')


def send_metrics(dataset_type: str, load_result: Dict[str, int], backend: str) -> None:
    """Send custom metrics to CloudWatch."""
    try:
        namespace = f'ONS/{backend.title()}' if backend in ['timestream', 'influxdb'] else 'ONS/DataLoader'
        
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    'MetricName': 'RecordsProcessed',
                    'Dimensions': [
                        {'Name': 'DatasetType', 'Value': dataset_type},
                        {'Name': 'Backend', 'Value': backend}
                    ],
                    'Value': load_result['records_processed'],
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': 'BatchesProcessed',
                    'Dimensions': [
                        {'Name': 'DatasetType', 'Value': dataset_type},
                        {'Name': 'Backend', 'Value': backend}
                    ],
                    'Value': load_result['batches_processed'],
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    except Exception as e:
        logger.error(f"Error sending metrics: {str(e)}")


def send_error_metrics(error_message: str, backend: str = 'unknown') -> None:
    """Send error metrics to CloudWatch."""
    try:
        namespace = f'ONS/{backend.title()}' if backend in ['timestream', 'influxdb'] else 'ONS/DataLoader'
        
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    'MetricName': 'ProcessingErrors',
                    'Dimensions': [
                        {'Name': 'Backend', 'Value': backend}
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    except Exception as e:
        logger.error(f"Error sending error metrics: {str(e)}")


def create_response(status_code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create standardized Lambda response."""
    response = {
        'statusCode': status_code,
        'message': message
    }
    
    if data:
        response['data'] = data
    
    return response