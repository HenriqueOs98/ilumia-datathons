output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.data_processing_pipeline.arn
}

output "state_machine_name" {
  description = "Name of the Step Functions state machine"
  value       = aws_sfn_state_machine.data_processing_pipeline.name
}

output "dlq_topic_arn" {
  description = "ARN of the Dead Letter Queue SNS topic"
  value       = aws_sns_topic.processing_dlq.arn
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions execution role"
  value       = aws_iam_role.step_functions_role.arn
}