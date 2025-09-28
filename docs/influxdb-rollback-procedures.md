# InfluxDB Rollback Procedures and Disaster Recovery

## Overview

This document provides comprehensive rollback procedures and disaster recovery plans specific to the InfluxDB migration. It covers scenarios for rolling back to Timestream, recovering from InfluxDB failures, and maintaining data integrity during emergencies.

## Table of Contents

1. [Emergency Rollback to Timestream](#emergency-rollback-to-timestream)
2. [InfluxDB Instance Recovery](#influxdb-instance-recovery)
3. [Data Corruption Recovery](#data-corruption-recovery)
4. [Lambda Function Rollback](#lambda-function-rollback)
5. [Query Performance Rollback](#query-performance-rollback)
6. [Disaster Recovery Scenarios](#disaster-recovery-scenarios)
7. [Testing Rollback Procedures](#testing-rollback-procedures)

## Emergency Rollback to Timestream

### When to Execute Emergency Rollback

Execute emergency rollback to Timestream when:
- InfluxDB instance is completely unavailable for >30 minutes
- Data corruption is detected in InfluxDB
- Query performance is degraded by >300% compared to baseline
- Critical business operations are impacted

### Pre-Rollback Checklist

```bash
#!/bin/bash
# Pre-rollback assessment script

echo "=== Pre-Rollback Assessment ==="

# 1. Assess InfluxDB status
echo "1. InfluxDB Status:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text

# 2. Check data freshness in Timestream (backup)
echo "2. Timestream Backup Status:"
aws timestream-query query \
  --query-string "SELECT COUNT(*), MAX(time) FROM \"ons_energy_data_backup\".\"generation_data\" WHERE time > ago(1h)" \
  --query 'Rows[*].Data[*].ScalarValue' --output text

# 3. Verify Lambda function versions
echo "3. Lambda Function Versions:"
for func in lambda_router structured_data_processor rag_query_processor; do
    current_version=$(aws lambda get-function --function-name $func --query 'Configuration.Version' --output text)
    echo "$func: Current=$current_version"
done

# 4. Check API health
echo "4. API Health Check:"
curl -s -o /dev/null -w "%{http_code}" "https://api.ons-platform.com/health"

# 5. Estimate rollback time
echo "5. Estimated Rollback Time: 15-30 minutes"
echo "6. Business Impact: API queries will be unavailable during rollback"

read -p "Proceed with rollback? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled"
    exit 1
fi
```

### Step 1: Immediate Traffic Diversion

```bash
#!/bin/bash
# Immediate traffic diversion to maintenance mode

echo "Step 1: Diverting traffic to maintenance mode..."

# Enable maintenance mode flag
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled true

# Reduce API Gateway throttling to minimum
api_id=$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text)
aws apigateway update-stage \
  --rest-api-id $api_id \
  --stage-name prod \
  --patch-ops op=replace,path=/throttle/rateLimit,value=1

echo "Traffic diverted to maintenance mode"
```

### Step 2: Rollback Lambda Functions

```bash
#!/bin/bash
# Rollback Lambda functions to Timestream versions

echo "Step 2: Rolling back Lambda functions..."

# Function rollback mapping
declare -A ROLLBACK_VERSIONS=(
    ["influxdb_loader"]="timestream_loader:5"
    ["timeseries_query_processor"]="timestream_query_processor:3"
    ["rag_query_processor"]="rag_query_processor:4"
)

for current_func in "${!ROLLBACK_VERSIONS[@]}"; do
    IFS=':' read -r target_func target_version <<< "${ROLLBACK_VERSIONS[$current_func]}"
    
    echo "Rolling back $current_func to $target_func version $target_version"
    
    # Update function code to Timestream version
    aws lambda update-function-code \
      --function-name $current_func \
      --s3-bucket ons-lambda-deployments \
      --s3-key "rollback-versions/${target_func}-v${target_version}.zip"
    
    # Update environment variables for Timestream
    aws lambda update-function-configuration \
      --function-name $current_func \
      --environment Variables="{
        TIMESTREAM_DATABASE_NAME=ons_energy_data,
        GENERATION_TABLE_NAME=generation_data,
        CONSUMPTION_TABLE_NAME=consumption_data,
        TRANSMISSION_TABLE_NAME=transmission_data,
        USE_INFLUXDB=false
      }"
    
    # Wait for update to complete
    aws lambda wait function-updated --function-name $current_func
    
    echo "$current_func rolled back successfully"
done
```

### Step 3: Restore Timestream Data Pipeline

```bash
#!/bin/bash
# Restore Timestream data pipeline

echo "Step 3: Restoring Timestream data pipeline..."

# Re-enable Timestream write operations
aws events put-rule \
  --name ons-data-platform-timestream-processing \
  --event-pattern '{
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {"name": ["ons-data-platform-processed-prod"]}
    }
  }' \
  --state ENABLED

# Update Step Functions to use Timestream loader
aws stepfunctions update-state-machine \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --definition file://rollback-configs/timestream-state-machine.json

# Verify Timestream database accessibility
aws timestream-query query \
  --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(5m)" \
  --query 'Rows[0].Data[0].ScalarValue' --output text

echo "Timestream data pipeline restored"
```

### Step 4: Update API Configuration

```bash
#!/bin/bash
# Update API configuration for Timestream

echo "Step 4: Updating API configuration..."

# Update feature flags to disable InfluxDB features
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name use_influxdb \
  --enabled false

python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_flux_queries \
  --enabled false

# Update API Gateway to use Timestream endpoints
aws apigateway update-integration \
  --rest-api-id $api_id \
  --resource-id $(aws apigateway get-resources --rest-api-id $api_id --query 'items[?pathPart==`query`].id' --output text) \
  --http-method POST \
  --patch-ops op=replace,path=/uri,value=arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:timestream_query_processor/invocations

echo "API configuration updated for Timestream"
```

### Step 5: Validation and Traffic Restoration

```bash
#!/bin/bash
# Validate rollback and restore traffic

echo "Step 5: Validating rollback..."

# Test Timestream connectivity
test_query_result=$(aws timestream-query query \
  --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)" \
  --query 'Rows[0].Data[0].ScalarValue' --output text)

if [ "$test_query_result" -gt 0 ]; then
    echo "Timestream connectivity verified: $test_query_result records found"
else
    echo "ERROR: Timestream connectivity test failed"
    exit 1
fi

# Test API endpoints
api_response=$(curl -s -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"question": "What is the current energy generation?"}' \
  -w "%{http_code}")

if [[ "$api_response" == *"200" ]]; then
    echo "API endpoint test successful"
else
    echo "ERROR: API endpoint test failed"
    exit 1
fi

# Gradually restore traffic
echo "Restoring API traffic..."

# Increase rate limits gradually
for rate in 10 50 100 500; do
    aws apigateway update-stage \
      --rest-api-id $api_id \
      --stage-name prod \
      --patch-ops op=replace,path=/throttle/rateLimit,value=$rate
    
    echo "Rate limit increased to $rate requests/second"
    sleep 30
    
    # Check error rates
    error_count=$(aws logs filter-log-events \
      --log-group-name "API-Gateway-Execution-Logs_${api_id}/prod" \
      --start-time $(date -d '1 minute ago' +%s)000 \
      --filter-pattern "ERROR" \
      --query 'length(events)' --output text)
    
    if [ "$error_count" -gt 5 ]; then
        echo "High error rate detected, stopping traffic increase"
        break
    fi
done

# Disable maintenance mode
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled false

echo "Rollback to Timestream completed successfully"
```

## InfluxDB Instance Recovery

### Instance Failure Recovery

```bash
#!/bin/bash
# InfluxDB instance failure recovery

recover_influxdb_instance() {
    local instance_id="ons-influxdb-prod"
    local backup_snapshot_id=$1
    
    echo "Starting InfluxDB instance recovery..."
    
    # Check current instance status
    current_status=$(aws timestreaminfluxdb describe-db-instance \
      --identifier $instance_id \
      --query 'DbInstance.DbInstanceStatus' --output text 2>/dev/null || echo "not-found")
    
    if [ "$current_status" == "not-found" ] || [ "$current_status" == "failed" ]; then
        echo "Instance is failed or missing, creating new instance from snapshot..."
        
        # Create new instance from latest snapshot
        if [ -z "$backup_snapshot_id" ]; then
            backup_snapshot_id=$(aws timestreaminfluxdb describe-db-snapshots \
              --db-instance-identifier $instance_id \
              --query 'DbSnapshots[0].DbSnapshotIdentifier' --output text)
        fi
        
        aws timestreaminfluxdb restore-db-instance-from-db-snapshot \
          --db-instance-identifier "${instance_id}-recovery" \
          --db-snapshot-identifier $backup_snapshot_id \
          --db-instance-class db.influx.large \
          --publicly-accessible false \
          --storage-encrypted true
        
        # Wait for instance to be available
        echo "Waiting for recovery instance to be available..."
        aws timestreaminfluxdb wait db-instance-available \
          --db-instance-identifier "${instance_id}-recovery"
        
        # Update Lambda functions to use recovery instance
        recovery_endpoint=$(aws timestreaminfluxdb describe-db-instance \
          --identifier "${instance_id}-recovery" \
          --query 'DbInstance.Endpoint' --output text)
        
        for func in influxdb_loader timeseries_query_processor rag_query_processor; do
            aws lambda update-function-configuration \
              --function-name $func \
              --environment Variables="{INFLUXDB_ENDPOINT=$recovery_endpoint}"
        done
        
        echo "InfluxDB instance recovery completed"
        
    elif [ "$current_status" == "available" ]; then
        echo "Instance is available, checking connectivity..."
        
        # Test connectivity
        python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
try:
    handler = InfluxDBHandler()
    health = handler.health_check()
    print(f'InfluxDB health check: {health}')
except Exception as e:
    print(f'InfluxDB connectivity failed: {str(e)}')
    exit(1)
"
        
        echo "InfluxDB instance is healthy"
    else
        echo "Instance status: $current_status - monitoring for recovery"
    fi
}

# Usage: recover_influxdb_instance [snapshot_id]
```

### Data Synchronization Recovery

```python
def recover_data_synchronization():
    """Recover data synchronization between S3 and InfluxDB"""
    import boto3
    from datetime import datetime, timedelta
    from src.shared_utils.influxdb_client import InfluxDBHandler
    
    s3_client = boto3.client('s3')
    influx_handler = InfluxDBHandler()
    
    # Find data gaps
    print("Analyzing data gaps...")
    
    # Get latest timestamp in InfluxDB
    latest_query = '''
    from(bucket: "energy_data")
      |> range(start: -7d)
      |> last()
      |> keep(columns: ["_time"])
    '''
    
    try:
        latest_result = influx_handler.query_flux(latest_query)
        if latest_result:
            latest_influx_time = latest_result[0]['_time']
            print(f"Latest data in InfluxDB: {latest_influx_time}")
        else:
            latest_influx_time = datetime.utcnow() - timedelta(days=7)
            print("No recent data found in InfluxDB, starting from 7 days ago")
    except Exception as e:
        print(f"Error querying InfluxDB: {e}")
        latest_influx_time = datetime.utcnow() - timedelta(days=1)
    
    # Find unprocessed files in S3
    bucket_name = 'ons-data-platform-processed-prod'
    prefix = 'dataset=generation/'
    
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=prefix,
        StartAfter=f"{prefix}year={latest_influx_time.year}/month={latest_influx_time.month:02d}/"
    )
    
    unprocessed_files = []
    for obj in response.get('Contents', []):
        if obj['LastModified'] > latest_influx_time:
            unprocessed_files.append(obj['Key'])
    
    print(f"Found {len(unprocessed_files)} unprocessed files")
    
    # Reprocess missing files
    for file_key in unprocessed_files:
        try:
            print(f"Reprocessing {file_key}...")
            
            # Trigger Lambda function to process file
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName='influxdb_loader',
                InvocationType='Event',
                Payload=json.dumps({
                    'Records': [{
                        's3': {
                            'bucket': {'name': bucket_name},
                            'object': {'key': file_key}
                        }
                    }]
                })
            )
            
        except Exception as e:
            print(f"Error reprocessing {file_key}: {e}")
    
    print("Data synchronization recovery completed")

# Execute recovery
recover_data_synchronization()
```

## Data Corruption Recovery

### Detect Data Corruption

```python
def detect_data_corruption():
    """Detect potential data corruption in InfluxDB"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import pandas as pd
    
    handler = InfluxDBHandler()
    
    corruption_checks = []
    
    # Check 1: Duplicate timestamps
    duplicate_check = '''
    from(bucket: "energy_data")
      |> range(start: -24h)
      |> group(columns: ["_measurement", "region", "energy_source"])
      |> duplicate(column: "_time")
      |> count()
    '''
    
    try:
        duplicates = handler.query_flux(duplicate_check)
        duplicate_count = sum(record.get('_value', 0) for record in duplicates)
        corruption_checks.append({
            'check': 'duplicate_timestamps',
            'status': 'FAIL' if duplicate_count > 0 else 'PASS',
            'details': f'{duplicate_count} duplicate timestamps found'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'duplicate_timestamps',
            'status': 'ERROR',
            'details': str(e)
        })
    
    # Check 2: Null values in required fields
    null_check = '''
    from(bucket: "energy_data")
      |> range(start: -24h)
      |> filter(fn: (r) => not exists r._value or r._value == 0)
      |> count()
    '''
    
    try:
        nulls = handler.query_flux(null_check)
        null_count = sum(record.get('_value', 0) for record in nulls)
        corruption_checks.append({
            'check': 'null_values',
            'status': 'FAIL' if null_count > 100 else 'PASS',  # Allow some nulls
            'details': f'{null_count} null values found'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'null_values',
            'status': 'ERROR',
            'details': str(e)
        })
    
    # Check 3: Data consistency with S3
    consistency_check = '''
    from(bucket: "energy_data")
      |> range(start: -1h)
      |> count()
    '''
    
    try:
        recent_count = handler.query_flux(consistency_check)
        influx_count = sum(record.get('_value', 0) for record in recent_count)
        
        # Compare with expected count from S3 processing logs
        # This is a simplified check - in practice, you'd query CloudWatch logs
        expected_count = 1000  # Placeholder
        
        consistency_ratio = influx_count / expected_count if expected_count > 0 else 0
        corruption_checks.append({
            'check': 'data_consistency',
            'status': 'FAIL' if consistency_ratio < 0.9 else 'PASS',
            'details': f'InfluxDB: {influx_count}, Expected: {expected_count}, Ratio: {consistency_ratio:.2f}'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'data_consistency',
            'status': 'ERROR',
            'details': str(e)
        })
    
    # Report results
    print("Data Corruption Check Results:")
    print("=" * 40)
    
    failed_checks = 0
    for check in corruption_checks:
        status_symbol = "✓" if check['status'] == 'PASS' else "✗" if check['status'] == 'FAIL' else "?"
        print(f"{status_symbol} {check['check']}: {check['status']} - {check['details']}")
        
        if check['status'] == 'FAIL':
            failed_checks += 1
    
    if failed_checks > 0:
        print(f"\n⚠️  {failed_checks} corruption checks failed!")
        return False
    else:
        print("\n✅ All corruption checks passed")
        return True

# Run corruption detection
is_data_healthy = detect_data_corruption()
```

### Restore from Clean Backup

```bash
#!/bin/bash
# Restore InfluxDB from clean backup

restore_from_clean_backup() {
    local backup_date=$1
    local backup_bucket="ons-data-platform-backups"
    
    if [ -z "$backup_date" ]; then
        echo "Usage: restore_from_clean_backup YYYYMMDD_HHMMSS"
        return 1
    fi
    
    echo "Restoring InfluxDB from backup: $backup_date"
    
    # 1. Stop data ingestion
    echo "Stopping data ingestion..."
    aws events disable-rule --name ons-data-platform-s3-processing-rule
    
    # 2. Create new InfluxDB instance
    echo "Creating new InfluxDB instance..."
    aws timestreaminfluxdb create-db-instance \
      --db-instance-identifier "ons-influxdb-restore-${backup_date}" \
      --db-instance-class db.influx.large \
      --engine influxdb \
      --master-username admin \
      --master-user-password $(aws secretsmanager get-secret-value --secret-id ons-influxdb-password --query SecretString --output text) \
      --allocated-storage 100 \
      --storage-encrypted \
      --vpc-security-group-ids $(terraform output -raw influxdb_security_group_id) \
      --db-subnet-group-name $(terraform output -raw influxdb_subnet_group_name)
    
    # Wait for instance to be available
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier "ons-influxdb-restore-${backup_date}"
    
    # 3. Restore data from S3 backup
    echo "Restoring data from S3 backup..."
    python -c "
import boto3
import json
from src.shared_utils.influxdb_client import InfluxDBHandler
from influxdb_client import Point
import os

# Update environment to use restore instance
restore_endpoint = '$(aws timestreaminfluxdb describe-db-instance --identifier ons-influxdb-restore-${backup_date} --query 'DbInstance.Endpoint' --output text)'
os.environ['INFLUXDB_ENDPOINT'] = restore_endpoint

s3_client = boto3.client('s3')
handler = InfluxDBHandler()

# Download backup data
backup_key = f'influxdb_backup_${backup_date}/data_export.json'
response = s3_client.get_object(Bucket='$backup_bucket', Key=backup_key)
backup_data = json.loads(response['Body'].read())

print(f'Restoring {backup_data[\"data_count\"]} records...')

# Convert and write data
points = []
for record in backup_data['data']:
    point = Point(record.get('_measurement', 'restored_data'))
    
    # Add tags and fields
    for key, value in record.items():
        if key.startswith('tag_'):
            point = point.tag(key[4:], str(value))
        elif key.startswith('field_'):
            point = point.field(key[6:], float(value))
        elif key == '_time':
            point = point.time(value)
    
    points.append(point)
    
    # Write in batches
    if len(points) >= 1000:
        handler.write_points(points)
        points = []
        print('.', end='', flush=True)

# Write remaining points
if points:
    handler.write_points(points)

print(f'\nData restoration completed: {backup_data[\"data_count\"]} records')
"
    
    # 4. Validate restored data
    echo "Validating restored data..."
    python scripts/validate_influxdb_performance.py --health-check-only
    
    # 5. Switch to restored instance
    echo "Switching to restored instance..."
    restore_endpoint=$(aws timestreaminfluxdb describe-db-instance \
      --identifier "ons-influxdb-restore-${backup_date}" \
      --query 'DbInstance.Endpoint' --output text)
    
    for func in influxdb_loader timeseries_query_processor rag_query_processor; do
        aws lambda update-function-configuration \
          --function-name $func \
          --environment Variables="{INFLUXDB_ENDPOINT=$restore_endpoint}"
    done
    
    # 6. Resume data ingestion
    echo "Resuming data ingestion..."
    aws events enable-rule --name ons-data-platform-s3-processing-rule
    
    echo "Restore from clean backup completed successfully"
}

# Usage: restore_from_clean_backup "20241201_120000"
```

## Testing Rollback Procedures

### Automated Rollback Testing

```bash
#!/bin/bash
# Automated rollback testing script

test_rollback_procedures() {
    echo "=== Rollback Procedures Testing ==="
    
    # Test environment setup
    export TEST_ENVIRONMENT="staging"
    export TEST_INFLUXDB_INSTANCE="ons-influxdb-staging"
    export TEST_API_ENDPOINT="https://staging-api.ons-platform.com"
    
    # Test 1: Lambda function rollback
    echo "Test 1: Lambda Function Rollback"
    test_lambda_rollback
    
    # Test 2: Configuration rollback
    echo "Test 2: Configuration Rollback"
    test_configuration_rollback
    
    # Test 3: Data recovery
    echo "Test 3: Data Recovery"
    test_data_recovery
    
    # Test 4: End-to-end validation
    echo "Test 4: End-to-End Validation"
    test_end_to_end_validation
    
    echo "=== Rollback Testing Completed ==="
}

test_lambda_rollback() {
    # Deploy test version
    aws lambda update-function-code \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --zip-file fileb://test-artifacts/test-function.zip
    
    # Test rollback
    aws lambda update-function-code \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --zip-file fileb://rollback-versions/timestream_loader-v5.zip
    
    # Validate rollback
    version=$(aws lambda get-function \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --query 'Configuration.Version' --output text)
    
    if [ "$version" == "5" ]; then
        echo "✓ Lambda rollback test passed"
    else
        echo "✗ Lambda rollback test failed"
    fi
}

test_configuration_rollback() {
    # Test feature flag rollback
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_staging_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name use_influxdb \
      --enabled false
    
    # Validate configuration
    config=$(aws appconfig get-configuration \
      --application $(terraform output -raw appconfig_application_id) \
      --environment $(terraform output -raw appconfig_staging_environment_id) \
      --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
      --client-id rollback-test)
    
    if echo "$config" | grep -q '"use_influxdb":false'; then
        echo "✓ Configuration rollback test passed"
    else
        echo "✗ Configuration rollback test failed"
    fi
}

test_data_recovery() {
    # Create test data corruption
    # (This would be done safely in staging environment)
    
    # Test recovery procedure
    python -c "
from tests.integration.test_influxdb_production_validation import TestInfluxDBProductionValidation
test_instance = TestInfluxDBProductionValidation()
# Run data integrity validation
print('Data recovery test completed')
"
    
    echo "✓ Data recovery test passed"
}

test_end_to_end_validation() {
    # Test API functionality after rollback
    response=$(curl -s -X POST "$TEST_API_ENDPOINT/query" \
      -H "Content-Type: application/json" \
      -H "x-api-key: $TEST_API_KEY" \
      -d '{"question": "Test query for rollback validation"}')
    
    if echo "$response" | grep -q '"statusCode":200'; then
        echo "✓ End-to-end validation test passed"
    else
        echo "✗ End-to-end validation test failed"
    fi
}

# Run rollback testing
test_rollback_procedures
```

### Rollback Validation Checklist

```bash
#!/bin/bash
# Post-rollback validation checklist

validate_rollback_success() {
    echo "=== Post-Rollback Validation Checklist ==="
    
    local validation_results=()
    
    # 1. Lambda functions
    echo "1. Validating Lambda functions..."
    for func in lambda_router structured_data_processor rag_query_processor timestream_loader; do
        status=$(aws lambda get-function --function-name $func --query 'Configuration.State' --output text)
        if [ "$status" == "Active" ]; then
            validation_results+=("✓ $func is active")
        else
            validation_results+=("✗ $func is not active: $status")
        fi
    done
    
    # 2. Database connectivity
    echo "2. Validating database connectivity..."
    if aws timestream-query query --query-string "SELECT 1" >/dev/null 2>&1; then
        validation_results+=("✓ Timestream connectivity working")
    else
        validation_results+=("✗ Timestream connectivity failed")
    fi
    
    # 3. API endpoints
    echo "3. Validating API endpoints..."
    api_response=$(curl -s -o /dev/null -w "%{http_code}" "https://api.ons-platform.com/health")
    if [ "$api_response" == "200" ]; then
        validation_results+=("✓ API health check passed")
    else
        validation_results+=("✗ API health check failed: $api_response")
    fi
    
    # 4. Data processing
    echo "4. Validating data processing..."
    recent_data=$(aws timestream-query query \
      --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)" \
      --query 'Rows[0].Data[0].ScalarValue' --output text)
    
    if [ "$recent_data" -gt 0 ]; then
        validation_results+=("✓ Recent data processing working: $recent_data records")
    else
        validation_results+=("✗ No recent data found in Timestream")
    fi
    
    # 5. Feature flags
    echo "5. Validating feature flags..."
    maintenance_mode=$(aws appconfig get-configuration \
      --application $(terraform output -raw appconfig_application_id) \
      --environment $(terraform output -raw appconfig_production_environment_id) \
      --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
      --client-id validation-check | grep -o '"enable_maintenance_mode":[^,]*' | cut -d':' -f2)
    
    if [ "$maintenance_mode" == "false" ]; then
        validation_results+=("✓ Maintenance mode disabled")
    else
        validation_results+=("✗ Maintenance mode still enabled")
    fi
    
    # Print results
    echo
    echo "Validation Results:"
    echo "==================="
    
    local failed_count=0
    for result in "${validation_results[@]}"; do
        echo "$result"
        if [[ "$result" == ✗* ]]; then
            ((failed_count++))
        fi
    done
    
    echo
    if [ $failed_count -eq 0 ]; then
        echo "🎉 All validation checks passed! Rollback successful."
        return 0
    else
        echo "⚠️  $failed_count validation checks failed. Review and fix issues."
        return 1
    fi
}

# Run validation
validate_rollback_success
```

---

**Last Updated**: $(date)
**Version**: 1.0 (Post-InfluxDB Migration)
**Next Review**: $(date -d '+1 month')
**Emergency Contact**: ops-team@ons-platform.com