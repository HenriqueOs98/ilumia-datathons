"""
Comprehensive unit tests for Lambda Router Function
Tests file routing logic, configuration generation, and error handling
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
import sys

# Add source path
sys.path.insert(0, 'src/lambda_router')

from lambda_function import (
    lambda_handler,
    extract_file_info,
    get_file_extension,
    validate_file_format,
    determine_processing_path,
    get_lambda_config,
    get_batch_config,
    get_batch_pdf_config,
    generate_output_location
)


class TestFileInfoExtraction:
    """Test file information extraction from various event sources"""
    
    def test_extract_s3_event_records(self):
        """Test extraction from S3 Records event"""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {
                        'key': 'data/generation/file.csv',
                        'size': 2097152  # 2MB
                    }
                }
            }]
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'data/generation/file.csv'
        assert result['size_bytes'] == 2097152
        assert result['size_mb'] == 2.0
        assert result['file_extension'] == '.csv'
        assert result['filename'] == 'file.csv'
    
    def test_extract_eventbridge_detail(self):
        """Test extraction from EventBridge detail event"""
        event = {
            'detail': {
                'bucket': {'name': 'eventbridge-bucket'},
                'object': {
                    'key': 'reports/consumption.xlsx',
                    'size': 10485760  # 10MB
                }
            }
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'eventbridge-bucket'
        assert result['key'] == 'reports/consumption.xlsx'
        assert result['size_mb'] == 10.0
        assert result['file_extension'] == '.xlsx'
        assert result['filename'] == 'consumption.xlsx'
    
    def test_extract_direct_invocation(self):
        """Test extraction from direct Lambda invocation"""
        event = {
            'bucket': 'direct-bucket',
            'key': 'pdfs/transmission-report.pdf',
            'size': 52428800  # 50MB
        }
        
        result = extract_file_info(event)
        
        assert result['bucket'] == 'direct-bucket'
        assert result['key'] == 'pdfs/transmission-report.pdf'
        assert result['size_mb'] == 50.0
        assert result['file_extension'] == '.pdf'
        assert result['filename'] == 'transmission-report.pdf'
    
    def test_extract_missing_bucket(self):
        """Test error handling for missing bucket"""
        event = {'key': 'test.csv'}
        
        with pytest.raises(ValueError, match="Missing required file information"):
            extract_file_info(event)
    
    def test_extract_missing_key(self):
        """Test error handling for missing key"""
        event = {'bucket': 'test-bucket'}
        
        with pytest.raises(ValueError, match="Missing required file information"):
            extract_file_info(event)
    
    def test_extract_zero_size_file(self):
        """Test handling of zero-size files"""
        event = {
            'bucket': 'test-bucket',
            'key': 'empty.csv',
            'size': 0
        }
        
        result = extract_file_info(event)
        
        assert result['size_mb'] == 0.0
        assert result['size_bytes'] == 0


class TestFileExtensionHandling:
    """Test file extension detection and validation"""
    
    def test_get_extension_various_formats(self):
        """Test extension extraction for supported formats"""
        test_cases = [
            ('data.csv', '.csv'),
            ('report.XLSX', '.xlsx'),
            ('old-format.XLS', '.xls'),
            ('processed.PARQUET', '.parquet'),
            ('document.PDF', '.pdf'),
            ('path/to/file.CSV', '.csv'),
            ('complex.name.with.dots.xlsx', '.xlsx')
        ]
        
        for filename, expected in test_cases:
            assert get_file_extension(filename) == expected
    
    def test_get_extension_no_extension(self):
        """Test files without extensions"""
        assert get_file_extension('filename_no_ext') == ''
        assert get_file_extension('path/to/file_no_ext') == ''
    
    def test_validate_supported_formats(self):
        """Test validation accepts all supported formats"""
        supported_formats = ['.csv', '.xlsx', '.xls', '.parquet', '.pdf']
        
        for ext in supported_formats:
            file_info = {'file_extension': ext}
            # Should not raise exception
            validate_file_format(file_info)
    
    def test_validate_unsupported_formats(self):
        """Test validation rejects unsupported formats"""
        unsupported_formats = ['.txt', '.doc', '.docx', '.json', '.xml', '.zip', '']
        
        for ext in unsupported_formats:
            file_info = {'file_extension': ext}
            with pytest.raises(ValueError, match="Unsupported file format"):
                validate_file_format(file_info)


class TestProcessingPathDetermination:
    """Test routing logic for different file types and sizes"""
    
    def test_small_csv_lambda_routing(self):
        """Test small CSV files route to Lambda"""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/small.csv',
            'size_mb': 25,  # Below 100MB threshold
            'file_extension': '.csv',
            'filename': 'small.csv'
        }
        
        result = determine_processing_path(file_info)
        
        assert result['processingType'] == 'lambda'
        assert result['processorConfig']['functionName'] == 'ons-structured-data-processor'
        assert result['processorConfig']['memory'] == 3008
        assert result['processorConfig']['timeout'] == 900
        assert 'outputLocation' in result
        assert 'inputFile' in result
    
    def test_large_csv_batch_routing(self):
        """Test large CSV files route to Batch"""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/large.csv',
            'size_mb': 250,  # Above 100MB threshold
            'file_extension': '.csv',
            'filename': 'large.csv'
        }
        
        result = determine_processing_path(file_info)
        
        assert result['processingType'] == 'batch'
        assert result['processorConfig']['jobDefinition'] == 'ons-structured-data-processor-batch'
        assert result['processorConfig']['jobQueue'] == 'ons-data-processing-queue'
        assert result['processorConfig']['vcpus'] >= 1
        assert result['processorConfig']['memory'] >= 4096
    
    def test_xlsx_file_routing_by_size(self):
        """Test XLSX files route based on size"""
        # Small XLSX -> Lambda
        small_file = {
            'bucket': 'test-bucket',
            'key': 'reports/small.xlsx',
            'size_mb': 50,
            'file_extension': '.xlsx',
            'filename': 'small.xlsx'
        }
        
        result = determine_processing_path(small_file)
        assert result['processingType'] == 'lambda'
        
        # Large XLSX -> Batch
        large_file = {
            'bucket': 'test-bucket',
            'key': 'reports/large.xlsx',
            'size_mb': 150,
            'file_extension': '.xlsx',
            'filename': 'large.xlsx'
        }
        
        result = determine_processing_path(large_file)
        assert result['processingType'] == 'batch'
    
    def test_pdf_always_batch(self):
        """Test PDF files always route to Batch regardless of size"""
        sizes = [1, 50, 100, 500, 1000]  # Various sizes in MB
        
        for size in sizes:
            file_info = {
                'bucket': 'test-bucket',
                'key': f'pdfs/file_{size}mb.pdf',
                'size_mb': size,
                'file_extension': '.pdf',
                'filename': f'file_{size}mb.pdf'
            }
            
            result = determine_processing_path(file_info)
            
            assert result['processingType'] == 'batch'
            assert result['processorConfig']['jobDefinition'] == 'ons-pdf-processor-batch'
            assert 'PDF_EXTRACTION_TOOLS' in result['processorConfig']['environment']
    
    def test_parquet_file_routing(self):
        """Test Parquet files route to specialized processors"""
        # Small Parquet -> Lambda
        small_file = {
            'bucket': 'test-bucket',
            'key': 'data/small.parquet',
            'size_mb': 30,
            'file_extension': '.parquet',
            'filename': 'small.parquet'
        }
        
        result = determine_processing_path(small_file)
        assert result['processingType'] == 'lambda'
        assert result['processorConfig']['functionName'] == 'ons-parquet-processor'
        assert result['processorConfig']['environment']['INPUT_FORMAT'] == 'parquet'
        assert result['processorConfig']['environment']['PROCESSING_MODE'] == 'parquet_optimization'
        
        # Large Parquet -> Batch
        large_file = {
            'bucket': 'test-bucket',
            'key': 'data/large.parquet',
            'size_mb': 300,
            'file_extension': '.parquet',
            'filename': 'large.parquet'
        }
        
        result = determine_processing_path(large_file)
        assert result['processingType'] == 'batch'
        assert result['processorConfig']['jobDefinition'] == 'ons-parquet-processor-batch'


class TestProcessorConfigurations:
    """Test processor configuration generation"""
    
    def test_lambda_config_standard(self):
        """Test standard Lambda configuration"""
        file_info = {'file_extension': '.csv', 'size_mb': 10}
        
        config = get_lambda_config(file_info)
        
        assert config['functionName'] == 'ons-structured-data-processor'
        assert config['memory'] == 3008
        assert config['timeout'] == 900
        assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
        assert config['environment']['PARTITION_STRATEGY'] == 'year_month'
    
    def test_batch_config_resource_scaling(self):
        """Test Batch configuration scales resources by file size"""
        test_cases = [
            # (size_mb, expected_vcpus, expected_memory)
            (50, 1, 4096),      # Small file
            (750, 2, 8192),     # Medium file  
            (1500, 4, 16384),   # Large file
            (2000, 4, 16384),   # Very large file (capped at max)
        ]
        
        for size_mb, expected_vcpus, expected_memory in test_cases:
            file_info = {'size_mb': size_mb}
            config = get_batch_config(file_info)
            
            assert config['vcpus'] == expected_vcpus
            assert config['memory'] == expected_memory
            assert config['jobDefinition'] == 'ons-structured-data-processor-batch'
            assert config['jobQueue'] == 'ons-data-processing-queue'
            assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
    
    def test_batch_pdf_config(self):
        """Test Batch PDF processor configuration"""
        file_info = {'file_extension': '.pdf', 'size_mb': 100}
        
        config = get_batch_pdf_config(file_info)
        
        assert config['jobDefinition'] == 'ons-pdf-processor-batch'
        assert config['jobQueue'] == 'ons-data-processing-queue'
        assert config['vcpus'] == 2
        assert config['memory'] == 8192
        assert config['environment']['PDF_EXTRACTION_TOOLS'] == 'camelot,tabula'
        assert config['environment']['OUTPUT_FORMAT'] == 'parquet'
        assert config['environment']['PROCESSING_MODE'] == 'pdf'


class TestOutputLocationGeneration:
    """Test S3 output location generation with dataset type detection"""
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_generation_dataset_detection(self):
        """Test generation dataset type detection"""
        test_cases = [
            'geracao-mensal-2024.csv',
            'generation-data.xlsx', 
            'dados-gen-jan.pdf',
            'producao-energia.csv'
        ]
        
        for filename in test_cases:
            file_info = {
                'filename': filename,
                'key': f'data/{filename}'
            }
            
            output_location = generate_output_location(file_info)
            
            assert 'test-processed-bucket' in output_location
            assert 'dataset=generation' in output_location
            assert 'year=' in output_location
            assert 'month=' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_consumption_dataset_detection(self):
        """Test consumption dataset type detection"""
        test_cases = [
            'consumo-regional.xlsx',
            'consumption-data.csv',
            'demanda-energia.pdf'
        ]
        
        for filename in test_cases:
            file_info = {
                'filename': filename,
                'key': f'reports/{filename}'
            }
            
            output_location = generate_output_location(file_info)
            assert 'dataset=consumption' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_transmission_dataset_detection(self):
        """Test transmission dataset type detection"""
        test_cases = [
            'transmissao-dados.pdf',
            'transmission-report.csv',
            'rede-eletrica.xlsx'
        ]
        
        for filename in test_cases:
            file_info = {
                'filename': filename,
                'key': f'transmission/{filename}'
            }
            
            output_location = generate_output_location(file_info)
            assert 'dataset=transmission' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'})
    def test_general_dataset_fallback(self):
        """Test fallback to general dataset type"""
        file_info = {
            'filename': 'unknown-data.csv',
            'key': 'misc/unknown-data.csv'
        }
        
        output_location = generate_output_location(file_info)
        assert 'dataset=general' in output_location
    
    @patch.dict(os.environ, {'PROCESSED_BUCKET': 'custom-bucket'})
    def test_custom_bucket_environment(self):
        """Test custom bucket from environment variable"""
        file_info = {
            'filename': 'test.csv',
            'key': 'test.csv'
        }
        
        output_location = generate_output_location(file_info)
        assert 'custom-bucket' in output_location


class TestLambdaHandler:
    """Test main Lambda handler function"""
    
    def test_successful_processing(self):
        """Test successful file processing"""
        event = {
            'bucket': 'test-bucket',
            'key': 'data/test.csv',
            'size': 1048576  # 1MB
        }
        
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        assert 'body' in result
        body = result['body']
        assert body['processingType'] in ['lambda', 'batch']
        assert 'processorConfig' in body
        assert 'outputLocation' in body
        assert 'inputFile' in body
    
    def test_s3_records_event(self):
        """Test processing S3 Records event"""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {
                        'key': 'data/generation.csv',
                        'size': 5242880  # 5MB
                    }
                }
            }]
        }
        
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = result['body']
        assert body['inputFile']['bucket'] == 'test-bucket'
        assert body['inputFile']['key'] == 'data/generation.csv'
        assert body['inputFile']['size_mb'] == 5.0
    
    def test_error_handling_invalid_event(self):
        """Test error handling for invalid events"""
        event = {}  # Empty event
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'error' in result['body']
        assert result['body']['processingType'] == 'failed'
    
    def test_error_handling_unsupported_format(self):
        """Test error handling for unsupported file formats"""
        event = {
            'bucket': 'test-bucket',
            'key': 'data/unsupported.txt',
            'size': 1000
        }
        
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        assert 'Unsupported file format' in result['body']['error']
        assert result['body']['processingType'] == 'failed'


class TestEdgeCasesAndErrorScenarios:
    """Test edge cases and error scenarios"""
    
    def test_extremely_large_file(self):
        """Test handling of extremely large files"""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/huge.csv',
            'size_mb': 10000,  # 10GB
            'file_extension': '.csv',
            'filename': 'huge.csv'
        }
        
        result = determine_processing_path(file_info)
        
        # Should route to Batch with maximum resources
        assert result['processingType'] == 'batch'
        config = result['processorConfig']
        assert config['vcpus'] == 4  # Maximum vCPUs
        assert config['memory'] == 16384  # Maximum memory
    
    def test_file_with_special_characters(self):
        """Test files with special characters in names"""
        special_names = [
            'dados-geração-2024.csv',
            'consumo_região_sul.xlsx',
            'transmissão (backup).pdf',
            'file with spaces.csv'
        ]
        
        for filename in special_names:
            file_info = {
                'bucket': 'test-bucket',
                'key': f'data/{filename}',
                'size_mb': 10,
                'file_extension': get_file_extension(filename),
                'filename': filename
            }
            
            # Should process without errors
            result = determine_processing_path(file_info)
            assert result['processingType'] in ['lambda', 'batch']
    
    @patch.dict(os.environ, {'LAMBDA_SIZE_THRESHOLD_MB': '50'})
    def test_custom_size_threshold(self):
        """Test custom size threshold from environment"""
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/medium.csv',
            'size_mb': 75,  # Above custom threshold
            'file_extension': '.csv',
            'filename': 'medium.csv'
        }
        
        result = determine_processing_path(file_info)
        assert result['processingType'] == 'batch'
    
    def test_malformed_s3_uri_in_output(self):
        """Test output location generation with various inputs"""
        file_info = {
            'filename': 'test.csv',
            'key': 'very/deep/nested/path/test.csv'
        }
        
        output_location = generate_output_location(file_info)
        
        # Should still generate valid S3 URI
        assert output_location.startswith('s3://')
        assert 'dataset=' in output_location
        assert 'year=' in output_location
        assert 'month=' in output_location
    
    def test_concurrent_processing_simulation(self):
        """Test multiple files processing simulation"""
        files = [
            {'key': 'gen1.csv', 'size_mb': 10, 'ext': '.csv'},
            {'key': 'cons1.xlsx', 'size_mb': 200, 'ext': '.xlsx'},
            {'key': 'trans1.pdf', 'size_mb': 5, 'ext': '.pdf'},
            {'key': 'data1.parquet', 'size_mb': 150, 'ext': '.parquet'}
        ]
        
        results = []
        for file_data in files:
            file_info = {
                'bucket': 'test-bucket',
                'key': file_data['key'],
                'size_mb': file_data['size_mb'],
                'file_extension': file_data['ext'],
                'filename': file_data['key']
            }
            
            result = determine_processing_path(file_info)
            results.append(result)
        
        # Verify all processed successfully
        assert len(results) == 4
        for result in results:
            assert result['processingType'] in ['lambda', 'batch']
            assert 'outputLocation' in result


class TestAdvancedRoutingScenarios:
    """Test advanced routing scenarios and edge cases"""
    
    def test_routing_with_metadata_analysis(self):
        """Test routing decisions based on file metadata"""
        # Test with content-type metadata
        file_info = {
            'bucket': 'test-bucket',
            'key': 'data/unknown_extension',
            'size_mb': 25,
            'file_extension': '',
            'filename': 'unknown_extension',
            'content_type': 'text/csv'
        }
        
        # Should infer CSV from content-type
        result = determine_processing_path(file_info)
        assert result['processingType'] == 'lambda'
    
    def test_routing_performance_optimization(self):
        """Test routing performance with various file characteristics"""
        test_cases = [
            # (size_mb, expected_processing, expected_vcpus, expected_memory)
            (1, 'lambda', None, None),
            (50, 'lambda', None, None),
            (150, 'batch', 2, 8192),
            (500, 'batch', 4, 16384),
            (2000, 'batch', 4, 16384),  # Capped at maximum
        ]
        
        for size_mb, expected_processing, expected_vcpus, expected_memory in test_cases:
            file_info = {
                'bucket': 'test-bucket',
                'key': 'data/test.csv',
                'size_mb': size_mb,
                'file_extension': '.csv',
                'filename': 'test.csv'
            }
            
            result = determine_processing_path(file_info)
            assert result['processingType'] == expected_processing
            
            if expected_processing == 'batch':
                config = result['processorConfig']
                assert config['vcpus'] == expected_vcpus
                assert config['memory'] == expected_memory
    
    def test_routing_with_custom_thresholds(self):
        """Test routing with custom size thresholds"""
        with patch.dict(os.environ, {'LAMBDA_SIZE_THRESHOLD_MB': '200'}):
            file_info = {
                'bucket': 'test-bucket',
                'key': 'data/medium.csv',
                'size_mb': 150,  # Below custom threshold
                'file_extension': '.csv',
                'filename': 'medium.csv'
            }
            
            result = determine_processing_path(file_info)
            assert result['processingType'] == 'lambda'
            
            # Test above custom threshold
            file_info['size_mb'] = 250
            result = determine_processing_path(file_info)
            assert result['processingType'] == 'batch'


class TestErrorRecoveryAndResilience:
    """Test error recovery and system resilience"""
    
    def test_graceful_degradation_missing_env_vars(self):
        """Test graceful degradation when environment variables are missing"""
        with patch.dict(os.environ, {}, clear=True):
            file_info = {
                'bucket': 'test-bucket',
                'key': 'data/test.csv',
                'size_mb': 10,
                'file_extension': '.csv',
                'filename': 'test.csv'
            }
            
            # Should use defaults when env vars are missing
            output_location = generate_output_location(file_info)
            assert 'ons-data-platform-processed' in output_location  # Default bucket
    
    def test_invalid_file_metadata_handling(self):
        """Test handling of invalid or corrupted file metadata"""
        invalid_events = [
            {'Records': [{'s3': {'bucket': {'name': 'test'}, 'object': {}}}]},  # Missing key
            {'Records': [{'s3': {'bucket': {}, 'object': {'key': 'test.csv'}}}]},  # Missing bucket name
            {'Records': [{}]},  # Missing s3 section
            {'Records': []},  # Empty records
        ]
        
        for event in invalid_events:
            with pytest.raises(ValueError):
                extract_file_info(event)
    
    def test_routing_fallback_mechanisms(self):
        """Test fallback mechanisms in routing logic"""
        # Test with minimal file info
        minimal_file_info = {
            'bucket': 'test-bucket',
            'key': 'unknown',
            'size_mb': 0,
            'file_extension': '',
            'filename': 'unknown'
        }
        
        with pytest.raises(ValueError, match="Unsupported file format"):
            determine_processing_path(minimal_file_info)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])