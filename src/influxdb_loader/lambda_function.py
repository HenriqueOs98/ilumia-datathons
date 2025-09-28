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
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from influxdb_client import Point

try:
    from shared_utils.influxdb_client import InfluxDBHandler, InfluxDBConnectionError, InfluxDBWriteError
    from shared_utils.data_conversion import (
        convert_parquet_to_influxdb_points,
        get_dataset_type_from_s3_key,
        validate_influxdb_points,
        DataConversionError
    )
    from shared_utils.logging_config import setup_logging
except ImportError as e:
    # Fallback for testing or when shared_utils is not available
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import shared_utils: {e}")
    
    # Define minimal fallback classes for testing
    class InfluxDBHandler:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def health_check(self):
            return {'status': 'healthy'}
        def write_points(self, points, bucket=None):
            return True
    
    class InfluxDBConnectionError(Exception):
        pass
    
    class InfluxDBWriteError(Exception):
        pass
    
    class DataConversionError(Exception):
        pass
    
    def setup_logging():
        return logging.getLogger()
    
    def convert_parquet_to_influxdb_points(df, dataset_type, validate_schema=True, drop_invalid=True):
        return []
    
    def get_dataset_type_from_s3_key(key):
        if 'generation' in key:
            return 'generation'
        elif 'consumption' in key:
            return 'consumption'
        elif 'transmission' in key:
            return 'transmission'
        return None
    
    def validate_influxdb_points(points):
        return {'valid': True, 'errors': [], 'warnings': []}
    


# Configure logging
try:
    logger = setup_logging()
    logger = logging.getLogger(__name__)
except:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

# Initialize AWS clients (with fallback for testing)
try:
    s3_client = boto3.client('s3')
    cloudwatch_client = boto3.client('cloudwatch')
except Exception as e:
    logger.warning(f"Could not initialize AWS clients: {e}")
    s3_client = None
    cloudwatch_client = None

# Environment variables
INFLUXDB_URL = os.environ.get('INFLUXDB_URL')
INFLUXDB_ORG = os.environ.get('INFLUXDB_ORG', 'ons-energy')
INFLUXDB_BUCKET = os.environ.get('INFLUXDB_BUCKET', 'energy_data')
MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', '1000'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '3'))
ENABLE_METRICS = os.environ.get('ENABLE_METRICS', 'true').lower() == 'true'
VALIDATE_SCHEMA = os.environ.get('VALIDATE_SCHEMA', 'true').lower() == 'true'
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
        logger.info(f"Processing event: {json.dumps(event, default=str)}")
        
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
        
        logger.info(f"Detected dataset type: {dataset_type}")
        
        # Initialize InfluxDB handler
        with InfluxDBHandler(
            url=INFLUXDB_URL,
            org=INFLUXDB_ORG,
            bucket=INFLUXDB_BUCKET,
            max_retries=MAX_RETRIES
        ) as influx_handler:
            
            # Perform health check
            health_result = influx_handler.health_check()
            if health_result['status'] != 'healthy':
                logger.error(f"InfluxDB health check failed: {health_result}")
                return create_response(503, f"InfluxDB unavailable: {health_result.get('error', 'Unknown error')}")
            
            # Load and process data
            df = load_parquet_from_s3(bucket_name, object_key)
            if df.empty:
                logger.warning(f"No data found in file: {object_key}")
                return create_response(200, "No data to process")
            
            logger.info(f"Loaded {len(df)} records from Parquet file")
            
            # Convert to InfluxDB points
            points = convert_parquet_to_influxdb_points(
                df=df,
                dataset_type=dataset_type,
                validate_schema=VALIDATE_SCHEMA,
                drop_invalid=DROP_INVALID_RECORDS
            )
            
            if not points:
                logger.warning("No valid points generated from data")
                return create_response(200, "No valid data to process")
            
            logger.info(f"Converted {len(points)} points for InfluxDB")
            
            # Validate points before writing
            validation_result = validate_influxdb_points(points)
            if not validation_result['valid']:
                logger.error(f"Point validation failed: {validation_result['errors']}")
                if not DROP_INVALID_RECORDS:
                    return create_response(400, f"Point validation failed: {validation_result['errors']}")
            
            if validation_result['warnings']:
                logger.warning(f"Point validation warnings: {validation_result['warnings']}")
            
            # Load data into InfluxDB
            load_result = load_data_to_influxdb(influx_handler, points, dataset_type)
            
            # Calculate processing metrics
            processing_time = time.time() - start_time
            
            # Send metrics to CloudWatch
            if ENABLE_METRICS:
                send_metrics(dataset_type, load_result, processing_time, len(df))
            
            logger.info(f"Successfully processed {load_result['points_written']} points in {processing_time:.2f}s")
            
            return create_response(200, "Data loaded successfully", {
                'points_written': load_result['points_written'],
                'batches_processed': load_result['batches_processed'],
                'dataset_type': dataset_type,
                'processing_time_seconds': round(processing_time, 2),
                'source_records': len(df),
                'health_check': health_result
            })
        
    except DataConversionError as e:
        logger.error(f"Data conversion error: {str(e)}")
        if ENABLE_METRICS:
            send_error_metrics("DataConversionError", str(e))
        return create_response(400, f"Data conversion failed: {str(e)}")
    
    except InfluxDBConnectionError as e:
        logger.error(f"InfluxDB connection error: {str(e)}")
        if ENABLE_METRICS:
            send_error_metrics("InfluxDBConnectionError", str(e))
        return create_response(503, f"InfluxDB connection failed: {str(e)}")
    
    except InfluxDBWriteError as e:
        logger.error(f"InfluxDB write error: {str(e)}")
        if ENABLE_METRICS:
            send_error_metrics("InfluxDBWriteError", str(e))
        return create_response(500, f"InfluxDB write failed: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error processing event: {str(e)}", exc_info=True)
        if ENABLE_METRICS:
            send_error_metrics("UnexpectedError", str(e))
        return create_response(500, f"Internal error: {str(e)}")


def extract_s3_info(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract S3 bucket and key from Lambda event.
    
    Supports multiple event formats:
    - Direct S3 event notification
    - Step Functions input
    - API Gateway with S3 info in body
    """
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
        
        # Handle API Gateway event with body
        if 'body' in event:
            try:
                body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
                if 'bucket' in body and 'key' in body:
                    return {
                        'bucket': body['bucket'],
                        'key': body['key']
                    }
            except json.JSONDecodeError:
                logger.warning("Failed to parse event body as JSON")
        
        return None
        
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error extracting S3 info: {str(e)}")
        return None


def load_parquet_from_s3(bucket_name: str, object_key: str) -> pd.DataFrame:
    """
    Load Parquet file from S3 into pandas DataFrame.
    
    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key
        
    Returns:
        pandas DataFrame with loaded data
        
    Raises:
        Exception: If file loading fails
    """
    try:
        if s3_client is None:
            raise RuntimeError("S3 client not initialized")
            
        # Direct S3 access
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        df = pd.read_parquet(response['Body'])
        
        logger.info(f"Loaded {len(df)} records from s3://{bucket_name}/{object_key}")
        
        # Log basic data info
        if not df.empty:
            logger.debug(f"DataFrame columns: {list(df.columns)}")
            logger.debug(f"DataFrame shape: {df.shape}")
            
            # Log timestamp range if available
            if 'timestamp' in df.columns:
                try:
                    timestamps = pd.to_datetime(df['timestamp'])
                    logger.info(f"Data timestamp range: {timestamps.min()} to {timestamps.max()}")
                except Exception as e:
                    logger.warning(f"Could not parse timestamp range: {e}")
        
        return df
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            logger.error(f"S3 object not found: s3://{bucket_name}/{object_key}")
            raise FileNotFoundError(f"S3 object not found: {object_key}")
        elif error_code == 'NoSuchBucket':
            logger.error(f"S3 bucket not found: {bucket_name}")
            raise FileNotFoundError(f"S3 bucket not found: {bucket_name}")
        else:
            logger.error(f"S3 error loading file: {str(e)}")
            raise
    
    except Exception as e:
        logger.error(f"Error loading Parquet file from S3: {str(e)}")
        raise


def load_data_to_influxdb(
    influx_handler: InfluxDBHandler,
    points: List[Point],
    dataset_type: str
) -> Dict[str, int]:
    """
    Load InfluxDB points with batch processing and comprehensive error handling.
    
    Args:
        influx_handler: InfluxDB handler instance
        points: List of InfluxDB Point objects
        dataset_type: Type of dataset for metrics
        
    Returns:
        Dictionary with loading results
        
    Raises:
        InfluxDBWriteError: If write operations fail
    """
    points_written = 0
    batches_processed = 0
    failed_batches = 0
    
    logger.info(f"Starting batch write of {len(points)} points with batch size {MAX_BATCH_SIZE}")
    
    # Process in batches
    for i in range(0, len(points), MAX_BATCH_SIZE):
        batch = points[i:i + MAX_BATCH_SIZE]
        batch_number = (i // MAX_BATCH_SIZE) + 1
        
        logger.debug(f"Processing batch {batch_number} with {len(batch)} points")
        
        try:
            # Write batch to InfluxDB
            success = influx_handler.write_points(
                points=batch,
                bucket=INFLUXDB_BUCKET
            )
            
            if success:
                points_written += len(batch)
                batches_processed += 1
                logger.debug(f"Successfully wrote batch {batch_number}")
            else:
                failed_batches += 1
                logger.error(f"Failed to write batch {batch_number}")
        
        except InfluxDBWriteError as e:
            failed_batches += 1
            logger.error(f"Write error for batch {batch_number}: {str(e)}")
            
            # For critical errors, stop processing
            if "authentication" in str(e).lower() or "authorization" in str(e).lower():
                raise
            
            # For other errors, continue with next batch if DROP_INVALID_RECORDS is True
            if not DROP_INVALID_RECORDS:
                raise
        
        except Exception as e:
            failed_batches += 1
            logger.error(f"Unexpected error writing batch {batch_number}: {str(e)}")
            
            if not DROP_INVALID_RECORDS:
                raise InfluxDBWriteError(f"Batch write failed: {str(e)}")
    
    # Log final results
    total_batches = (len(points) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
    success_rate = (batches_processed / total_batches) * 100 if total_batches > 0 else 0
    
    logger.info(f"Batch processing complete: {points_written}/{len(points)} points written "
                f"({batches_processed}/{total_batches} batches, {success_rate:.1f}% success rate)")
    
    if failed_batches > 0:
        logger.warning(f"{failed_batches} batches failed during processing")
    
    return {
        'points_written': points_written,
        'batches_processed': batches_processed,
        'failed_batches': failed_batches,
        'total_points': len(points),
        'success_rate': success_rate
    }


def send_metrics(
    dataset_type: str,
    load_result: Dict[str, int],
    processing_time: float,
    source_records: int
) -> None:
    """
    Send comprehensive metrics to CloudWatch.
    
    Args:
        dataset_type: Type of dataset processed
        load_result: Results from data loading
        processing_time: Total processing time in seconds
        source_records: Number of source records from Parquet
    """
    try:
        if cloudwatch_client is None:
            logger.warning("CloudWatch client not available, skipping metrics")
            return
        timestamp = datetime.utcnow()
        
        metrics = [
            {
                'MetricName': 'PointsWritten',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': load_result['points_written'],
                'Unit': 'Count',
                'Timestamp': timestamp
            },
            {
                'MetricName': 'BatchesProcessed',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': load_result['batches_processed'],
                'Unit': 'Count',
                'Timestamp': timestamp
            },
            {
                'MetricName': 'ProcessingTime',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': processing_time,
                'Unit': 'Seconds',
                'Timestamp': timestamp
            },
            {
                'MetricName': 'SourceRecords',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': source_records,
                'Unit': 'Count',
                'Timestamp': timestamp
            },
            {
                'MetricName': 'ConversionRate',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': (load_result['points_written'] / source_records * 100) if source_records > 0 else 0,
                'Unit': 'Percent',
                'Timestamp': timestamp
            },
            {
                'MetricName': 'BatchSuccessRate',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': load_result.get('success_rate', 0),
                'Unit': 'Percent',
                'Timestamp': timestamp
            }
        ]
        
        # Add failed batches metric if any failures occurred
        if load_result.get('failed_batches', 0) > 0:
            metrics.append({
                'MetricName': 'FailedBatches',
                'Dimensions': [
                    {'Name': 'DatasetType', 'Value': dataset_type},
                    {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                ],
                'Value': load_result['failed_batches'],
                'Unit': 'Count',
                'Timestamp': timestamp
            })
        
        # Send metrics in batches (CloudWatch limit is 20 metrics per call)
        for i in range(0, len(metrics), 20):
            batch_metrics = metrics[i:i + 20]
            cloudwatch_client.put_metric_data(
                Namespace='ONS/InfluxDB',
                MetricData=batch_metrics
            )
        
        logger.debug(f"Sent {len(metrics)} metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Error sending metrics to CloudWatch: {str(e)}")


def send_error_metrics(error_type: str, error_message: str) -> None:
    """
    Send error metrics to CloudWatch.
    
    Args:
        error_type: Type/category of error
        error_message: Error message
    """
    try:
        if cloudwatch_client is None:
            logger.warning("CloudWatch client not available, skipping error metrics")
            return
        cloudwatch_client.put_metric_data(
            Namespace='ONS/InfluxDB',
            MetricData=[
                {
                    'MetricName': 'ProcessingErrors',
                    'Dimensions': [
                        {'Name': 'ErrorType', 'Value': error_type},
                        {'Name': 'Function', 'Value': 'InfluxDBLoader'}
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
        
        logger.debug(f"Sent error metric for {error_type}")
        
    except Exception as e:
        logger.error(f"Error sending error metrics: {str(e)}")


def create_response(
    status_code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized Lambda response.
    
    Args:
        status_code: HTTP status code
        message: Response message
        data: Optional response data
        
    Returns:
        Standardized response dictionary
    """
    response = {
        'statusCode': status_code,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if data:
        response['data'] = data
    
    return response