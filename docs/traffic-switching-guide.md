# Traffic Switching Guide for InfluxDB Migration

This guide provides step-by-step instructions for switching production traffic from Amazon Timestream to Amazon Timestream for InfluxDB using the traffic switching infrastructure.

## Overview

The traffic switching process uses AWS AppConfig feature flags to gradually migrate API queries from Timestream to InfluxDB while monitoring performance metrics and providing automatic rollback capabilities.

## Prerequisites

1. InfluxDB infrastructure is deployed and healthy
2. Data migration from Timestream to InfluxDB is complete
3. All Lambda functions are updated with traffic switching code
4. Monitoring dashboards and alarms are configured

## Traffic Switching Components

### 1. Feature Flags

- `use_influxdb_for_data_ingestion`: Controls data ingestion backend (should be enabled)
- `use_influxdb_for_api_queries`: Controls API query backend
- `influxdb_traffic_percentage`: Percentage of traffic routed to InfluxDB (0-100)
- `enable_query_performance_monitoring`: Enables detailed performance tracking

### 2. Monitoring

- CloudWatch dashboards for real-time metrics
- Automated alarms for error rates and latency
- Performance comparison between backends
- Automatic rollback triggers

### 3. Deployment Tools

- `traffic_switch_deployment.py`: Command-line tool for managing deployments
- AppConfig integration for configuration management
- Gradual rollout capabilities with configurable steps

## Deployment Process

### Phase 1: Enable InfluxDB Queries (0% Traffic)

1. **Enable InfluxDB for API queries without traffic**:
   ```bash
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     enable-queries
   ```

2. **Verify configuration**:
   ```bash
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     status
   ```

3. **Monitor for 15 minutes** to ensure no errors are introduced.

### Phase 2: Gradual Traffic Rollout

1. **Start with 10% traffic**:
   ```bash
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     gradual-rollout \
     --target 10 \
     --step-size 10 \
     --wait-minutes 15
   ```

2. **Monitor key metrics**:
   - Response time comparison
   - Error rate comparison
   - InfluxDB connection health
   - Lambda function performance

3. **Continue gradual rollout**:
   ```bash
   # 25% traffic
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     set-percentage --percentage 25

   # 50% traffic
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     set-percentage --percentage 50

   # 75% traffic
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     set-percentage --percentage 75
   ```

### Phase 3: Full Migration (100% Traffic)

1. **Complete migration to InfluxDB**:
   ```bash
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     set-percentage --percentage 100
   ```

2. **Monitor for 24 hours** to ensure stability.

3. **Validate all functionality**:
   - API response accuracy
   - Query performance
   - Knowledge Base integration
   - Error rates and latency

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Response Time**:
   - Target: InfluxDB response time ≤ Timestream + 20%
   - Alert threshold: > 10 seconds difference

2. **Error Rate**:
   - Target: < 5% error rate
   - Alert threshold: > 5% error rate for 2 consecutive periods

3. **Connection Health**:
   - Target: < 10 connection failures per 5 minutes
   - Alert threshold: > 10 connection failures

4. **Success Rate**:
   - Target: > 95% success rate
   - Alert threshold: < 95% success rate for 3 consecutive periods

### CloudWatch Dashboards

Access the traffic switching dashboard:
- Dashboard name: `ons-data-platform-production-traffic-switching`
- Includes real-time metrics for both backends
- Error logs and performance comparisons

### Automated Alarms

The following alarms will trigger automatic notifications:

1. `ons-data-platform-influxdb-migration-error-rate`
2. `ons-data-platform-influxdb-migration-latency`
3. `ons-data-platform-influxdb-connection-failures`
4. `ons-data-platform-traffic-switch-success-rate`
5. `ons-data-platform-influxdb-latency-comparison`

## Rollback Procedures

### Automatic Rollback

The system will automatically rollback if:
- Error rate exceeds 5% for 2 consecutive periods
- Response time exceeds 10 seconds difference for 3 consecutive periods
- Connection failures exceed threshold

### Manual Rollback

1. **Emergency rollback to 0% InfluxDB traffic**:
   ```bash
   python scripts/traffic_switch_deployment.py \
     --app-name ons-data-platform-app \
     --environment production \
     set-percentage --percentage 0
   ```

2. **Disable InfluxDB queries entirely**:
   ```bash
   # Update AppConfig directly via AWS Console
   # Set use_influxdb_for_api_queries.enabled = false
   ```

3. **Verify rollback**:
   - Check CloudWatch metrics
   - Verify API responses
   - Monitor error rates

## Troubleshooting

### Common Issues

1. **High InfluxDB Response Time**:
   - Check InfluxDB cluster health
   - Verify network connectivity
   - Review query complexity
   - Check resource utilization

2. **Connection Failures**:
   - Verify InfluxDB endpoint accessibility
   - Check security group rules
   - Validate authentication tokens
   - Review VPC configuration

3. **Data Inconsistencies**:
   - Compare query results between backends
   - Verify data migration completeness
   - Check timestamp handling
   - Validate data conversion logic

### Diagnostic Commands

1. **Check Lambda function logs**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/ons-data-platform-production-rag-query-processor \
     --start-time $(date -d '1 hour ago' +%s)000 \
     --filter-pattern "ERROR"
   ```

2. **Check InfluxDB health**:
   ```bash
   # Via Lambda function health check endpoint
   aws lambda invoke \
     --function-name ons-data-platform-production-timeseries-query-processor \
     --payload '{"httpMethod":"GET","path":"/health"}' \
     response.json
   ```

3. **Monitor traffic distribution**:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace ONS/TrafficSwitching \
     --metric-name RequestCount \
     --dimensions Name=Backend,Value=influxdb \
     --start-time $(date -d '1 hour ago' --iso-8601) \
     --end-time $(date --iso-8601) \
     --period 300 \
     --statistics Sum
   ```

## Performance Validation

### Acceptance Criteria

Before completing the migration, validate:

1. **API Response Accuracy**: ✅
   - Query results match between backends
   - Timestamp handling is correct
   - Data aggregations are accurate

2. **Performance Requirements**: ✅
   - Average response time ≤ 5 seconds
   - 95th percentile response time ≤ 10 seconds
   - Error rate < 1%

3. **Knowledge Base Integration**: ✅
   - Time series context detection works
   - RAG responses include InfluxDB data
   - Citations reference correct sources

4. **Monitoring and Alerting**: ✅
   - All alarms are functional
   - Dashboards show accurate data
   - Automated rollback works

### Load Testing

Run load tests to validate performance under production load:

```bash
# Example load test command
python tests/load/test_load_scenarios.py \
  --endpoint https://api.ons-data-platform.com/query \
  --concurrent-users 50 \
  --duration 300 \
  --ramp-up 60
```

## Post-Migration Tasks

After successful migration to 100% InfluxDB traffic:

1. **Update documentation** to reflect InfluxDB as primary backend
2. **Schedule Timestream resource cleanup** (after 30-day retention period)
3. **Update operational runbooks** for InfluxDB maintenance
4. **Archive migration artifacts** for future reference
5. **Conduct post-migration review** and lessons learned session

## Support and Escalation

For issues during traffic switching:

1. **Monitor CloudWatch alarms** for automatic notifications
2. **Check traffic switching dashboard** for real-time status
3. **Review Lambda function logs** for detailed error information
4. **Use rollback procedures** if issues persist
5. **Escalate to platform team** for complex issues

## Configuration Reference

### AppConfig Application Structure

```
ons-data-platform-app/
├── environments/
│   ├── development/
│   └── production/
├── configuration-profiles/
│   ├── feature-flags/
│   └── app-settings/
└── deployment-strategies/
    └── canary-10-percent/
```

### Feature Flag Schema

```json
{
  "flags": {
    "use_influxdb_for_data_ingestion": {
      "name": "use_influxdb_for_data_ingestion",
      "enabled": true
    },
    "use_influxdb_for_api_queries": {
      "name": "use_influxdb_for_api_queries", 
      "enabled": false
    },
    "influxdb_traffic_percentage": {
      "name": "influxdb_traffic_percentage",
      "enabled": true,
      "variant": "0"
    }
  }
}
```

This guide ensures a safe, monitored, and reversible migration from Timestream to InfluxDB with minimal risk to production systems.