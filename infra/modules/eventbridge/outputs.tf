output "s3_event_rule_arn" {
  description = "ARN of the S3 object creation EventBridge rule"
  value       = aws_cloudwatch_event_rule.s3_object_created.arn
}

output "s3_event_rule_name" {
  description = "Name of the S3 object creation EventBridge rule"
  value       = aws_cloudwatch_event_rule.s3_object_created.name
}

output "processing_completed_rule_arn" {
  description = "ARN of the processing completed EventBridge rule"
  value       = aws_cloudwatch_event_rule.processing_completed.arn
}

output "processing_failed_rule_arn" {
  description = "ARN of the processing failed EventBridge rule"
  value       = aws_cloudwatch_event_rule.processing_failed.arn
}

output "processing_alerts_topic_arn" {
  description = "ARN of the processing alerts SNS topic"
  value       = aws_sns_topic.processing_alerts.arn
}

output "eventbridge_step_functions_role_arn" {
  description = "ARN of the EventBridge role for invoking Step Functions"
  value       = aws_iam_role.eventbridge_step_functions_role.arn
}

output "eventbridge_sns_role_arn" {
  description = "ARN of the EventBridge role for publishing to SNS"
  value       = aws_iam_role.eventbridge_sns_role.arn
}