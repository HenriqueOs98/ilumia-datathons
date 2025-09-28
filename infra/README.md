# Infrastructure

This directory contains the Terraform infrastructure code for the ONS Data Platform, implementing a serverless, event-driven architecture on AWS.

## 🏗️ Architecture Overview

The infrastructure is organized into modular components that work together to provide:

- **Data Ingestion**: S3 + EventBridge for automated file processing
- **Processing**: Lambda functions + AWS Batch for different data types
- **Storage**: S3 Data Lake + Amazon Timestream for time series
- **AI/ML**: Amazon Bedrock + Knowledge Bases for intelligent querying
- **API**: API Gateway + Lambda for REST endpoints
- **Monitoring**: CloudWatch + SNS for comprehensive observability
- **Deployment**: CodeDeploy + AppConfig for blue-green deployments

## 📁 Structure

```
infra/
├── modules/                    # Reusable Terraform modules
│   ├── api_gateway/           # API Gateway configuration
│   ├── appconfig/             # Feature flags and configuration
│   ├── codedeploy/            # Blue-green deployment setup
│   ├── eventbridge/           # Event routing
│   ├── knowledge_base/        # RAG system components
│   ├── lambda/                # Lambda functions
│   ├── monitoring/            # CloudWatch and alerting
│   ├── s3/                    # Data lake storage
│   ├── step_functions/        # Workflow orchestration
│   └── timestream/            # Time series database
├── environments/              # Environment-specific configurations
│   ├── dev.tfvars            # Development environment
│   ├── staging.tfvars        # Staging environment
│   └── prod.tfvars           # Production environment
├── main.tf                   # Root module configuration
├── variables.tf              # Input variables
├── outputs.tf                # Output values
├── backend.tf                # Remote state configuration
└── setup-remote-state.tf     # Initial state setup
```

## 🚀 Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- Access to AWS account with necessary permissions

### 1. Setup Remote State (First Time Only)

```bash
# Initialize and create remote state resources
terraform init
terraform apply -target=aws_s3_bucket.terraform_state -target=aws_dynamodb_table.terraform_locks
```

### 2. Deploy Infrastructure

```bash
# Initialize with remote backend
terraform init

# Plan deployment for specific environment
terraform plan -var-file="environments/dev.tfvars"

# Apply changes
terraform apply -var-file="environments/dev.tfvars"
```

### 3. Verify Deployment

```bash
# Check outputs
terraform output

# Test API endpoint
curl -X GET "$(terraform output -raw api_gateway_url)/health"
```

## 🔧 Module Documentation

### Core Modules

#### S3 Module (`modules/s3/`)
- **Purpose**: Data lake storage with lifecycle policies
- **Resources**: Raw, processed, and failed data buckets
- **Features**: Cross-region replication, encryption, access logging

#### Lambda Module (`modules/lambda/`)
- **Purpose**: Serverless compute for data processing
- **Resources**: Router, processor, API, and loader functions
- **Features**: Auto-scaling, monitoring, error handling

#### API Gateway Module (`modules/api_gateway/`)
- **Purpose**: REST API for external access
- **Resources**: API Gateway, stages, usage plans
- **Features**: Authentication, throttling, monitoring

#### Timestream Module (`modules/timestream/`)
- **Purpose**: Time series database for energy data
- **Resources**: Database, tables, IAM roles
- **Features**: Automatic scaling, retention policies

#### Knowledge Base Module (`modules/knowledge_base/`)
- **Purpose**: RAG system for intelligent querying
- **Resources**: Knowledge Base, OpenSearch collection
- **Features**: Vector embeddings, semantic search

### Deployment Modules

#### CodeDeploy Module (`modules/codedeploy/`)
- **Purpose**: Blue-green deployments for Lambda functions
- **Resources**: Applications, deployment groups, alarms
- **Features**: Canary releases, automatic rollback

#### AppConfig Module (`modules/appconfig/`)
- **Purpose**: Feature flags and configuration management
- **Resources**: Applications, environments, profiles
- **Features**: Gradual rollouts, monitoring integration

### Monitoring Module (`modules/monitoring/`)
- **Purpose**: Comprehensive observability
- **Resources**: CloudWatch alarms, SNS topics, dashboards
- **Features**: Real-time alerts, cost monitoring

## 🌍 Environment Management

### Development Environment

```bash
# Deploy to development
terraform workspace select dev || terraform workspace new dev
terraform apply -var-file="environments/dev.tfvars"
```

### Production Environment

```bash
# Deploy to production
terraform workspace select prod || terraform workspace new prod
terraform apply -var-file="environments/prod.tfvars"
```

## 🔒 Security Configuration

### IAM Policies
All modules follow the principle of least privilege with specific IAM roles and policies.

### Encryption
- **S3**: AES-256 encryption at rest
- **Lambda**: Environment variables encrypted with KMS
- **Timestream**: Encryption in transit and at rest
- **API Gateway**: TLS 1.2+ for all communications

## 📊 Monitoring and Alerting

### Key Metrics
- **Lambda**: Error rate, duration, throttles
- **API Gateway**: Latency, 4xx/5xx errors
- **S3**: Request metrics, storage utilization
- **Timestream**: Write/read throughput, errors

## 💰 Cost Optimization

### Resource Tagging
All resources are tagged for cost tracking and management.

### Lifecycle Policies
Automatic data archiving and cleanup policies to optimize storage costs.

## 🧪 Testing

```bash
# Format code
terraform fmt -recursive

# Validate configuration
terraform validate

# Security scanning
checkov -d . --framework terraform
```

---

**Maintained by**: Platform Engineering Team