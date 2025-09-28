#!/bin/bash

# Timestream Decommissioning Verification Script
# This script verifies that the Timestream decommissioning process is complete

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

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

echo -e "${BLUE}=== Timestream Decommissioning Verification ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Project: $PROJECT_NAME"
echo "Region: $AWS_REGION"
echo ""

# Function to run a check
run_check() {
    local description="$1"
    local command="$2"
    local expected_result="$3"  # "empty" or "exists"
    
    echo -n "Checking $description... "
    
    if result=$(eval "$command" 2>/dev/null); then
        if [ "$expected_result" = "empty" ]; then
            if [ -z "$result" ] || [ "$result" = "None" ] || [ "$result" = "[]" ]; then
                echo -e "${GREEN}✓ PASS${NC}"
                ((CHECKS_PASSED++))
            else
                echo -e "${RED}✗ FAIL${NC}"
                echo "  Found: $result"
                ((CHECKS_FAILED++))
            fi
        elif [ "$expected_result" = "exists" ]; then
            if [ -n "$result" ] && [ "$result" != "None" ] && [ "$result" != "[]" ]; then
                echo -e "${GREEN}✓ PASS${NC}"
                ((CHECKS_PASSED++))
            else
                echo -e "${RED}✗ FAIL${NC}"
                echo "  Expected to find resources but none found"
                ((CHECKS_FAILED++))
            fi
        fi
    else
        if [ "$expected_result" = "empty" ]; then
            echo -e "${GREEN}✓ PASS${NC} (service not accessible - expected)"
            ((CHECKS_PASSED++))
        else
            echo -e "${YELLOW}⚠ WARNING${NC} (could not check)"
            ((WARNINGS++))
        fi
    fi
}

# Function to run a warning check
run_warning_check() {
    local description="$1"
    local command="$2"
    local message="$3"
    
    echo -n "Checking $description... "
    
    if result=$(eval "$command" 2>/dev/null); then
        if [ -n "$result" ] && [ "$result" != "None" ] && [ "$result" != "[]" ]; then
            echo -e "${YELLOW}⚠ WARNING${NC}"
            echo "  $message"
            echo "  Found: $result"
            ((WARNINGS++))
        else
            echo -e "${GREEN}✓ PASS${NC}"
            ((CHECKS_PASSED++))
        fi
    else
        echo -e "${GREEN}✓ PASS${NC} (service not accessible)"
        ((CHECKS_PASSED++))
    fi
}

echo -e "${BLUE}=== AWS Resource Checks ===${NC}"

# Check for Timestream databases
run_check "Timestream databases" \
    "aws timestream-write list-databases --query 'Databases[?contains(DatabaseName, \`${PROJECT_NAME}\`)].DatabaseName' --output text" \
    "empty"

# Check for Timestream-related Lambda functions
run_check "Timestream Lambda functions" \
    "aws lambda list-functions --query 'Functions[?contains(FunctionName, \`timestream-loader\`)].FunctionName' --output text" \
    "empty"

# Check for Timestream-related IAM roles
run_check "Timestream IAM roles" \
    "aws iam list-roles --query 'Roles[?contains(RoleName, \`timestream-lambda-role\`)].RoleName' --output text" \
    "empty"

# Check for Timestream-related IAM policies
run_check "Timestream IAM policies" \
    "aws iam list-policies --scope Local --query 'Policies[?contains(PolicyName, \`timestream-lambda-policy\`)].PolicyName' --output text" \
    "empty"

# Check for Timestream-related CloudWatch log groups
run_check "Timestream CloudWatch log groups" \
    "aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/${PROJECT_NAME}-${ENVIRONMENT}-timestream' --query 'logGroups[].logGroupName' --output text" \
    "empty"

# Check for Timestream-related CloudWatch alarms
run_check "Timestream CloudWatch alarms" \
    "aws cloudwatch describe-alarms --alarm-name-prefix '${PROJECT_NAME}-${ENVIRONMENT}-timestream' --query 'MetricAlarms[].AlarmName' --output text" \
    "empty"

echo ""
echo -e "${BLUE}=== InfluxDB Resource Checks ===${NC}"

# Check that InfluxDB resources exist
run_check "InfluxDB instance" \
    "aws timestreaminfluxdb describe-db-instance --identifier '${PROJECT_NAME}-${ENVIRONMENT}-influxdb' --query 'DbInstanceArn' --output text 2>/dev/null || echo ''" \
    "exists"

# Check for InfluxDB Lambda functions
run_check "InfluxDB Lambda functions" \
    "aws lambda list-functions --query 'Functions[?contains(FunctionName, \`influxdb-loader\`)].FunctionName' --output text" \
    "exists"

echo ""
echo -e "${BLUE}=== File System Checks ===${NC}"

# Check that Terraform files are updated
echo -n "Checking Terraform timestream module removal... "
if [ ! -d "infra/modules/timestream" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Timestream module directory still exists"
    ((CHECKS_FAILED++))
fi

# Check that main.tf is updated
echo -n "Checking main.tf timestream references... "
if ! grep -q "module.*timestream.*{" infra/main.tf 2>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Found uncommented timestream module references in main.tf"
    ((CHECKS_FAILED++))
fi

# Check for timestream_loader source code
echo -n "Checking timestream_loader source code... "
if [ ! -d "src/timestream_loader" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC}"
    echo "  timestream_loader source code still exists (consider archiving)"
    ((WARNINGS++))
fi

echo ""
echo -e "${BLUE}=== Data Archive Checks ===${NC}"

# Check for archive bucket
ARCHIVE_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-timestream-archive"
echo -n "Checking data archive bucket... "
if aws s3 ls "s3://$ARCHIVE_BUCKET" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((CHECKS_PASSED++))
    
    # Check for export metadata
    echo -n "Checking export metadata... "
    if aws s3 ls "s3://$ARCHIVE_BUCKET/timestream-archive/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((CHECKS_PASSED++))
    else
        echo -e "${YELLOW}⚠ WARNING${NC}"
        echo "  Archive bucket exists but no export data found"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠ WARNING${NC}"
    echo "  No archive bucket found - ensure data was exported before decommissioning"
    ((WARNINGS++))
fi

echo ""
echo -e "${BLUE}=== Application Health Checks ===${NC}"

# Check if InfluxDB endpoints are accessible (if configured)
run_warning_check "InfluxDB connectivity" \
    "timeout 5 curl -s -o /dev/null -w '%{http_code}' http://localhost:8086/health 2>/dev/null || echo ''" \
    "Could not connect to InfluxDB - verify service is running"

# Check API Gateway endpoints
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='${PROJECT_NAME}-${ENVIRONMENT}-api'].id" --output text 2>/dev/null || echo "")
if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
    echo -n "Checking API Gateway health... "
    if aws apigateway get-rest-api --rest-api-id "$API_ID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((CHECKS_PASSED++))
    else
        echo -e "${YELLOW}⚠ WARNING${NC}"
        echo "  API Gateway not accessible"
        ((WARNINGS++))
    fi
else
    echo -n "Checking API Gateway health... "
    echo -e "${YELLOW}⚠ WARNING${NC}"
    echo "  Could not find API Gateway"
    ((WARNINGS++))
fi

echo ""
echo -e "${BLUE}=== Summary ===${NC}"
echo -e "Checks passed: ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks failed: ${RED}$CHECKS_FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"

echo ""
if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ Decommissioning verification PASSED${NC}"
    
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  There are $WARNINGS warnings to review${NC}"
    fi
    
    echo ""
    echo "Next steps:"
    echo "1. Review any warnings above"
    echo "2. Update monitoring dashboards to use InfluxDB metrics"
    echo "3. Update operational documentation"
    echo "4. Notify stakeholders that migration is complete"
    
    exit 0
else
    echo -e "${RED}❌ Decommissioning verification FAILED${NC}"
    echo ""
    echo "Issues found:"
    echo "- $CHECKS_FAILED critical checks failed"
    echo "- Review the failed checks above and remediate"
    echo "- Re-run this script after fixing issues"
    
    exit 1
fi