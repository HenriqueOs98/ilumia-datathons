# Infrastructure Documentation

This document describes the AWS infrastructure components and their configurations.

## Terraform Modules

### Monitoring

**Resources:**
- `aws_sns_topic.critical_alerts`: aws_sns_topic resource
- `aws_sns_topic.warning_alerts`: aws_sns_topic resource
- `aws_sns_topic_subscription.critical_email`: aws_sns_topic_subscription resource
- `aws_sns_topic_subscription.warning_email`: aws_sns_topic_subscription resource
- `aws_cloudwatch_log_group.lambda_router`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_log_group.lambda_processor`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_log_group.lambda_api`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_log_group.lambda_timestream`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_log_group.step_functions`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_log_group.api_gateway`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_dashboard.ons_platform`: aws_cloudwatch_dashboard resource
- `aws_cloudwatch_metric_alarm.lambda_router_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.lambda_router_duration`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.lambda_processor_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.lambda_processor_duration`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.api_gateway_latency`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.api_gateway_4xx_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.api_gateway_5xx_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.step_functions_failed_executions`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.step_functions_execution_time`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_log_metric_filter.processing_success_rate`: aws_cloudwatch_log_metric_filter resource
- `aws_cloudwatch_log_metric_filter.processing_failure_rate`: aws_cloudwatch_log_metric_filter resource
- `aws_cloudwatch_log_metric_filter.data_quality_issues`: aws_cloudwatch_log_metric_filter resource
- `aws_cloudwatch_metric_alarm.processing_failure_rate_alarm`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.data_quality_issues_alarm`: aws_cloudwatch_metric_alarm resource
- `aws_budgets_budget.ons_platform_budget`: aws_budgets_budget resource
- `aws_cloudwatch_log_metric_filter.lambda_cold_starts`: aws_cloudwatch_log_metric_filter resource
- `aws_cloudwatch_log_metric_filter.lambda_memory_utilization`: aws_cloudwatch_log_metric_filter resource
- `aws_cloudwatch_metric_alarm.high_lambda_cold_starts`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_dashboard.cost_optimization`: aws_cloudwatch_dashboard resource
- `aws_lambda_function.cost_optimizer`: aws_lambda_function resource
- `aws_iam_role.cost_optimizer_role`: aws_iam_role resource
- `aws_iam_role_policy.cost_optimizer_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_event_rule.cost_optimization_schedule`: aws_cloudwatch_event_rule resource
- `aws_cloudwatch_event_target.cost_optimizer_target`: aws_cloudwatch_event_target resource
- `aws_lambda_permission.allow_eventbridge_cost_optimizer`: aws_lambda_permission resource

**Variables:**
- `environment`: Environment name (dev, staging, prod) (Type: string)
- `project_name`: Name of the project (Type: string)
- `aws_region`: AWS region (Type: string)
- `critical_alert_emails`: List of email addresses for critical alerts (Type: list(string))
- `warning_alert_emails`: List of email addresses for warning alerts (Type: list(string))
- `log_retention_days`: CloudWatch log retention period in days (Type: number)
- `api_gateway_id`: API Gateway ID for log group creation (Type: string)
- `step_functions_arn`: Step Functions state machine ARN for monitoring (Type: string)
- `monthly_budget_limit`: Monthly budget limit in USD for the ONS Data Platform (Type: number)
- `cost_alert_emails`: List of email addresses for cost alerts (Type: list(string))
- `cost_anomaly_threshold`: Cost anomaly threshold in USD (Type: number)

**Outputs:**
- `critical_alerts_topic_arn`: ARN of the critical alerts SNS topic
- `warning_alerts_topic_arn`: ARN of the warning alerts SNS topic
- `dashboard_url`: URL of the CloudWatch dashboard
- `log_groups`: Map of log group names and ARNs
- `budget_name`: Name of the AWS Budget for cost monitoring
- `cost_optimizer_function_name`: Name of the cost optimizer Lambda function
- `cost_optimization_dashboard_url`: URL of the cost optimization CloudWatch dashboard
- `sns_topic_arn`: ARN of the primary SNS topic for notifications
- `development_alarm_arn`: ARN of the development environment alarm
- `production_alarm_arn`: ARN of the production environment alarm

### Knowledge Base

**Resources:**
- `aws_iam_role.knowledge_base_role`: aws_iam_role resource
- `aws_iam_role_policy.knowledge_base_s3_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.knowledge_base_opensearch_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.knowledge_base_bedrock_policy`: aws_iam_role_policy resource
- `aws_opensearchserverless_security_policy.knowledge_base_encryption`: aws_opensearchserverless_security_policy resource
- `aws_opensearchserverless_security_policy.knowledge_base_network`: aws_opensearchserverless_security_policy resource
- `aws_opensearchserverless_access_policy.knowledge_base_data_access`: aws_opensearchserverless_access_policy resource
- `aws_opensearchserverless_collection.knowledge_base`: aws_opensearchserverless_collection resource
- `aws_bedrockagent_knowledge_base.ons_knowledge_base`: aws_bedrockagent_knowledge_base resource
- `aws_bedrockagent_data_source.s3_data_source`: aws_bedrockagent_data_source resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `s3_processed_bucket`: S3 processed data bucket name (Type: string)

**Outputs:**
- `knowledge_base_id`: ID of the Knowledge Base
- `knowledge_base_arn`: ARN of the Knowledge Base
- `opensearch_collection_arn`: ARN of the OpenSearch Serverless collection
- `opensearch_collection_endpoint`: Endpoint of the OpenSearch Serverless collection
- `data_source_id`: ID of the S3 data source
- `knowledge_base_role_arn`: ARN of the Knowledge Base IAM role

### Step Functions

**Resources:**
- `aws_iam_role.step_functions_role`: aws_iam_role resource
- `aws_iam_role_policy.step_functions_policy`: aws_iam_role_policy resource
- `aws_sns_topic.processing_dlq`: aws_sns_topic resource
- `aws_cloudwatch_log_group.step_functions_logs`: aws_cloudwatch_log_group resource
- `aws_sfn_state_machine.data_processing_pipeline`: aws_sfn_state_machine resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `lambda_router_arn`: ARN of the router Lambda function (Type: string)
- `lambda_processor_arn`: ARN of the processor Lambda function (Type: string)
- `lambda_timestream_loader_arn`: ARN of the Timestream loader Lambda function (Type: string)
- `lambda_knowledge_base_updater_arn`: ARN of the Knowledge Base updater Lambda function (Type: string)
- `batch_job_definition_arn`: ARN of the Batch job definition for PDF processing (Type: string)
- `batch_job_queue_arn`: ARN of the Batch job queue (Type: string)

**Outputs:**
- `state_machine_arn`: ARN of the Step Functions state machine
- `state_machine_name`: Name of the Step Functions state machine
- `dlq_topic_arn`: ARN of the Dead Letter Queue SNS topic
- `step_functions_role_arn`: ARN of the Step Functions execution role

### Timestream

**Resources:**
- `aws_timestreamwrite_database.main`: aws_timestreamwrite_database resource
- `aws_timestreamwrite_table.generation_data`: aws_timestreamwrite_table resource
- `aws_timestreamwrite_table.consumption_data`: aws_timestreamwrite_table resource
- `aws_timestreamwrite_table.transmission_data`: aws_timestreamwrite_table resource
- `aws_iam_role.timestream_lambda_role`: aws_iam_role resource
- `aws_iam_policy.timestream_lambda_policy`: aws_iam_policy resource
- `aws_iam_role_policy_attachment.timestream_lambda_policy`: aws_iam_role_policy_attachment resource
- `aws_cloudwatch_log_group.timestream_lambda_logs`: aws_cloudwatch_log_group resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `memory_retention_hours`: Memory store retention period in hours (Type: number)
- `magnetic_retention_days`: Magnetic store retention period in days (Type: number)
- `processed_data_bucket`: S3 bucket name for processed data (Type: string)
- `rejected_data_bucket`: S3 bucket name for rejected data (Type: string)
- `log_retention_days`: CloudWatch log retention in days (Type: number)

**Outputs:**
- `database_name`: Name of the Timestream database
- `database_arn`: ARN of the Timestream database
- `generation_table_name`: Name of the generation data table
- `consumption_table_name`: Name of the consumption data table
- `transmission_table_name`: Name of the transmission data table
- `lambda_role_arn`: ARN of the Timestream Lambda IAM role
- `lambda_log_group_name`: Name of the Timestream Lambda CloudWatch log group
- `table_arns`: ARNs of all Timestream tables

### Api Gateway

**Resources:**
- `aws_api_gateway_rest_api.main`: aws_api_gateway_rest_api resource
- `aws_api_gateway_deployment.main`: aws_api_gateway_deployment resource
- `aws_api_gateway_stage.prod`: aws_api_gateway_stage resource
- `aws_cloudwatch_log_group.api_gateway`: aws_cloudwatch_log_group resource
- `aws_api_gateway_api_key.main`: aws_api_gateway_api_key resource
- `aws_api_gateway_usage_plan.basic`: aws_api_gateway_usage_plan resource
- `aws_api_gateway_usage_plan.premium`: aws_api_gateway_usage_plan resource
- `aws_api_gateway_usage_plan_key.main`: aws_api_gateway_usage_plan_key resource
- `aws_lambda_permission.api_gateway`: aws_lambda_permission resource
- `aws_iam_role.api_gateway_cloudwatch`: aws_iam_role resource
- `aws_iam_role_policy_attachment.api_gateway_cloudwatch`: aws_iam_role_policy_attachment resource
- `aws_api_gateway_account.main`: aws_api_gateway_account resource
- `aws_api_gateway_method_settings.all`: aws_api_gateway_method_settings resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `lambda_api_arn`: ARN of the API Lambda function (Type: string)
- `lambda_function_name`: Name of the API Lambda function (Type: string)
- `throttle_rate_limit`: API Gateway throttle rate limit (requests per second) (Type: number)
- `throttle_burst_limit`: API Gateway throttle burst limit (Type: number)
- `premium_throttle_rate_limit`: Premium tier throttle rate limit (requests per second) (Type: number)
- `premium_throttle_burst_limit`: Premium tier throttle burst limit (Type: number)
- `quota_limit`: Daily quota limit for basic plan (Type: number)
- `premium_quota_limit`: Daily quota limit for premium plan (Type: number)
- `log_retention_days`: CloudWatch log retention in days (Type: number)
- `tags`: Tags to apply to resources (Type: map(string))

**Outputs:**
- `api_id`: ID of the API Gateway
- `api_url`: URL of the API Gateway
- `api_key_id`: ID of the API key
- `api_key_value`: Value of the API key
- `usage_plan_basic_id`: ID of the basic usage plan
- `usage_plan_premium_id`: ID of the premium usage plan
- `stage_name`: Name of the API Gateway stage
- `execution_arn`: Execution ARN of the API Gateway

### Lambda

**Resources:**
- `aws_iam_role.lambda_execution_role`: aws_iam_role resource
- `aws_iam_role_policy_attachment.lambda_basic_execution`: aws_iam_role_policy_attachment resource
- `aws_lambda_function.timestream_loader`: aws_lambda_function resource
- `aws_cloudwatch_log_group.timestream_loader`: aws_cloudwatch_log_group resource
- `aws_lambda_layer_version.pandas_layer`: aws_lambda_layer_version resource
- `null_resource.build_pandas_layer`: null_resource resource
- `aws_lambda_function.rag_query_processor`: aws_lambda_function resource
- `aws_iam_role.rag_lambda_role`: aws_iam_role resource
- `aws_iam_role_policy_attachment.rag_lambda_basic_execution`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy.rag_lambda_bedrock_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.rag_lambda_cloudwatch_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_log_group.rag_query_processor`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_metric_alarm.rag_processor_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.rag_processor_duration`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.rag_processor_query_failures`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.rag_processor_high_latency`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.timestream_loader_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.timestream_loader_duration`: aws_cloudwatch_metric_alarm resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `s3_raw_bucket`: S3 raw data bucket name (Type: string)
- `s3_processed_bucket`: S3 processed data bucket name (Type: string)
- `timestream_database_name`: Timestream database name (Type: string)
- `generation_table_name`: Timestream generation table name (Type: string)
- `consumption_table_name`: Timestream consumption table name (Type: string)
- `transmission_table_name`: Timestream transmission table name (Type: string)
- `timestream_lambda_role_arn`: IAM role ARN for Timestream Lambda function (Type: string)
- `log_retention_days`: CloudWatch log retention in days (Type: number)
- `sns_topic_arn`: SNS topic ARN for alarms (Type: string)
- `knowledge_base_id`: Amazon Bedrock Knowledge Base ID (Type: string)
- `bedrock_model_arn`: Amazon Bedrock model ARN for RAG generation (Type: string)

**Outputs:**
- `router_lambda_arn`: ARN of the router Lambda function
- `processor_lambda_arn`: ARN of the processor Lambda function
- `api_lambda_arn`: ARN of the API Lambda function
- `function_names`: List of Lambda function names
- `timestream_loader_arn`: ARN of the Timestream loader Lambda function
- `timestream_loader_name`: Name of the Timestream loader Lambda function
- `timestream_loader_log_group`: CloudWatch log group for Timestream loader
- `pandas_layer_arn`: ARN of the pandas Lambda layer
- `rag_query_processor_arn`: ARN of the RAG query processor Lambda function
- `rag_query_processor_name`: Name of the RAG query processor Lambda function
- `rag_query_processor_log_group`: CloudWatch log group for RAG query processor
- `rag_lambda_role_arn`: ARN of the RAG Lambda execution role
- `router_lambda_name`: Name of the router Lambda function
- `processor_lambda_name`: Name of the processor Lambda function
- `api_lambda_name`: Name of the API Lambda function
- `lambda_router_name`: Name of the lambda router function
- `structured_data_processor_name`: Name of the structured data processor function
- `cost_optimizer_name`: Name of the cost optimizer function

### Appconfig

**Resources:**
- `aws_appconfig_application.main`: aws_appconfig_application resource
- `aws_appconfig_configuration_profile.feature_flags`: aws_appconfig_configuration_profile resource
- `aws_appconfig_configuration_profile.app_settings`: aws_appconfig_configuration_profile resource
- `aws_appconfig_environment.development`: aws_appconfig_environment resource
- `aws_appconfig_environment.production`: aws_appconfig_environment resource
- `aws_appconfig_deployment_strategy.canary_10_percent`: aws_appconfig_deployment_strategy resource
- `aws_iam_role.appconfig_service_role`: aws_iam_role resource
- `aws_iam_role_policy.appconfig_cloudwatch_policy`: aws_iam_role_policy resource
- `aws_appconfig_hosted_configuration_version.feature_flags_initial`: aws_appconfig_hosted_configuration_version resource
- `aws_appconfig_hosted_configuration_version.app_settings_initial`: aws_appconfig_hosted_configuration_version resource

**Variables:**
- `project_name`: Name of the project (Type: string)
- `tags`: Tags to apply to resources (Type: map(string))
- `development_alarm_arn`: CloudWatch alarm ARN for development environment monitoring (Type: string)
- `production_alarm_arn`: CloudWatch alarm ARN for production environment monitoring (Type: string)

**Outputs:**
- `application_id`: AppConfig application ID
- `feature_flags_profile_id`: Feature flags configuration profile ID
- `app_settings_profile_id`: Application settings configuration profile ID
- `development_environment_id`: Development environment ID
- `production_environment_id`: Production environment ID
- `canary_deployment_strategy_id`: Canary deployment strategy ID
- `service_role_arn`: AppConfig service role ARN

### Codedeploy

**Resources:**
- `aws_codedeploy_app.lambda_app`: aws_codedeploy_app resource
- `aws_iam_role.codedeploy_service_role`: aws_iam_role resource
- `aws_iam_role_policy_attachment.codedeploy_service_role_policy`: aws_iam_role_policy_attachment resource
- `aws_cloudwatch_metric_alarm.lambda_error_rate`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.lambda_duration`: aws_cloudwatch_metric_alarm resource
- `aws_sns_topic.deployment_alerts`: aws_sns_topic resource
- `aws_codedeploy_deployment_group.lambda_deployment_group`: aws_codedeploy_deployment_group resource

**Variables:**
- `project_name`: Name of the project (Type: string)
- `tags`: Tags to apply to resources (Type: map(string))
- `lambda_functions`: Map of Lambda functions to configure for blue-green deployment (Type: map(object({)
- `error_rate_threshold`: Error rate threshold for automatic rollback (Type: number)
- `duration_threshold`: Duration threshold in milliseconds for automatic rollback (Type: number)
- `deployment_config_name`: CodeDeploy deployment configuration (Type: string)
- `sns_email_endpoint`: Email endpoint for deployment alerts (Type: string)

**Outputs:**
- `codedeploy_application_name`: Name of the CodeDeploy application
- `codedeploy_service_role_arn`: ARN of the CodeDeploy service role
- `deployment_groups`: Map of deployment group names
- `sns_topic_arn`: ARN of the SNS topic for deployment alerts
- `cloudwatch_alarms`: Map of CloudWatch alarm names

### Eventbridge

**Resources:**
- `aws_cloudwatch_event_rule.s3_object_created`: aws_cloudwatch_event_rule resource
- `aws_iam_role.eventbridge_step_functions_role`: aws_iam_role resource
- `aws_iam_role_policy.eventbridge_step_functions_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_event_target.step_functions_target`: aws_cloudwatch_event_target resource
- `aws_cloudwatch_event_rule.processing_completed`: aws_cloudwatch_event_rule resource
- `aws_cloudwatch_event_rule.processing_failed`: aws_cloudwatch_event_rule resource
- `aws_sns_topic.processing_alerts`: aws_sns_topic resource
- `aws_cloudwatch_event_target.processing_failure_alert`: aws_cloudwatch_event_target resource
- `aws_iam_role.eventbridge_sns_role`: aws_iam_role resource
- `aws_iam_role_policy.eventbridge_sns_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_log_group.eventbridge_logs`: aws_cloudwatch_log_group resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `s3_raw_bucket`: S3 raw data bucket name (Type: string)
- `step_function_arn`: ARN of the Step Functions state machine (Type: string)

**Outputs:**
- `s3_event_rule_arn`: ARN of the S3 object creation EventBridge rule
- `s3_event_rule_name`: Name of the S3 object creation EventBridge rule
- `processing_completed_rule_arn`: ARN of the processing completed EventBridge rule
- `processing_failed_rule_arn`: ARN of the processing failed EventBridge rule
- `processing_alerts_topic_arn`: ARN of the processing alerts SNS topic
- `eventbridge_step_functions_role_arn`: ARN of the EventBridge role for invoking Step Functions
- `eventbridge_sns_role_arn`: ARN of the EventBridge role for publishing to SNS

### S3

**Resources:**
- `aws_s3_bucket.raw_data`: aws_s3_bucket resource
- `aws_s3_bucket_versioning.raw_data`: aws_s3_bucket_versioning resource
- `aws_s3_bucket_server_side_encryption_configuration.raw_data`: aws_s3_bucket_server_side_encryption_configuration resource
- `aws_s3_bucket_public_access_block.raw_data`: aws_s3_bucket_public_access_block resource
- `aws_s3_bucket_lifecycle_configuration.raw_data`: aws_s3_bucket_lifecycle_configuration resource
- `aws_s3_bucket_notification.raw_data`: aws_s3_bucket_notification resource
- `aws_s3_bucket.processed_data`: aws_s3_bucket resource
- `aws_s3_bucket_versioning.processed_data`: aws_s3_bucket_versioning resource
- `aws_s3_bucket_server_side_encryption_configuration.processed_data`: aws_s3_bucket_server_side_encryption_configuration resource
- `aws_s3_bucket_public_access_block.processed_data`: aws_s3_bucket_public_access_block resource
- `aws_s3_bucket_lifecycle_configuration.processed_data`: aws_s3_bucket_lifecycle_configuration resource
- `aws_s3_bucket_intelligent_tiering_configuration.processed_data`: aws_s3_bucket_intelligent_tiering_configuration resource
- `aws_s3_bucket.failed_data`: aws_s3_bucket resource
- `aws_s3_bucket_versioning.failed_data`: aws_s3_bucket_versioning resource
- `aws_s3_bucket_server_side_encryption_configuration.failed_data`: aws_s3_bucket_server_side_encryption_configuration resource
- `aws_s3_bucket_public_access_block.failed_data`: aws_s3_bucket_public_access_block resource
- `aws_s3_bucket_lifecycle_configuration.failed_data`: aws_s3_bucket_lifecycle_configuration resource
- `aws_s3_object.raw_data_structure`: aws_s3_object resource
- `aws_s3_object.processed_data_structure`: aws_s3_object resource
- `aws_s3_bucket.processed_data_replica`: aws_s3_bucket resource
- `aws_s3_bucket_versioning.processed_data_replica`: aws_s3_bucket_versioning resource
- `aws_iam_role.replication`: aws_iam_role resource
- `aws_iam_policy.replication`: aws_iam_policy resource
- `aws_iam_role_policy_attachment.replication`: aws_iam_role_policy_attachment resource
- `aws_s3_bucket_replication_configuration.processed_data`: aws_s3_bucket_replication_configuration resource
- `aws_s3_bucket_metric.raw_data_metrics`: aws_s3_bucket_metric resource
- `aws_s3_bucket_metric.processed_data_metrics`: aws_s3_bucket_metric resource
- `aws_s3_bucket_metric.failed_data_metrics`: aws_s3_bucket_metric resource
- `aws_s3_bucket.access_logs`: aws_s3_bucket resource
- `aws_s3_bucket_server_side_encryption_configuration.access_logs`: aws_s3_bucket_server_side_encryption_configuration resource
- `aws_s3_bucket_lifecycle_configuration.access_logs`: aws_s3_bucket_lifecycle_configuration resource
- `aws_s3_bucket_logging.raw_data`: aws_s3_bucket_logging resource
- `aws_s3_bucket_logging.processed_data`: aws_s3_bucket_logging resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `enable_cross_region_replication`: Enable cross-region replication for critical buckets (Type: bool)
- `replication_destination_region`: Destination region for cross-region replication (Type: string)
- `enable_mfa_delete`: Enable MFA delete for critical buckets (Type: bool)
- `raw_data_retention_days`: Retention period for raw data in days (Type: number)
- `processed_data_retention_days`: Retention period for processed data in days (Type: number)

**Outputs:**
- `raw_bucket_name`: Name of the raw data bucket
- `raw_bucket_arn`: ARN of the raw data bucket
- `processed_bucket_name`: Name of the processed data bucket
- `processed_bucket_arn`: ARN of the processed data bucket
- `failed_bucket_name`: Name of the failed data bucket
- `failed_bucket_arn`: ARN of the failed data bucket
- `access_logs_bucket_name`: Name of the access logs bucket
- `access_logs_bucket_arn`: ARN of the access logs bucket
- `processed_bucket_replica_name`: Name of the processed data replica bucket
- `processed_bucket_replica_arn`: ARN of the processed data replica bucket
- `data_lake_structure`: Data lake folder structure information

