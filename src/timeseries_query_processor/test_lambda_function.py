"""
Unit tests for the time series query processor Lambda function.

Tests query processing, caching, error handling, and performance monitoring.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import time

# Import the module under test
from lambda_function import (
    TimeSeriesQueryProcessor,
    QueryProcessorError,
    lambda_handler,
    processor
)


class TestTimeSeriesQueryProcessor:
    """Test cases for TimeSeriesQueryProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = TimeSeriesQueryProcessor()
    
    def test_initialization(self):
        """Test processor initialization."""
        assert self.processor.influxdb_handler is None
        assert self.processor.query_translator is None
        assert self.processor.metrics_namespace == 'ONS/TimeSeriesQueryProcessor'
        assert self.processor.query_timeout_seconds == 30
        assert self.processor.max_result_size == 10000
    
    @patch('lambda_function.InfluxDBHandler')
    def test_get_influxdb_handler_success(self, mock_influxdb_handler):
        """Test successful InfluxDB handler initialization."""
        mock_handler = Mock()
        mock_influxdb_handler.return_value = mock_handler
        
        handler = self.processor._get_influxdb_handler()
        
        assert handler == mock_handler
        assert self.processor.influxdb_handler == mock_handler
        mock_influxdb_handler.assert_called_once()
    
    @patch('lambda_function.InfluxDBHandler')
    def test_get_influxdb_handler_failure(self, mock_influxdb_handler):
        """Test InfluxDB handler initialization failure."""
        mock_influxdb_handler.side_effect = Exception("Connection failed")
        
        with pytest.raises(QueryProcessorError, match="InfluxDB connection failed"):
            self.processor._get_influxdb_handler()
    
    @patch('lambda_function.create_query_translator')
    def test_get_query_translator_success(self, mock_create_translator):
        """Test successful query translator initialization."""
        mock_translator = Mock()
        mock_create_translator.return_value = mock_translator
        
        translator = self.processor._get_query_translator()
        
        assert translator == mock_translator
        assert self.processor.query_translator == mock_translator
        mock_create_translator.assert_called_once()
    
    @patch('lambda_function.create_query_translator')
    def test_get_query_translator_failure(self, mock_create_translator):
        """Test query translator initialization failure."""
        mock_create_translator.side_effect = Exception("Translator failed")
        
        with pytest.raises(QueryProcessorError, match="Query translator initialization failed"):
            self.processor._get_query_translator()
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        query = "SELECT * FROM test"
        parameters = {"region": "southeast", "time_range": "1d"}
        
        key1 = self.processor._generate_cache_key(query, parameters)
        key2 = self.processor._generate_cache_key(query, parameters)
        
        # Same inputs should generate same key
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length
        
        # Different inputs should generate different keys
        different_params = {"region": "northeast", "time_range": "1d"}
        key3 = self.processor._generate_cache_key(query, different_params)
        assert key1 != key3
    
    def test_cache_operations(self):
        """Test cache get and set operations."""
        cache_key = "test_key"
        test_result = {"data": "test_data"}
        
        # Initially no cached result
        cached = self.processor._get_cached_result(cache_key)
        assert cached is None
        
        # Cache the result
        self.processor._cache_result(cache_key, test_result)
        
        # Should retrieve cached result
        cached = self.processor._get_cached_result(cache_key)
        assert cached == test_result
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache_key = "test_key"
        test_result = {"data": "test_data"}
        
        # Cache the result
        self.processor._cache_result(cache_key, test_result)
        
        # Mock time to simulate expiration
        with patch('time.time', return_value=time.time() + 400):  # Beyond TTL
            cached = self.processor._get_cached_result(cache_key)
            assert cached is None
    
    @patch('lambda_function.cloudwatch')
    def test_publish_metrics_success(self, mock_cloudwatch):
        """Test successful metrics publishing."""
        metrics = {
            'query_count': 1,
            'query_time_ms': 250.5,
            'cache_hits': 1
        }
        
        self.processor._publish_metrics(metrics)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        assert call_args['Namespace'] == 'ONS/TimeSeriesQueryProcessor'
        assert len(call_args['MetricData']) == 3
    
    @patch('lambda_function.cloudwatch')
    def test_publish_metrics_failure(self, mock_cloudwatch):
        """Test metrics publishing failure handling."""
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        
        metrics = {'query_count': 1}
        
        # Should not raise exception
        self.processor._publish_metrics(metrics)
    
    def test_format_time_series_data(self):
        """Test time series data formatting."""
        raw_results = [
            {
                'time': datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                'measurement': 'generation_data',
                'field': 'power_mw',
                'value': 14000.5,
                'tags': {
                    'region': 'southeast',
                    'energy_source': 'hydro',
                    '_measurement': 'generation_data',  # Should be filtered out
                    '_field': 'power_mw'  # Should be filtered out
                }
            },
            {
                'time': '2024-01-01T13:00:00Z',
                'measurement': 'consumption_data',
                'field': 'demand_mw',
                'value': 8500.0,
                'tags': {'region': 'northeast'}
            }
        ]
        
        formatted = self.processor._format_time_series_data(raw_results)
        
        assert len(formatted) == 2
        
        # Check first record
        first_record = formatted[0]
        assert first_record['timestamp'] == '2024-01-01T12:00:00+00:00'
        assert first_record['measurement'] == 'generation_data'
        assert first_record['field'] == 'power_mw'
        assert first_record['value'] == 14000.5
        assert first_record['tags'] == {
            'region': 'southeast',
            'energy_source': 'hydro'
        }
        
        # Check second record
        second_record = formatted[1]
        assert second_record['timestamp'] == '2024-01-01T13:00:00Z'
        assert second_record['measurement'] == 'consumption_data'
        assert second_record['field'] == 'demand_mw'
        assert second_record['value'] == 8500.0
        assert second_record['tags'] == {'region': 'northeast'}
    
    def test_validate_query_parameters_success(self):
        """Test successful parameter validation."""
        event = {
            'body': json.dumps({
                'question': 'Show hydro generation',
                'language': 'flux',
                'context': {'region': 'southeast'},
                'use_cache': True
            })
        }
        
        params = self.processor._validate_query_parameters(event)
        
        assert params['question'] == 'Show hydro generation'
        assert params['language'].value == 'flux'
        assert params['context'] == {'region': 'southeast'}
        assert params['use_cache'] is True
    
    def test_validate_query_parameters_missing_question(self):
        """Test parameter validation with missing question."""
        event = {
            'body': json.dumps({
                'language': 'flux'
            })
        }
        
        with pytest.raises(QueryProcessorError, match="Question parameter is required"):
            self.processor._validate_query_parameters(event)
    
    def test_validate_query_parameters_invalid_language(self):
        """Test parameter validation with invalid language."""
        event = {
            'body': json.dumps({
                'question': 'Show data',
                'language': 'invalid'
            })
        }
        
        with pytest.raises(QueryProcessorError, match="Unsupported query language"):
            self.processor._validate_query_parameters(event)
    
    def test_validate_query_parameters_invalid_json(self):
        """Test parameter validation with invalid JSON."""
        event = {
            'body': 'invalid json'
        }
        
        with pytest.raises(QueryProcessorError, match="Invalid JSON in request body"):
            self.processor._validate_query_parameters(event)
    
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    @patch.object(TimeSeriesQueryProcessor, '_publish_metrics')
    def test_process_query_success(self, mock_publish_metrics, mock_get_influxdb, mock_get_translator):
        """Test successful query processing."""
        # Mock translator
        mock_translator = Mock()
        mock_translator.translate_query.return_value = {
            'query': 'from(bucket: "test")',
            'query_type': 'generation_trend',
            'language': 'flux',
            'confidence_score': 0.95,
            'template_description': 'Test query',
            'parameters': {'region': 'southeast'}
        }
        mock_get_translator.return_value = mock_translator
        
        # Mock InfluxDB handler
        mock_influxdb = Mock()
        mock_influxdb.query_flux.return_value = [
            {
                'time': datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                'measurement': 'generation_data',
                'field': 'power_mw',
                'value': 14000.5,
                'tags': {'region': 'southeast'}
            }
        ]
        mock_get_influxdb.return_value = mock_influxdb
        
        # Test event
        event = {
            'body': json.dumps({
                'question': 'Show hydro generation',
                'language': 'flux',
                'use_cache': False
            })
        }
        
        result = self.processor.process_query(event)
        
        assert result['statusCode'] == 200
        
        body = json.loads(result['body'])
        assert body['question'] == 'Show hydro generation'
        assert body['query_metadata']['query_type'] == 'generation_trend'
        assert body['influxdb_query'] == 'from(bucket: "test")'
        assert len(body['time_series_data']) == 1
        assert body['record_count'] == 1
        assert body['cached'] is False
        assert 'processing_time_ms' in body
        
        mock_publish_metrics.assert_called_once()
    
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    @patch.object(TimeSeriesQueryProcessor, '_publish_metrics')
    def test_process_query_with_cache(self, mock_publish_metrics, mock_get_influxdb, mock_get_translator):
        """Test query processing with cache hit."""
        # Mock translator
        mock_translator = Mock()
        mock_translator.translate_query.return_value = {
            'query': 'from(bucket: "test")',
            'query_type': 'generation_trend',
            'language': 'flux',
            'confidence_score': 0.95,
            'template_description': 'Test query',
            'parameters': {'region': 'southeast'}
        }
        mock_get_translator.return_value = mock_translator
        
        # Pre-populate cache
        cache_key = self.processor._generate_cache_key(
            'from(bucket: "test")',
            {'region': 'southeast'}
        )
        cached_data = {
            'question': 'Show hydro generation',
            'time_series_data': [{'test': 'data'}],
            'cached': False
        }
        self.processor._cache_result(cache_key, cached_data)
        
        # Test event
        event = {
            'body': json.dumps({
                'question': 'Show hydro generation',
                'language': 'flux',
                'use_cache': True
            })
        }
        
        result = self.processor.process_query(event)
        
        assert result['statusCode'] == 200
        
        body = json.loads(result['body'])
        assert body['cached'] is True
        assert body['time_series_data'] == [{'test': 'data'}]
        
        # InfluxDB should not be called due to cache hit
        mock_get_influxdb.assert_not_called()
    
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    @patch.object(TimeSeriesQueryProcessor, '_publish_metrics')
    def test_process_query_translation_error(self, mock_publish_metrics, mock_get_translator):
        """Test query processing with translation error."""
        mock_translator = Mock()
        mock_translator.translate_query.side_effect = Exception("Translation failed")
        mock_get_translator.return_value = mock_translator
        
        event = {
            'body': json.dumps({
                'question': 'Show data',
                'language': 'flux'
            })
        }
        
        result = self.processor.process_query(event)
        
        assert result['statusCode'] == 500
        
        body = json.loads(result['body'])
        assert body['error'] == 'Internal server error'
        assert body['error_type'] == 'InternalError'
    
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    @patch.object(TimeSeriesQueryProcessor, '_publish_metrics')
    def test_process_query_result_truncation(self, mock_publish_metrics, mock_get_influxdb, mock_get_translator):
        """Test query result truncation for large result sets."""
        # Set small max result size for testing
        self.processor.max_result_size = 2
        
        # Mock translator
        mock_translator = Mock()
        mock_translator.translate_query.return_value = {
            'query': 'from(bucket: "test")',
            'query_type': 'generation_trend',
            'language': 'flux',
            'confidence_score': 0.95,
            'template_description': 'Test query',
            'parameters': {}
        }
        mock_get_translator.return_value = mock_translator
        
        # Mock InfluxDB handler with large result set
        mock_influxdb = Mock()
        large_results = [
            {'time': f'2024-01-01T{i:02d}:00:00Z', 'value': i}
            for i in range(5)  # 5 results, but max is 2
        ]
        mock_influxdb.query_flux.return_value = large_results
        mock_get_influxdb.return_value = mock_influxdb
        
        event = {
            'body': json.dumps({
                'question': 'Show data',
                'use_cache': False
            })
        }
        
        result = self.processor.process_query(event)
        
        assert result['statusCode'] == 200
        
        body = json.loads(result['body'])
        assert body['record_count'] == 2  # Truncated
        assert body['query_metadata']['truncated'] is True
    
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    def test_health_check_healthy(self, mock_get_translator, mock_get_influxdb):
        """Test health check with all components healthy."""
        # Mock InfluxDB handler
        mock_influxdb = Mock()
        mock_influxdb.health_check.return_value = {
            'status': 'healthy',
            'response_time_ms': 15.2
        }
        mock_get_influxdb.return_value = mock_influxdb
        
        # Mock query translator
        mock_translator = Mock()
        mock_translator.translate_query.return_value = {
            'query_type': 'generation_trend'
        }
        mock_get_translator.return_value = mock_translator
        
        health_result = self.processor.health_check()
        
        assert health_result['status'] == 'healthy'
        assert 'timestamp' in health_result
        assert 'response_time_ms' in health_result
        assert health_result['components']['influxdb']['status'] == 'healthy'
        assert health_result['components']['query_translator']['status'] == 'healthy'
        assert health_result['components']['cache']['status'] == 'healthy'
    
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    def test_health_check_degraded(self, mock_get_influxdb):
        """Test health check with degraded components."""
        # Mock InfluxDB handler with unhealthy status
        mock_influxdb = Mock()
        mock_influxdb.health_check.return_value = {
            'status': 'unhealthy',
            'error': 'Connection timeout'
        }
        mock_get_influxdb.return_value = mock_influxdb
        
        health_result = self.processor.health_check()
        
        assert health_result['status'] == 'degraded'
        assert health_result['components']['influxdb']['status'] == 'unhealthy'


class TestLambdaHandler:
    """Test cases for the Lambda handler function."""
    
    @patch.object(TimeSeriesQueryProcessor, 'process_query')
    def test_lambda_handler_post_request(self, mock_process_query):
        """Test Lambda handler with POST request."""
        mock_process_query.return_value = {
            'statusCode': 200,
            'body': json.dumps({'result': 'success'})
        }
        
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'Show data'})
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        mock_process_query.assert_called_once_with(event)
    
    @patch.object(TimeSeriesQueryProcessor, 'health_check')
    def test_lambda_handler_health_check(self, mock_health_check):
        """Test Lambda handler with health check request."""
        mock_health_check.return_value = {
            'status': 'healthy',
            'components': {}
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        mock_health_check.assert_called_once()
    
    @patch.object(TimeSeriesQueryProcessor, 'health_check')
    def test_lambda_handler_health_check_unhealthy(self, mock_health_check):
        """Test Lambda handler with unhealthy health check."""
        mock_health_check.return_value = {
            'status': 'unhealthy',
            'error': 'Database connection failed'
        }
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 503
    
    def test_lambda_handler_options_request(self):
        """Test Lambda handler with OPTIONS request (CORS preflight)."""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/query'
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        assert 'Access-Control-Allow-Methods' in result['headers']
        assert 'Access-Control-Allow-Headers' in result['headers']
    
    def test_lambda_handler_method_not_allowed(self):
        """Test Lambda handler with unsupported HTTP method."""
        event = {
            'httpMethod': 'DELETE',
            'path': '/query'
        }
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 405
        
        body = json.loads(result['body'])
        assert 'Method DELETE not allowed' in body['error']
    
    def test_lambda_handler_exception(self):
        """Test Lambda handler with unexpected exception."""
        # Invalid event structure to trigger exception
        event = None
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 500
        
        body = json.loads(result['body'])
        assert body['error'] == 'Internal server error'
        assert body['error_type'] == 'LambdaHandlerError'


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = TimeSeriesQueryProcessor()
    
    @patch.object(TimeSeriesQueryProcessor, '_get_query_translator')
    @patch.object(TimeSeriesQueryProcessor, '_get_influxdb_handler')
    @patch.object(TimeSeriesQueryProcessor, '_publish_metrics')
    def test_end_to_end_query_processing(self, mock_publish_metrics, mock_get_influxdb, mock_get_translator):
        """Test complete end-to-end query processing."""
        # Mock translator
        mock_translator = Mock()
        mock_translator.translate_query.return_value = {
            'query': 'from(bucket: "energy_data") |> range(start: -1d)',
            'query_type': 'generation_trend',
            'language': 'flux',
            'confidence_score': 0.95,
            'template_description': 'Analyze power generation trends over time',
            'parameters': {'region': 'southeast', 'time_range': {'start': '-1d'}}
        }
        mock_get_translator.return_value = mock_translator
        
        # Mock InfluxDB handler
        mock_influxdb = Mock()
        mock_influxdb.query_flux.return_value = [
            {
                'time': datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                'measurement': 'generation_data',
                'field': 'power_mw',
                'value': 14000.5,
                'tags': {
                    'region': 'southeast',
                    'energy_source': 'hydro',
                    'plant_name': 'itaipu'
                }
            },
            {
                'time': datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
                'measurement': 'generation_data',
                'field': 'power_mw',
                'value': 13500.0,
                'tags': {
                    'region': 'southeast',
                    'energy_source': 'hydro',
                    'plant_name': 'itaipu'
                }
            }
        ]
        mock_get_influxdb.return_value = mock_influxdb
        
        # Create realistic event
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({
                'question': 'Show hydro generation trend in southeast for last day',
                'language': 'flux',
                'context': {
                    'default_region': 'southeast',
                    'time_zone': 'UTC'
                },
                'use_cache': True
            })
        }
        
        # Process through Lambda handler
        result = lambda_handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in result['headers']
        
        body = json.loads(result['body'])
        assert body['question'] == 'Show hydro generation trend in southeast for last day'
        assert body['query_metadata']['query_type'] == 'generation_trend'
        assert body['query_metadata']['confidence_score'] == 0.95
        assert 'from(bucket: "energy_data")' in body['influxdb_query']
        assert len(body['time_series_data']) == 2
        assert body['record_count'] == 2
        assert body['cached'] is False
        assert 'processing_time_ms' in body
        
        # Verify data formatting
        first_record = body['time_series_data'][0]
        assert first_record['timestamp'] == '2024-01-01T12:00:00+00:00'
        assert first_record['measurement'] == 'generation_data'
        assert first_record['field'] == 'power_mw'
        assert first_record['value'] == 14000.5
        assert first_record['tags']['region'] == 'southeast'
        assert first_record['tags']['energy_source'] == 'hydro'
        assert first_record['tags']['plant_name'] == 'itaipu'
        
        # Verify metrics were published
        mock_publish_metrics.assert_called_once()
        
        # Verify translator was called correctly
        mock_translator.translate_query.assert_called_once()
        call_args = mock_translator.translate_query.call_args
        assert call_args[0][0] == 'Show hydro generation trend in southeast for last day'
        
        # Verify InfluxDB was called correctly
        mock_influxdb.query_flux.assert_called_once()
        influxdb_query = mock_influxdb.query_flux.call_args[0][0]
        assert 'from(bucket: "energy_data")' in influxdb_query