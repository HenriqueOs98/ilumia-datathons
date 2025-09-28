# Timestream Database
resource "aws_timestreamwrite_database" "main" {
  database_name = "${var.project_name}_${var.environment}_energy_data"

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-db"
    Environment = var.environment
    Purpose     = "Energy Data Time Series Storage"
  }
}

# Generation Data Table
resource "aws_timestreamwrite_table" "generation_data" {
  database_name = aws_timestreamwrite_database.main.database_name
  table_name    = "generation_data"

  retention_properties {
    memory_store_retention_period_in_hours  = var.memory_retention_hours
    magnetic_store_retention_period_in_days = var.magnetic_retention_days
  }

  magnetic_store_write_properties {
    enable_magnetic_store_writes = true

    magnetic_store_rejected_data_location {
      s3_configuration {
        bucket_name       = var.rejected_data_bucket
        object_key_prefix = "timestream-rejected/generation/"
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-generation-table"
    Environment = var.environment
    DataType    = "Generation"
  }
}

# Consumption Data Table
resource "aws_timestreamwrite_table" "consumption_data" {
  database_name = aws_timestreamwrite_database.main.database_name
  table_name    = "consumption_data"

  retention_properties {
    memory_store_retention_period_in_hours  = var.memory_retention_hours
    magnetic_store_retention_period_in_days = var.magnetic_retention_days
  }

  magnetic_store_write_properties {
    enable_magnetic_store_writes = true

    magnetic_store_rejected_data_location {
      s3_configuration {
        bucket_name       = var.rejected_data_bucket
        object_key_prefix = "timestream-rejected/consumption/"
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-consumption-table"
    Environment = var.environment
    DataType    = "Consumption"
  }
}

# Transmission Data Table
resource "aws_timestreamwrite_table" "transmission_data" {
  database_name = aws_timestreamwrite_database.main.database_name
  table_name    = "transmission_data"

  retention_properties {
    memory_store_retention_period_in_hours  = var.memory_retention_hours
    magnetic_store_retention_period_in_days = var.magnetic_retention_days
  }

  magnetic_store_write_properties {
    enable_magnetic_store_writes = true

    magnetic_store_rejected_data_location {
      s3_configuration {
        bucket_name       = var.rejected_data_bucket
        object_key_prefix = "timestream-rejected/transmission/"
      }
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-transmission-table"
    Environment = var.environment
    DataType    = "Transmission"
  }
}

# IAM Role for Timestream Lambda function
resource "aws_iam_role" "timestream_lambda_role" {
  name = "${var.project_name}-${var.environment}-timestream-lambda-role"

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
    Name        = "${var.project_name}-${var.environment}-timestream-lambda-role"
    Environment = var.environment
  }
}

# IAM Policy for Timestream access
resource "aws_iam_policy" "timestream_lambda_policy" {
  name        = "${var.project_name}-${var.environment}-timestream-lambda-policy"
  description = "IAM policy for Timestream Lambda function"

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
          "timestream:WriteRecords",
          "timestream:DescribeEndpoints"
        ]
        Resource = [
          aws_timestreamwrite_database.main.arn,
          "${aws_timestreamwrite_database.main.arn}/table/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.processed_data_bucket}",
          "arn:aws:s3:::${var.processed_data_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.rejected_data_bucket}/timestream-rejected/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "timestream_lambda_policy" {
  role       = aws_iam_role.timestream_lambda_role.name
  policy_arn = aws_iam_policy.timestream_lambda_policy.arn
}

# CloudWatch Log Group for Timestream Lambda
resource "aws_cloudwatch_log_group" "timestream_lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-timestream-loader"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-${var.environment}-timestream-lambda-logs"
    Environment = var.environment
  }
}