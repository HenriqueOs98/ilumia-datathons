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
  value       = ["placeholder-router", "placeholder-processor", "rag-query-processor"]
}

# Timestream loader outputs removed as part of decommissioning
# These outputs were for the timestream_loader function which has been removed

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

# Additional outputs for main module compatibility
output "lambda_router_name" {
  description = "Name of the lambda router function"
  value       = "placeholder-router"
}

output "structured_data_processor_name" {
  description = "Name of the structured data processor function"
  value       = "placeholder-processor"
}

output "cost_optimizer_name" {
  description = "Name of the cost optimizer function"
  value       = "placeholder-cost-optimizer"
}