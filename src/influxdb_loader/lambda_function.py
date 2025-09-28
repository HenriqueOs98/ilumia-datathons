"""
InfluxDB Loader Lambda Function

This function loads processed Parquet data from S3 into Amazon Timestream for InfluxDB.
It handles batch loading with error handling, retries, and comprehensive monitoring.
"""

import json
import logging
import os
import boto3
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import time

# Import shared utilities
import sys
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))

from influxdb_client import InfluxDBHandler, InfluxDBConnectionError, InfluxDBWriteError
from data_conversion import (
    EnergyDataConverter, 
    convert_parquet_to_influxdb_points,
    get_dataset_type_from_s3_key,
    validate_influxdb_points,
    DataConversionError
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
cloudwatch_client = boto3.client('cloudwatch')

# Environment variables
INFLUXDB_URL = os.environ['INFLUXDB_URL']
INFLUXDB_ORG = os.environ['INFLUXDB_ORG']
INFLUXDB_BUCKET = os.environ['INFLUXDB_BUCKET']
MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', '1000'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
ENABLE_VALIDATION = os.environ.get('ENABLE_VALIDATION', 'true').lower() == 'true'
DROP_INVALID_RECORDS = os.environ.get('DROP_INVALID_RECORDS', 'true').lower() == 'true'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for loading data into InfluxDB.
    
    Args:
        event: Lambda event containing S3 object information
        context: Lambda context
        
    Returns:
        Dict with processing results
    """
    start_time = time.time()
    
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
        dataset_type = get_dataset_type_from_s3_key(object_key)
        if not dataset_type:
            return create_response(400, f"Unable to determine dataset type from key: {object_key}")
        
        # Initialize InfluxDB handler
        influxdb_handler = InfluxDBHandler(
            url=INFLUXDB_URL,
            org=INFLUXDB_ORG,
            bucket=INFLUXDB_BUCKET,
            max_retries=MAX_RETRIES
        )
        
        # Perform health check
        health_result = influxdb_handler.health_check()
        if health_result['status'] != 'healthy':
            logger.error(f"InfluxDB health check failed: {health_result}")
            return create_response(503, f"InfluxDB unavailable: {health_result.get('error', 'Unknown error')}")
        
        # Load and process data
        df = load_parquet_from_s3(bucket_name, object_key)
        if df.empty:
            logger.warning(f"No data found in file: {object_key}")
            return create_response(200, "No data to process")
        
        # Convert data to InfluxDB points
        conversion_result = convert_data_to_influxdb_points(df, dataset_type)
        if not conversion_result['points']:
            logger.warning("No valid points generated from data")
            return create_response(200, "No valid data to process", conversion_result['stats'])
        
        # Load data into InfluxDB
        load_result = load_data_to_influxdb(influxdb_handler, conversion_result['points'], dataset_type)
        
        # Calculate processing metrics
        processing_time = time.time() - start_time
        
        # Send metrics to CloudWatch
        send_metrics(dataset_type, load_result, conversion_result['stats'], processing_time)
        
        logger.info(f"Successfully processed {load_result['points_written']} points in {processing_time:.2f}s")
        
        return create_response(200, "Data loaded successfully", {
            'points_written': load_result['points_written'],
            'batches_processed': load_result['batches_processed'],
            'dataset_type': dataset_type,
            'processing_time_seconds': round(processing_time, 2),
            'conversion_stats': conversion_result['stats'],
            'influxdb_health': health_result
        })
        
    except InfluxDBConnectionError as e:
        logger.error(f"InfluxDB connection error: {str(e)}")
        send_error_metrics("connection_error", str(e))
        return create_response(503, f"InfluxDB connection failed: {str(e)}")
        
    except DataConversionError as e:
        logger.error(f"Data conversion error: {str(e)}")
        send_error_metrics("conversion_error", str(e))
        return create_response(400, f"Data conversion failed: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        send_error_metrics("processing_error", str(e))
        return create_response(500, f"Internal error: {str(e)}")
    
    finally:
        # Cleanup InfluxDB handler if it exists
        try:
            if 'influxdb_handler' in locals():
                influxdb_handler.close()
        except Exception as e:
            logger.warning(f"Error closing InfluxDB handler: {e}")


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


def convert_data_to_influxdb_points(df: pd.DataFrame, dataset_type: str) -> Dict[str, Any]:
    """
    Convert DataFrame to InfluxDB points with validation and statistics.
    
    Args:
        df: Input DataFrame
        dataset_type: Type of dataset
        
    Returns:
        Dictionary with points and conversion statistics
    """
    try:
        # Convert to InfluxDB points
        points = convert_parquet_to_influxdb_points(
            df=df,
            dataset_type=dataset_type,
            validate_schema=ENABLE_VALIDATION,
            drop_invalid=DROP_INVALID_RECORDS
        )
        
        # Validate points if enabled
        validation_result = validate_influxdb_points(points) if ENABLE_VALIDATION else {'valid': True}
        
        # Collect statistics
        stats = {
            'input_rows': len(df),
            'output_points': len(points),
            'conversion_rate': len(points) / len(df) if len(df) > 0 else 0,
            'validation_result': validation_result,
            'dataset_type': dataset_type
        }
        
        if not validation_result['valid']:
            logger.warning(f"Point validation issues: {validation_result}")
        
        logger.info(f"Converted {len(df)} rows to {len(points)} InfluxDB points")
        
        return {
            'points': points,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Error converting data to InfluxDB points: {e}")
        raise DataConversionError(f"Data conversion failed: {e}")


def load_data_to_influxdb(
    influxdb_handler: InfluxDBHandler, 
    points: List, 
    dataset_type: str
) -> Dict[str, int]:
    """
    Load InfluxDB points with batch processing and comprehensive error handling.
    
    Args:
        influxdb_handler: InfluxDB handler instance
        points: List of InfluxDB Point objects
        dataset_type: Type of dataset for metrics
        
    Returns:
        Dictionary with loading statistics
    """
    points_written = 0
    batches_processed = 0
    failed_batches = 0
    
    try:
        # Use batch writer for optimal performance
        with influxdb_handler.batch_writer(batch_size=MAX_BATCH_SIZE) as batch_writer:
            
            # Process in batches
            for i in range(0, len(points), MAX_BATCH_SIZE):
                batch = points[i:i + MAX_BATCH_SIZE]
                batch_number = batches_processed + 1
                
                # Retry logic for batch processing
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        batch_writer.write(
                            bucket=INFLUXDB_BUCKET,
                            record=batch
                        )
                        
                        points_written += len(batch)
                        batches_processed += 1
                        
                        logger.info(f"Successfully wrote batch {batch_number} with {len(batch)} points")
                        break
                        
                    except InfluxDBWriteError as e:
                        if attempt == MAX_RETRIES:
                            logger.error(f"Failed to write batch {batch_number} after {MAX_RETRIES + 1} attempts: {e}")
                            failed_batches += 1
                            
                            # Send individual points if batch fails
                            if DROP_INVALID_RECORDS:
                                points_written += write_points_individually(
                                    influxdb_handler, batch, batch_number
                                )
                            else:
                                raise
                        else:
                            wait_time = (2 ** attempt) * 1
                            logger.warning(f"Batch {batch_number} attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                            time.sleep(wait_time)
                    
                    except Exception as e:
                        logger.error(f"Unexpected error writing batch {batch_number}: {e}")
                        failed_batches += 1
                        if not DROP_INVALID_RECORDS:
                            raise
                        break
        
        logger.info(f"Batch processing complete: {points_written} points written, {failed_batches} batches failed")
        
        return {
            'points_written': points_written,
            'batches_processed': batches_processed,
            'failed_batches': failed_batches,
            'success_rate': (batches_processed / (batches_processed + failed_batches)) if (batches_processed + failed_batches) > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error in batch loading: {e}")
        raise InfluxDBWriteError(f"Batch loading failed: {e}")


def write_points_individually(
    influxdb_handler: InfluxDBHandler, 
    points: List, 
    batch_number: int
) -> int:
    """
    Write points individually when batch write fails.
    
    Args:
        influxdb_handler: InfluxDB handler instance
        points: List of points to write
        batch_number: Batch number for logging
        
    Returns:
        Number of points successfully written
    """
    points_written = 0
    
    logger.info(f"Writing {len(points)} points individually for failed batch {batch_number}")
    
    for i, point in enumerate(points):
        try:
            influxdb_handler.write_points([point])
            points_written += 1
        except Exception as e:
            logger.warning(f"Failed to write individual point {i} from batch {batch_number}: {e}")
    
    logger.info(f"Individual write complete: {points_written}/{len(points)} points written")
    return points_written


def send_metrics(
    dataset_type: str, 
    load_result: Dict[str, int], 
    conversion_stats: Dict[str, Any],
    processing_time: float
) -> None:
    """Send comprehensive metrics to CloudWatch."""
    try:
        metric_data = [
            {
                'MetricName': 'PointsWritten',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': load_result['points_written'],
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'BatchesProcessed',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': load_result['batches_processed'],
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'ProcessingTime',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': processing_time,
                'Unit': 'Seconds',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'ConversionRate',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': conversion_stats['conversion_rate'],
                'Unit': 'Percent',
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'SuccessRate',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': load_result['success_rate'],
                'Unit': 'Percent',
                'Timestamp': datetime.utcnow()
            }
        ]
        
        # Add failed batches metric if any
        if load_result['failed_batches'] > 0:
            metric_data.append({
                'MetricName': 'FailedBatches',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type}
                ],
                'Value': load_result['failed_batches'],
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            })
        
        cloudwatch_client.put_metric_data(
            Namespace='ONS/InfluxDB',
            MetricData=metric_data
        )
        
        logger.debug("Successfully sent metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Error sending metrics: {str(e)}")


def send_error_metrics(error_type: str, error_message: str) -> None:
    """Send error metrics to CloudWatch."""
    try:
        cloudwatch_client.put_metric_data(
            Namespace='ONS/InfluxDB',
            MetricData=[
                {
                    'MetricName': 'ProcessingErrors',
                    'Dimensions': [
                        {'Name': 'ErrorType', 'Value': error_type}
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
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data:
        response['data'] = data
    
    return response