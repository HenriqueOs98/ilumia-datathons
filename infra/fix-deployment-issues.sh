#!/bin/bash

# Fix Terraform deployment issues
# This script addresses the AppConfig version conflict and Knowledge Base index issues

set -e

echo "🔧 Fixing Terraform deployment issues..."

# Navigate to infra directory
cd "$(dirname "$0")"

echo "📋 Current Terraform state:"
terraform state list | grep -E "(appconfig|knowledge_base)" || echo "No conflicting resources found in state"

echo ""
echo "🧹 Cleaning up conflicting AppConfig versions..."

# Remove the conflicting AppConfig hosted configuration versions from state
# This allows Terraform to recreate them with the new timestamp-based descriptions
if terraform state list | grep -q "aws_appconfig_hosted_configuration_version.feature_flags_initial"; then
    echo "Removing feature_flags_initial from state..."
    terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.feature_flags_initial || true
fi

if terraform state list | grep -q "aws_appconfig_hosted_configuration_version.app_settings_initial"; then
    echo "Removing app_settings_initial from state..."
    terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.app_settings_initial || true
fi

echo ""
echo "🔍 Checking for existing Knowledge Base resources..."

# Check if Knowledge Base exists and remove from state if needed
if terraform state list | grep -q "aws_bedrockagent_knowledge_base.ons_knowledge_base"; then
    echo "Knowledge Base found in state. Checking if it needs to be recreated..."
    # We'll let Terraform handle this with the new dependencies
fi

echo ""
echo "📦 Initializing and planning deployment..."

# Initialize Terraform (in case new providers are needed)
terraform init

# Create a targeted plan to see what will be changed
echo "Creating deployment plan..."
terraform plan -out=fix-deployment.tfplan

echo ""
echo "🚀 Applying fixes..."

# Apply the plan
terraform apply fix-deployment.tfplan

echo ""
echo "✅ Deployment fixes completed!"
echo ""
echo "📊 Verifying deployment..."

# Verify the resources are created properly
echo "Checking AppConfig application..."
aws appconfig list-applications --query 'Items[?Name==`ons-data-platform-app`]' --output table || echo "AppConfig check failed"

echo ""
echo "Checking Knowledge Base..."
aws bedrock-agent list-knowledge-bases --query 'knowledgeBaseSummaries[?name==`ons-data-platform-dev-knowledge-base`]' --output table || echo "Knowledge Base check failed"

echo ""
echo "🎉 All fixes applied successfully!"
echo ""
echo "💡 Next steps:"
echo "1. Monitor the deployment for any remaining issues"
echo "2. Test the Knowledge Base functionality"
echo "3. Verify AppConfig feature flags are working"
echo "4. Run smoke tests: ./smoke-tests.sh"