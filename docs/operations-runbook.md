# Operations Runbook

## Overview

This runbook provides step-by-step procedures for common operational tasks, troubleshooting guides, and emergency response procedures for the ONS Data Platform.

## Table of Contents

1. [System Health Checks](#system-health-checks)
2. [Common Maintenance Tasks](#common-maintenance-tasks)
3. [Troubleshooting Guides](#troubleshooting-guides)
4. [Emergency Procedures](#emergency-procedures)
5. [Performance Monitoring](#performance-monitoring)
6. [Cost Management](#cost-management)
7. [Security Operations](#security-operations)

## System Health Checks

### Daily Health Check

Run this comprehensive health check every morning:

```bash
#!/bin/bash
# Daily health check script

echo "=== ONS Data Platform Health Check ==="
echo "Date: $(date)"
echo

# 1. Check Lambda function health
echo "1. Lambda Function Health:"
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor timestream_loader

# 2. Check API Gateway health
echo "2. API Gateway Health:"
curl -s -o /dev/null -w "%{http_code}" \
  "https://$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text).execute-api.us-east-1.amazonaws.com/prod/health"

# 3. Check S3 bucket accessibility
echo "3. S3 Bucket Health:"
aws s3 ls s3://ons-data-platform-raw-prod/ > /dev/null && echo "✓ Raw bucket accessible" || echo "✗ Raw bucket error"
aws s3 ls s3://ons-data-platform-processed-prod/ > /dev/null && echo "✓ Processed bucket accessible" || echo "✗ Processed bucket error"

# 4. Check InfluxDB database
echo "4. InfluxDB Database Health:"
python scripts/validate_influxdb_performance.py --health-check-only

# 5. Check recent processing activity
echo "5. Recent Processing Activity:"
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "SUCCESS" \
  --query 'events[*].message' --output table

echo "=== Health Check Complete ==="
```

### Weekly Health Check

Extended health check for weekly review:

```bash
#!/bin/bash
# Weekly health check script

echo "=== Weekly Health Review ==="

# 1. Check error rates over the past week
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'length(events)' --output text

# 2. Review cost trends
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 3. Check storage utilization
aws s3api list-objects-v2 \
  --bucket ons-data-platform-raw-prod \
  --query 'sum(Contents[].Size)' --output text

# 4. Review security alerts
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "SECURITY" \
  --query 'length(events)' --output text
```

## Common Maintenance Tasks

### 1. Update Lambda Function Code

```bash
# Update a specific Lambda function
cd src/lambda_router

# Package the function
zip -r lambda_router.zip . -x "tests/*" "*.pyc" "__pycache__/*"

# Update function code
aws lambda update-function-code \
  --function-name lambda_router \
  --zip-file fileb://lambda_router.zip

# Publish new version
VERSION=$(aws lambda publish-version \
  --function-name lambda_router \
  --description "Manual update $(date)" \
  --query 'Version' --output text)

echo "Published version: $VERSION"

# Deploy with blue-green strategy
python ../../scripts/deploy.py \
  --function-name lambda_router \
  --version $VERSION \
  --deployment-group lambda_router-deployment-group
```

### 2. Scale InfluxDB Database

```bash
# Check current InfluxDB usage
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[DbInstanceStatus,AllocatedStorage,DbInstanceClass]' --output table

# Scale up instance if needed
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.large \
  --allocated-storage 200 \
  --apply-immediately

# Update retention policies
python scripts/manage_influxdb_retention.py \
  --bucket energy_data \
  --retention-period 7y
```

### 3. Clean Up Old Data

```bash
# Clean up old Lambda versions (keep last 5)
FUNCTION_NAME="lambda_router"
aws lambda list-versions-by-function \
  --function-name $FUNCTION_NAME \
  --query 'Versions[?Version!=`$LATEST`].Version' \
  --output text | \
  head -n -5 | \
  xargs -I {} aws lambda delete-function \
    --function-name $FUNCTION_NAME \
    --qualifier {}

# Clean up old CloudWatch logs (older than retention period)
aws logs describe-log-groups \
  --query 'logGroups[?retentionInDays==`null`].logGroupName' \
  --output text | \
  xargs -I {} aws logs put-retention-policy \
    --log-group-name {} \
    --retention-in-days 30
```

### 4. Update Feature Flags

```bash
# Enable a feature flag
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_new_api_endpoint \
  --enabled true

# Check flag status
aws appconfig get-configuration \
  --application $(terraform output -raw appconfig_application_id) \
  --environment $(terraform output -raw appconfig_production_environment_id) \
  --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
  --client-id operations-check
```

## Troubleshooting Guides

### Issue: High Error Rate in Lambda Functions

**Symptoms:**
- CloudWatch alarms firing
- Increased error logs
- API returning 5xx errors

**Investigation Steps:**

1. **Check recent deployments:**
```bash
aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses Succeeded Failed \
  --max-items 5
```

2. **Analyze error logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'events[*].[timestamp,message]' --output table
```

3. **Check function metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=lambda_router \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

**Resolution:**

1. **If recent deployment caused issues:**
```bash
python scripts/rollback.py --action rollback-function \
  --function-name lambda_router
```

2. **If configuration issue:**
```bash
# Disable problematic feature flag
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_problematic_feature
```

### Issue: S3 Processing Failures

**Symptoms:**
- Files stuck in raw bucket
- No processed files appearing
- Step Functions failures

**Investigation Steps:**

1. **Check Step Functions executions:**
```bash
aws stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --status-filter FAILED \
  --max-items 10
```

2. **Check EventBridge rules:**
```bash
aws events list-rules \
  --name-prefix ons-data-platform \
  --query 'Rules[*].[Name,State]' --output table
```

3. **Check S3 bucket notifications:**
```bash
aws s3api get-bucket-notification-configuration \
  --bucket $(terraform output -raw s3_raw_bucket_name)
```

**Resolution:**

1. **Reprocess failed files:**
```bash
# Get failed execution details
EXECUTION_ARN=$(aws stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --status-filter FAILED \
  --max-items 1 \
  --query 'executions[0].executionArn' --output text)

# Get input from failed execution
aws stepfunctions describe-execution \
  --execution-arn $EXECUTION_ARN \
  --query 'input'

# Restart execution with same input
aws stepfunctions start-execution \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --input "$(aws stepfunctions describe-execution --execution-arn $EXECUTION_ARN --query 'input' --output text)"
```

### Issue: API Gateway Timeouts

**Symptoms:**
- 504 Gateway Timeout errors
- Slow API responses
- High latency metrics

**Investigation Steps:**

1. **Check API Gateway metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=ons-data-platform-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

2. **Check Lambda duration:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=rag_query_processor \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Resolution:**

1. **Increase Lambda timeout:**
```bash
aws lambda update-function-configuration \
  --function-name rag_query_processor \
  --timeout 300
```

2. **Scale up Lambda memory:**
```bash
aws lambda update-function-configuration \
  --function-name rag_query_processor \
  --memory-size 1024
```

### Issue: InfluxDB Write Failures

**Symptoms:**
- Data not appearing in InfluxDB
- Connection timeouts
- High write latency

**Investigation Steps:**

1. **Check InfluxDB metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_WriteLatency \
  --dimensions Name=DatabaseName,Value=ons_influxdb_prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

2. **Check database status:**
```bash
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text
```

3. **Test connectivity:**
```bash
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()
print(handler.health_check())
"
```

**Resolution:**

1. **Implement batch writing with retry logic:**
```python
# Update influxdb_loader to use optimized batch writes
from src.shared_utils.influxdb_client import InfluxDBHandler
import time

def batch_write_with_retry(points, max_retries=3):
    handler = InfluxDBHandler()
    
    for attempt in range(max_retries):
        try:
            handler.write_points(points, batch_size=1000)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
            print(f"Write retry {attempt + 1}/{max_retries} after {wait_time}s")
    
    return False
```

2. **Scale up InfluxDB instance:**
```bash
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.xlarge \
  --apply-immediately
```

## Emergency Procedures

### Critical System Failure

**Immediate Actions (First 5 minutes):**

1. **Assess impact:**
```bash
# Check all critical components
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor timestream_loader
```

2. **Stop ongoing deployments:**
```bash
# List active deployments
aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses InProgress

# Stop all active deployments
for deployment in $(aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses InProgress \
  --query 'deployments[]' --output text); do
  python scripts/rollback.py --action stop-deployment --deployment-id $deployment
done
```

3. **Disable problematic features:**
```bash
# Disable all non-critical feature flags
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_new_api_endpoint enable_enhanced_processing
```

### Data Loss Prevention

**If data corruption is suspected:**

1. **Stop all processing:**
```bash
# Disable EventBridge rules
aws events disable-rule --name ons-data-platform-s3-processing-rule

# Stop Step Functions executions
for execution in $(aws stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --status-filter RUNNING \
  --query 'executions[].executionArn' --output text); do
  aws stepfunctions stop-execution --execution-arn $execution
done
```

2. **Create data snapshots:**
```bash
# Snapshot S3 buckets
aws s3 sync s3://$(terraform output -raw s3_processed_bucket_name) \
  s3://$(terraform output -raw s3_processed_bucket_name)-backup-$(date +%Y%m%d) \
  --storage-class GLACIER
```

3. **Verify data integrity:**
```bash
# Check recent data quality
aws timestream-query query \
  --query-string "SELECT COUNT(*), MIN(time), MAX(time) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(24h)"
```

### Security Incident Response

**If security breach is suspected:**

1. **Immediate containment:**
```bash
# Disable API access
aws apigateway update-stage \
  --rest-api-id $(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text) \
  --stage-name prod \
  --patch-ops op=replace,path=/throttle/rateLimit,value=0
```

2. **Audit access:**
```bash
# Check recent API access
aws logs filter-log-events \
  --log-group-name API-Gateway-Execution-Logs_$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text)/prod \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --filter-pattern "[timestamp, request_id, ip = \"ERROR\" || ip = \"WARN\"]"
```

3. **Rotate credentials:**
```bash
# Rotate API keys
aws apigateway create-api-key \
  --name ons-data-platform-emergency-key \
  --description "Emergency replacement key"

# Update usage plan
aws apigateway update-usage-plan \
  --usage-plan-id $(aws apigateway get-usage-plans --query 'items[0].id' --output text) \
  --patch-ops op=add,path=/apiStages,value='[{"apiId":"'$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text)'","stage":"prod"}]'
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

1. **Processing Throughput:**
```bash
# Files processed per hour
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "PROCESSED" \
  --query 'length(events)'
```

2. **API Response Time:**
```bash
# Average API latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=ons-data-platform-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average
```

3. **Error Rates:**
```bash
# Lambda error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=lambda_router \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Sum
```

### Performance Optimization

1. **Lambda Cold Start Optimization:**
```bash
# Enable provisioned concurrency for critical functions
aws lambda put-provisioned-concurrency-config \
  --function-name lambda_router \
  --qualifier LIVE \
  --provisioned-concurrency-config ProvisionedConcurrencyConfigs=2
```

2. **API Gateway Caching:**
```bash
# Enable caching for GET endpoints
aws apigateway update-stage \
  --rest-api-id $(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text) \
  --stage-name prod \
  --patch-ops op=replace,path=/cacheClusterEnabled,value=true
```

## Cost Management

### Daily Cost Monitoring

```bash
# Check daily costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '1 day ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.BlendedCost.Amount]' \
  --output table
```

### Cost Optimization Actions

1. **Clean up unused resources:**
```bash
# Remove old Lambda versions
for function in lambda_router structured_data_processor rag_query_processor timestream_loader; do
  aws lambda list-versions-by-function \
    --function-name $function \
    --query 'Versions[?Version!=`$LATEST`].Version' \
    --output text | \
    head -n -3 | \
    xargs -I {} aws lambda delete-function \
      --function-name $function \
      --qualifier {}
done
```

2. **Optimize storage classes:**
```bash
# Move old data to cheaper storage
aws s3api put-bucket-lifecycle-configuration \
  --bucket $(terraform output -raw s3_raw_bucket_name) \
  --lifecycle-configuration file://lifecycle-policy.json
```

## Security Operations

### Daily Security Checks

```bash
# Check for security alerts
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --filter-pattern "SECURITY" \
  --query 'events[*].[timestamp,message]' --output table

# Check IAM policy changes
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutUserPolicy \
  --start-time $(date -d '24 hours ago' --iso-8601) \
  --end-time $(date --iso-8601)
```

### Security Hardening

1. **Update security groups:**
```bash
# Review and tighten security group rules
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=ons-data-platform-* \
  --query 'SecurityGroups[*].[GroupName,IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[*].CidrIp]]' \
  --output table
```

2. **Rotate access keys:**
```bash
# List old access keys
aws iam list-access-keys \
  --query 'AccessKeyMetadata[?Age>`90`].[AccessKeyId,CreateDate]' \
  --output table
```

## Maintenance Windows

### Scheduled Maintenance Procedure

1. **Pre-maintenance (30 minutes before):**
```bash
# Notify users
aws sns publish \
  --topic-arn $(terraform output -raw deployment_sns_topic_arn) \
  --message "Scheduled maintenance starting in 30 minutes. API may be temporarily unavailable."

# Create backup
aws s3 sync s3://$(terraform output -raw s3_processed_bucket_name) \
  s3://$(terraform output -raw s3_processed_bucket_name)-maintenance-backup-$(date +%Y%m%d)
```

2. **During maintenance:**
```bash
# Enable maintenance mode
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_maintenance_mode

# Perform maintenance tasks
terraform plan -var-file="environments/prod.tfvars"
terraform apply -var-file="environments/prod.tfvars"
```

3. **Post-maintenance:**
```bash
# Disable maintenance mode
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled false

# Run health checks
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor timestream_loader

# Notify completion
aws sns publish \
  --topic-arn $(terraform output -raw deployment_sns_topic_arn) \
  --message "Scheduled maintenance completed successfully. All systems operational."
```

## Contact Information

### Escalation Matrix

1. **Level 1 - Operations Team**
   - Email: ops-team@company.com
   - Slack: #ops-alerts
   - Phone: +1-555-OPS-TEAM

2. **Level 2 - Engineering Team**
   - Email: engineering@company.com
   - Slack: #engineering-alerts
   - Phone: +1-555-ENG-TEAM

3. **Level 3 - Architecture Team**
   - Email: architecture@company.com
   - Slack: #architecture-alerts
   - Phone: +1-555-ARCH-TEAM

### Emergency Contacts

- **Security Incidents**: security@company.com
- **Data Privacy**: privacy@company.com
- **Legal/Compliance**: legal@company.com
- **Executive Escalation**: executives@company.com

---

**Last Updated**: $(date)
**Version**: 1.0
**Next Review**: $(date -d '+3 months')