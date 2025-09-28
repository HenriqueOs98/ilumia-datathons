# Timestream for InfluxDB Database Instance
resource "aws_timestreaminfluxdb_db_instance" "main" {
  allocated_storage      = var.allocated_storage
  bucket                = var.influxdb_bucket
  db_instance_type      = var.db_instance_class
  name                  = "${var.project_name}-${var.environment}-influxdb"
  organization          = var.influxdb_org
  password              = var.password
  publicly_accessible  = var.publicly_accessible
  username              = var.username
  vpc_security_group_ids = [aws_security_group.influxdb.id]
  vpc_subnet_ids        = var.subnet_ids

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb"
    Environment = var.environment
    Purpose     = "Energy Data Time Series Storage - InfluxDB"
    Project     = var.project_name
  }
}

# Note: Timestream for InfluxDB uses vpc_subnet_ids directly, no subnet group needed

# Security Group for InfluxDB
resource "aws_security_group" "influxdb" {
  name_prefix = "${var.project_name}-${var.environment}-influxdb-"
  vpc_id      = var.vpc_id
  description = "Security group for Timestream InfluxDB instance"

  # InfluxDB HTTP API port
  ingress {
    from_port       = var.port
    to_port         = var.port
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda_influxdb_client.id]
    description     = "InfluxDB HTTP API access from Lambda functions"
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-sg"
    Environment = var.environment
    Project     = var.project_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Lambda functions accessing InfluxDB
resource "aws_security_group" "lambda_influxdb_client" {
  name_prefix = "${var.project_name}-${var.environment}-lambda-influxdb-client-"
  vpc_id      = var.vpc_id
  description = "Security group for Lambda functions accessing InfluxDB"

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-lambda-influxdb-client-sg"
    Environment = var.environment
    Project     = var.project_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

# IAM Role for InfluxDB Lambda functions
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
    Name        = "${var.project_name}-${var.environment}-influxdb-lambda-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# IAM Policy for InfluxDB Lambda functions
resource "aws_iam_policy" "influxdb_lambda_policy" {
  name        = "${var.project_name}-${var.environment}-influxdb-lambda-policy"
  description = "IAM policy for InfluxDB Lambda functions"

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
          "timestream-influxdb:GetDbInstance",
          "timestream-influxdb:ListDbInstances",
          "timestream-influxdb:DescribeDbInstances"
        ]
        Resource = aws_timestreaminfluxdb_db_instance.main.arn
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
          "arn:aws:s3:::${var.rejected_data_bucket}/influxdb-rejected/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.influxdb_credentials.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AttachNetworkInterface",
          "ec2:DetachNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "influxdb_lambda_policy" {
  role       = aws_iam_role.influxdb_lambda_role.name
  policy_arn = aws_iam_policy.influxdb_lambda_policy.arn
}

# Attach VPC execution role for Lambda
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution_role" {
  role       = aws_iam_role.influxdb_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Secrets Manager for InfluxDB credentials
resource "aws_secretsmanager_secret" "influxdb_credentials" {
  name        = "${var.project_name}-${var.environment}-influxdb-credentials"
  description = "InfluxDB database credentials"

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-credentials"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "influxdb_credentials" {
  secret_id = aws_secretsmanager_secret.influxdb_credentials.id
  secret_string = jsonencode({
    username = var.username
    password = var.password
    endpoint = aws_timestreaminfluxdb_db_instance.main.endpoint
    port     = var.port
    org      = var.influxdb_org
    bucket   = var.influxdb_bucket
    token    = var.influxdb_token
  })
}

# CloudWatch Log Group for InfluxDB Lambda functions
resource "aws_cloudwatch_log_group" "influxdb_lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-influxdb-loader"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-lambda-logs"
    Environment = var.environment
    Project     = var.project_name
  }
}

# CloudWatch Metrics for InfluxDB monitoring
resource "aws_cloudwatch_metric_alarm" "influxdb_cpu_utilization" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/TimestreamInfluxDB"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "This metric monitors InfluxDB CPU utilization"
  alarm_actions       = var.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_timestreaminfluxdb_db_instance.main.name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-cpu-alarm"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_cloudwatch_metric_alarm" "influxdb_connection_count" {
  alarm_name          = "${var.project_name}-${var.environment}-influxdb-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/TimestreamInfluxDB"
  period              = "300"
  statistic           = "Average"
  threshold           = var.connection_alarm_threshold
  alarm_description   = "This metric monitors InfluxDB connection count"
  alarm_actions       = var.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_timestreaminfluxdb_db_instance.main.name
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-connections-alarm"
    Environment = var.environment
    Project     = var.project_name
  }
}

# KMS Key for InfluxDB encryption
resource "aws_kms_key" "influxdb" {
  count = var.storage_encrypted ? 1 : 0

  description             = "KMS key for InfluxDB encryption"
  deletion_window_in_days = var.kms_deletion_window

  tags = {
    Name        = "${var.project_name}-${var.environment}-influxdb-kms"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_kms_alias" "influxdb" {
  count = var.storage_encrypted ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-influxdb"
  target_key_id = aws_kms_key.influxdb[0].key_id
}