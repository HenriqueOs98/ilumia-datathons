# S3 Raw Data Bucket
resource "aws_s3_bucket" "raw_data" {
  bucket = "${var.project_name}-${var.environment}-raw-data"
}

resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy for raw data bucket
resource "aws_s3_bucket_lifecycle_configuration" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    id     = "raw_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# Bucket notification for raw data
resource "aws_s3_bucket_notification" "raw_data" {
  bucket      = aws_s3_bucket.raw_data.id
  eventbridge = true
}

# S3 Processed Data Bucket
resource "aws_s3_bucket" "processed_data" {
  bucket = "${var.project_name}-${var.environment}-processed-data"
}

resource "aws_s3_bucket_versioning" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy for processed data bucket
resource "aws_s3_bucket_lifecycle_configuration" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id

  rule {
    id     = "processed_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 730
    }
  }
}

# Intelligent tiering for processed data (cost optimization)
resource "aws_s3_bucket_intelligent_tiering_configuration" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed_data_intelligent_tiering"

  status = "Enabled"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 90
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 180
  }
}

# S3 Failed Data Bucket
resource "aws_s3_bucket" "failed_data" {
  bucket = "${var.project_name}-${var.environment}-failed-data"
}

resource "aws_s3_bucket_versioning" "failed_data" {
  bucket = aws_s3_bucket.failed_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "failed_data" {
  bucket = aws_s3_bucket.failed_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "failed_data" {
  bucket = aws_s3_bucket.failed_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy for failed data bucket
resource "aws_s3_bucket_lifecycle_configuration" "failed_data" {
  bucket = aws_s3_bucket.failed_data.id

  rule {
    id     = "failed_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555 # 7 years retention for compliance
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# Data lake folder structure using S3 objects
resource "aws_s3_object" "raw_data_structure" {
  for_each = toset([
    "year=2024/",
    "year=2025/",
    "dataset=generation/",
    "dataset=consumption/",
    "dataset=transmission/"
  ])

  bucket = aws_s3_bucket.raw_data.id
  key    = each.value
  source = "/dev/null"
}

resource "aws_s3_object" "processed_data_structure" {
  for_each = toset([
    "dataset=generation/year=2024/month=01/",
    "dataset=generation/year=2024/month=02/",
    "dataset=generation/year=2025/month=01/",
    "dataset=consumption/year=2024/month=01/",
    "dataset=consumption/year=2024/month=02/",
    "dataset=consumption/year=2025/month=01/",
    "dataset=transmission/year=2024/month=01/",
    "dataset=transmission/year=2024/month=02/",
    "dataset=transmission/year=2025/month=01/"
  ])

  bucket = aws_s3_bucket.processed_data.id
  key    = each.value
  source = "/dev/null"
}
# Cross-region replication (optional)
resource "aws_s3_bucket" "processed_data_replica" {
  count    = var.enable_cross_region_replication ? 1 : 0
  provider = aws.replica
  bucket   = "${var.project_name}-${var.environment}-processed-data-replica"
}

resource "aws_s3_bucket_versioning" "processed_data_replica" {
  count    = var.enable_cross_region_replication ? 1 : 0
  provider = aws.replica
  bucket   = aws_s3_bucket.processed_data_replica[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

# IAM role for replication
resource "aws_iam_role" "replication" {
  count = var.enable_cross_region_replication ? 1 : 0
  name  = "${var.project_name}-${var.environment}-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "replication" {
  count = var.enable_cross_region_replication ? 1 : 0
  name  = "${var.project_name}-${var.environment}-s3-replication-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl"
        ]
        Resource = "${aws_s3_bucket.processed_data.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.processed_data.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete"
        ]
        Resource = var.enable_cross_region_replication ? "${aws_s3_bucket.processed_data_replica[0].arn}/*" : ""
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication" {
  count      = var.enable_cross_region_replication ? 1 : 0
  role       = aws_iam_role.replication[0].name
  policy_arn = aws_iam_policy.replication[0].arn
}

# Replication configuration
resource "aws_s3_bucket_replication_configuration" "processed_data" {
  count  = var.enable_cross_region_replication ? 1 : 0
  role   = aws_iam_role.replication[0].arn
  bucket = aws_s3_bucket.processed_data.id

  rule {
    id     = "processed_data_replication"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.processed_data_replica[0].arn
      storage_class = "STANDARD_IA"
    }
  }

  depends_on = [aws_s3_bucket_versioning.processed_data]
}

# CloudWatch metrics for S3 buckets
resource "aws_s3_bucket_metric" "raw_data_metrics" {
  bucket = aws_s3_bucket.raw_data.id
  name   = "raw_data_metrics"
}

resource "aws_s3_bucket_metric" "processed_data_metrics" {
  bucket = aws_s3_bucket.processed_data.id
  name   = "processed_data_metrics"
}

resource "aws_s3_bucket_metric" "failed_data_metrics" {
  bucket = aws_s3_bucket.failed_data.id
  name   = "failed_data_metrics"
}

# S3 Access Logging (optional)
resource "aws_s3_bucket" "access_logs" {
  bucket = "${var.project_name}-${var.environment}-access-logs"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "access_logs_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_logging" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "raw-data-access-logs/"
}

resource "aws_s3_bucket_logging" "processed_data" {
  bucket = aws_s3_bucket.processed_data.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "processed-data-access-logs/"
}