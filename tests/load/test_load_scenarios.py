"""
Load Testing Scenarios for ONS Data Platform
Tests system behavior under various load conditions
"""

import pytest
import time
import concurrent.futures
import threading
import queue
import statistics
from unittest.mock import patch
import sys
import os

# Add source paths
sys.path.insert(0, 'src/rag_query_processor')
sys.path.insert(0, 'src/structured_data_processor')


class TestHighVolumeDataProcessing:
    """Test high volume data processing scenarios"""
    
    def test_concurrent_file_processing(self):
        """Test concurrent processing of multiple files"""
        from src.lambda_router.lambda_function import determine_processing_path
        
        # Simulate 50 files being processed concurrently
        files = [
            {
                'bucket': 'test-bucket',
                'key': f'data/file_{i}.csv',
                'size_mb': 10 + (i % 20),  # Varying sizes
                'file_extension': '.csv',
                'filename': f'file_{i}.csv'
            }
            for i in range(50)
        ]
        
        def process_file(file_info):
            start_time = time.time()
            decision = determine_processing_path(file_info)
            end_time = time.time()
            
            return {
                'file': file_info['filename'],
                'processing_type': decision['processingType'],
                'response_time': (end_time - start_time) * 1000,
                'success': True
            }
        
        # Process files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            start_time = time.time()
            futures = [executor.submit(process_file, file_info) for file_info in files]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time
        
        # Analyze results
        successful_results = [r for r in results if r['success']]
        assert len(successful_results) == 50
        
        throughput = len(successful_results) / total_time
        assert throughput > 20  # Should process at least 20 files per second
        
        avg_response_time = statistics.mean([r['response_time'] for r in successful_results])
        assert avg_response_time < 100  # Average under 100ms per file  
  def test_sustained_query_load(self):
        """Test sustained query load over time"""
        from src.rag_query_processor.lambda_function import lambda_handler as rag_handler
        import json
        
        duration_seconds = 30
        queries_per_second = 5
        total_queries = duration_seconds * queries_per_second
        
        results = []
        start_time = time.time()
        
        def make_query(query_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Load test query {query_id}'})
            }
            
            mock_response = {
                'output': {'text': f'Response {query_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    query_start = time.time()
                    response = rag_handler(event, None)
                    query_end = time.time()
                    
                    return {
                        'query_id': query_id,
                        'response_time': (query_end - query_start) * 1000,
                        'status_code': response['statusCode'],
                        'timestamp': query_start
                    }
        
        # Execute sustained load
        for i in range(total_queries):
            if i % 10 == 0:  # Every 10th query, use thread pool for burst
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    batch_futures = [executor.submit(make_query, i + j) for j in range(min(5, total_queries - i))]
                    batch_results = [f.result() for f in concurrent.futures.as_completed(batch_futures)]
                    results.extend(batch_results)
                    i += len(batch_results) - 1
            else:
                result = make_query(i)
                results.append(result)
            
            # Control rate
            elapsed = time.time() - start_time
            expected_time = i / queries_per_second
            if elapsed < expected_time:
                time.sleep(expected_time - elapsed)
        
        total_duration = time.time() - start_time
        
        # Analyze sustained load performance
        successful_queries = [r for r in results if r['status_code'] == 200]
        actual_throughput = len(successful_queries) / total_duration
        
        assert len(successful_queries) >= total_queries * 0.95  # 95% success rate
        assert actual_throughput >= queries_per_second * 0.8  # 80% of target throughput


class TestMemoryStressScenarios:
    """Test memory stress scenarios"""
    
    def test_large_dataset_processing(self):
        """Test processing of large datasets"""
        import pandas as pd
        from src.structured_data_processor.lambda_function import StructuredDataProcessor
        
        processor = StructuredDataProcessor()
        
        # Create large dataset (100k records)
        large_dataset = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100000, freq='min'),
            'region': (['sudeste', 'nordeste', 'sul', 'norte'] * 25000),
            'energy_source': (['hidrica', 'eolica', 'solar', 'termica'] * 25000),
            'value': [1000.0 + i * 0.01 for i in range(100000)],
            'unit': ['MW'] * 100000
        })
        
        # Process in chunks to test memory management
        chunk_size = 10000
        processed_chunks = []
        
        for i in range(0, len(large_dataset), chunk_size):
            chunk = large_dataset.iloc[i:i + chunk_size]
            
            # Simulate processing
            try:
                cleaned_chunk = processor._clean_and_validate_data(chunk, f'chunk_{i}.csv')
                processed_chunks.append(len(cleaned_chunk))
            except Exception as e:
                # Should handle memory pressure gracefully
                assert 'memory' in str(e).lower() or 'out of' in str(e).lower()
        
        # Verify chunked processing
        total_processed = sum(processed_chunks)
        assert total_processed > 90000  # Should process most records
        assert len(processed_chunks) == 10  # Should process all chunks


class TestConcurrencyStressTests:
    """Test concurrency stress scenarios"""
    
    def test_thread_safety_under_load(self):
        """Test thread safety under concurrent load"""
        shared_counter = {'value': 0}
        lock = threading.Lock()
        errors = queue.Queue()
        
        def concurrent_operation(thread_id):
            try:
                for i in range(100):
                    # Simulate concurrent access to shared resource
                    with lock:
                        current_value = shared_counter['value']
                        time.sleep(0.001)  # Simulate processing time
                        shared_counter['value'] = current_value + 1
                
                return {'thread_id': thread_id, 'success': True}
            except Exception as e:
                errors.put({'thread_id': thread_id, 'error': str(e)})
                return {'thread_id': thread_id, 'success': False}
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify thread safety
        successful_threads = [r for r in results if r['success']]
        assert len(successful_threads) == 20
        assert shared_counter['value'] == 2000  # 20 threads * 100 operations
        assert errors.empty()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])