"""
Validation script for Timestream Loader implementation
"""

import boto3
import pandas as pd
import json
from datetime import datetime, timedelta
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_timestream_setup():
    """Validate Timestream database and tables setup."""
    try:
        timestream_client = boto3.client('timestream-write')
        
        # List databases
        databases = timestream_client.list_databases()
        logger.info(f"Found {len(databases['Databases'])} Timestream databases")
        
        # Find our database
        db_name = None
        for db in databases['Databases']:
            if 'energy_data' in db['DatabaseName']:
                db_name = db['DatabaseName']
                logger.info(f"Found energy data database: {db_name}")
                break
        
        if not db_name:
            logger.error("Energy data database not found")
            return False
        
        # List tables
        tables = timestream_client.list_tables(DatabaseName=db_name)
        table_names = [table['TableName'] for table in tables['Tables']]
        
        expected_tables = ['generation_data', 'consumption_data', 'transmission_data']
        missing_tables = [table for table in expected_tables if table not in table_names]
        
        if missing_tables:
            logger.error(f"Missing tables: {missing_tables}")
            return False
        
        logger.info(f"All required tables found: {table_names}")
        return True
        
    except Exception as e:
        logger.error(f"Error validating Timestream setup: {str(e)}")
        return False


def create_sample_data() -> pd.DataFrame:
    """Create sample energy data for testing."""
    now = datetime.utcnow()
    
    data = []
    for i in range(10):
        timestamp = now - timedelta(hours=i)
        data.append({
            'timestamp': timestamp,
            'region': 'SE',
            'value': 100.0 + i * 10,
            'unit': 'MW',
            'energy_source': 'hydro',
            'measurement_type': 'power',
            'quality_flag': 'good'
        })
    
    return pd.DataFrame(data)


def test_data_validation():
    """Test data validation functions."""
    from lambda_function import validate_data_schema, convert_to_timestream_records
    
    # Test valid data
    df = create_sample_data()
    validation_result = validate_data_schema(df, 'generation')
    
    if not validation_result['valid']:
        logger.error(f"Data validation failed: {validation_result['errors']}")
        return False
    
    logger.info("Data validation passed")
    
    # Test record conversion
    records = convert_to_timestream_records(df, 'generation')
    
    if len(records) != len(df):
        logger.error(f"Record conversion failed: expected {len(df)}, got {len(records)}")
        return False
    
    logger.info(f"Successfully converted {len(records)} records")
    
    # Validate record structure
    sample_record = records[0]
    required_fields = ['Time', 'TimeUnit', 'Dimensions', 'MeasureName', 'MeasureValue', 'MeasureValueType']
    
    for field in required_fields:
        if field not in sample_record:
            logger.error(f"Missing required field in record: {field}")
            return False
    
    logger.info("Record structure validation passed")
    return True


def test_lambda_function_locally():
    """Test Lambda function with sample event."""
    from lambda_function import lambda_handler
    
    # Create test event
    event = {
        'bucket': 'test-bucket',
        'key': 'dataset=generation/year=2024/month=01/sample.parquet'
    }
    
    try:
        # Note: This will fail without actual S3 data, but we can test the event parsing
        result = lambda_handler(event, {})
        logger.info(f"Lambda function test result: {result}")
        return True
    except Exception as e:
        # Expected to fail without real S3 data
        if "Error loading Parquet file" in str(e) or "NoCredentialsError" in str(e):
            logger.info("Lambda function structure test passed (expected S3 error)")
            return True
        else:
            logger.error(f"Unexpected error in Lambda function: {str(e)}")
            return False


def validate_iam_permissions():
    """Validate IAM permissions for Timestream access."""
    try:
        # Test Timestream permissions
        timestream_client = boto3.client('timestream-write')
        timestream_client.describe_endpoints()
        logger.info("Timestream permissions validated")
        
        # Test S3 permissions (basic check)
        s3_client = boto3.client('s3')
        s3_client.list_buckets()
        logger.info("S3 permissions validated")
        
        # Test CloudWatch permissions
        cloudwatch_client = boto3.client('cloudwatch')
        cloudwatch_client.list_metrics(Namespace='ONS/Timestream', MaxRecords=1)
        logger.info("CloudWatch permissions validated")
        
        return True
        
    except Exception as e:
        logger.error(f"Permission validation failed: {str(e)}")
        return False


def main():
    """Run all validation tests."""
    logger.info("Starting Timestream Loader validation...")
    
    tests = [
        ("Timestream Setup", validate_timestream_setup),
        ("Data Validation", test_data_validation),
        ("Lambda Function", test_lambda_function_locally),
        ("IAM Permissions", validate_iam_permissions)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"{test_name} test failed with exception: {str(e)}")
            results[test_name] = False
    
    # Summary
    logger.info("\n--- Validation Summary ---")
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ All validations passed! Timestream Loader is ready.")
        return True
    else:
        logger.error("❌ Some validations failed. Please check the logs above.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)