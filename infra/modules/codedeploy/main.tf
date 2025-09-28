# CodeDeploy Application and Deployment Groups for Lambda Blue-Green Deployments

resource "aws_codedeploy_application" "lambda_app" {
  compute_platform = "Lambda"
  name             = "${var.project_name}-lambda-app"

  tags = var.tags
}

# CodeDeploy Service Role
resource "aws_iam_role" "codedeploy_service_role" {
  name = "${var.project_name}-codedeploy-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "codedeploy.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "codedeploy_service_role_policy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSCodeDeployRoleForLambda"
  role       = aws_iam_role.codedeploy_service_role.name
}

# CloudWatch Alarms for automatic rollback triggers
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  for_each = var.lambda_functions

  alarm_name          = "${each.key}-error-rate-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = var.error_rate_threshold
  alarm_description   = "This metric monitors lambda error rate for ${each.key}"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    FunctionName = each.value.function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = var.lambda_functions

  alarm_name          = "${each.key}-duration-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Average"
  threshold           = var.duration_threshold
  alarm_description   = "This metric monitors lambda duration for ${each.key}"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    FunctionName = each.value.function_name
  }

  tags = var.tags
}

# SNS Topic for deployment alerts
resource "aws_sns_topic" "deployment_alerts" {
  name = "${var.project_name}-deployment-alerts"
  tags = var.tags
}

# CodeDeploy Deployment Groups for each Lambda function
resource "aws_codedeploy_deployment_group" "lambda_deployment_group" {
  for_each = var.lambda_functions

  app_name               = aws_codedeploy_application.lambda_app.name
  deployment_group_name  = "${each.key}-deployment-group"
  service_role_arn      = aws_iam_role.codedeploy_service_role.arn

  deployment_config_name = var.deployment_config_name

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }

  alarm_configuration {
    enabled = true
    alarms  = [
      aws_cloudwatch_metric_alarm.lambda_error_rate[each.key].alarm_name,
      aws_cloudwatch_metric_alarm.lambda_duration[each.key].alarm_name
    ]
  }

  blue_green_deployment_config {
    deployment_ready_option {
      action_on_timeout = "CONTINUE_DEPLOYMENT"
    }

    green_fleet_provisioning_option {
      action = "COPY_AUTO_SCALING_GROUP"
    }

    terminate_blue_instances_on_deployment_success {
      action                         = "TERMINATE"
      termination_wait_time_in_minutes = 5
    }
  }

  tags = var.tags
}