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
- `aws_cloudwatch_dashboard.influxdb_monitoring`: aws_cloudwatch_dashboard resource
- `aws_cloudwatch_dashboard.cost_optimization`: aws_cloudwatch_dashboard resource
- `aws_cloudwatch_log_group.influxdb_monitor`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_metric_alarm.influxdb_connection_status`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_health_check_latency`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_query_latency_simple`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_query_latency_complex`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_write_latency`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_write_throughput_low`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_query_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_write_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_cpu_utilization`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_memory_utilization`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_disk_utilization`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_active_connections`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_daily_cost_high`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_storage_growth`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_composite_alarm.influxdb_overall_health`: aws_cloudwatch_composite_alarm resource
- `aws_lambda_function.cost_optimizer`: aws_lambda_function resource
- `aws_iam_role.cost_optimizer_role`: aws_iam_role resource
- `aws_iam_role_policy.cost_optimizer_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_event_rule.cost_optimization_schedule`: aws_cloudwatch_event_rule resource
- `aws_cloudwatch_event_target.cost_optimizer_target`: aws_cloudwatch_event_target resource
- `aws_lambda_permission.allow_eventbridge_cost_optimizer`: aws_lambda_permission resource
- `aws_cloudwatch_event_rule.influxdb_monitor_schedule`: aws_cloudwatch_event_rule resource
- `aws_cloudwatch_event_target.influxdb_monitor_target`: aws_cloudwatch_event_target resource
- `aws_lambda_permission.allow_eventbridge_influxdb_monitor`: aws_lambda_permission resource
- `aws_sns_topic.influxdb_alerts`: aws_sns_topic resource
- `aws_sns_topic_subscription.influxdb_alert_email`: aws_sns_topic_subscription resource
- `aws_cloudwatch_metric_alarm.influxdb_scale_up_cpu`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_scale_down_cpu`: aws_cloudwatch_metric_alarm resource

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
- `influxdb_max_connections_threshold`: Maximum number of InfluxDB connections before alerting (Type: number)
- `influxdb_daily_cost_threshold`: Daily cost threshold for InfluxDB in USD (Type: number)
- `influxdb_storage_threshold_gb`: Storage usage threshold for InfluxDB in GB (Type: number)
- `influxdb_monitor_lambda_arn`: ARN of the InfluxDB monitor Lambda function (Type: string)

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
- `influxdb_alerts_topic_arn`: ARN of the InfluxDB alerts SNS topic
- `influxdb_dashboard_url`: URL of the InfluxDB monitoring CloudWatch dashboard
- `influxdb_composite_alarm_arn`: ARN of the InfluxDB overall health composite alarm
- `influxdb_log_group_arn`: ARN of the InfluxDB monitor Lambda log group
- `influxdb_connection_alarm_arn`: ARN of the InfluxDB connection status alarm
- `influxdb_performance_alarms`: Map of InfluxDB performance alarm ARNs
- `influxdb_resource_alarms`: Map of InfluxDB resource utilization alarm ARNs
- `influxdb_cost_alarms`: Map of InfluxDB cost monitoring alarm ARNs

### Timestream Influxdb

**Resources:**
- `aws_timestreaminfluxdb_db_instance.main`: aws_timestreaminfluxdb_db_instance resource
- `aws_security_group.influxdb`: aws_security_group resource
- `aws_security_group.lambda_influxdb_client`: aws_security_group resource
- `aws_iam_role.influxdb_lambda_role`: aws_iam_role resource
- `aws_iam_policy.influxdb_lambda_policy`: aws_iam_policy resource
- `aws_iam_role_policy_attachment.influxdb_lambda_policy`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy_attachment.lambda_vpc_execution_role`: aws_iam_role_policy_attachment resource
- `aws_secretsmanager_secret.influxdb_credentials`: aws_secretsmanager_secret resource
- `aws_secretsmanager_secret_version.influxdb_credentials`: aws_secretsmanager_secret_version resource
- `aws_cloudwatch_log_group.influxdb_lambda_logs`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_metric_alarm.influxdb_cpu_utilization`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_connection_count`: aws_cloudwatch_metric_alarm resource
- `aws_kms_key.influxdb`: aws_kms_key resource
- `aws_kms_alias.influxdb`: aws_kms_alias resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `vpc_id`: VPC ID where InfluxDB will be deployed (Type: string)
- `subnet_ids`: List of subnet IDs for InfluxDB deployment (Type: list(string))
- `availability_zone`: Availability zone for InfluxDB instance (Type: string)
- `allocated_storage`: The allocated storage in gibibytes (Type: number)
- `db_instance_class`: The InfluxDB instance class (Type: string)
- `db_name`: The name of the database to create when the DB instance is created (Type: string)
- `username`: Username for the master DB user (Type: string)
- `password`: Password for the master DB user (Type: string)
- `port`: The port on which the DB accepts connections (Type: number)
- `engine_version`: The engine version to use (Type: string)
- `influxdb_org`: InfluxDB organization name (Type: string)
- `influxdb_bucket`: Default InfluxDB bucket name (Type: string)
- `influxdb_token`: InfluxDB authentication token (Type: string)
- `backup_retention_period`: The days to retain backups for (Type: number)
- `backup_window`: The daily time range during which automated backups are created (Type: string)
- `maintenance_window`: The window to perform maintenance in (Type: string)
- `apply_immediately`: Specifies whether any database modifications are applied immediately (Type: bool)
- `auto_minor_version_upgrade`: Indicates that minor engine upgrades will be applied automatically (Type: bool)
- `publicly_accessible`: Bool to control if instance is publicly accessible (Type: bool)
- `storage_encrypted`: Specifies whether the DB instance is encrypted (Type: bool)
- `storage_type`: One of 'standard' (magnetic), 'gp2' (general purpose SSD), or 'io1' (provisioned IOPS SSD) (Type: string)
- `deletion_protection`: If the DB instance should have deletion protection enabled (Type: bool)
- `final_db_snapshot_identifier`: The name of your final DB snapshot when this DB instance is deleted (Type: string)
- `skip_final_snapshot`: Determines whether a final DB snapshot is created before the DB instance is deleted (Type: bool)
- `db_parameter_group_name`: Name of the DB parameter group to associate (Type: string)
- `processed_data_bucket`: S3 bucket name for processed data (Type: string)
- `rejected_data_bucket`: S3 bucket name for rejected data (Type: string)
- `log_retention_days`: CloudWatch log retention in days (Type: number)
- `cpu_alarm_threshold`: CPU utilization threshold for CloudWatch alarm (Type: number)
- `connection_alarm_threshold`: Connection count threshold for CloudWatch alarm (Type: number)
- `alarm_actions`: List of ARNs to notify when alarm triggers (Type: list(string))
- `kms_deletion_window`: The waiting period, specified in number of days, after which the KMS key is deleted (Type: number)
- `memory_retention_hours`: Memory store retention period in hours (InfluxDB equivalent) (Type: number)
- `magnetic_retention_days`: Long-term storage retention period in days (Type: number)

**Outputs:**
- `db_instance_identifier`: The InfluxDB instance identifier
- `db_instance_arn`: The ARN of the InfluxDB instance
- `endpoint`: The connection endpoint for the InfluxDB instance
- `port`: The port the InfluxDB instance is listening on
- `db_name`: The name of the database
- `username`: The master username for the database
- `availability_zone`: The availability zone of the instance
- `influxdb_organization`: The InfluxDB organization
- `influxdb_bucket`: The InfluxDB bucket
- `security_group_id`: The ID of the InfluxDB security group
- `lambda_security_group_id`: The ID of the Lambda client security group
- `lambda_role_arn`: ARN of the InfluxDB Lambda IAM role
- `lambda_role_name`: Name of the InfluxDB Lambda IAM role
- `credentials_secret_arn`: ARN of the Secrets Manager secret containing InfluxDB credentials
- `credentials_secret_name`: Name of the Secrets Manager secret containing InfluxDB credentials
- `lambda_log_group_name`: Name of the InfluxDB Lambda CloudWatch log group
- `lambda_log_group_arn`: ARN of the InfluxDB Lambda CloudWatch log group
- `cpu_alarm_arn`: ARN of the CPU utilization CloudWatch alarm
- `connection_alarm_arn`: ARN of the connection count CloudWatch alarm
- `kms_key_id`: The globally unique identifier for the KMS key
- `kms_key_arn`: The Amazon Resource Name (ARN) of the KMS key
- `vpc_subnet_ids`: The VPC subnet IDs used by InfluxDB
- `lambda_environment_variables`: Environment variables for Lambda functions to connect to InfluxDB
- `connection_info`: Connection information for InfluxDB

### Vpc

**Resources:**
- `aws_vpc.main`: aws_vpc resource
- `aws_internet_gateway.main`: aws_internet_gateway resource
- `aws_subnet.public`: aws_subnet resource
- `aws_subnet.private`: aws_subnet resource
- `aws_eip.nat`: aws_eip resource
- `aws_nat_gateway.main`: aws_nat_gateway resource
- `aws_route_table.public`: aws_route_table resource
- `aws_route_table_association.public`: aws_route_table_association resource
- `aws_route_table.private`: aws_route_table resource
- `aws_route_table_association.private`: aws_route_table_association resource
- `aws_vpc_endpoint.s3`: aws_vpc_endpoint resource
- `aws_vpc_endpoint.secretsmanager`: aws_vpc_endpoint resource
- `aws_vpc_endpoint.logs`: aws_vpc_endpoint resource
- `aws_security_group.vpc_endpoints`: aws_security_group resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `vpc_cidr`: CIDR block for VPC (Type: string)
- `public_subnet_cidrs`: CIDR blocks for public subnets (Type: list(string))
- `private_subnet_cidrs`: CIDR blocks for private subnets (Type: list(string))
- `enable_nat_gateway`: Enable NAT Gateway for private subnets (Type: bool)
- `enable_vpc_endpoints`: Enable VPC endpoints for AWS services (Type: bool)

**Outputs:**
- `vpc_id`: ID of the VPC
- `vpc_cidr_block`: CIDR block of the VPC
- `internet_gateway_id`: ID of the Internet Gateway
- `public_subnet_ids`: IDs of the public subnets
- `private_subnet_ids`: IDs of the private subnets
- `public_subnet_cidrs`: CIDR blocks of the public subnets
- `private_subnet_cidrs`: CIDR blocks of the private subnets
- `nat_gateway_ids`: IDs of the NAT Gateways
- `nat_gateway_public_ips`: Public IPs of the NAT Gateways
- `public_route_table_id`: ID of the public route table
- `private_route_table_ids`: IDs of the private route tables
- `vpc_endpoint_s3_id`: ID of the S3 VPC endpoint
- `vpc_endpoint_secretsmanager_id`: ID of the Secrets Manager VPC endpoint
- `vpc_endpoint_logs_id`: ID of the CloudWatch Logs VPC endpoint
- `availability_zones`: List of availability zones used

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
- `aws_lambda_layer_version.shared_utils_layer`: aws_lambda_layer_version resource
- `aws_lambda_function.influxdb_loader`: aws_lambda_function resource
- `aws_security_group.influxdb_lambda_sg`: aws_security_group resource
- `aws_iam_role.influxdb_lambda_role`: aws_iam_role resource
- `aws_iam_role_policy_attachment.influxdb_lambda_basic_execution`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy_attachment.influxdb_lambda_vpc_execution`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy.influxdb_lambda_s3_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.influxdb_lambda_secrets_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.influxdb_lambda_cloudwatch_policy`: aws_iam_role_policy resource
- `aws_s3_bucket_notification.influxdb_loader_trigger`: aws_s3_bucket_notification resource
- `aws_lambda_permission.influxdb_loader_s3_invoke`: aws_lambda_permission resource
- `aws_cloudwatch_log_group.influxdb_loader`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_metric_alarm.influxdb_loader_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_loader_duration`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_loader_connection_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.influxdb_loader_low_success_rate`: aws_cloudwatch_metric_alarm resource
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
- `aws_lambda_function.timeseries_query_processor`: aws_lambda_function resource
- `aws_iam_role.timeseries_lambda_role`: aws_iam_role resource
- `aws_iam_role_policy_attachment.timeseries_lambda_basic_execution`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy_attachment.timeseries_lambda_vpc_execution`: aws_iam_role_policy_attachment resource
- `aws_iam_role_policy.timeseries_lambda_secrets_policy`: aws_iam_role_policy resource
- `aws_iam_role_policy.timeseries_lambda_cloudwatch_policy`: aws_iam_role_policy resource
- `aws_cloudwatch_log_group.timeseries_query_processor`: aws_cloudwatch_log_group resource
- `aws_cloudwatch_metric_alarm.timeseries_processor_errors`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.timeseries_processor_duration`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.timeseries_processor_query_failures`: aws_cloudwatch_metric_alarm resource
- `aws_cloudwatch_metric_alarm.timeseries_processor_high_latency`: aws_cloudwatch_metric_alarm resource

**Variables:**
- `environment`: Environment name (Type: string)
- `project_name`: Project name for resource naming (Type: string)
- `s3_raw_bucket`: S3 raw data bucket name (Type: string)
- `s3_processed_bucket`: S3 processed data bucket name (Type: string)
- `s3_processed_bucket_arn`: S3 processed data bucket ARN (Type: string)
- `influxdb_url`: InfluxDB instance URL (Type: string)
- `influxdb_org`: InfluxDB organization name (Type: string)
- `influxdb_bucket`: InfluxDB bucket name for time series data (Type: string)
- `influxdb_token_secret_name`: AWS Secrets Manager secret name containing InfluxDB token (Type: string)
- `vpc_id`: VPC ID for Lambda functions (Type: string)
- `vpc_cidr`: VPC CIDR block (Type: string)
- `private_subnet_ids`: List of private subnet IDs for Lambda functions (Type: list(string))
- `log_retention_days`: CloudWatch log retention in days (Type: number)
- `sns_topic_arn`: SNS topic ARN for alarms (Type: string)
- `knowledge_base_id`: Amazon Bedrock Knowledge Base ID (Type: string)
- `bedrock_model_arn`: Amazon Bedrock model ARN for RAG generation (Type: string)

**Outputs:**
- `router_lambda_arn`: ARN of the router Lambda function
- `processor_lambda_arn`: ARN of the processor Lambda function
- `api_lambda_arn`: ARN of the API Lambda function
- `function_names`: List of Lambda function names
- `influxdb_loader_arn`: ARN of the InfluxDB loader Lambda function
- `influxdb_loader_name`: Name of the InfluxDB loader Lambda function
- `influxdb_loader_log_group`: CloudWatch log group for InfluxDB loader
- `influxdb_lambda_role_arn`: ARN of the InfluxDB Lambda execution role
- `shared_utils_layer_arn`: ARN of the shared utilities Lambda layer
- `rag_query_processor_arn`: ARN of the RAG query processor Lambda function
- `rag_query_processor_name`: Name of the RAG query processor Lambda function
- `rag_query_processor_log_group`: CloudWatch log group for RAG query processor
- `rag_lambda_role_arn`: ARN of the RAG Lambda execution role
- `router_lambda_name`: Name of the router Lambda function
- `processor_lambda_name`: Name of the processor Lambda function
- `api_lambda_name`: Name of the API Lambda function
- `timeseries_query_processor_arn`: ARN of the timeseries query processor Lambda function
- `timeseries_query_processor_name`: Name of the timeseries query processor Lambda function
- `timeseries_query_processor_log_group`: CloudWatch log group for timeseries query processor
- `timeseries_lambda_role_arn`: ARN of the timeseries Lambda execution role
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

