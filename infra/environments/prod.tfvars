# Production environment configuration
environment = "prod"
aws_region = "us-east-1"
project_name = "ons-data-platform"

# Production-specific settings
enable_deletion_protection = true
log_retention_days = 90
api_throttle_burst_limit = 2000
api_throttle_rate_limit = 1000