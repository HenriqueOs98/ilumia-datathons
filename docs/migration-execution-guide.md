# Timestream to InfluxDB Migration Execution Guide

This guide provides step-by-step instructions for executing the complete data migration from Amazon Timestream to InfluxDB using the migration infrastructure and scripts.

## Prerequisites

### Infrastructure Requirements

1. **InfluxDB Infrastructure**: Ensure the Timestream for InfluxDB cluster is deployed and accessible
2. **Lambda Functions**: Migration orchestrator, data validator, and InfluxDB loader functions must be deployed
3. **Step Functions**: Migration state machine must be configured and accessible
4. **S3 Buckets**: Export bucket for temporary data storage must be available
5. **IAM Permissions**: Appropriate permissions for Timestream, InfluxDB, S3, Lambda, and Step Functions

### Environment Variables

Set the following environment variables before running migration scripts:

```bash
export MIGRATION_ORCHESTRATOR_LAMBDA_ARN="arn:aws:lambda:region:account:function:migration-orchestrator"
export MIGRATION_STATE_MACHINE_ARN="arn:aws:states:region:account:stateMachine:migration-state-machine"
export S3_EXPORT_BUCKET="your-migration-export-bucket"
export NOTIFICATION_TOPIC_ARN="arn:aws:sns:region:account:migration-notifications"
export INFLUXDB_URL="https://your-influxdb-endpoint:8086"
export INFLUXDB_TOKEN="your-influxdb-token"
export INFLUXDB_ORG="ons-energy"
```

### Python Dependencies

Install required Python packages:

```bash
pip install boto3 pyyaml pandas influxdb-client
```

## Migration Process Overview

The migration process consists of the following phases:

1. **Pre-Migration Validation**: Verify infrastructure and configuration
2. **Data Export**: Export data from Timestream to S3
3. **Data Conversion**: Convert Timestream data to InfluxDB line protocol
4. **Data Loading**: Load converted data into InfluxDB
5. **Data Validation**: Verify data integrity and completeness
6. **Post-Migration Cleanup**: Clean up temporary resources

## Step-by-Step Execution

### Step 1: Configuration

Create or customize the migration configuration file:

```bash
# Copy the default configuration
cp scripts/migration_config.yaml my_migration_config.yaml

# Edit the configuration to match your requirements
vim my_migration_config.yaml
```

Key configuration parameters:

- **migration_jobs**: List of tables to migrate with time ranges
- **parallel_jobs**: Number of concurrent migration jobs
- **validation_enabled**: Whether to validate data after migration
- **rollback_enabled**: Whether to enable automatic rollback on failure

### Step 2: Pre-Migration Validation

Validate the configuration and infrastructure before starting:

```bash
# Dry run to validate configuration
python scripts/execute_migration.py --config my_migration_config.yaml --dry-run

# Check infrastructure connectivity
python scripts/execute_migration.py --config my_migration_config.yaml --dry-run --region us-east-1
```

Expected output:
```
Configuration validation completed: 3 jobs validated
Prerequisites validation passed
All infrastructure components accessible
```

### Step 3: Execute Migration

Start the migration process:

```bash
# Execute migration with default settings
python scripts/execute_migration.py --config my_migration_config.yaml

# Execute with custom parallel job count
python scripts/execute_migration.py --config my_migration_config.yaml --parallel-jobs 2

# Execute with specific region
python scripts/execute_migration.py --config my_migration_config.yaml --region us-east-1
```

The script will:
1. Start migration jobs for each configured table
2. Monitor progress and display status updates
3. Handle errors and retries automatically
4. Generate a final summary report

### Step 4: Monitor Migration Progress

In a separate terminal, monitor the migration progress:

```bash
# Monitor all active migrations
python scripts/monitor_migration.py --auto-discover

# Monitor specific job IDs
python scripts/monitor_migration.py --job-ids job1 job2 job3

# Monitor single job with detailed output
python scripts/monitor_migration.py --job-id specific-job-id --update-interval 30
```

The monitor will display:
- Real-time progress updates
- Current step for each job
- Record counts and processing rates
- Error messages and warnings

### Step 5: Validate Migration Results

After migration completion, validate the data integrity:

```bash
# Validate all migrated tables
python scripts/validate_migration.py --config my_migration_config.yaml

# Validate specific table
python scripts/validate_migration.py \
  --database ons_energy_data \
  --table generation_data \
  --bucket generation_data \
  --start-time "2023-01-01T00:00:00Z" \
  --end-time "2024-12-31T23:59:59Z"

# Run validations in parallel
python scripts/validate_migration.py --config my_migration_config.yaml --parallel
```

The validation will check:
- Record count consistency
- Data integrity using checksums
- Sample data accuracy
- Schema compatibility
- Time range coverage

## Migration Configuration Examples

### Basic Configuration

```yaml
migration_jobs:
  - job_name: "Generation Data Migration"
    source_database: "ons_energy_data"
    source_table: "generation_data"
    target_bucket: "generation_data"
    start_time: "2023-01-01T00:00:00Z"
    end_time: "2024-12-31T23:59:59Z"
    batch_size: 10000
    validation_enabled: true
    rollback_enabled: true

migration_settings:
  parallel_jobs: 1
  progress_monitoring_interval: 60
  max_retry_attempts: 3
```

### Production Configuration

```yaml
migration_jobs:
  - job_name: "Generation Data Migration"
    source_database: "ons_energy_data"
    source_table: "generation_data"
    target_bucket: "generation_data"
    start_time: "2023-01-01T00:00:00Z"
    end_time: "2024-12-31T23:59:59Z"
    batch_size: 50000
    validation_enabled: true
    rollback_enabled: false  # Manual approval required

migration_settings:
  parallel_jobs: 3
  progress_monitoring_interval: 30
  max_retry_attempts: 5
  retry_delay_seconds: 600

validation_rules:
  record_count_tolerance: 0.0001  # 0.01% tolerance
  sample_accuracy_threshold: 0.99
```

## Monitoring and Troubleshooting

### Real-Time Monitoring

Monitor migration progress using the monitoring script:

```bash
# Basic monitoring
python scripts/monitor_migration.py --job-ids job1 job2

# Detailed monitoring with custom intervals
python scripts/monitor_migration.py --job-id job1 --update-interval 15 --max-duration 7200
```

### Log Files

Migration logs are written to:
- `migration_execution.log`: Main execution log
- `migration_validation.log`: Validation log
- CloudWatch Logs: Lambda function logs

### Common Issues and Solutions

#### Issue: Migration Job Stuck in "Export" Step

**Symptoms**: Job remains in export step for extended period

**Solutions**:
1. Check Timestream query permissions
2. Verify S3 bucket write permissions
3. Check for large data volumes requiring longer processing time
4. Review CloudWatch logs for specific errors

```bash
# Check job status
python scripts/execute_migration.py --job-id stuck-job-id

# Cancel if necessary
python scripts/execute_migration.py --cancel-job stuck-job-id
```

#### Issue: Validation Failures

**Symptoms**: Data validation reports mismatches or errors

**Solutions**:
1. Check InfluxDB connectivity and permissions
2. Verify data conversion logic
3. Review time zone handling
4. Check for data type mismatches

```bash
# Run detailed validation
python scripts/validate_migration.py --database db --table table --bucket bucket \
  --start-time "2023-01-01T00:00:00Z" --end-time "2023-01-02T00:00:00Z"
```

#### Issue: Performance Issues

**Symptoms**: Slow migration or high resource usage

**Solutions**:
1. Reduce batch sizes in configuration
2. Decrease parallel job count
3. Check InfluxDB cluster resources
4. Optimize time ranges for smaller chunks

```yaml
migration_settings:
  parallel_jobs: 1  # Reduce parallelism
  
migration_jobs:
  - batch_size: 5000  # Smaller batches
```

### Emergency Procedures

#### Stopping Migration

To stop all running migrations:

```bash
# List active jobs
python scripts/monitor_migration.py --auto-discover

# Cancel specific jobs
python scripts/execute_migration.py --cancel-job job-id-1
python scripts/execute_migration.py --cancel-job job-id-2
```

#### Rollback Procedure

If rollback is enabled and automatic rollback fails:

1. Check rollback state machine execution
2. Manually clean up InfluxDB data if needed
3. Clean up S3 export data
4. Reset migration job status

## Post-Migration Tasks

### 1. Final Validation

Run comprehensive validation after all migrations complete:

```bash
python scripts/validate_migration.py --config my_migration_config.yaml --parallel
```

### 2. Performance Testing

Test query performance on migrated data:

```bash
# Test basic queries
influx query 'from(bucket:"generation_data") |> range(start:-1h) |> limit(n:10)'

# Test aggregation queries
influx query 'from(bucket:"generation_data") |> range(start:-24h) |> aggregateWindow(every:1h, fn:mean)'
```

### 3. Update Applications

Update application configurations to use InfluxDB:

1. Update Lambda function environment variables
2. Update API Gateway configurations
3. Update monitoring dashboards
4. Update documentation

### 4. Cleanup

Clean up migration resources:

```bash
# Clean up S3 export data (if no longer needed)
aws s3 rm s3://your-export-bucket/timestream-export/ --recursive

# Archive migration logs
tar -czf migration_logs_$(date +%Y%m%d).tar.gz *.log migration_results_*.json
```

## Validation Reports

The validation process generates several types of reports:

### HTML Report

Interactive HTML report with detailed results:
- Executive summary with overall status
- Table-by-table validation results
- Error and warning details
- Visual progress indicators

### JSON Report

Machine-readable JSON report for integration:
- Structured validation results
- Metrics and statistics
- Error details for automated processing

### Console Output

Real-time console output during validation:
- Progress indicators
- Status updates
- Error messages
- Summary statistics

## Best Practices

### 1. Migration Planning

- **Test in Development**: Always test migration process in development environment first
- **Incremental Migration**: Consider migrating data in time-based chunks
- **Backup Strategy**: Ensure Timestream data is backed up before migration
- **Rollback Plan**: Have a tested rollback procedure ready

### 2. Performance Optimization

- **Batch Sizing**: Optimize batch sizes based on data volume and complexity
- **Parallel Processing**: Use appropriate parallelism for your infrastructure
- **Resource Monitoring**: Monitor CPU, memory, and network usage during migration
- **Time Windows**: Schedule migrations during low-traffic periods

### 3. Data Validation

- **Comprehensive Testing**: Validate both data integrity and query functionality
- **Sample Validation**: Use representative data samples for thorough testing
- **Performance Validation**: Ensure query performance meets requirements
- **Business Logic Validation**: Test application-specific data transformations

### 4. Monitoring and Alerting

- **Real-Time Monitoring**: Use monitoring scripts for real-time progress tracking
- **Alert Configuration**: Set up alerts for failures and performance issues
- **Log Retention**: Maintain detailed logs for troubleshooting
- **Status Reporting**: Provide regular status updates to stakeholders

## Support and Troubleshooting

For additional support:

1. **Check Logs**: Review migration execution and validation logs
2. **AWS Documentation**: Consult AWS Timestream and InfluxDB documentation
3. **CloudWatch Metrics**: Monitor AWS service metrics and alarms
4. **Infrastructure Team**: Contact infrastructure team for AWS resource issues

## Appendix

### A. Environment Setup Script

```bash
#!/bin/bash
# setup_migration_environment.sh

# Set AWS region
export AWS_DEFAULT_REGION=us-east-1

# Get Terraform outputs
cd infra
MIGRATION_ORCHESTRATOR_ARN=$(terraform output -raw migration_orchestrator_lambda_arn)
MIGRATION_STATE_MACHINE_ARN=$(terraform output -raw migration_state_machine_arn)
S3_EXPORT_BUCKET=$(terraform output -raw migration_export_bucket)
NOTIFICATION_TOPIC_ARN=$(terraform output -raw migration_notification_topic_arn)

# Export environment variables
export MIGRATION_ORCHESTRATOR_LAMBDA_ARN="$MIGRATION_ORCHESTRATOR_ARN"
export MIGRATION_STATE_MACHINE_ARN="$MIGRATION_STATE_MACHINE_ARN"
export S3_EXPORT_BUCKET="$S3_EXPORT_BUCKET"
export NOTIFICATION_TOPIC_ARN="$NOTIFICATION_TOPIC_ARN"

# InfluxDB configuration (set these manually)
export INFLUXDB_URL="https://your-influxdb-endpoint:8086"
export INFLUXDB_TOKEN="your-influxdb-token"
export INFLUXDB_ORG="ons-energy"

echo "Migration environment configured successfully"
```

### B. Quick Start Commands

```bash
# 1. Setup environment
source setup_migration_environment.sh

# 2. Validate configuration
python scripts/execute_migration.py --config scripts/migration_config.yaml --dry-run

# 3. Start migration
python scripts/execute_migration.py --config scripts/migration_config.yaml

# 4. Monitor progress (in separate terminal)
python scripts/monitor_migration.py --auto-discover

# 5. Validate results
python scripts/validate_migration.py --config scripts/migration_config.yaml
```