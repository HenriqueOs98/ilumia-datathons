"""
Unit tests for InfluxDB Monitor Lambda Function.
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Mock the shared_utils imports before importing the lambda function
with patch.dict('sys.modules', {
    'shared_utils.influxdb_client': Mock(),
    'shared_utils.logging_config': Mock()
}):
    from lambda_function import InfluxDBMonitor, lambda_handler


class TestInfluxDBMonitor:
    """Test cases for InfluxDBMonitor class."""
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_init(self, mock_boto3, mock_influx_handler):
        """Test InfluxDBMonitor initialization."""
        monitor = InfluxDBMonitor()
        
        assert monitor.namespace == 'ONS/InfluxDB'
        assert monitor.environment == 'dev'
        assert 'simple_query' in monitor.test_queries
        assert 'aggregation_query' in monitor.test_queries
        assert 'complex_query' in monitor.test_queries
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_perform_health_check_success(self, mock_boto3, mock_influx_handler):
        """Test successful health check."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.health_check.return_value = {
            'status': 'healthy',
            'response_time_ms': 150.5,
            'url': 'http://test-influxdb:8086',
            'org': 'ons-energy',
            'bucket': 'energy_data'
        }
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.perform_health_check()
        
        assert result['status'] == 'healthy'
        assert result['connectivity_status'] == 'connected'
        assert 'total_check_time_ms' in result
        assert result['environment'] == 'dev'
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_perform_health_check_failure(self, mock_boto3, mock_influx_handler):
        """Test health check failure."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.health_check.side_effect = Exception("Connection failed")
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.perform_health_check()
        
        assert result['status'] == 'unhealthy'
        assert result['connectivity_status'] == 'disconnected'
        assert 'error' in result
        assert 'Connection failed' in result['error']
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_measure_query_performance_success(self, mock_boto3, mock_influx_handler):
        """Test successful query performance measurement."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.query_flux.return_value = [
            {'measurement': 'power_mw', 'value': 1000.0},
            {'measurement': 'power_mw', 'value': 1100.0}
        ]
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.measure_query_performance()
        
        assert 'simple_query' in result
        assert 'aggregation_query' in result
        assert 'complex_query' in result
        
        for query_name, metrics in result.items():
            assert metrics['status'] == 'success'
            assert 'execution_time_ms' in metrics
            assert 'result_count' in metrics
            assert metrics['result_count'] == 2
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_measure_query_performance_failure(self, mock_boto3, mock_influx_handler):
        """Test query performance measurement with failures."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.query_flux.side_effect = Exception("Query failed")
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.measure_query_performance()
        
        for query_name, metrics in result.items():
            assert metrics['status'] == 'error'
            assert 'error' in metrics
            assert metrics['result_count'] == 0
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    @patch('lambda_function.Point')
    def test_measure_write_performance_success(self, mock_point, mock_boto3, mock_influx_handler):
        """Test successful write performance measurement."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.write_points.return_value = True
        mock_influx_handler.return_value = mock_handler
        
        mock_point_instance = Mock()
        mock_point.return_value = mock_point_instance
        mock_point_instance.tag.return_value = mock_point_instance
        mock_point_instance.field.return_value = mock_point_instance
        mock_point_instance.time.return_value = mock_point_instance
        
        monitor = InfluxDBMonitor()
        result = monitor.measure_write_performance()
        
        assert result['status'] == 'success'
        assert result['points_written'] == 100
        assert 'write_time_ms' in result
        assert 'write_throughput_points_per_sec' in result
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_collect_resource_metrics_success(self, mock_boto3, mock_influx_handler):
        """Test successful resource metrics collection."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.query_flux.return_value = [
            {'field': 'cpu_usage', 'value': 45.5},
            {'field': 'memory_usage', 'value': 60.2},
            {'field': 'disk_usage', 'value': 30.1},
            {'field': 'connections', 'value': 25},
            {'field': 'query_queue', 'value': 3}
        ]
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.collect_resource_metrics()
        
        assert result['cpu_usage_percent'] == 45.5
        assert result['memory_usage_percent'] == 60.2
        assert result['disk_usage_percent'] == 30.1
        assert result['active_connections'] == 25
        assert result['query_queue_length'] == 3
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_collect_resource_metrics_failure(self, mock_boto3, mock_influx_handler):
        """Test resource metrics collection failure."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.query_flux.side_effect = Exception("Monitoring data unavailable")
        mock_influx_handler.return_value = mock_handler
        
        monitor = InfluxDBMonitor()
        result = monitor.collect_resource_metrics()
        
        assert result['cpu_usage_percent'] == 0
        assert result['memory_usage_percent'] == 0
        assert result['disk_usage_percent'] == 0
        assert 'error' in result
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_estimate_costs(self, mock_boto3, mock_influx_handler):
        """Test cost estimation."""
        # Setup mocks
        mock_handler = Mock()
        mock_handler.query_flux.return_value = [
            {'value': 10737418240}  # 10 GB in bytes
        ]
        mock_influx_handler.return_value = mock_handler
        
        with patch.dict(os.environ, {'INFLUXDB_INSTANCE_TYPE': 'db.influx.large'}):
            monitor = InfluxDBMonitor()
            result = monitor.estimate_costs()
        
        assert result['instance_type'] == 'db.influx.large'
        assert result['storage_gb'] == 10.0
        assert 'estimated_hourly_cost_usd' in result
        assert 'estimated_daily_cost_usd' in result
        assert 'estimated_monthly_cost_usd' in result
    
    @patch('lambda_function.InfluxDBHandler')
    @patch('lambda_function.boto3.client')
    def test_publish_connectivity_metrics(self, mock_boto3, mock_influx_handler):
        """Test CloudWatch metrics publishing for connectivity."""
        mock_cloudwatch = Mock()
        mock_boto3.return_value = mock_cloudwatch
        
        monitor = InfluxDBMonitor()
        health_data = {
            'status': 'healthy',
            'response_time_ms': 200.5
        }
        
        monitor._publish_connectivity_metrics(health_data)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'ONS/InfluxDB'
        metrics = call_args[1]['MetricData']
        assert len(metrics) == 2
        assert any(m['MetricName'] == 'ConnectionStatus' for m in metrics)
        assert any(m['MetricName'] == 'HealthCheckResponseTime' for m in metrics)


class TestLambdaHandler:
    """Test cases for lambda_handler function."""
    
    @patch('lambda_function.InfluxDBMonitor')
    def test_lambda_handler_success(self, mock_monitor_class):
        """Test successful lambda handler execution."""
        # Setup mocks
        mock_monitor = Mock()
        mock_monitor.environment = 'test'
        mock_monitor.perform_health_check.return_value = {'status': 'healthy'}
        mock_monitor.measure_query_performance.return_value = {'simple_query': {'status': 'success'}}
        mock_monitor.measure_write_performance.return_value = {'status': 'success'}
        mock_monitor.collect_resource_metrics.return_value = {'cpu_usage_percent': 50}
        mock_monitor.estimate_costs.return_value = {'estimated_daily_cost_usd': 25.0}
        mock_monitor_class.return_value = mock_monitor
        
        event = {}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['overall_status'] == 'healthy'
        assert 'health_check' in body
        assert 'query_performance' in body
        assert 'write_performance' in body
        assert 'resource_metrics' in body
        assert 'cost_estimation' in body
    
    @patch('lambda_function.InfluxDBMonitor')
    def test_lambda_handler_unhealthy(self, mock_monitor_class):
        """Test lambda handler with unhealthy InfluxDB."""
        # Setup mocks
        mock_monitor = Mock()
        mock_monitor.environment = 'test'
        mock_monitor.perform_health_check.return_value = {'status': 'unhealthy'}
        mock_monitor.measure_query_performance.return_value = {}
        mock_monitor.measure_write_performance.return_value = {'status': 'error'}
        mock_monitor.collect_resource_metrics.return_value = {}
        mock_monitor.estimate_costs.return_value = {}
        mock_monitor_class.return_value = mock_monitor
        
        event = {}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['overall_status'] == 'unhealthy'
    
    @patch('lambda_function.InfluxDBMonitor')
    def test_lambda_handler_exception(self, mock_monitor_class):
        """Test lambda handler with exception."""
        # Setup mocks
        mock_monitor_class.side_effect = Exception("Monitor initialization failed")
        
        event = {}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['status'] == 'error'
        assert 'Monitor initialization failed' in body['error']


if __name__ == '__main__':
    pytest.main([__file__])