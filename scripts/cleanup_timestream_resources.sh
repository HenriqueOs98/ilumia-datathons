#!/bin/bash

# Timestream Resource Cleanup Script
# This script helps clean up any remaining Timestream resources after migration to InfluxDB

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${ENVIRONMENT:-dev}
PROJECT_NAME=${PROJECT_NAME:-ons-data-platform}
AWS_REGION=${AWS_REGION:-us-east-1}
DRY_RUN=${DRY_RUN:-true}

# Derived values
DATABASE_NAME="${PROJECT_NAME}_${ENVIRONMENT}_energy_data"

echo -e "${BLUE}=== Timestream Resource Cleanup ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_NAME"
echo "Database: $DATABASE_NAME"
echo "Region: $AWS_REGION"
echo "Dry Run: $DRY_RUN"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    echo -e "${YELLOW}Running in DRY RUN mode - no resources will be deleted${NC}"
    echo -e "${YELLOW}Set DRY_RUN=false to actually delete resources${NC}"
    echo ""
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}Error: AWS CLI is not configured or credentials are invalid${NC}"
    exit 1
fi

# Function to execute or simulate command
execute_command() {
    local cmd="$1"
    local description="$2"
    
    echo -e "${YELLOW}$description${NC}"
    echo "Command: $cmd"
    
    if [ "$DRY_RUN" = "false" ]; then
        eval "$cmd"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Success${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
        fi
    else
        echo -e "${BLUE}[DRY RUN] Would execute this command${NC}"
    fi
    echo ""
}

# Check if Timestream database exists
echo -e "${YELLOW}Checking for Timestream database...${NC}"
if aws timestream-write describe-database --database-name "$DATABASE_NAME" > /dev/null 2>&1; then
    echo -e "${GREEN}Found Timestream database: $DATABASE_NAME${NC}"
    
    # List tables in the database
    echo "Tables in database:"
    aws timestream-write list-tables --database-name "$DATABASE_NAME" --query 'Tables[].TableName' --output table
    
    # Delete tables first
    tables=$(aws timestream-write list-tables --database-name "$DATABASE_NAME" --query 'Tables[].TableName' --output text)
    
    for table in $tables; do
        execute_command \
            "aws timestream-write delete-table --database-name '$DATABASE_NAME' --table-name '$table'" \
            "Deleting Timestream table: $table"
    done
    
    # Delete the database
    execute_command \
        "aws timestream-write delete-database --database-name '$DATABASE_NAME'" \
        "Deleting Timestream database: $DATABASE_NAME"
    
else
    echo -e "${GREEN}No Timestream database found with name: $DATABASE_NAME${NC}"
fi

# Check for Lambda functions
echo -e "${YELLOW}Checking for Timestream-related Lambda functions...${NC}"
lambda_functions=$(aws lambda list-functions --query "Functions[?contains(FunctionName, 'timestream-loader')].FunctionName" --output text)

if [ -n "$lambda_functions" ]; then
    for func in $lambda_functions; do
        echo "Found Lambda function: $func"
        
        # Delete function
        execute_command \
            "aws lambda delete-function --function-name '$func'" \
            "Deleting Lambda function: $func"
    done
else
    echo -e "${GREEN}No Timestream-related Lambda functions found${NC}"
fi

# Check for CloudWatch Log Groups
echo -e "${YELLOW}Checking for Timestream-related CloudWatch log groups...${NC}"
log_groups=$(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/${PROJECT_NAME}-${ENVIRONMENT}-timestream" --query 'logGroups[].logGroupName' --output text)

if [ -n "$log_groups" ]; then
    for log_group in $log_groups; do
        echo "Found log group: $log_group"
        
        execute_command \
            "aws logs delete-log-group --log-group-name '$log_group'" \
            "Deleting CloudWatch log group: $log_group"
    done
else
    echo -e "${GREEN}No Timestream-related log groups found${NC}"
fi

# Check for IAM roles
echo -e "${YELLOW}Checking for Timestream-related IAM roles...${NC}"
iam_roles=$(aws iam list-roles --query "Roles[?contains(RoleName, 'timestream-lambda-role')].RoleName" --output text)

if [ -n "$iam_roles" ]; then
    for role in $iam_roles; do
        echo "Found IAM role: $role"
        
        # List and detach policies
        attached_policies=$(aws iam list-attached-role-policies --role-name "$role" --query 'AttachedPolicies[].PolicyArn' --output text)
        for policy_arn in $attached_policies; do
            execute_command \
                "aws iam detach-role-policy --role-name '$role' --policy-arn '$policy_arn'" \
                "Detaching policy $policy_arn from role $role"
        done
        
        # List and delete inline policies
        inline_policies=$(aws iam list-role-policies --role-name "$role" --query 'PolicyNames' --output text)
        for policy_name in $inline_policies; do
            execute_command \
                "aws iam delete-role-policy --role-name '$role' --policy-name '$policy_name'" \
                "Deleting inline policy $policy_name from role $role"
        done
        
        # Delete the role
        execute_command \
            "aws iam delete-role --role-name '$role'" \
            "Deleting IAM role: $role"
    done
else
    echo -e "${GREEN}No Timestream-related IAM roles found${NC}"
fi

# Check for IAM policies
echo -e "${YELLOW}Checking for Timestream-related IAM policies...${NC}"
iam_policies=$(aws iam list-policies --scope Local --query "Policies[?contains(PolicyName, 'timestream-lambda-policy')].Arn" --output text)

if [ -n "$iam_policies" ]; then
    for policy_arn in $iam_policies; do
        echo "Found IAM policy: $policy_arn"
        
        # List policy versions
        versions=$(aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?!IsDefaultVersion].VersionId' --output text)
        
        # Delete non-default versions
        for version in $versions; do
            execute_command \
                "aws iam delete-policy-version --policy-arn '$policy_arn' --version-id '$version'" \
                "Deleting policy version $version"
        done
        
        # Delete the policy
        execute_command \
            "aws iam delete-policy --policy-arn '$policy_arn'" \
            "Deleting IAM policy: $policy_arn"
    done
else
    echo -e "${GREEN}No Timestream-related IAM policies found${NC}"
fi

# Check for CloudWatch Alarms
echo -e "${YELLOW}Checking for Timestream-related CloudWatch alarms...${NC}"
alarms=$(aws cloudwatch describe-alarms --alarm-name-prefix "${PROJECT_NAME}-${ENVIRONMENT}-timestream" --query 'MetricAlarms[].AlarmName' --output text)

if [ -n "$alarms" ]; then
    for alarm in $alarms; do
        echo "Found CloudWatch alarm: $alarm"
        
        execute_command \
            "aws cloudwatch delete-alarms --alarm-names '$alarm'" \
            "Deleting CloudWatch alarm: $alarm"
    done
else
    echo -e "${GREEN}No Timestream-related CloudWatch alarms found${NC}"
fi

echo -e "${BLUE}=== Cleanup Summary ===${NC}"
if [ "$DRY_RUN" = "true" ]; then
    echo -e "${YELLOW}This was a dry run. No resources were actually deleted.${NC}"
    echo -e "${YELLOW}To perform the actual cleanup, run: DRY_RUN=false $0${NC}"
else
    echo -e "${GREEN}Cleanup completed!${NC}"
    echo ""
    echo "Remaining steps:"
    echo "1. Run 'terraform plan' to verify no Timestream resources remain"
    echo "2. Run 'terraform apply' to update the infrastructure state"
    echo "3. Verify that InfluxDB is handling all time series operations"
fi

echo ""
echo -e "${BLUE}Note: This script only cleans up AWS resources.${NC}"
echo -e "${BLUE}You may also want to:${NC}"
echo "- Remove the timestream_loader source code directory"
echo "- Update any documentation that references Timestream"
echo "- Update monitoring dashboards to use InfluxDB metrics"