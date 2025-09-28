# Placeholder for Lambda functions module
# This will be implemented in subsequent tasks

# Lambda execution role
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-execution-role"

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
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_execution_role.name
}

# Timestream Loader Lambda Function
resource "aws_lambda_function" "timestream_loader" {
  filename      = data.archive_file.timestream_loader.output_path
  function_name = "${var.project_name}-${var.environment}-timestream-loader"
  role          = var.timestream_lambda_role_arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 900 # 15 minutes
  memory_size   = 1024

  source_code_hash = data.archive_file.timestream_loader.output_base64sha256

  environment {
    variables = {
      TIMESTREAM_DATABASE_NAME = var.timestream_database_name
      GENERATION_TABLE_NAME    = var.generation_table_name
      CONSUMPTION_TABLE_NAME   = var.consumption_table_name
      TRANSMISSION_TABLE_NAME  = var.transmission_table_name
      MAX_BATCH_SIZE           = "100"
      MAX_RETRIES              = "3"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.timestream_loader
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-loader"
    Environment = var.environment
    Purpose     = "Load processed data into Timestream"
  }
}

# Package Timestream Loader Lambda
data "archive_file" "timestream_loader" {
  type        = "zip"
  source_dir  = "${path.root}/../src/timestream_loader"
  output_path = "${path.module}/timestream_loader.zip"
  excludes    = ["__pycache__", "*.pyc", "test_*.py", "validate_*.py"]
}

# CloudWatch Log Group for Timestream Loader
resource "aws_cloudwatch_log_group" "timestream_loader" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-timestream-loader"
  retention_in_days = var.log_retention_days

  lifecycle {
    ignore_changes = [name]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-loader-logs"
    Environment = var.environment
  }
}

# Lambda Layer for common dependencies
resource "aws_lambda_layer_version" "pandas_layer" {
  filename         = data.archive_file.pandas_layer.output_path
  layer_name       = "${var.project_name}-${var.environment}-pandas-layer"
  source_code_hash = data.archive_file.pandas_layer.output_base64sha256

  compatible_runtimes = ["python3.11"]
  description         = "Pandas and PyArrow layer for data processing"

  depends_on = [null_resource.build_pandas_layer]
}

# Build pandas layer
resource "null_resource" "build_pandas_layer" {
  triggers = {
    requirements = filemd5("${path.root}/../src/timestream_loader/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${path.module}/layer/python
      # Use specific versions that are compatible
      pip install boto3==1.34.0 pandas==2.0.3 pyarrow==12.0.1 -t ${path.module}/layer/python/ --no-deps --platform manylinux2014_x86_64 --only-binary=:all:
      # Install dependencies separately
      pip install numpy==1.24.4 python-dateutil==2.8.2 pytz==2023.3 six==1.16.0 -t ${path.module}/layer/python/ --no-deps --platform manylinux2014_x86_64 --only-binary=:all:
    EOT
  }
}

data "archive_file" "pandas_layer" {
  type        = "zip"
  source_dir  = "${path.module}/layer"
  output_path = "${path.module}/pandas_layer.zip"

  depends_on = [null_resource.build_pandas_layer]
}

# Layer is attached directly to the timestream_loader function above

# RAG Query Processor Lambda Function
resource "aws_lambda_function" "rag_query_processor" {
  filename      = data.archive_file.rag_query_processor.output_path
  function_name = "${var.project_name}-${var.environment}-rag-query-processor"
  role          = aws_iam_role.rag_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300 # 5 minutes
  memory_size   = 1024

  source_code_hash = data.archive_file.rag_query_processor.output_base64sha256

  environment {
    variables = {
      KNOWLEDGE_BASE_ID    = var.knowledge_base_id
      MODEL_ARN            = var.bedrock_model_arn
      MAX_QUERY_LENGTH     = "1000"
      MAX_RESULTS          = "5"
      MIN_CONFIDENCE_SCORE = "0.7"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.rag_query_processor
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-query-processor"
    Environment = var.environment
    Purpose     = "Process RAG queries using Knowledge Base"
  }
}

# Package RAG Query Processor Lambda
data "archive_file" "rag_query_processor" {
  type        = "zip"
  source_dir  = "${path.root}/../src/rag_query_processor"
  output_path = "${path.module}/rag_query_processor.zip"
  excludes    = ["__pycache__", "*.pyc", "test_*.py", "validate_*.py", "README.md"]
}

# IAM role for RAG Query Processor
resource "aws_iam_role" "rag_lambda_role" {
  name = "${var.project_name}-${var.environment}-rag-lambda-role"

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
    Name = "${var.project_name}-${var.environment}-rag-lambda-role"
  }
}

# Basic execution policy for RAG Lambda
resource "aws_iam_role_policy_attachment" "rag_lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.rag_lambda_role.name
}

# Bedrock access policy for RAG Lambda
resource "aws_iam_role_policy" "rag_lambda_bedrock_policy" {
  name = "${var.project_name}-${var.environment}-rag-lambda-bedrock-policy"
  role = aws_iam_role.rag_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          var.bedrock_model_arn,
          "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = [
          "arn:aws:bedrock:*:*:knowledge-base/${var.knowledge_base_id}"
        ]
      }
    ]
  })
}

# CloudWatch metrics policy for RAG Lambda
resource "aws_iam_role_policy" "rag_lambda_cloudwatch_policy" {
  name = "${var.project_name}-${var.environment}-rag-lambda-cloudwatch-policy"
  role = aws_iam_role.rag_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "ONS/RAGProcessor"
          }
        }
      }
    ]
  })
}

# CloudWatch Log Group for RAG Query Processor
resource "aws_cloudwatch_log_group" "rag_query_processor" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-rag-query-processor"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-query-processor-logs"
    Environment = var.environment
  }
}

# CloudWatch Alarms for RAG Query Processor
resource "aws_cloudwatch_metric_alarm" "rag_processor_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-rag-processor-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors RAG processor errors"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.rag_query_processor.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-processor-errors"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "rag_processor_duration" {
  alarm_name          = "${var.project_name}-${var.environment}-rag-processor-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "30000" # 30 seconds
  alarm_description   = "This metric monitors RAG processor duration"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.rag_query_processor.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-processor-duration"
    Environment = var.environment
  }
}

# Custom CloudWatch Alarms for RAG-specific metrics
resource "aws_cloudwatch_metric_alarm" "rag_processor_query_failures" {
  alarm_name          = "${var.project_name}-${var.environment}-rag-query-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "QueryFailure"
  namespace           = "ONS/RAGProcessor"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors RAG query failures"
  alarm_actions       = [var.sns_topic_arn]

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-query-failures"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "rag_processor_high_latency" {
  alarm_name          = "${var.project_name}-${var.environment}-rag-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "ResponseTime"
  namespace           = "ONS/RAGProcessor"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000" # 10 seconds
  alarm_description   = "This metric monitors RAG response time"
  alarm_actions       = [var.sns_topic_arn]

  tags = {
    Name        = "${var.project_name}-${var.environment}-rag-high-latency"
    Environment = var.environment
  }
}

# CloudWatch Alarms for Timestream Loader
resource "aws_cloudwatch_metric_alarm" "timestream_loader_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-timestream-loader-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors timestream loader errors"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.timestream_loader.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-loader-errors"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "timestream_loader_duration" {
  alarm_name          = "${var.project_name}-${var.environment}-timestream-loader-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "600000" # 10 minutes
  alarm_description   = "This metric monitors timestream loader duration"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.timestream_loader.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-loader-duration"
    Environment = var.environment
  }
}