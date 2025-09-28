# Timestream Decommissioning Guide

This document provides a comprehensive guide for decommissioning Amazon Timestream resources after migrating to Amazon Timestream for InfluxDB.

## Overview

As part of the migration from Amazon Timestream to Timestream for InfluxDB, this guide covers:

1. Data export for compliance archiving
2. Resource cleanup and removal
3. Infrastructure updates
4. Verification steps

## Prerequisites

- [ ] InfluxDB migration is complete and verified
- [ ] All applications are using InfluxDB instead of Timestream
- [ ] AWS CLI configured with appropriate permissions
- [ ] Python 3.8+ with boto3, pandas, and pyarrow packages
- [ ] Terraform access to update infrastructure

## Step 1: Data Export for Compliance

Before removing any Timestream resources, export all data for compliance archiving.

### 1.1 Run Data Export

```bash
# Set environment variables
export ENVIRONMENT=dev  # or staging/prod
export PROJECT_NAME=ons-data-platform
export AWS_REGION=us-east-1

# Run the export script
./scripts/run_timestream_export.sh
```

### 1.2 Verify Export

```bash
# Check exported data
aws s3 ls s3://ons-data-platform-dev-timestream-archive/timestream-archive/ --recursive --human-readable

# Download and verify a sample file
aws s3 cp s3://ons-data-platform-dev-timestream-archive/timestream-archive/ons-data-platform_dev_energy_data/generation_data/year=2024/month=01/generation_data_20240101_20240131.parquet /tmp/
python3 -c "import pandas as pd; df = pd.read_parquet('/tmp/generation_data_20240101_20240131.parquet'); print(f'Records: {len(df)}'); print(df.head())"
```

### 1.3 Export Metadata

The export process creates metadata files containing:
- Export timestamp
- Record counts per table
- File locations
- Data integrity checksums

Access metadata at: `s3://bucket-name/timestream-archive/database-name/export_metadata.json`

## Step 2: Infrastructure Updates

### 2.1 Update Terraform Configuration

The following changes have been made to the Terraform configuration:

#### Removed Resources:
- `infra/modules/timestream/` - Entire module removed
- Timestream database and tables
- Timestream Lambda function (`timestream_loader`)
- Associated IAM roles and policies
- CloudWatch log groups and alarms
- Lambda layer for pandas/pyarrow

#### Updated Files:
- `infra/main.tf` - Removed timestream module reference and CodeDeploy configuration
- `infra/modules/lambda/main.tf` - Removed timestream_loader function
- `infra/modules/lambda/variables.tf` - Removed Timestream variables
- `infra/modules/lambda/outputs.tf` - Removed Timestream outputs

### 2.2 Apply Infrastructure Changes

```bash
cd infra

# Review planned changes
terraform plan

# Apply changes (removes Timestream resources)
terraform apply
```

## Step 3: AWS Resource Cleanup

### 3.1 Automated Cleanup

Use the provided cleanup script to remove any remaining resources:

```bash
# Dry run to see what would be deleted
DRY_RUN=true ./scripts/cleanup_timestream_resources.sh

# Actually delete resources
DRY_RUN=false ./scripts/cleanup_timestream_resources.sh
```

### 3.2 Manual Verification

Verify that all Timestream resources have been removed:

```bash
# Check for databases
aws timestream-write list-databases

# Check for Lambda functions
aws lambda list-functions --query "Functions[?contains(FunctionName, 'timestream')]"

# Check for IAM roles
aws iam list-roles --query "Roles[?contains(RoleName, 'timestream')]"

# Check for CloudWatch log groups
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ons-data-platform-dev-timestream"
```

## Step 4: Source Code Cleanup

### 4.1 Remove Source Code

The following source code has been preserved for reference but can be removed:

```bash
# Archive the timestream_loader source code
tar -czf timestream_loader_archive.tar.gz src/timestream_loader/
mv timestream_loader_archive.tar.gz docs/archives/

# Remove the source directory
rm -rf src/timestream_loader/
```

### 4.2 Update Documentation

- [x] Update API documentation to reflect InfluxDB usage
- [x] Update deployment guides
- [x] Update troubleshooting documentation
- [ ] Update monitoring dashboards
- [ ] Update operational runbooks

## Step 5: Verification and Testing

### 5.1 Functional Testing

Verify that all functionality works with InfluxDB:

```bash
# Run integration tests
python -m pytest tests/integration/ -v

# Test API endpoints
curl -X POST https://api.example.com/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the peak power generation yesterday?"}'

# Verify Knowledge Base integration
curl -X POST https://api.example.com/rag-query \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me energy consumption trends for the last month"}'
```

### 5.2 Performance Verification

Compare performance metrics between Timestream and InfluxDB:

- Query response times
- Data ingestion rates
- Resource utilization
- Cost metrics

### 5.3 Monitoring Verification

Ensure all monitoring and alerting works correctly:

- CloudWatch metrics are being collected
- Alarms are properly configured
- Dashboards show InfluxDB data
- Log aggregation is working

## Step 6: Final Cleanup

### 6.1 Remove Archive Bucket (Optional)

After the retention period, you may remove the archive bucket:

```bash
# List archive contents
aws s3 ls s3://ons-data-platform-dev-timestream-archive/ --recursive

# Remove archive (only after retention period)
# aws s3 rb s3://ons-data-platform-dev-timestream-archive/ --force
```

### 6.2 Update Cost Tracking

- Remove Timestream cost allocation tags
- Update budget alerts
- Verify cost savings from migration

## Rollback Plan

If issues are discovered after decommissioning:

### Emergency Rollback

1. **Stop the cleanup process** if still running
2. **Restore from archive data**:
   ```bash
   # Download archived data
   aws s3 sync s3://archive-bucket/timestream-archive/ /tmp/timestream-restore/
   
   # Recreate Timestream database and tables
   terraform apply -target=module.timestream
   
   # Restore data using custom import script
   python scripts/restore_timestream_data.py
   ```

3. **Revert application configuration** to use Timestream
4. **Update DNS/load balancer** to route to Timestream endpoints

### Data Recovery

Archived data is stored in Parquet format and can be:
- Imported back into Timestream
- Imported into InfluxDB
- Analyzed using pandas/Spark
- Converted to other formats

## Compliance and Audit

### Data Retention

- Archived data follows the same 7-year retention policy
- S3 lifecycle policies automatically transition to cheaper storage
- Versioning is enabled for data integrity

### Audit Trail

The decommissioning process creates audit logs:
- Export metadata with timestamps and checksums
- Terraform state changes
- CloudTrail logs of resource deletions
- Script execution logs

### Compliance Verification

- [ ] Verify all data is archived according to retention policies
- [ ] Confirm data integrity through checksums
- [ ] Document the decommissioning process
- [ ] Update compliance documentation

## Troubleshooting

### Common Issues

1. **Export fails with permission errors**
   - Verify IAM permissions for Timestream and S3
   - Check bucket policies and ACLs

2. **Terraform apply fails**
   - Check for resource dependencies
   - Verify AWS provider version compatibility

3. **Resources not deleted**
   - Check for resource dependencies
   - Verify IAM permissions for deletion
   - Use AWS console to manually remove stuck resources

4. **Data integrity concerns**
   - Compare record counts between export and original
   - Verify timestamp ranges
   - Check for data corruption in Parquet files

### Support Contacts

- Infrastructure Team: [email]
- Data Engineering Team: [email]
- Compliance Team: [email]

## Conclusion

The Timestream decommissioning process ensures:
- ✅ Data is safely archived for compliance
- ✅ All AWS resources are properly cleaned up
- ✅ Infrastructure costs are reduced
- ✅ InfluxDB provides equivalent functionality
- ✅ Audit trail is maintained for compliance

The migration to InfluxDB provides better service availability, enhanced query capabilities, and improved integration with existing tools while maintaining all required functionality.