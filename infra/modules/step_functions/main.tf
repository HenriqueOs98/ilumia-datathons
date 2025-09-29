# Step Functions State Machine for ONS Data Processing Pipeline

# IAM Role for Step Functions
resource "aws_iam_role" "step_functions_role" {
  name = "${var.project_name}-${var.environment}-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for Step Functions to invoke Lambda functions and Batch jobs
resource "aws_iam_role_policy" "step_functions_policy" {
  name = "${var.project_name}-${var.environment}-step-functions-policy"
  role = aws_iam_role.step_functions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          var.lambda_router_arn,
          var.lambda_processor_arn,
          var.lambda_timestream_loader_arn,
          var.lambda_knowledge_base_updater_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "batch:SubmitJob",
          "batch:DescribeJobs",
          "batch:TerminateJob"
        ]
        Resource = [
          var.batch_job_definition_arn,
          var.batch_job_queue_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          aws_sns_topic.processing_dlq.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Resource" : "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "events:PutRule",
          "events:PutTargets",
          "events:DeleteRule",
          "events:DescribeRule"
        ],
        Resource = [
          "arn:aws:events:*:*:rule/StepFunctionsGetEventsForBatchJobsRule",
          "arn:aws:events:*:*:rule/StepFunctionsGetEventsForECSTaskRule",
          "arn:aws:events:*:*:rule/StepFunctionsGetEventsForStepFunctionsExecutionRule"
        ]
      }
    ]
  })
}

# SNS Topic for Dead Letter Queue
resource "aws_sns_topic" "processing_dlq" {
  name = "${var.project_name}-${var.environment}-processing-dlq"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions_logs" {
  name              = "/aws/stepfunctions/${var.project_name}-${var.environment}-data-processing"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "data_processing_pipeline" {
  name     = "${var.project_name}-${var.environment}-data-processing"
  role_arn = aws_iam_role.step_functions_role.arn

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions_logs.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  definition = jsonencode({
    Comment = "ONS Data Processing Pipeline with routing, processing, and error handling"
    StartAt = "RouteFile"
    States = {
      # Route file based on type and size
      RouteFile = {
        Type     = "Task"
        Resource = var.lambda_router_arn
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "NotifyFailure"
            ResultPath  = "$.error"
          }
        ]
        Next = "ProcessingChoice"
      }

      # Choice state to determine processing path
      ProcessingChoice = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.processingType"
            StringEquals = "lambda"
            Next         = "ProcessStructuredData"
          },
          {
            Variable     = "$.processingType"
            StringEquals = "batch"
            Next         = "ProcessUnstructuredData"
          }
        ]
        Default = "NotifyFailure"
      }

      # Process structured data (CSV/XLSX) via Lambda
      ProcessStructuredData = {
        Type     = "Task"
        Resource = var.lambda_processor_arn
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2.0
          },
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 5
            MaxAttempts     = 2
            BackoffRate     = 3.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "NotifyFailure"
            ResultPath  = "$.error"
          }
        ]
        Next = "LoadToTimestream"
      }

      # Process unstructured data (PDF) via AWS Batch
      ProcessUnstructuredData = {
        Type     = "Task"
        Resource = "arn:aws:states:::batch:submitJob.sync"
        Parameters = {
          JobDefinition = var.batch_job_definition_arn
          JobName       = "${var.project_name}-pdf-processing"
          JobQueue      = var.batch_job_queue_arn
          Parameters = {
            "inputFile.$"  = "$.inputFile"
            "outputPath.$" = "$.outputPath"
          }
        }
        Retry = [
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 30
            MaxAttempts     = 2
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "NotifyFailure"
            ResultPath  = "$.error"
          }
        ]
        Next = "LoadToTimestream"
      }

      # Load processed data to Timestream
      LoadToTimestream = {
        Type     = "Task"
        Resource = var.lambda_timestream_loader_arn
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "NotifyFailure"
            ResultPath  = "$.error"
          }
        ]
        Next = "UpdateKnowledgeBase"
      }

      # Update Knowledge Base for RAG
      UpdateKnowledgeBase = {
        Type     = "Task"
        Resource = var.lambda_knowledge_base_updater_arn
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "NotifyFailure"
            ResultPath  = "$.error"
          }
        ]
        Next = "ProcessingComplete"
      }

      # Success state
      ProcessingComplete = {
        Type    = "Succeed"
        Comment = "Data processing pipeline completed successfully"
      }

      # Failure notification
      NotifyFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.processing_dlq.arn
          Message = {
            "executionArn.$" = "$$.Execution.Name"
            "stateMachine.$" = "$$.StateMachine.Name"
            "error.$"        = "$.error"
            "input.$"        = "$$.Execution.Input"
            "timestamp.$"    = "$$.State.EnteredTime"
          }
          Subject = "ONS Data Processing Pipeline Failure"
        }
        End = true
      }
    }
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}