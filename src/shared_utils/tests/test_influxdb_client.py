"""
Unit tests for InfluxDB client handler.

Tests the InfluxDBHandler class functionality including connection management,
error handling, retry logic, and data operations.
"""

import os
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

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
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        with patch.dict(os.environ, {
            'INFLUXDB_URL': 'http://localhost:8086',
            'INFLUXDB_TOKEN': 'test-token',
            'INFLUXDB_ORG': 'test-org',
            'INFLUXDB_BUCKET': 'test-bucket'
        }):
            yield
    
    @pytest.fixture
    def handler(self, mock_env_vars):
        """Create InfluxDBHandler instance for testing."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client_class.return_value = mock_client
            
            handler = InfluxDBHandler()
            handler._client = mock_client
            yield handler
    
    def test_init_with_parameters(self):
        """Test initialization with explicit parameters."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient'):
            handler = InfluxDBHandler(
                url='http://test:8086',
                token='test-token',
                org='test-org',
                bucket='test-bucket',
                timeout=60000,
                max_retries=5,
                retry_delay=2.0
            )
            
            assert handler.url == 'http://test:8086'
            assert handler.token == 'test-token'
            assert handler.org == 'test-org'
            assert handler.bucket == 'test-bucket'
            assert handler.timeout == 60000
            assert handler.max_retries == 5
            assert handler.retry_delay == 2.0
    
    def test_init_with_env_vars(self, mock_env_vars):
        """Test initialization with environment variables."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient'):
            handler = InfluxDBHandler()
            
            assert handler.url == 'http://localhost:8086'
            assert handler.token == 'test-token'
            assert handler.org == 'test-org'
            assert handler.bucket == 'test-bucket'
    
    def test_init_missing_url(self):
        """Test initialization fails without URL."""
        with pytest.raises(ValueError, match="InfluxDB URL must be provided"):
            InfluxDBHandler(token='test-token')
    
    def test_init_missing_token(self):
        """Test initialization fails without token."""
        with pytest.raises(ValueError, match="InfluxDB token must be provided"):
            InfluxDBHandler(url='http://localhost:8086')
    
    @patch('boto3.client')
    def test_get_token_from_secrets_manager(self, mock_boto_client):
        """Test token retrieval from AWS Secrets Manager."""
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {'SecretString': 'secret-token'}
        mock_boto_client.return_value = mock_secrets
        
        with patch.dict(os.environ, {
            'INFLUXDB_URL': 'http://localhost:8086',
            'INFLUXDB_TOKEN_SECRET_NAME': 'influxdb-token'
        }):
            with patch('src.shared_utils.influxdb_client.InfluxDBClient'):
                handler = InfluxDBHandler()
                assert handler.token == 'secret-token'
    
    def test_client_property_creates_connection(self, handler):
        """Test client property creates and caches connection."""
        # Reset client to test lazy initialization
        handler._client = None
        
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client_class.return_value = mock_client
            
            # First access should create client
            client1 = handler.client
            assert client1 is mock_client
            mock_client_class.assert_called_once()
            
            # Second access should return cached client
            client2 = handler.client
            assert client2 is client1
            assert mock_client_class.call_count == 1
    
    def test_client_connection_failure(self, handler):
        """Test client connection failure handling."""
        handler._client = None
        
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(InfluxDBConnectionError, match="Could not connect to InfluxDB"):
                _ = handler.client
    
    def test_health_check_success(self, handler):
        """Test successful health check."""
        mock_write_api = Mock()
        mock_query_api = Mock()
        handler._write_api = mock_write_api
        handler._query_api = mock_query_api
        
        handler._client.ping.return_value = True
        
        result = handler.health_check()
        
        assert result['status'] == 'healthy'
        assert 'response_time_ms' in result
        assert result['url'] == handler.url
        assert result['org'] == handler.org
        assert result['bucket'] == handler.bucket
        assert 'timestamp' in result
        
        mock_write_api.write.assert_called_once()
        mock_query_api.query.assert_called_once()
    
    def test_health_check_failure(self, handler):
        """Test health check failure handling."""
        handler._client.ping.side_effect = Exception("Connection failed")
        
        result = handler.health_check()
        
        assert result['status'] == 'unhealthy'
        assert 'error' in result
        assert 'response_time_ms' in result
        assert result['url'] == handler.url
    
    def test_write_points_single_point(self, handler):
        """Test writing a single point."""
        mock_write_api = Mock()
        handler._write_api = mock_write_api
        
        point = Point("test_measurement").field("value", 1.0)
        
        result = handler.write_points(point)
        
        assert result is True
        mock_write_api.write.assert_called_once_with(
            bucket=handler.bucket,
            record=[point],
            write_precision=WritePrecision.NS
        )
    
    def test_write_points_multiple_points(self, handler):
        """Test writing multiple points."""
        mock_write_api = Mock()
        handler._write_api = mock_write_api
        
        points = [
            Point("test_measurement").field("value", 1.0),
            Point("test_measurement").field("value", 2.0)
        ]
        
        result = handler.write_points(points, bucket="custom_bucket")
        
        assert result is True
        mock_write_api.write.assert_called_once_with(
            bucket="custom_bucket",
            record=points,
            write_precision=WritePrecision.NS
        )
    
    def test_write_points_with_retry(self, handler):
        """Test write points with retry logic."""
        mock_write_api = Mock()
        handler._write_api = mock_write_api
        handler.retry_delay = 0.01  # Speed up test
        
        # First call fails, second succeeds
        mock_write_api.write.side_effect = [InfluxDBError("Temporary error"), None]
        
        point = Point("test_measurement").field("value", 1.0)
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = handler.write_points(point)
        
        assert result is True
        assert mock_write_api.write.call_count == 2
    
    def test_write_points_max_retries_exceeded(self, handler):
        """Test write points fails after max retries."""
        mock_write_api = Mock()
        handler._write_api = mock_write_api
        handler.max_retries = 2
        handler.retry_delay = 0.01
        
        mock_write_api.write.side_effect = InfluxDBError("Persistent error")
        
        point = Point("test_measurement").field("value", 1.0)
        
        with patch('time.sleep'):
            with pytest.raises(InfluxDBWriteError, match="Write failed"):
                handler.write_points(point)
        
        assert mock_write_api.write.call_count == 3  # Initial + 2 retries
    
    def test_query_flux_success(self, handler):
        """Test successful Flux query execution."""
        mock_query_api = Mock()
        handler._query_api = mock_query_api
        
        # Mock query result
        mock_record = Mock()
        mock_record.get_measurement.return_value = "test_measurement"
        mock_record.get_time.return_value = datetime.now(timezone.utc)
        mock_record.get_field.return_value = "value"
        mock_record.get_value.return_value = 1.0
        mock_record.values = {"tag1": "value1"}
        
        mock_table = Mock()
        mock_table.records = [mock_record]
        mock_query_api.query.return_value = [mock_table]
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        result = handler.query_flux(query)
        
        assert len(result) == 1
        assert result[0]['measurement'] == "test_measurement"
        assert result[0]['field'] == "value"
        assert result[0]['value'] == 1.0
        assert result[0]['tags'] == {"tag1": "value1"}
        
        mock_query_api.query.assert_called_once_with(query, params=None)
    
    def test_query_flux_with_params(self, handler):
        """Test Flux query with parameters."""
        mock_query_api = Mock()
        handler._query_api = mock_query_api
        mock_query_api.query.return_value = []
        
        query = 'from(bucket: params.bucket) |> range(start: params.start)'
        params = {"bucket": "test_bucket", "start": "-1h"}
        
        handler.query_flux(query, params)
        
        mock_query_api.query.assert_called_once_with(query, params=params)
    
    def test_query_flux_with_retry(self, handler):
        """Test query with retry logic."""
        mock_query_api = Mock()
        handler._query_api = mock_query_api
        handler.retry_delay = 0.01
        
        # First call fails, second succeeds
        mock_query_api.query.side_effect = [InfluxDBError("Temporary error"), []]
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        
        with patch('time.sleep'):
            result = handler.query_flux(query)
        
        assert result == []
        assert mock_query_api.query.call_count == 2
    
    def test_query_flux_max_retries_exceeded(self, handler):
        """Test query fails after max retries."""
        mock_query_api = Mock()
        handler._query_api = mock_query_api
        handler.max_retries = 2
        handler.retry_delay = 0.01
        
        mock_query_api.query.side_effect = InfluxDBError("Persistent error")
        
        query = 'from(bucket: "test") |> range(start: -1h)'
        
        with patch('time.sleep'):
            with pytest.raises(InfluxDBQueryError, match="Query failed"):
                handler.query_flux(query)
        
        assert mock_query_api.query.call_count == 3
    
    def test_batch_writer_context_manager(self, handler):
        """Test batch writer context manager."""
        mock_batch_api = Mock()
        
        with patch.object(handler.client, 'write_api', return_value=mock_batch_api):
            with handler.batch_writer(batch_size=500, flush_interval=2000) as batch_api:
                assert batch_api is mock_batch_api
            
            mock_batch_api.close.assert_called_once()
    
    def test_close_cleanup(self, handler):
        """Test proper cleanup on close."""
        mock_write_api = Mock()
        mock_query_api = Mock()
        mock_client = Mock()
        
        handler._write_api = mock_write_api
        handler._query_api = mock_query_api
        handler._client = mock_client
        
        handler.close()
        
        mock_write_api.close.assert_called_once()
        mock_query_api.close.assert_called_once()
        mock_client.close.assert_called_once()
        
        assert handler._write_api is None
        assert handler._query_api is None
        assert handler._client is None
    
    def test_context_manager(self, mock_env_vars):
        """Test context manager functionality."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient'):
            with InfluxDBHandler() as handler:
                assert isinstance(handler, InfluxDBHandler)
            
            # Close should be called automatically
            # (We can't easily test this without more complex mocking)
    
    def test_thread_safety(self, handler):
        """Test thread safety of client initialization."""
        import threading
        
        handler._client = None
        clients = []
        
        def get_client():
            clients.append(handler.client)
        
        # Create multiple threads trying to access client
        threads = [threading.Thread(target=get_client) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should get the same client instance
        assert len(set(id(client) for client in clients)) == 1


class TestInfluxDBHandlerIntegration:
    """Integration-style tests that test multiple components together."""
    
    @pytest.fixture
    def mock_influxdb_client(self):
        """Mock the entire InfluxDB client stack."""
        with patch('src.shared_utils.influxdb_client.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_write_api = Mock()
            mock_query_api = Mock()
            
            mock_client.ping.return_value = True
            mock_client.write_api.return_value = mock_write_api
            mock_client.query_api.return_value = mock_query_api
            
            mock_client_class.return_value = mock_client
            
            yield {
                'client_class': mock_client_class,
                'client': mock_client,
                'write_api': mock_write_api,
                'query_api': mock_query_api
            }
    
    def test_full_workflow(self, mock_influxdb_client):
        """Test complete workflow from initialization to data operations."""
        with patch.dict(os.environ, {
            'INFLUXDB_URL': 'http://localhost:8086',
            'INFLUXDB_TOKEN': 'test-token',
            'INFLUXDB_ORG': 'test-org',
            'INFLUXDB_BUCKET': 'test-bucket'
        }):
            # Initialize handler
            handler = InfluxDBHandler()
            
            # Test health check
            health = handler.health_check()
            assert health['status'] == 'healthy'
            
            # Test write operation
            point = Point("temperature").tag("location", "office").field("value", 23.5)
            success = handler.write_points(point)
            assert success is True
            
            # Test query operation
            mock_influxdb_client['query_api'].query.return_value = []
            results = handler.query_flux('from(bucket: "test") |> range(start: -1h)')
            assert results == []
            
            # Test cleanup
            handler.close()
            
            # Verify all APIs were used
            mock_influxdb_client['write_api'].write.assert_called()
            mock_influxdb_client['query_api'].query.assert_called()