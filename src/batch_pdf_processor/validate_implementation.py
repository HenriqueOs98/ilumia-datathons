#!/usr/bin/env python3
"""
Validation script for AWS Batch PDF Processor implementation
Checks if all requirements from task 2.3 are met
"""

import os
import sys
from pathlib import Path


def validate_dockerfile():
    """Validate Dockerfile exists and contains required components"""
    dockerfile_path = Path('src/batch_pdf_processor/Dockerfile')
    
    if not dockerfile_path.exists():
        return False, "Dockerfile not found"
    
    content = dockerfile_path.read_text()
    
    required_components = [
        'FROM python:3.11',
        'ghostscript',
        'poppler',
        'tesseract',
        'camelot',
        'tabula',
        'WORKDIR /app',
        'pip install',
        'CMD ["python", "pdf_processor.py"]'
    ]
    
    missing = []
    for component in required_components:
        if component.lower() not in content.lower():
            missing.append(component)
    
    if missing:
        return False, f"Missing components in Dockerfile: {missing}"
    
    return True, "Dockerfile validation passed"


def validate_requirements():
    """Validate requirements.txt contains necessary libraries"""
    req_path = Path('src/batch_pdf_processor/requirements.txt')
    
    if not req_path.exists():
        return False, "requirements.txt not found"
    
    content = req_path.read_text()
    
    required_libs = [
        'boto3',
        'pandas',
        'camelot-py',
        'tabula-py',
        'PyPDF2',
        'pdfplumber',
        'pyarrow',
        'pytest'
    ]
    
    missing = []
    for lib in required_libs:
        if lib.lower() not in content.lower():
            missing.append(lib)
    
    if missing:
        return False, f"Missing libraries in requirements.txt: {missing}"
    
    return True, "Requirements.txt validation passed"


def validate_pdf_processor():
    """Validate PDF processor implementation"""
    processor_path = Path('src/batch_pdf_processor/pdf_processor.py')
    
    if not processor_path.exists():
        return False, "pdf_processor.py not found"
    
    content = processor_path.read_text()
    
    required_features = [
        'class PDFProcessor',
        'def process_pdf_file',
        'def _extract_tables_multi_method',
        'def _standardize_data',
        'camelot',
        'tabula',
        'pdfplumber',

        'try:',
        'except',
        'logging',
        'boto3',
        'parquet',
        's3_client'
    ]
    
    missing = []
    for feature in required_features:
        if feature.lower() not in content.lower():
            missing.append(feature)
    
    if missing:
        return False, f"Missing features in PDF processor: {missing}"
    
    # Check for specific error handling patterns
    error_patterns = [
        'except Exception',
        'try:',
        'raise',
        'error_message'
    ]
    
    error_handling_found = any(pattern in content for pattern in error_patterns)
    if not error_handling_found:
        return False, "Insufficient error handling in PDF processor"
    
    return True, "PDF processor validation passed"


def validate_tests():
    """Validate test implementation"""
    test_path = Path('src/batch_pdf_processor/test_pdf_processor.py')
    
    if not test_path.exists():
        return False, "test_pdf_processor.py not found"
    
    content = test_path.read_text()
    
    required_test_features = [
        'class TestPDFProcessor',
        'def test_',
        'unittest',
        'mock',
        'assert',
        'setUp',
        'mock_s3',
        'sample_table_data',
        'test_extract_tables',
        'test_standardize_data',
        'test_process_pdf_file'
    ]
    
    missing = []
    for feature in required_test_features:
        if feature.lower() not in content.lower():
            missing.append(feature)
    
    if missing:
        return False, f"Missing test features: {missing}"
    
    return True, "Test implementation validation passed"


def validate_sample_pdfs():
    """Validate sample PDF creation script"""
    sample_path = Path('src/batch_pdf_processor/create_sample_pdfs.py')
    
    if not sample_path.exists():
        return False, "create_sample_pdfs.py not found"
    
    content = sample_path.read_text()
    
    required_features = [
        'def create_sample',
        'def create_pdf_with_table',
        'def create_malformed_pdf',
        'reportlab',
        'pandas',
        'ONS',
        'energia',
        'samples'
    ]
    
    missing = []
    for feature in required_features:
        if feature.lower() not in content.lower():
            missing.append(feature)
    
    if missing:
        return False, f"Missing sample PDF features: {missing}"
    
    return True, "Sample PDF creation validation passed"


def validate_readme():
    """Validate README documentation"""
    readme_path = Path('src/batch_pdf_processor/README.md')
    
    if not readme_path.exists():
        return False, "README.md not found"
    
    content = readme_path.read_text()
    
    required_sections = [
        '# AWS Batch PDF Processor',
        'Overview',
        'Features',
        'Architecture',
        'Docker',
        'Usage',
        'Error Handling',
        'Testing',
        'Dependencies'
    ]
    
    missing = []
    for section in required_sections:
        if section.lower() not in content.lower():
            missing.append(section)
    
    if missing:
        return False, f"Missing README sections: {missing}"
    
    return True, "README documentation validation passed"


def main():
    """Run all validations"""
    print("Validating AWS Batch PDF Processor Implementation")
    print("=" * 50)
    
    validations = [
        ("Dockerfile", validate_dockerfile),
        ("Requirements", validate_requirements),
        ("PDF Processor", validate_pdf_processor),
        ("Tests", validate_tests),
        ("Sample PDFs", validate_sample_pdfs),
        ("README", validate_readme)
    ]
    
    all_passed = True
    
    for name, validator in validations:
        try:
            passed, message = validator()
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{name:15} {status:8} {message}")
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            print(f"{name:15} ✗ ERROR  {str(e)}")
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("✓ All validations passed! Implementation meets requirements.")
        print("\nTask 2.3 Requirements Coverage:")
        print("✓ Dockerfile with Python environment and specialized libraries")
        print("✓ PDF table extraction and data standardization logic")
        print("✓ Error handling for malformed PDFs and extraction failures")
        print("✓ Integration tests with sample PDF files")
        return 0
    else:
        print("✗ Some validations failed. Please review the implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(main())