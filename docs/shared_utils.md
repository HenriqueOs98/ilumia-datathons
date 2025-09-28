# Shared Utils

## Code Documentation

### data_conversion.py

Data conversion utilities for InfluxDB line protocol.

This module provides functions to convert Parquet data structures to InfluxDB
Point objects with proper tag and field mapping based on energy data schema.

**Functions:**

#### `create_converter`

Factory function to create data converter for specific dataset type.

Args:
    dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
    
Returns:
    EnergyDataConverter instance

**Parameters:**
- `dataset_type` (Any): 

#### `convert_parquet_to_influxdb_points`

Convenience function to convert Parquet DataFrame to InfluxDB Points.

Args:
    df: Input DataFrame with energy data
    dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
    validate_schema: Whether to validate DataFrame schema
    drop_invalid: Whether to drop invalid rows or raise error
    
Returns:
    List of InfluxDB Point objects
    
Raises:
    DataConversionError: If conversion fails

**Parameters:**
- `df` (Any): 
- `dataset_type` (Any): 
- `validate_schema` (Any): 
- `drop_invalid` (Any): 

#### `get_dataset_type_from_s3_key`

Extract dataset type from S3 object key.

Args:
    s3_key: S3 object key
    
Returns:
    Dataset type or None if not found

**Parameters:**
- `s3_key` (Any): 

#### `validate_influxdb_points`

Validate list of InfluxDB Points for common issues.

Args:
    points: List of InfluxDB Point objects
    
Returns:
    Validation results dictionary

**Parameters:**
- `points` (Any): 

#### `__init__`

Initialize converter for specific dataset type.

Args:
    dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
    
Raises:
    ValueError: If dataset_type is not supported

**Parameters:**
- `self` (Any): 
- `dataset_type` (Any): 

#### `convert_dataframe_to_points`

Convert pandas DataFrame to InfluxDB Point objects.

Args:
    df: Input DataFrame with energy data
    validate_schema: Whether to validate DataFrame schema
    drop_invalid: Whether to drop invalid rows or raise error
    
Returns:
    List of InfluxDB Point objects
    
Raises:
    DataConversionError: If conversion fails

**Parameters:**
- `self` (Any): 
- `df` (Any): 
- `validate_schema` (Any): 
- `drop_invalid` (Any): 

#### `validate_dataframe_schema`

Validate DataFrame schema for InfluxDB conversion.

Args:
    df: DataFrame to validate
    
Returns:
    Dictionary with validation results

**Parameters:**
- `self` (Any): 
- `df` (Any): 

#### `_prepare_dataframe`

Clean and prepare DataFrame for conversion.

Args:
    df: Input DataFrame
    drop_invalid: Whether to drop invalid rows
    
Returns:
    Cleaned DataFrame

**Parameters:**
- `self` (Any): 
- `df` (Any): 
- `drop_invalid` (Any): 

#### `_convert_row_to_point`

Convert a single DataFrame row to InfluxDB Point.

Args:
    row: DataFrame row as Series
    
Returns:
    InfluxDB Point object or None if conversion fails

**Parameters:**
- `self` (Any): 
- `row` (Any): 

#### `_get_field_name_from_unit`

Get appropriate field name based on unit.

Args:
    unit: Unit string
    
Returns:
    Field name for the measurement

**Parameters:**
- `self` (Any): 
- `unit` (Any): 

#### `convert_timestream_to_influxdb`

Convert Timestream record format to InfluxDB Points.

This is useful for migrating existing Timestream data.

Args:
    timestream_records: List of Timestream record dictionaries
    dataset_type: Type of dataset
    
Returns:
    List of InfluxDB Point objects

**Parameters:**
- `cls` (Any): 
- `timestream_records` (Any): 
- `dataset_type` (Any): 

#### `_convert_timestream_record_to_point`

Convert single Timestream record to InfluxDB Point.

Args:
    record: Timestream record dictionary
    
Returns:
    InfluxDB Point object or None if conversion fails

**Parameters:**
- `self` (Any): 
- `record` (Any): 

**Classes:**

#### `DataConversionError`

Raised when data conversion fails.

#### `EnergyDataConverter`

Converter for energy data from Parquet format to InfluxDB line protocol.

Handles conversion of ONS energy data including generation, consumption,
and transmission datasets with proper tag and field mapping.

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

### influxdb_client.py

InfluxDB client handler for the ONS Data Platform.

This module provides a robust InfluxDB client with connection management,
error handling, and retry logic for time series data operations.

**Functions:**

#### `__init__`

Initialize InfluxDB handler.

Args:
    url: InfluxDB URL (defaults to INFLUXDB_URL env var)
    token: InfluxDB token (defaults to INFLUXDB_TOKEN env var)
    org: InfluxDB organization (defaults to INFLUXDB_ORG env var)
    bucket: Default bucket name (defaults to INFLUXDB_BUCKET env var)
    timeout: Connection timeout in milliseconds
    max_retries: Maximum number of retry attempts
    retry_delay: Base delay between retries in seconds
    enable_gzip: Enable gzip compression for requests

**Parameters:**
- `self` (Any): 
- `url` (Any): 
- `token` (Any): 
- `org` (Any): 
- `bucket` (Any): 
- `timeout` (Any): 
- `max_retries` (Any): 
- `retry_delay` (Any): 
- `enable_gzip` (Any): 

#### `_get_token`

Retrieve InfluxDB token from environment or AWS Secrets Manager.

Returns:
    InfluxDB authentication token
    
Raises:
    ValueError: If token cannot be retrieved

**Parameters:**
- `self` (Any): 

#### `client`

Get or create InfluxDB client with connection pooling.

Returns:
    InfluxDB client instance

**Parameters:**
- `self` (Any): 

#### `write_api`

Get write API instance.

**Parameters:**
- `self` (Any): 

#### `query_api`

Get query API instance.

**Parameters:**
- `self` (Any): 

#### `health_check`

Perform health check on InfluxDB connection.

Returns:
    Health check results with status and metrics

**Parameters:**
- `self` (Any): 

#### `write_points`

Write points to InfluxDB with retry logic.

Args:
    points: Single point or list of points to write
    bucket: Target bucket (defaults to instance bucket)
    precision: Time precision for timestamps
    
Returns:
    True if write successful
    
Raises:
    InfluxDBWriteError: If write fails after all retries

**Parameters:**
- `self` (Any): 
- `points` (Any): 
- `bucket` (Any): 
- `precision` (Any): 

#### `query_flux`

Execute Flux query with retry logic.

Args:
    query: Flux query string
    params: Query parameters for parameterized queries
    
Returns:
    List of query results as dictionaries
    
Raises:
    InfluxDBQueryError: If query fails after all retries

**Parameters:**
- `self` (Any): 
- `query` (Any): 
- `params` (Any): 

#### `batch_writer`

Context manager for batch writing operations.

Args:
    batch_size: Number of points per batch
    flush_interval: Flush interval in milliseconds
    
Yields:
    Batch write API instance

**Parameters:**
- `self` (Any): 
- `batch_size` (Any): 
- `flush_interval` (Any): 

#### `close`

Close InfluxDB client and cleanup resources.

**Parameters:**
- `self` (Any): 

#### `__enter__`

Context manager entry.

**Parameters:**
- `self` (Any): 

#### `__exit__`

Context manager exit.

**Parameters:**
- `self` (Any): 
- `exc_type` (Any): 
- `exc_val` (Any): 
- `exc_tb` (Any): 

**Classes:**

#### `InfluxDBConnectionError`

Raised when InfluxDB connection fails.

#### `InfluxDBWriteError`

Raised when InfluxDB write operation fails.

#### `InfluxDBQueryError`

Raised when InfluxDB query operation fails.

#### `InfluxDBHandler`

InfluxDB client handler with connection management and error handling.

Provides robust connection management, automatic retries, and proper
error handling for InfluxDB operations in the ONS Data Platform.

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

### query_translator.py

Natural language to InfluxDB query translator for the ONS Data Platform.

This module provides functionality to translate natural language questions
about energy data into InfluxDB Flux and InfluxQL queries, with support
for parameter extraction and query generation logic.

**Functions:**

#### `create_query_translator`

Factory function to create a QueryTranslator instance.

Returns:
    QueryTranslator instance

#### `translate_natural_language_query`

Convenience function to translate natural language to InfluxDB query.

Args:
    question: Natural language question about energy data
    language: Target query language (Flux or InfluxQL)
    context: Additional context for query generation
    
Returns:
    Dictionary containing query, parameters, and metadata
    
Raises:
    QueryTranslationError: If translation fails

**Parameters:**
- `question` (Any): 
- `language` (Any): 
- `context` (Any): 

#### `__init__`

Initialize the query translator with templates and patterns.

**Parameters:**
- `self` (Any): 

#### `translate_query`

Translate natural language question to InfluxDB query.

Args:
    question: Natural language question about energy data
    language: Target query language (Flux or InfluxQL)
    context: Additional context for query generation
    
Returns:
    Dictionary containing query, parameters, and metadata
    
Raises:
    QueryTranslationError: If translation fails

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `language` (Any): 
- `context` (Any): 

#### `_normalize_question`

Normalize natural language question for processing.

Args:
    question: Raw natural language question
    
Returns:
    Normalized question string

**Parameters:**
- `self` (Any): 
- `question` (Any): 

#### `_identify_query_type`

Identify the type of query based on keywords and patterns.

Args:
    question: Normalized question string
    
Returns:
    QueryType enum value

**Parameters:**
- `self` (Any): 
- `question` (Any): 

#### `_extract_parameters`

Extract query parameters from natural language question.

Args:
    question: Normalized question string
    context: Additional context for parameter extraction
    
Returns:
    QueryParameters object with extracted parameters

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_time_range`

Extract time range from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_regions`

Extract regions from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_energy_sources`

Extract energy sources from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_measurement_types`

Extract measurement types from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_aggregation`

Extract aggregation type from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_filters`

Extract additional filters from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_limit`

Extract result limit from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_extract_group_by`

Extract group by fields from question.

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `context` (Any): 

#### `_generate_flux_query`

Generate Flux query from template and parameters.

Args:
    template: Query template
    parameters: Extracted parameters
    
Returns:
    Generated Flux query string

**Parameters:**
- `self` (Any): 
- `template` (Any): 
- `parameters` (Any): 

#### `_generate_influxql_query`

Generate InfluxQL query from template and parameters.

Args:
    template: Query template
    parameters: Extracted parameters
    
Returns:
    Generated InfluxQL query string

**Parameters:**
- `self` (Any): 
- `template` (Any): 
- `parameters` (Any): 

#### `_validate_parameters`

Validate that required parameters are present.

Args:
    template: Query template
    parameters: Extracted parameters
    
Raises:
    QueryTranslationError: If required parameters are missing

**Parameters:**
- `self` (Any): 
- `template` (Any): 
- `parameters` (Any): 

#### `_calculate_confidence_score`

Calculate confidence score for query translation.

Args:
    question: Normalized question
    query_type: Identified query type
    
Returns:
    Confidence score between 0 and 1

**Parameters:**
- `self` (Any): 
- `question` (Any): 
- `query_type` (Any): 

#### `_initialize_query_templates`

Initialize query templates for different query types.

**Parameters:**
- `self` (Any): 

#### `_initialize_time_patterns`

Initialize time range extraction patterns.

**Parameters:**
- `self` (Any): 

#### `_initialize_region_patterns`

Initialize region extraction patterns.

**Parameters:**
- `self` (Any): 

#### `_initialize_source_patterns`

Initialize energy source extraction patterns.

**Parameters:**
- `self` (Any): 

#### `_initialize_measurement_patterns`

Initialize measurement type extraction patterns.

**Parameters:**
- `self` (Any): 

#### `last_hour`

**Parameters:**
- `now` (Any): 

#### `last_day`

**Parameters:**
- `now` (Any): 

#### `last_week`

**Parameters:**
- `now` (Any): 

#### `last_month`

**Parameters:**
- `now` (Any): 

#### `last_year`

**Parameters:**
- `now` (Any): 

#### `today`

**Parameters:**
- `now` (Any): 

#### `yesterday`

**Parameters:**
- `now` (Any): 

**Classes:**

#### `QueryLanguage`

Supported query languages.

#### `QueryType`

Types of energy data queries.

#### `QueryParameters`

Parameters extracted from natural language query.

#### `QueryTemplate`

Template for generating InfluxDB queries.

#### `QueryTranslationError`

Raised when query translation fails.

#### `QueryTranslator`

Natural language to InfluxDB query translator.

Converts natural language questions about energy data into properly
formatted InfluxDB Flux and InfluxQL queries with parameter extraction
and validation.

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
- `influxdb-client>=1.40.0`
- `# Testing dependencies`
- `pytest>=7.4.0`
- `pytest-cov>=4.1.0`
- `moto>=4.2.0`
- `# Security and validation`
- `pydantic>=2.5.0`
- `jsonschema>=4.20.0`

