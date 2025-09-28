# Lambda Router Function

This Lambda function analyzes incoming file metadata and determines the appropriate processing path for ONS data files.

## Overview

The Lambda Router is the first component in the ONS Data Platform processing pipeline. It receives file metadata from EventBridge or Step Functions and makes intelligent routing decisions based on:

- File type (CSV, XLSX, PDF)
- File size (determines Lambda vs Batch processing)
- Content analysis for dataset type classification

## Supported File Formats

### Structured Data (CSV/XLSX/Parquet)
- **Small files (< 100MB)**: Routed to Lambda processing
- **Large files (≥ 100MB)**: Routed to AWS Batch processing
- **Parquet files**: Optimized processing path with Parquet-to-Parquet optimization

### Unstructured Data (PDF)
- **All PDF files**: Always routed to AWS Batch (requires specialized libraries)

**Default Output Format**: All processed data is converted to Parquet format for optimal storage and query performance.

## Configuration

### Environment Variables

- `LAMBDA_SIZE_THRESHOLD_MB`: Size threshold for Lambda vs Batch routing (default: 100)
- `PROCESSED_BUCKET`: S3 bucket for processed data output (default: ons-data-platform-processed)

### Input Event Formats

The function supports multiple event sources:

#### S3 Event via EventBridge
```json
{
  "Records": [{
    "s3": {
      "bucket": {"name": "source-bucket"},
      "object": {
        "key": "data/file.csv",
        "size": 1048576
      }
    }
  }]
}
```

#### EventBridge Event
```json
{
  "detail": {
    "bucket": {"name": "source-bucket"},
    "object": {
      "key": "data/file.csv",
      "size": 1048576
    }
  }
}
```

#### Direct Invocation
```json
{
  "bucket": "source-bucket",
  "key": "data/file.csv",
  "size": 1048576
}
```

## Output Format

```json
{
  "statusCode": 200,
  "body": {
    "processingType": "lambda|batch",
    "processorConfig": {
      "functionName": "processor-function",
      "memory": 3008,
      "timeout": 900,
      "environment": {...}
    },
    "outputLocation": "s3://processed-bucket/dataset=type/year=2024/month=01/",
    "inputFile": {
      "bucket": "source-bucket",
      "key": "data/file.csv",
      "size_mb": 1.0,
      "format": ".csv"
    }
  }
}
```

## Dataset Type Detection

The function automatically detects dataset types based on filename patterns:

- **Generation**: Files containing "geracao", "generation", "gen"
- **Consumption**: Files containing "consumo", "consumption", "cons"
- **Transmission**: Files containing "transmissao", "transmission", "trans"
- **General**: Fallback for unrecognized patterns

## Resource Allocation

### Lambda Processing
- Memory: 3008 MB (maximum for CPU optimization)
- Timeout: 15 minutes
- Runtime: Python 3.11

### Batch Processing
Resource allocation based on file size:
- **< 500MB**: 1 vCPU, 4GB memory
- **500MB - 1GB**: 2 vCPUs, 8GB memory
- **> 1GB**: 4 vCPUs, 16GB memory

## Error Handling

- **Unsupported file formats**: Returns 500 error with descriptive message
- **Missing file information**: Returns 500 error for missing bucket/key
- **Processing failures**: Logged to CloudWatch with full error context

## Testing

Run the validation script to test basic functionality:

```bash
python3 validate_function.py
```

For comprehensive testing with pytest (when available):

```bash
python3 -m pytest test_lambda_function.py -v
```

## Deployment

This function is designed to be deployed as part of the ONS Data Platform infrastructure using Terraform. The deployment includes:

- Lambda function with appropriate IAM roles
- EventBridge rules for S3 event routing
- CloudWatch log groups with retention policies
- Environment variable configuration

## Requirements

See `requirements.txt` for Python dependencies. The function uses minimal dependencies to reduce cold start times:

- boto3: AWS SDK for Python
- botocore: Low-level AWS service access

## Integration

This function integrates with:

- **EventBridge**: Receives S3 object creation events
- **Step Functions**: Orchestrates the processing workflow
- **Lambda Processor**: Handles structured data processing (CSV/XLSX → Parquet)
- **Lambda Parquet Processor**: Handles Parquet optimization and validation
- **AWS Batch**: Handles large files and PDF processing (all → Parquet)
- **CloudWatch**: Logging and monitoring

## Processing Workflows

### CSV/XLSX Files
1. **Input**: CSV or XLSX files
2. **Processing**: Data cleaning, validation, standardization
3. **Output**: Optimized Parquet files with partitioning

### Parquet Files
1. **Input**: Existing Parquet files
2. **Processing**: Validation, optimization, re-partitioning if needed
3. **Output**: Optimized Parquet files

### PDF Files
1. **Input**: PDF documents with tabular data
2. **Processing**: Table extraction, data standardization
3. **Output**: Structured Parquet files