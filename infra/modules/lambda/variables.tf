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

# Timestream-related variables removed as part of decommissioning
# These variables were used by the timestream_loader function which has been removed

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