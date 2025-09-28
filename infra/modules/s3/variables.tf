variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "enable_cross_region_replication" {
  description = "Enable cross-region replication for critical buckets"
  type        = bool
  default     = false
}

variable "replication_destination_region" {
  description = "Destination region for cross-region replication"
  type        = string
  default     = "us-west-2"
}

variable "enable_mfa_delete" {
  description = "Enable MFA delete for critical buckets"
  type        = bool
  default     = false
}

variable "raw_data_retention_days" {
  description = "Retention period for raw data in days"
  type        = number
  default     = 2555  # 7 years
}

variable "processed_data_retention_days" {
  description = "Retention period for processed data in days"
  type        = number
  default     = 2555  # 7 years
}