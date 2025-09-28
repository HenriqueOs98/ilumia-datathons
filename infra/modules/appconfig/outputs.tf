output "application_id" {
  description = "AppConfig application ID"
  value       = aws_appconfig_application.main.id
}

output "feature_flags_profile_id" {
  description = "Feature flags configuration profile ID"
  value       = aws_appconfig_configuration_profile.feature_flags.configuration_profile_id
}

output "app_settings_profile_id" {
  description = "Application settings configuration profile ID"
  value       = aws_appconfig_configuration_profile.app_settings.configuration_profile_id
}

output "development_environment_id" {
  description = "Development environment ID"
  value       = aws_appconfig_environment.development.environment_id
}

output "production_environment_id" {
  description = "Production environment ID"
  value       = aws_appconfig_environment.production.environment_id
}

output "canary_deployment_strategy_id" {
  description = "Canary deployment strategy ID"
  value       = aws_appconfig_deployment_strategy.canary_10_percent.id
}

output "service_role_arn" {
  description = "AppConfig service role ARN"
  value       = aws_iam_role.appconfig_service_role.arn
}