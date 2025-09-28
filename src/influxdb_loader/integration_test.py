#!/usr/bin/env python3
"""
Integration test for InfluxDB Loader Lambda Function

This test demonstrates the complete functionality of the InfluxDB loader
with mock data and services.
"""

import json
import os
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Set up environment for testing
os.environ['INFLUXDB_URL'] = 'http://localhost:8086'
os.environ['INFLUXDB_ORG'] = 'test-org'
os.environ['INFLUXDB_BUCKET'] = 'test-bucket'
os.environ['MAX_BATCH_SIZE'] = '100'
os.environ['MAX_RETRIES'] = '2'
os.environ['ENABLE_METRICS'] = 'false'

# Import after setting environment
from lambda_function import lambda_handler


def create_test_event(dataset_type: str = 'generation') -> dict:
    """Create a test S3 event."""
    return {
        'Records': [{
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': f'processed/dataset={dataset_type}/year=2024/month=01/day=01/file.parquet'}
            }
        }]
    }


def create_test_dataframe(dataset_type: str = 'generation') -> pd.DataFrame:
    """Create test DataFrame based on dataset type."""
    base_data = {
        'timestamp': [
            '2024-01-01T00:00:00Z',
            '2024-01-01T01:00:00Z',
            '2024-01-01T02:00:00Z'
        ],
        'region': ['southeast', 'northeast', 'south'],
        'value': [1500.5, 2200.3, 1800.7],
        'unit': ['MW', 'MW', 'MW']
    }
    
    if dataset_type == 'generation':
        base_data.update({
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power', 'power', 'power']
        })
    elif dataset_type == 'consumption':
        base_data.update({
            'consumer_type': ['industrial', 'residential', 'commercial'],
            'measurement_type': ['demand', 'demand', 'demand']
        })
    elif dataset_type == 'transmission':
        base_data.update({
            'line_id': ['line_001', 'line_002', 'line_003'],
            'measurement_type': ['flow', 'flow', 'flow']
        })
    
    return pd.DataFrame(base_data)


@patch('lambda_function.InfluxDBHandler')
@patch('lambda_function.convert_parquet_to_influxdb_points')
@patch('lambda_function.load_parquet_from_s3')
@patch('lambda_function.get_dataset_type_from_s3_key')
def test_complete_workflow(
    mock_get_dataset_type,
    mock_load_parquet,
    mock_convert_points,
    mock_influx_handler_class
):
    """Test the complete workflow from S3 event to InfluxDB write."""
    
    print("🧪 Testing Complete InfluxDB Loader Workflow")
    print("=" * 50)
    
    # Setup test data
    dataset_type = 'generation'
    test_df = create_test_dataframe(dataset_type)
    test_event = create_test_event(dataset_type)
    
    print(f"📊 Test data: {len(test_df)} records of type '{dataset_type}'")
    
    # Setup mocks
    mock_get_dataset_type.return_value = dataset_type
    mock_load_parquet.return_value = test_df
    
    # Mock InfluxDB points with proper attributes
    mock_points = []
    for i in range(len(test_df)):
        mock_point = Mock()
        mock_point._name = 'generation_data'
        mock_point._fields = {'power_mw': 1500.0 + i * 100}
        mock_point._tags = {'region': f'region_{i}', 'energy_source': 'hydro'}
        mock_point._time = datetime.now(timezone.utc)
        mock_points.append(mock_point)
    
    mock_convert_points.return_value = mock_points
    
    # Mock InfluxDB handler
    mock_handler = Mock()
    mock_handler.health_check.return_value = {
        'status': 'healthy',
        'response_time_ms': 25.5,
        'url': 'http://localhost:8086'
    }
    mock_handler.write_points.return_value = True
    mock_influx_handler_class.return_value.__enter__.return_value = mock_handler
    
    print("🔧 Mocks configured")
    
    # Execute lambda handler
    print("🚀 Executing lambda handler...")
    result = lambda_handler(test_event, Mock())
    
    # Verify results
    print("✅ Verifying results...")
    
    assert result['statusCode'] == 200, f"Expected 200, got {result['statusCode']}"
    assert result['message'] == "Data loaded successfully"
    assert result['data']['dataset_type'] == dataset_type
    assert result['data']['points_written'] == len(test_df)
    assert result['data']['source_records'] == len(test_df)
    
    print(f"✅ Status Code: {result['statusCode']}")
    print(f"✅ Points Written: {result['data']['points_written']}")
    print(f"✅ Processing Time: {result['data']['processing_time_seconds']}s")
    print(f"✅ Dataset Type: {result['data']['dataset_type']}")
    
    # Verify mock calls
    mock_get_dataset_type.assert_called_once()
    mock_load_parquet.assert_called_once()
    mock_convert_points.assert_called_once()
    mock_handler.health_check.assert_called_once()
    mock_handler.write_points.assert_called_once()
    
    print("✅ All mock calls verified")
    print("🎉 Integration test PASSED!")
    
    return result


@patch('lambda_function.InfluxDBHandler')
def test_error_handling(mock_influx_handler_class):
    """Test error handling scenarios."""
    
    print("\n🧪 Testing Error Handling")
    print("=" * 50)
    
    # Test InfluxDB connection error
    mock_handler = Mock()
    mock_handler.health_check.return_value = {
        'status': 'unhealthy',
        'error': 'Connection timeout'
    }
    mock_influx_handler_class.return_value.__enter__.return_value = mock_handler
    
    test_event = create_test_event()
    
    print("🔧 Testing unhealthy InfluxDB connection...")
    result = lambda_handler(test_event, Mock())
    
    assert result['statusCode'] == 503
    assert 'InfluxDB unavailable' in result['message']
    print("✅ InfluxDB connection error handled correctly")
    
    # Test invalid event format
    print("🔧 Testing invalid event format...")
    invalid_event = {'invalid': 'event'}
    result = lambda_handler(invalid_event, Mock())
    
    assert result['statusCode'] == 400
    assert result['message'] == "Invalid event format"
    print("✅ Invalid event error handled correctly")
    
    print("🎉 Error handling tests PASSED!")


def test_multiple_event_formats():
    """Test different event format support."""
    
    print("\n🧪 Testing Multiple Event Formats")
    print("=" * 50)
    
    from lambda_function import extract_s3_info
    
    # Test S3 event
    s3_event = {
        'Records': [{
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'test/dataset=generation/file.parquet'}
            }
        }]
    }
    
    result = extract_s3_info(s3_event)
    assert result['bucket'] == 'test-bucket'
    assert result['key'] == 'test/dataset=generation/file.parquet'
    print("✅ S3 event format supported")
    
    # Test Step Functions event
    step_functions_event = {
        'bucket': 'test-bucket',
        'key': 'test/dataset=consumption/file.parquet'
    }
    
    result = extract_s3_info(step_functions_event)
    assert result['bucket'] == 'test-bucket'
    assert result['key'] == 'test/dataset=consumption/file.parquet'
    print("✅ Step Functions event format supported")
    
    # Test API Gateway event
    api_gateway_event = {
        'body': json.dumps({
            'bucket': 'test-bucket',
            'key': 'test/dataset=transmission/file.parquet'
        })
    }
    
    result = extract_s3_info(api_gateway_event)
    assert result['bucket'] == 'test-bucket'
    assert result['key'] == 'test/dataset=transmission/file.parquet'
    print("✅ API Gateway event format supported")
    
    print("🎉 Multiple event format tests PASSED!")


def main():
    """Run all integration tests."""
    print("🚀 Starting InfluxDB Loader Integration Tests")
    print("=" * 60)
    
    try:
        # Run tests
        test_complete_workflow()
        test_error_handling()
        test_multiple_event_formats()
        
        print("\n" + "=" * 60)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ InfluxDB Loader implementation is working correctly")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {str(e)}")
        print("=" * 60)
        return False


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)