#!/bin/bash

# Setup Terraform remote state infrastructure
# This script creates the S3 bucket and DynamoDB table needed for Terraform state management

set -e

# Configuration
AWS_REGION=${AWS_REGION:-"us-east-1"}
ENVIRONMENTS=("dev" "staging" "prod")

echo "Setting up Terraform state infrastructure in region: $AWS_REGION"

for ENV in "${ENVIRONMENTS[@]}"; do
    echo "Setting up state infrastructure for environment: $ENV"
    
    # S3 bucket for state
    BUCKET_NAME="ons-data-platform-terraform-state-$ENV"
    
    # Check if bucket exists
    if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
        echo "✅ S3 bucket $BUCKET_NAME already exists"
    else
        echo "Creating S3 bucket: $BUCKET_NAME"
        
        if [ "$AWS_REGION" = "us-east-1" ]; then
            # us-east-1 doesn't need LocationConstraint
            aws s3api create-bucket --bucket "$BUCKET_NAME"
        else
            aws s3api create-bucket \
                --bucket "$BUCKET_NAME" \
                --region "$AWS_REGION" \
                --create-bucket-configuration LocationConstraint="$AWS_REGION"
        fi
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "$BUCKET_NAME" \
            --versioning-configuration Status=Enabled
        
        # Enable server-side encryption
        aws s3api put-bucket-encryption \
            --bucket "$BUCKET_NAME" \
            --server-side-encryption-configuration '{
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }'
        
        # Block public access
        aws s3api put-public-access-block \
            --bucket "$BUCKET_NAME" \
            --public-access-block-configuration \
            BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
        
        echo "✅ Created and configured S3 bucket: $BUCKET_NAME"
    fi
    
    # DynamoDB table for state locking
    TABLE_NAME="ons-data-platform-terraform-locks-$ENV"
    
    # Check if table exists
    if aws dynamodb describe-table --table-name "$TABLE_NAME" 2>/dev/null >/dev/null; then
        echo "✅ DynamoDB table $TABLE_NAME already exists"
    else
        echo "Creating DynamoDB table: $TABLE_NAME"
        
        aws dynamodb create-table \
            --table-name "$TABLE_NAME" \
            --attribute-definitions AttributeName=LockID,AttributeType=S \
            --key-schema AttributeName=LockID,KeyType=HASH \
            --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
            --region "$AWS_REGION"
        
        # Wait for table to be active
        echo "Waiting for DynamoDB table to be active..."
        aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$AWS_REGION"
        
        echo "✅ Created DynamoDB table: $TABLE_NAME"
    fi
    
    echo "State infrastructure for $ENV environment is ready!"
    echo ""
done

echo "🎉 All Terraform state infrastructure is set up!"
echo ""
echo "You can now run terraform init with the following backend configuration:"
echo ""
for ENV in "${ENVIRONMENTS[@]}"; do
    echo "For $ENV environment:"
    echo "terraform init \\"
    echo "  -backend-config=\"bucket=ons-data-platform-terraform-state-$ENV\" \\"
    echo "  -backend-config=\"key=terraform.tfstate\" \\"
    echo "  -backend-config=\"region=$AWS_REGION\" \\"
    echo "  -backend-config=\"dynamodb_table=ons-data-platform-terraform-locks-$ENV\""
    echo ""
done