#!/bin/bash

# Quick fix for immediate deployment issues

set -e

echo "🚨 Quick fix for deployment errors..."

cd "$(dirname "$0")"

echo "1️⃣ Removing conflicting AppConfig resources from Terraform state..."

# Remove all AppConfig hosted configuration versions and their random IDs
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.feature_flags_initial 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.app_settings_initial 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.influxdb_migration_flags 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.aws_appconfig_hosted_configuration_version.traffic_switch_settings 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.aws_appconfig_deployment.development_traffic_switch 2>/dev/null || echo "Resource not in state"

# Remove random ID resources
terraform state rm module.appconfig.random_id.feature_flags_version 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.random_id.app_settings_version 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.random_id.migration_flags_version 2>/dev/null || echo "Resource not in state"
terraform state rm module.appconfig.random_id.traffic_switch_version 2>/dev/null || echo "Resource not in state"

echo "2️⃣ Removing Knowledge Base from state to allow recreation with proper dependencies..."
terraform state rm module.knowledge_base.aws_bedrockagent_knowledge_base.ons_knowledge_base 2>/dev/null || echo "Resource not in state"

echo "3️⃣ Applying targeted fixes..."

# Apply only the specific modules that were fixed
terraform apply -target=module.appconfig -auto-approve
terraform apply -target=module.knowledge_base -auto-approve

echo "✅ Quick fixes applied! Now run full deployment:"
echo "terraform apply"