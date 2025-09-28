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

# InfluxDB Monitoring Outputs
output "influxdb_alerts_topic_arn" {
  description = "ARN of the InfluxDB alerts SNS topic"
  value       = aws_sns_topic.influxdb_alerts.arn
}

output "influxdb_dashboard_url" {
  description = "URL of the InfluxDB monitoring CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.influxdb_monitoring.dashboard_name}"
}

output "influxdb_composite_alarm_arn" {
  description = "ARN of the InfluxDB overall health composite alarm"
  value       = aws_cloudwatch_composite_alarm.influxdb_overall_health.arn
}

output "influxdb_log_group_arn" {
  description = "ARN of the InfluxDB monitor Lambda log group"
  value       = aws_cloudwatch_log_group.influxdb_monitor.arn
}

output "influxdb_connection_alarm_arn" {
  description = "ARN of the InfluxDB connection status alarm"
  value       = aws_cloudwatch_metric_alarm.influxdb_connection_status.arn
}

output "influxdb_performance_alarms" {
  description = "Map of InfluxDB performance alarm ARNs"
  value = {
    query_latency_simple  = aws_cloudwatch_metric_alarm.influxdb_query_latency_simple.arn
    query_latency_complex = aws_cloudwatch_metric_alarm.influxdb_query_latency_complex.arn
    write_latency         = aws_cloudwatch_metric_alarm.influxdb_write_latency.arn
    write_throughput_low  = aws_cloudwatch_metric_alarm.influxdb_write_throughput_low.arn
    query_errors          = aws_cloudwatch_metric_alarm.influxdb_query_errors.arn
    write_errors          = aws_cloudwatch_metric_alarm.influxdb_write_errors.arn
  }
}

output "influxdb_resource_alarms" {
  description = "Map of InfluxDB resource utilization alarm ARNs"
  value = {
    cpu_utilization    = aws_cloudwatch_metric_alarm.influxdb_cpu_utilization.arn
    memory_utilization = aws_cloudwatch_metric_alarm.influxdb_memory_utilization.arn
    disk_utilization   = aws_cloudwatch_metric_alarm.influxdb_disk_utilization.arn
    active_connections = aws_cloudwatch_metric_alarm.influxdb_active_connections.arn
  }
}

output "influxdb_cost_alarms" {
  description = "Map of InfluxDB cost monitoring alarm ARNs"
  value = {
    daily_cost_high  = aws_cloudwatch_metric_alarm.influxdb_daily_cost_high.arn
    storage_growth   = aws_cloudwatch_metric_alarm.influxdb_storage_growth.arn
  }
}