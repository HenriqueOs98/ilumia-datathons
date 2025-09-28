# Shared Utils

## Code Documentation

### s3_utils.py

S3 utilities for the ONS Data Platform.

**Functions:**

#### `parse_s3_event`

Parse S3 event to extract bucket and key information.

Args:
    event: Lambda event from S3

Returns:
    Dictionary with bucket and key information

**Parameters:**
- `event` (Any): 

#### `get_object_metadata`

Get S3 object metadata.

Args:
    bucket: S3 bucket name
    key: S3 object key

Returns:
    Object metadata dictionary

**Parameters:**
- `bucket` (Any): 
- `key` (Any): 

#### `download_file`

Download file from S3 to local path.

Args:
    bucket: S3 bucket name
    key: S3 object key
    local_path: Local file path

Returns:
    Local file path

**Parameters:**
- `bucket` (Any): 
- `key` (Any): 
- `local_path` (Any): 

#### `upload_file`

Upload file from local path to S3.

Args:
    local_path: Local file path
    bucket: S3 bucket name
    key: S3 object key
    metadata: Optional metadata dictionary

Returns:
    S3 URI

**Parameters:**
- `local_path` (Any): 
- `bucket` (Any): 
- `key` (Any): 
- `metadata` (Any): 

#### `list_objects`

List objects in S3 bucket with optional prefix.

Args:
    bucket: S3 bucket name
    prefix: Object key prefix
    max_keys: Maximum number of keys to return

Returns:
    List of object information dictionaries

**Parameters:**
- `bucket` (Any): 
- `prefix` (Any): 
- `max_keys` (Any): 

**Classes:**

#### `S3Utils`

S3 utility functions.

### data_validation.py

Data validation utilities for the ONS Data Platform.

**Functions:**

#### `validate_dataframe`

Validate a DataFrame against expected schema.

Args:
    df: DataFrame to validate
    dataset_type: Type of dataset (generation, consumption, transmission)

Returns:
    Validation results dictionary

**Parameters:**
- `df` (Any): 
- `dataset_type` (Any): 

#### `clean_dataframe`

Clean and standardize DataFrame.

Args:
    df: DataFrame to clean
    dataset_type: Type of dataset

Returns:
    Cleaned DataFrame

**Parameters:**
- `df` (Any): 
- `dataset_type` (Any): 

**Classes:**

#### `DataValidator`

Data validation utilities for energy data.

### logging_config.py

Centralized logging configuration for the ONS Data Platform.

**Functions:**

#### `setup_logging`

Setup centralized logging configuration.

Args:
    level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Returns:
    Configured logger instance

**Parameters:**
- `level` (Any): 

#### `log_with_context`

Log message with additional context fields.

Args:
    logger: Logger instance
    level: Log level
    message: Log message
    **context: Additional context fields

**Parameters:**
- `logger` (Any): 
- `level` (Any): 
- `message` (Any): 

#### `format`

**Parameters:**
- `self` (Any): 
- `record` (Any): 

**Classes:**

#### `JSONFormatter`

Custom JSON formatter for structured logging.

### aws_clients.py

AWS client utilities for consistent service access across the platform.

**Functions:**

#### `__init__`

**Parameters:**
- `self` (Any): 
- `region` (Any): 

#### `s3`

Get S3 client.

**Parameters:**
- `self` (Any): 

#### `timestream_write`

Get Timestream Write client.

**Parameters:**
- `self` (Any): 

#### `bedrock_agent_runtime`

Get Bedrock Agent Runtime client.

**Parameters:**
- `self` (Any): 

#### `stepfunctions`

Get Step Functions client.

**Parameters:**
- `self` (Any): 

**Classes:**

#### `AWSClients`

Centralized AWS client management.

### __init__.py

Shared utilities for the ONS Data Platform.

This module provides common functionality used across Lambda functions,
Batch jobs, and other components of the platform.

## Dependencies

- `# Core AWS and data processing dependencies`
- `boto3>=1.34.0`
- `pandas>=2.1.0`
- `pyarrow>=14.0.0`
- `awswrangler>=3.5.0`
- `# Testing dependencies`
- `pytest>=7.4.0`
- `pytest-cov>=4.1.0`
- `moto>=4.2.0`
- `# Security and validation`
- `pydantic>=2.5.0`
- `jsonschema>=4.20.0`

