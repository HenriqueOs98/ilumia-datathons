output "db_instance_identifier" {
  description = "The InfluxDB instance identifier"
  value       = aws_timestreaminfluxdb_db_instance.main.name
}

output "db_instance_arn" {
  description = "The ARN of the InfluxDB instance"
  value       = aws_timestreaminfluxdb_db_instance.main.arn
}

output "endpoint" {
  description = "The connection endpoint for the InfluxDB instance"
  value       = aws_timestreaminfluxdb_db_instance.main.endpoint
}

output "port" {
  description = "The port the InfluxDB instance is listening on"
  value       = 8086 # InfluxDB default port
}

output "db_name" {
  description = "The name of the database"
  value       = aws_timestreaminfluxdb_db_instance.main.name
}

output "username" {
  description = "The master username for the database"
  value       = aws_timestreaminfluxdb_db_instance.main.username
  sensitive   = true
}

output "availability_zone" {
  description = "The availability zone of the instance"
  value       = aws_timestreaminfluxdb_db_instance.main.availability_zone
}

output "influxdb_organization" {
  description = "The InfluxDB organization"
  value       = aws_timestreaminfluxdb_db_instance.main.organization
}

output "influxdb_bucket" {
  description = "The InfluxDB bucket"
  value       = aws_timestreaminfluxdb_db_instance.main.bucket
}

# Security Group Outputs
output "security_group_id" {
  description = "The ID of the InfluxDB security group"
  value       = aws_security_group.influxdb.id
}

output "lambda_security_group_id" {
  description = "The ID of the Lambda client security group"
  value       = aws_security_group.lambda_influxdb_client.id
}

# IAM Outputs
output "lambda_role_arn" {
  description = "ARN of the InfluxDB Lambda IAM role"
  value       = aws_iam_role.influxdb_lambda_role.arn
}

output "lambda_role_name" {
  description = "Name of the InfluxDB Lambda IAM role"
  value       = aws_iam_role.influxdb_lambda_role.name
}

# Secrets Manager Outputs
output "credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret containing InfluxDB credentials"
  value       = aws_secretsmanager_secret.influxdb_credentials.arn
}

output "credentials_secret_name" {
  description = "Name of the Secrets Manager secret containing InfluxDB credentials"
  value       = aws_secretsmanager_secret.influxdb_credentials.name
}

# CloudWatch Outputs
output "lambda_log_group_name" {
  description = "Name of the InfluxDB Lambda CloudWatch log group"
  value       = aws_cloudwatch_log_group.influxdb_lambda_logs.name
}

output "lambda_log_group_arn" {
  description = "ARN of the InfluxDB Lambda CloudWatch log group"
  value       = aws_cloudwatch_log_group.influxdb_lambda_logs.arn
}

# Monitoring Outputs
output "cpu_alarm_arn" {
  description = "ARN of the CPU utilization CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.influxdb_cpu_utilization.arn
}

output "connection_alarm_arn" {
  description = "ARN of the connection count CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.influxdb_connection_count.arn
}

# KMS Outputs
output "kms_key_id" {
  description = "The globally unique identifier for the KMS key"
  value       = var.storage_encrypted ? aws_kms_key.influxdb[0].key_id : null
}

output "kms_key_arn" {
  description = "The Amazon Resource Name (ARN) of the KMS key"
  value       = var.storage_encrypted ? aws_kms_key.influxdb[0].arn : null
}

# Network Configuration Outputs
output "vpc_subnet_ids" {
  description = "The VPC subnet IDs used by InfluxDB"
  value       = aws_timestreaminfluxdb_db_instance.main.vpc_subnet_ids
}

# Configuration for Lambda Environment Variables
output "lambda_environment_variables" {
  description = "Environment variables for Lambda functions to connect to InfluxDB"
  value = {
    INFLUXDB_ENDPOINT   = aws_timestreaminfluxdb_db_instance.main.endpoint
    INFLUXDB_PORT       = "8086"
    INFLUXDB_DATABASE   = aws_timestreaminfluxdb_db_instance.main.name
    INFLUXDB_ORG        = aws_timestreaminfluxdb_db_instance.main.organization
    INFLUXDB_BUCKET     = aws_timestreaminfluxdb_db_instance.main.bucket
    INFLUXDB_SECRET_ARN = aws_secretsmanager_secret.influxdb_credentials.arn
    INFLUXDB_LOG_GROUP  = aws_cloudwatch_log_group.influxdb_lambda_logs.name
  }
  sensitive = true
}

# Connection String for Applications
output "connection_info" {
  description = "Connection information for InfluxDB"
  value = {
    endpoint = aws_timestreaminfluxdb_db_instance.main.endpoint
    port     = 8086
    database = aws_timestreaminfluxdb_db_instance.main.name
    org      = aws_timestreaminfluxdb_db_instance.main.organization
    bucket   = aws_timestreaminfluxdb_db_instance.main.bucket
  }
  sensitive = true
}