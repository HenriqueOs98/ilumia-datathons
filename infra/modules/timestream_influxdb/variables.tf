variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where InfluxDB will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for InfluxDB deployment"
  type        = list(string)
}

variable "availability_zone" {
  description = "Availability zone for InfluxDB instance"
  type        = string
  default     = null
}

# Database Configuration
variable "allocated_storage" {
  description = "The allocated storage in gibibytes"
  type        = number
  default     = 20
}

variable "db_instance_class" {
  description = "The InfluxDB instance class"
  type        = string
  default     = "db.influx.medium"
}

variable "db_name" {
  description = "The name of the database to create when the DB instance is created"
  type        = string
  default     = "ons_energy_data"
}

variable "username" {
  description = "Username for the master DB user"
  type        = string
  default     = "admin"
}

variable "password" {
  description = "Password for the master DB user"
  type        = string
  sensitive   = true
}

variable "port" {
  description = "The port on which the DB accepts connections"
  type        = number
  default     = 8086
}

variable "engine_version" {
  description = "The engine version to use"
  type        = string
  default     = "2.0.x"
}

# InfluxDB Specific Configuration
variable "influxdb_org" {
  description = "InfluxDB organization name"
  type        = string
  default     = "ons-energy"
}

variable "influxdb_bucket" {
  description = "Default InfluxDB bucket name"
  type        = string
  default     = "energy_data"
}

variable "influxdb_token" {
  description = "InfluxDB authentication token"
  type        = string
  sensitive   = true
}

# Backup and Maintenance
variable "backup_retention_period" {
  description = "The days to retain backups for"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "The daily time range during which automated backups are created"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "The window to perform maintenance in"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "apply_immediately" {
  description = "Specifies whether any database modifications are applied immediately"
  type        = bool
  default     = false
}

variable "auto_minor_version_upgrade" {
  description = "Indicates that minor engine upgrades will be applied automatically"
  type        = bool
  default     = true
}

# Security Configuration
variable "publicly_accessible" {
  description = "Bool to control if instance is publicly accessible"
  type        = bool
  default     = false
}

variable "storage_encrypted" {
  description = "Specifies whether the DB instance is encrypted"
  type        = bool
  default     = true
}

variable "storage_type" {
  description = "One of 'standard' (magnetic), 'gp2' (general purpose SSD), or 'io1' (provisioned IOPS SSD)"
  type        = string
  default     = "gp2"
}

variable "deletion_protection" {
  description = "If the DB instance should have deletion protection enabled"
  type        = bool
  default     = true
}

variable "final_db_snapshot_identifier" {
  description = "The name of your final DB snapshot when this DB instance is deleted"
  type        = string
  default     = null
}

variable "skip_final_snapshot" {
  description = "Determines whether a final DB snapshot is created before the DB instance is deleted"
  type        = bool
  default     = false
}

variable "db_parameter_group_name" {
  description = "Name of the DB parameter group to associate"
  type        = string
  default     = "default.influxdb"
}

# S3 Configuration
variable "processed_data_bucket" {
  description = "S3 bucket name for processed data"
  type        = string
}

variable "rejected_data_bucket" {
  description = "S3 bucket name for rejected data"
  type        = string
}

# Monitoring Configuration
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "cpu_alarm_threshold" {
  description = "CPU utilization threshold for CloudWatch alarm"
  type        = number
  default     = 80
}

variable "connection_alarm_threshold" {
  description = "Connection count threshold for CloudWatch alarm"
  type        = number
  default     = 80
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarm triggers"
  type        = list(string)
  default     = []
}

# KMS Configuration
variable "kms_deletion_window" {
  description = "The waiting period, specified in number of days, after which the KMS key is deleted"
  type        = number
  default     = 7
}

# Retention Policies
variable "memory_retention_hours" {
  description = "Memory store retention period in hours (InfluxDB equivalent)"
  type        = number
  default     = 24
}

variable "magnetic_retention_days" {
  description = "Long-term storage retention period in days"
  type        = number
  default     = 2555 # 7 years
}