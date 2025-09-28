# Environment Configuration
environment  = "dev"
project_name = "ons-data-platform"
aws_region   = "us-east-1"

# VPC Configuration
vpc_cidr             = "10.0.0.0/16"
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
enable_nat_gateway   = true
enable_vpc_endpoints = true

# InfluxDB Configuration
influxdb_password                = "SecureInfluxDBPassword123!"
influxdb_token                   = "influxdb-token-placeholder-will-be-generated"
influxdb_instance_class          = "db.influx.medium"
influxdb_allocated_storage       = 20
influxdb_backup_retention_period = 7
influxdb_org                     = "ons-energy"
influxdb_bucket                  = "energy_data"
influxdb_token_secret_name       = "ons/influxdb/token"

# S3 Configuration
enable_cross_region_replication = false
replication_region              = "us-west-2"
raw_data_retention_days         = 2555 # 7 years
processed_data_retention_days   = 2555 # 7 years

# API Configuration
api_throttle_burst_limit = 2000
api_throttle_rate_limit  = 1000

# Monitoring Configuration
log_retention_days = 30

# Bedrock Configuration
bedrock_model_arn = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"

# Deployment Configuration
deployment_error_threshold    = 5
deployment_duration_threshold = 10000
deployment_config_name        = "CodeDeployDefault.LambdaCanary10Percent5Minutes"
deployment_notification_email = "admin@ons-platform.com"

# Security Configuration
enable_deletion_protection = false