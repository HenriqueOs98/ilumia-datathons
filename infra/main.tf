terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "ONS Data Platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Provider for cross-region replication
provider "aws" {
  alias  = "replica"
  region = var.replication_region

  default_tags {
    tags = {
      Project     = "ONS Data Platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Purpose     = "Replica"
    }
  }
}

# Generate a random password for InfluxDB if not provided
resource "random_password" "influxdb" {
  length  = 16
  special = true
}

# VPC Infrastructure
module "vpc" {
  source = "./modules/vpc"

  environment          = var.environment
  project_name         = var.project_name
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
  enable_vpc_endpoints = var.enable_vpc_endpoints
}

# S3 Buckets
module "s3_buckets" {
  source = "./modules/s3"

  environment                     = var.environment
  project_name                    = var.project_name
  enable_cross_region_replication = var.enable_cross_region_replication
  replication_destination_region  = var.replication_region
  raw_data_retention_days         = var.raw_data_retention_days
  processed_data_retention_days   = var.processed_data_retention_days

  providers = {
    aws.replica = aws.replica
  }
}

# Timestream for InfluxDB
locals {
  influxdb_password = var.influxdb_password == null ? random_password.influxdb.result : var.influxdb_password
}

module "timestream_influxdb" {
  source = "./modules/timestream_influxdb"

  environment             = var.environment
  project_name            = var.project_name
  vpc_id                  = module.vpc.vpc_id
  subnet_ids              = module.vpc.private_subnet_ids
  password                = local.influxdb_password
  influxdb_token          = var.influxdb_token
  db_instance_class       = var.influxdb_instance_class
  allocated_storage       = var.influxdb_allocated_storage
  backup_retention_period = var.influxdb_backup_retention_period
  influxdb_org            = var.influxdb_org
  influxdb_bucket         = var.influxdb_bucket
  processed_data_bucket   = module.s3_buckets.processed_bucket_name
  rejected_data_bucket    = module.s3_buckets.failed_bucket_name
  log_retention_days      = var.log_retention_days
  alarm_actions           = [module.monitoring.sns_topic_arn]
}

# Lambda Functions
module "lambda_functions" {
  source = "./modules/lambda"

  environment                = var.environment
  project_name               = var.project_name
  s3_raw_bucket              = module.s3_buckets.raw_bucket_name
  s3_processed_bucket        = module.s3_buckets.processed_bucket_name
  s3_processed_bucket_arn    = module.s3_buckets.processed_bucket_arn
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  vpc_cidr                   = var.vpc_cidr
  influxdb_url               = module.timestream_influxdb.endpoint
  influxdb_org               = var.influxdb_org
  influxdb_bucket            = var.influxdb_bucket
  influxdb_token_secret_name = var.influxdb_token_secret_name
  log_retention_days         = var.log_retention_days
  sns_topic_arn              = module.monitoring.sns_topic_arn
  knowledge_base_id          = module.knowledge_base.knowledge_base_id
  bedrock_model_arn          = var.bedrock_model_arn
}

# Step Functions
module "step_functions" {
  source = "./modules/step_functions"

  environment          = var.environment
  project_name         = var.project_name
  lambda_router_arn    = module.lambda_functions.router_lambda_arn
  lambda_processor_arn = module.lambda_functions.processor_lambda_arn
}

# EventBridge
module "eventbridge" {
  source = "./modules/eventbridge"

  environment       = var.environment
  project_name      = var.project_name
  s3_raw_bucket     = module.s3_buckets.raw_bucket_name
  step_function_arn = module.step_functions.state_machine_arn
}

# API Gateway
module "api_gateway" {
  source = "./modules/api_gateway"

  environment          = var.environment
  project_name         = var.project_name
  lambda_api_arn       = module.lambda_functions.rag_query_processor_arn
  lambda_function_name = module.lambda_functions.rag_query_processor_name
}

# Timestream - Temporarily disabled due to access requirements
# module "timestream" {
#   source = "./modules/timestream"
# 
#   environment           = var.environment
#   project_name          = var.project_name
#   processed_data_bucket = module.s3_buckets.processed_bucket_name
#   rejected_data_bucket  = module.s3_buckets.failed_bucket_name
#   log_retention_days    = var.log_retention_days
# }

# Knowledge Base
module "knowledge_base" {
  source = "./modules/knowledge_base"

  environment         = var.environment
  project_name        = var.project_name
  s3_processed_bucket = module.s3_buckets.processed_bucket_name
}

# Monitoring
module "monitoring" {
  source = "./modules/monitoring"

  environment        = var.environment
  project_name       = var.project_name
  api_gateway_id     = module.api_gateway.api_id
  step_functions_arn = module.step_functions.state_machine_arn
}

# CodeDeploy for Blue-Green Deployments
module "codedeploy" {
  source = "./modules/codedeploy"

  project_name = var.project_name
  lambda_functions = {
    lambda_router = {
      function_name = module.lambda_functions.router_lambda_name
      alias_name    = "live"
    }
    structured_data_processor = {
      function_name = module.lambda_functions.processor_lambda_name
      alias_name    = "live"
    }
    rag_query_processor = {
      function_name = module.lambda_functions.api_lambda_name
      alias_name    = "live"
    }

  }
  error_rate_threshold   = var.deployment_error_threshold
  duration_threshold     = var.deployment_duration_threshold
  deployment_config_name = var.deployment_config_name
  sns_email_endpoint     = var.deployment_notification_email

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# AppConfig for Feature Flags
module "appconfig" {
  source = "./modules/appconfig"

  project_name          = var.project_name
  development_alarm_arn = module.monitoring.development_alarm_arn
  production_alarm_arn  = module.monitoring.production_alarm_arn

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}