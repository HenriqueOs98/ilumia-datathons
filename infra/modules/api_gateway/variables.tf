variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "lambda_api_arn" {
  description = "ARN of the API Lambda function"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the API Lambda function"
  type        = string
}

variable "throttle_rate_limit" {
  description = "API Gateway throttle rate limit (requests per second)"
  type        = number
  default     = 1000
}

variable "throttle_burst_limit" {
  description = "API Gateway throttle burst limit"
  type        = number
  default     = 2000
}

variable "premium_throttle_rate_limit" {
  description = "Premium tier throttle rate limit (requests per second)"
  type        = number
  default     = 5000
}

variable "premium_throttle_burst_limit" {
  description = "Premium tier throttle burst limit"
  type        = number
  default     = 10000
}

variable "quota_limit" {
  description = "Daily quota limit for basic plan"
  type        = number
  default     = 10000
}

variable "premium_quota_limit" {
  description = "Daily quota limit for premium plan"
  type        = number
  default     = 100000
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}