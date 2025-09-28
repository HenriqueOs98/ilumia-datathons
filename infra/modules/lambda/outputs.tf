# Placeholder outputs for Lambda functions
# These will be implemented in subsequent tasks

output "router_lambda_arn" {
  description = "ARN of the router Lambda function"
  value       = "arn:aws:lambda:us-east-1:123456789012:function:placeholder-router"
}

output "processor_lambda_arn" {
  description = "ARN of the processor Lambda function"
  value       = "arn:aws:lambda:us-east-1:123456789012:function:placeholder-processor"
}

output "api_lambda_arn" {
  description = "ARN of the API Lambda function"
  value       = "arn:aws:lambda:us-east-1:123456789012:function:placeholder-api"
}

output "function_names" {
  description = "List of Lambda function names"
  value       = ["placeholder-router", "placeholder-processor", "rag-query-processor", "timestream-loader"]
}

output "timestream_loader_arn" {
  description = "ARN of the Timestream loader Lambda function"
  value       = aws_lambda_function.timestream_loader.arn
}

output "timestream_loader_name" {
  description = "Name of the Timestream loader Lambda function"
  value       = aws_lambda_function.timestream_loader.function_name
}

output "timestream_loader_log_group" {
  description = "CloudWatch log group for Timestream loader"
  value       = aws_cloudwatch_log_group.timestream_loader.name
}

output "pandas_layer_arn" {
  description = "ARN of the pandas Lambda layer"
  value       = aws_lambda_layer_version.pandas_layer.arn
}

# RAG Query Processor outputs
output "rag_query_processor_arn" {
  description = "ARN of the RAG query processor Lambda function"
  value       = aws_lambda_function.rag_query_processor.arn
}

output "rag_query_processor_name" {
  description = "Name of the RAG query processor Lambda function"
  value       = aws_lambda_function.rag_query_processor.function_name
}

output "rag_query_processor_log_group" {
  description = "CloudWatch log group for RAG query processor"
  value       = aws_cloudwatch_log_group.rag_query_processor.name
}

output "rag_lambda_role_arn" {
  description = "ARN of the RAG Lambda execution role"
  value       = aws_iam_role.rag_lambda_role.arn
}

# Individual function names for CodeDeploy
output "router_lambda_name" {
  description = "Name of the router Lambda function"
  value       = "placeholder-router"
}

output "processor_lambda_name" {
  description = "Name of the processor Lambda function"
  value       = "placeholder-processor"
}

output "api_lambda_name" {
  description = "Name of the API Lambda function"
  value       = "placeholder-api"
}