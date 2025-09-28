"""
Lambda Router Function for ONS Data Platform

This function analyzes incoming file metadata and determines the appropriate
processing path based on file type, size, and other characteristics.

Supported formats: CSV, XLSX, Parquet, PDF
Default output format: Parquet (optimized for analytics and storage)

Requirements: 2.1, 2.4, 8.1
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration constants
LAMBDA_SIZE_THRESHOLD_MB = int(os.environ.get('LAMBDA_SIZE_THRESHOLD_MB', '100'))
SUPPORTED_STRUCTURED_FORMATS = {'.csv', '.xlsx', '.xls', '.parquet'}
SUPPORTED_UNSTRUCTURED_FORMATS = {'.pdf'}
ALL_SUPPORTED_FORMATS = SUPPORTED_STRUCTURED_FORMATS | SUPPORTED_UNSTRUCTURED_FORMATS


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for routing file processing decisions.
    
    Args:
        event: Lambda event containing file metadata
        context: Lambda context object
        
    Returns:
        Dict containing processing type and configuration
    """
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Extract file information from event
        file_info = extract_file_info(event)
        
        # Validate file format
        validate_file_format(file_info)
        
        # Determine processing path
        processing_decision = determine_processing_path(file_info)
        
        logger.info(f"Processing decision: {json.dumps(processing_decision)}")
        
        return {
            'statusCode': 200,
            'body': processing_decision
        }
        
    except Exception as e:
        logger.error(f"Error processing file routing: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'processingType': 'failed'
            }
        }


def extract_file_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract file information from the Lambda event.
    
    Args:
        event: Lambda event from Step Functions or EventBridge
        
    Returns:
        Dict containing file metadata
    """
    # Handle different event sources
    if 'Records' in event:
        # S3 event via EventBridge
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        size = record['s3']['object']['size']
    elif 'detail' in event:
        # EventBridge event
        detail = event['detail']
        bucket = detail['bucket']['name']
        key = detail['object']['key']
        size = detail['object']['size']
    else:
        # Direct invocation with file info
        bucket = event.get('bucket')
        key = event.get('key')
        size = event.get('size', 0)
    
    if not bucket or not key:
        raise ValueError("Missing required file information: bucket and key")
    
    # Extract file extension
    file_extension = get_file_extension(key)
    
    # Convert size to MB
    size_mb = size / (1024 * 1024) if size else 0
    
    return {
        'bucket': bucket,
        'key': key,
        'size_bytes': size,
        'size_mb': size_mb,
        'file_extension': file_extension,
        'filename': key.split('/')[-1]
    }


def get_file_extension(filename: str) -> str:
    """
    Extract and normalize file extension.
    
    Args:
        filename: Full filename or path
        
    Returns:
        Lowercase file extension with dot
    """
    if '.' not in filename:
        return ''
    
    return '.' + filename.split('.')[-1].lower()


def validate_file_format(file_info: Dict[str, Any]) -> None:
    """
    Validate that the file format is supported.
    
    Args:
        file_info: File metadata dictionary
        
    Raises:
        ValueError: If file format is not supported
    """
    file_extension = file_info['file_extension']
    
    if file_extension not in ALL_SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported file format: {file_extension}. "
            f"Supported formats: {', '.join(sorted(ALL_SUPPORTED_FORMATS))}"
        )


def determine_processing_path(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine the appropriate processing path based on file characteristics.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Processing configuration dictionary
    """
    file_extension = file_info['file_extension']
    size_mb = file_info['size_mb']
    
    # Determine processing type based on file format and size
    if file_extension in SUPPORTED_STRUCTURED_FORMATS:
        # Special handling for Parquet files - they may need different processing
        if file_extension == '.parquet':
            # Parquet files are already optimized, may need different handling
            if size_mb > LAMBDA_SIZE_THRESHOLD_MB:
                processing_type = 'batch'
                processor_config = get_batch_parquet_config(file_info)
            else:
                processing_type = 'lambda'
                processor_config = get_lambda_parquet_config(file_info)
        else:
            # CSV, XLSX files need conversion to Parquet
            if size_mb > LAMBDA_SIZE_THRESHOLD_MB:
                processing_type = 'batch'
                processor_config = get_batch_config(file_info)
            else:
                processing_type = 'lambda'
                processor_config = get_lambda_config(file_info)
    elif file_extension in SUPPORTED_UNSTRUCTURED_FORMATS:
        # PDFs always go to Batch due to specialized library requirements
        processing_type = 'batch'
        processor_config = get_batch_pdf_config(file_info)
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")
    
    # Generate output location
    output_location = generate_output_location(file_info)
    
    return {
        'processingType': processing_type,
        'processorConfig': processor_config,
        'outputLocation': output_location,
        'inputFile': {
            'bucket': file_info['bucket'],
            'key': file_info['key'],
            'size_mb': size_mb,
            'format': file_extension
        }
    }


def get_lambda_config(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate configuration for Lambda processing.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Lambda processor configuration
    """
    return {
        'functionName': 'ons-structured-data-processor',
        'memory': 3008,  # Maximum memory for CPU optimization
        'timeout': 900,  # 15 minutes
        'environment': {
            'OUTPUT_FORMAT': 'parquet',
            'PARTITION_STRATEGY': 'year_month'
        }
    }


def get_batch_config(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate configuration for Batch processing of large structured files.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Batch processor configuration
    """
    # Determine resource allocation based on file size
    size_mb = file_info['size_mb']
    
    if size_mb > 1000:  # > 1GB
        vcpus = 4
        memory = 16384
    elif size_mb > 500:  # > 500MB
        vcpus = 2
        memory = 8192
    else:
        vcpus = 1
        memory = 4096
    
    return {
        'jobDefinition': 'ons-structured-data-processor-batch',
        'jobQueue': 'ons-data-processing-queue',
        'vcpus': vcpus,
        'memory': memory,
        'environment': {
            'OUTPUT_FORMAT': 'parquet',
            'PARTITION_STRATEGY': 'year_month',
            'PROCESSING_MODE': 'batch'
        }
    }


def get_batch_pdf_config(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate configuration for Batch PDF processing.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Batch PDF processor configuration
    """
    return {
        'jobDefinition': 'ons-pdf-processor-batch',
        'jobQueue': 'ons-data-processing-queue',
        'vcpus': 2,
        'memory': 8192,
        'environment': {
            'OUTPUT_FORMAT': 'parquet',
            'PARTITION_STRATEGY': 'year_month',
            'PDF_EXTRACTION_TOOLS': 'camelot,tabula',
            'PROCESSING_MODE': 'pdf'
        }
    }


def get_lambda_parquet_config(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate configuration for Lambda processing of Parquet files.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Lambda Parquet processor configuration
    """
    return {
        'functionName': 'ons-parquet-processor',
        'memory': 3008,
        'timeout': 900,
        'environment': {
            'INPUT_FORMAT': 'parquet',
            'OUTPUT_FORMAT': 'parquet',
            'PARTITION_STRATEGY': 'year_month',
            'PROCESSING_MODE': 'parquet_optimization'
        }
    }


def get_batch_parquet_config(file_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate configuration for Batch processing of large Parquet files.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        Batch Parquet processor configuration
    """
    # Determine resource allocation based on file size
    size_mb = file_info['size_mb']
    
    if size_mb > 1000:  # > 1GB
        vcpus = 4
        memory = 16384
    elif size_mb > 500:  # > 500MB
        vcpus = 2
        memory = 8192
    else:
        vcpus = 1
        memory = 4096
    
    return {
        'jobDefinition': 'ons-parquet-processor-batch',
        'jobQueue': 'ons-data-processing-queue',
        'vcpus': vcpus,
        'memory': memory,
        'environment': {
            'INPUT_FORMAT': 'parquet',
            'OUTPUT_FORMAT': 'parquet',
            'PARTITION_STRATEGY': 'year_month',
            'PROCESSING_MODE': 'parquet_optimization'
        }
    }


def generate_output_location(file_info: Dict[str, Any]) -> str:
    """
    Generate S3 output location for processed data.
    
    Args:
        file_info: File metadata dictionary
        
    Returns:
        S3 output path
    """
    # Extract dataset type from filename or path
    filename = file_info['filename'].lower()
    key_path = file_info['key'].lower()
    
    # Determine dataset type based on filename patterns
    if any(term in filename or term in key_path for term in ['geracao', 'generation', 'gen']):
        dataset_type = 'generation'
    elif any(term in filename or term in key_path for term in ['consumo', 'consumption', 'cons']):
        dataset_type = 'consumption'
    elif any(term in filename or term in key_path for term in ['transmissao', 'transmission', 'trans']):
        dataset_type = 'transmission'
    else:
        dataset_type = 'general'
    
    # Generate partitioned path
    # Format: s3://bucket/processed/dataset=type/year=YYYY/month=MM/
    import datetime
    now = datetime.datetime.now()
    
    output_bucket = os.environ.get('PROCESSED_BUCKET', 'ons-data-platform-processed')
    output_path = f"s3://{output_bucket}/processed/dataset={dataset_type}/year={now.year}/month={now.month:02d}/"
    
    return output_path