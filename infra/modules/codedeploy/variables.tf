variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "lambda_functions" {
  description = "Map of Lambda functions to configure for blue-green deployment"
  type = map(object({
    function_name = string
    alias_name    = string
  }))
}

variable "error_rate_threshold" {
  description = "Error rate threshold for automatic rollback"
  type        = number
  default     = 5
}

variable "duration_threshold" {
  description = "Duration threshold in milliseconds for automatic rollback"
  type        = number
  default     = 10000
}

variable "deployment_config_name" {
  description = "CodeDeploy deployment configuration"
  type        = string
  default     = "CodeDeployDefault.LambdaCanary10Percent5Minutes"
}

variable "sns_email_endpoint" {
  description = "Email endpoint for deployment alerts"
  type        = string
  default     = ""
}