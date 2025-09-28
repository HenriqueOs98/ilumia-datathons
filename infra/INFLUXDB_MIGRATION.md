# Timestream for InfluxDB Migration Infrastructure

This document describes the infrastructure setup for migrating from Amazon Timestream to Amazon Timestream for InfluxDB.

## Overview

The migration introduces new infrastructure components to support InfluxDB while maintaining compatibility with existing systems. The infrastructure includes:

- **VPC**: Secure network environment for InfluxDB deployment
- **Timestream for InfluxDB**: Managed InfluxDB service
- **Security Groups**: Network access controls
- **IAM Roles**: Least-privilege access for Lambda functions
- **Secrets Manager**: Secure credential storage
- **CloudWatch**: Monitoring and alerting

## Architecture Components

### 1. VPC Infrastructure (`modules/vpc`)

Creates a secure network environment with:
- Public and private subnets across multiple AZs
- NAT Gateways for outbound internet access from private subnets
- VPC endpoints for AWS services (S3, Secrets Manager, CloudWatch Logs)
- Internet Gateway for public subnet access

### 2. InfluxDB Infrastructure (`modules/timestream_influxdb`)

Provisions the managed InfluxDB service with:
- Timestream for InfluxDB database instance
- DB subnet group for multi-AZ deployment
- Security groups for database and Lambda access
- IAM roles and policies for Lambda functions
- Secrets Manager for credential storage
- CloudWatch monitoring and alarms
- KMS encryption for data at rest

## Deployment Guide

### Prerequisites

1. **AWS CLI**: Configured with appropriate credentials
2. **Terraform**: Version >= 1.0
3. **Permissions**: IAM permissions to create VPC, RDS, IAM, and other resources

### Step 1: Configure Variables

Copy the example configuration:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your specific values:
```hcl
# Required variables
influxdb_password = "your-secure-password"
influxdb_token    = "your-influxdb-token"

# Optional customizations
influxdb_instance_class = "db.influx.large"  # Scale as needed
vpc_cidr               = "10.0.0.0/16"       # Adjust if conflicts exist
```

### Step 2: Deploy Infrastructure

Use the deployment script:
```bash
# Initialize Terraform
./deploy-influxdb.sh init

# Review the plan
./deploy-influxdb.sh plan

# Deploy infrastructure
./deploy-influxdb.sh apply
```

Or use Terraform directly:
```bash
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

### Step 3: Verify Deployment

Check the outputs:
```bash
./deploy-influxdb.sh output
```

Key outputs to verify:
- `influxdb_endpoint`: Database connection endpoint
- `vpc_id`: VPC where InfluxDB is deployed
- `influxdb_lambda_role_arn`: IAM role for Lambda functions

## Security Configuration

### Network Security

- **Private Deployment**: InfluxDB is deployed in private subnets
- **Security Groups**: Restrict access to Lambda functions only
- **VPC Endpoints**: Reduce internet traffic for AWS service calls

### Access Control

- **IAM Roles**: Least-privilege access for Lambda functions
- **Secrets Manager**: Secure storage of database credentials
- **KMS Encryption**: Data encrypted at rest and in transit

### Monitoring

- **CloudWatch Alarms**: CPU utilization and connection monitoring
- **Log Groups**: Centralized logging for Lambda functions
- **Custom Metrics**: Application-specific monitoring

## Configuration Reference

### InfluxDB Instance Classes

| Class | vCPUs | Memory | Use Case |
|-------|-------|--------|----------|
| db.influx.medium | 2 | 4 GB | Development/Testing |
| db.influx.large | 4 | 8 GB | Production (Small) |
| db.influx.xlarge | 8 | 16 GB | Production (Medium) |
| db.influx.2xlarge | 16 | 32 GB | Production (Large) |

### Storage Configuration

- **Storage Type**: gp2 (General Purpose SSD) by default
- **Allocated Storage**: 20 GB minimum, scales automatically
- **Backup Retention**: 7 days by default
- **Encryption**: Enabled by default using AWS managed keys

### Network Configuration

Default CIDR blocks:
- **VPC**: 10.0.0.0/16
- **Public Subnets**: 10.0.1.0/24, 10.0.2.0/24
- **Private Subnets**: 10.0.10.0/24, 10.0.20.0/24

## Migration Considerations

### From Timestream to InfluxDB

1. **Data Format**: Convert from Timestream records to InfluxDB line protocol
2. **Query Language**: Change from SQL to InfluxQL/Flux
3. **Client Libraries**: Update Lambda functions to use InfluxDB client
4. **Network Access**: InfluxDB requires VPC configuration

### Backward Compatibility

- API endpoints remain unchanged
- Response formats maintained
- Knowledge Base integration preserved
- Monitoring and alerting continue to work

## Troubleshooting

### Common Issues

1. **VPC CIDR Conflicts**
   - Solution: Adjust `vpc_cidr` variable to avoid conflicts

2. **Insufficient Permissions**
   - Solution: Ensure IAM user has permissions for VPC, RDS, IAM resources

3. **InfluxDB Connection Issues**
   - Check security groups allow Lambda access
   - Verify Lambda functions are in correct subnets
   - Confirm Secrets Manager permissions

### Validation Commands

```bash
# Check VPC configuration
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*ons-data-platform*"

# Verify InfluxDB instance
aws timestream-influxdb describe-db-instances

# Test Lambda connectivity (after Lambda updates)
aws lambda invoke --function-name ons-data-platform-dev-influxdb-test response.json
```

## Cost Optimization

### Instance Sizing
- Start with `db.influx.medium` for development
- Monitor CPU and memory usage to right-size
- Use CloudWatch metrics for scaling decisions

### Storage Optimization
- Monitor storage growth patterns
- Implement appropriate retention policies
- Consider data archival strategies

### Network Costs
- VPC endpoints reduce data transfer costs
- NAT Gateway costs scale with usage
- Consider single NAT Gateway for cost savings in dev environments

## Maintenance

### Regular Tasks

1. **Monitor Alarms**: Review CloudWatch alarms weekly
2. **Update Passwords**: Rotate InfluxDB credentials quarterly
3. **Review Logs**: Check Lambda and InfluxDB logs for errors
4. **Backup Verification**: Test backup restoration procedures

### Updates

- **Terraform**: Keep modules updated for security patches
- **InfluxDB Version**: Plan for minor version upgrades
- **Security Groups**: Review and audit access rules

## Support

For issues with this infrastructure:

1. Check CloudWatch logs for error details
2. Review Terraform state for resource status
3. Validate network connectivity and security groups
4. Consult AWS documentation for service-specific issues

## Next Steps

After infrastructure deployment:

1. **Update Lambda Functions**: Implement InfluxDB client integration
2. **Data Migration**: Plan and execute data migration from Timestream
3. **Testing**: Validate functionality with new infrastructure
4. **Monitoring**: Set up application-specific monitoring
5. **Documentation**: Update operational runbooks