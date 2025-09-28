#!/usr/bin/env python3
"""
Basic validation script for Lambda Router function
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import (
    lambda_handler,
    extract_file_info,
    get_file_extension,
    validate_file_format,
    determine_processing_path
)

def test_basic_functionality():
    """Run basic validation tests."""
    print("Testing Lambda Router Function...")
    
    # Test 1: File extension extraction
    print("\n1. Testing file extension extraction:")
    test_cases = [
        ('file.csv', '.csv'),
        ('data.XLSX', '.xlsx'),
        ('report.PDF', '.pdf'),
        ('data.parquet', '.parquet'),
        ('noextension', ''),
    ]
    
    for filename, expected in test_cases:
        result = get_file_extension(filename)
        status = "✓" if result == expected else "✗"
        print(f"   {status} {filename} -> {result} (expected: {expected})")
    
    # Test 2: File format validation
    print("\n2. Testing file format validation:")
    try:
        validate_file_format({'file_extension': '.csv'})
        print("   ✓ CSV format validation passed")
    except Exception as e:
        print(f"   ✗ CSV format validation failed: {e}")
    
    try:
        validate_file_format({'file_extension': '.parquet'})
        print("   ✓ Parquet format validation passed")
    except Exception as e:
        print(f"   ✗ Parquet format validation failed: {e}")
    
    try:
        validate_file_format({'file_extension': '.txt'})
        print("   ✗ TXT format should have been rejected")
    except ValueError:
        print("   ✓ TXT format correctly rejected")
    
    # Test 3: Processing path determination
    print("\n3. Testing processing path determination:")
    
    # Small CSV file -> Lambda
    small_csv = {
        'bucket': 'test-bucket',
        'key': 'data/small.csv',
        'size_mb': 50,
        'file_extension': '.csv',
        'filename': 'small.csv'
    }
    
    result = determine_processing_path(small_csv)
    if result['processingType'] == 'lambda':
        print("   ✓ Small CSV routed to Lambda")
    else:
        print(f"   ✗ Small CSV incorrectly routed to {result['processingType']}")
    
    # Large CSV file -> Batch
    large_csv = {
        'bucket': 'test-bucket',
        'key': 'data/large.csv',
        'size_mb': 150,
        'file_extension': '.csv',
        'filename': 'large.csv'
    }
    
    result = determine_processing_path(large_csv)
    if result['processingType'] == 'batch':
        print("   ✓ Large CSV routed to Batch")
    else:
        print(f"   ✗ Large CSV incorrectly routed to {result['processingType']}")
    
    # PDF file -> Batch (always)
    pdf_file = {
        'bucket': 'test-bucket',
        'key': 'docs/report.pdf',
        'size_mb': 10,
        'file_extension': '.pdf',
        'filename': 'report.pdf'
    }
    
    result = determine_processing_path(pdf_file)
    if result['processingType'] == 'batch':
        print("   ✓ PDF routed to Batch")
    else:
        print(f"   ✗ PDF incorrectly routed to {result['processingType']}")
    
    # Small Parquet file -> Lambda
    small_parquet = {
        'bucket': 'test-bucket',
        'key': 'data/small.parquet',
        'size_mb': 25,
        'file_extension': '.parquet',
        'filename': 'small.parquet'
    }
    
    result = determine_processing_path(small_parquet)
    if result['processingType'] == 'lambda':
        print("   ✓ Small Parquet routed to Lambda")
        if result['processorConfig']['environment']['OUTPUT_FORMAT'] == 'parquet':
            print("   ✓ Parquet output format configured")
        else:
            print("   ✗ Incorrect output format for Parquet")
    else:
        print(f"   ✗ Small Parquet incorrectly routed to {result['processingType']}")
    
    # Large Parquet file -> Batch
    large_parquet = {
        'bucket': 'test-bucket',
        'key': 'data/large.parquet',
        'size_mb': 200,
        'file_extension': '.parquet',
        'filename': 'large.parquet'
    }
    
    result = determine_processing_path(large_parquet)
    if result['processingType'] == 'batch':
        print("   ✓ Large Parquet routed to Batch")
    else:
        print(f"   ✗ Large Parquet incorrectly routed to {result['processingType']}")
    
    # Test 4: Lambda handler integration
    print("\n4. Testing Lambda handler:")
    
    test_event = {
        'bucket': 'test-bucket',
        'key': 'data/test.csv',
        'size': 1048576  # 1MB
    }
    
    try:
        result = lambda_handler(test_event, None)
        if result['statusCode'] == 200:
            print("   ✓ Lambda handler returned success")
            print(f"   ✓ Processing type: {result['body']['processingType']}")
        else:
            print(f"   ✗ Lambda handler returned error: {result}")
    except Exception as e:
        print(f"   ✗ Lambda handler failed: {e}")
    
    print("\nValidation complete!")

if __name__ == '__main__':
    test_basic_functionality()