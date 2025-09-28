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

# Shared Utils Lambda Layer
resource "aws_lambda_layer_version" "shared_utils_layer" {
  filename         = data.archive_file.shared_utils_layer.output_path
  layer_name       = "${var.project_name}-${var.environment}-shared-utils"
  source_code_hash = data.archive_file.shared_utils_layer.output_base64sha256

  compatible_runtimes = ["python3.11"]
  description         = "Shared utilities for InfluxDB integration and data processing"

  depends_on = [data.archive_file.shared_utils_layer]
}

# Package Shared Utils Layer
data "archive_file" "shared_utils_layer" {
  type        = "zip"
  output_path = "${path.module}/shared_utils_layer.zip"

  source {
    content  = templatefile("${path.root}/../src/shared_utils/requirements.txt", {})
    filename = "requirements.txt"
  }

  source {
    content  = file("${path.root}/../src/shared_utils/__init__.py")
    filename = "python/shared_utils/__init__.py"
  }

  source {
    content  = file("${path.root}/../src/shared_utils/influxdb_client.py")
    filename = "python/shared_utils/influxdb_client.py"
  }

  source {
    content  = file("${path.root}/../src/shared_utils/data_conversion.py")
    filename = "python/shared_utils/data_conversion.py"
  }

  source {
    content  = file("${path.root}/../src/shared_utils/logging_config.py")
    filename = "python/shared_utils/logging_config.py"
  }

  source {
    content  = file("${path.root}/../src/shared_utils/data_validation.py")
    filename = "python/shared_utils/data_validation.py"
  }
}

# InfluxDB Loader Lambda Function
resource "aws_lambda_function" "influxdb_loader" {
  filename      = data.archive_file.influxdb_loader.output_path
  function_name = "${var.project_name}-${var.environment}-influxdb-loader"
  role          = aws_iam_role.influxdb_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 900  # 15 minutes for large data processing
  memory_size   = 2048 # Increased memory for data processing

  source_code_hash = data.archive_file.influxdb_loader.output_base64sha256

  layers = [aws_lambda_layer_version.shared_utils_layer.arn]

  environment {
    variables = {
      INFLUXDB_URL               = var.influxdb_url
      INFLUXDB_ORG               = var.influxdb_org
      INFLUXDB_BUCKET            = var.influxdb_bucket
      INFLUXDB_TOKEN_SECRET_NAME = var.influxdb_token_secret_name
      MAX_BATCH_SIZE             = "1000"
      MAX_RETRIES                = "3"
      ENABLE_VALIDATION          = "true"
      DROP_INVALID_RECORDS       = "true"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.influxdb_lambda_sg.id]
  }

  depends_on = [
    aws_cloudwatch_log_group.influxdb_loader
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-loader"
    Environment = var.environment
    Purpose     = "Load processed data into InfluxDB"
  }
}

# Package InfluxDB Loader Lambda
data "archive_file" "influxdb_loader" {
  type        = "zip"
  source_dir  = "${path.root}/../src/influxdb_loader"
  output_path = "${path.module}/influxdb_loader.zip"
  excludes    = ["__pycache__", "*.pyc", "test_*.py", "validate_*.py", "README.md"]
}

# Security Group for InfluxDB Lambda
resource "aws_security_group" "influxdb_lambda_sg" {
  name_prefix = "${var.project_name}-${var.environment}-influxdb-lambda-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound for AWS services"
  }

  egress {
    from_port   = 8086
    to_port     = 8086
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "InfluxDB connection"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-lambda-sg"
    Environment = var.environment
  }
}

# IAM role for InfluxDB Loader
resource "aws_iam_role" "influxdb_lambda_role" {
  name = "${var.project_name}-${var.environment}-influxdb-lambda-role"

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
    Name = "${var.project_name}-${var.environment}-influxdb-lambda-role"
  }
}

# Basic execution policy for InfluxDB Lambda
resource "aws_iam_role_policy_attachment" "influxdb_lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.influxdb_lambda_role.name
}

# VPC execution policy for InfluxDB Lambda
resource "aws_iam_role_policy_attachment" "influxdb_lambda_vpc_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  role       = aws_iam_role.influxdb_lambda_role.name
}

# S3 access policy for InfluxDB Lambda
resource "aws_iam_role_policy" "influxdb_lambda_s3_policy" {
  name = "${var.project_name}-${var.environment}-influxdb-lambda-s3-policy"
  role = aws_iam_role.influxdb_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = [
          "${var.s3_processed_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_processed_bucket_arn
        ]
      }
    ]
  })
}

# Secrets Manager access policy for InfluxDB Lambda
resource "aws_iam_role_policy" "influxdb_lambda_secrets_policy" {
  name = "${var.project_name}-${var.environment}-influxdb-lambda-secrets-policy"
  role = aws_iam_role.influxdb_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:${var.influxdb_token_secret_name}*"
        ]
      }
    ]
  })
}

# CloudWatch metrics policy for InfluxDB Lambda
resource "aws_iam_role_policy" "influxdb_lambda_cloudwatch_policy" {
  name = "${var.project_name}-${var.environment}-influxdb-lambda-cloudwatch-policy"
  role = aws_iam_role.influxdb_lambda_role.id

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
            "cloudwatch:namespace" = ["ONS/InfluxDB", "ONS/TrafficSwitching", "ONS/DataLoader"]
          }
        }
      }
    ]
  })
}

# AppConfig access policy for InfluxDB Lambda
resource "aws_iam_role_policy" "influxdb_lambda_appconfig_policy" {
  name = "${var.project_name}-${var.environment}-influxdb-lambda-appconfig-policy"
  role = aws_iam_role.influxdb_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "appconfig:StartConfigurationSession",
          "appconfig:GetConfiguration"
        ]
        Resource = [
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/environment/*",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/configurationprofile/*"
        ]
      }
    ]
  })
}

# S3 Event Notification for InfluxDB Loader
resource "aws_s3_bucket_notification" "influxdb_loader_trigger" {
  bucket = var.s3_processed_bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.influxdb_loader.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "processed/"
    filter_suffix       = ".parquet"
  }

  depends_on = [aws_lambda_permission.influxdb_loader_s3_invoke]
}

# Lambda permission for S3 to invoke InfluxDB loader
resource "aws_lambda_permission" "influxdb_loader_s3_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.influxdb_loader.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.s3_processed_bucket_arn
}

# CloudWatch Log Group for InfluxDB Loader
resource "aws_cloudwatch_log_group" "influxdb_loader" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-influxdb-loader"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-loader-logs"
    Environment = var.environment
  }
}

# CloudWatch Alarms for InfluxDB Loader
resource "aws_cloudwatch_metric_alarm" "influxdb_loader_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-loader-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors InfluxDB loader errors"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.influxdb_loader.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-loader-errors"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "influxdb_loader_duration" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-loader-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "600000" # 10 minutes
  alarm_description   = "This metric monitors InfluxDB loader duration"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.influxdb_loader.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-loader-duration"
    Environment = var.environment
  }
}

# Custom CloudWatch Alarms for InfluxDB-specific metrics
resource "aws_cloudwatch_metric_alarm" "influxdb_loader_connection_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-connection-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ProcessingErrors"
  namespace           = "ONS/InfluxDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors InfluxDB connection errors"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    ErrorType = "connection_error"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-connection-errors"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "influxdb_loader_low_success_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-low-success-rate"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "SuccessRate"
  namespace           = "ONS/InfluxDB"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.95" # 95% success rate
  alarm_description   = "This metric monitors InfluxDB loader success rate"
  alarm_actions       = [var.sns_topic_arn]

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-low-success-rate"
    Environment = var.environment
  }
}

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
      KNOWLEDGE_BASE_ID           = var.knowledge_base_id
      MODEL_ARN                   = var.bedrock_model_arn
      MAX_QUERY_LENGTH            = "1000"
      MAX_RESULTS                 = "5"
      MIN_CONFIDENCE_SCORE        = "0.7"
      APPCONFIG_APPLICATION       = "${var.project_name}-${var.environment}-app"
      ENVIRONMENT                 = var.environment
      TIMESERIES_LAMBDA_NAME      = "${var.project_name}-${var.environment}-timeseries-query-processor"
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
            "cloudwatch:namespace" = ["ONS/RAGProcessor", "ONS/TrafficSwitching"]
          }
        }
      }
    ]
  })
}

# AppConfig access policy for RAG Lambda
resource "aws_iam_role_policy" "rag_lambda_appconfig_policy" {
  name = "${var.project_name}-${var.environment}-rag-lambda-appconfig-policy"
  role = aws_iam_role.rag_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "appconfig:StartConfigurationSession",
          "appconfig:GetConfiguration"
        ]
        Resource = [
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/environment/*",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/configurationprofile/*"
        ]
      }
    ]
  })
}

# Lambda invoke permission for RAG Lambda to call timeseries processor
resource "aws_iam_role_policy" "rag_lambda_invoke_policy" {
  name = "${var.project_name}-${var.environment}-rag-lambda-invoke-policy"
  role = aws_iam_role.rag_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:*:*:function:${var.project_name}-${var.environment}-timeseries-query-processor"
        ]
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

# Timeseries Query Processor Lambda Function
resource "aws_lambda_function" "timeseries_query_processor" {
  filename      = data.archive_file.timeseries_query_processor.output_path
  function_name = "${var.project_name}-${var.environment}-timeseries-query-processor"
  role          = aws_iam_role.timeseries_lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300 # 5 minutes
  memory_size   = 1024

  source_code_hash = data.archive_file.timeseries_query_processor.output_base64sha256

  layers = [aws_lambda_layer_version.shared_utils_layer.arn]

  environment {
    variables = {
      INFLUXDB_URL               = var.influxdb_url
      INFLUXDB_ORG               = var.influxdb_org
      INFLUXDB_BUCKET            = var.influxdb_bucket
      INFLUXDB_TOKEN_SECRET_NAME = var.influxdb_token_secret_name
      MAX_QUERY_RESULTS          = "1000"
      QUERY_TIMEOUT_SECONDS      = "30"
      ENABLE_QUERY_CACHING       = "true"
      CACHE_TTL_SECONDS          = "300"
      APPCONFIG_APPLICATION      = "${var.project_name}-${var.environment}-app"
      ENVIRONMENT                = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.influxdb_lambda_sg.id]
  }

  depends_on = [
    aws_cloudwatch_log_group.timeseries_query_processor
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-query-processor"
    Environment = var.environment
    Purpose     = "Process time series queries against InfluxDB"
  }
}

# Package Timeseries Query Processor Lambda
data "archive_file" "timeseries_query_processor" {
  type        = "zip"
  source_dir  = "${path.root}/../src/timeseries_query_processor"
  output_path = "${path.module}/timeseries_query_processor.zip"
  excludes    = ["__pycache__", "*.pyc", "test_*.py", "README.md"]
}

# IAM role for Timeseries Query Processor
resource "aws_iam_role" "timeseries_lambda_role" {
  name = "${var.project_name}-${var.environment}-timeseries-lambda-role"

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
    Name = "${var.project_name}-${var.environment}-timeseries-lambda-role"
  }
}

# Basic execution policy for Timeseries Lambda
resource "aws_iam_role_policy_attachment" "timeseries_lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.timeseries_lambda_role.name
}

# VPC execution policy for Timeseries Lambda
resource "aws_iam_role_policy_attachment" "timeseries_lambda_vpc_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  role       = aws_iam_role.timeseries_lambda_role.name
}

# Secrets Manager access policy for Timeseries Lambda
resource "aws_iam_role_policy" "timeseries_lambda_secrets_policy" {
  name = "${var.project_name}-${var.environment}-timeseries-lambda-secrets-policy"
  role = aws_iam_role.timeseries_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:${var.influxdb_token_secret_name}*"
        ]
      }
    ]
  })
}

# CloudWatch metrics policy for Timeseries Lambda
resource "aws_iam_role_policy" "timeseries_lambda_cloudwatch_policy" {
  name = "${var.project_name}-${var.environment}-timeseries-lambda-cloudwatch-policy"
  role = aws_iam_role.timeseries_lambda_role.id

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
            "cloudwatch:namespace" = ["ONS/TimeseriesProcessor", "ONS/TrafficSwitching"]
          }
        }
      }
    ]
  })
}

# AppConfig access policy for Timeseries Lambda
resource "aws_iam_role_policy" "timeseries_lambda_appconfig_policy" {
  name = "${var.project_name}-${var.environment}-timeseries-lambda-appconfig-policy"
  role = aws_iam_role.timeseries_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "appconfig:StartConfigurationSession",
          "appconfig:GetConfiguration"
        ]
        Resource = [
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/environment/*",
          "arn:aws:appconfig:*:*:application/${var.project_name}-${var.environment}-app/configurationprofile/*"
        ]
      }
    ]
  })
}

# CloudWatch Log Group for Timeseries Query Processor
resource "aws_cloudwatch_log_group" "timeseries_query_processor" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-timeseries-query-processor"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-query-processor-logs"
    Environment = var.environment
  }
}

# CloudWatch Alarms for Timeseries Query Processor
resource "aws_cloudwatch_metric_alarm" "timeseries_processor_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-timeseries-processor-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors timeseries processor errors"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.timeseries_query_processor.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-processor-errors"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "timeseries_processor_duration" {
  alarm_name          = "${var.project_name}-${var.environment}-timeseries-processor-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Average"
  threshold           = "30000" # 30 seconds
  alarm_description   = "This metric monitors timeseries processor duration"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.timeseries_query_processor.function_name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-processor-duration"
    Environment = var.environment
  }
}

# Custom CloudWatch Alarms for Timeseries-specific metrics
resource "aws_cloudwatch_metric_alarm" "timeseries_processor_query_failures" {
  alarm_name          = "${var.project_name}-${var.environment}-timeseries-query-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "QueryFailure"
  namespace           = "ONS/TimeseriesProcessor"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors timeseries query failures"
  alarm_actions       = [var.sns_topic_arn]

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-query-failures"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "timeseries_processor_high_latency" {
  alarm_name          = "${var.project_name}-${var.environment}-timeseries-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "QueryLatency"
  namespace           = "ONS/TimeseriesProcessor"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000" # 5 seconds
  alarm_description   = "This metric monitors timeseries query latency"
  alarm_actions       = [var.sns_topic_arn]

  tags = {
    Name        = "${var.project_name}-${var.environment}-timeseries-high-latency"
    Environment = var.environment
  }
}