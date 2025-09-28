variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "s3_raw_bucket" {
  description = "S3 raw data bucket name"
  type        = string
}

variable "s3_processed_bucket" {
  description = "S3 processed data bucket name"
  type        = string
}

variable "s3_processed_bucket_arn" {
  description = "S3 processed data bucket ARN"
  type        = string
}

# InfluxDB-related variables
variable "influxdb_url" {
  description = "InfluxDB instance URL"
  type        = string
}

variable "influxdb_org" {
  description = "InfluxDB organization name"
  type        = string
  default     = "ons-energy"
}

variable "influxdb_bucket" {
  description = "InfluxDB bucket name for time series data"
  type        = string
  default     = "energy_data"
}

variable "influxdb_token_secret_name" {
  description = "AWS Secrets Manager secret name containing InfluxDB token"
  type        = string
}

# VPC configuration for InfluxDB Lambda
variable "vpc_id" {
  description = "VPC ID for Lambda functions"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda functions"
  type        = list(string)
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for alarms"
  type        = string
  default     = ""
}

variable "knowledge_base_id" {
  description = "Amazon Bedrock Knowledge Base ID"
  type        = string
}

variable "bedrock_model_arn" {
  description = "Amazon Bedrock model ARN for RAG generation"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
}