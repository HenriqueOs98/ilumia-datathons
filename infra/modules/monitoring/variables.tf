variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ons-data-platform"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "critical_alert_emails" {
  description = "List of email addresses for critical alerts"
  type        = list(string)
  default     = []
}

variable "warning_alert_emails" {
  description = "List of email addresses for warning alerts"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30
}

variable "api_gateway_id" {
  description = "API Gateway ID for log group creation"
  type        = string
}

variable "step_functions_arn" {
  description = "Step Functions state machine ARN for monitoring"
  type        = string
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD for the ONS Data Platform"
  type        = number
  default     = 500
}

variable "cost_alert_emails" {
  description = "List of email addresses for cost alerts"
  type        = list(string)
  default     = []
}

variable "cost_anomaly_threshold" {
  description = "Cost anomaly threshold in USD"
  type        = number
  default     = 50
}

# InfluxDB Monitoring Variables
variable "influxdb_max_connections_threshold" {
  description = "Maximum number of InfluxDB connections before alerting"
  type        = number
  default     = 100
}

variable "influxdb_daily_cost_threshold" {
  description = "Daily cost threshold for InfluxDB in USD"
  type        = number
  default     = 50
}

variable "influxdb_storage_threshold_gb" {
  description = "Storage usage threshold for InfluxDB in GB"
  type        = number
  default     = 80
}

variable "influxdb_monitor_lambda_arn" {
  description = "ARN of the InfluxDB monitor Lambda function"
  type        = string
  default     = ""
}
