"""
Unit tests for InfluxDB Loader Lambda Function
"""

import json
import os
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Import the lambda function
from lambda_function import (
    lambda_handler,
    extract_s3_info,
    load_parquet_from_s3,
    load_data_to_influxdb,
    send_metrics,
    create_response
)


class TestInfluxDBLoaderLambda:
    """Test cases for InfluxDB Loader Lambda function."""
    
    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ['INFLUXDB_URL'] = 'http://localhost:8086'
        os.environ['INFLUXDB_ORG'] = 'test-org'
        os.environ['INFLUXDB_BUCKET'] = 'test-bucket'
        os.environ['MAX_BATCH_SIZE'] = '100'
        os.environ['MAX_RETRIES'] = '2'
        os.environ['ENABLE_METRICS'] = 'false'  # Disable for tests
    
    def test_extract_s3_info_s3_event(self):
        """Test extracting S3 info from S3 event."""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test/dataset=generation/file.parquet'}
                }
            }]
        }
        
        result = extract_s3_info(event)
        
        assert result is not None
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'test/dataset=generation/file.parquet'
    
    def test_extract_s3_info_step_functions(self):
        """Test extracting S3 info from Step Functions event."""
        event = {
            'bucket': 'test-bucket',
            'key': 'test/dataset=consumption/file.parquet'
        }
        
        result = extract_s3_info(event)
        
        assert result is not None
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'test/dataset=consumption/file.parquet'
    
    def test_extract_s3_info_api_gateway(self):
        """Test extracting S3 info from API Gateway event."""
        event = {
            'body': json.dumps({
                'bucket': 'test-bucket',
                'key': 'test/dataset=transmission/file.parquet'
            })
        }
        
        result = extract_s3_info(event)
        
        assert result is not None
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'test/dataset=transmission/file.parquet'
    
    def test_extract_s3_info_invalid_event(self):
        """Test extracting S3 info from invalid event."""
        event = {'invalid': 'event'}
        
        result = extract_s3_info(event)
        
        assert result is None
    
    @patch('lambda_function.s3_client')
    def test_load_parquet_from_s3_success(self, mock_s3_client):
        """Test successful Parquet loading from S3."""
        # Mock S3 response
        mock_response = {
            'Body': Mock()
        }
        mock_s3_client.get_object.return_value = mock_response
        
        # Mock pandas read_parquet
        test_df = pd.DataFrame({
            'timestamp': ['2024-01-01T00:00:00Z'],
            'region': ['southeast'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power']
        })
        
        with patch('pandas.read_parquet', return_value=test_df):
            result = load_parquet_from_s3('test-bucket', 'test-key')
        
        assert not result.empty
        assert len(result) == 1
        assert 'timestamp' in result.columns
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='test-key'
        )
    
    @patch('lambda_function.s3_client')
    def test_load_parquet_from_s3_not_found(self, mock_s3_client):
        """Test Parquet loading when file not found."""
        from botocore.exceptions import ClientError
        
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}},
            'GetObject'
        )
        
        with pytest.raises(FileNotFoundError):
            load_parquet_from_s3('test-bucket', 'nonexistent-key')
    
    def test_load_data_to_influxdb_success(self):
        """Test successful data loading to InfluxDB."""
        # Mock InfluxDB handler
        mock_handler = Mock()
        mock_handler.write_points.return_value = True
        
        # Mock points
        mock_points = [Mock() for _ in range(150)]  # More than batch size
        
        result = load_data_to_influxdb(mock_handler, mock_points, 'generation')
        
        assert result['points_written'] == 150
        assert result['batches_processed'] == 2  # 100 + 50
        assert result['failed_batches'] == 0
        assert result['success_rate'] == 100.0
        
        # Verify write_points was called for each batch
        assert mock_handler.write_points.call_count == 2
    
    def test_load_data_to_influxdb_partial_failure(self):
        """Test data loading with some batch failures."""
        # Mock InfluxDB handler with alternating success/failure
        mock_handler = Mock()
        mock_handler.write_points.side_effect = [True, Exception("Write failed"), True]
        
        # Mock points
        mock_points = [Mock() for _ in range(250)]  # 3 batches
        
        # Enable dropping invalid records
        os.environ['DROP_INVALID_RECORDS'] = 'true'
        
        result = load_data_to_influxdb(mock_handler, mock_points, 'generation')
        
        assert result['points_written'] == 200  # 2 successful batches
        assert result['batches_processed'] == 2
        assert result['failed_batches'] == 1
        assert result['success_rate'] < 100.0
    
    @patch('lambda_function.cloudwatch_client')
    def test_send_metrics(self, mock_cloudwatch):
        """Test sending metrics to CloudWatch."""
        load_result = {
            'points_written': 100,
            'batches_processed': 1,
            'failed_batches': 0,
            'success_rate': 100.0
        }
        
        send_metrics('generation', load_result, 5.5, 100)
        
        # Verify CloudWatch put_metric_data was called
        mock_cloudwatch.put_metric_data.assert_called_once()
        
        # Check the metrics data
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'ONS/InfluxDB'
        assert len(call_args[1]['MetricData']) >= 6  # At least 6 metrics
    
    def test_create_response(self):
        """Test response creation."""
        response = create_response(200, "Success", {"key": "value"})
        
        assert response['statusCode'] == 200
        assert response['message'] == "Success"
        assert response['data']['key'] == "value"
        assert 'timestamp' in response
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.convert_parquet_to_influxdb_points')
    @patch('lambda_function.load_parquet_from_s3')
    @patch('lambda_function.get_dataset_type_from_s3_key')
    def test_lambda_handler_success(
        self,
        mock_get_dataset_type,
        mock_load_parquet,
        mock_convert_points,
        mock_influx_handler_class
    ):
        """Test successful lambda handler execution."""
        # Setup mocks
        mock_get_dataset_type.return_value = 'generation'
        
        test_df = pd.DataFrame({
            'timestamp': ['2024-01-01T00:00:00Z'],
            'region': ['southeast'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power']
        })
        mock_load_parquet.return_value = test_df
        
        mock_points = [Mock() for _ in range(10)]
        mock_convert_points.return_value = mock_points
        
        mock_handler = Mock()
        mock_handler.health_check.return_value = {'status': 'healthy'}
        mock_handler.write_points.return_value = True
        mock_influx_handler_class.return_value.__enter__.return_value = mock_handler
        
        # Test event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test/dataset=generation/file.parquet'}
                }
            }]
        }
        
        # Execute lambda handler
        result = lambda_handler(event, Mock())
        
        # Verify response
        assert result['statusCode'] == 200
        assert result['message'] == "Data loaded successfully"
        assert result['data']['dataset_type'] == 'generation'
        assert result['data']['points_written'] == 10
    
    @patch('lambda_function.InfluxDBHandler')
    def test_lambda_handler_influxdb_unhealthy(self, mock_influx_handler_class):
        """Test lambda handler with unhealthy InfluxDB."""
        mock_handler = Mock()
        mock_handler.health_check.return_value = {
            'status': 'unhealthy',
            'error': 'Connection failed'
        }
        mock_influx_handler_class.return_value.__enter__.return_value = mock_handler
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test/dataset=generation/file.parquet'}
                }
            }]
        }
        
        result = lambda_handler(event, Mock())
        
        assert result['statusCode'] == 503
        assert 'InfluxDB unavailable' in result['message']
    
    def test_lambda_handler_invalid_event(self):
        """Test lambda handler with invalid event."""
        event = {'invalid': 'event'}
        
        result = lambda_handler(event, Mock())
        
        assert result['statusCode'] == 400
        assert result['message'] == "Invalid event format"
    
    @patch('lambda_function.get_dataset_type_from_s3_key')
    def test_lambda_handler_unknown_dataset_type(self, mock_get_dataset_type):
        """Test lambda handler with unknown dataset type."""
        mock_get_dataset_type.return_value = None
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test/unknown/file.parquet'}
                }
            }]
        }
        
        result = lambda_handler(event, Mock())
        
        assert result['statusCode'] == 400
        assert 'Unable to determine dataset type' in result['message']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])