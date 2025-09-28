#!/bin/bash

# Knowledge Base Integration Tests Runner
# This script runs tests to verify Knowledge Base setup and functionality

set -e

echo "🚀 Starting Knowledge Base Integration Tests"
echo "=============================================="

# Check if required environment variables are set
if [ -z "$AWS_REGION" ]; then
    export AWS_REGION="us-east-1"
    echo "⚠️  AWS_REGION not set, using default: $AWS_REGION"
fi

if [ -z "$PROJECT_NAME" ]; then
    export PROJECT_NAME="ons-data-platform"
    echo "⚠️  PROJECT_NAME not set, using default: $PROJECT_NAME"
fi

if [ -z "$ENVIRONMENT" ]; then
    export ENVIRONMENT="dev"
    echo "⚠️  ENVIRONMENT not set, using default: $ENVIRONMENT"
fi

echo "Configuration:"
echo "  AWS Region: $AWS_REGION"
echo "  Project: $PROJECT_NAME"
echo "  Environment: $ENVIRONMENT"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured or no valid credentials found"
    echo "Please run 'aws configure' or set AWS credentials"
    exit 1
fi

echo "✅ AWS credentials validated"

# Check if required Python packages are available
echo "📦 Checking Python dependencies..."

if ! python3 -c "import boto3" 2>/dev/null; then
    echo "Installing boto3..."
    pip3 install boto3
fi

if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Installing pytest..."
    pip3 install pytest
fi

echo "✅ Python dependencies ready"
echo ""

# Run the knowledge base tests
echo "🧪 Running Knowledge Base tests..."
python3 test_knowledge_base.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 All Knowledge Base tests completed successfully!"
    echo "The Knowledge Base infrastructure is properly configured and functional."
else
    echo ""
    echo "❌ Some Knowledge Base tests failed."
    echo "Please check the output above for details."
    exit 1
fi