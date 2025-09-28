# Migration Orchestrator

This Lambda function coordinates the entire migration process from Amazon Timestream to InfluxDB using AWS Step Functions. It provides comprehensive orchestration with error handling, progress tracking, notifications, and rollback capabilities.

## Features

- **Step Functions Integration**: Orchestrates complex migration workflows
- **Progress Tracking**: Real-time status updates and progress monitoring
- **Error Handling**: Comprehensive error handling with automatic retries
- **Rollback Capabilities**: Automatic rollback on failure if enabled
- **SNS Notifications**: Real-time notifications for migration events
- **DynamoDB Persistence**: Job status and metadata persistence
- **Cancellation Support**: Ability to cancel running migrations

## Architecture

The orchestrator manages two main Step Functions state machines:

1. **Migration State Machine**: Handles the complete migration workflow
   - Data export from Timestream
   - Data validation (optional)
   - Data loading to InfluxDB
   - Progress notifications

2. **Rollback State Machine**: Handles rollback operations
   - InfluxDB data cleanup
   - S3 export data cleanup
   - Status notifications

## Environment Variables

- `MIGRATION_STATE_MACHINE_ARN`: ARN of the migration Step Functions state machine
- `ROLLBACK_STATE_MACHINE_ARN`: ARN of the rollback Step Functions state machine
- `MIGRATION_JOBS_TABLE`: DynamoDB table name for job tracking (default: migration-jobs)
- `NOTIFICATION_TOPIC_ARN`: SNS topic ARN for notifications
- `S3_EXPORT_BUCKET`: S3 bucket for temporary data export

## API Actions

### Start Migration
```json
{
  "action": "start_migration",
  "migration_config": {
    "job_id": "migration_001",
    "job_name": "Production Migration",
    "source_database": "ons_energy_data",
    "source_table": "generation_data",
    "target_bucket": "generation_data",
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-31T23:59:59Z",
    "batch_size": 10000,
    "validation_enabled": true,
    "rollback_enabled": true,
    "notification_topic_arn": "arn:aws:sns:us-east-1:123456789012:migration-notifications"
  }
}
```

### Get Job Status
```json
{
  "action": "get_status",
  "job_id": "migration_001"
}
```

### Cancel Migration
```json
{
  "action": "cancel_migration",
  "job_id": "migration_001"
}
```

## Job Status Flow

1. **pending**: Job created but not started
2. **running**: Migration in progress
   - **export**: Exporting data from Timestream
   - **validation**: Validating exported data (if enabled)
   - **migration**: Loading data to InfluxDB
3. **completed**: Migration completed successfully
4. **failed**: Migration failed (rollback may be initiated)
5. **cancelled**: Migration cancelled by user

## Error Handling

- **Automatic Retries**: Configurable retry logic for transient failures
- **Circuit Breaker**: Fail-fast for persistent errors
- **Rollback**: Automatic cleanup on failure (if enabled)
- **Notifications**: Real-time error notifications via SNS

## Monitoring

The orchestrator provides comprehensive monitoring through:

- **CloudWatch Logs**: Detailed execution logs
- **CloudWatch Metrics**: Custom metrics for job status and performance
- **SNS Notifications**: Real-time status updates
- **DynamoDB**: Persistent job status and metadata

## Usage Examples

### Basic Migration
```python
import boto3
import json

lambda_client = boto3.client('lambda')

response = lambda_client.invoke(
    FunctionName='migration-orchestrator',
    Payload=json.dumps({
        'action': 'start_migration',
        'migration_config': {
            'source_database': 'ons_energy_data',
            'source_table': 'generation_data',
            'target_bucket': 'generation_data',
            'start_time': '2024-01-01T00:00:00Z',
            'end_time': '2024-01-31T23:59:59Z'
        }
    })
)

result = json.loads(response['Payload'].read())
print(f"Job ID: {result['body']['job_id']}")
```

### Monitor Progress
```python
# Check job status
response = lambda_client.invoke(
    FunctionName='migration-orchestrator',
    Payload=json.dumps({
        'action': 'get_status',
        'job_id': 'migration_001'
    })
)

status = json.loads(response['Payload'].read())
print(f"Status: {status['body']['job']['status']}")
print(f"Progress: {status['body']['job']['progress_percentage']}%")
```

## Deployment

The orchestrator requires the following AWS resources:

1. **Lambda Function**: The orchestrator function itself
2. **Step Functions**: Migration and rollback state machines
3. **DynamoDB Table**: Job tracking table
4. **SNS Topic**: Notification topic
5. **IAM Roles**: Appropriate permissions for all services

See the Terraform configuration in `infra/modules/` for complete deployment setup.

## Testing

Run unit tests:
```bash
python -m pytest test_lambda_function.py -v
```

Run integration tests:
```bash
python -m pytest integration_test.py -v
```

## Troubleshooting

### Common Issues

1. **State Machine Not Found**: Verify `MIGRATION_STATE_MACHINE_ARN` environment variable
2. **DynamoDB Access Denied**: Check IAM permissions for DynamoDB operations
3. **SNS Publish Failed**: Verify SNS topic ARN and permissions
4. **Step Functions Execution Failed**: Check individual Lambda function logs

### Debugging

Enable debug logging by setting the Lambda environment variable:
```
LOG_LEVEL=DEBUG
```

Check CloudWatch logs for detailed execution traces and error messages.