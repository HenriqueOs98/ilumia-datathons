#!/bin/bash

# Package the cost optimizer Lambda function
echo "Packaging cost optimizer Lambda function..."

# Create a temporary directory
mkdir -p temp_package

# Copy the Lambda function code
cp lambda_function.py temp_package/

# Install dependencies
pip install -r requirements.txt -t temp_package/

# Create the zip file
cd temp_package
zip -r ../cost_optimizer.zip .
cd ..

# Clean up
rm -rf temp_package

# Move the zip file to the infra directory for Terraform
mv cost_optimizer.zip ../../infra/modules/monitoring/

echo "Cost optimizer Lambda package created successfully!"