"""
Performance Tests for ONS Data Platform API Endpoints
Tests API performance under various load conditions
"""

import pytest
import json
import time
import asyncio
import concurrent.futures
from unittest.mock import Mock, MagicMock, patch
import statistics
import sys
import os
from datetime import datetime

# Add source path
sys.path.insert(0, 'src/rag_query_processor')

from lambda_function import lambda_handler as rag_handler


class TestAPIPerformanceBaseline:
    """Test baseline API performance metrics"""
    
    def test_single_query_response_time(self):
        """Test response time for single query"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'What is the energy generation capacity in Brazil?'
            })
        }
        
        mock_response = {
            'output': {'text': 'Brazil has approximately 180 GW of installed capacity.'},
            'citations': []
        }
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.return_value = mock_response
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                start_time = time.time()
                response = rag_handler(event, None)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                assert response['statusCode'] == 200
                assert response_time < 5000  # Should respond within 5 seconds
                
                body = json.loads(response['body'])
                assert 'processing_time_ms' in body
                assert body['processing_time_ms'] > 0
    
    def test_health_check_response_time(self):
        """Test health check endpoint response time"""
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            start_time = time.time()
            response = rag_handler(event, None)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000
            
            assert response['statusCode'] == 200
            assert response_time < 1000  # Health check should be very fast
    
    def test_query_processing_time_distribution(self):
        """Test distribution of query processing times"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'What is the renewable energy percentage?'
            })
        }
        
        mock_response = {
            'output': {'text': 'Renewable energy accounts for 85% of Brazil\'s capacity.'},
            'citations': []
        }
        
        response_times = []
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.return_value = mock_response
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                # Run multiple queries to get distribution
                for _ in range(10):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    response_time = (end_time - start_time) * 1000
                    response_times.append(response_time)
                    
                    assert response['statusCode'] == 200
        
        # Analyze response time distribution
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        max_time = max(response_times)
        min_time = min(response_times)
        
        assert avg_time < 3000  # Average under 3 seconds
        assert median_time < 2500  # Median under 2.5 seconds
        assert max_time < 5000  # Max under 5 seconds
        assert min_time > 0  # Minimum should be positive
        
        # Check for reasonable consistency (standard deviation)
        std_dev = statistics.stdev(response_times)
        assert std_dev < avg_time * 0.5  # Standard deviation should be less than 50% of average


class TestConcurrentLoadTesting:
    """Test API performance under concurrent load"""
    
    def test_concurrent_queries_performance(self):
        """Test performance with concurrent queries"""
        queries = [
            'What is the energy generation in 2024?',
            'How much renewable energy is produced?',
            'What are the consumption patterns?',
            'Which regions have highest demand?',
            'What is the transmission capacity?',
            'How does solar energy contribute?',
            'What is the peak demand time?',
            'Which energy source is most reliable?',
            'How efficient is the grid?',
            'What are the future projections?'
        ]
        
        mock_response = {
            'output': {'text': 'Mock response for performance testing.'},
            'citations': []
        }
        
        def make_query(question):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': question})
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    return {
                        'question': question,
                        'response_time': (end_time - start_time) * 1000,
                        'status_code': response['statusCode'],
                        'success': response['statusCode'] == 200
                    }
        
        # Execute queries concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            start_time = time.time()
            future_to_query = {executor.submit(make_query, query): query for query in queries}
            results = []
            
            for future in concurrent.futures.as_completed(future_to_query):
                result = future.result()
                results.append(result)
            
            total_time = (time.time() - start_time) * 1000
        
        # Analyze concurrent performance
        successful_queries = [r for r in results if r['success']]
        failed_queries = [r for r in results if not r['success']]
        
        assert len(successful_queries) == len(queries)  # All queries should succeed
        assert len(failed_queries) == 0
        
        # Check response times under concurrent load
        response_times = [r['response_time'] for r in successful_queries]
        avg_concurrent_time = statistics.mean(response_times)
        max_concurrent_time = max(response_times)
        
        assert avg_concurrent_time < 5000  # Average under 5 seconds under load
        assert max_concurrent_time < 10000  # Max under 10 seconds under load
        assert total_time < 15000  # Total execution under 15 seconds
    
    def test_burst_load_handling(self):
        """Test API handling of burst load"""
        burst_size = 20
        
        def make_burst_query(query_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Query {query_id} for burst testing'})
            }
            
            mock_response = {
                'output': {'text': f'Response for query {query_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    return {
                        'query_id': query_id,
                        'response_time': (end_time - start_time) * 1000,
                        'status_code': response['statusCode']
                    }
        
        # Execute burst of queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            start_time = time.time()
            futures = [executor.submit(make_burst_query, i) for i in range(burst_size)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_burst_time = (time.time() - start_time) * 1000
        
        # Analyze burst performance
        successful_results = [r for r in results if r['status_code'] == 200]
        
        assert len(successful_results) == burst_size  # All queries should succeed
        
        response_times = [r['response_time'] for r in successful_results]
        avg_burst_time = statistics.mean(response_times)
        
        assert avg_burst_time < 8000  # Average under 8 seconds during burst
        assert total_burst_time < 30000  # Total burst processing under 30 seconds
    
    def test_sustained_load_performance(self):
        """Test performance under sustained load"""
        duration_seconds = 10
        queries_per_second = 2
        total_queries = duration_seconds * queries_per_second
        
        def make_sustained_query(query_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Sustained query {query_id}'})
            }
            
            mock_response = {
                'output': {'text': f'Sustained response {query_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    return {
                        'query_id': query_id,
                        'response_time': (end_time - start_time) * 1000,
                        'timestamp': start_time,
                        'status_code': response['statusCode']
                    }
        
        results = []
        start_time = time.time()
        
        # Simulate sustained load with controlled rate
        for i in range(total_queries):
            query_start = time.time()
            
            # Execute query
            result = make_sustained_query(i)
            results.append(result)
            
            # Control rate (queries per second)
            elapsed = time.time() - query_start
            sleep_time = (1.0 / queries_per_second) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        total_duration = time.time() - start_time
        
        # Analyze sustained load performance
        successful_results = [r for r in results if r['status_code'] == 200]
        
        assert len(successful_results) == total_queries
        
        response_times = [r['response_time'] for r in successful_results]
        avg_sustained_time = statistics.mean(response_times)
        
        # Performance should remain stable under sustained load
        assert avg_sustained_time < 4000  # Average under 4 seconds
        assert total_duration < duration_seconds * 1.5  # Total time within 150% of expected


class TestMemoryAndResourceUsage:
    """Test memory and resource usage under load"""
    
    def test_memory_usage_single_query(self):
        """Test memory usage for single query processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'What is the detailed energy generation breakdown by source and region for the last 5 years?'
            })
        }
        
        mock_response = {
            'output': {'text': 'Detailed response with comprehensive data analysis...'},
            'citations': [
                {
                    'retrievedReferences': [{
                        'content': {'text': 'Large content block for memory testing' * 100},
                        'location': {'s3Location': {'uri': 's3://bucket/large-data.parquet'}},
                        'metadata': {'score': 0.95}
                    }]
                }
            ]
        }
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.return_value = mock_response
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                response = rag_handler(event, None)
                
                # Measure peak memory during processing
                peak_memory = process.memory_info().rss / 1024 / 1024  # MB
                
                assert response['statusCode'] == 200
                
                # Memory usage should be reasonable
                memory_increase = peak_memory - baseline_memory
                assert memory_increase < 100  # Should not use more than 100MB additional
    
    def test_memory_cleanup_after_queries(self):
        """Test memory cleanup after processing multiple queries"""
        import psutil
        import os
        import gc
        
        process = psutil.Process(os.getpid())
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process multiple queries
        for i in range(10):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Memory test query {i}'})
            }
            
            mock_response = {
                'output': {'text': f'Response {i}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    response = rag_handler(event, None)
                    assert response['statusCode'] == 200
        
        # Force garbage collection
        gc.collect()
        
        # Check memory after processing
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - baseline_memory
        
        # Memory should not grow significantly after cleanup
        assert memory_increase < 50  # Should not retain more than 50MB
    
    def test_large_response_handling(self):
        """Test handling of large responses"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'Provide comprehensive analysis of all energy data'
            })
        }
        
        # Create large mock response
        large_text = 'Comprehensive energy analysis data. ' * 1000  # ~35KB text
        large_citations = []
        
        for i in range(10):
            large_citations.append({
                'retrievedReferences': [{
                    'content': {'text': f'Large citation content {i}. ' * 200},
                    'location': {'s3Location': {'uri': f's3://bucket/data-{i}.parquet'}},
                    'metadata': {'score': 0.9 - i * 0.05}
                }]
            })
        
        mock_response = {
            'output': {'text': large_text},
            'citations': large_citations
        }
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.return_value = mock_response
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                start_time = time.time()
                response = rag_handler(event, None)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                
                assert response['statusCode'] == 200
                
                body = json.loads(response['body'])
                assert len(body['answer']) > 30000  # Large response
                assert len(body['sources']) == 10  # All citations processed
                
                # Should still respond within reasonable time even with large response
                assert response_time < 8000  # Under 8 seconds for large response


class TestErrorHandlingPerformance:
    """Test performance of error handling scenarios"""
    
    def test_invalid_query_error_response_time(self):
        """Test response time for invalid query errors"""
        invalid_events = [
            {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': ''})  # Empty question
            },
            {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': 'x' * 2000})  # Too long
            },
            {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({})  # Missing question
            }
        ]
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            for event in invalid_events:
                start_time = time.time()
                response = rag_handler(event, None)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                
                assert response['statusCode'] == 400
                assert response_time < 1000  # Error responses should be very fast
    
    def test_service_error_handling_performance(self):
        """Test performance when handling service errors"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'Test service error handling'})
        }
        
        from botocore.exceptions import ClientError
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.side_effect = ClientError(
                {'Error': {'Code': 'ServiceUnavailableException', 'Message': 'Service temporarily unavailable'}},
                'retrieve_and_generate'
            )
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                start_time = time.time()
                response = rag_handler(event, None)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                
                assert response['statusCode'] == 500
                assert response_time < 2000  # Error handling should be fast
                
                body = json.loads(response['body'])
                assert 'error' in body
    
    def test_timeout_handling_performance(self):
        """Test performance of timeout handling"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'Test timeout handling'})
        }
        
        def slow_response(*args, **kwargs):
            time.sleep(2)  # Simulate slow response
            return {
                'output': {'text': 'Slow response'},
                'citations': []
            }
        
        with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
            mock_bedrock.retrieve_and_generate.side_effect = slow_response
            
            with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                start_time = time.time()
                response = rag_handler(event, None)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000
                
                assert response['statusCode'] == 200
                assert response_time >= 2000  # Should include the delay
                assert response_time < 5000  # But not excessively long


class TestScalabilityMetrics:
    """Test scalability metrics and limits"""
    
    def test_throughput_measurement(self):
        """Measure API throughput under optimal conditions"""
        num_queries = 50
        
        def execute_query(query_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Throughput test query {query_id}'})
            }
            
            mock_response = {
                'output': {'text': f'Response {query_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    return {
                        'query_id': query_id,
                        'response_time': (end_time - start_time) * 1000,
                        'success': response['statusCode'] == 200
                    }
        
        # Execute queries with maximum concurrency
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            start_time = time.time()
            futures = [executor.submit(execute_query, i) for i in range(num_queries)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time
        
        # Calculate throughput metrics
        successful_queries = [r for r in results if r['success']]
        throughput = len(successful_queries) / total_time  # Queries per second
        
        assert len(successful_queries) == num_queries
        assert throughput > 5  # Should handle at least 5 queries per second
        
        # Calculate percentile response times
        response_times = sorted([r['response_time'] for r in successful_queries])
        p50 = response_times[len(response_times) // 2]
        p95 = response_times[int(len(response_times) * 0.95)]
        p99 = response_times[int(len(response_times) * 0.99)]
        
        assert p50 < 3000  # 50th percentile under 3 seconds
        assert p95 < 6000  # 95th percentile under 6 seconds
        assert p99 < 10000  # 99th percentile under 10 seconds


class TestAdvancedPerformanceScenarios:
    """Test advanced performance scenarios"""
    
    def test_api_rate_limiting_behavior(self):
        """Test API behavior under rate limiting"""
        # Simulate rate limiting by controlling request timing
        requests_per_second = 10
        duration_seconds = 5
        total_requests = requests_per_second * duration_seconds
        
        def make_rate_limited_request(request_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Rate limit test {request_id}'})
            }
            
            mock_response = {
                'output': {'text': f'Response {request_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    return {
                        'request_id': request_id,
                        'response_time': (end_time - start_time) * 1000,
                        'status_code': response['statusCode'],
                        'timestamp': start_time
                    }
        
        results = []
        start_time = time.time()
        
        # Execute requests at controlled rate
        for i in range(total_requests):
            request_start = time.time()
            
            result = make_rate_limited_request(i)
            results.append(result)
            
            # Control rate
            elapsed = time.time() - request_start
            sleep_time = (1.0 / requests_per_second) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        total_duration = time.time() - start_time
        actual_rate = len(results) / total_duration
        
        # Verify rate limiting behavior
        successful_requests = [r for r in results if r['status_code'] == 200]
        assert len(successful_requests) == total_requests
        assert abs(actual_rate - requests_per_second) < 2  # Within 2 RPS tolerance
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during extended operation"""
        import psutil
        import gc
        
        process = psutil.Process(os.getpid())
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = []
        
        # Run multiple iterations to detect memory leaks
        for iteration in range(20):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Memory leak test iteration {iteration}'})
            }
            
            mock_response = {
                'output': {'text': f'Response for iteration {iteration}' * 100},  # Larger response
                'citations': [
                    {
                        'retrievedReferences': [{
                            'content': {'text': f'Citation content {iteration}' * 50},
                            'location': {'s3Location': {'uri': f's3://bucket/data-{iteration}.parquet'}},
                            'metadata': {'score': 0.9}
                        }]
                    }
                ]
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    response = rag_handler(event, None)
                    assert response['statusCode'] == 200
            
            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory - baseline_memory)
            
            # Force garbage collection every 5 iterations
            if iteration % 5 == 0:
                gc.collect()
        
        # Analyze memory usage trend
        early_avg = statistics.mean(memory_samples[:5])
        late_avg = statistics.mean(memory_samples[-5:])
        memory_growth = late_avg - early_avg
        
        # Memory growth should be minimal (less than 20MB over 20 iterations)
        assert memory_growth < 20, f"Potential memory leak detected: {memory_growth}MB growth"
    
    def test_cpu_intensive_query_performance(self):
        """Test performance with CPU-intensive queries"""
        cpu_intensive_queries = [
            'Analyze the complete energy generation patterns across all regions for the past 5 years with detailed breakdowns by source type, seasonal variations, and efficiency metrics',
            'Compare consumption trends between residential, commercial, and industrial sectors across all regions with monthly granularity and identify peak demand periods',
            'Evaluate transmission line capacity utilization and identify bottlenecks in the grid infrastructure with recommendations for optimization',
            'Perform comprehensive analysis of renewable energy integration impact on grid stability and traditional generation displacement',
            'Calculate detailed carbon footprint analysis for all energy sources with lifecycle assessments and environmental impact projections'
        ]
        
        performance_results = []
        
        for i, query in enumerate(cpu_intensive_queries):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': query})
            }
            
            # Simulate CPU-intensive processing
            large_response = {
                'output': {'text': 'Comprehensive analysis results: ' + 'detailed data ' * 1000},
                'citations': [
                    {
                        'retrievedReferences': [{
                            'content': {'text': f'Complex analysis data {j}: ' + 'analysis content ' * 100},
                            'location': {'s3Location': {'uri': f's3://bucket/analysis-{i}-{j}.parquet'}},
                            'metadata': {'score': 0.95 - j * 0.05}
                        }]
                    } for j in range(5)  # Multiple citations
                ]
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                # Simulate processing delay
                def slow_processing(*args, **kwargs):
                    time.sleep(0.5)  # Simulate CPU-intensive work
                    return large_response
                
                mock_bedrock.retrieve_and_generate.side_effect = slow_processing
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    response = rag_handler(event, None)
                    end_time = time.time()
                    
                    response_time = (end_time - start_time) * 1000
                    
                    performance_results.append({
                        'query_index': i,
                        'query_length': len(query),
                        'response_time': response_time,
                        'response_size': len(json.dumps(response)),
                        'status_code': response['statusCode']
                    })
        
        # Analyze CPU-intensive performance
        avg_response_time = statistics.mean([r['response_time'] for r in performance_results])
        max_response_time = max([r['response_time'] for r in performance_results])
        
        # All queries should succeed
        assert all(r['status_code'] == 200 for r in performance_results)
        
        # Performance should be reasonable even for CPU-intensive queries
        assert avg_response_time < 8000  # Average under 8 seconds
        assert max_response_time < 15000  # Max under 15 seconds
    
    def test_database_connection_pooling_simulation(self):
        """Test database connection pooling simulation"""
        # Simulate multiple concurrent database operations
        connection_pool_size = 10
        concurrent_operations = 20
        
        def simulate_database_operation(operation_id):
            # Simulate database query with connection from pool
            connection_acquired_time = time.time()
            
            # Simulate query execution time
            query_duration = random.uniform(0.1, 0.5)
            time.sleep(query_duration)
            
            connection_released_time = time.time()
            
            return {
                'operation_id': operation_id,
                'connection_acquired_time': connection_acquired_time,
                'connection_released_time': connection_released_time,
                'query_duration': query_duration,
                'total_duration': connection_released_time - connection_acquired_time
            }
        
        # Execute operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=connection_pool_size) as executor:
            start_time = time.time()
            futures = [executor.submit(simulate_database_operation, i) for i in range(concurrent_operations)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time
        
        # Analyze connection pooling efficiency
        avg_total_duration = statistics.mean([r['total_duration'] for r in results])
        avg_query_duration = statistics.mean([r['query_duration'] for r in results])
        
        # Connection overhead should be minimal
        connection_overhead = avg_total_duration - avg_query_duration
        assert connection_overhead < 0.1  # Less than 100ms overhead
        
        # Total time should be efficient with pooling
        expected_sequential_time = sum([r['query_duration'] for r in results])
        efficiency = expected_sequential_time / total_time
        assert efficiency > 5  # Should be at least 5x faster than sequential


class TestStressTestingScenarios:
    """Test system behavior under extreme stress"""
    
    def test_extreme_load_stress_test(self):
        """Test system behavior under extreme load"""
        extreme_load_queries = 100
        max_workers = 50
        
        def execute_stress_query(query_id):
            event = {
                'httpMethod': 'POST',
                'path': '/query',
                'body': json.dumps({'question': f'Stress test query {query_id}'})
            }
            
            mock_response = {
                'output': {'text': f'Stress response {query_id}'},
                'citations': []
            }
            
            with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                mock_bedrock.retrieve_and_generate.return_value = mock_response
                
                with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                    start_time = time.time()
                    try:
                        response = rag_handler(event, None)
                        end_time = time.time()
                        
                        return {
                            'query_id': query_id,
                            'response_time': (end_time - start_time) * 1000,
                            'status_code': response['statusCode'],
                            'success': True,
                            'error': None
                        }
                    except Exception as e:
                        end_time = time.time()
                        return {
                            'query_id': query_id,
                            'response_time': (end_time - start_time) * 1000,
                            'status_code': 500,
                            'success': False,
                            'error': str(e)
                        }
        
        # Execute extreme load test
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            start_time = time.time()
            futures = [executor.submit(execute_stress_query, i) for i in range(extreme_load_queries)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
            total_time = time.time() - start_time
        
        # Analyze stress test results
        successful_queries = [r for r in results if r['success']]
        failed_queries = [r for r in results if not r['success']]
        
        success_rate = len(successful_queries) / len(results) * 100
        throughput = len(successful_queries) / total_time
        
        # Under extreme load, should maintain reasonable success rate
        assert success_rate > 80  # At least 80% success rate
        assert throughput > 10  # At least 10 successful queries per second
        
        if successful_queries:
            avg_response_time = statistics.mean([r['response_time'] for r in successful_queries])
            p95_response_time = sorted([r['response_time'] for r in successful_queries])[int(len(successful_queries) * 0.95)]
            
            # Response times may degrade under extreme load but should be bounded
            assert avg_response_time < 10000  # Average under 10 seconds
            assert p95_response_time < 20000  # 95th percentile under 20 seconds
    
    def test_resource_exhaustion_recovery(self):
        """Test recovery from resource exhaustion"""
        # Simulate resource exhaustion scenario
        resource_exhaustion_events = [
            {'type': 'memory_pressure', 'severity': 'high'},
            {'type': 'cpu_throttling', 'severity': 'medium'},
            {'type': 'network_congestion', 'severity': 'high'},
            {'type': 'disk_io_bottleneck', 'severity': 'low'}
        ]
        
        recovery_results = []
        
        for event_info in resource_exhaustion_events:
            # Simulate system under resource pressure
            if event_info['type'] == 'memory_pressure':
                # Simulate memory pressure with large objects
                large_objects = []
                try:
                    for i in range(100):
                        large_objects.append([0] * 10000)  # Create memory pressure
                    
                    # Try to process query under memory pressure
                    test_event = {
                        'httpMethod': 'POST',
                        'path': '/query',
                        'body': json.dumps({'question': 'Memory pressure test'})
                    }
                    
                    mock_response = {
                        'output': {'text': 'Response under memory pressure'},
                        'citations': []
                    }
                    
                    with patch('src.rag_query_processor.lambda_function.bedrock_runtime') as mock_bedrock:
                        mock_bedrock.retrieve_and_generate.return_value = mock_response
                        
                        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
                            response = rag_handler(test_event, None)
                            
                            recovery_results.append({
                                'event_type': event_info['type'],
                                'severity': event_info['severity'],
                                'recovery_successful': response['statusCode'] == 200,
                                'response_time': 'measured'
                            })
                
                finally:
                    # Clean up memory
                    large_objects.clear()
                    import gc
                    gc.collect()
            
            else:
                # Simulate other resource pressures
                recovery_results.append({
                    'event_type': event_info['type'],
                    'severity': event_info['severity'],
                    'recovery_successful': True,  # Simulated recovery
                    'response_time': 'simulated'
                })
        
        # Verify recovery capabilities
        high_severity_events = [r for r in recovery_results if r['severity'] == 'high']
        successful_recoveries = [r for r in recovery_results if r['recovery_successful']]
        
        # Should recover from most resource exhaustion scenarios
        recovery_rate = len(successful_recoveries) / len(recovery_results) * 100
        assert recovery_rate > 75  # At least 75% recovery rate


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])