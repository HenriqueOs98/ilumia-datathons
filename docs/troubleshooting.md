# Troubleshooting Guide

## Overview

This guide provides solutions to common issues encountered in the ONS Data Platform, organized by component and symptom.

## Table of Contents

1. [General Troubleshooting](#general-troubleshooting)
2. [Lambda Function Issues](#lambda-function-issues)
3. [API Gateway Problems](#api-gateway-problems)
4. [S3 and Data Processing](#s3-and-data-processing)
5. [Timestream Database Issues](#timestream-database-issues)
6. [Knowledge Base and RAG](#knowledge-base-and-rag)
7. [Deployment and CI/CD](#deployment-and-cicd)
8. [Performance Issues](#performance-issues)
9. [Security and Access](#security-and-access)
10. [Cost and Billing](#cost-and-billing)

## General Troubleshooting

### System Health Check

Before diving into specific issues, run a comprehensive health check:

```bash
# Quick health check script
#!/bin/bash
echo "=== ONS Data Platform Health Check ==="

# Check AWS CLI configuration
aws sts get-caller-identity

# Check Lambda functions
for func in lambda_router structured_data_processor rag_query_processor timestream_loader; do
    echo "Checking $func..."
    aws lambda get-function --function-name $func --query 'Configuration.State' --output text
done

# Check API Gateway
api_id=$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text)
echo "API Gateway ID: $api_id"

# Check S3 buckets
aws s3 ls | grep ons-data-platform

# Check Timestream database
aws timestream-query query --query-string "SHOW TABLES FROM \"ons_energy_data\""
```

### Common Error Patterns

#### "Access Denied" Errors

**Symptoms**: 403 errors, permission denied messages

**Causes**:
- Incorrect IAM permissions
- Missing resource policies
- Cross-account access issues

**Solutions**:
```bash
# Check current IAM identity
aws sts get-caller-identity

# Verify IAM role permissions
aws iam get-role-policy --role-name lambda-execution-role --policy-name lambda-policy

# Check resource-based policies
aws s3api get-bucket-policy --bucket ons-data-platform-raw-prod
```

#### "Resource Not Found" Errors

**Symptoms**: 404 errors, NoSuchBucket, function not found

**Causes**:
- Resources not deployed
- Incorrect resource names
- Wrong AWS region

**Solutions**:
```bash
# Verify resource existence
aws lambda list-functions --query 'Functions[?contains(FunctionName, `ons-data-platform`)]'

# Check current region
aws configure get region

# List all S3 buckets
aws s3 ls
```

## Lambda Function Issues

### Cold Start Problems

**Symptoms**:
- High latency on first invocation
- Timeout errors after periods of inactivity
- Inconsistent performance

**Diagnosis**:
```bash
# Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=lambda_router \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Solutions**:
1. **Enable Provisioned Concurrency**:
```bash
aws lambda put-provisioned-concurrency-config \
  --function-name lambda_router \
  --qualifier $LATEST \
  --provisioned-concurrency-config ProvisionedConcurrencyConfigs=2
```

2. **Optimize Package Size**:
```bash
# Remove unnecessary files
cd src/lambda_router
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
zip -r function.zip . -x "tests/*" "*.pyc" "__pycache__/*"
```

3. **Use Lambda Layers**:
```bash
# Create layer for common dependencies
zip -r shared-layer.zip python/
aws lambda publish-layer-version \
  --layer-name ons-shared-utils \
  --zip-file fileb://shared-layer.zip \
  --compatible-runtimes python3.11
```

### Memory and Timeout Issues

**Symptoms**:
- "Task timed out" errors
- Out of memory errors
- Slow processing

**Diagnosis**:
```bash
# Check memory usage
aws logs filter-log-events \
  --log-group-name /aws/lambda/structured_data_processor \
  --filter-pattern "REPORT" \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --query 'events[*].message'
```

**Solutions**:
1. **Increase Memory**:
```bash
aws lambda update-function-configuration \
  --function-name structured_data_processor \
  --memory-size 1024
```

2. **Increase Timeout**:
```bash
aws lambda update-function-configuration \
  --function-name structured_data_processor \
  --timeout 300
```

3. **Optimize Code**:
```python
# Use streaming for large files
import pandas as pd

def process_large_csv(file_path):
    chunk_size = 10000
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        yield process_chunk(chunk)
```

### Import and Dependency Errors

**Symptoms**:
- "No module named" errors
- Import failures
- Package version conflicts

**Diagnosis**:
```bash
# Check function configuration
aws lambda get-function --function-name lambda_router

# Download and inspect package
aws lambda get-function --function-name lambda_router \
  --query 'Code.Location' --output text | xargs wget -O function.zip
unzip -l function.zip
```

**Solutions**:
1. **Fix Dependencies**:
```bash
# Install dependencies correctly
cd src/lambda_router
pip install -r requirements.txt -t .
zip -r function.zip .
```

2. **Use Virtual Environment**:
```bash
python -m venv lambda-env
source lambda-env/bin/activate
pip install -r requirements.txt
```

## API Gateway Problems

### High Latency Issues

**Symptoms**:
- Slow API responses
- Timeout errors
- Poor user experience

**Diagnosis**:
```bash
# Check API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=ons-data-platform-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Solutions**:
1. **Enable Caching**:
```bash
aws apigateway update-stage \
  --rest-api-id $API_ID \
  --stage-name prod \
  --patch-ops op=replace,path=/cacheClusterEnabled,value=true
```

2. **Optimize Lambda**:
```python
# Cache expensive operations
import functools
import time

@functools.lru_cache(maxsize=128)
def expensive_operation(param):
    # Cache results for repeated calls
    return compute_result(param)
```

### Authentication Problems

**Symptoms**:
- 401 Unauthorized errors
- API key validation failures
- CORS issues

**Diagnosis**:
```bash
# Check API key
aws apigateway get-api-keys

# Test authentication
curl -X GET "https://$API_ID.execute-api.us-east-1.amazonaws.com/prod/health" \
  -H "x-api-key: $API_KEY" \
  -v
```

**Solutions**:
1. **Verify API Key**:
```bash
# Create new API key
aws apigateway create-api-key \
  --name ons-platform-key \
  --description "API key for ONS platform"

# Associate with usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-id $API_KEY_ID \
  --key-type API_KEY
```

2. **Fix CORS**:
```bash
# Enable CORS for all methods
aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters method.response.header.Access-Control-Allow-Origin=true
```

## S3 and Data Processing

### File Processing Failures

**Symptoms**:
- Files stuck in raw bucket
- Processing never starts
- EventBridge not triggering

**Diagnosis**:
```bash
# Check EventBridge rules
aws events list-rules --name-prefix ons-data-platform

# Check rule targets
aws events list-targets-by-rule --rule ons-data-platform-s3-processing

# Check S3 event notifications
aws s3api get-bucket-notification-configuration \
  --bucket ons-data-platform-raw-prod
```

**Solutions**:
1. **Fix EventBridge Rule**:
```bash
# Update rule pattern
aws events put-rule \
  --name ons-data-platform-s3-processing \
  --event-pattern '{
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {"name": ["ons-data-platform-raw-prod"]}
    }
  }'
```

2. **Reprocess Failed Files**:
```bash
# List files in raw bucket
aws s3 ls s3://ons-data-platform-raw-prod/ --recursive

# Manually trigger processing
aws stepfunctions start-execution \
  --state-machine-arn $STATE_MACHINE_ARN \
  --input '{
    "bucket": "ons-data-platform-raw-prod",
    "key": "failed-file.csv"
  }'
```

### Data Quality Issues

**Symptoms**:
- Malformed data in processed bucket
- Schema validation errors
- Missing or corrupted files

**Diagnosis**:
```bash
# Check processed files
aws s3 ls s3://ons-data-platform-processed-prod/ --recursive

# Download and inspect
aws s3 cp s3://ons-data-platform-processed-prod/sample.parquet .
python -c "import pandas as pd; print(pd.read_parquet('sample.parquet').info())"
```

**Solutions**:
1. **Implement Data Validation**:
```python
def validate_energy_data(df):
    """Validate energy data DataFrame"""
    required_columns = ['timestamp', 'region', 'value']
    
    # Check required columns
    missing_cols = set(required_columns) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")
    
    # Check data types
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        raise ValueError("Timestamp column must be datetime")
    
    # Check for null values
    if df[required_columns].isnull().any().any():
        raise ValueError("Required columns cannot have null values")
    
    return True
```

2. **Add Data Cleaning**:
```python
def clean_energy_data(df):
    """Clean and standardize energy data"""
    # Remove duplicates
    df = df.drop_duplicates()
    
    # Standardize column names
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    
    # Convert timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Remove outliers
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        df = df[~((df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR)))]
    
    return df
```

## Timestream Database Issues

### Write Failures

**Symptoms**:
- Data not appearing in Timestream
- Write throttling errors
- High write latency

**Diagnosis**:
```bash
# Check Timestream metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name UserErrors \
  --dimensions Name=DatabaseName,Value=ons_energy_data \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum

# Check recent writes
aws timestream-query query \
  --query-string "SELECT COUNT(*), MAX(time) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)"
```

**Solutions**:
1. **Implement Batch Writing**:
```python
def batch_write_timestream(records, batch_size=100):
    """Write records to Timestream in batches"""
    timestream = boto3.client('timestream-write')
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            timestream.write_records(
                DatabaseName='ons_energy_data',
                TableName='generation_data',
                Records=batch
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                time.sleep(2 ** retry_count)  # Exponential backoff
                continue
            raise
```

2. **Optimize Record Format**:
```python
def format_timestream_record(row):
    """Format DataFrame row for Timestream"""
    return {
        'Time': str(int(row['timestamp'].timestamp() * 1000)),
        'TimeUnit': 'MILLISECONDS',
        'Dimensions': [
            {'Name': 'region', 'Value': str(row['region'])},
            {'Name': 'source', 'Value': str(row['energy_source'])}
        ],
        'MeasureName': 'generation',
        'MeasureValue': str(row['value']),
        'MeasureValueType': 'DOUBLE'
    }
```

### Query Performance Issues

**Symptoms**:
- Slow query responses
- Query timeouts
- High costs

**Diagnosis**:
```bash
# Check query performance
aws timestream-query query \
  --query-string "SELECT * FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)" \
  --max-rows 10
```

**Solutions**:
1. **Optimize Queries**:
```sql
-- Use time-based filtering
SELECT region, AVG(measure_value::double) as avg_generation
FROM "ons_energy_data"."generation_data"
WHERE time BETWEEN ago(24h) AND now()
  AND region = 'Southeast'
GROUP BY region

-- Use appropriate time granularity
SELECT bin(time, 1h) as hour, AVG(measure_value::double)
FROM "ons_energy_data"."generation_data"
WHERE time > ago(7d)
GROUP BY bin(time, 1h)
ORDER BY hour
```

2. **Implement Caching**:
```python
import redis
import json

redis_client = redis.Redis(host='elasticache-endpoint')

def cached_timestream_query(query, cache_ttl=300):
    """Cache Timestream query results"""
    cache_key = f"timestream:{hash(query)}"
    
    # Check cache first
    cached_result = redis_client.get(cache_key)
    if cached_result:
        return json.loads(cached_result)
    
    # Execute query
    result = timestream_client.query(QueryString=query)
    
    # Cache result
    redis_client.setex(cache_key, cache_ttl, json.dumps(result))
    
    return result
```

## Knowledge Base and RAG

### Query Processing Failures

**Symptoms**:
- RAG queries returning empty results
- Knowledge Base not finding relevant content
- Poor answer quality

**Diagnosis**:
```bash
# Check Knowledge Base status
aws bedrock-agent get-knowledge-base --knowledge-base-id $KB_ID

# Check data source sync
aws bedrock-agent list-data-source-sync-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID

# Test direct query
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query '{"text": "energy generation"}'
```

**Solutions**:
1. **Improve Data Chunking**:
```python
def chunk_document(text, chunk_size=300, overlap=50):
    """Chunk document with overlap for better context"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks
```

2. **Optimize Query Processing**:
```python
def preprocess_query(query):
    """Preprocess user query for better retrieval"""
    # Expand abbreviations
    abbreviations = {
        'ONS': 'Operador Nacional do Sistema Elétrico',
        'MW': 'megawatt',
        'GW': 'gigawatt'
    }
    
    for abbr, full in abbreviations.items():
        query = query.replace(abbr, full)
    
    # Add context keywords
    energy_keywords = ['energia', 'geração', 'consumo', 'transmissão']
    if not any(keyword in query.lower() for keyword in energy_keywords):
        query += ' energia elétrica'
    
    return query
```

### Embedding Issues

**Symptoms**:
- Poor semantic search results
- Inconsistent retrieval quality
- High embedding costs

**Solutions**:
1. **Optimize Embedding Strategy**:
```python
def create_enhanced_embeddings(text):
    """Create embeddings with metadata"""
    # Add metadata to improve context
    metadata = extract_metadata(text)
    enhanced_text = f"{text}\nMetadata: {metadata}"
    
    # Use appropriate embedding model
    response = bedrock_client.invoke_model(
        modelId='amazon.titan-embed-text-v1',
        body=json.dumps({
            'inputText': enhanced_text
        })
    )
    
    return json.loads(response['body'].read())
```

2. **Implement Hybrid Search**:
```python
def hybrid_search(query, knowledge_base_id):
    """Combine semantic and keyword search"""
    # Semantic search via Knowledge Base
    semantic_results = bedrock_runtime.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={'text': query}
    )
    
    # Keyword search via OpenSearch
    keyword_results = opensearch_client.search(
        index='documents',
        body={
            'query': {
                'multi_match': {
                    'query': query,
                    'fields': ['title', 'content']
                }
            }
        }
    )
    
    # Combine and rank results
    return combine_search_results(semantic_results, keyword_results)
```

## Deployment and CI/CD

### GitHub Actions Failures

**Symptoms**:
- Pipeline failures
- Deployment timeouts
- Test failures

**Diagnosis**:
```bash
# Check workflow runs
gh run list --workflow=deploy-lambda.yml

# View specific run logs
gh run view $RUN_ID --log
```

**Solutions**:
1. **Fix Common Pipeline Issues**:
```yaml
# Add retry logic
- name: Deploy with retry
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: |
      aws lambda update-function-code \
        --function-name ${{ matrix.function }} \
        --zip-file fileb://function.zip
```

2. **Improve Test Reliability**:
```python
# Use proper mocking
import pytest
from moto import mock_s3, mock_lambda

@mock_s3
@mock_lambda
def test_lambda_function():
    # Setup mocks
    s3_client = boto3.client('s3', region_name='us-east-1')
    s3_client.create_bucket(Bucket='test-bucket')
    
    # Run test
    result = lambda_handler(test_event, test_context)
    assert result['statusCode'] == 200
```

### Terraform Issues

**Symptoms**:
- State lock errors
- Resource conflicts
- Plan/apply failures

**Diagnosis**:
```bash
# Check state
terraform state list

# Validate configuration
terraform validate

# Check for drift
terraform plan -detailed-exitcode
```

**Solutions**:
1. **Fix State Issues**:
```bash
# Force unlock (use with caution)
terraform force-unlock $LOCK_ID

# Import existing resources
terraform import aws_s3_bucket.example bucket-name

# Remove from state
terraform state rm aws_s3_bucket.example
```

2. **Handle Resource Conflicts**:
```bash
# Target specific resources
terraform apply -target=module.s3

# Refresh state
terraform refresh

# Replace problematic resources
terraform apply -replace=aws_lambda_function.example
```

## Performance Issues

### High Latency

**Root Causes**:
- Cold starts
- Large package sizes
- Inefficient algorithms
- Network latency

**Solutions**:
1. **Optimize Lambda Performance**:
```python
# Connection pooling
import boto3
from botocore.config import Config

# Reuse connections
config = Config(
    retries={'max_attempts': 3},
    max_pool_connections=50
)
s3_client = boto3.client('s3', config=config)

# Cache expensive operations
@functools.lru_cache(maxsize=128)
def get_configuration():
    return load_config_from_s3()
```

2. **Implement Caching**:
```python
# API response caching
from functools import wraps
import time

def cache_response(ttl=300):
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            
            if key in cache and now - cache[key]['time'] < ttl:
                return cache[key]['result']
            
            result = func(*args, **kwargs)
            cache[key] = {'result': result, 'time': now}
            return result
        
        return wrapper
    return decorator
```

### Memory Issues

**Solutions**:
1. **Optimize Memory Usage**:
```python
# Process data in chunks
def process_large_dataset(file_path):
    chunk_size = 10000
    
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        # Process chunk
        processed_chunk = transform_data(chunk)
        
        # Write immediately to free memory
        write_to_output(processed_chunk)
        
        # Explicit cleanup
        del processed_chunk
        gc.collect()
```

2. **Use Streaming**:
```python
# Stream large files
def stream_s3_object(bucket, key):
    s3_client = boto3.client('s3')
    
    response = s3_client.get_object(Bucket=bucket, Key=key)
    
    # Stream content
    for line in response['Body'].iter_lines():
        yield line.decode('utf-8')
```

## Security and Access

### IAM Permission Issues

**Diagnosis**:
```bash
# Check current permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/lambda-role \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::bucket/key
```

**Solutions**:
1. **Fix IAM Policies**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::ons-data-platform-*/*"
      ]
    }
  ]
}
```

### Security Vulnerabilities

**Solutions**:
1. **Update Dependencies**:
```bash
# Check for vulnerabilities
pip audit

# Update packages
pip install --upgrade package-name

# Use security scanning
bandit -r src/
```

2. **Implement Security Headers**:
```python
def add_security_headers(response):
    """Add security headers to API response"""
    headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    }
    
    response['headers'].update(headers)
    return response
```

## Cost and Billing

### Unexpected Costs

**Diagnosis**:
```bash
# Check cost breakdown
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

**Solutions**:
1. **Optimize Costs**:
```bash
# Set up budget alerts
aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://budget.json

# Clean up old resources
aws lambda list-functions \
  --query 'Functions[?LastModified<`2024-01-01`].FunctionName' \
  --output text | xargs -I {} aws lambda delete-function --function-name {}
```

2. **Implement Cost Controls**:
```python
def check_cost_threshold():
    """Check if costs exceed threshold"""
    ce_client = boto3.client('ce')
    
    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': '2024-01-01',
            'End': '2024-01-31'
        },
        Granularity='MONTHLY',
        Metrics=['BlendedCost']
    )
    
    current_cost = float(response['ResultsByTime'][0]['Total']['BlendedCost']['Amount'])
    
    if current_cost > COST_THRESHOLD:
        send_alert(f"Cost threshold exceeded: ${current_cost}")
```

## Emergency Procedures

### System-Wide Outage

1. **Immediate Response**:
```bash
# Check system status
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor timestream_loader

# Stop all deployments
aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses InProgress | \
  xargs -I {} python scripts/rollback.py --action stop-deployment --deployment-id {}
```

2. **Rollback Procedures**:
```bash
# Rollback all functions
for func in lambda_router structured_data_processor rag_query_processor timestream_loader; do
  python scripts/rollback.py --action rollback-function --function-name $func
done

# Disable feature flags
python scripts/rollback.py --action rollback-flags \
  --application-id $APP_ID \
  --environment-id $ENV_ID \
  --profile-id $PROFILE_ID \
  --flags enable_new_features
```

### Data Corruption

1. **Stop Processing**:
```bash
# Disable EventBridge rules
aws events disable-rule --name ons-data-platform-s3-processing

# Stop Step Functions
aws stepfunctions list-executions \
  --state-machine-arn $STATE_MACHINE_ARN \
  --status-filter RUNNING | \
  jq -r '.executions[].executionArn' | \
  xargs -I {} aws stepfunctions stop-execution --execution-arn {}
```

2. **Restore from Backup**:
```bash
# Restore S3 data
aws s3 sync s3://backup-bucket/ s3://ons-data-platform-processed-prod/

# Verify data integrity
python scripts/verify_data_integrity.py
```

## Getting Help

### Internal Resources

1. **Documentation**: Check the `docs/` directory
2. **Runbooks**: See `docs/operations-runbook.md`
3. **Logs**: Check CloudWatch Logs for detailed error information

### External Resources

1. **AWS Support**: Create support case for AWS-specific issues
2. **Community**: Stack Overflow, AWS forums
3. **Documentation**: AWS service documentation

### Escalation Path

1. **Level 1**: Operations team (ops-team@company.com)
2. **Level 2**: Engineering team (engineering@company.com)
3. **Level 3**: Architecture team (architecture@company.com)
4. **Emergency**: On-call engineer (emergency@company.com)

---

**Last Updated**: $(date)
**Version**: 1.0
**Next Review**: $(date -d '+1 month')