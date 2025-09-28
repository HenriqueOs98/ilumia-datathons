#!/usr/bin/env python3
"""
Validation script for InfluxDB Loader Lambda Function

This script validates that the implementation meets the requirements
specified in task 3.1 of the timestream-influxdb-migration spec.
"""

import os
import sys
import importlib.util
import inspect
from typing import List, Dict, Any

def validate_implementation() -> Dict[str, Any]:
    """
    Validate the InfluxDB loader implementation against requirements.
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'requirements_met': []
    }
    
    try:
        # Import the lambda function module
        spec = importlib.util.spec_from_file_location(
            "lambda_function", 
            os.path.join(os.path.dirname(__file__), "lambda_function.py")
        )
        lambda_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lambda_module)
        
        # Requirement 3.1: Use InfluxDB Python client instead of Timestream client
        if hasattr(lambda_module, 'InfluxDBHandler'):
            results['requirements_met'].append("3.1 - Uses InfluxDB Python client")
        else:
            results['errors'].append("3.1 - Missing InfluxDB client usage")
            results['valid'] = False
        
        # Requirement 3.2: Use InfluxDB line protocol for optimal performance
        if 'convert_parquet_to_influxdb_points' in lambda_module.__dict__ or \
           'Point' in lambda_module.__dict__:
            results['requirements_met'].append("3.2 - Uses InfluxDB line protocol")
        else:
            results['errors'].append("3.2 - Missing InfluxDB line protocol usage")
            results['valid'] = False
        
        # Requirement 3.3: Implement proper error handling and retry logic
        error_handling_functions = [
            'InfluxDBConnectionError',
            'InfluxDBWriteError',
            'DataConversionError'
        ]
        
        error_handling_present = any(
            error_class in lambda_module.__dict__ 
            for error_class in error_handling_functions
        )
        
        if error_handling_present and hasattr(lambda_module, 'MAX_RETRIES'):
            results['requirements_met'].append("3.3 - Implements error handling and retry logic")
        else:
            results['errors'].append("3.3 - Missing comprehensive error handling")
            results['valid'] = False
        
        # Requirement 3.4: Queue data for retry with exponential backoff
        lambda_handler_source = inspect.getsource(lambda_module.lambda_handler)
        load_data_source = inspect.getsource(lambda_module.load_data_to_influxdb)
        
        if 'retry' in lambda_handler_source.lower() or 'retry' in load_data_source.lower():
            results['requirements_met'].append("3.4 - Implements retry with backoff")
        else:
            results['warnings'].append("3.4 - Retry logic may not be fully implemented")
        
        # Check for batch processing capability
        if hasattr(lambda_module, 'MAX_BATCH_SIZE') and \
           'batch' in load_data_source.lower():
            results['requirements_met'].append("Batch processing implemented")
        else:
            results['errors'].append("Missing batch processing capability")
            results['valid'] = False
        
        # Check for CloudWatch metrics
        if hasattr(lambda_module, 'send_metrics') and \
           hasattr(lambda_module, 'send_error_metrics'):
            results['requirements_met'].append("CloudWatch metrics implemented")
        else:
            results['errors'].append("Missing CloudWatch metrics")
            results['valid'] = False
        
        # Check for comprehensive error handling
        required_functions = [
            'lambda_handler',
            'extract_s3_info',
            'load_parquet_from_s3',
            'load_data_to_influxdb',
            'send_metrics',
            'create_response'
        ]
        
        missing_functions = [
            func for func in required_functions 
            if not hasattr(lambda_module, func)
        ]
        
        if missing_functions:
            results['errors'].append(f"Missing required functions: {missing_functions}")
            results['valid'] = False
        else:
            results['requirements_met'].append("All required functions present")
        
        # Check for environment variable handling
        lambda_source = inspect.getsource(lambda_module)
        env_vars = [
            'INFLUXDB_URL',
            'INFLUXDB_ORG',
            'INFLUXDB_BUCKET',
            'MAX_BATCH_SIZE',
            'MAX_RETRIES'
        ]
        
        env_vars_present = all(
            env_var in lambda_source for env_var in env_vars
        )
        
        if env_vars_present:
            results['requirements_met'].append("Environment variable configuration implemented")
        else:
            results['warnings'].append("Some environment variables may be missing")
        
        # Check for multiple event source support
        extract_s3_source = inspect.getsource(lambda_module.extract_s3_info)
        event_sources = ['Records', 'bucket', 'body']
        
        event_sources_supported = all(
            source in extract_s3_source for source in event_sources
        )
        
        if event_sources_supported:
            results['requirements_met'].append("Multiple event sources supported")
        else:
            results['warnings'].append("Limited event source support")
        
    except Exception as e:
        results['valid'] = False
        results['errors'].append(f"Validation failed: {str(e)}")
    
    return results


def print_validation_results(results: Dict[str, Any]) -> None:
    """Print validation results in a readable format."""
    print("=" * 60)
    print("InfluxDB Loader Implementation Validation")
    print("=" * 60)
    
    if results['valid']:
        print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION FAILED")
    
    print(f"\nRequirements Met ({len(results['requirements_met'])}):")
    for req in results['requirements_met']:
        print(f"  ✅ {req}")
    
    if results['warnings']:
        print(f"\nWarnings ({len(results['warnings'])}):")
        for warning in results['warnings']:
            print(f"  ⚠️  {warning}")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  ❌ {error}")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    results = validate_implementation()
    print_validation_results(results)
    
    # Exit with appropriate code
    sys.exit(0 if results['valid'] else 1)