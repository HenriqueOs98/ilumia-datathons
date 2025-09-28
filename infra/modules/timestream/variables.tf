variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "memory_retention_hours" {
  description = "Memory store retention period in hours"
  type        = number
  default     = 24
}

variable "magnetic_retention_days" {
  description = "Magnetic store retention period in days"
  type        = number
  default     = 2555 # 7 years
}

variable "processed_data_bucket" {
  description = "S3 bucket name for processed data"
  type        = string
}

variable "rejected_data_bucket" {
  description = "S3 bucket name for rejected data"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}