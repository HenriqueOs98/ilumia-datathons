output "database_name" {
  description = "Name of the Timestream database"
  value       = aws_timestreamwrite_database.main.database_name
}

output "database_arn" {
  description = "ARN of the Timestream database"
  value       = aws_timestreamwrite_database.main.arn
}

output "generation_table_name" {
  description = "Name of the generation data table"
  value       = aws_timestreamwrite_table.generation_data.table_name
}

output "consumption_table_name" {
  description = "Name of the consumption data table"
  value       = aws_timestreamwrite_table.consumption_data.table_name
}

output "transmission_table_name" {
  description = "Name of the transmission data table"
  value       = aws_timestreamwrite_table.transmission_data.table_name
}

output "lambda_role_arn" {
  description = "ARN of the Timestream Lambda IAM role"
  value       = aws_iam_role.timestream_lambda_role.arn
}

output "lambda_log_group_name" {
  description = "Name of the Timestream Lambda CloudWatch log group"
  value       = aws_cloudwatch_log_group.timestream_lambda_logs.name
}

output "table_arns" {
  description = "ARNs of all Timestream tables"
  value = {
    generation_data   = aws_timestreamwrite_table.generation_data.arn
    consumption_data  = aws_timestreamwrite_table.consumption_data.arn
    transmission_data = aws_timestreamwrite_table.transmission_data.arn
  }
}