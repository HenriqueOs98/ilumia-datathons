output "codedeploy_application_name" {
  description = "Name of the CodeDeploy application"
  value       = aws_codedeploy_application.lambda_app.name
}

output "codedeploy_service_role_arn" {
  description = "ARN of the CodeDeploy service role"
  value       = aws_iam_role.codedeploy_service_role.arn
}

output "deployment_groups" {
  description = "Map of deployment group names"
  value = {
    for k, v in aws_codedeploy_deployment_group.lambda_deployment_group : k => v.deployment_group_name
  }
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for deployment alerts"
  value       = aws_sns_topic.deployment_alerts.arn
}

output "cloudwatch_alarms" {
  description = "Map of CloudWatch alarm names"
  value = {
    error_rate_alarms = {
      for k, v in aws_cloudwatch_metric_alarm.lambda_error_rate : k => v.alarm_name
    }
    duration_alarms = {
      for k, v in aws_cloudwatch_metric_alarm.lambda_duration : k => v.alarm_name
    }
  }
}