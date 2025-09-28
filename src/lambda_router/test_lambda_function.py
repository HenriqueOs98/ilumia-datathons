"""
Unit tests for Lambda Router Function

Tests cover file type detection, size analysis, routing logic,
and various file scenarios as specified in requirements.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
import sys

# Add the lambda function to the path
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import (
    lambda_handler,
    extract_file_info,
    get_file_extension,
    validate_file_format,
    determine_processing_path,
    get_lambda_config,
    get_batch_config,
    get_batch_pdf_config,
    get_lambda_parquet_config,
    get_batch_parquet_config,
    generate_output_location
)


class TestFileExtraction:
    """Test file information extraction from various event sources."""
    
    def test_extract_file_info_s3_event(self):
        """Test extraction from S3 event via EventBridge."""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {
                        'key': 'data/test-file.csv',
                        'size': 1048576  # 1MB
                    }
                }
            }]
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'data/test-file.csv'
        assert result['size_bytes'] == 1048576
        assert result['size_mb'] == 1.0
        assert result['file_extension'] == '.csv'
        assert result['filename'] == 'test-file.csv'
    
    def test_extract_file_info_eventbridge_event(self):
        """Test extraction from EventBridge event."""
        event = {
            'detail': {
                'bucket': {'name': 'test-bucket'},
                'object': {
                    'key': 'reports/monthly-report.xlsx',
                    'size': 5242880  # 5MB
                }
            }
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'reports/monthly-report.xlsx'
        assert result['size_mb'] == 5.0
        assert result['file_extension'] == '.xlsx'
    
    def test_extract_file_info_direct_invocation(self):
        """Test extraction from direct invocation."""
        event = {
            'bucket': 'direct-bucket',
            'key': 'files/document.pdf',
            'size': 10485760  # 10MB
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'direct-bucket'
        assert result['key'] == 'files/document.pdf'
        assert result['size_mb'] == 10.0
        assert result['file_extension'] == '.pdf'
    
    def test_extract_file_info_missing_required_fields(self):
        """Test error handling for missing required fields."""
        event = {'size': 1000}
        
        with pytest.raises(ValueError, match="Missing required file information"):
            extract_file_info(event)


class TestFileExtensionHandling:
    """Test file extension detection and normalization."""
    
    def test_get_file_extension_various_formats(self):
        """Test extension extraction for various file formats."""
        test_cases = [
            ('file.csv', '.csv'),
            ('data.XLSX', '.xlsx'),
            ('report.PDF', '.pdf'),
            ('archive.tar.gz', '.gz'),
            ('noextension', ''),
            ('path/to/file.CSV', '.csv')
        ]
        
        for filename, expected in test_cases:
            assert get_file_extension(filename) == expected
    
    def test_validate_file_format_supported(self):
        """Test validation of supported file formats."""
        supported_files = [
            {'file_extension': '.csv'},
            {'file_extension': '.xlsx'},
            {'file_extension': '.xls'},
            {'file_extension': '.parquet'},
            {'file_extension': '.pdf'}
        ]
        
        for file_info in supported_files:
            # Should not raise exception
            validate_file_format(file_info)
    
    def test_validate_file_format_unsupported(self):
        """Test validation rejection of unsupported formats."""
        unsupported_files = [
            {'file_extension': '.txt'},
            {'file_extension': '.doc'},
            {'file_extension': '.json'},
            {'file_extension': ''}
        ]
        
        for file_info in unsupported_files:
            with pytest.raises(ValueError, match="Unsupported file format"):
                validate_file_format(file_info)


class TestProcessingPathDetermination:
    """Test routing logic for different file types and sizes."""
    
    def test_small_csv_routes_to_lambda(self):
        """Test that small CSV files route to Lambda processing."""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/small.csv',
            'size_mb': 50,  # Below threshold
            'file_extension': '.csv',
            'filename': 'small.csv'
        }
        
        result = determine_processing_path(file_info)
        
        assert result['processingType'] == 'lambda'
        assert result['processorConfig']['functionName'] == 'ons-structured-data-processor'
        assert 'outputLocation' in result
    
    def test_large_csv_routes_to_batch(self):
        """Test that large CSV files route to Batch processing."""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/large.csv',
            'size_mb': 150,  # Above threshold
            'file_extension': '.csv',
            'filename': 'large.csv'
        }
        
        result = determine_processing_path(file_info)
        
        assert result['processingType'] == 'batch'
        assert result['processorConfig']['jobDefinition'] == 'ons-structured-data-processor-batch'
    
    def test_xlsx_file_routing(self):
        """Test XLSX file routing based on size."""
        # Small XLSX -> Lambda
        small_file = {
            'bucket': 'test-bucket',
            'key': 'reports/small.xlsx',
            'size_mb': 25,
            'file_extension': '.xlsx',
            'filename': 'small.xlsx'
        }
        
        result = determine_processing_path(small_file)
        assert result['processingType'] == 'lambda'
        
        # Large XLSX -> Batch
        large_file = {
            'bucket': 'test-bucket',
            'key': 'reports/large.xlsx',
            'size_mb': 200,
            'file_extension': '.xlsx',
            'filename': 'large.xlsx'
        }
        
        result = determine_processing_path(large_file)
        assert result['processingType'] == 'batch'
    
    def test_pdf_always_routes_to_batch(self):
        """Test that PDF files always route to Batch regardless of size."""
        test_cases = [
            {'size_mb': 1, 'filename': 'small.pdf'},
            {'size_mb': 50, 'filename': 'medium.pdf'},
            {'size_mb': 500, 'filename': 'large.pdf'}
        ]
        
        for case in test_cases:
            file_info = {
                'bucket': 'test-bucket',
                'key': f"pdfs/{case['filename']}",
                'size_mb': case['size_mb'],
                'file_extension': '.pdf',
                'filename': case['filename']
            }
            
            result = determine_processing_path(file_info)
            
            assert result['processingType'] == 'batch'
            assert result['processorConfig']['jobDefinition'] == 'ons-pdf-processor-batch'
    
    def test_parquet_file_routing(self):
        """Test Parquet file routing based on size."""
        # Small Parquet -> Lambda
        small_file = {
            'bucket': 'test-bucket',
            'key': 'data/small.parquet',
            'size_mb': 25,
            'file_extension': '.parquet',
            'filename': 'small.parquet'
        }
        
        result = determine_processing_path(small_file)
        assert result['processingType'] == 'lambda'
        assert result['processorConfig']['functionName'] == 'ons-parquet-processor'
        assert result['processorConfig']['environment']['INPUT_FORMAT'] == 'parquet'
        assert result['processorConfig']['environment']['OUTPUT_FORMAT'] == 'parquet'
        
        # Large Parquet -> Batch
        large_file = {
            'bucket': 'test-bucket',
            'key': 'data/large.parquet',
            'size_mb': 200,
            'file_extension': '.parquet',
            'filename': 'large.parquet'
        }
        
        result = determine_processing_path(large_file)
        assert result['processingType'] == 'batch'
        assert result['processorConfig']['jobDefinition'] == 'ons-parquet-processor-batch'
        assert result['processorConfig']['environment']['INPUT_FORMAT'] == 'parquet'


class TestProcessorConfigurations:
    """Test processor configuration generation."""
    
    def test_lambda_config_generation(self):
        """Test Lambda processor configuration."""
        file_info = {'file_extension': '.csv', 'size_mb': 10}
        
        config = get_lambda_config(file_info)
        
        assert config['functionName'] == 'ons-structured-data-processor'
        assert config['memory'] == 3008
        assert config['timeout'] == 900
        assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
    
    def test_batch_config_resource_allocation(self):
        """Test Batch configuration with different file sizes."""
        test_cases = [
            # Small file
            {'size_mb': 100, 'expected_vcpus': 1, 'expected_memory': 4096},
            # Medium file
            {'size_mb': 750, 'expected_vcpus': 2, 'expected_memory': 8192},
            # Large file
            {'size_mb': 1500, 'expected_vcpus': 4, 'expected_memory': 16384}
        ]
        
        for case in test_cases:
            file_info = {'size_mb': case['size_mb']}
            config = get_batch_config(file_info)
            
            assert config['vcpus'] == case['expected_vcpus']
            assert config['memory'] == case['expected_memory']
            assert config['jobDefinition'] == 'ons-structured-data-processor-batch'
    
    def test_batch_pdf_config(self):
        """Test Batch PDF processor configuration."""
        file_info = {'file_extension': '.pdf', 'size_mb': 50}
        
        config = get_batch_pdf_config(file_info)
        
        assert config['jobDefinition'] == 'ons-pdf-processor-batch'
        assert config['vcpus'] == 2
        assert config['memory'] == 8192
        assert 'camelot,tabula' in config['environment']['PDF_EXTRACTION_TOOLS']
        assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
    
    def test_lambda_parquet_config(self):
        """Test Lambda Parquet processor configuration."""
        file_info = {'file_extension': '.parquet', 'size_mb': 10}
        
        config = get_lambda_parquet_config(file_info)
        
        assert config['functionName'] == 'ons-parquet-processor'
        assert config['memory'] == 3008
        assert config['timeout'] == 900
        assert config['environment']['INPUT_FORMAT'] == 'parquet'
        assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
        assert config['environment']['PROCESSING_MODE'] == 'parquet_optimization'
    
    def test_batch_parquet_config_resource_allocation(self):
        """Test Batch Parquet configuration with different file sizes."""
        test_cases = [
            # Small file
            {'size_mb': 100, 'expected_vcpus': 1, 'expected_memory': 4096},
            # Medium file
            {'size_mb': 750, 'expected_vcpus': 2, 'expected_memory': 8192},
            # Large file
            {'size_mb': 1500, 'expected_vcpus': 4, 'expected_memory': 16384}
        ]
        
        for case in test_cases:
            file_info = {'size_mb': case['size_mb']}
            config = get_batch_parquet_config(file_info)
            
            assert config['vcpus'] == case['expected_vcpus']
            assert config['memory'] == case['expected_memory']
            assert config['jobDefinition'] == 'ons-parquet-processor-batch'
            assert config['environment']['INPUT_FORMAT'] == 'parquet'
            assert config['environment']['OUTPUT_FORMAT'] == 'parquet'


class TestOutputLocationGeneration:
    """Test S3 output location generation with partitioning."""
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_generation_dataset_detection(self):
        """Test dataset type detection for generation data."""
        file_info = {
            'filename': 'geracao-mensal-2024.csv',
            'key': 'data/generation/geracao-mensal-2024.csv'
        }
        
        output_location = generate_output_location(file_info)
        
        assert 'test-processed-bucket' in output_location
        assert 'dataset=generation' in output_location
        assert 'year=' in output_location
        assert 'month=' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_consumption_dataset_detection(self):
        """Test dataset type detection for consumption data."""
        file_info = {
            'filename': 'consumo-regional.xlsx',
            'key': 'reports/consumption/consumo-regional.xlsx'
        }
        
        output_location = generate_output_location(file_info)
        
        assert 'dataset=consumption' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_transmission_dataset_detection(self):
        """Test dataset type detection for transmission data."""
        file_info = {
            'filename': 'transmissao-dados.pdf',
            'key': 'data/transmission/transmissao-dados.pdf'
        }
        
        output_location = generate_output_location(file_info)
        
        assert 'dataset=transmission' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_general_dataset_fallback(self):
        """Test fallback to general dataset type."""
        file_info = {
            'filename': 'unknown-data.csv',
            'key': 'misc/unknown-data.csv'
        }
        
        output_location = generate_output_location(file_info)
        
        assert 'dataset=general' in output_location


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    def test_successful_processing(self):
        """Test successful file processing."""
        event = {
            'bucket': 'test-bucket',
            'key': 'data/test.csv',
            'size': 1048576  # 1MB
        }
        
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        assert 'body' in result
        assert result['body']['processingType'] in ['lambda', 'batch']
    
    def test_error_handling(self):
        """Test error handling in Lambda handler."""
        # Invalid event without required fields
        event = {}
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'error' in result['body']
        assert result['body']['processingType'] == 'failed'
    
    def test_unsupported_file_format_handling(self):
        """Test handling of unsupported file formats."""
        event = {
            'bucket': 'test-bucket',
            'key': 'data/unsupported.txt',
            'size': 1000
        }
        
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'Unsupported file format' in result['body']['error']


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_zero_size_file(self):
        """Test handling of zero-size files."""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'empty.csv',
            'size_bytes': 0,
            'size_mb': 0,
            'file_extension': '.csv',
            'filename': 'empty.csv'
        }
        
        # Should still route to Lambda for small files
        result = determine_processing_path(file_info)
        assert result['processingType'] == 'lambda'
    
    def test_file_with_multiple_extensions(self):
        """Test files with multiple extensions."""
        filename = 'data.backup.csv'
        extension = get_file_extension(filename)
        assert extension == '.csv'
    
    def test_case_insensitive_extension_handling(self):
        """Test case-insensitive file extension handling."""
        test_cases = [
            'file.CSV',
            'file.Csv',
            'file.cSv',
            'file.csv'
        ]
        
        for filename in test_cases:
            extension = get_file_extension(filename)
            assert extension == '.csv'
    
    @patch.dict(os.environ, {'LAMBDA_SIZE_THRESHOLD_MB': '50'})
    def test_custom_size_threshold(self):
        """Test custom size threshold from environment variable."""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/medium.csv',
            'size_mb': 75,  # Above custom threshold of 50MB
            'file_extension': '.csv',
            'filename': 'medium.csv'
        }
        
        result = determine_processing_path(file_info)
        assert result['processingType'] == 'batch'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])