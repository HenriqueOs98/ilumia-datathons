"""
Unit tests for InfluxDB client handler.

Tests the InfluxDBHandler class with mocked InfluxDB client for isolated testing.
"""

import pytest
import os
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone
import threading

from influxdb_client import Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.rest import ApiException

from src.shared_utils.influxdb_client import (
    InfluxDBHandler,
    InfluxDBConnectionError,
    InfluxDBWriteError,
    InfluxDBQueryError
)


class TestInfluxDBHandler:
    """Test cases for InfluxDBHandler class."""
    
    @pytest.fixture
    def mock_influxdb_client(self):
        """Mock InfluxDB client for testing."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            
            # Mock API instances
            mock_instance.write_api.return_value = Mock()
            mock_instance.query_api.return_value = Mock()
            mock_instance.ping.return_value = True
            
            yield mock_instance
    
    @pytest.fixture
    def handler_config(self):
        """Configuration for InfluxDB handler."""
        return {
            'url': 'http://localhost:8086',
            'token': 'test-token',
            'org': 'test-org',
            'bucket': 'test-bucket',
            'timeout': 30000,
            'max_retries': 3,
            'retry_delay': 1.0
        }
    
    def test_init_with_parameters(self, mock_influxdb_client, handler_config):
        """Test handler initialization with explicit parameters."""
        handler = InfluxDBHandler(**handler_config)
        
        assert handler.url == handler_config['url']
        assert handler.token == handler_config['token']
        assert handler.org == handler_config['org']
        assert handler.bucket == handler_config['bucket']
        assert handler.timeout == handler_config['timeout']
        assert handler.max_retries == handler_config['max_retries']
        assert handler.retry_delay == handler_config['retry_delay']
    
    @patch.dict(os.environ, {
        'INFLUXDB_URL': 'http://env-url:8086',
        'INFLUXDB_TOKEN': 'env-token',
        'INFLUXDB_ORG': 'env-org',
        'INFLUXDB_BUCKET': 'env-bucket'
    })
    def test_init_with_environment_variables(self, mock_influxdb_client):
        """Test handler initialization with environment variables."""
        handler = InfluxDBHandler()
        
        assert handler.url == 'http://env-url:8086'
        assert handler.token == 'env-token'
        assert handler.org == 'env-org'
        assert handler.bucket == 'env-bucket'
    
    def test_init_missing_url_raises_error(self):
        """Test that missing URL raises ValueError."""
        with pytest.raises(ValueError, match="InfluxDB URL must be provided"):
            InfluxDBHandler(token='test-token')
    
    def test_init_missing_token_raises_error(self):
        """Test that missing token raises ValueError."""
        with pytest.raises(ValueError, match="InfluxDB token must be provided"):
            InfluxDBHandler(url='http://localhost:8086')
    
    @patch('src.shared_utils.influxdb_client.boto3.client')
    def test_get_token_from_secrets_manager(self, mock_boto_client, mock_influxdb_client):
        """Test token retrieval from AWS Secrets Manager."""
        # Mock secrets manager response
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {'SecretString': 'secret-token'}
        mock_boto_client.return_value = mock_secrets
        
        with patch.dict(os.environ, {
            'INFLUXDB_URL': 'http://localhost:8086',
            'INFLUXDB_TOKEN_SECRET_NAME': 'test-secret'
        }):
            handler = InfluxDBHandler()
            assert handler.token == 'secret-token'
    
    def test_client_property_creates_client(self, mock_influxdb_client, handler_config):
        """Test that client property creates and caches InfluxDB client."""
        handler = InfluxDBHandler(**handler_config)
        
        # First access should create client
        client = handler.client
        assert client is not None
        mock_influxdb_client.ping.assert_called_once()
        
        # Second access should return cached client
        client2 = handler.client
        assert client is client2
        # Ping should still only be called once
        assert mock_influxdb_client.ping.call_count == 1
    
    def test_client_connection_failure_raises_error(self, handler_config):
        """Test that client connection failure raises InfluxDBConnectionError."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client:
            mock_client.side_effect = Exception("Connection failed")
            
            handler = InfluxDBHandler(**handler_config)
            
            with pytest.raises(InfluxDBConnectionError, match="Could not connect to InfluxDB"):
                _ = handler.client
    
    def test_write_api_property(self, mock_influxdb_client, handler_config):
        """Test write_api property returns write API instance."""
        handler = InfluxDBHandler(**handler_config)
        
        write_api = handler.write_api
        assert write_api is not None
        mock_influxdb_client.write_api.assert_called_once()
    
    def test_query_api_property(self, mock_influxdb_client, handler_config):
        """Test query_api property returns query API instance."""
        handler = InfluxDBHandler(**handler_config)
        
        query_api = handler.query_api
        assert query_api is not None
        mock_influxdb_client.query_api.assert_called_once()
    
    def test_health_check_success(self, mock_influxdb_client, handler_config):
        """Test successful health check."""
        handler = InfluxDBHandler(**handler_config)
        
        # Mock successful operations
        mock_influxdb_client.ping.return_value = True
        handler.write_api.write = Mock()
        handler.query_api.query = Mock()
        
        result = handler.health_check()
        
        assert result['status'] == 'healthy'
        assert 'response_time_ms' in result
        assert result['url'] == handler_config['url']
        assert result['org'] == handler_config['org']
        assert result['bucket'] == handler_config['bucket']
        assert 'timestamp' in result
    
    def test_health_check_failure(self, mock_influxdb_client, handler_config):
        """Test health check failure."""
        handler = InfluxDBHandler(**handler_config)
        
        # Mock failed ping
        mock_influxdb_client.ping.side_effect = Exception("Connection failed")
        
        result = handler.health_check()
        
        assert result['status'] == 'unhealthy'
        assert 'error' in result
        assert 'response_time_ms' in result
    
    def test_write_points_single_point_success(self, mock_influxdb_client, handler_config):
        """Test successful write of single point."""
        handler = InfluxDBHandler(**handler_config)
        
        point = Point("test_measurement").field("value", 1.0)
        result = handler.write_points(point)
        
        assert result is True
        handler.write_api.write.assert_called_once()
    
    def test_write_points_multiple_points_success(self, mock_influxdb_client, handler_config):
        """Test successful write of multiple points."""
        handler = InfluxDBHandler(**handler_config)
        
        points = [
            Point("test_measurement").field("value", 1.0),
            Point("test_measurement").field("value", 2.0)
        ]
        result = handler.write_points(points)
        
        assert result is True
        handler.write_api.write.assert_called_once()
    
    def test_write_points_with_custom_bucket(self, mock_influxdb_client, handler_config):
        """Test write points with custom bucket."""
        handler = InfluxDBHandler(**handler_config)
        
        point = Point("test_measurement").field("value", 1.0)
        result = handler.write_points(point, bucket="custom_bucket")
        
        assert result is True
        handler.write_api.write.assert_called_once_with(
            bucket="custom_bucket",
            record=[point],
            write_precision=WritePrecision.NS
        )
    
    def test_write_points_retry_on_failure(self, mock_influxdb_client, handler_config):
        """Test write points retry logic on failure."""
        handler = InfluxDBHandler(**handler_config)
        handler.retry_delay = 0.1  # Speed up test
        
        point = Point("test_measurement").field("value", 1.0)
        
        # Mock first two calls to fail, third to succeed
        handler.write_api.write.side_effect = [
            InfluxDBError("Write failed"),
            InfluxDBError("Write failed"),
            None  # Success
        ]
        
        result = handler.write_points(point)
        
        assert result is True
        assert handler.write_api.write.call_count == 3
    
    def test_write_points_max_retries_exceeded(self, mock_influxdb_client, handler_config):
        """Test write points when max retries exceeded."""
        handler = InfluxDBHandler(**handler_config)
        handler.retry_delay = 0.1  # Speed up test
        
        point = Point("test_measurement").field("value", 1.0)
        
        # Mock all calls to fail
        handler.write_api.write.side_effect = InfluxDBError("Write failed")
        
        with pytest.raises(InfluxDBWriteError, match="Write failed"):
            handler.write_points(point)
        
        assert handler.write_api.write.call_count == handler.max_retries + 1
    
    def test_query_flux_success(self, mock_influxdb_client, handler_config):
        """Test successful Flux query execution."""
        handler = InfluxDBHandler(**handler_config)
        
        # Mock query result
        mock_record = Mock()
        mock_record.get_measurement.return_value = "test_measurement"
        mock_record.get_time.return_value = datetime.now(timezone.utc)
        mock_record.get_field.return_value = "value"
        mock_record.get_value.return_value = 1.0
        mock_record.values = {"tag1": "value1"}
        
        mock_table = Mock()
        mock_table.records = [mock_record]
        
        handler.query_api.query.return_value = [mock_table]
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        result = handler.query_flux(query)
        
        assert len(result) == 1
        assert result[0]['measurement'] == "test_measurement"
        assert result[0]['field'] == "value"
        assert result[0]['value'] == 1.0
        assert result[0]['tags'] == {"tag1": "value1"}
    
    def test_query_flux_with_parameters(self, mock_influxdb_client, handler_config):
        """Test Flux query with parameters."""
        handler = InfluxDBHandler(**handler_config)
        handler.query_api.query.return_value = []
        
        query = 'from(bucket: params.bucket) |> range(start: params.start)'
        params = {"bucket": "test_bucket", "start": "-1h"}
        
        result = handler.query_flux(query, params)
        
        handler.query_api.query.assert_called_once_with(query, params=params)
        assert result == []
    
    def test_query_flux_retry_on_failure(self, mock_influxdb_client, handler_config):
        """Test query retry logic on failure."""
        handler = InfluxDBHandler(**handler_config)
        handler.retry_delay = 0.1  # Speed up test
        
        # Mock first two calls to fail, third to succeed
        handler.query_api.query.side_effect = [
            InfluxDBError("Query failed"),
            InfluxDBError("Query failed"),
            []  # Success
        ]
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        result = handler.query_flux(query)
        
        assert result == []
        assert handler.query_api.query.call_count == 3
    
    def test_query_flux_max_retries_exceeded(self, mock_influxdb_client, handler_config):
        """Test query when max retries exceeded."""
        handler = InfluxDBHandler(**handler_config)
        handler.retry_delay = 0.1  # Speed up test
        
        # Mock all calls to fail
        handler.query_api.query.side_effect = InfluxDBError("Query failed")
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        
        with pytest.raises(InfluxDBQueryError, match="Query failed"):
            handler.query_flux(query)
        
        assert handler.query_api.query.call_count == handler.max_retries + 1
    
    def test_batch_writer_context_manager(self, mock_influxdb_client, handler_config):
        """Test batch writer context manager."""
        handler = InfluxDBHandler(**handler_config)
        
        mock_batch_api = Mock()
        mock_influxdb_client.write_api.return_value = mock_batch_api
        
        with handler.batch_writer(batch_size=500, flush_interval=2000) as batch_api:
            assert batch_api is mock_batch_api
        
        # Verify batch API was closed
        mock_batch_api.close.assert_called_once()
    
    def test_close_cleanup(self, mock_influxdb_client, handler_config):
        """Test proper cleanup when closing handler."""
        handler = InfluxDBHandler(**handler_config)
        
        # Access properties to create API instances
        _ = handler.write_api
        _ = handler.query_api
        _ = handler.client
        
        handler.close()
        
        # Verify all APIs were closed
        handler._write_api.close.assert_called_once()
        handler._query_api.close.assert_called_once()
        handler._client.close.assert_called_once()
        
        # Verify references were cleared
        assert handler._write_api is None
        assert handler._query_api is None
        assert handler._client is None
    
    def test_context_manager(self, mock_influxdb_client, handler_config):
        """Test handler as context manager."""
        with InfluxDBHandler(**handler_config) as handler:
            assert handler is not None
            # Access client to create it
            _ = handler.client
        
        # Verify close was called
        handler._client.close.assert_called_once()
    
    def test_thread_safety(self, mock_influxdb_client, handler_config):
        """Test thread safety of client creation."""
        handler = InfluxDBHandler(**handler_config)
        
        clients = []
        
        def get_client():
            clients.append(handler.client)
        
        # Create multiple threads accessing client
        threads = [threading.Thread(target=get_client) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should get the same client instance
        assert len(set(id(client) for client in clients)) == 1
        
        # Client should only be created once
        assert mock_influxdb_client.ping.call_count == 1


class TestInfluxDBHandlerIntegration:
    """Integration-style tests with more realistic scenarios."""
    
    @pytest.fixture
    def handler(self):
        """Create handler with test configuration."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient'):
            return InfluxDBHandler(
                url='http://localhost:8086',
                token='test-token',
                org='test-org',
                bucket='test-bucket'
            )
    
    def test_write_and_query_workflow(self, handler):
        """Test typical write and query workflow."""
        # Mock successful write
        handler.write_api.write = Mock()
        
        # Write some test data
        points = [
            Point("generation_data")
            .tag("region", "southeast")
            .tag("energy_source", "hydro")
            .field("power_mw", 1000.0)
            .time(datetime.now(timezone.utc)),
            
            Point("generation_data")
            .tag("region", "northeast")
            .tag("energy_source", "wind")
            .field("power_mw", 500.0)
            .time(datetime.now(timezone.utc))
        ]
        
        result = handler.write_points(points)
        assert result is True
        
        # Mock query result
        mock_record = Mock()
        mock_record.get_measurement.return_value = "generation_data"
        mock_record.get_time.return_value = datetime.now(timezone.utc)
        mock_record.get_field.return_value = "power_mw"
        mock_record.get_value.return_value = 750.0
        mock_record.values = {"region": "all"}
        
        mock_table = Mock()
        mock_table.records = [mock_record]
        handler.query_api.query.return_value = [mock_table]
        
        # Query the data
        query = '''
        from(bucket: "test-bucket")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "generation_data")
        |> mean()
        '''
        
        results = handler.query_flux(query)
        assert len(results) == 1
        assert results[0]['value'] == 750.0
    
    def test_error_handling_workflow(self, handler):
        """Test error handling in typical workflow."""
        # Test write failure followed by successful retry
        handler.write_api.write.side_effect = [
            InfluxDBError("Temporary failure"),
            None  # Success on retry
        ]
        handler.retry_delay = 0.1
        
        point = Point("test").field("value", 1.0)
        result = handler.write_points(point)
        
        assert result is True
        assert handler.write_api.write.call_count == 2
        
        # Test query failure followed by successful retry
        handler.query_api.query.side_effect = [
            ApiException("Temporary failure"),
            []  # Success on retry
        ]
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        result = handler.query_flux(query)
        
        assert result == []
        assert handler.query_api.query.call_count == 2