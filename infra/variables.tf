variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "ons-data-platform"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "enable_cross_region_replication" {
  description = "Enable cross-region replication for critical S3 buckets"
  type        = bool
  default     = false
}

variable "replication_region" {
  description = "AWS region for cross-region replication"
  type        = string
  default     = "us-west-2"
}

variable "raw_data_retention_days" {
  description = "Retention period for raw data in days"
  type        = number
  default     = 2555 # 7 years for compliance
}

variable "processed_data_retention_days" {
  description = "Retention period for processed data in days"
  type        = number
  default     = 2555 # 7 years for compliance
}

variable "bedrock_model_arn" {
  description = "Amazon Bedrock model ARN for RAG generation"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
}

# Deployment and Rollback Configuration
variable "deployment_error_threshold" {
  description = "Error rate threshold for automatic rollback (percentage)"
  type        = number
  default     = 5
}

variable "deployment_duration_threshold" {
  description = "Duration threshold in milliseconds for automatic rollback"
  type        = number
  default     = 10000
}

variable "deployment_config_name" {
  description = "CodeDeploy deployment configuration for canary releases"
  type        = string
  default     = "CodeDeployDefault.LambdaCanary10Percent5Minutes"
}

variable "deployment_notification_email" {
  description = "Email address for deployment notifications"
  type        = string
  default     = ""
}

# InfluxDB Configuration
variable "influxdb_password" {
  description = "Password for InfluxDB master user"
  type        = string
  sensitive   = true
  default     = null
}

variable "influxdb_token" {
  description = "InfluxDB authentication token"
  type        = string
  sensitive   = true
  default     = null
}

variable "influxdb_instance_class" {
  description = "InfluxDB instance class"
  type        = string
  default     = "db.influx.medium"
}

variable "influxdb_allocated_storage" {
  description = "InfluxDB allocated storage in GB"
  type        = number
  default     = 20
}

variable "influxdb_backup_retention_period" {
  description = "InfluxDB backup retention period in days"
  type        = number
  default     = 7
}

variable "influxdb_org" {
  description = "InfluxDB organization name"
  type        = string
  default     = "ons-energy"
}

variable "influxdb_bucket" {
  description = "Default InfluxDB bucket name"
  type        = string
  default     = "energy_data"
}

variable "influxdb_token_secret_name" {
  description = "Name of the secret containing the InfluxDB token"
  type        = string
  default     = "ons/influxdb/token"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints for AWS services"
  type        = bool
  default     = true
}