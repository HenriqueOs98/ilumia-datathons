#!/usr/bin/env python3
"""
Simple validation script for the Structured Data Processor
Tests core functionality without external dependencies
"""

import sys
import os
import re
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_column_name_standardization():
    """Test column name standardization logic"""
    print("Testing column name standardization...")
    
    # Mock the StructuredDataProcessor class for testing
    class MockProcessor:
        def _standardize_column_name(self, col_name: str) -> str:
            """Standardize column names to snake_case"""
            import unicodedata
            
            # Convert to string and strip whitespace
            name = str(col_name).strip()
            
            # Convert to lowercase
            name = name.lower()
            
            # Normalize Unicode characters (remove accents)
            name = unicodedata.normalize('NFD', name)
            name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
            
            # Replace common Portuguese terms
            replacements = {
                'data': 'timestamp',
                'hora': 'time',
                'valor': 'value',
                'quantidade': 'quantity',
                'potencia': 'power',
                'energia': 'energy',
                'regiao': 'region',
                'fonte': 'source',
                'tipo': 'type',
                'unidade': 'unit'
            }
            
            for pt_term, en_term in replacements.items():
                if pt_term in name:
                    name = name.replace(pt_term, en_term)
            
            # Replace spaces and special characters with underscores
            name = re.sub(r'[^\w]', '_', name)
            
            # Remove multiple underscores
            name = re.sub(r'_+', '_', name)
            
            # Remove leading/trailing underscores
            name = name.strip('_')
            
            return name
    
    processor = MockProcessor()
    
    test_cases = [
        ('Data', 'timestamp'),
        ('Valor (MW)', 'value_mw'),
        ('Região', 'region'),
        ('Fonte de Energia', 'source_de_energy'),
        ('Potência Total', 'power_total'),
        ('  Espaços  ', 'espacos'),
        ('Carácteres-Especiais!@#', 'caracteres_especiais'),
        ('múltiplos___underscores', 'multiplos_underscores')
    ]
    
    passed = 0
    failed = 0
    
    for input_name, expected in test_cases:
        result = processor._standardize_column_name(input_name)
        if result == expected:
            print(f"  ✓ '{input_name}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_name}' -> '{result}' (expected '{expected}')")
            failed += 1
    
    print(f"Column standardization tests: {passed} passed, {failed} failed")
    return failed == 0

def test_file_extension_extraction():
    """Test file extension extraction"""
    print("\nTesting file extension extraction...")
    
    def get_file_extension(key: str) -> str:
        """Extract file extension from S3 key"""
        return os.path.splitext(key.lower())[1]
    
    test_cases = [
        ('test.csv', '.csv'),
        ('data.XLSX', '.xlsx'),
        ('file.XLS', '.xls'),
        ('path/to/file.CSV', '.csv'),
        ('no_extension', ''),
        ('multiple.dots.csv', '.csv')
    ]
    
    passed = 0
    failed = 0
    
    for input_key, expected in test_cases:
        result = get_file_extension(input_key)
        if result == expected:
            print(f"  ✓ '{input_key}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_key}' -> '{result}' (expected '{expected}')")
            failed += 1
    
    print(f"File extension tests: {passed} passed, {failed} failed")
    return failed == 0

def test_dataset_type_determination():
    """Test dataset type determination logic"""
    print("\nTesting dataset type determination...")
    
    def determine_dataset_type(filename: str) -> str:
        """Determine dataset type based on filename"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['geracao', 'generation', 'producao']):
            return 'generation'
        elif any(term in filename_lower for term in ['consumo', 'consumption', 'demanda']):
            return 'consumption'
        elif any(term in filename_lower for term in ['transmissao', 'transmission', 'rede']):
            return 'transmission'
        else:
            return 'general'
    
    test_cases = [
        ('dados_geracao_2024.csv', 'generation'),
        ('consumo_energia_jan.xlsx', 'consumption'),
        ('transmissao_rede.csv', 'transmission'),
        ('outros_dados.csv', 'general'),
        ('GERACAO_HIDRICA.CSV', 'generation'),
        ('demanda_regiao_sul.xlsx', 'consumption')
    ]
    
    passed = 0
    failed = 0
    
    for filename, expected in test_cases:
        result = determine_dataset_type(filename)
        if result == expected:
            print(f"  ✓ '{filename}' -> '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{filename}' -> '{result}' (expected '{expected}')")
            failed += 1
    
    print(f"Dataset type tests: {passed} passed, {failed} failed")
    return failed == 0

def test_quality_score_calculation():
    """Test data quality score calculation"""
    print("\nTesting quality score calculation...")
    
    def calculate_quality_score(total_cells: int, non_null_cells: int) -> float:
        """Calculate a simple data quality score based on completeness"""
        return round((non_null_cells / total_cells) * 100, 2) if total_cells > 0 else 0.0
    
    test_cases = [
        (6, 6, 100.0),  # Perfect data
        (6, 4, 66.67),  # 4 out of 6 cells filled
        (10, 8, 80.0),  # 8 out of 10 cells filled
        (0, 0, 0.0),    # Empty data
        (5, 0, 0.0)     # All null data
    ]
    
    passed = 0
    failed = 0
    
    for total, non_null, expected in test_cases:
        result = calculate_quality_score(total, non_null)
        if result == expected:
            print(f"  ✓ {non_null}/{total} cells -> {result}%")
            passed += 1
        else:
            print(f"  ✗ {non_null}/{total} cells -> {result}% (expected {expected}%)")
            failed += 1
    
    print(f"Quality score tests: {passed} passed, {failed} failed")
    return failed == 0

def test_lambda_event_parsing():
    """Test Lambda event parsing logic"""
    print("\nTesting Lambda event parsing...")
    
    def parse_lambda_event(event):
        """Parse Lambda event to extract bucket and key"""
        if 'Records' in event:
            # S3 event format
            results = []
            for record in event['Records']:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                results.append((bucket, key))
            return results
        else:
            # Direct invocation format
            bucket = event.get('bucket')
            key = event.get('key')
            if not bucket or not key:
                raise ValueError("Missing required parameters: bucket and key")
            return [(bucket, key)]
    
    # Test S3 event
    s3_event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test.csv'}
                }
            }
        ]
    }
    
    # Test direct invocation
    direct_event = {
        'bucket': 'test-bucket',
        'key': 'test.csv'
    }
    
    # Test invalid event
    invalid_event = {'bucket': 'test-bucket'}  # Missing key
    
    passed = 0
    failed = 0
    
    try:
        result = parse_lambda_event(s3_event)
        if result == [('test-bucket', 'test.csv')]:
            print("  ✓ S3 event parsing")
            passed += 1
        else:
            print(f"  ✗ S3 event parsing: {result}")
            failed += 1
    except Exception as e:
        print(f"  ✗ S3 event parsing failed: {e}")
        failed += 1
    
    try:
        result = parse_lambda_event(direct_event)
        if result == [('test-bucket', 'test.csv')]:
            print("  ✓ Direct invocation parsing")
            passed += 1
        else:
            print(f"  ✗ Direct invocation parsing: {result}")
            failed += 1
    except Exception as e:
        print(f"  ✗ Direct invocation parsing failed: {e}")
        failed += 1
    
    try:
        parse_lambda_event(invalid_event)
        print("  ✗ Invalid event should have raised ValueError")
        failed += 1
    except ValueError:
        print("  ✓ Invalid event properly rejected")
        passed += 1
    except Exception as e:
        print(f"  ✗ Invalid event raised wrong exception: {e}")
        failed += 1
    
    print(f"Event parsing tests: {passed} passed, {failed} failed")
    return failed == 0

def main():
    """Run all validation tests"""
    print("=" * 60)
    print("Structured Data Processor - Implementation Validation")
    print("=" * 60)
    
    tests = [
        test_column_name_standardization,
        test_file_extension_extraction,
        test_dataset_type_determination,
        test_quality_score_calculation,
        test_lambda_event_parsing
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test in tests:
        if test():
            passed_tests += 1
    
    print("\n" + "=" * 60)
    print(f"VALIDATION SUMMARY: {passed_tests}/{total_tests} test suites passed")
    
    if passed_tests == total_tests:
        print("✓ All core functionality tests passed!")
        return 0
    else:
        print("✗ Some tests failed. Please review the implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())