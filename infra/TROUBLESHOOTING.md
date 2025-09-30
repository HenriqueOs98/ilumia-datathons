# Terraform Deployment Troubleshooting Guide

## Current Issues and Solutions

### 1. AppConfig Hosted Configuration Version Conflict

**Error**: `ConflictException: Hosted configuration version 7 already exists`

**Root Cause**: AppConfig versions are immutable and the same version number was attempted to be created again.

**Solution Applied**:
- Modified the AppConfig module to use timestamp-based descriptions
- Added lifecycle rules to handle version conflicts
- Use `quick-fix.sh` to remove conflicting resources from state

### 2. Knowledge Base OpenSearch Index Missing

**Error**: `ValidationException: no such index [ons-data-platform-dev-kb-energy-index]`

**Root Cause**: Bedrock Knowledge Base expects the OpenSearch index to exist before creation, but the index wasn't being created automatically.

**Solution Applied**:
- Added a Lambda function to create the OpenSearch index with proper vector mappings
- Added proper dependencies to ensure index creation before Knowledge Base creation
- Included AWS Signature V4 authentication for OpenSearch Serverless

## Quick Resolution Steps

### Option 1: Quick Fix (Recommended)
```bash
cd infra
./quick-fix.sh
```

### Option 2: Manual Resolution
```bash
cd infra

# Remove conflicting resources from state
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.feature_flags_initial
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.app_settings_initial
terraform state rm module.knowledge_base.aws_bedrockagent_knowledge_base.ons_knowledge_base

# Apply targeted fixes
terraform apply -target=module.appconfig
terraform apply -target=module.knowledge_base

# Apply full deployment
terraform apply
```

### Option 3: Complete Reset (If needed)
```bash
cd infra

# Destroy and recreate problematic resources
terraform destroy -target=module.appconfig
terraform destroy -target=module.knowledge_base

terraform apply
```

## Prevention Strategies

### 1. AppConfig Version Management
- Use content-based versioning with timestamps
- Implement proper lifecycle management
- Consider using external version management

### 2. Knowledge Base Dependencies
- Ensure OpenSearch collection is fully ready before index creation
- Use proper wait conditions and dependencies
- Implement retry logic for index creation

### 3. General Best Practices
- Always run `terraform plan` before `apply`
- Use targeted applies for complex deployments
- Implement proper resource dependencies
- Use data sources to check resource existence

## Monitoring and Validation

### Check AppConfig Status
```bash
aws appconfig list-applications
aws appconfig list-configuration-profiles --application-id <app-id>
```

### Check Knowledge Base Status
```bash
aws bedrock-agent list-knowledge-bases
aws opensearchserverless list-collections
```

### Check OpenSearch Index
```bash
# Get collection endpoint
aws opensearchserverless get-collection --id <collection-id>

# Check if index exists (requires proper authentication)
curl -X GET "https://<collection-endpoint>/_cat/indices"
```

## Common Error Patterns

### 1. Resource Already Exists
- **Symptom**: 409 Conflict errors
- **Solution**: Remove from state or use import
- **Prevention**: Use lifecycle rules and proper state management

### 2. Dependency Not Ready
- **Symptom**: 404 Not Found errors for dependent resources
- **Solution**: Add explicit dependencies and wait conditions
- **Prevention**: Use proper `depends_on` and data sources

### 3. Authentication Issues
- **Symptom**: 403 Forbidden errors
- **Solution**: Check IAM policies and resource-based policies
- **Prevention**: Use least-privilege principle with comprehensive policies

## Recovery Procedures

### If Deployment Fails Completely
1. Check Terraform state: `terraform state list`
2. Identify problematic resources: `terraform plan`
3. Remove problematic resources from state
4. Apply targeted fixes
5. Run full deployment

### If Resources Are Partially Created
1. Import existing resources: `terraform import`
2. Update configuration to match existing state
3. Apply remaining changes

### If State Is Corrupted
1. Backup current state: `cp terraform.tfstate terraform.tfstate.backup`
2. Use `terraform refresh` to sync state
3. If needed, recreate state from existing resources

## Contact and Support

For additional support:
1. Check AWS CloudTrail for detailed error logs
2. Review Terraform debug logs: `TF_LOG=DEBUG terraform apply`
3. Consult AWS documentation for service-specific requirements
4. Use AWS Support for service-level issues