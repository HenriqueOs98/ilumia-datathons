# AWS AppConfig for Feature Flags and Configuration Management

resource "aws_appconfig_application" "main" {
  name        = "${var.project_name}-app"
  description = "Application configuration for ${var.project_name}"

  tags = var.tags
}

# Configuration Profile for Feature Flags
resource "aws_appconfig_configuration_profile" "feature_flags" {
  application_id = aws_appconfig_application.main.id
  name           = "feature-flags"
  description    = "Feature flags configuration"
  location_uri   = "hosted"
  type           = "AWS.AppConfig.FeatureFlags"

  tags = var.tags
}

# Configuration Profile for Application Settings
resource "aws_appconfig_configuration_profile" "app_settings" {
  application_id = aws_appconfig_application.main.id
  name           = "app-settings"
  description    = "Application settings configuration"
  location_uri   = "hosted"
  type           = "AWS.Freeform"

  validator {
    content = jsonencode({
      "$schema" = "http://json-schema.org/draft-07/schema#"
      type      = "object"
      properties = {
        deployment = {
          type = "object"
          properties = {
            canary_percentage = {
              type    = "number"
              minimum = 0
              maximum = 100
            }
            rollback_threshold = {
              type    = "number"
              minimum = 0
              maximum = 100
            }
          }
        }
      }
    })
    type = "JSON_SCHEMA"
  }

  tags = var.tags
}

# Environment for Development
resource "aws_appconfig_environment" "development" {
  name           = "development"
  description    = "Development environment"
  application_id = aws_appconfig_application.main.id

  monitor {
    alarm_arn      = var.development_alarm_arn
    alarm_role_arn = aws_iam_role.appconfig_service_role.arn
  }

  tags = var.tags
}

# Environment for Production
resource "aws_appconfig_environment" "production" {
  name           = "production"
  description    = "Production environment"
  application_id = aws_appconfig_application.main.id

  monitor {
    alarm_arn      = var.production_alarm_arn
    alarm_role_arn = aws_iam_role.appconfig_service_role.arn
  }

  tags = var.tags
}

# Deployment Strategy for Canary Releases
resource "aws_appconfig_deployment_strategy" "canary_10_percent" {
  name                           = "canary-10-percent"
  description                    = "Canary deployment with 10% traffic"
  deployment_duration_in_minutes = 10
  final_bake_time_in_minutes     = 5
  growth_factor                  = 10
  growth_type                    = "LINEAR"
  replicate_to                   = "NONE"

  tags = var.tags
}

# IAM Role for AppConfig Service
resource "aws_iam_role" "appconfig_service_role" {
  name = "${var.project_name}-appconfig-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "appconfig.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "appconfig_cloudwatch_policy" {
  name = "${var.project_name}-appconfig-cloudwatch-policy"
  role = aws_iam_role.appconfig_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms"
        ]
        Resource = "*"
      }
    ]
  })
}

# Initial Feature Flags Configuration
resource "aws_appconfig_hosted_configuration_version" "feature_flags_initial" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
  description              = "Initial feature flags configuration"
  content_type             = "application/json"

  content = jsonencode({
    flags = {
      enable_new_api_endpoint = {
        name    = "enable_new_api_endpoint"
        enabled = false
        variants = {
          on = {
            name  = "on"
            value = true
          }
          off = {
            name  = "off"
            value = false
          }
        }
      }
      enable_enhanced_processing = {
        name    = "enable_enhanced_processing"
        enabled = false
        variants = {
          on = {
            name  = "on"
            value = true
          }
          off = {
            name  = "off"
            value = false
          }
        }
      }
      enable_advanced_monitoring = {
        name    = "enable_advanced_monitoring"
        enabled = true
        variants = {
          on = {
            name  = "on"
            value = true
          }
          off = {
            name  = "off"
            value = false
          }
        }
      }
    }
    values = {
      enable_new_api_endpoint = {
        enabled = false
      }
      enable_enhanced_processing = {
        enabled = false
      }
      enable_advanced_monitoring = {
        enabled = true
      }
    }
    version = "1"
  })
}

# Initial Application Settings Configuration
resource "aws_appconfig_hosted_configuration_version" "app_settings_initial" {
  application_id           = aws_appconfig_application.main.id
  configuration_profile_id = aws_appconfig_configuration_profile.app_settings.configuration_profile_id
  description              = "Initial application settings"
  content_type             = "application/json"

  content = jsonencode({
    deployment = {
      canary_percentage  = 10
      rollback_threshold = 5
    }
    processing = {
      batch_size      = 100
      timeout_seconds = 300
    }
    monitoring = {
      log_level       = "INFO"
      metrics_enabled = true
    }
  })
}