"""
Comprehensive unit tests for Timestream Loader Lambda function
Tests data loading, validation, error handling, and performance
"""

import pytest
import json
import pandas as pd
import boto3
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from moto import mock_s3, mock_timestream_write, mock_cloudwatch
from botocore.exceptions import ClientError
import sys
import os

# Add source path
sys.path.insert(0, 'src/timestream_loader')

from lambda_function import (
    lambda_handler,
    extract_s3_info,
    determine_dataset_type,
    load_parquet_from_s3,
    validate_data_schema,
    load_data_to_timestream,
    convert_to_timestream_records,
    get_table_name,
    send_metrics,
    send_error_metrics,
    create_response
)


class TestS3InfoExtraction:
    """Test S3 information extraction from various event sources"""
    
    def test_extract_s3_records_event(self):
        """Test extraction from S3 Records event"""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'dataset=generation/year=2024/month=01/data.parquet'}
                }
            }]
        }
        
        result = extract_s3_info(event)
        
        assert result is not None
        assert result['bucket'] == 'test-bucket'
        assert result['key'] == 'dataset=generation/year=2024/month=01/data.parquet'
    
    def test_extract_step_functions_event(self):
        """Test extraction from Step Functions event"""
        event = {
            'bucket': 'step-functions-bucket',
            'key': 'dataset=consumption/year=2024/month=02/processed.parquet'
        }
        
        result = extract_s3_info(event)
        
        assert result is not None
        assert result['bucket'] == 'step-functions-bucket'
        assert result['key'] == 'dataset=consumption/year=2024/month=02/processed.parquet'
    
    def test_extract_invalid_event(self):
        """Test extraction from invalid event format"""
        invalid_events = [
            {},
            {'Records': []},
            {'Records': [{}]},
            {'bucket': 'test-bucket'},  # Missing key
            {'key': 'test-key'}  # Missing bucket
        ]
        
        for event in invalid_events:
            result = extract_s3_info(event)
            assert result is None


class TestDatasetTypeDetection:
    """Test dataset type determination from S3 object keys"""
    
    def test_generation_dataset_detection(self):
        """Test generation dataset type detection"""
        generation_keys = [
            'dataset=generation/year=2024/month=01/data.parquet',
            'processed/dataset=generation/year=2024/data.parquet',
            's3://bucket/dataset=generation/file.parquet'
        ]
        
        for key in generation_keys:
            result = determine_dataset_type(key)
            assert result == 'generation'
    
    def test_consumption_dataset_detection(self):
        """Test consumption dataset type detection"""
        consumption_keys = [
            'dataset=consumption/year=2024/month=01/data.parquet',
            'processed/dataset=consumption/year=2024/data.parquet'
        ]
        
        for key in consumption_keys:
            result = determine_dataset_type(key)
            assert result == 'consumption'
    
    def test_transmission_dataset_detection(self):
        """Test transmission dataset type detection"""
        transmission_keys = [
            'dataset=transmission/year=2024/month=01/data.parquet',
            'processed/dataset=transmission/year=2024/data.parquet'
        ]
        
        for key in transmission_keys:
            result = determine_dataset_type(key)
            assert result == 'transmission'
    
    def test_unknown_dataset_type(self):
        """Test unknown dataset type returns None"""
        unknown_keys = [
            'some/random/path/file.parquet',
            'data/unknown/file.parquet',
            'dataset=unknown/file.parquet'
        ]
        
        for key in unknown_keys:
            result = determine_dataset_type(key)
            assert result is None


class TestParquetLoading:
    """Test Parquet file loading from S3"""
    
    @mock_s3
    def test_load_parquet_success(self):
        """Test successful Parquet loading"""
        # Create test data
        test_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='H'),
            'region': ['sudeste'] * 5,
            'energy_source': ['hidrica'] * 5,
            'measurement_type': ['power'] * 5,
            'value': [1000.0, 1100.0, 1200.0, 1150.0, 1050.0],
            'unit': ['MW'] * 5,
            'quality_flag': ['good'] * 5
        })
        
        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')
        
        # Upload test Parquet file
        parquet_buffer = test_data.to_parquet(index=False)
        s3_client.put_object(
            Bucket='test-bucket',
            Key='test.parquet',
            Body=parquet_buffer
        )
        
        # Test loading
        with patch('src.timestream_loader.lambda_function.s3_client', s3_client):
            result_df = load_parquet_from_s3('test-bucket', 'test.parquet')
            
            assert len(result_df) == 5
            assert list(result_df.columns) == list(test_data.columns)
            assert result_df['region'].iloc[0] == 'sudeste'
    
    def test_load_parquet_file_not_found(self):
        """Test Parquet loading with file not found"""
        with patch('src.timestream_loader.lambda_function.s3_client') as mock_s3:
            mock_s3.get_object.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
                'get_object'
            )
            
            with pytest.raises(Exception, match="Error loading Parquet file"):
                load_parquet_from_s3('test-bucket', 'nonexistent.parquet')


class TestDataValidation:
    """Test data schema validation for Timestream compatibility"""
    
    def test_validate_generation_data_valid(self):
        """Test validation of valid generation data"""
        valid_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'region': ['sudeste', 'nordeste', 'sul'],
            'energy_source': ['hidrica', 'eolica', 'solar'],
            'measurement_type': ['power', 'power', 'power'],
            'value': [1000.0, 800.0, 200.0],
            'unit': ['MW', 'MW', 'MW']
        })
        
        result = validate_data_schema(valid_df, 'generation')
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_consumption_data_valid(self):
        """Test validation of valid consumption data"""
        valid_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='D'),
            'region': ['sudeste', 'nordeste', 'sul'],
            'consumer_type': ['residential', 'commercial', 'industrial'],
            'measurement_type': ['consumption', 'consumption', 'consumption'],
            'value': [5000.0, 3000.0, 8000.0],
            'unit': ['MWh', 'MWh', 'MWh']
        })
        
        result = validate_data_schema(valid_df, 'consumption')
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_transmission_data_valid(self):
        """Test validation of valid transmission data"""
        valid_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'region': ['sudeste', 'nordeste', 'sul'],
            'line_id': ['LINE_001', 'LINE_002', 'LINE_003'],
            'measurement_type': ['flow', 'flow', 'flow'],
            'value': [500.0, 300.0, 700.0],
            'unit': ['MW', 'MW', 'MW']
        })
        
        result = validate_data_schema(valid_df, 'transmission')
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_missing_required_columns(self):
        """Test validation with missing required columns"""
        invalid_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'value': [1000.0, 800.0, 200.0]
            # Missing: region, energy_source, measurement_type, unit
        })
        
        result = validate_data_schema(invalid_df, 'generation')
        
        assert result['valid'] is False
        assert 'Missing required columns' in result['errors'][0]
        assert 'region' in result['errors'][0]
        assert 'energy_source' in result['errors'][0]
    
    def test_validate_invalid_timestamp(self):
        """Test validation with invalid timestamp format"""
        invalid_df = pd.DataFrame({
            'timestamp': ['invalid-date', 'another-invalid', 'not-a-date'],
            'region': ['sudeste', 'nordeste', 'sul'],
            'energy_source': ['hidrica', 'eolica', 'solar'],
            'measurement_type': ['power', 'power', 'power'],
            'value': [1000.0, 800.0, 200.0],
            'unit': ['MW', 'MW', 'MW']
        })
        
        result = validate_data_schema(invalid_df, 'generation')
        
        assert result['valid'] is False
        assert any('Invalid timestamp format' in error for error in result['errors'])
    
    def test_validate_non_numeric_values(self):
        """Test validation with non-numeric value column"""
        invalid_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'region': ['sudeste', 'nordeste', 'sul'],
            'energy_source': ['hidrica', 'eolica', 'solar'],
            'measurement_type': ['power', 'power', 'power'],
            'value': ['not-a-number', 'invalid', 'text'],
            'unit': ['MW', 'MW', 'MW']
        })
        
        result = validate_data_schema(invalid_df, 'generation')
        
        assert result['valid'] is False
        assert any('Value column must be numeric' in error for error in result['errors'])


class TestTimestreamRecordConversion:
    """Test conversion of DataFrame to Timestream record format"""
    
    def test_convert_generation_records(self):
        """Test conversion of generation data to Timestream records"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='H'),
            'region': ['sudeste', 'nordeste'],
            'energy_source': ['hidrica', 'eolica'],
            'measurement_type': ['power', 'power'],
            'value': [1000.0, 800.0],
            'unit': ['MW', 'MW'],
            'quality_flag': ['good', 'good']
        })
        
        records = convert_to_timestream_records(df, 'generation')
        
        assert len(records) == 2
        
        # Check first record
        record1 = records[0]
        assert record1['MeasureName'] == 'value'
        assert record1['MeasureValue'] == '1000.0'
        assert record1['MeasureValueType'] == 'DOUBLE'
        assert record1['TimeUnit'] == 'MILLISECONDS'
        
        # Check dimensions
        dimensions = {dim['Name']: dim['Value'] for dim in record1['Dimensions']}
        assert dimensions['region'] == 'sudeste'
        assert dimensions['dataset_type'] == 'generation'
        assert dimensions['energy_source'] == 'hidrica'
        assert dimensions['measurement_type'] == 'power'
        assert dimensions['quality_flag'] == 'good'
    
    def test_convert_consumption_records(self):
        """Test conversion of consumption data to Timestream records"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='D'),
            'region': ['sudeste', 'nordeste'],
            'consumer_type': ['residential', 'commercial'],
            'measurement_type': ['consumption', 'consumption'],
            'value': [5000.0, 3000.0],
            'unit': ['MWh', 'MWh']
        })
        
        records = convert_to_timestream_records(df, 'consumption')
        
        assert len(records) == 2
        
        # Check dimensions for consumption data
        dimensions = {dim['Name']: dim['Value'] for dim in records[0]['Dimensions']}
        assert dimensions['region'] == 'sudeste'
        assert dimensions['dataset_type'] == 'consumption'
        assert dimensions['consumer_type'] == 'residential'
        assert dimensions['measurement_type'] == 'consumption'
    
    def test_convert_transmission_records(self):
        """Test conversion of transmission data to Timestream records"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='H'),
            'region': ['sudeste', 'nordeste'],
            'line_id': ['LINE_001', 'LINE_002'],
            'measurement_type': ['flow', 'flow'],
            'value': [500.0, 300.0],
            'unit': ['MW', 'MW']
        })
        
        records = convert_to_timestream_records(df, 'transmission')
        
        assert len(records) == 2
        
        # Check dimensions for transmission data
        dimensions = {dim['Name']: dim['Value'] for dim in records[0]['Dimensions']}
        assert dimensions['region'] == 'sudeste'
        assert dimensions['dataset_type'] == 'transmission'
        assert dimensions['line_id'] == 'LINE_001'
        assert dimensions['measurement_type'] == 'flow'
    
    def test_convert_records_timestamp_format(self):
        """Test timestamp conversion to milliseconds"""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp('2024-01-01 10:00:00')],
            'region': ['sudeste'],
            'value': [1000.0]
        })
        
        records = convert_to_timestream_records(df, 'generation')
        
        # Check timestamp conversion
        expected_timestamp = int(pd.Timestamp('2024-01-01 10:00:00').timestamp() * 1000)
        assert records[0]['Time'] == str(expected_timestamp)
        assert records[0]['TimeUnit'] == 'MILLISECONDS'


class TestTimestreamDataLoading:
    """Test data loading to Timestream with batch processing and retries"""
    
    @mock_timestream_write
    def test_load_data_success(self):
        """Test successful data loading to Timestream"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='H'),
            'region': ['sudeste'] * 5,
            'energy_source': ['hidrica'] * 5,
            'measurement_type': ['power'] * 5,
            'value': [1000.0, 1100.0, 1200.0, 1150.0, 1050.0],
            'unit': ['MW'] * 5
        })
        
        with patch.dict(os.environ, {
            'TIMESTREAM_DATABASE_NAME': 'test_db',
            'GENERATION_TABLE_NAME': 'generation_data',
            'MAX_BATCH_SIZE': '100'
        }):
            result = load_data_to_timestream(df, 'generation')
            
            assert result['records_processed'] == 5
            assert result['batches_processed'] == 1
    
    @mock_timestream_write
    def test_load_data_large_dataset_batching(self):
        """Test data loading with large dataset requiring batching"""
        # Create large dataset
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=250, freq='H'),
            'region': ['sudeste'] * 250,
            'energy_source': ['hidrica'] * 250,
            'measurement_type': ['power'] * 250,
            'value': [1000.0 + i for i in range(250)],
            'unit': ['MW'] * 250
        })
        
        with patch.dict(os.environ, {
            'TIMESTREAM_DATABASE_NAME': 'test_db',
            'GENERATION_TABLE_NAME': 'generation_data',
            'MAX_BATCH_SIZE': '100'  # Force batching
        }):
            result = load_data_to_timestream(df, 'generation')
            
            assert result['records_processed'] == 250
            assert result['batches_processed'] == 3  # 100 + 100 + 50
    
    def test_load_data_throttling_retry(self):
        """Test retry logic for throttling exceptions"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='H'),
            'region': ['sudeste'] * 2,
            'energy_source': ['hidrica'] * 2,
            'measurement_type': ['power'] * 2,
            'value': [1000.0, 1100.0],
            'unit': ['MW'] * 2
        })
        
        with patch('src.timestream_loader.lambda_function.timestream_client') as mock_client:
            # First call fails with throttling, second succeeds
            mock_client.write_records.side_effect = [
                ClientError(
                    {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                    'write_records'
                ),
                {'ResponseMetadata': {'HTTPStatusCode': 200}}
            ]
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                with patch.dict(os.environ, {
                    'TIMESTREAM_DATABASE_NAME': 'test_db',
                    'GENERATION_TABLE_NAME': 'generation_data',
                    'MAX_RETRIES': '3'
                }):
                    result = load_data_to_timestream(df, 'generation')
                    
                    assert result['records_processed'] == 2
                    assert mock_client.write_records.call_count == 2
    
    def test_load_data_permanent_failure(self):
        """Test handling of permanent failures"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='H'),
            'region': ['sudeste'] * 2,
            'value': [1000.0, 1100.0]
        })
        
        with patch('src.timestream_loader.lambda_function.timestream_client') as mock_client:
            mock_client.write_records.side_effect = ClientError(
                {'Error': {'Code': 'ValidationException', 'Message': 'Invalid data'}},
                'write_records'
            )
            
            with patch.dict(os.environ, {
                'TIMESTREAM_DATABASE_NAME': 'test_db',
                'GENERATION_TABLE_NAME': 'generation_data'
            }):
                with pytest.raises(ClientError):
                    load_data_to_timestream(df, 'generation')


class TestTableNameMapping:
    """Test table name mapping for different dataset types"""
    
    def test_get_table_name_generation(self):
        """Test table name for generation dataset"""
        with patch.dict(os.environ, {'GENERATION_TABLE_NAME': 'gen_table'}):
            result = get_table_name('generation')
            assert result == 'gen_table'
    
    def test_get_table_name_consumption(self):
        """Test table name for consumption dataset"""
        with patch.dict(os.environ, {'CONSUMPTION_TABLE_NAME': 'cons_table'}):
            result = get_table_name('consumption')
            assert result == 'cons_table'
    
    def test_get_table_name_transmission(self):
        """Test table name for transmission dataset"""
        with patch.dict(os.environ, {'TRANSMISSION_TABLE_NAME': 'trans_table'}):
            result = get_table_name('transmission')
            assert result == 'trans_table'
    
    def test_get_table_name_unknown_fallback(self):
        """Test fallback to generation table for unknown dataset type"""
        with patch.dict(os.environ, {'GENERATION_TABLE_NAME': 'default_table'}):
            result = get_table_name('unknown_type')
            assert result == 'default_table'


class TestMetrics:
    """Test CloudWatch metrics functionality"""
    
    @mock_cloudwatch
    def test_send_metrics_success(self):
        """Test successful metrics sending"""
        load_result = {
            'records_processed': 100,
            'batches_processed': 2
        }
        
        with patch('src.timestream_loader.lambda_function.cloudwatch_client') as mock_cw:
            send_metrics('generation', load_result)
            
            mock_cw.put_metric_data.assert_called_once()
            call_args = mock_cw.put_metric_data.call_args[1]
            
            assert call_args['Namespace'] == 'ONS/Timestream'
            metrics = call_args['MetricData']
            
            # Check metrics
            metric_names = [metric['MetricName'] for metric in metrics]
            assert 'RecordsProcessed' in metric_names
            assert 'BatchesProcessed' in metric_names
            
            # Check dimensions
            records_metric = next(m for m in metrics if m['MetricName'] == 'RecordsProcessed')
            dimensions = {dim['Name']: dim['Value'] for dim in records_metric['Dimensions']}
            assert dimensions['DatasetType'] == 'generation'
    
    @mock_cloudwatch
    def test_send_error_metrics(self):
        """Test error metrics sending"""
        with patch('src.timestream_loader.lambda_function.cloudwatch_client') as mock_cw:
            send_error_metrics('Test error message')
            
            mock_cw.put_metric_data.assert_called_once()
            call_args = mock_cw.put_metric_data.call_args[1]
            
            assert call_args['Namespace'] == 'ONS/Timestream'
            metrics = call_args['MetricData']
            
            assert len(metrics) == 1
            assert metrics[0]['MetricName'] == 'ProcessingErrors'
            assert metrics[0]['Value'] == 1
    
    def test_send_metrics_failure_handling(self):
        """Test metrics sending failure handling"""
        with patch('src.timestream_loader.lambda_function.cloudwatch_client') as mock_cw:
            mock_cw.put_metric_data.side_effect = Exception("CloudWatch error")
            
            # Should not raise exception
            send_metrics('generation', {'records_processed': 100, 'batches_processed': 1})


class TestLambdaHandler:
    """Test main Lambda handler function"""
    
    def test_lambda_handler_s3_event_success(self):
        """Test successful processing of S3 event"""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'dataset=generation/year=2024/month=01/data.parquet'}
                }
            }]
        }
        
        test_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'region': ['sudeste'] * 3,
            'energy_source': ['hidrica'] * 3,
            'measurement_type': ['power'] * 3,
            'value': [1000.0, 1100.0, 1200.0],
            'unit': ['MW'] * 3
        })
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load, \
             patch('src.timestream_loader.lambda_function.load_data_to_timestream') as mock_timestream, \
             patch('src.timestream_loader.lambda_function.send_metrics') as mock_metrics:
            
            mock_load.return_value = test_df
            mock_timestream.return_value = {'records_processed': 3, 'batches_processed': 1}
            
            with patch.dict(os.environ, {
                'TIMESTREAM_DATABASE_NAME': 'test_db',
                'GENERATION_TABLE_NAME': 'generation_data'
            }):
                response = lambda_handler(event, None)
                
                assert response['statusCode'] == 200
                assert response['message'] == 'Data loaded successfully'
                assert response['data']['records_processed'] == 3
                assert response['data']['dataset_type'] == 'generation'
                
                mock_metrics.assert_called_once()
    
    def test_lambda_handler_step_functions_event(self):
        """Test processing of Step Functions event"""
        event = {
            'bucket': 'step-functions-bucket',
            'key': 'dataset=consumption/year=2024/month=02/data.parquet'
        }
        
        test_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=2, freq='D'),
            'region': ['sudeste', 'nordeste'],
            'consumer_type': ['residential', 'commercial'],
            'measurement_type': ['consumption', 'consumption'],
            'value': [5000.0, 3000.0],
            'unit': ['MWh', 'MWh']
        })
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load, \
             patch('src.timestream_loader.lambda_function.load_data_to_timestream') as mock_timestream:
            
            mock_load.return_value = test_df
            mock_timestream.return_value = {'records_processed': 2, 'batches_processed': 1}
            
            with patch.dict(os.environ, {
                'TIMESTREAM_DATABASE_NAME': 'test_db',
                'CONSUMPTION_TABLE_NAME': 'consumption_data'
            }):
                response = lambda_handler(event, None)
                
                assert response['statusCode'] == 200
                assert response['data']['dataset_type'] == 'consumption'
    
    def test_lambda_handler_invalid_event(self):
        """Test handling of invalid event format"""
        event = {}  # Invalid event
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        assert 'Invalid event format' in response['message']
    
    def test_lambda_handler_unknown_dataset_type(self):
        """Test handling of unknown dataset type"""
        event = {
            'bucket': 'test-bucket',
            'key': 'unknown/path/data.parquet'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        assert 'Unable to determine dataset type' in response['message']
    
    def test_lambda_handler_empty_data(self):
        """Test handling of empty data file"""
        event = {
            'bucket': 'test-bucket',
            'key': 'dataset=generation/year=2024/month=01/empty.parquet'
        }
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load:
            mock_load.return_value = pd.DataFrame()  # Empty DataFrame
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            assert response['message'] == 'No data to process'
    
    def test_lambda_handler_validation_failure(self):
        """Test handling of data validation failure"""
        event = {
            'bucket': 'test-bucket',
            'key': 'dataset=generation/year=2024/month=01/invalid.parquet'
        }
        
        invalid_df = pd.DataFrame({
            'timestamp': ['invalid-date'],
            'value': ['not-a-number']
        })
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load:
            mock_load.return_value = invalid_df
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 400
            assert 'Data validation failed' in response['message']
    
    def test_lambda_handler_processing_error(self):
        """Test handling of processing errors"""
        event = {
            'bucket': 'test-bucket',
            'key': 'dataset=generation/year=2024/month=01/data.parquet'
        }
        
        with patch('src.timestream_loader.lambda_function.load_parquet_from_s3') as mock_load:
            mock_load.side_effect = Exception("S3 loading failed")
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
            assert 'Internal error' in response['message']


class TestResponseCreation:
    """Test response creation utility function"""
    
    def test_create_response_success(self):
        """Test creating successful response"""
        response = create_response(200, "Success message", {'key': 'value'})
        
        assert response['statusCode'] == 200
        assert response['message'] == "Success message"
        assert response['data']['key'] == 'value'
    
    def test_create_response_error(self):
        """Test creating error response"""
        response = create_response(500, "Error message")
        
        assert response['statusCode'] == 500
        assert response['message'] == "Error message"
        assert 'data' not in response


class TestPerformanceAndStress:
    """Test performance and stress scenarios"""
    
    def test_large_dataset_processing(self):
        """Test processing of large datasets"""
        # Create large dataset (10,000 records)
        large_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10000, freq='H'),
            'region': (['sudeste', 'nordeste', 'sul', 'norte', 'centro_oeste'] * 2000),
            'energy_source': (['hidrica', 'eolica', 'solar', 'termica'] * 2500),
            'measurement_type': ['power'] * 10000,
            'value': [1000.0 + i * 0.1 for i in range(10000)],
            'unit': ['MW'] * 10000
        })
        
        # Test record conversion performance
        records = convert_to_timestream_records(large_df, 'generation')
        
        assert len(records) == 10000
        
        # Verify record structure
        sample_record = records[0]
        assert 'Time' in sample_record
        assert 'Dimensions' in sample_record
        assert 'MeasureName' in sample_record
        assert 'MeasureValue' in sample_record
    
    def test_batch_processing_efficiency(self):
        """Test batch processing with different batch sizes"""
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=500, freq='H'),
            'region': ['sudeste'] * 500,
            'energy_source': ['hidrica'] * 500,
            'measurement_type': ['power'] * 500,
            'value': [1000.0 + i for i in range(500)],
            'unit': ['MW'] * 500
        })
        
        # Test with different batch sizes
        batch_sizes = [50, 100, 200]
        
        for batch_size in batch_sizes:
            with patch('src.timestream_loader.lambda_function.timestream_client') as mock_client:
                mock_client.write_records.return_value = {'ResponseMetadata': {'HTTPStatusCode': 200}}
                
                with patch.dict(os.environ, {
                    'TIMESTREAM_DATABASE_NAME': 'test_db',
                    'GENERATION_TABLE_NAME': 'generation_data',
                    'MAX_BATCH_SIZE': str(batch_size)
                }):
                    result = load_data_to_timestream(df, 'generation')
                    
                    expected_batches = (500 + batch_size - 1) // batch_size  # Ceiling division
                    assert result['records_processed'] == 500
                    assert result['batches_processed'] == expected_batches
                    assert mock_client.write_records.call_count == expected_batches


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])