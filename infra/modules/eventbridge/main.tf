# EventBridge Integration for ONS Data Processing Pipeline

# EventBridge Rule for S3 Object Creation Events
resource "aws_cloudwatch_event_rule" "s3_object_created" {
  name        = "${var.project_name}-${var.environment}-s3-object-created"
  description = "Capture S3 object creation events for ONS data files"
  state       = "ENABLED"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.s3_raw_bucket]
      }
      object = {
        key = [
          {
            suffix = ".csv"
          },
          {
            suffix = ".xlsx"
          },
          {
            suffix = ".xls"
          },
          {
            suffix = ".pdf"
          }
        ]
      }
    }
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Role for EventBridge to invoke Step Functions
resource "aws_iam_role" "eventbridge_step_functions_role" {
  name = "${var.project_name}-${var.environment}-eventbridge-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for EventBridge to invoke Step Functions
resource "aws_iam_role_policy" "eventbridge_step_functions_policy" {
  name = "${var.project_name}-${var.environment}-eventbridge-stepfunctions-policy"
  role = aws_iam_role.eventbridge_step_functions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = [
          var.step_function_arn
        ]
      }
    ]
  })
}

# EventBridge Target - Step Functions State Machine
resource "aws_cloudwatch_event_target" "step_functions_target" {
  rule      = aws_cloudwatch_event_rule.s3_object_created.name
  target_id = "StepFunctionsTarget"
  arn       = var.step_function_arn
  role_arn  = aws_iam_role.eventbridge_step_functions_role.arn

  # Input transformation to format the event for Step Functions
  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
      size   = "$.detail.object.size"
      etag   = "$.detail.object.etag"
      time   = "$.time"
    }
    
    input_template = jsonencode({
      Records = [{
        eventSource = "aws:s3"
        eventName   = "ObjectCreated:Put"
        eventTime   = "<time>"
        s3 = {
          bucket = {
            name = "<bucket>"
          }
          object = {
            key  = "<key>"
            size = "<size>"
            eTag = "<etag>"
          }
        }
      }]
      eventBridgeSource = true
      processingTimestamp = "<time>"
    })
  }
}

# EventBridge Rule for Processing Completion Events (for chaining workflows)
resource "aws_cloudwatch_event_rule" "processing_completed" {
  name        = "${var.project_name}-${var.environment}-processing-completed"
  description = "Capture processing completion events for downstream workflows"
  state       = "ENABLED"

  event_pattern = jsonencode({
    source      = ["ons.data.platform"]
    detail-type = ["Data Processing Completed"]
    detail = {
      status = ["SUCCESS"]
    }
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# EventBridge Rule for Processing Failures (for alerting)
resource "aws_cloudwatch_event_rule" "processing_failed" {
  name        = "${var.project_name}-${var.environment}-processing-failed"
  description = "Capture processing failure events for alerting"
  state       = "ENABLED"

  event_pattern = jsonencode({
    source      = ["ons.data.platform"]
    detail-type = ["Data Processing Failed"]
    detail = {
      status = ["FAILED", "TIMEOUT", "ABORTED"]
    }
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# SNS Topic for Processing Alerts
resource "aws_sns_topic" "processing_alerts" {
  name = "${var.project_name}-${var.environment}-processing-alerts"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# EventBridge Target for Processing Failures - SNS Alert
resource "aws_cloudwatch_event_target" "processing_failure_alert" {
  rule      = aws_cloudwatch_event_rule.processing_failed.name
  target_id = "ProcessingFailureAlert"
  arn       = aws_sns_topic.processing_alerts.arn

  input_transformer {
    input_paths = {
      source     = "$.source"
      detailType = "$.detail-type"
      status     = "$.detail.status"
      error      = "$.detail.error"
      file       = "$.detail.inputFile"
      time       = "$.time"
    }
    
    input_template = jsonencode({
      alert_type    = "Processing Failure"
      timestamp     = "<time>"
      status        = "<status>"
      error_details = "<error>"
      failed_file   = "<file>"
      source        = "<source>"
      detail_type   = "<detailType>"
    })
  }
}

# IAM Role for EventBridge to publish to SNS
resource "aws_iam_role" "eventbridge_sns_role" {
  name = "${var.project_name}-${var.environment}-eventbridge-sns-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for EventBridge to publish to SNS
resource "aws_iam_role_policy" "eventbridge_sns_policy" {
  name = "${var.project_name}-${var.environment}-eventbridge-sns-policy"
  role = aws_iam_role.eventbridge_sns_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          aws_sns_topic.processing_alerts.arn
        ]
      }
    ]
  })
}

# CloudWatch Log Group for EventBridge
resource "aws_cloudwatch_log_group" "eventbridge_logs" {
  name              = "/aws/events/${var.project_name}-${var.environment}"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}