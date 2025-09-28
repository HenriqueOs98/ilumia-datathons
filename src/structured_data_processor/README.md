# Structured Data Processor Lambda

This Lambda function processes structured data files (CSV and XLSX) from the ONS (Operador Nacional do Sistema Elétrico) data platform. It performs data cleaning, validation, standardization, and converts the data to optimized Parquet format with proper partitioning.

## Features

- **Multi-format Support**: Processes CSV and XLSX files with automatic format detection
- **Data Cleaning**: Removes duplicates, handles missing values, and removes statistical outliers
- **Data Validation**: Validates and converts data types, standardizes column names
- **Data Standardization**: Applies consistent schema and adds processing metadata
- **Parquet Conversion**: Saves processed data in Parquet format with optimal partitioning
- **Error Handling**: Comprehensive error handling with failed file management
- **Quality Scoring**: Calculates data quality scores based on completeness

## Architecture

The processor follows a pipeline approach:

1. **File Reading**: Reads CSV/XLSX files from S3 using AWS Data Wrangler
2. **Data Cleaning**: Removes empty rows/columns, handles duplicates and missing values
3. **Data Validation**: Converts data types and validates content
4. **Data Standardization**: Applies consistent schema and naming conventions
5. **Parquet Conversion**: Saves to S3 with partitioning strategy
6. **Metadata Generation**: Creates processing metadata and quality metrics

## Data Processing Pipeline

```
S3 Raw File → Read → Clean → Validate → Standardize → Parquet → S3 Processed
                ↓
            Error Handling → Failed Bucket
```

## Input/Output Schema

### Input Files
- **CSV**: Comma, semicolon, or tab-separated values
- **XLSX**: Excel format with automatic sheet detection
- **Encoding**: UTF-8, Latin-1, or ISO-8859-1 support

### Output Schema (Parquet)
```json
{
  "timestamp": "datetime",
  "value": "float",
  "region": "string",
  "energy_source": "string", 
  "measurement_type": "string",
  "unit": "string",
  "quality_flag": "string",
  "processing_metadata_processed_at": "datetime",
  "processing_metadata_processor_version": "string",
  "processing_metadata_source_file": "string"
}
```

## Partitioning Strategy

Files are partitioned in S3 using the following structure:
```
s3://processed-bucket/
├── dataset=generation/
│   ├── year=2024/
│   │   ├── month=01/
│   │   └── month=02/
├── dataset=consumption/
└── dataset=transmission/
```

## Environment Variables

- `PROCESSED_BUCKET`: S3 bucket for processed Parquet files (default: `ons-data-platform-processed`)
- `FAILED_BUCKET`: S3 bucket for failed processing files (default: `ons-data-platform-failed`)

## Event Formats

### S3 Event (EventBridge)
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "source-bucket"},
        "object": {"key": "data/file.csv"}
      }
    }
  ]
}
```

### Direct Invocation
```json
{
  "bucket": "source-bucket",
  "key": "data/file.csv"
}
```

## Data Quality Features

### Column Name Standardization
- Converts Portuguese terms to English equivalents
- Applies snake_case naming convention
- Removes special characters and extra spaces

### Missing Value Handling
- Numeric columns: Filled with median values
- Categorical columns: Filled with 'unknown' or mode
- Timestamp columns: Converted to datetime with error handling

### Outlier Detection
- Uses IQR method for numeric columns
- Configurable bounds (1.5 * IQR)
- Logs outlier removal statistics

### Data Type Validation
- Automatic timestamp detection and conversion
- Numeric value validation and conversion
- String standardization for categorical data

## Error Handling

### Processing Errors
- **File Format Errors**: Unsupported formats are rejected
- **Data Quality Issues**: Low-quality data is flagged but processed
- **Conversion Errors**: Failed conversions are logged and handled gracefully

### Failed File Management
- Failed files are moved to dedicated S3 bucket
- Error metadata is attached to failed files
- Processing errors are logged with full context

## Testing

The module includes comprehensive unit tests covering:

- Data cleaning and validation scenarios
- File format handling (CSV, XLSX)
- Error conditions and edge cases
- Performance with large datasets
- Unicode and special character handling
- End-to-end processing workflows

Run tests with:
```bash
python -m pytest test_lambda_function.py -v
```

## Performance Considerations

- **Memory**: Configured for 3008 MB (maximum Lambda memory)
- **Timeout**: 15 minutes for large file processing
- **Concurrency**: Supports parallel processing of multiple files
- **Optimization**: Uses AWS Data Wrangler for efficient S3 operations

## Monitoring and Observability

The function provides comprehensive logging:
- Processing statistics (records processed, quality scores)
- Performance metrics (processing time, file sizes)
- Error details with full stack traces
- Data quality metrics and warnings

## Dependencies

- `pandas`: Data manipulation and analysis
- `awswrangler`: AWS data processing utilities
- `boto3`: AWS SDK for Python
- `pyarrow`: Parquet file format support
- `openpyxl`: Excel file reading
- `xlrd`: Legacy Excel file support

## Deployment

This Lambda function is deployed as part of the ONS Data Platform infrastructure using Terraform. The deployment includes:

- Lambda function configuration
- IAM roles and policies
- S3 bucket permissions
- CloudWatch logging setup
- Environment variable configuration