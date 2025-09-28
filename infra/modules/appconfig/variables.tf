variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "development_alarm_arn" {
  description = "CloudWatch alarm ARN for development environment monitoring"
  type        = string
  default     = ""
}

variable "production_alarm_arn" {
  description = "CloudWatch alarm ARN for production environment monitoring"
  type        = string
  default     = ""
}