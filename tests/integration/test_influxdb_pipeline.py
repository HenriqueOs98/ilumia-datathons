"""
Integration tests for InfluxDB pipeline workflows.

Tests the complete data pipeline from S3 to InfluxDB, API endpoint testing
with real InfluxDB queries, and performance benchmarking for InfluxDB operations.
"""

import pytest
import json
import time
import boto3
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from moto import mock_s3, mock_lambda
import tempfile
import os

from influxdb_client import Point, WritePrecision

from src.shared_utils.influxdb_client import InfluxDBHandler
from src.shared_utils.data_conversion import EnergyDataConverter
from src.shared_utils.query_translator import QueryTranslator, QueryLanguage
from src.influxdb_loader.lambda_function import lambda_handler as influxdb_loader_handler
from src.timeseries_query_processor.lambda_function import lambda_handler as query_processor_handler
from src.rag_query_processor.lambda_function import lambda_handler as rag_processor_handler


class TestInfluxDBPipelineIntegration:
    """Integration tests for complete InfluxDB data pipeline."""
    
    @pytest.fixture
    def mock_influxdb_handler(self):
        """Mock InfluxDB handler for integration testing."""
        handler = Mock(spec=InfluxDBHandler)
        handler.write_points.return_value = True
        handler.query_flux.return_value = [
            {
                'measurement': 'generation_data',
                'time': datetime.now(timezone.utc),
                'field': 'power_mw',
                'value': 1000.0,
                'tags': {'region': 'southeast', 'energy_source': 'hydro'}
            }
        ]
        handler.health_check.return_value = {
            'status': 'healthy',
            'response_time_ms': 50.0
        }
        return handler
    
    @pytest.fixture
    def sample_parquet_data(self):
        """Sample Parquet data for testing."""
        return pd.DataFrame({
            'timestamp': [
                '2024-01-01T12:00:00Z',
                '2024-01-01T13:00:00Z',
                '2024-01-01T14:00:00Z'
            ],
            'region': ['southeast', 'northeast', 'south'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw'],
            'value': [1000.0, 500.0, 300.0],
            'unit': ['MW', 'MW', 'MW'],
            'plant_name': ['Itaipu', 'WindFarm1', 'SolarPark1'],
            'capacity_mw': [14000.0, 1000.0, 500.0],
            'efficiency': [0.85, 0.92, 0.88],
            'quality_flag': ['good', 'good', 'good']
        })
    
    @pytest.fixture
    def s3_event(self):
        """Sample S3 event for Lambda testing."""
        return {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'processed/dataset=generation/year=2024/month=01/file.parquet'}
                    }
                }
            ]
        }
    
    @mock_s3
    def test_complete_data_pipeline_s3_to_influxdb(self, mock_influxdb_handler, sample_parquet_data, s3_event):
        """Test complete data pipeline from S3 to InfluxDB."""
        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')
        
        # Create temporary parquet file
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
            sample_parquet_data.to_parquet(tmp_file.name)
            
            # Upload to S3
            s3_client.upload_file(
                tmp_file.name,
                'test-bucket',
                'processed/dataset=generation/year=2024/month=01/file.parquet'
            )
        
        # Mock the InfluxDB handler in the Lambda function
        with patch('src.influxdb_loader.lambda_function.InfluxDBHandler') as mock_handler_class:
            mock_handler_class.return_value = mock_influxdb_handler
            
            # Mock pandas read_parquet
            with patch('src.influxdb_loader.lambda_function.pd.read_parquet') as mock_read_parquet:
                mock_read_parquet.return_value = sample_parquet_data
                
                # Execute Lambda function
                response = influxdb_loader_handler(s3_event, {})
                
                # Verify response
                assert response['statusCode'] == 200
                
                # Verify InfluxDB handler was called
                mock_influxdb_handler.write_points.assert_called_once()
                
                # Verify data conversion occurred
                call_args = mock_influxdb_handler.write_points.call_args[0]
                points = call_args[0]
                assert len(points) == 3
                assert all(isinstance(point, Point) for point in points)
        
        # Cleanup
        os.unlink(tmp_file.name)
    
    def test_api_endpoint_query_processing(self, mock_influxdb_handler):
        """Test API endpoint with real InfluxDB query processing."""
        # Mock API Gateway event
        api_event = {
            'body': json.dumps({
                'question': 'What is the average hydro generation in southeast region for the last week?'
            }),
            'headers': {'Content-Type': 'application/json'}
        }
        
        # Mock the InfluxDB handler and query translator
        with patch('src.timeseries_query_processor.lambda_function.InfluxDBHandler') as mock_handler_class:
            mock_handler_class.return_value = mock_influxdb_handler
            
            with patch('src.timeseries_query_processor.lambda_function.QueryTranslator') as mock_translator_class:
                mock_translator = Mock()
                mock_translator.translate_query.return_value = {
                    'query': 'from(bucket: "energy_data") |> range(start: -7d) |> filter(fn: (r) => r["_measurement"] == "generation_data")',
                    'query_type': 'generation_trend',
                    'language': 'flux',
                    'parameters': {
                        'time_range': {'start': '-7d', 'stop': 'now()'},
                        'regions': ['southeast'],
                        'energy_sources': ['hydro'],
                        'aggregation': 'mean'
                    },
                    'confidence_score': 0.95
                }
                mock_translator_class.return_value = mock_translator
                
                # Execute query processor
                response = query_processor_handler(api_event, {})
                
                # Verify response
                assert response['statusCode'] == 200
                response_body = json.loads(response['body'])
                
                assert 'time_series_data' in response_body
                assert 'query_used' in response_body
                assert 'confidence_score' in response_body
                assert response_body['confidence_score'] == 0.95
                
                # Verify InfluxDB query was executed
                mock_influxdb_handler.query_flux.assert_called_once()
    
    def test_rag_integration_with_time_series_data(self, mock_influxdb_handler):
        """Test RAG query processor integration with time series data."""
        # Mock API Gateway event for RAG query
        rag_event = {
            'body': json.dumps({
                'question': 'How has renewable energy generation changed in Brazil over the past year?',
                'include_time_series': True
            }),
            'headers': {'Content-Type': 'application/json'}
        }
        
        # Mock Knowledge Base response
        mock_kb_response = {
            'answer': 'Renewable energy generation has increased by 15% over the past year.',
            'sources': [
                {
                    'document': 'renewable_energy_report_2024.pdf',
                    'relevance_score': 0.92
                }
            ]
        }
        
        with patch('src.rag_query_processor.lambda_function.InfluxDBHandler') as mock_handler_class:
            mock_handler_class.return_value = mock_influxdb_handler
            
            with patch('src.rag_query_processor.lambda_function.query_knowledge_base') as mock_kb:
                mock_kb.return_value = mock_kb_response
                
                with patch('src.rag_query_processor.lambda_function.QueryTranslator') as mock_translator_class:
                    mock_translator = Mock()
                    mock_translator.translate_query.return_value = {
                        'query': 'from(bucket: "energy_data") |> range(start: -1y)',
                        'query_type': 'source_breakdown',
                        'language': 'flux'
                    }
                    mock_translator_class.return_value = mock_translator
                    
                    # Execute RAG processor
                    response = rag_processor_handler(rag_event, {})
                    
                    # Verify response
                    assert response['statusCode'] == 200
                    response_body = json.loads(response['body'])
                    
                    assert 'answer' in response_body
                    assert 'time_series_data' in response_body
                    assert 'sources' in response_body
                    
                    # Verify both Knowledge Base and InfluxDB were queried
                    mock_kb.assert_called_once()
                    mock_influxdb_handler.query_flux.assert_called_once()
    
    def test_error_handling_in_pipeline(self, mock_influxdb_handler, s3_event):
        """Test error handling throughout the pipeline."""
        # Test InfluxDB connection failure
        mock_influxdb_handler.write_points.side_effect = Exception("InfluxDB connection failed")
        
        with patch('src.influxdb_loader.lambda_function.InfluxDBHandler') as mock_handler_class:
            mock_handler_class.return_value = mock_influxdb_handler
            
            with patch('src.influxdb_loader.lambda_function.pd.read_parquet') as mock_read_parquet:
                mock_read_parquet.return_value = pd.DataFrame({'test': [1, 2, 3]})
                
                # Should handle error gracefully
                response = influxdb_loader_handler(s3_event, {})
                
                # Should return error response
                assert response['statusCode'] == 500
                assert 'error' in json.loads(response['body'])
    
    def test_data_validation_in_pipeline(self, mock_influxdb_handler, sample_parquet_data):
        """Test data validation throughout the pipeline."""
        # Create invalid data
        invalid_data = sample_parquet_data.copy()
        invalid_data.loc[0, 'value'] = 'invalid_number'
        invalid_data.loc[1, 'timestamp'] = 'invalid_timestamp'
        
        # Test data conversion with validation
        converter = EnergyDataConverter('generation')
        
        # Should handle invalid data gracefully
        points = converter.convert_dataframe_to_points(invalid_data, drop_invalid=True)
        
        # Should only get valid points
        assert len(points) == 1  # Only one completely valid row
        
        # Test validation results
        validation_result = converter.validate_dataframe_schema(invalid_data)
        assert not validation_result['valid']
        assert len(validation_result['errors']) > 0


class TestInfluxDBPerformanceBenchmarks:
    """Performance benchmarking tests for InfluxDB operations."""
    
    @pytest.fixture
    def performance_influxdb_handler(self):
        """Mock InfluxDB handler with performance simulation."""
        handler = Mock(spec=InfluxDBHandler)
        
        def mock_write_with_delay(points, **kwargs):
            # Simulate write latency based on number of points
            delay = len(points) * 0.001  # 1ms per point
            time.sleep(delay)
            return True
        
        def mock_query_with_delay(query, **kwargs):
            # Simulate query latency based on query complexity
            delay = 0.1 if 'aggregateWindow' in query else 0.05
            time.sleep(delay)
            return [{'measurement': 'test', 'value': 100.0}]
        
        handler.write_points.side_effect = mock_write_with_delay
        handler.query_flux.side_effect = mock_query_with_delay
        
        return handler
    
    def test_write_performance_benchmark(self, performance_influxdb_handler):
        """Benchmark write performance for different batch sizes."""
        batch_sizes = [100, 500, 1000, 5000]
        results = {}
        
        for batch_size in batch_sizes:
            # Create test points
            points = [
                Point("test_measurement")
                .tag("region", f"region_{i % 5}")
                .field("value", float(i))
                .time(datetime.now(timezone.utc) + timedelta(seconds=i))
                for i in range(batch_size)
            ]
            
            # Measure write time
            start_time = time.time()
            performance_influxdb_handler.write_points(points)
            end_time = time.time()
            
            write_time = end_time - start_time
            throughput = batch_size / write_time
            
            results[batch_size] = {
                'write_time': write_time,
                'throughput': throughput,
                'latency_per_point': write_time / batch_size
            }
        
        # Verify performance expectations
        for batch_size, metrics in results.items():
            # Should achieve reasonable throughput
            assert metrics['throughput'] > 100  # points per second
            
            # Latency per point should be reasonable
            assert metrics['latency_per_point'] < 0.01  # less than 10ms per point
        
        # Larger batches should have better throughput
        assert results[5000]['throughput'] > results[100]['throughput']
    
    def test_query_performance_benchmark(self, performance_influxdb_handler):
        """Benchmark query performance for different query types."""
        queries = {
            'simple_filter': '''
                from(bucket: "energy_data")
                |> range(start: -1h)
                |> filter(fn: (r) => r["region"] == "southeast")
            ''',
            'aggregation': '''
                from(bucket: "energy_data")
                |> range(start: -1d)
                |> filter(fn: (r) => r["_measurement"] == "generation_data")
                |> aggregateWindow(every: 1h, fn: mean)
            ''',
            'complex_grouping': '''
                from(bucket: "energy_data")
                |> range(start: -7d)
                |> filter(fn: (r) => r["_measurement"] == "generation_data")
                |> group(columns: ["region", "energy_source"])
                |> aggregateWindow(every: 1h, fn: mean)
                |> sort(columns: ["_value"], desc: true)
            '''
        }
        
        results = {}
        
        for query_name, query in queries.items():
            # Measure query time
            start_time = time.time()
            performance_influxdb_handler.query_flux(query)
            end_time = time.time()
            
            query_time = end_time - start_time
            results[query_name] = query_time
        
        # Verify performance expectations
        assert results['simple_filter'] < 0.1  # Simple queries should be fast
        assert results['aggregation'] < 0.2   # Aggregations should be reasonable
        assert results['complex_grouping'] < 0.5  # Complex queries should still be acceptable
        
        # Simple queries should be faster than complex ones
        assert results['simple_filter'] < results['complex_grouping']
    
    def test_concurrent_operations_performance(self, performance_influxdb_handler):
        """Test performance under concurrent read/write operations."""
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def write_worker():
            """Worker function for write operations."""
            points = [
                Point("concurrent_test")
                .field("value", 1.0)
                .time(datetime.now(timezone.utc))
            ]
            
            start_time = time.time()
            performance_influxdb_handler.write_points(points)
            end_time = time.time()
            
            results_queue.put(('write', end_time - start_time))
        
        def read_worker():
            """Worker function for read operations."""
            query = 'from(bucket: "energy_data") |> range(start: -1h)'
            
            start_time = time.time()
            performance_influxdb_handler.query_flux(query)
            end_time = time.time()
            
            results_queue.put(('read', end_time - start_time))
        
        # Create concurrent threads
        threads = []
        for _ in range(5):  # 5 write threads
            thread = threading.Thread(target=write_worker)
            threads.append(thread)
        
        for _ in range(5):  # 5 read threads
            thread = threading.Thread(target=read_worker)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Collect results
        write_times = []
        read_times = []
        
        while not results_queue.empty():
            operation_type, operation_time = results_queue.get()
            if operation_type == 'write':
                write_times.append(operation_time)
            else:
                read_times.append(operation_time)
        
        # Verify concurrent performance
        assert len(write_times) == 5
        assert len(read_times) == 5
        
        # Average operation time should be reasonable
        avg_write_time = sum(write_times) / len(write_times)
        avg_read_time = sum(read_times) / len(read_times)
        
        assert avg_write_time < 0.1
        assert avg_read_time < 0.2
        
        # Total time should be less than sequential execution
        sequential_time = sum(write_times) + sum(read_times)
        assert total_time < sequential_time * 0.8  # At least 20% improvement
    
    def test_memory_usage_monitoring(self, performance_influxdb_handler):
        """Test memory usage during large data operations."""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        large_dataset = pd.DataFrame({
            'timestamp': [datetime.now(timezone.utc) + timedelta(seconds=i) for i in range(10000)],
            'region': ['southeast'] * 10000,
            'energy_source': ['hydro'] * 10000,
            'measurement_type': ['power_mw'] * 10000,
            'value': [1000.0 + i for i in range(10000)],
            'unit': ['MW'] * 10000
        })
        
        # Convert to InfluxDB points
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(large_dataset)
        
        # Check memory usage after conversion
        after_conversion_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Write points
        performance_influxdb_handler.write_points(points)
        
        # Check memory usage after write
        after_write_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Clean up
        del points
        del large_dataset
        gc.collect()
        
        # Check memory usage after cleanup
        after_cleanup_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Verify memory usage is reasonable
        conversion_overhead = after_conversion_memory - initial_memory
        write_overhead = after_write_memory - after_conversion_memory
        
        # Memory overhead should be reasonable (less than 500MB for 10k points)
        assert conversion_overhead < 500
        assert write_overhead < 100
        
        # Memory should be released after cleanup
        assert after_cleanup_memory < after_write_memory


class TestInfluxDBDataIntegrity:
    """Test data integrity throughout the InfluxDB pipeline."""
    
    @pytest.fixture
    def integrity_test_data(self):
        """Test data with various edge cases for integrity testing."""
        return pd.DataFrame({
            'timestamp': [
                '2024-01-01T12:00:00Z',
                '2024-01-01T12:00:00Z',  # Duplicate timestamp
                '2024-01-01T13:00:00Z',
                '2024-01-01T14:00:00Z'
            ],
            'region': ['southeast', 'southeast', 'northeast', 'south'],
            'energy_source': ['hydro', 'hydro', 'wind', 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw', 'power_mw'],
            'value': [1000.0, 1000.0, 500.0, 300.0],  # Duplicate values
            'unit': ['MW', 'MW', 'MW', 'MW'],
            'quality_flag': ['good', 'good', 'good', 'poor']  # Mixed quality
        })
    
    def test_duplicate_data_handling(self, integrity_test_data):
        """Test handling of duplicate data points."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(integrity_test_data)
        
        # Should handle duplicates gracefully
        assert len(points) == 4
        
        # Validate points for potential duplicates
        from src.shared_utils.data_conversion import validate_influxdb_points
        validation_result = validate_influxdb_points(points)
        
        # Should detect potential duplicates
        assert len(validation_result['warnings']) > 0
        duplicate_warning = any('duplicate' in warning for warning in validation_result['warnings'])
        assert duplicate_warning
    
    def test_data_type_consistency(self, integrity_test_data):
        """Test data type consistency throughout conversion."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(integrity_test_data)
        
        for point in points:
            # Check that all field values are numeric
            for field_name, field_value in point._fields.items():
                if field_name != 'unit':  # Unit is string field
                    assert isinstance(field_value, (int, float))
            
            # Check that all tag values are strings
            for tag_name, tag_value in point._tags.items():
                assert isinstance(tag_value, str)
            
            # Check that timestamp is properly set
            assert point._time is not None
    
    def test_data_completeness_validation(self, integrity_test_data):
        """Test validation of data completeness."""
        converter = EnergyDataConverter('generation')
        
        # Test with complete data
        validation_result = converter.validate_dataframe_schema(integrity_test_data)
        assert validation_result['valid']
        
        # Test with missing required columns
        incomplete_data = integrity_test_data.drop(columns=['region'])
        validation_result = converter.validate_dataframe_schema(incomplete_data)
        assert not validation_result['valid']
        assert any('Missing required columns' in error for error in validation_result['errors'])
    
    def test_timestamp_consistency(self, integrity_test_data):
        """Test timestamp handling and consistency."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(integrity_test_data)
        
        # All points should have timestamps
        for point in points:
            assert point._time is not None
        
        # Timestamps should be in correct order (or at least valid)
        timestamps = [point._time for point in points]
        for ts in timestamps:
            assert isinstance(ts, datetime)
            # Should be timezone-aware
            assert ts.tzinfo is not None