# InfluxDB Operations Runbook

## Overview

This runbook provides specific operational procedures for managing the Amazon Timestream for InfluxDB instance used in the ONS Data Platform after the migration from regular Amazon Timestream.

## Table of Contents

1. [InfluxDB Health Monitoring](#influxdb-health-monitoring)
2. [Performance Optimization](#performance-optimization)
3. [Data Management](#data-management)
4. [Query Optimization](#query-optimization)
5. [Backup and Recovery](#backup-and-recovery)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Monitoring and Alerting](#monitoring-and-alerting)

## InfluxDB Health Monitoring

### Daily Health Checks

```bash
#!/bin/bash
# InfluxDB Daily Health Check

echo "=== InfluxDB Health Check ==="
echo "Date: $(date)"
echo

# 1. Check database instance status
echo "1. Database Instance Status:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[DbInstanceStatus,DbInstanceClass,AllocatedStorage,AvailabilityZone]' \
  --output table

# 2. Check connectivity and response time
echo "2. Connectivity Test:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import time
handler = InfluxDBHandler()
start = time.time()
health = handler.health_check()
response_time = (time.time() - start) * 1000
print(f'Status: {health[\"status\"]}')
print(f'Response Time: {response_time:.2f}ms')
print(f'Connection Pool: {health.get(\"connection_pool_active\", \"N/A\")} active, {health.get(\"connection_pool_idle\", \"N/A\")} idle')
"

# 3. Check recent data ingestion
echo "3. Recent Data Ingestion:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()
query = '''
from(bucket: \"energy_data\")
  |> range(start: -1h)
  |> count()
'''
result = handler.query_flux(query)
print(f'Records in last hour: {len(result)}')
"

# 4. Check query performance
echo "4. Query Performance Test:"
python scripts/validate_influxdb_performance.py --quick-test

# 5. Check CloudWatch metrics
echo "5. CloudWatch Metrics:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_ResponseTime \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average,Maximum \
  --query 'Datapoints[0].[Average,Maximum]' --output text

echo "=== Health Check Complete ==="
```

### Weekly Performance Review

```bash
#!/bin/bash
# Weekly InfluxDB Performance Review

echo "=== Weekly InfluxDB Performance Review ==="

# 1. Query performance trends
echo "1. Query Performance Trends (Last 7 Days):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_QueryLatency \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 86400 \
  --statistics Average,Maximum \
  --query 'Datapoints[*].[Timestamp,Average,Maximum]' --output table

# 2. Write throughput analysis
echo "2. Write Throughput Analysis:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_WritePoints \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 86400 \
  --statistics Sum \
  --query 'Datapoints[*].[Timestamp,Sum]' --output table

# 3. Storage utilization
echo "3. Storage Utilization:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[AllocatedStorage,StorageEncrypted,StorageType]' --output table

# 4. Connection pool analysis
echo "4. Connection Pool Analysis:"
python -c "
from src.influxdb_monitor.lambda_function import lambda_handler
import json
result = lambda_handler({'source': 'manual'}, {})
metrics = json.loads(result['body'])['metrics']
print(f'Active Connections: {metrics.get(\"connection_pool_active\", \"N/A\")}')
print(f'Idle Connections: {metrics.get(\"connection_pool_idle\", \"N/A\")}')
print(f'Average Response Time: {metrics.get(\"response_time_ms\", \"N/A\")}ms')
"

# 5. Error rate analysis
echo "5. Error Rate Analysis:"
aws logs filter-log-events \
  --log-group-name /aws/lambda/influxdb_loader \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'length(events)' --output text
```

## Performance Optimization

### Query Performance Optimization

1. **Analyze Slow Queries:**
```python
# Create query performance analyzer
def analyze_query_performance():
    """Analyze and optimize slow queries"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import time
    
    handler = InfluxDBHandler()
    
    # Test queries with different patterns
    test_queries = [
        {
            'name': 'Simple Filter',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -1h)
                |> filter(fn: (r) => r["region"] == "southeast")
            '''
        },
        {
            'name': 'Aggregation',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -1d)
                |> aggregateWindow(every: 1h, fn: mean)
            '''
        },
        {
            'name': 'Complex Grouping',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -7d)
                |> group(columns: ["region", "energy_source"])
                |> aggregateWindow(every: 6h, fn: mean)
            '''
        }
    ]
    
    results = []
    for test in test_queries:
        start_time = time.time()
        try:
            result = handler.query_flux(test['query'])
            execution_time = (time.time() - start_time) * 1000
            results.append({
                'name': test['name'],
                'execution_time_ms': execution_time,
                'result_count': len(result),
                'status': 'success'
            })
        except Exception as e:
            results.append({
                'name': test['name'],
                'execution_time_ms': 0,
                'result_count': 0,
                'status': f'error: {str(e)}'
            })
    
    return results

# Run analysis
performance_results = analyze_query_performance()
for result in performance_results:
    print(f"{result['name']}: {result['execution_time_ms']:.2f}ms ({result['status']})")
```

2. **Optimize Data Schema:**
```python
def optimize_data_schema():
    """Optimize InfluxDB data schema for better performance"""
    
    # Recommended schema optimizations:
    schema_recommendations = {
        'tags': [
            'region',           # Low cardinality (5 regions)
            'energy_source',    # Medium cardinality (~10 sources)
            'plant_name'        # High cardinality (but necessary for queries)
        ],
        'fields': [
            'power_mw',         # Numeric measurement
            'capacity_mw',      # Numeric measurement
            'efficiency',       # Numeric measurement
            'availability'      # Numeric measurement
        ],
        'timestamp': 'time'     # Use InfluxDB native timestamp
    }
    
    # Cardinality analysis
    print("Schema Optimization Recommendations:")
    print("=====================================")
    print("Tags (indexed, low cardinality preferred):")
    for tag in schema_recommendations['tags']:
        print(f"  - {tag}")
    
    print("\nFields (not indexed, high cardinality OK):")
    for field in schema_recommendations['fields']:
        print(f"  - {field}")
    
    return schema_recommendations
```

### Write Performance Optimization

1. **Batch Write Optimization:**
```python
def optimize_batch_writes():
    """Optimize batch write performance"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    from influxdb_client import Point
    import time
    
    handler = InfluxDBHandler()
    
    # Test different batch sizes
    batch_sizes = [100, 500, 1000, 2000]
    results = {}
    
    for batch_size in batch_sizes:
        # Create test points
        points = []
        for i in range(batch_size):
            point = Point("performance_test") \
                .tag("region", f"region_{i % 5}") \
                .tag("source", f"source_{i % 3}") \
                .field("value", float(i)) \
                .time(time.time_ns() + i * 1000000)  # Nanosecond precision
            points.append(point)
        
        # Measure write performance
        start_time = time.time()
        try:
            handler.write_points(points, batch_size=batch_size)
            write_time = (time.time() - start_time) * 1000
            throughput = batch_size / (write_time / 1000)
            
            results[batch_size] = {
                'write_time_ms': write_time,
                'throughput_points_per_sec': throughput,
                'status': 'success'
            }
        except Exception as e:
            results[batch_size] = {
                'write_time_ms': 0,
                'throughput_points_per_sec': 0,
                'status': f'error: {str(e)}'
            }
    
    # Find optimal batch size
    optimal_batch_size = max(
        [k for k, v in results.items() if v['status'] == 'success'],
        key=lambda k: results[k]['throughput_points_per_sec']
    )
    
    print("Batch Write Performance Results:")
    print("================================")
    for batch_size, result in results.items():
        print(f"Batch Size {batch_size}: {result['throughput_points_per_sec']:.2f} points/sec ({result['status']})")
    
    print(f"\nOptimal batch size: {optimal_batch_size}")
    return optimal_batch_size
```

## Data Management

### Retention Policy Management

```bash
#!/bin/bash
# Manage InfluxDB retention policies

# Check current retention settings
echo "Current Retention Policies:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()

# Query bucket information
query = '''
buckets()
  |> filter(fn: (r) => r.name == \"energy_data\")
  |> yield()
'''

result = handler.query_flux(query)
for bucket in result:
    print(f'Bucket: {bucket.get(\"name\", \"N/A\")}')
    print(f'Retention Period: {bucket.get(\"retentionPeriod\", \"N/A\")}')
    print(f'Organization: {bucket.get(\"orgID\", \"N/A\")}')
"

# Update retention policy if needed
update_retention_policy() {
    local bucket_name=$1
    local retention_period=$2
    
    echo "Updating retention policy for bucket: $bucket_name"
    echo "New retention period: $retention_period"
    
    python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()

# Note: Retention policy updates depend on InfluxDB version and setup
# This is a placeholder for the actual implementation
print('Retention policy update would be implemented here')
print('Bucket: $bucket_name')
print('Retention: $retention_period')
"
}

# Example usage
# update_retention_policy "energy_data" "2555d"  # ~7 years
```

### Data Cleanup and Archival

```python
def cleanup_old_data():
    """Clean up old data based on retention policies"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    from datetime import datetime, timedelta
    
    handler = InfluxDBHandler()
    
    # Define cleanup thresholds
    cleanup_thresholds = {
        'test_data': timedelta(days=7),      # Test data kept for 1 week
        'debug_data': timedelta(days=30),    # Debug data kept for 1 month
        'temp_data': timedelta(days=1)       # Temporary data kept for 1 day
    }
    
    for measurement, threshold in cleanup_thresholds.items():
        cutoff_time = datetime.utcnow() - threshold
        
        # Delete old data
        delete_query = f'''
        from(bucket: "energy_data")
          |> range(start: 1970-01-01T00:00:00Z, stop: {cutoff_time.isoformat()}Z)
          |> filter(fn: (r) => r["_measurement"] == "{measurement}")
          |> drop()
        '''
        
        try:
            result = handler.query_flux(delete_query)
            print(f"Cleaned up {measurement} data older than {threshold}")
        except Exception as e:
            print(f"Failed to clean up {measurement}: {str(e)}")

def archive_historical_data():
    """Archive historical data to S3 for long-term storage"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import boto3
    import json
    from datetime import datetime, timedelta
    
    handler = InfluxDBHandler()
    s3_client = boto3.client('s3')
    
    # Archive data older than 1 year
    archive_cutoff = datetime.utcnow() - timedelta(days=365)
    
    # Query historical data
    archive_query = f'''
    from(bucket: "energy_data")
      |> range(start: 1970-01-01T00:00:00Z, stop: {archive_cutoff.isoformat()}Z)
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    try:
        historical_data = handler.query_flux(archive_query)
        
        # Convert to JSON for archival
        archive_data = {
            'archived_at': datetime.utcnow().isoformat(),
            'data_count': len(historical_data),
            'data': historical_data
        }
        
        # Upload to S3
        archive_key = f"archives/influxdb_archive_{archive_cutoff.strftime('%Y%m%d')}.json"
        s3_client.put_object(
            Bucket='ons-data-platform-archives',
            Key=archive_key,
            Body=json.dumps(archive_data, default=str),
            StorageClass='GLACIER'
        )
        
        print(f"Archived {len(historical_data)} records to s3://ons-data-platform-archives/{archive_key}")
        
    except Exception as e:
        print(f"Failed to archive historical data: {str(e)}")
```

## Query Optimization

### Query Performance Best Practices

1. **Time Range Optimization:**
```flux
// Good: Specific time range
from(bucket: "energy_data")
  |> range(start: -24h, stop: now())
  |> filter(fn: (r) => r["region"] == "southeast")

// Bad: No time range (scans all data)
from(bucket: "energy_data")
  |> filter(fn: (r) => r["region"] == "southeast")
```

2. **Filter Optimization:**
```flux
// Good: Filter early and use indexed tags
from(bucket: "energy_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["region"] == "southeast")
  |> filter(fn: (r) => r["energy_source"] == "hydro")
  |> filter(fn: (r) => r["_field"] == "power_mw")

// Bad: Filter late and use non-indexed fields
from(bucket: "energy_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_value"] > 1000.0)
  |> filter(fn: (r) => r["region"] == "southeast")
```

3. **Aggregation Optimization:**
```flux
// Good: Use appropriate window sizes
from(bucket: "energy_data")
  |> range(start: -7d)
  |> aggregateWindow(every: 1h, fn: mean)
  |> group(columns: ["region"])

// Bad: Too granular aggregation for large time ranges
from(bucket: "energy_data")
  |> range(start: -30d)
  |> aggregateWindow(every: 1m, fn: mean)  // Too many points
```

### Query Caching Implementation

```python
def implement_query_caching():
    """Implement query result caching for better performance"""
    import redis
    import json
    import hashlib
    from src.shared_utils.influxdb_client import InfluxDBHandler
    
    # Initialize Redis client
    redis_client = redis.Redis(
        host='ons-elasticache-cluster.cache.amazonaws.com',
        port=6379,
        decode_responses=True
    )
    
    class CachedInfluxDBHandler(InfluxDBHandler):
        def __init__(self, cache_ttl=300):  # 5 minutes default TTL
            super().__init__()
            self.cache_ttl = cache_ttl
        
        def query_flux_cached(self, query, cache_ttl=None):
            """Execute Flux query with caching"""
            # Generate cache key
            cache_key = f"influxdb_query:{hashlib.md5(query.encode()).hexdigest()}"
            
            # Check cache first
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)
            except Exception as e:
                print(f"Cache read error: {e}")
            
            # Execute query
            result = self.query_flux(query)
            
            # Cache result
            try:
                ttl = cache_ttl or self.cache_ttl
                redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, default=str)
                )
            except Exception as e:
                print(f"Cache write error: {e}")
            
            return result
        
        def invalidate_cache_pattern(self, pattern):
            """Invalidate cache entries matching pattern"""
            try:
                keys = redis_client.keys(f"influxdb_query:*{pattern}*")
                if keys:
                    redis_client.delete(*keys)
                    print(f"Invalidated {len(keys)} cache entries")
            except Exception as e:
                print(f"Cache invalidation error: {e}")
    
    return CachedInfluxDBHandler
```

## Backup and Recovery

### Automated Backup Procedures

```bash
#!/bin/bash
# InfluxDB Backup Script

BACKUP_BUCKET="ons-data-platform-backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PREFIX="influxdb_backup_${BACKUP_DATE}"

echo "Starting InfluxDB backup: $BACKUP_PREFIX"

# 1. Export data to S3
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import boto3
import json
from datetime import datetime, timedelta

handler = InfluxDBHandler()
s3_client = boto3.client('s3')

# Export recent data (last 30 days)
export_query = '''
from(bucket: \"energy_data\")
  |> range(start: -30d)
  |> pivot(rowKey:[\"_time\"], columnKey: [\"_field\"], valueColumn: \"_value\")
'''

try:
    data = handler.query_flux(export_query)
    
    backup_data = {
        'backup_timestamp': datetime.utcnow().isoformat(),
        'data_count': len(data),
        'data': data
    }
    
    # Upload to S3
    s3_client.put_object(
        Bucket='$BACKUP_BUCKET',
        Key='$BACKUP_PREFIX/data_export.json',
        Body=json.dumps(backup_data, default=str)
    )
    
    print(f'Backed up {len(data)} records to S3')
    
except Exception as e:
    print(f'Backup failed: {str(e)}')
    exit(1)
"

# 2. Backup configuration
echo "Backing up InfluxDB configuration..."
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod > "/tmp/influxdb_config_${BACKUP_DATE}.json"

aws s3 cp "/tmp/influxdb_config_${BACKUP_DATE}.json" \
  "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/configuration.json"

# 3. Create snapshot if supported
echo "Creating database snapshot..."
aws timestreaminfluxdb create-db-snapshot \
  --db-instance-identifier ons-influxdb-prod \
  --db-snapshot-identifier "ons-influxdb-snapshot-${BACKUP_DATE}" \
  --tags Key=BackupDate,Value=$BACKUP_DATE Key=Environment,Value=prod

echo "Backup completed: $BACKUP_PREFIX"

# 4. Cleanup old backups (keep last 30 days)
aws s3 ls "s3://${BACKUP_BUCKET}/" --recursive | \
  awk '{print $4}' | \
  grep "influxdb_backup_" | \
  head -n -30 | \
  xargs -I {} aws s3 rm "s3://${BACKUP_BUCKET}/{}"
```

### Disaster Recovery Procedures

```bash
#!/bin/bash
# InfluxDB Disaster Recovery Script

restore_from_backup() {
    local backup_date=$1
    local backup_bucket="ons-data-platform-backups"
    local backup_prefix="influxdb_backup_${backup_date}"
    
    echo "Starting disaster recovery from backup: $backup_prefix"
    
    # 1. Stop current processing
    echo "Stopping data processing..."
    aws events disable-rule --name ons-data-platform-s3-processing-rule
    
    # 2. Create new InfluxDB instance from snapshot
    echo "Creating new InfluxDB instance from snapshot..."
    aws timestreaminfluxdb restore-db-instance-from-db-snapshot \
      --db-instance-identifier ons-influxdb-recovery \
      --db-snapshot-identifier "ons-influxdb-snapshot-${backup_date}" \
      --db-instance-class db.influx.large
    
    # Wait for instance to be available
    echo "Waiting for instance to be available..."
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier ons-influxdb-recovery
    
    # 3. Update Lambda functions to use new instance
    echo "Updating Lambda functions..."
    for func in influxdb_loader timeseries_query_processor rag_query_processor; do
        aws lambda update-function-configuration \
          --function-name $func \
          --environment Variables="{INFLUXDB_ENDPOINT=$(aws timestreaminfluxdb describe-db-instance --identifier ons-influxdb-recovery --query 'DbInstance.Endpoint' --output text)}"
    done
    
    # 4. Restore data from S3 backup
    echo "Restoring data from S3 backup..."
    python -c "
import boto3
import json
from src.shared_utils.influxdb_client import InfluxDBHandler
from influxdb_client import Point

s3_client = boto3.client('s3')
handler = InfluxDBHandler()

# Download backup data
response = s3_client.get_object(
    Bucket='$backup_bucket',
    Key='$backup_prefix/data_export.json'
)

backup_data = json.loads(response['Body'].read())
data_points = backup_data['data']

# Convert to InfluxDB points
points = []
for record in data_points:
    point = Point('restored_data')
    
    # Add tags
    for key, value in record.items():
        if key.startswith('tag_'):
            point = point.tag(key[4:], str(value))
        elif key.startswith('field_'):
            point = point.field(key[6:], float(value))
        elif key == '_time':
            point = point.time(value)

    points.append(point)

# Write to InfluxDB
handler.write_points(points, batch_size=1000)
print(f'Restored {len(points)} data points')
"
    
    # 5. Validate recovery
    echo "Validating recovery..."
    python scripts/validate_influxdb_performance.py --health-check-only
    
    # 6. Switch traffic to recovered instance
    echo "Switching traffic to recovered instance..."
    # Update Terraform configuration or use blue-green deployment
    
    echo "Disaster recovery completed successfully"
}

# Usage: restore_from_backup "20241201_120000"
```

## Troubleshooting

### Common InfluxDB Issues

#### Connection Timeouts

**Symptoms:**
- Lambda functions timing out
- Connection refused errors
- Intermittent connectivity issues

**Diagnosis:**
```bash
# Check instance status
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text

# Test connectivity
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import time

handler = InfluxDBHandler()
start_time = time.time()
try:
    health = handler.health_check()
    response_time = (time.time() - start_time) * 1000
    print(f'Connection successful: {response_time:.2f}ms')
    print(f'Status: {health}')
except Exception as e:
    print(f'Connection failed: {str(e)}')
"

# Check security groups
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=ons-influxdb-sg \
  --query 'SecurityGroups[*].IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[*].CidrIp]' \
  --output table
```

**Solutions:**
1. **Increase connection timeout:**
```python
# Update InfluxDB client configuration
from influxdb_client import InfluxDBClient

client = InfluxDBClient(
    url=influxdb_url,
    token=influxdb_token,
    org=influxdb_org,
    timeout=30000  # 30 seconds
)
```

2. **Optimize connection pooling:**
```python
# Configure connection pool
client = InfluxDBClient(
    url=influxdb_url,
    token=influxdb_token,
    org=influxdb_org,
    connection_pool_maxsize=20,
    connection_pool_block=True
)
```

#### High Memory Usage

**Symptoms:**
- Out of memory errors
- Slow query performance
- Instance becoming unresponsive

**Diagnosis:**
```bash
# Check instance metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_MemoryUtilization \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Solutions:**
1. **Scale up instance:**
```bash
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.xlarge \
  --apply-immediately
```

2. **Optimize queries:**
```flux
// Use smaller time ranges
from(bucket: "energy_data")
  |> range(start: -1h)  // Instead of -30d
  |> limit(n: 1000)     // Limit result size
```

## Maintenance Procedures

### Scheduled Maintenance

```bash
#!/bin/bash
# InfluxDB Scheduled Maintenance

maintenance_window() {
    echo "Starting InfluxDB maintenance window..."
    
    # 1. Enable maintenance mode
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_production_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name enable_maintenance_mode \
      --enabled true
    
    # 2. Create backup before maintenance
    echo "Creating pre-maintenance backup..."
    ./backup_influxdb.sh
    
    # 3. Apply instance updates
    echo "Applying instance updates..."
    aws timestreaminfluxdb modify-db-instance \
      --db-instance-identifier ons-influxdb-prod \
      --auto-minor-version-upgrade \
      --apply-immediately
    
    # 4. Wait for updates to complete
    echo "Waiting for updates to complete..."
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier ons-influxdb-prod
    
    # 5. Run post-maintenance validation
    echo "Running post-maintenance validation..."
    python scripts/validate_influxdb_performance.py
    
    # 6. Disable maintenance mode
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_production_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name enable_maintenance_mode \
      --enabled false
    
    echo "Maintenance window completed successfully"
}

# Schedule maintenance (example: first Sunday of each month at 2 AM)
# 0 2 1-7 * 0 /path/to/maintenance_window.sh
```

## Monitoring and Alerting

### CloudWatch Alarms for InfluxDB

```bash
#!/bin/bash
# Create CloudWatch alarms for InfluxDB monitoring

# 1. High response time alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-HighResponseTime" \
  --alarm-description "InfluxDB response time is high" \
  --metric-name InfluxDB_ResponseTime \
  --namespace AWS/Timestream \
  --statistic Average \
  --period 300 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 2. Connection failure alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-ConnectionFailures" \
  --alarm-description "InfluxDB connection failures detected" \
  --metric-name InfluxDB_ConnectionErrors \
  --namespace AWS/Timestream \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 3. Memory utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-HighMemoryUtilization" \
  --alarm-description "InfluxDB memory utilization is high" \
  --metric-name InfluxDB_MemoryUtilization \
  --namespace AWS/Timestream \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 3 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 4. Write throughput alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-LowWriteThroughput" \
  --alarm-description "InfluxDB write throughput is low" \
  --metric-name InfluxDB_WritePoints \
  --namespace AWS/Timestream \
  --statistic Sum \
  --period 900 \
  --threshold 1000 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod
```

### Custom Monitoring Dashboard

```python
def create_influxdb_dashboard():
    """Create CloudWatch dashboard for InfluxDB monitoring"""
    import boto3
    import json
    
    cloudwatch = boto3.client('cloudwatch')
    
    dashboard_body = {
        "widgets": [
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_ResponseTime", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_QueryLatency", ".", "."],
                        [".", "InfluxDB_WriteLatency", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "InfluxDB Response Times"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_WritePoints", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_QueryCount", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "InfluxDB Throughput"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_MemoryUtilization", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_CPUUtilization", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "InfluxDB Resource Utilization"
                }
            }
        ]
    }
    
    cloudwatch.put_dashboard(
        DashboardName='InfluxDB-Operations',
        DashboardBody=json.dumps(dashboard_body)
    )
    
    print("InfluxDB monitoring dashboard created successfully")

# Create the dashboard
create_influxdb_dashboard()
```

---

**Last Updated**: $(date)
**Version**: 1.0 (Post-InfluxDB Migration)
**Next Review**: $(date -d '+1 month')