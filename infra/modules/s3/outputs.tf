output "raw_bucket_name" {
  description = "Name of the raw data bucket"
  value       = aws_s3_bucket.raw_data.bucket
}

output "raw_bucket_arn" {
  description = "ARN of the raw data bucket"
  value       = aws_s3_bucket.raw_data.arn
}

output "processed_bucket_name" {
  description = "Name of the processed data bucket"
  value       = aws_s3_bucket.processed_data.bucket
}

output "processed_bucket_arn" {
  description = "ARN of the processed data bucket"
  value       = aws_s3_bucket.processed_data.arn
}

output "failed_bucket_name" {
  description = "Name of the failed data bucket"
  value       = aws_s3_bucket.failed_data.bucket
}

output "failed_bucket_arn" {
  description = "ARN of the failed data bucket"
  value       = aws_s3_bucket.failed_data.arn
}

output "access_logs_bucket_name" {
  description = "Name of the access logs bucket"
  value       = aws_s3_bucket.access_logs.bucket
}

output "access_logs_bucket_arn" {
  description = "ARN of the access logs bucket"
  value       = aws_s3_bucket.access_logs.arn
}

output "processed_bucket_replica_name" {
  description = "Name of the processed data replica bucket"
  value       = var.enable_cross_region_replication ? aws_s3_bucket.processed_data_replica[0].bucket : null
}

output "processed_bucket_replica_arn" {
  description = "ARN of the processed data replica bucket"
  value       = var.enable_cross_region_replication ? aws_s3_bucket.processed_data_replica[0].arn : null
}

output "data_lake_structure" {
  description = "Data lake folder structure information"
  value = {
    raw_data_folders = [
      "year=2024/",
      "year=2025/",
      "dataset=generation/",
      "dataset=consumption/",
      "dataset=transmission/"
    ]
    processed_data_folders = [
      "dataset=generation/year=2024/month=01/",
      "dataset=generation/year=2024/month=02/",
      "dataset=generation/year=2025/month=01/",
      "dataset=consumption/year=2024/month=01/",
      "dataset=consumption/year=2024/month=02/",
      "dataset=consumption/year=2025/month=01/",
      "dataset=transmission/year=2024/month=01/",
      "dataset=transmission/year=2024/month=02/",
      "dataset=transmission/year=2025/month=01/"
    ]
  }
}