output "api_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_url" {
  description = "URL of the API Gateway"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/prod"
}

output "api_key_id" {
  description = "ID of the API key"
  value       = aws_api_gateway_api_key.main.id
}

output "api_key_value" {
  description = "Value of the API key"
  value       = aws_api_gateway_api_key.main.value
  sensitive   = true
}

output "usage_plan_basic_id" {
  description = "ID of the basic usage plan"
  value       = aws_api_gateway_usage_plan.basic.id
}

output "usage_plan_premium_id" {
  description = "ID of the premium usage plan"
  value       = aws_api_gateway_usage_plan.premium.id
}

output "stage_name" {
  description = "Name of the API Gateway stage"
  value       = aws_api_gateway_stage.prod.stage_name
}

output "execution_arn" {
  description = "Execution ARN of the API Gateway"
  value       = aws_api_gateway_rest_api.main.execution_arn
}