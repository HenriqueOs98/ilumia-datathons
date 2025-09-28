# Timestream for InfluxDB Module

This Terraform module provisions Amazon Timestream for InfluxDB infrastructure for the ONS Data Platform. It replaces the traditional Amazon Timestream service to overcome AWS service access limitations while maintaining time series functionality.

## Features

- **InfluxDB Instance**: Fully managed Timestream for InfluxDB database instance
- **VPC Integration**: Secure deployment within private subnets
- **Security Groups**: Properly configured network access controls
- **IAM Roles**: Least-privilege access for Lambda functions
- **Secrets Management**: Secure credential storage using AWS Secrets Manager
- **Monitoring**: CloudWatch alarms for CPU and connection monitoring
- **Encryption**: Optional KMS encryption for data at rest
- **Backup Configuration**: Automated backup with configurable retention

## Architecture

The module creates:

1. **Timestream for InfluxDB Instance**: The main database instance with configurable storage and compute
2. **DB Subnet Group**: Network configuration for multi-AZ deployment
3. **Security Groups**: 
   - InfluxDB security group allowing access from Lambda functions
   - Lambda client security group for outbound connections
4. **IAM Resources**: Roles and policies for Lambda function access
5. **Secrets Manager**: Secure storage for database credentials and connection details
6. **CloudWatch Resources**: Log groups and monitoring alarms
7. **KMS Key**: Optional encryption key for data at rest

## Usage

```hcl
module "timestream_influxdb" {
  source = "./modules/timestream_influxdb"

  environment   = "production"
  project_name  = "ons-data-platform"
  
  # Network Configuration
  vpc_id     = "vpc-12345678"
  subnet_ids = ["subnet-12345678", "subnet-87654321"]
  
  # Database Configuration
  allocated_storage     = 100
  db_instance_class     = "db.influx.large"
  backup_retention_period = 7
  
  # Security
  password = var.influxdb_password
  influxdb_token = var.influxdb_token
  storage_encrypted = true
  
  # S3 Integration
  processed_data_bucket = "ons-processed-data"
  rejected_data_bucket  = "ons-failed-data"
  
  # Monitoring
  alarm_actions = [aws_sns_topic.alerts.arn]
}
```

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| aws | ~> 5.0 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 5.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| environment | Environment name | `string` | n/a | yes |
| project_name | Project name for resource naming | `string` | n/a | yes |
| vpc_id | VPC ID where InfluxDB will be deployed | `string` | n/a | yes |
| subnet_ids | List of subnet IDs for InfluxDB deployment | `list(string)` | n/a | yes |
| password | Password for the master DB user | `string` | n/a | yes |
| influxdb_token | InfluxDB authentication token | `string` | n/a | yes |
| processed_data_bucket | S3 bucket name for processed data | `string` | n/a | yes |
| rejected_data_bucket | S3 bucket name for rejected data | `string` | n/a | yes |
| allocated_storage | The allocated storage in gibibytes | `number` | `20` | no |
| db_instance_class | The InfluxDB instance class | `string` | `"db.influx.medium"` | no |
| backup_retention_period | The days to retain backups for | `number` | `7` | no |
| storage_encrypted | Specifies whether the DB instance is encrypted | `bool` | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| endpoint | The connection endpoint for the InfluxDB instance |
| port | The port the InfluxDB instance is listening on |
| lambda_role_arn | ARN of the InfluxDB Lambda IAM role |
| security_group_id | The ID of the InfluxDB security group |
| lambda_security_group_id | The ID of the Lambda client security group |
| credentials_secret_arn | ARN of the Secrets Manager secret containing InfluxDB credentials |
| lambda_environment_variables | Environment variables for Lambda functions to connect to InfluxDB |

## Security Considerations

1. **Network Security**: The InfluxDB instance is deployed in private subnets with security groups restricting access
2. **Encryption**: Data is encrypted at rest using KMS and in transit using TLS
3. **Access Control**: IAM roles follow least-privilege principles
4. **Credential Management**: Database credentials are stored securely in AWS Secrets Manager
5. **Monitoring**: CloudWatch alarms monitor for unusual activity and performance issues

## Migration from Timestream

This module is designed to replace the existing Timestream module. Key differences:

1. **Service**: Uses Timestream for InfluxDB instead of regular Timestream
2. **Query Language**: Supports InfluxQL and Flux instead of SQL
3. **Data Format**: Uses InfluxDB line protocol instead of Timestream records
4. **Networking**: Requires VPC configuration for secure access

## Monitoring and Alerting

The module includes CloudWatch alarms for:

- **CPU Utilization**: Alerts when CPU usage exceeds threshold
- **Connection Count**: Monitors database connection usage
- **Custom Metrics**: Lambda functions can publish additional metrics

## Backup and Recovery

- **Automated Backups**: Daily backups with configurable retention period
- **Point-in-Time Recovery**: Restore to any point within the backup retention period
- **Final Snapshot**: Optional final snapshot before instance deletion

## Cost Optimization

- **Instance Sizing**: Choose appropriate instance class based on workload
- **Storage Type**: Use gp2 for general purpose, io1 for high IOPS requirements
- **Backup Retention**: Balance data protection needs with storage costs
- **Monitoring**: Track usage metrics to optimize resource allocation