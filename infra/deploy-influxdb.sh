#!/bin/bash

# Deploy InfluxDB Infrastructure Script
# This script deploys the Timestream for InfluxDB infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_status "Prerequisites check passed."
}

# Initialize Terraform
init_terraform() {
    print_status "Initializing Terraform..."
    terraform init
    
    if [ $? -eq 0 ]; then
        print_status "Terraform initialization completed successfully."
    else
        print_error "Terraform initialization failed."
        exit 1
    fi
}

# Validate Terraform configuration
validate_terraform() {
    print_status "Validating Terraform configuration..."
    terraform validate
    
    if [ $? -eq 0 ]; then
        print_status "Terraform validation passed."
    else
        print_error "Terraform validation failed."
        exit 1
    fi
}

# Plan Terraform deployment
plan_terraform() {
    print_status "Creating Terraform execution plan..."
    terraform plan -var-file="terraform.tfvars" -out=tfplan
    
    if [ $? -eq 0 ]; then
        print_status "Terraform plan created successfully."
        print_warning "Please review the plan above before proceeding."
        read -p "Do you want to continue with the deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled by user."
            exit 0
        fi
    else
        print_error "Terraform plan failed."
        exit 1
    fi
}

# Apply Terraform configuration
apply_terraform() {
    print_status "Applying Terraform configuration..."
    terraform apply tfplan
    
    if [ $? -eq 0 ]; then
        print_status "Terraform deployment completed successfully."
    else
        print_error "Terraform deployment failed."
        exit 1
    fi
}

# Generate outputs
show_outputs() {
    print_status "Deployment outputs:"
    terraform output
}

# Main deployment function
main() {
    print_status "Starting InfluxDB infrastructure deployment..."
    
    # Check if terraform.tfvars exists
    if [ ! -f "terraform.tfvars" ]; then
        print_error "terraform.tfvars file not found."
        print_status "Please copy terraform.tfvars.example to terraform.tfvars and configure your values."
        exit 1
    fi
    
    check_prerequisites
    init_terraform
    validate_terraform
    plan_terraform
    apply_terraform
    show_outputs
    
    print_status "InfluxDB infrastructure deployment completed successfully!"
    print_status "You can now proceed with the Lambda function updates to use InfluxDB."
}

# Handle script arguments
case "${1:-}" in
    "init")
        check_prerequisites
        init_terraform
        ;;
    "plan")
        check_prerequisites
        init_terraform
        validate_terraform
        terraform plan -var-file="terraform.tfvars"
        ;;
    "apply")
        main
        ;;
    "destroy")
        print_warning "This will destroy all InfluxDB infrastructure!"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            terraform destroy -var-file="terraform.tfvars"
        else
            print_status "Destroy cancelled by user."
        fi
        ;;
    "output")
        terraform output
        ;;
    *)
        echo "Usage: $0 {init|plan|apply|destroy|output}"
        echo ""
        echo "Commands:"
        echo "  init     - Initialize Terraform"
        echo "  plan     - Show Terraform execution plan"
        echo "  apply    - Deploy InfluxDB infrastructure"
        echo "  destroy  - Destroy InfluxDB infrastructure"
        echo "  output   - Show deployment outputs"
        echo ""
        echo "Example: $0 apply"
        exit 1
        ;;
esac