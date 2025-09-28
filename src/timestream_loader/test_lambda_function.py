"""
Unit tests for Timestream Loader Lambda Function
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json
import os

# Set environment variables for testing
os.environ['TIMESTREAM_DATABASE_NAME'] = 'test_database'
os.environ['GENERATION_TABLE_NAME'] = 'generation_data'
os.environ['CONSUMPTION_TABLE_NAME'] = 'consumption_data'
os.environ['TRANSMISSION_TABLE_NAME'] = 'transmission_data'

from lambda_function import (
    lambda_handler,
    extract_s3_info,
    determine_dataset_type,
    validate_data_schema,
    convert_to_timestream_records,
    get_table_name
)


class TestTimestreamLoader:
    """Test class for Timestream Loader Lambda function."""
    
    def test_extract_s3_info_from_s3_event(self):
        """Test extracting S3 info from S3 event."""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'test-key.parquet'}
                }
            }]
        }
        
        result = extract_s3_info(event)
        assert result == {'bucket': 'test-bucket', 'key': 'test-key.parquet'}
    
    def test_extract_s3_info_from_step_functions(self):
        """Test extracting S3 info from Step Functions event."""
        event = {
            'bucket': 'test-bucket',
            'key': 'test-key.parquet'
        }
        
        result = extract_s3_info(event)
        assert result == {'bucket': 'test-bucket', 'key': 'test-key.parquet'}
    
    def test_extract_s3_info_invalid_event(self):
        """Test extracting S3 info from invalid event."""
        event = {'invalid': 'event'}
        
        result = extract_s3_info(event)
        assert result is None
    
    def test_determine_dataset_type(self):
        """Test determining dataset type from object key."""
        assert determine_dataset_type('dataset=generation/year=2024/file.parquet') == 'generation'
        assert determine_dataset_type('dataset=consumption/year=2024/file.parquet') == 'consumption'
        assert determine_dataset_type('dataset=transmission/year=2024/file.parquet') == 'transmission'
        assert determine_dataset_type('invalid/path/file.parquet') is None
    
    def test_validate_data_schema_generation_valid(self):
        """Test data schema validation for valid generation data."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00'],
            'region': ['SE'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power']
        })
        
        result = validate_data_schema(df, 'generation')
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_data_schema_missing_columns(self):
        """Test data schema validation with missing columns."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00'],
            'region': ['SE']
        })
        
        result = validate_data_schema(df, 'generation')
        assert result['valid'] is False
        assert 'Missing required columns' in result['errors'][0]
    
    def test_validate_data_schema_invalid_timestamp(self):
        """Test data schema validation with invalid timestamp."""
        df = pd.DataFrame({
            'timestamp': ['invalid-timestamp'],
            'region': ['SE'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power']
        })
        
        result = validate_data_schema(df, 'generation')
        assert result['valid'] is False
        assert any('Invalid timestamp format' in error for error in result['errors'])
    
    def test_convert_to_timestream_records_generation(self):
        """Test converting DataFrame to Timestream records for generation data."""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp('2024-01-01 00:00:00')],
            'region': ['SE'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power'],
            'quality_flag': ['good']
        })
        
        records = convert_to_timestream_records(df, 'generation')
        
        assert len(records) == 1
        record = records[0]
        
        assert record['MeasureName'] == 'value'
        assert record['MeasureValue'] == '100.5'
        assert record['MeasureValueType'] == 'DOUBLE'
        assert record['TimeUnit'] == 'MILLISECONDS'
        
        # Check dimensions
        dimensions = {dim['Name']: dim['Value'] for dim in record['Dimensions']}
        assert dimensions['region'] == 'SE'
        assert dimensions['dataset_type'] == 'generation'
        assert dimensions['energy_source'] == 'hydro'
        assert dimensions['measurement_type'] == 'power'
        assert dimensions['quality_flag'] == 'good'
    
    def test_convert_to_timestream_records_consumption(self):
        """Test converting DataFrame to Timestream records for consumption data."""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp('2024-01-01 00:00:00')],
            'region': ['SE'],
            'value': [50.2],
            'unit': ['MW'],
            'consumer_type': ['residential'],
            'measurement_type': ['consumption']
        })
        
        records = convert_to_timestream_records(df, 'consumption')
        
        assert len(records) == 1
        record = records[0]
        
        dimensions = {dim['Name']: dim['Value'] for dim in record['Dimensions']}
        assert dimensions['consumer_type'] == 'residential'
        assert dimensions['dataset_type'] == 'consumption'
    
    def test_get_table_name(self):
        """Test getting table name for dataset type."""
        assert get_table_name('generation') == 'generation_data'
        assert get_table_name('consumption') == 'consumption_data'
        assert get_table_name('transmission') == 'transmission_data'
        assert get_table_name('unknown') == 'generation_data'  # Default
    
    @patch('lambda_function.s3_client')
    @patch('lambda_function.timestream_client')
    @patch('lambda_function.cloudwatch_client')
    def test_lambda_handler_success(self, mock_cloudwatch, mock_timestream, mock_s3):
        """Test successful Lambda handler execution."""
        # Mock S3 response
        mock_parquet_data = pd.DataFrame({
            'timestamp': [pd.Timestamp('2024-01-01 00:00:00')],
            'region': ['SE'],
            'value': [100.5],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power']
        })
        
        mock_s3.get_object.return_value = {
            'Body': MagicMock()
        }
        
        # Mock pandas read_parquet
        with patch('pandas.read_parquet', return_value=mock_parquet_data):
            # Mock Timestream response
            mock_timestream.write_records.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            # Test event
            event = {
                'bucket': 'test-bucket',
                'key': 'dataset=generation/year=2024/file.parquet'
            }
            
            result = lambda_handler(event, {})
            
            assert result['statusCode'] == 200
            assert result['message'] == 'Data loaded successfully'
            assert result['data']['records_processed'] == 1
            assert result['data']['dataset_type'] == 'generation'
    
    @patch('lambda_function.s3_client')
    def test_lambda_handler_invalid_event(self, mock_s3):
        """Test Lambda handler with invalid event."""
        event = {'invalid': 'event'}
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 400
        assert 'Invalid event format' in result['message']
    
    @patch('lambda_function.s3_client')
    def test_lambda_handler_unknown_dataset_type(self, mock_s3):
        """Test Lambda handler with unknown dataset type."""
        event = {
            'bucket': 'test-bucket',
            'key': 'unknown/path/file.parquet'
        }
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 400
        assert 'Unable to determine dataset type' in result['message']


if __name__ == '__main__':
    pytest.main([__file__])