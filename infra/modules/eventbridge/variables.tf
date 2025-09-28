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

variable "step_function_arn" {
  description = "ARN of the Step Functions state machine"
  type        = string
}