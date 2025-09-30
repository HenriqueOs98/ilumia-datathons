# Traffic Switching Configuration for InfluxDB Migration
# This configuration manages the gradual rollout from Timestream to InfluxDB

# Local content for migration flags
locals {
  migration_flags_content = jsonencode({
    version = "1",
    flags = {
      use_influxdb_for_data_ingestion = {
        name = "use_influxdb_for_data_ingestion"
      },
      use_influxdb_for_api_queries = {
        name = "use_influxdb_for_api_queries"
      },
      enable_query_performance_monitoring = {
        name = "enable_query_performance_monitoring"
      },
      influxdb_traffic_percentage = {
        name = "influxdb_traffic_percentage",
        attributes = {
          percentage = {
            constraints = {
              type = "number"
            }
          }
        }
      }
    },
    values = {
      use_influxdb_for_data_ingestion = {
        enabled = true
      },
      use_influxdb_for_api_queries = {
        enabled = false
      },
      enable_query_performance_monitoring = {
        enabled = true
      },
      influxdb_traffic_percentage = {
        enabled    = true,
        percentage = 0
      }
    }
  })
}

# Use timestamp and content hash for unique versions
resource "random_uuid" "migration_flags_version" {
  keepers = {
    content   = local.migration_flags_content
    timestamp = timestamp()
  }
}

# Feature Flag Configuration for InfluxDB Migration
resource "aws_appconfig_hosted_configuration_version" "influxdb_migration_flags" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  description              = "Migration flags ${substr(random_uuid.migration_flags_version.result, 0, 8)}"
  content_type             = "application/json"
  content                  = local.migration_flags_content

  lifecycle {
    create_before_destroy = true
  }
}

# Local content for traffic switch settings
locals {
  traffic_switch_content = jsonencode({
    traffic_switching = {
      canary_percentage          = 10
      rollback_threshold_errors  = 5
      rollback_threshold_latency = 10000 # 10 seconds
      monitoring_window_minutes  = 15
      auto_rollback_enabled      = true
      performance_baseline = {
        max_response_time_ms = 5000
        min_success_rate     = 0.95
        max_error_rate       = 0.05
      }
    }
    influxdb_config = {
      connection_timeout_ms = 30000
      query_timeout_ms      = 60000
      max_retries           = 3
      batch_size            = 1000
      enable_caching        = true
      cache_ttl_seconds     = 300
    }
    monitoring = {
      enable_detailed_metrics = true
      enable_x_ray_tracing    = true
      log_level               = "INFO"
      sample_rate             = 0.1
    }
  })
}

# Use timestamp and content hash for unique versions
resource "random_uuid" "traffic_switch_version" {
  keepers = {
    content   = local.traffic_switch_content
    timestamp = timestamp()
  }
}

# Application Settings for Traffic Switching
resource "aws_appconfig_hosted_configuration_version" "traffic_switch_settings" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.app_settings.configuration_profile_id
  description              = "Traffic switch ${substr(random_uuid.traffic_switch_version.result, 0, 8)}"
  content_type             = "application/json"
  content                  = local.traffic_switch_content

  lifecycle {
    create_before_destroy = true
  }
}

# Deployment for Development Environment
resource "aws_appconfig_deployment" "development_traffic_switch" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  configuration_version    = aws_appconfig_hosted_configuration_version.influxdb_migration_flags.version_number
  deployment_strategy_id   = aws_appconfig_deployment_strategy.canary_10_percent.id
  description              = "Deploy InfluxDB migration flags to development"
  environment_id           = aws_appconfig_environment.development.environment_id

  tags = var.tags
}

# CloudWatch Alarms for Traffic Switching Monitoring
resource "aws_cloudwatch_metric_alarm" "influxdb_migration_error_rate" {
  alarm_name          = "${var.project_name}-influxdb-migration-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorRate"
  namespace           = "ONS/TrafficSwitching"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.05" # 5% error rate
  alarm_description   = "High error rate during InfluxDB migration"
  treat_missing_data  = "notBreaching"

  alarm_actions = [
    "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${var.project_name}-alerts"
  ]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "influxdb_migration_latency" {
  alarm_name          = "${var.project_name}-influxdb-migration-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "ResponseTime"
  namespace           = "ONS/TrafficSwitching"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000" # 10 seconds
  alarm_description   = "High latency during InfluxDB migration"
  treat_missing_data  = "notBreaching"

  alarm_actions = [
    "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${var.project_name}-alerts"
  ]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "influxdb_connection_failures" {
  alarm_name          = "${var.project_name}-influxdb-connection-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ConnectionFailures"
  namespace           = "ONS/TrafficSwitching"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "High number of InfluxDB connection failures"
  treat_missing_data  = "notBreaching"

  alarm_actions = [
    "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${var.project_name}-alerts"
  ]

  tags = var.tags
}

# Data sources for current AWS account and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}