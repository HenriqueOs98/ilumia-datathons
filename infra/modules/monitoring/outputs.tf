output "critical_alerts_topic_arn" {
  description = "ARN of the critical alerts SNS topic"
  value       = aws_sns_topic.critical_alerts.arn
}

output "warning_alerts_topic_arn" {
  description = "ARN of the warning alerts SNS topic"
  value       = aws_sns_topic.warning_alerts.arn
}

output "dashboard_url" {
  description = "URL of the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.ons_platform.dashboard_name}"
}

output "log_groups" {
  description = "Map of log group names and ARNs"
  value = {
    lambda_router     = aws_cloudwatch_log_group.lambda_router.arn
    lambda_processor  = aws_cloudwatch_log_group.lambda_processor.arn
    lambda_api        = aws_cloudwatch_log_group.lambda_api.arn
    lambda_timestream = aws_cloudwatch_log_group.lambda_timestream.arn
    step_functions    = aws_cloudwatch_log_group.step_functions.arn
    api_gateway       = aws_cloudwatch_log_group.api_gateway.arn
  }
}

output "budget_name" {
  description = "Name of the AWS Budget for cost monitoring"
  value       = length(aws_budgets_budget.ons_platform_budget) > 0 ? aws_budgets_budget.ons_platform_budget[0].name : null
}

# Cost anomaly detector output removed as the resource is not available in all regions

output "cost_optimizer_function_name" {
  description = "Name of the cost optimizer Lambda function"
  value       = aws_lambda_function.cost_optimizer.function_name
}

output "cost_optimization_dashboard_url" {
  description = "URL of the cost optimization CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.cost_optimization.dashboard_name}"
}

output "sns_topic_arn" {
  description = "ARN of the primary SNS topic for notifications"
  value       = aws_sns_topic.critical_alerts.arn
}

output "development_alarm_arn" {
  description = "ARN of the development environment alarm"
  value       = aws_cloudwatch_metric_alarm.lambda_router_errors.arn
}

output "production_alarm_arn" {
  description = "ARN of the production environment alarm"
  value       = aws_cloudwatch_metric_alarm.api_gateway_5xx_errors.arn
}