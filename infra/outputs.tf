output "s3_raw_bucket_name" {
  description = "Name of the S3 raw data bucket"
  value       = module.s3_buckets.raw_bucket_name
}

output "s3_processed_bucket_name" {
  description = "Name of the S3 processed data bucket"
  value       = module.s3_buckets.processed_bucket_name
}

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = module.api_gateway.api_url
}

output "timestream_database_name" {
  description = "Timestream database name"
  value       = module.timestream.database_name
}

output "knowledge_base_id" {
  description = "Knowledge Base ID"
  value       = module.knowledge_base.knowledge_base_id
}

output "step_function_arn" {
  description = "Step Functions state machine ARN"
  value       = module.step_functions.state_machine_arn
}

output "s3_failed_bucket_name" {
  description = "Name of the S3 failed data bucket"
  value       = module.s3_buckets.failed_bucket_name
}

output "s3_access_logs_bucket_name" {
  description = "Name of the S3 access logs bucket"
  value       = module.s3_buckets.access_logs_bucket_name
}

output "s3_data_lake_structure" {
  description = "S3 data lake folder structure"
  value       = module.s3_buckets.data_lake_structure
}

output "s3_cross_region_replication_enabled" {
  description = "Whether cross-region replication is enabled"
  value       = var.enable_cross_region_replication
}

output "s3_processed_bucket_replica_name" {
  description = "Name of the processed data replica bucket"
  value       = module.s3_buckets.processed_bucket_replica_name
}

output "timestream_table_arns" {
  description = "ARNs of Timestream tables"
  value       = module.timestream.table_arns
}

output "timestream_loader_lambda_arn" {
  description = "ARN of the Timestream loader Lambda function"
  value       = module.lambda_functions.timestream_loader_arn
}

output "timestream_loader_lambda_name" {
  description = "Name of the Timestream loader Lambda function"
  value       = module.lambda_functions.timestream_loader_name
}

# Knowledge Base outputs
output "knowledge_base_arn" {
  description = "ARN of the Knowledge Base"
  value       = module.knowledge_base.knowledge_base_arn
}

output "opensearch_collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = module.knowledge_base.opensearch_collection_arn
}

output "opensearch_collection_endpoint" {
  description = "Endpoint of the OpenSearch Serverless collection"
  value       = module.knowledge_base.opensearch_collection_endpoint
}

output "knowledge_base_data_source_id" {
  description = "ID of the Knowledge Base S3 data source"
  value       = module.knowledge_base.data_source_id
}

# RAG Query Processor outputs
output "rag_query_processor_arn" {
  description = "ARN of the RAG query processor Lambda function"
  value       = module.lambda_functions.rag_query_processor_arn
}

output "rag_query_processor_name" {
  description = "Name of the RAG query processor Lambda function"
  value       = module.lambda_functions.rag_query_processor_name
}

# CodeDeploy outputs
output "codedeploy_application_name" {
  description = "Name of the CodeDeploy application"
  value       = module.codedeploy.codedeploy_application_name
}

output "codedeploy_deployment_groups" {
  description = "Map of CodeDeploy deployment group names"
  value       = module.codedeploy.deployment_groups
}

output "deployment_sns_topic_arn" {
  description = "ARN of the SNS topic for deployment alerts"
  value       = module.codedeploy.sns_topic_arn
}

# AppConfig outputs
output "appconfig_application_id" {
  description = "AppConfig application ID"
  value       = module.appconfig.application_id
}

output "appconfig_feature_flags_profile_id" {
  description = "AppConfig feature flags configuration profile ID"
  value       = module.appconfig.feature_flags_profile_id
}

output "appconfig_development_environment_id" {
  description = "AppConfig development environment ID"
  value       = module.appconfig.development_environment_id
}

output "appconfig_production_environment_id" {
  description = "AppConfig production environment ID"
  value       = module.appconfig.production_environment_id
}

output "appconfig_canary_deployment_strategy_id" {
  description = "AppConfig canary deployment strategy ID"
  value       = module.appconfig.canary_deployment_strategy_id
}

# Additional outputs for validation
output "s3_bucket_names" {
  description = "Map of all S3 bucket names"
  value = {
    raw_data       = module.s3_buckets.raw_bucket_name
    processed_data = module.s3_buckets.processed_bucket_name
    failed_data    = module.s3_buckets.failed_bucket_name
    access_logs    = module.s3_buckets.access_logs_bucket_name
  }
}

output "lambda_function_names" {
  description = "Map of all Lambda function names"
  value = {
    lambda_router             = module.lambda_functions.lambda_router_name
    structured_data_processor = module.lambda_functions.structured_data_processor_name
    rag_query_processor       = module.lambda_functions.rag_query_processor_name
    timestream_loader         = module.lambda_functions.timestream_loader_name
    cost_optimizer            = module.lambda_functions.cost_optimizer_name
  }
}