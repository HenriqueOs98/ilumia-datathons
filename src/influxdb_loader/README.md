# InfluxDB Loader Lambda Function

This Lambda function loads processed Parquet data from S3 into Amazon Timestream for InfluxDB. It's designed to replace the existing Timestream loader as part of the migration to InfluxDB.

## Features

- **Batch Processing**: Configurable batch sizes for optimal performance
- **Error Handling**: Comprehensive error handling with retry logic
- **Data Validation**: Schema validation and data quality checks
- **Monitoring**: CloudWatch metrics and health checks
- **Multiple Event Sources**: Supports S3 events, Step Functions, and API Gateway
- **Flexible Configuration**: Environment variable-based configuration

## Architecture

```
S3 Parquet Files → Lambda Trigger → InfluxDB Loader → Timestream for InfluxDB
                                         ↓
                                   CloudWatch Metrics
```

## Environment Variables

### Required
- `INFLUXDB_URL`: InfluxDB endpoint URL
- `INFLUXDB_ORG`: InfluxDB organization name (default: 'ons-energy')
- `INFLUXDB_BUCKET`: InfluxDB bucket name (default: 'energy_data')

### Optional
- `INFLUXDB_TOKEN`: InfluxDB authentication token (can also use Secrets Manager)
- `INFLUXDB_TOKEN_SECRET_NAME`: AWS Secrets Manager secret name for InfluxDB token
- `MAX_BATCH_SIZE`: Maximum points per batch (default: 1000)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `ENABLE_METRICS`: Enable CloudWatch metrics (default: true)
- `VALIDATE_SCHEMA`: Enable data schema validation (default: true)
- `DROP_INVALID_RECORDS`: Drop invalid records instead of failing (default: true)

## Supported Event Formats

### S3 Event Notification
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "my-bucket"},
        "object": {"key": "path/to/file.parquet"}
      }
    }
  ]
}
```

### Step Functions Input
```json
{
  "bucket": "my-bucket",
  "key": "path/to/file.parquet"
}
```

### API Gateway Event
```json
{
  "body": "{\"bucket\": \"my-bucket\", \"key\": \"path/to/file.parquet\"}"
}
```

## Data Processing Flow

1. **Event Processing**: Extract S3 bucket and key from event
2. **Dataset Detection**: Determine dataset type from S3 key path
3. **Health Check**: Verify InfluxDB connectivity
4. **Data Loading**: Load Parquet file from S3
5. **Data Conversion**: Convert to InfluxDB Point objects
6. **Validation**: Validate points and schema
7. **Batch Writing**: Write points to InfluxDB in batches
8. **Metrics**: Send processing metrics to CloudWatch

## Dataset Types

The function automatically detects dataset types from S3 object keys:

- **Generation Data**: `dataset=generation` or path contains 'generation'
- **Consumption Data**: `dataset=consumption` or path contains 'consumption'
- **Transmission Data**: `dataset=transmission` or path contains 'transmission'

## Error Handling

### Error Types
- `DataConversionError`: Issues converting Parquet to InfluxDB format
- `InfluxDBConnectionError`: InfluxDB connectivity problems
- `InfluxDBWriteError`: Write operation failures
- `UnexpectedError`: Other unexpected errors

### Retry Logic
- Exponential backoff for transient errors
- Configurable maximum retry attempts
- Circuit breaker for persistent failures

### Error Recovery
- Invalid records can be dropped or cause function failure
- Failed batches are logged and optionally skipped
- Comprehensive error metrics sent to CloudWatch

## Monitoring

### CloudWatch Metrics
- `PointsWritten`: Number of points successfully written
- `BatchesProcessed`: Number of batches processed
- `ProcessingTime`: Total processing time in seconds
- `SourceRecords`: Number of source records from Parquet
- `ConversionRate`: Percentage of records successfully converted
- `BatchSuccessRate`: Percentage of batches successfully written
- `FailedBatches`: Number of failed batches
- `ProcessingErrors`: Count of processing errors by type

### Health Checks
- InfluxDB connectivity verification
- Write/read capability testing
- Performance metrics collection

## Performance Considerations

### Batch Size Optimization
- Default batch size: 1000 points
- Adjust based on data volume and InfluxDB performance
- Monitor write latency and throughput metrics

### Memory Usage
- Processes entire Parquet file in memory
- Consider file size limits for Lambda memory configuration
- Use streaming for very large files if needed

### Concurrency
- Lambda can process multiple files concurrently
- InfluxDB connection pooling handles concurrent writes
- Monitor InfluxDB resource utilization

## Testing

### Unit Tests
```bash
# Run unit tests
python -m pytest tests/unit/test_influxdb_loader.py -v
```

### Integration Tests
```bash
# Run integration tests with real InfluxDB
python -m pytest tests/integration/test_influxdb_integration.py -v
```

### Load Testing
```bash
# Run load tests
python -m pytest tests/load/test_influxdb_load.py -v
```

## Deployment

### Lambda Configuration
- Runtime: Python 3.9+
- Memory: 512MB - 3008MB (based on data volume)
- Timeout: 15 minutes maximum
- VPC: Required for InfluxDB access

### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:influxdb-token-*"
    }
  ]
}
```

### Lambda Layers
- Shared utilities layer with InfluxDB client and data conversion utilities
- Python dependencies layer with required packages

## Migration from Timestream Loader

### Key Differences
1. **Database Client**: Uses InfluxDB client instead of Timestream client
2. **Data Format**: Converts to InfluxDB line protocol instead of Timestream records
3. **Batch Processing**: Optimized for InfluxDB write patterns
4. **Error Handling**: Enhanced error handling for InfluxDB-specific issues
5. **Monitoring**: Additional metrics for InfluxDB performance

### Migration Steps
1. Deploy InfluxDB infrastructure
2. Deploy InfluxDB loader Lambda
3. Update S3 triggers to use new function
4. Validate data processing
5. Decommission old Timestream loader

## Troubleshooting

### Common Issues

#### Connection Errors
- Verify InfluxDB URL and credentials
- Check VPC and security group configuration
- Validate network connectivity

#### Write Errors
- Check InfluxDB resource limits
- Verify data format and schema
- Monitor batch size and memory usage

#### Performance Issues
- Adjust batch size configuration
- Monitor InfluxDB resource utilization
- Consider Lambda memory allocation

### Debugging
- Enable debug logging: Set log level to DEBUG
- Check CloudWatch logs for detailed error information
- Use health check endpoint for connectivity testing
- Monitor CloudWatch metrics for performance insights

## Support

For issues and questions:
1. Check CloudWatch logs for error details
2. Review CloudWatch metrics for performance issues
3. Validate InfluxDB connectivity and configuration
4. Consult the troubleshooting guide above