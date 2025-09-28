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

variable "enable_deletion_protection" {
  description = "Enable deletion protection for critical resources"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "api_throttle_burst_limit" {
  description = "API Gateway throttle burst limit"
  type        = number
  default     = 2000
}

variable "api_throttle_rate_limit" {
  description = "API Gateway throttle rate limit"
  type        = number
  default     = 1000
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