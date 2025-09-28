# InfluxDB Loader Lambda Function

This Lambda function loads processed Parquet data from S3 into Amazon Timestream for InfluxDB. It replaces the original Timestream loader as part of the migration to InfluxDB.

## Features

- **Batch Processing**: Configurable batch sizes for optimal performance
- **Error Handling**: Comprehensive retry logic with exponential backoff
- **Data Validation**: Schema validation and data quality checks
- **Monitoring**: CloudWatch metrics for performance and error tracking
- **Health Checks**: InfluxDB connectivity validation before processing
- **Flexible Configuration**: Environment-based configuration for different deployments

## Environment Variables

### Required
- `INFLUXDB_URL`: InfluxDB instance URL
- `INFLUXDB_ORG`: InfluxDB organization name
- `INFLUXDB_BUCKET`: Default bucket for time series data
- `INFLUXDB_TOKEN` or `INFLUXDB_TOKEN_SECRET_NAME`: Authentication token

### Optional
- `MAX_BATCH_SIZE`: Maximum points per batch (default: 1000)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `ENABLE_VALIDATION`: Enable data validation (default: true)
- `DROP_INVALID_RECORDS`: Drop invalid records instead of failing (default: true)

## Input Event Format

### S3 Event
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "bucket-name"},
        "object": {"key": "path/to/file.parquet"}
      }
    }
  ]
}
```

### Step Functions Input
```json
{
  "bucket": "bucket-name",
  "key": "path/to/file.parquet"
}
```

## Output Format

```json
{
  "statusCode": 200,
  "message": "Data loaded successfully",
  "timestamp": "2024-01-01T12:00:00.000000",
  "data": {
    "points_written": 1500,
    "batches_processed": 2,
    "dataset_type": "generation",
    "processing_time_seconds": 3.45,
    "conversion_stats": {
      "input_rows": 1500,
      "output_points": 1500,
      "conversion_rate": 1.0
    },
    "influxdb_health": {
      "status": "healthy",
      "response_time_ms": 45.2
    }
  }
}
```

## Data Processing Flow

1. **Event Processing**: Extract S3 bucket and key from Lambda event
2. **Dataset Type Detection**: Determine dataset type from S3 key path
3. **Health Check**: Verify InfluxDB connectivity and performance
4. **Data Loading**: Load Parquet file from S3 into pandas DataFrame
5. **Data Conversion**: Convert DataFrame to InfluxDB Point objects
6. **Validation**: Validate data schema and point structure (if enabled)
7. **Batch Writing**: Write points to InfluxDB in configurable batches
8. **Metrics**: Send performance and error metrics to CloudWatch
9. **Response**: Return processing results and statistics

## Error Handling

### Connection Errors
- InfluxDB connectivity issues result in 503 Service Unavailable
- Automatic retry with exponential backoff
- Health check validation before processing

### Data Errors
- Schema validation failures result in 400 Bad Request
- Invalid records can be dropped or cause processing failure
- Detailed error logging for troubleshooting

### Processing Errors
- Batch write failures trigger individual point writing
- Configurable retry attempts with backoff
- Comprehensive error metrics for monitoring

## Monitoring

### CloudWatch Metrics
- `ONS/InfluxDB/PointsWritten`: Number of points successfully written
- `ONS/InfluxDB/BatchesProcessed`: Number of batches processed
- `ONS/InfluxDB/ProcessingTime`: Total processing time in seconds
- `ONS/InfluxDB/ConversionRate`: Data conversion success rate
- `ONS/InfluxDB/SuccessRate`: Batch write success rate
- `ONS/InfluxDB/ProcessingErrors`: Error count by type
- `ONS/InfluxDB/FailedBatches`: Number of failed batch writes

### Logging
- Structured logging with correlation IDs
- Debug information for data conversion
- Error details with stack traces
- Performance metrics and timing

## Dataset Types

The function supports three dataset types automatically detected from S3 key:

### Generation Data
- **Path Pattern**: `dataset=generation`
- **Measurement**: `generation_data`
- **Tags**: region, energy_source, measurement_type, quality_flag
- **Fields**: power_mw, capacity_factor, efficiency

### Consumption Data
- **Path Pattern**: `dataset=consumption`
- **Measurement**: `consumption_data`
- **Tags**: region, consumer_type, measurement_type, quality_flag
- **Fields**: consumption_mwh, demand_mw, load_factor

### Transmission Data
- **Path Pattern**: `dataset=transmission`
- **Measurement**: `transmission_data`
- **Tags**: region, line_id, measurement_type, quality_flag
- **Fields**: flow_mw, losses_mwh, voltage_kv

## Dependencies

- `influxdb-client`: InfluxDB Python client library
- `pandas`: Data manipulation and analysis
- `numpy`: Numerical computing support
- `boto3`: AWS SDK for Python
- `pyarrow`: Parquet file support

## Testing

Run unit tests:
```bash
python -m pytest test_lambda_function.py -v
```

Run integration tests:
```bash
python -m pytest test_integration.py -v
```

## Deployment

The function is deployed via Terraform using the Lambda module. See `infra/modules/lambda/main.tf` for configuration details.