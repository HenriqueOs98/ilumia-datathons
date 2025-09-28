# InfluxDB Monitor Lambda Function

This Lambda function provides comprehensive monitoring and health checking for the InfluxDB instance in the ONS Data Platform. It performs connectivity checks, measures query and write performance, collects resource utilization metrics, and estimates costs.

## Features

- **Health Checks**: Connectivity, read/write capability testing
- **Performance Monitoring**: Query execution time, write throughput measurement
- **Resource Metrics**: CPU, memory, disk utilization tracking
- **Cost Estimation**: Usage-based cost calculations
- **CloudWatch Integration**: Automatic metric publishing for alerting

## Metrics Published

### Connectivity Metrics
- `ConnectionStatus`: 1 for healthy, 0 for unhealthy
- `HealthCheckResponseTime`: Response time in milliseconds

### Performance Metrics
- `QueryExecutionTime`: Query execution time by query type
- `QueryThroughput`: Results per second by query type
- `WriteLatency`: Write operation latency
- `WriteThroughput`: Points written per second

### Resource Metrics
- `CPUUtilization`: CPU usage percentage
- `MemoryUtilization`: Memory usage percentage
- `DiskUtilization`: Disk usage percentage
- `ActiveConnections`: Number of active connections

### Cost Metrics
- `EstimatedDailyCost`: Estimated daily cost in USD
- `StorageUsage`: Storage usage in GB

## Environment Variables

- `INFLUXDB_URL`: InfluxDB connection URL
- `INFLUXDB_TOKEN`: Authentication token (or use Secrets Manager)
- `INFLUXDB_ORG`: InfluxDB organization name
- `INFLUXDB_BUCKET`: Default bucket name
- `CLOUDWATCH_NAMESPACE`: CloudWatch namespace (default: ONS/InfluxDB)
- `ENVIRONMENT`: Environment name for tagging
- `INFLUXDB_INSTANCE_TYPE`: Instance type for cost estimation

## Deployment

This function should be deployed with:
- VPC access to reach InfluxDB instance
- IAM permissions for CloudWatch metrics publishing
- Scheduled execution (recommended: every 5 minutes)

## Usage

The function can be invoked manually or scheduled via EventBridge. It returns comprehensive monitoring data and publishes metrics to CloudWatch for alerting and dashboards.