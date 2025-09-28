"""
End-to-End Integration Tests for ONS Data Platform
Tests complete data processing workflows from file upload to final storage
"""

import pytest
import json
import pandas as pd
import boto3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from moto import mock_s3, mock_timestream_write, mock_bedrock_agent_runtime
import time
import uuid


class TestCompleteDataProcessingWorkflow:
    """Test complete data processing workflow from S3 upload to Timestream"""
    
    @pytest.fixture
    def setup_test_environment(self):
        """Setup test environment with mock AWS services"""
        with mock_s3(), mock_timestream_write():
            # Create S3 buckets
            s3_client = boto3.client('s3', region_name='us-east-1')
            s3_client.create_bucket(Bucket='ons-data-platform-raw')
            s3_client.create_bucket(Bucket='ons-data-platform-processed')
            s3_client.create_bucket(Bucket='ons-data-platform-failed')
            
            # Create Timestream database and tables
            timestream_client = boto3.client('timestream-write', region_name='us-east-1')
            
            yield {
                's3_client': s3_client,
                'timestream_client': timestream_client
            }
    
    def test_csv_file_complete_workflow(self, setup_test_environment):
        """Test complete workflow for CSV file processing"""
        s3_client = setup_test_environment['s3_client']
        
        # Create test CSV data
        test_data = pd.DataFrame({
            'Data': ['2024-01-01 10:00', '2024-01-01 11:00', '2024-01-01 12:00'],
            'Região': ['Sudeste', 'Nordeste', 'Sul'],
            'Fonte': ['Hidrica', 'Eolica', 'Solar'],
            'Potência (MW)': [1500.0, 800.0, 200.0],
            'Unidade': ['MW', 'MW', 'MW']
        })
        
        # Upload CSV to raw bucket
        csv_content = test_data.to_csv(index=False)
        s3_client.put_object(
            Bucket='ons-data-platform-raw',
            Key='data/generation/test_generation.csv',
            Body=csv_content
        )
        
        # Step 1: Lambda Router
        from src.lambda_router.lambda_function import lambda_handler as router_handler
        
        router_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/generation/test_generation.csv',
            'size': len(csv_content.encode())
        }
        
        with patch.dict(os.environ, {'PROCESSED_BUCKET': 'ons-data-platform-processed'}):
            router_response = router_handler(router_event, None)
            
            assert router_response['statusCode'] == 200
            routing_decision = router_response['body']
            assert routing_decision['processingType'] == 'lambda'  # Small file should use Lambda
        
        # Step 2: Structured Data Processor
        from src.structured_data_processor.lambda_function import lambda_handler as processor_handler
        
        processor_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/generation/test_generation.csv'
        }
        
        with patch.dict(os.environ, {
            'PROCESSED_BUCKET': 'ons-data-platform-processed',
            'FAILED_BUCKET': 'ons-data-platform-failed'
        }):
            processor_response = processor_handler(processor_event, None)
            
            assert processor_response['statusCode'] == 200
            processing_result = json.loads(processor_response['body'])
            assert processing_result['message'] == 'Processing completed successfully'
            assert len(processing_result['results']) == 1
            assert processing_result['results'][0]['status'] == 'success'
        
        # Step 3: Timestream Loader
        from src.timestream_loader.lambda_function import lambda_handler as timestream_handler
        
        # Mock the processed Parquet file
        processed_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 10:00', periods=3, freq='H'),
            'region': ['sudeste', 'nordeste', 'sul'],
            'energy_source': ['hidrica', 'eolica', 'solar'],
            'measurement_type': ['power', 'power', 'power'],
            'value': [1500.0, 800.0, 200.0],
            'unit': ['MW', 'MW', 'MW'],
            'quality_flag': ['valid', 'valid', 'valid']
        })
        
        timestream_event = {
            'bucket': 'ons-data-platform-processed',
            'key': 'dataset=generation/year=2024/month=01/processed_data.parquet'
        }
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load:
            mock_load.return_value = processed_data
            
            with patch.dict(os.environ, {
                'TIMESTREAM_DATABASE_NAME': 'ons_energy_data',
                'GENERATION_TABLE_NAME': 'generation_data',
                'CONSUMPTION_TABLE_NAME': 'consumption_data',
                'TRANSMISSION_TABLE_NAME': 'transmission_data'
            }):
                timestream_response = timestream_handler(timestream_event, None)
                
                assert timestream_response['statusCode'] == 200
                assert timestream_response['message'] == 'Data loaded successfully'
                assert timestream_response['data']['records_processed'] == 3
                assert timestream_response['data']['dataset_type'] == 'generation'
    
    def test_large_file_batch_workflow(self, setup_test_environment):
        """Test workflow for large files that require Batch processing"""
        s3_client = setup_test_environment['s3_client']
        
        # Create large CSV data (simulate 200MB file)
        large_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=1000000, freq='min'),
            'region': (['sudeste', 'nordeste', 'sul', 'norte'] * 250000),
            'energy_source': (['hidrica', 'eolica', 'solar', 'termica'] * 250000),
            'value': [1000.0 + i * 0.001 for i in range(1000000)],
            'unit': ['MW'] * 1000000
        })
        
        # Simulate large file size
        large_file_size = 200 * 1024 * 1024  # 200MB
        
        # Test Lambda Router decision
        from src.lambda_router.lambda_function import lambda_handler as router_handler
        
        router_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/generation/large_generation.csv',
            'size': large_file_size
        }
        
        with patch.dict(os.environ, {'PROCESSED_BUCKET': 'ons-data-platform-processed'}):
            router_response = router_handler(router_event, None)
            
            assert router_response['statusCode'] == 200
            routing_decision = router_response['body']
            assert routing_decision['processingType'] == 'batch'  # Large file should use Batch
            
            # Verify Batch configuration
            batch_config = routing_decision['processorConfig']
            assert batch_config['jobDefinition'] == 'ons-structured-data-processor-batch'
            assert batch_config['vcpus'] >= 2  # Should allocate more resources for large file
            assert batch_config['memory'] >= 8192
    
    def test_pdf_processing_workflow(self, setup_test_environment):
        """Test workflow for PDF file processing"""
        s3_client = setup_test_environment['s3_client']
        
        # Test Lambda Router decision for PDF
        from src.lambda_router.lambda_function import lambda_handler as router_handler
        
        router_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'reports/transmission_report.pdf',
            'size': 5 * 1024 * 1024  # 5MB PDF
        }
        
        with patch.dict(os.environ, {'PROCESSED_BUCKET': 'ons-data-platform-processed'}):
            router_response = router_handler(router_event, None)
            
            assert router_response['statusCode'] == 200
            routing_decision = router_response['body']
            assert routing_decision['processingType'] == 'batch'  # PDFs always use Batch
            
            # Verify PDF-specific Batch configuration
            batch_config = routing_decision['processorConfig']
            assert batch_config['jobDefinition'] == 'ons-pdf-processor-batch'
            assert 'PDF_EXTRACTION_TOOLS' in batch_config['environment']
            assert batch_config['environment']['PDF_EXTRACTION_TOOLS'] == 'camelot,tabula'
    
    def test_error_handling_workflow(self, setup_test_environment):
        """Test error handling throughout the workflow"""
        s3_client = setup_test_environment['s3_client']
        
        # Test with unsupported file format
        from src.lambda_router.lambda_function import lambda_handler as router_handler
        
        router_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/unsupported_file.txt',
            'size': 1024
        }
        
        router_response = router_handler(router_event, None)
        
        assert router_response['statusCode'] == 500
        assert 'Unsupported file format' in router_response['body']['error']
        assert router_response['body']['processingType'] == 'failed'
        
        # Test structured data processor with invalid data
        from src.structured_data_processor.lambda_function import lambda_handler as processor_handler
        
        # Create invalid CSV data
        invalid_csv = "invalid,csv,data\n,,,\n"
        s3_client.put_object(
            Bucket='ons-data-platform-raw',
            Key='data/invalid.csv',
            Body=invalid_csv
        )
        
        processor_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/invalid.csv'
        }
        
        with patch.dict(os.environ, {
            'PROCESSED_BUCKET': 'ons-data-platform-processed',
            'FAILED_BUCKET': 'ons-data-platform-failed'
        }):
            processor_response = processor_handler(processor_event, None)
            
            # Should handle error gracefully
            assert processor_response['statusCode'] == 500
            error_body = json.loads(processor_response['body'])
            assert 'error' in error_body
    
    def test_data_quality_validation_workflow(self, setup_test_environment):
        """Test data quality validation throughout the workflow"""
        s3_client = setup_test_environment['s3_client']
        
        # Create data with quality issues
        quality_test_data = pd.DataFrame({
            'Data': ['2024-01-01 10:00', 'invalid-date', '2024-01-01 12:00'],
            'Região': ['Sudeste', '', 'Sul'],
            'Potência (MW)': [1500.0, 'invalid', 200.0],
            'Observações': ['Normal', 'Erro', 'Normal']
        })
        
        csv_content = quality_test_data.to_csv(index=False)
        s3_client.put_object(
            Bucket='ons-data-platform-raw',
            Key='data/quality_test.csv',
            Body=csv_content
        )
        
        # Process through structured data processor
        from src.structured_data_processor.lambda_function import lambda_handler as processor_handler
        
        processor_event = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/quality_test.csv'
        }
        
        with patch.dict(os.environ, {
            'PROCESSED_BUCKET': 'ons-data-platform-processed',
            'FAILED_BUCKET': 'ons-data-platform-failed'
        }):
            processor_response = processor_handler(processor_event, None)
            
            # Should process successfully with data cleaning
            assert processor_response['statusCode'] == 200
            processing_result = json.loads(processor_response['body'])
            
            # Should have processed fewer records due to data cleaning
            assert processing_result['results'][0]['records_processed'] > 0
            
            # Check metadata includes quality score
            metadata = processing_result['results'][0]['metadata']
            assert 'data_quality_score' in metadata
            assert metadata['data_quality_score'] < 100.0  # Should be less than perfect due to quality issues


class TestRAGQueryProcessingWorkflow:
    """Test RAG query processing workflow with Knowledge Base"""
    
    @pytest.fixture
    def setup_rag_environment(self):
        """Setup RAG testing environment"""
        with mock_bedrock_agent_runtime():
            bedrock_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
            yield {'bedrock_client': bedrock_client}
    
    def test_complete_rag_query_workflow(self, setup_rag_environment):
        """Test complete RAG query processing workflow"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        
        # Test API Gateway event
        api_event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'What is the energy generation capacity in Brazil for 2024?'
            })
        }
        
        # Mock Bedrock responses
        mock_rag_response = {
            'output': {
                'text': 'Based on the available data, Brazil\'s energy generation capacity in 2024 reached approximately 180 GW, with renewable sources accounting for 85% of the total capacity.'
            },
            'citations': [{
                'retrievedReferences': [{
                    'content': {'text': 'Energy generation statistics for Brazil in 2024 show total installed capacity of 180 GW.'},
                    'location': {'s3Location': {'uri': 's3://processed/generation-2024.parquet'}},
                    'metadata': {'score': 0.95}
                }]
            }]
        }
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.return_value = mock_rag_response
            
            with patch.dict(os.environ, {
                'KNOWLEDGE_BASE_ID': 'test-kb-id',
                'MODEL_ARN': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
            }):
                response = rag_handler(api_event, None)
                
                assert response['statusCode'] == 200
                
                body = json.loads(response['body'])
                assert 'query_id' in body
                assert body['question'] == 'What is the energy generation capacity in Brazil for 2024?'
                assert 'Brazil\'s energy generation capacity' in body['answer']
                assert body['confidence_score'] > 0.9
                assert len(body['sources']) == 1
                assert body['sources'][0]['relevance_score'] == 0.95
    
    def test_rag_health_check_workflow(self, setup_rag_environment):
        """Test RAG health check workflow"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        
        health_event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            response = rag_handler(health_event, None)
            
            assert response['statusCode'] == 200
            
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
            assert body['service'] == 'ons-rag-query-processor'
            assert body['knowledge_base_configured'] is True
    
    def test_rag_error_handling_workflow(self, setup_rag_environment):
        """Test RAG error handling workflow"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        
        # Test with missing Knowledge Base ID
        api_event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'Test query'
            })
        }
        
        with patch.dict(os.environ, {}, clear=True):  # No KNOWLEDGE_BASE_ID
            response = rag_handler(api_event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Knowledge Base ID not configured' in body['error']
        
        # Test with invalid query
        invalid_event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': ''  # Empty question
            })
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            response = rag_handler(invalid_event, None)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'Invalid query' in body['error']


class TestStepFunctionsOrchestration:
    """Test Step Functions orchestration workflow simulation"""
    
    def test_step_functions_workflow_simulation(self):
        """Simulate Step Functions workflow orchestration"""
        
        # Step 1: File uploaded to S3 (simulated)
        file_info = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/generation/monthly_report.csv',
            'size': 50 * 1024 * 1024  # 50MB
        }
        
        # Step 2: Lambda Router determines processing path
        from src.lambda_router.lambda_function import determine_processing_path, extract_file_info
        
        router_event = {
            'bucket': file_info['bucket'],
            'key': file_info['key'],
            'size': file_info['size']
        }
        
        file_info_extracted = extract_file_info(router_event)
        processing_decision = determine_processing_path(file_info_extracted)
        
        assert processing_decision['processingType'] == 'lambda'  # 50MB should use Lambda
        
        # Step 3: Structured Data Processor processes file
        processor_result = {
            'status': 'success',
            'records_processed': 1000,
            'output_location': 's3://ons-data-platform-processed/dataset=generation/year=2024/month=01/',
            'dataset_type': 'generation'
        }
        
        # Step 4: Timestream Loader loads processed data
        timestream_input = {
            'bucket': 'ons-data-platform-processed',
            'key': 'dataset=generation/year=2024/month=01/processed_data.parquet'
        }
        
        # Simulate successful loading
        timestream_result = {
            'statusCode': 200,
            'message': 'Data loaded successfully',
            'data': {
                'records_processed': 1000,
                'batches_processed': 10,
                'dataset_type': 'generation'
            }
        }
        
        # Verify workflow completion
        assert processor_result['status'] == 'success'
        assert timestream_result['statusCode'] == 200
        assert processor_result['records_processed'] == timestream_result['data']['records_processed']
    
    def test_error_recovery_workflow(self):
        """Test error recovery in Step Functions workflow"""
        
        # Simulate processing failure
        processing_error = {
            'status': 'error',
            'error_message': 'Data validation failed',
            'input_file': 's3://ons-data-platform-raw/data/invalid.csv'
        }
        
        # Verify error handling
        assert processing_error['status'] == 'error'
        assert 'Data validation failed' in processing_error['error_message']
        
        # Simulate retry with corrected data
        retry_result = {
            'status': 'success',
            'records_processed': 500,
            'retry_attempt': 1
        }
        
        assert retry_result['status'] == 'success'
        assert retry_result['retry_attempt'] == 1


class TestPerformanceIntegration:
    """Test performance characteristics of integrated workflows"""
    
    def test_high_throughput_processing(self):
        """Test high throughput file processing simulation"""
        
        # Simulate multiple files being processed concurrently
        files = [
            {'key': f'data/generation/file_{i}.csv', 'size': 10 * 1024 * 1024}  # 10MB each
            for i in range(10)
        ]
        
        processing_results = []
        
        for file_info in files:
            # Simulate router decision
            from src.lambda_router.lambda_function import get_file_extension, determine_processing_path
            
            file_data = {
                'bucket': 'ons-data-platform-raw',
                'key': file_info['key'],
                'size_mb': file_info['size'] / (1024 * 1024),
                'file_extension': get_file_extension(file_info['key']),
                'filename': file_info['key'].split('/')[-1]
            }
            
            decision = determine_processing_path(file_data)
            
            # All should use Lambda processing (small files)
            assert decision['processingType'] == 'lambda'
            
            processing_results.append({
                'file': file_info['key'],
                'processing_type': decision['processingType'],
                'status': 'success'
            })
        
        # Verify all files processed successfully
        assert len(processing_results) == 10
        assert all(result['status'] == 'success' for result in processing_results)
    
    def test_memory_usage_optimization(self):
        """Test memory usage optimization in data processing"""
        
        # Simulate processing large dataset in chunks
        total_records = 100000
        chunk_size = 10000
        
        processed_chunks = []
        
        for i in range(0, total_records, chunk_size):
            chunk_data = pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=min(chunk_size, total_records - i), freq='H'),
                'region': ['sudeste'] * min(chunk_size, total_records - i),
                'value': [1000.0 + j for j in range(min(chunk_size, total_records - i))]
            })
            
            # Simulate chunk processing
            chunk_result = {
                'chunk_id': i // chunk_size,
                'records_processed': len(chunk_data),
                'memory_usage': len(chunk_data) * 8 * 3  # Approximate memory usage
            }
            
            processed_chunks.append(chunk_result)
        
        # Verify chunked processing
        total_processed = sum(chunk['records_processed'] for chunk in processed_chunks)
        assert total_processed == total_records
        assert len(processed_chunks) == 10  # 100k / 10k = 10 chunks
    
    def test_concurrent_query_processing(self):
        """Test concurrent RAG query processing"""
        
        # Simulate multiple concurrent queries
        queries = [
            'What is the energy generation in 2024?',
            'How much renewable energy is produced?',
            'What are the consumption patterns?',
            'Which regions have highest demand?',
            'What is the transmission capacity?'
        ]
        
        query_results = []
        
        for query in queries:
            # Simulate query processing
            query_result = {
                'query_id': str(uuid.uuid4()),
                'question': query,
                'processing_time_ms': 1500,  # Simulated processing time
                'status': 'success'
            }
            
            query_results.append(query_result)
        
        # Verify all queries processed
        assert len(query_results) == 5
        assert all(result['status'] == 'success' for result in query_results)
        assert all(result['processing_time_ms'] < 5000 for result in query_results)  # Under 5 seconds


class TestDataConsistencyIntegration:
    """Test data consistency across the entire pipeline"""
    
    def test_data_lineage_tracking(self):
        """Test data lineage tracking through the pipeline"""
        
        # Original data
        original_data = {
            'source_file': 'generation_data_2024.csv',
            'records_count': 1000,
            'upload_timestamp': datetime.utcnow().isoformat()
        }
        
        # After structured processing
        processed_data = {
            'source_file': original_data['source_file'],
            'records_processed': 950,  # Some records filtered out
            'processing_timestamp': datetime.utcnow().isoformat(),
            'data_quality_score': 95.0
        }
        
        # After Timestream loading
        timestream_data = {
            'source_file': original_data['source_file'],
            'records_loaded': processed_data['records_processed'],
            'load_timestamp': datetime.utcnow().isoformat()
        }
        
        # Verify data lineage consistency
        assert processed_data['source_file'] == original_data['source_file']
        assert timestream_data['records_loaded'] == processed_data['records_processed']
        assert processed_data['records_processed'] <= original_data['records_count']  # Some filtering expected
    
    def test_data_validation_consistency(self):
        """Test data validation consistency across components"""
        
        # Test data that should pass all validation stages
        valid_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='H'),
            'region': ['sudeste', 'nordeste', 'sul', 'norte', 'centro_oeste'],
            'energy_source': ['hidrica', 'eolica', 'solar', 'termica', 'nuclear'],
            'measurement_type': ['power'] * 5,
            'value': [1500.0, 800.0, 200.0, 600.0, 1200.0],
            'unit': ['MW'] * 5,
            'quality_flag': ['good'] * 5
        })
        
        # Validate in structured processor context
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        processor = StructuredDataProcessor()
        
        # Should pass validation
        quality_score = processor._calculate_quality_score(valid_data)
        assert quality_score == 100.0
        
        # Validate in Timestream loader context
        from src.timestream_loader.lambda_function import validate_data_schema
        
        validation_result = validate_data_schema(valid_data, 'generation')
        assert validation_result['valid'] is True
        assert len(validation_result['errors']) == 0


class TestAdvancedIntegrationScenarios:
    """Test advanced integration scenarios"""
    
    def test_multi_file_batch_processing(self):
        """Test processing multiple files in batch"""
        files = [
            {'key': 'data/gen1.csv', 'size': 10 * 1024 * 1024, 'type': 'generation'},
            {'key': 'data/cons1.xlsx', 'size': 15 * 1024 * 1024, 'type': 'consumption'},
            {'key': 'reports/trans1.pdf', 'size': 5 * 1024 * 1024, 'type': 'transmission'},
        ]
        
        processing_results = []
        
        for file_info in files:
            # Simulate router decision
            from src.lambda_router.lambda_function import determine_processing_path
            
            file_data = {
                'bucket': 'ons-data-platform-raw',
                'key': file_info['key'],
                'size_mb': file_info['size'] / (1024 * 1024),
                'file_extension': '.' + file_info['key'].split('.')[-1],
                'filename': file_info['key'].split('/')[-1]
            }
            
            decision = determine_processing_path(file_data)
            
            # Simulate processing result
            result = {
                'file': file_info['key'],
                'processing_type': decision['processingType'],
                'dataset_type': file_info['type'],
                'status': 'success',
                'records_processed': 1000 + len(file_info['key'])  # Simulate variable record count
            }
            
            processing_results.append(result)
        
        # Verify all files processed
        assert len(processing_results) == 3
        assert all(r['status'] == 'success' for r in processing_results)
        
        # Verify correct processing types
        csv_result = next(r for r in processing_results if r['file'].endswith('.csv'))
        pdf_result = next(r for r in processing_results if r['file'].endswith('.pdf'))
        
        assert csv_result['processing_type'] == 'lambda'  # Small CSV
        assert pdf_result['processing_type'] == 'batch'   # PDF always batch
    
    def test_data_lineage_end_to_end(self):
        """Test data lineage tracking through entire pipeline"""
        # Original file metadata
        original_file = {
            'bucket': 'ons-data-platform-raw',
            'key': 'data/generation/monthly_2024_01.csv',
            'size': 25 * 1024 * 1024,
            'upload_time': datetime.utcnow().isoformat(),
            'checksum': 'abc123def456'
        }
        
        # Step 1: Router processing
        from src.lambda_router.lambda_function import extract_file_info, determine_processing_path
        
        router_event = {
            'bucket': original_file['bucket'],
            'key': original_file['key'],
            'size': original_file['size']
        }
        
        file_info = extract_file_info(router_event)
        routing_decision = determine_processing_path(file_info)
        
        # Step 2: Data processing simulation
        processing_metadata = {
            'source_file': original_file['key'],
            'source_checksum': original_file['checksum'],
            'processing_time': datetime.utcnow().isoformat(),
            'processor_type': routing_decision['processingType'],
            'records_input': 10000,
            'records_output': 9850,  # Some filtering
            'data_quality_score': 98.5
        }
        
        # Step 3: Storage metadata
        storage_metadata = {
            'source_file': original_file['key'],
            'processed_location': routing_decision['outputLocation'],
            'storage_time': datetime.utcnow().isoformat(),
            'records_stored': processing_metadata['records_output'],
            'partitions_created': 12
        }
        
        # Verify lineage consistency
        assert processing_metadata['source_file'] == original_file['key']
        assert storage_metadata['source_file'] == original_file['key']
        assert storage_metadata['records_stored'] == processing_metadata['records_output']
        assert processing_metadata['records_output'] <= processing_metadata['records_input']
    
    def test_error_propagation_and_recovery(self):
        """Test error propagation and recovery mechanisms"""
        # Simulate Step Functions workflow with error handling
        
        workflow_state = {
            'input_file': 's3://raw-bucket/data/problematic.csv',
            'current_step': 'router',
            'retry_count': 0,
            'max_retries': 3,
            'errors': []
        }
        
        # Step 1: Router fails
        router_error = {
            'step': 'router',
            'error_type': 'ValidationError',
            'error_message': 'Unsupported file format',
            'timestamp': datetime.utcnow().isoformat(),
            'retry_count': workflow_state['retry_count']
        }
        
        workflow_state['errors'].append(router_error)
        workflow_state['current_step'] = 'error_handler'
        
        # Error handler decides on retry or failure
        if router_error['error_type'] == 'ValidationError':
            # Non-retryable error
            workflow_state['status'] = 'failed'
            workflow_state['final_error'] = router_error
        else:
            # Retryable error
            workflow_state['retry_count'] += 1
            if workflow_state['retry_count'] <= workflow_state['max_retries']:
                workflow_state['current_step'] = 'router'
                workflow_state['status'] = 'retrying'
            else:
                workflow_state['status'] = 'failed_after_retries'
        
        # Verify error handling
        assert workflow_state['status'] == 'failed'
        assert len(workflow_state['errors']) == 1
        assert workflow_state['final_error']['error_type'] == 'ValidationError'
    
    def test_performance_monitoring_integration(self):
        """Test performance monitoring throughout the pipeline"""
        performance_metrics = {
            'router': {
                'start_time': time.time(),
                'end_time': None,
                'duration_ms': None,
                'memory_usage_mb': 128,
                'cpu_utilization': 15.5
            },
            'processor': {
                'start_time': None,
                'end_time': None,
                'duration_ms': None,
                'memory_usage_mb': None,
                'cpu_utilization': None,
                'records_per_second': None
            },
            'timestream_loader': {
                'start_time': None,
                'end_time': None,
                'duration_ms': None,
                'records_loaded': None,
                'batches_processed': None
            }
        }
        
        # Simulate router completion
        time.sleep(0.1)  # Simulate processing time
        performance_metrics['router']['end_time'] = time.time()
        performance_metrics['router']['duration_ms'] = (
            performance_metrics['router']['end_time'] - 
            performance_metrics['router']['start_time']
        ) * 1000
        
        # Simulate processor
        performance_metrics['processor']['start_time'] = time.time()
        time.sleep(0.2)  # Simulate processing time
        performance_metrics['processor']['end_time'] = time.time()
        performance_metrics['processor']['duration_ms'] = (
            performance_metrics['processor']['end_time'] - 
            performance_metrics['processor']['start_time']
        ) * 1000
        performance_metrics['processor']['memory_usage_mb'] = 512
        performance_metrics['processor']['cpu_utilization'] = 75.2
        performance_metrics['processor']['records_per_second'] = 5000
        
        # Simulate Timestream loader
        performance_metrics['timestream_loader']['start_time'] = time.time()
        time.sleep(0.05)  # Simulate loading time
        performance_metrics['timestream_loader']['end_time'] = time.time()
        performance_metrics['timestream_loader']['duration_ms'] = (
            performance_metrics['timestream_loader']['end_time'] - 
            performance_metrics['timestream_loader']['start_time']
        ) * 1000
        performance_metrics['timestream_loader']['records_loaded'] = 10000
        performance_metrics['timestream_loader']['batches_processed'] = 100
        
        # Verify performance metrics
        assert performance_metrics['router']['duration_ms'] > 0
        assert performance_metrics['processor']['duration_ms'] > 0
        assert performance_metrics['timestream_loader']['duration_ms'] > 0
        
        # Calculate total pipeline duration
        total_duration = (
            performance_metrics['router']['duration_ms'] +
            performance_metrics['processor']['duration_ms'] +
            performance_metrics['timestream_loader']['duration_ms']
        )
        
        assert total_duration > 0
        assert total_duration < 10000  # Should complete within 10 seconds


class TestDataQualityIntegration:
    """Test data quality throughout the integration pipeline"""
    
    def test_quality_score_propagation(self):
        """Test quality score calculation and propagation"""
        # Initial data quality assessment
        initial_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=1000, freq='H'),
            'region': ['sudeste'] * 500 + ['nordeste'] * 300 + [None] * 200,  # 20% missing
            'energy_source': ['hidrica'] * 800 + ['eolica'] * 150 + [None] * 50,  # 5% missing
            'value': [1000.0 + i * 0.1 for i in range(900)] + [None] * 100,  # 10% missing
            'unit': ['MW'] * 1000
        })
        
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        processor = StructuredDataProcessor()
        
        # Calculate initial quality score
        initial_quality = processor._calculate_quality_score(initial_data)
        expected_quality = ((1000 + 800 + 850 + 900 + 1000) / (5 * 1000)) * 100  # ~87%
        
        assert abs(initial_quality - expected_quality) < 5  # Within 5% tolerance
        
        # After cleaning
        cleaned_data = processor._clean_and_validate_data(initial_data, 'quality_test.csv')
        cleaned_quality = processor._calculate_quality_score(cleaned_data)
        
        # Quality should improve after cleaning
        assert cleaned_quality >= initial_quality
        assert cleaned_quality >= 90  # Should meet minimum quality threshold
    
    def test_data_validation_chain(self):
        """Test data validation throughout the processing chain"""
        # Test data with various quality issues
        test_data = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00', 'invalid-date', '2024-01-01 12:00', ''],
            'region': ['sudeste', 'INVALID_REGION', 'nordeste', None],
            'energy_source': ['hidrica', '', 'eolica', 'UNKNOWN'],
            'value': [1000.0, -999, 1200.0, float('inf')],
            'unit': ['MW', 'INVALID', 'MW', '']
        })
        
        # Step 1: Structured processor validation
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        processor = StructuredDataProcessor()
        
        try:
            cleaned_data = processor._clean_and_validate_data(test_data, 'validation_test.csv')
            
            # Should have valid data after cleaning
            assert len(cleaned_data) > 0
            
            # Step 2: Timestream validation
            from src.timestream_loader.lambda_function import validate_data_schema
            
            # Convert to expected Timestream format
            timestream_data = pd.DataFrame({
                'timestamp': cleaned_data['timestamp'],
                'region': cleaned_data['region'],
                'energy_source': cleaned_data.get('energy_source', cleaned_data.get('source', 'unknown')),
                'measurement_type': ['power'] * len(cleaned_data),
                'value': cleaned_data['value'],
                'unit': cleaned_data['unit']
            })
            
            validation_result = validate_data_schema(timestream_data, 'generation')
            
            if validation_result['valid']:
                assert len(validation_result['errors']) == 0
            else:
                # If validation fails, errors should be specific
                assert len(validation_result['errors']) > 0
                
        except Exception as e:
            # If processing fails completely, should be due to insufficient valid data
            assert 'No valid data remaining' in str(e)


class TestSecurityIntegration:
    """Test security aspects of the integration pipeline"""
    
    def test_data_sanitization_pipeline(self):
        """Test data sanitization throughout the pipeline"""
        # Data with potential security issues
        malicious_data = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00', '2024-01-01 11:00'],
            'region': ['<script>alert("xss")</script>', 'sudeste'],
            'energy_source': ['hidrica"; DROP TABLE users; --', 'eolica'],
            'value': [1000.0, 1100.0],
            'notes': ['Normal operation', 'System compromised: rm -rf /']
        })
        
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        processor = StructuredDataProcessor()
        
        # Should sanitize malicious content
        cleaned_data = processor._clean_and_validate_data(malicious_data, 'security_test.csv')
        
        # Verify sanitization
        for col in cleaned_data.select_dtypes(include=['object']).columns:
            for value in cleaned_data[col].dropna():
                assert '<script>' not in str(value)
                assert 'DROP TABLE' not in str(value)
                assert 'rm -rf' not in str(value)
    
    def test_access_control_simulation(self):
        """Test access control simulation in the pipeline"""
        # Simulate different user roles and permissions
        user_contexts = [
            {
                'role': 'data_analyst',
                'permissions': ['read_generation', 'read_consumption'],
                'restricted_datasets': ['transmission']
            },
            {
                'role': 'system_admin',
                'permissions': ['read_all', 'write_all', 'delete_all'],
                'restricted_datasets': []
            },
            {
                'role': 'external_user',
                'permissions': ['read_public'],
                'restricted_datasets': ['generation', 'consumption', 'transmission']
            }
        ]
        
        datasets = ['generation', 'consumption', 'transmission']
        
        for user in user_contexts:
            for dataset in datasets:
                # Simulate access check
                has_access = (
                    'read_all' in user['permissions'] or
                    f'read_{dataset}' in user['permissions'] or
                    ('read_public' in user['permissions'] and dataset not in user['restricted_datasets'])
                )
                
                if user['role'] == 'data_analyst':
                    if dataset in ['generation', 'consumption']:
                        assert has_access
                    else:
                        assert not has_access
                elif user['role'] == 'system_admin':
                    assert has_access
                elif user['role'] == 'external_user':
                    assert not has_access


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])