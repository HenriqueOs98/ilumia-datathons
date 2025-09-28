#!/bin/bash

# Timestream Data Export Script
# This script exports all Timestream data to S3 for compliance archiving
# before decommissioning the Timestream resources.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${ENVIRONMENT:-dev}
PROJECT_NAME=${PROJECT_NAME:-ons-data-platform}
AWS_REGION=${AWS_REGION:-us-east-1}

# Derived values
DATABASE_NAME="${PROJECT_NAME}_${ENVIRONMENT}_energy_data"
ARCHIVE_BUCKET_NAME="${PROJECT_NAME}-${ENVIRONMENT}-timestream-archive"

echo -e "${GREEN}=== Timestream Data Export for Compliance ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_NAME"
echo "Database: $DATABASE_NAME"
echo "Archive Bucket: $ARCHIVE_BUCKET_NAME"
echo "Region: $AWS_REGION"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}Error: AWS CLI is not configured or credentials are invalid${NC}"
    exit 1
fi

# Check if the archive bucket exists, create if it doesn't
echo -e "${YELLOW}Checking archive bucket...${NC}"
if ! aws s3 ls "s3://$ARCHIVE_BUCKET_NAME" > /dev/null 2>&1; then
    echo "Archive bucket doesn't exist. Creating..."
    aws s3 mb "s3://$ARCHIVE_BUCKET_NAME" --region "$AWS_REGION"
    
    # Enable versioning for compliance
    aws s3api put-bucket-versioning \
        --bucket "$ARCHIVE_BUCKET_NAME" \
        --versioning-configuration Status=Enabled
    
    # Set lifecycle policy to transition to cheaper storage classes
    cat > /tmp/lifecycle-policy.json << EOF
{
    "Rules": [
        {
            "ID": "TimeStreamArchiveLifecycle",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "timestream-archive/"
            },
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                },
                {
                    "Days": 365,
                    "StorageClass": "DEEP_ARCHIVE"
                }
            ]
        }
    ]
}
EOF
    
    aws s3api put-bucket-lifecycle-configuration \
        --bucket "$ARCHIVE_BUCKET_NAME" \
        --lifecycle-configuration file:///tmp/lifecycle-policy.json
    
    rm /tmp/lifecycle-policy.json
    
    echo -e "${GREEN}Archive bucket created with lifecycle policy${NC}"
else
    echo -e "${GREEN}Archive bucket exists${NC}"
fi

# Check if Timestream database exists
echo -e "${YELLOW}Checking Timestream database...${NC}"
if ! aws timestream-write describe-database --database-name "$DATABASE_NAME" > /dev/null 2>&1; then
    echo -e "${RED}Error: Timestream database '$DATABASE_NAME' not found${NC}"
    echo "Available databases:"
    aws timestream-write list-databases --query 'Databases[].DatabaseName' --output table
    exit 1
fi

echo -e "${GREEN}Timestream database found${NC}"

# Install required Python packages
echo -e "${YELLOW}Installing required Python packages...${NC}"
pip install boto3 pandas pyarrow > /dev/null 2>&1

# Run the export
echo -e "${YELLOW}Starting data export...${NC}"
export TIMESTREAM_DATABASE_NAME="$DATABASE_NAME"
export ARCHIVE_BUCKET_NAME="$ARCHIVE_BUCKET_NAME"
export AWS_REGION="$AWS_REGION"

python3 "$(dirname "$0")/timestream_data_export.py"

export_status=$?

if [ $export_status -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Export Completed Successfully ===${NC}"
    echo "Data has been archived to: s3://$ARCHIVE_BUCKET_NAME/timestream-archive/"
    echo ""
    echo "Next steps:"
    echo "1. Verify the exported data integrity"
    echo "2. Update your applications to use InfluxDB instead of Timestream"
    echo "3. Run the Terraform destroy to remove Timestream resources"
    echo ""
    echo "To verify the export:"
    echo "aws s3 ls s3://$ARCHIVE_BUCKET_NAME/timestream-archive/ --recursive --human-readable"
else
    echo ""
    echo -e "${RED}=== Export Failed ===${NC}"
    echo "Please check the logs above for error details"
    exit 1
fi