# CloudWatch Monitoring and Alerting Module
# This module creates comprehensive monitoring for the ONS Data Platform

# SNS Topics for different alert severities
resource "aws_sns_topic" "critical_alerts" {
  name = "${var.environment}-ons-critical-alerts"
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_sns_topic" "warning_alerts" {
  name = "${var.environment}-ons-warning-alerts"
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

# SNS Topic Subscriptions (email notifications)
resource "aws_sns_topic_subscription" "critical_email" {
  count     = length(var.critical_alert_emails)
  topic_arn = aws_sns_topic.critical_alerts.arn
  protocol  = "email"
  endpoint  = var.critical_alert_emails[count.index]
}

resource "aws_sns_topic_subscription" "warning_email" {
  count     = length(var.warning_alert_emails)
  topic_arn = aws_sns_topic.warning_alerts.arn
  protocol  = "email"
  endpoint  = var.warning_alert_emails[count.index]
}

# CloudWatch Log Groups with retention policies
resource "aws_cloudwatch_log_group" "lambda_router" {
  name              = "/aws/lambda/${var.environment}-ons-lambda-router"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "lambda-router"
  }
}

resource "aws_cloudwatch_log_group" "lambda_processor" {
  name              = "/aws/lambda/${var.environment}-ons-structured-processor"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "lambda-processor"
  }
}

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${var.environment}-ons-api-handler"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "lambda-api"
  }
}

resource "aws_cloudwatch_log_group" "lambda_timestream" {
  name              = "/aws/lambda/${var.environment}-ons-timestream-loader"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "lambda-timestream"
  }
}

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/stepfunctions/${var.environment}-ons-processing-workflow"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "step-functions"
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "API-Gateway-Execution-Logs_${var.api_gateway_id}/${var.environment}"
  retention_in_days = var.log_retention_days
  
  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "api-gateway"
  }
}

# Custom CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "ons_platform" {
  dashboard_name = "${var.environment}-ons-data-platform"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${var.environment}-ons-lambda-router"],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."],
            ["AWS/Lambda", "Duration", "FunctionName", "${var.environment}-ons-structured-processor"],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Functions Performance"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", "${var.environment}-ons-api"],
            [".", "Latency", ".", "."],
            [".", "4XXError", ".", "."],
            [".", "5XXError", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Gateway Performance"
          period  = 300
        }
      }
    ]
  })
}
# CloudWatc
h Alarms for Lambda Functions

# Lambda Router Function Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_router_errors" {
  alarm_name          = "${var.environment}-lambda-router-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors lambda router error rate"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    FunctionName = "${var.environment}-ons-lambda-router"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_router_duration" {
  alarm_name          = "${var.environment}-lambda-router-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "30000"  # 30 seconds
  alarm_description   = "This metric monitors lambda router duration"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    FunctionName = "${var.environment}-ons-lambda-router"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

# Lambda Processor Function Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_processor_errors" {
  alarm_name          = "${var.environment}-lambda-processor-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors lambda processor error rate"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    FunctionName = "${var.environment}-ons-structured-processor"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_processor_duration" {
  alarm_name          = "${var.environment}-lambda-processor-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "600000"  # 10 minutes
  alarm_description   = "This metric monitors lambda processor duration"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    FunctionName = "${var.environment}-ons-structured-processor"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

# API Gateway Alarms
resource "aws_cloudwatch_metric_alarm" "api_gateway_latency" {
  alarm_name          = "${var.environment}-api-gateway-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000"  # 10 seconds
  alarm_description   = "This metric monitors API Gateway latency"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    ApiName = "${var.environment}-ons-api"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_4xx_errors" {
  alarm_name          = "${var.environment}-api-gateway-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors API Gateway 4XX errors"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    ApiName = "${var.environment}-ons-api"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx_errors" {
  alarm_name          = "${var.environment}-api-gateway-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors API Gateway 5XX errors"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    ApiName = "${var.environment}-ons-api"
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

# Step Functions Alarms
resource "aws_cloudwatch_metric_alarm" "step_functions_failed_executions" {
  alarm_name          = "${var.environment}-step-functions-failed-executions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors Step Functions failed executions"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]

  dimensions = {
    StateMachineArn = var.step_functions_arn
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "step_functions_execution_time" {
  alarm_name          = "${var.environment}-step-functions-execution-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ExecutionTime"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Average"
  threshold           = "1800000"  # 30 minutes
  alarm_description   = "This metric monitors Step Functions execution time"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    StateMachineArn = var.step_functions_arn
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

# Custom Metrics for Business Logic Monitoring
resource "aws_cloudwatch_log_metric_filter" "processing_success_rate" {
  name           = "${var.environment}-processing-success-rate"
  log_group_name = aws_cloudwatch_log_group.lambda_processor.name
  pattern        = "[timestamp, request_id, level=\"INFO\", message=\"Processing completed successfully\"]"

  metric_transformation {
    name      = "ProcessingSuccessCount"
    namespace = "ONS/DataPlatform"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "processing_failure_rate" {
  name           = "${var.environment}-processing-failure-rate"
  log_group_name = aws_cloudwatch_log_group.lambda_processor.name
  pattern        = "[timestamp, request_id, level=\"ERROR\", message=\"Processing failed\"]"

  metric_transformation {
    name      = "ProcessingFailureCount"
    namespace = "ONS/DataPlatform"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "data_quality_issues" {
  name           = "${var.environment}-data-quality-issues"
  log_group_name = aws_cloudwatch_log_group.lambda_processor.name
  pattern        = "[timestamp, request_id, level=\"WARN\", message=\"Data quality issue detected\"]"

  metric_transformation {
    name      = "DataQualityIssueCount"
    namespace = "ONS/DataPlatform"
    value     = "1"
  }
}

# Business Logic Alarms
resource "aws_cloudwatch_metric_alarm" "processing_failure_rate_alarm" {
  alarm_name          = "${var.environment}-processing-failure-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ProcessingFailureCount"
  namespace           = "ONS/DataPlatform"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors data processing failure rate"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  ok_actions          = [aws_sns_topic.critical_alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}

resource "aws_cloudwatch_metric_alarm" "data_quality_issues_alarm" {
  alarm_name          = "${var.environment}-data-quality-issues"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DataQualityIssueCount"
  namespace           = "ONS/DataPlatform"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors data quality issues"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "monitoring"
  }
}
# Cost Mo
nitoring and Optimization

# Budget for the ONS Data Platform
resource "aws_budgets_budget" "ons_platform_budget" {
  name         = "${var.environment}-ons-data-platform-budget"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  time_period_start = formatdate("YYYY-MM-01_00:00", timestamp())

  cost_filters = {
    Tag = [
      "Project:ons-data-platform"
    ]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = var.cost_alert_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.cost_alert_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 120
    threshold_type            = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.critical_alert_emails
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-monitoring"
  }
}

# Cost Anomaly Detection
resource "aws_ce_anomaly_detector" "ons_platform_anomaly" {
  name         = "${var.environment}-ons-platform-cost-anomaly"
  monitor_type = "DIMENSIONAL"

  specification = jsonencode({
    Dimension = "SERVICE"
    MatchOptions = ["EQUALS"]
    Values = [
      "Amazon Simple Storage Service",
      "AWS Lambda",
      "Amazon API Gateway",
      "AWS Step Functions",
      "Amazon Timestream",
      "Amazon Bedrock",
      "Amazon OpenSearch Service"
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-monitoring"
  }
}

# Cost Anomaly Subscription
resource "aws_ce_anomaly_subscription" "ons_platform_anomaly_subscription" {
  name      = "${var.environment}-ons-platform-anomaly-subscription"
  frequency = "DAILY"
  
  monitor_arn_list = [
    aws_ce_anomaly_detector.ons_platform_anomaly.arn
  ]
  
  subscriber {
    type    = "EMAIL"
    address = var.cost_alert_emails[0]
  }

  threshold_expression {
    and {
      dimension {
        key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
        values        = [tostring(var.cost_anomaly_threshold)]
        match_options = ["GREATER_THAN_OR_EQUAL"]
      }
    }
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-monitoring"
  }
}

# CloudWatch Metrics for Cost Optimization
resource "aws_cloudwatch_log_metric_filter" "lambda_cold_starts" {
  name           = "${var.environment}-lambda-cold-starts"
  log_group_name = aws_cloudwatch_log_group.lambda_processor.name
  pattern        = "[timestamp, request_id, level, message=\"INIT_START\"]"

  metric_transformation {
    name      = "LambdaColdStarts"
    namespace = "ONS/CostOptimization"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "lambda_memory_utilization" {
  name           = "${var.environment}-lambda-memory-utilization"
  log_group_name = aws_cloudwatch_log_group.lambda_processor.name
  pattern        = "[timestamp, request_id, level=\"REPORT\", ..., memory_used=\"Used:\", memory_mb, memory_unit=\"MB\"]"

  metric_transformation {
    name      = "LambdaMemoryUtilization"
    namespace = "ONS/CostOptimization"
    value     = "$memory_mb"
  }
}

# Cost Optimization Alarms
resource "aws_cloudwatch_metric_alarm" "high_lambda_cold_starts" {
  alarm_name          = "${var.environment}-high-lambda-cold-starts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "LambdaColdStarts"
  namespace           = "ONS/CostOptimization"
  period              = "300"
  statistic           = "Sum"
  threshold           = "20"
  alarm_description   = "High number of Lambda cold starts indicating potential cost optimization opportunity"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-optimization"
  }
}

# Resource Utilization Monitoring Dashboard
resource "aws_cloudwatch_dashboard" "cost_optimization" {
  dashboard_name = "${var.environment}-ons-cost-optimization"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["ONS/CostOptimization", "LambdaColdStarts"],
            [".", "LambdaMemoryUtilization"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Cost Optimization Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", "${var.environment}-ons-raw-data", "StorageType", "StandardStorage"],
            [".", ".", ".", "${var.environment}-ons-processed-data", ".", "."],
            ["AWS/S3", "NumberOfObjects", "BucketName", "${var.environment}-ons-raw-data", "StorageType", "AllStorageTypes"],
            [".", ".", ".", "${var.environment}-ons-processed-data", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "S3 Storage Utilization"
          period  = 86400
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Timestream", "UserRecordsIngested", "DatabaseName", "${var.environment}-ons-energy-data"],
            [".", "SystemRecordsIngested", ".", "."],
            [".", "MagneticStoreRejectedRecordCount", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Timestream Utilization"
          period  = 300
        }
      }
    ]
  })
}

# Lambda Function for Cost Optimization Recommendations
resource "aws_lambda_function" "cost_optimizer" {
  filename         = "cost_optimizer.zip"
  function_name    = "${var.environment}-ons-cost-optimizer"
  role            = aws_iam_role.cost_optimizer_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.11"
  timeout         = 300

  environment {
    variables = {
      ENVIRONMENT = var.environment
      SNS_TOPIC_ARN = aws_sns_topic.warning_alerts.arn
    }
  }

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-optimization"
  }
}

# IAM Role for Cost Optimizer Lambda
resource "aws_iam_role" "cost_optimizer_role" {
  name = "${var.environment}-ons-cost-optimizer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-optimization"
  }
}

# IAM Policy for Cost Optimizer Lambda
resource "aws_iam_role_policy" "cost_optimizer_policy" {
  name = "${var.environment}-ons-cost-optimizer-policy"
  role = aws_iam_role.cost_optimizer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "ce:GetCostAndUsage",
          "ce:GetUsageReport",
          "lambda:GetFunction",
          "lambda:ListFunctions",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "timestream:DescribeDatabase",
          "timestream:DescribeTable",
          "sns:Publish"
        ]
        Resource = "*"
      }
    ]
  })
}

# EventBridge Rule to trigger cost optimization analysis weekly
resource "aws_cloudwatch_event_rule" "cost_optimization_schedule" {
  name                = "${var.environment}-cost-optimization-schedule"
  description         = "Trigger cost optimization analysis weekly"
  schedule_expression = "rate(7 days)"

  tags = {
    Environment = var.environment
    Project     = "ons-data-platform"
    Component   = "cost-optimization"
  }
}

resource "aws_cloudwatch_event_target" "cost_optimizer_target" {
  rule      = aws_cloudwatch_event_rule.cost_optimization_schedule.name
  target_id = "CostOptimizerTarget"
  arn       = aws_lambda_function.cost_optimizer.arn
}

resource "aws_lambda_permission" "allow_eventbridge_cost_optimizer" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_optimizer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cost_optimization_schedule.arn
}