variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "s3_processed_bucket" {
  description = "S3 processed data bucket name"
  type        = string
}