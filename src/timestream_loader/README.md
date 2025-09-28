# Timestream Loader Lambda Function

This Lambda function loads processed Parquet data from S3 into Amazon Timestream for time series analysis.

## Overview

The Timestream Loader is responsible for:
- Loading processed Parquet files from S3
- Validating data schema and quality
- Converting data to Timestream record format
- Batch loading data into appropriate Timestream tables
- Error handling and retry logic
- Monitoring and alerting

## Architecture

```
S3 Processed Data → Lambda Function → Amazon Timestream
                         ↓
                   CloudWatch Metrics
```

## Features

### Data Processing
- **Multi-format Support**: Handles generation, consumption, and transmission data
- **Schema Validation**: Validates data structure before loading
- **Batch Processing**: Processes data in configurable batches for optimal performance
- **Error Handling**: Comprehensive error handling with exponential backoff retry

### Monitoring
- **CloudWatch Metrics**: Custom metrics for records processed, batches, and errors
- **CloudWatch Alarms**: Automated alerting for failures and performance issues
- **Structured Logging**: Detailed logging for troubleshooting

### Performance
- **Optimized Batching**: Configurable batch sizes for optimal throughput
- **Memory Management**: Efficient memory usage for large datasets
- **Timeout Handling**: 15-minute timeout for processing large files

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TIMESTREAM_DATABASE_NAME` | Timestream database name | Required |
| `GENERATION_TABLE_NAME` | Generation data table name | Required |
| `CONSUMPTION_TABLE_NAME` | Consumption data table name | Required |
| `TRANSMISSION_TABLE_NAME` | Transmission data table name | Required |
| `MAX_BATCH_SIZE` | Maximum records per batch | 100 |
| `MAX_RETRIES` | Maximum retry attempts | 3 |

### IAM Permissions

The Lambda function requires the following permissions:
- `timestream:WriteRecords` - Write data to Timestream
- `timestream:DescribeEndpoints` - Get Timestream endpoints
- `s3:GetObject` - Read Parquet files from S3
- `s3:ListBucket` - List S3 bucket contents
- `cloudwatch:PutMetricData` - Send custom metrics
- `logs:*` - CloudWatch Logs access

## Data Schema

### Input Schema (Parquet)
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "region": "SE",
  "value": 100.5,
  "unit": "MW",
  "energy_source": "hydro",
  "measurement_type": "power",
  "quality_flag": "good"
}
```

### Timestream Record Format
```json
{
  "Time": "1704067200000",
  "TimeUnit": "MILLISECONDS",
  "Dimensions": [
    {"Name": "region", "Value": "SE"},
    {"Name": "dataset_type", "Value": "generation"},
    {"Name": "energy_source", "Value": "hydro"},
    {"Name": "measurement_type", "Value": "power"},
    {"Name": "quality_flag", "Value": "good"}
  ],
  "MeasureName": "value",
  "MeasureValue": "100.5",
  "MeasureValueType": "DOUBLE"
}
```

## Event Sources

### S3 Event
```json
{
  "Records": [{
    "s3": {
      "bucket": {"name": "processed-bucket"},
      "object": {"key": "dataset=generation/year=2024/file.parquet"}
    }
  }]
}
```

### Step Functions Event
```json
{
  "bucket": "processed-bucket",
  "key": "dataset=generation/year=2024/file.parquet"
}
```

## Error Handling

### Retry Logic
- **Throttling**: Exponential backoff for `ThrottlingException`
- **Transient Errors**: Automatic retry with configurable attempts
- **Permanent Errors**: Immediate failure with detailed logging

### Error Types
- **Schema Validation**: Invalid data structure or types
- **Timestream Errors**: Service limits, throttling, or configuration issues
- **S3 Errors**: File not found, access denied, or format issues

## Monitoring

### CloudWatch Metrics
- `ONS/Timestream/RecordsProcessed` - Number of records processed
- `ONS/Timestream/BatchesProcessed` - Number of batches processed
- `ONS/Timestream/ProcessingErrors` - Number of processing errors

### CloudWatch Alarms
- **Error Rate**: Triggers when error count exceeds threshold
- **Duration**: Triggers when processing time exceeds 10 minutes
- **Throttling**: Monitors for Timestream throttling events

## Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
python -m pytest test_lambda_function.py -v

# Run validation
python validate_implementation.py
```

### Deployment
The function is deployed via Terraform as part of the infrastructure stack.

## Troubleshooting

### Common Issues

1. **Schema Validation Errors**
   - Check data types and required columns
   - Verify timestamp format (ISO 8601)

2. **Timestream Throttling**
   - Reduce batch size
   - Implement exponential backoff
   - Check service limits

3. **Memory Issues**
   - Process data in smaller chunks
   - Optimize DataFrame operations
   - Monitor memory usage

### Debugging
- Check CloudWatch Logs for detailed error messages
- Monitor custom metrics for processing patterns
- Use validation script to test data compatibility

## Performance Tuning

### Batch Size Optimization
- Start with 100 records per batch
- Increase for smaller records, decrease for larger ones
- Monitor throttling and adjust accordingly

### Memory Optimization
- Process data in chunks for large files
- Use efficient pandas operations
- Clear DataFrames after processing

### Timeout Management
- Monitor processing duration
- Split large files if necessary
- Optimize data transformation logic