variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "lambda_router_arn" {
  description = "ARN of the router Lambda function"
  type        = string
}

variable "lambda_processor_arn" {
  description = "ARN of the processor Lambda function"
  type        = string
}

variable "lambda_timestream_loader_arn" {
  description = "ARN of the Timestream loader Lambda function"
  type        = string
  default     = "arn:aws:lambda:us-east-1:123456789012:function:placeholder-timestream-loader"
}

variable "lambda_knowledge_base_updater_arn" {
  description = "ARN of the Knowledge Base updater Lambda function"
  type        = string
  default     = "arn:aws:lambda:us-east-1:123456789012:function:placeholder-kb-updater"
}

variable "batch_job_definition_arn" {
  description = "ARN of the Batch job definition for PDF processing"
  type        = string
  default     = "arn:aws:batch:us-east-1:123456789012:job-definition/placeholder-pdf-processor"
}

variable "batch_job_queue_arn" {
  description = "ARN of the Batch job queue"
  type        = string
  default     = "arn:aws:batch:us-east-1:123456789012:job-queue/placeholder-pdf-queue"
}