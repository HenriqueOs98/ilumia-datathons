output "knowledge_base_id" {
  description = "ID of the Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.ons_knowledge_base.id
}

output "knowledge_base_arn" {
  description = "ARN of the Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.ons_knowledge_base.arn
}

output "opensearch_collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.knowledge_base.arn
}

output "opensearch_collection_endpoint" {
  description = "Endpoint of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.knowledge_base.collection_endpoint
}

output "data_source_id" {
  description = "ID of the S3 data source"
  value       = aws_bedrockagent_data_source.s3_data_source.data_source_id
}

output "knowledge_base_role_arn" {
  description = "ARN of the Knowledge Base IAM role"
  value       = aws_iam_role.knowledge_base_role.arn
}