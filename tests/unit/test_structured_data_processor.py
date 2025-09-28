"""
Comprehensive unit tests for Structured Data Processor Lambda function
Tests data cleaning, validation, transformation, and Parquet conversion
"""

import pytest
import pandas as pd
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from moto import mock_s3
import boto3
import sys

# Add source path
sys.path.insert(0, 'src/structured_data_processor')

from lambda_function import (
    StructuredDataProcessor,
    lambda_handler,
    DataProcessingError
)


class TestStructuredDataProcessor:
    """Test StructuredDataProcessor class functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.processor = StructuredDataProcessor()
        
        # Sample clean data
        self.clean_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='H'),
            'region': ['sudeste'] * 5 + ['nordeste'] * 5,
            'energy_source': ['hidrica', 'eolica'] * 5,
            'value': [1000.0 + i * 50 for i in range(10)],
            'unit': ['MW'] * 10
        })
        
        # Sample dirty data for cleaning tests
        self.dirty_data = pd.DataFrame({
            'Data/Hora': ['2024-01-01 10:00', '', '2024-01-03 15:30', None],
            'Potência (MW)': [1000.0, None, 2000.0, 'invalid'],
            'Região ': [' SUDESTE ', 'nordeste', '', 'CENTRO-OESTE'],
            'Fonte de Energia': ['Hidrica', 'EOLICA', 'termica', ''],
            'Observações': ['Normal', 'Manutenção', '', 'Teste'],
            '': [None, None, None, None],  # Empty column
            'Coluna_Vazia': [None, '', None, '']  # Another empty column
        })
        
        # Outlier data
        self.outlier_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=8, freq='H'),
            'value': [100, 110, 105, 10000, 95, 102, 107, 98],  # 10000 is outlier
            'region': ['norte'] * 8
        })
    
    def test_get_file_extension(self):
        """Test file extension extraction"""
        test_cases = [
            ('file.csv', '.csv'),
            ('DATA.XLSX', '.xlsx'),
            ('report.XLS', '.xls'),
            ('path/to/file.CSV', '.csv'),
            ('complex.name.with.dots.xlsx', '.xlsx'),
            ('no_extension', ''),
            ('', '')
        ]
        
        for filename, expected in test_cases:
            result = self.processor._get_file_extension(filename)
            assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"
    
    def test_standardize_column_name(self):
        """Test column name standardization"""
        test_cases = [
            # Portuguese to English mapping
            ('Data', 'timestamp'),
            ('Hora', 'time'),
            ('Valor', 'value'),
            ('Potência', 'power'),
            ('Energia', 'energy'),
            ('Região', 'region'),
            ('Fonte', 'source'),
            ('Tipo', 'type'),
            ('Unidade', 'unit'),
            
            # Special character handling
            ('Potência (MW)', 'power_mw'),
            ('Região/Estado', 'region_estado'),
            ('Fonte de Energia', 'source_de_energy'),
            ('  Espaços  ', 'espacos'),
            ('Múltiplos___Underscores', 'multiplos_underscores'),
            
            # Accent removal
            ('Geração', 'geracao'),
            ('Transmissão', 'transmissao'),
            ('Consumo Médio', 'consumo_medio'),
            
            # Edge cases
            ('', ''),
            ('123', '123'),
            ('_leading_underscore_', 'leading_underscore')
        ]
        
        for input_name, expected in test_cases:
            result = self.processor._standardize_column_name(input_name)
            assert result == expected, f"Failed for '{input_name}': expected '{expected}', got '{result}'"
    
    def test_clean_and_validate_data_basic(self):
        """Test basic data cleaning and validation"""
        cleaned_df = self.processor._clean_and_validate_data(self.dirty_data, 'test.csv')
        
        # Check that empty columns are removed
        assert '' not in cleaned_df.columns
        assert 'coluna_vazia' not in cleaned_df.columns
        
        # Check column name standardization
        expected_columns = ['timestamp_hora', 'power_mw', 'region', 'source_de_energy', 'observacoes']
        for col in expected_columns:
            assert col in cleaned_df.columns, f"Missing column: {col}"
        
        # Check that rows with all nulls are removed
        assert len(cleaned_df) > 0
        
        # Check data type conversions
        assert pd.api.types.is_datetime64_any_dtype(cleaned_df['timestamp_hora'])
        assert pd.api.types.is_numeric_dtype(cleaned_df['power_mw'])
    
    def test_clean_and_validate_data_empty_result(self):
        """Test cleaning data that results in empty DataFrame"""
        empty_data = pd.DataFrame({
            'col1': [None, None, None],
            'col2': ['', '', ''],
            'col3': [None, '', None]
        })
        
        with pytest.raises(DataProcessingError, match="No valid data remaining"):
            self.processor._clean_and_validate_data(empty_data, 'empty.csv')
    
    def test_handle_missing_values(self):
        """Test missing value handling strategies"""
        df_with_nulls = pd.DataFrame({
            'value': [100.0, None, 200.0, None, 150.0],
            'power': [500.0, None, 600.0, 700.0, None],
            'region': ['norte', None, 'sul', 'nordeste', None],
            'source': ['hidrica', 'eolica', None, 'solar', 'termica'],
            'type': ['A', 'B', None, 'A', None]
        })
        
        filled_df = self.processor._handle_missing_values(df_with_nulls)
        
        # Check that no nulls remain
        assert filled_df.isnull().sum().sum() == 0
        
        # Check numeric columns filled with median
        original_median = df_with_nulls['value'].median()
        assert filled_df['value'].iloc[1] == original_median
        assert filled_df['value'].iloc[3] == original_median
        
        # Check categorical columns filled appropriately
        assert filled_df['region'].iloc[1] == 'unknown'
        assert filled_df['region'].iloc[4] == 'unknown'
        
        # Check mode filling for type column
        mode_value = df_with_nulls['type'].mode()[0]  # Should be 'A'
        assert filled_df['type'].iloc[2] == mode_value
        assert filled_df['type'].iloc[4] == mode_value
    
    def test_validate_and_convert_types(self):
        """Test data type validation and conversion"""
        test_df = pd.DataFrame({
            'timestamp': ['2024-01-01', '2024-01-02', 'invalid-date'],
            'data_hora': ['2024-01-01 10:00', '2024-01-02 11:00', '2024-01-03 12:00'],
            'value_mw': ['100.5', '200.3', 'invalid'],
            'power_total': ['1500', '1800', '2000'],
            'energy_gwh': ['50.5', '60.2', '70.1'],
            'region': ['SUDESTE', 'nordeste', 'SUL'],
            'source': ['HIDRICA', 'eolica', 'SOLAR']
        })
        
        converted_df = self.processor._validate_and_convert_types(test_df)
        
        # Check timestamp conversions
        assert pd.api.types.is_datetime64_any_dtype(converted_df['timestamp'])
        assert pd.api.types.is_datetime64_any_dtype(converted_df['data_hora'])
        
        # Check numeric conversions
        assert pd.api.types.is_numeric_dtype(converted_df['value_mw'])
        assert pd.api.types.is_numeric_dtype(converted_df['power_total'])
        assert pd.api.types.is_numeric_dtype(converted_df['energy_gwh'])
        
        # Check string standardization
        assert converted_df['region'].iloc[0] == 'sudeste'
        assert converted_df['region'].iloc[1] == 'nordeste'
        assert converted_df['region'].iloc[2] == 'sul'
        
        assert converted_df['source'].iloc[0] == 'hidrica'
        assert converted_df['source'].iloc[1] == 'eolica'
        assert converted_df['source'].iloc[2] == 'solar'
    
    def test_remove_outliers(self):
        """Test outlier removal using IQR method"""
        cleaned_df = self.processor._remove_outliers(self.outlier_data)
        
        # Check that outlier is removed
        assert len(cleaned_df) < len(self.outlier_data)
        assert 10000 not in cleaned_df['value'].values
        
        # Check that normal values remain
        normal_values = [100, 110, 105, 95, 102, 107, 98]
        for val in normal_values:
            assert val in cleaned_df['value'].values
    
    def test_remove_outliers_no_outliers(self):
        """Test outlier removal when no outliers exist"""
        normal_data = pd.DataFrame({
            'value': [100, 105, 110, 95, 102, 108, 97, 103],
            'region': ['norte'] * 8
        })
        
        result_df = self.processor._remove_outliers(normal_data)
        
        # Should return all data when no outliers
        assert len(result_df) == len(normal_data)
    
    def test_standardize_data(self):
        """Test data standardization with metadata addition"""
        standardized_df = self.processor._standardize_data(self.clean_data, 'test.csv')
        
        # Check metadata columns added
        metadata_columns = [
            'processing_metadata_processed_at',
            'processing_metadata_processor_version',
            'processing_metadata_source_file',
            'quality_flag'
        ]
        
        for col in metadata_columns:
            assert col in standardized_df.columns, f"Missing metadata column: {col}"
        
        # Check metadata values
        assert standardized_df['processing_metadata_processor_version'].iloc[0] == '1.0.0'
        assert standardized_df['processing_metadata_source_file'].iloc[0] == 'test.csv'
        assert standardized_df['quality_flag'].iloc[0] == 'valid'
        
        # Check timestamp handling
        assert 'timestamp' in standardized_df.columns
        
        # Check unit column
        assert 'unit' in standardized_df.columns
    
    def test_standardize_data_missing_timestamp(self):
        """Test standardization when timestamp column is missing"""
        data_no_timestamp = pd.DataFrame({
            'value': [100, 200, 300],
            'region': ['norte', 'sul', 'nordeste']
        })
        
        standardized_df = self.processor._standardize_data(data_no_timestamp, 'no_timestamp.csv')
        
        # Should add timestamp column
        assert 'timestamp' in standardized_df.columns
        assert not standardized_df['timestamp'].isnull().any()
    
    def test_determine_dataset_type(self):
        """Test dataset type determination from filename"""
        test_cases = [
            # Generation patterns
            ('dados_geracao_2024.csv', 'generation'),
            ('generation_monthly.xlsx', 'generation'),
            ('producao_energia.pdf', 'generation'),
            ('gen_report.csv', 'generation'),
            
            # Consumption patterns
            ('consumo_energia_jan.xlsx', 'consumption'),
            ('consumption_data.csv', 'consumption'),
            ('demanda_regional.pdf', 'consumption'),
            ('cons_monthly.csv', 'consumption'),
            
            # Transmission patterns
            ('transmissao_rede.csv', 'transmission'),
            ('transmission_report.xlsx', 'transmission'),
            ('rede_eletrica.pdf', 'transmission'),
            ('trans_data.csv', 'transmission'),
            
            # General fallback
            ('outros_dados.csv', 'general'),
            ('unknown_file.xlsx', 'general'),
            ('misc_data.pdf', 'general')
        ]
        
        for filename, expected_type in test_cases:
            result = self.processor._determine_dataset_type(filename, self.clean_data)
            
            assert result['type'] == expected_type, f"Failed for {filename}: expected {expected_type}, got {result['type']}"
            assert 'year' in result
            assert 'month' in result
            assert len(result['year']) == 4  # YYYY format
            assert len(result['month']) == 2  # MM format
    
    def test_calculate_quality_score(self):
        """Test data quality score calculation"""
        # Perfect data (no nulls)
        perfect_df = pd.DataFrame({
            'col1': [1, 2, 3, 4],
            'col2': ['a', 'b', 'c', 'd'],
            'col3': [1.1, 2.2, 3.3, 4.4]
        })
        score = self.processor._calculate_quality_score(perfect_df)
        assert score == 100.0
        
        # Data with 50% nulls
        half_null_df = pd.DataFrame({
            'col1': [1, None, 3, None],
            'col2': ['a', None, 'c', None]
        })
        score = self.processor._calculate_quality_score(half_null_df)
        assert score == 50.0
        
        # Empty DataFrame
        empty_df = pd.DataFrame()
        score = self.processor._calculate_quality_score(empty_df)
        assert score == 0.0
    
    @patch('awswrangler.s3.read_csv')
    def test_read_file_from_s3_csv_success(self, mock_read_csv):
        """Test successful CSV reading from S3"""
        mock_read_csv.return_value = self.clean_data
        
        result_df = self.processor._read_file_from_s3('test-bucket', 'test.csv', '.csv')
        
        assert len(result_df) == 10
        assert list(result_df.columns) == list(self.clean_data.columns)
        mock_read_csv.assert_called()
    
    @patch('awswrangler.s3.read_csv')
    def test_read_file_from_s3_csv_encoding_fallback(self, mock_read_csv):
        """Test CSV reading with encoding fallback"""
        # Simulate encoding failures then success
        mock_read_csv.side_effect = [
            UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte'),
            UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte'),
            self.clean_data  # Success on third try
        ]
        
        result_df = self.processor._read_file_from_s3('test-bucket', 'test.csv', '.csv')
        
        assert len(result_df) == 10
        assert mock_read_csv.call_count == 3
    
    @patch('awswrangler.s3.read_csv')
    def test_read_file_from_s3_csv_failure(self, mock_read_csv):
        """Test CSV reading failure"""
        mock_read_csv.side_effect = Exception("All encoding attempts failed")
        
        with pytest.raises(DataProcessingError, match="Could not read CSV"):
            self.processor._read_file_from_s3('test-bucket', 'test.csv', '.csv')
    
    @patch('awswrangler.s3.read_excel')
    def test_read_file_from_s3_excel(self, mock_read_excel):
        """Test Excel file reading from S3"""
        mock_read_excel.return_value = self.clean_data
        
        # Test XLSX
        result_df = self.processor._read_file_from_s3('test-bucket', 'test.xlsx', '.xlsx')
        assert len(result_df) == 10
        mock_read_excel.assert_called_with(path='s3://test-bucket/test.xlsx', engine='openpyxl')
        
        # Test XLS
        result_df = self.processor._read_file_from_s3('test-bucket', 'test.xls', '.xls')
        assert len(result_df) == 10
    
    @patch('awswrangler.s3.to_parquet')
    def test_save_as_parquet(self, mock_to_parquet):
        """Test saving DataFrame as Parquet"""
        dataset_info = {
            'type': 'generation',
            'year': '2024',
            'month': '01'
        }
        
        with patch.dict(os.environ, {'PROCESSED_BUCKET': 'test-processed-bucket'}):
            output_path = self.processor._save_as_parquet(self.clean_data, dataset_info)
            
            expected_path = "s3://test-processed-bucket/dataset=generation/year=2024/month=01/"
            assert output_path == expected_path
            
            mock_to_parquet.assert_called_once()
            call_args = mock_to_parquet.call_args
            
            # Check DataFrame passed
            df_arg = call_args[1]['df']
            assert len(df_arg) == 10
            
            # Check other parameters
            assert call_args[1]['path'] == expected_path
            assert call_args[1]['dataset'] is True
            assert call_args[1]['compression'] == 'snappy'
    
    def test_generate_metadata(self):
        """Test metadata generation"""
        metadata = self.processor._generate_metadata(
            'test.csv',
            self.clean_data,
            's3://bucket/output/'
        )
        
        expected_keys = [
            'source_file', 'output_location', 'records_count',
            'columns_count', 'processing_timestamp',
            'data_quality_score', 'column_names'
        ]
        
        for key in expected_keys:
            assert key in metadata, f"Missing metadata key: {key}"
        
        assert metadata['source_file'] == 'test.csv'
        assert metadata['output_location'] == 's3://bucket/output/'
        assert metadata['records_count'] == 10
        assert metadata['columns_count'] == 5
        assert metadata['data_quality_score'] == 100.0  # Clean data
        assert len(metadata['column_names']) == 5
    
    @patch('src.structured_data_processor.lambda_function.s3_client')
    def test_move_to_failed_bucket(self, mock_s3_client):
        """Test moving failed files to failed bucket"""
        with patch.dict(os.environ, {'FAILED_BUCKET': 'test-failed-bucket'}):
            self.processor._move_to_failed_bucket('source-bucket', 'test.csv', 'Test error message')
            
            mock_s3_client.copy_object.assert_called_once()
            call_args = mock_s3_client.copy_object.call_args[1]
            
            assert call_args['CopySource']['Bucket'] == 'source-bucket'
            assert call_args['CopySource']['Key'] == 'test.csv'
            assert call_args['Bucket'] == 'test-failed-bucket'
            assert 'failed/' in call_args['Key']
            assert call_args['Metadata']['error_message'] == 'Test error message'
            assert 'failed_at' in call_args['Metadata']
    
    def test_process_file_success_integration(self):
        """Test complete file processing integration"""
        with patch.object(self.processor, '_read_file_from_s3') as mock_read, \
             patch.object(self.processor, '_save_as_parquet') as mock_save, \
             patch.object(self.processor, '_move_to_failed_bucket') as mock_move_failed:
            
            mock_read.return_value = self.clean_data
            mock_save.return_value = 's3://processed/output/'
            
            result = self.processor.process_file('test-bucket', 'generation_data.csv')
            
            assert result['status'] == 'success'
            assert result['records_processed'] == 10
            assert result['dataset_type'] == 'generation'
            assert result['output_location'] == 's3://processed/output/'
            assert 'metadata' in result
            
            mock_move_failed.assert_not_called()
    
    def test_process_file_failure_handling(self):
        """Test file processing failure handling"""
        with patch.object(self.processor, '_read_file_from_s3') as mock_read, \
             patch.object(self.processor, '_move_to_failed_bucket') as mock_move_failed:
            
            mock_read.side_effect = Exception("S3 read error")
            
            with pytest.raises(DataProcessingError, match="Failed to process"):
                self.processor.process_file('test-bucket', 'test.csv')
            
            mock_move_failed.assert_called_once_with('test-bucket', 'test.csv', 'S3 read error')
    
    def test_process_file_unsupported_format(self):
        """Test processing unsupported file format"""
        with patch.object(self.processor, '_move_to_failed_bucket') as mock_move_failed:
            
            with pytest.raises(DataProcessingError, match="Unsupported file format"):
                self.processor.process_file('test-bucket', 'test.txt')
            
            mock_move_failed.assert_called_once()


class TestLambdaHandler:
    """Test Lambda handler function"""
    
    def test_lambda_handler_s3_event(self):
        """Test Lambda handler with S3 event"""
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'data/test.csv'}
                    }
                }
            ]
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.return_value = {
                'status': 'success',
                'records_processed': 100,
                'dataset_type': 'generation'
            }
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['message'] == 'Processing completed successfully'
            assert len(body['results']) == 1
            assert body['results'][0]['records_processed'] == 100
    
    def test_lambda_handler_multiple_records(self):
        """Test Lambda handler with multiple S3 records"""
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'data/file1.csv'}
                    }
                },
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'data/file2.xlsx'}
                    }
                }
            ]
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.side_effect = [
                {'status': 'success', 'records_processed': 50},
                {'status': 'success', 'records_processed': 75}
            ]
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert len(body['results']) == 2
            assert mock_processor.process_file.call_count == 2
    
    def test_lambda_handler_direct_invocation(self):
        """Test Lambda handler with direct invocation"""
        event = {
            'bucket': 'direct-bucket',
            'key': 'data/direct.csv'
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.return_value = {
                'status': 'success',
                'records_processed': 25
            }
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert len(body['results']) == 1
    
    def test_lambda_handler_missing_parameters(self):
        """Test Lambda handler with missing required parameters"""
        event = {'bucket': 'test-bucket'}  # Missing 'key'
        
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['message'] == 'Processing failed'
    
    def test_lambda_handler_processing_error(self):
        """Test Lambda handler with processing error"""
        event = {
            'bucket': 'test-bucket',
            'key': 'data/error.csv'
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.side_effect = DataProcessingError("Processing failed")
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Processing failed' in body['error']


class TestDataValidationScenarios:
    """Test various data validation and edge case scenarios"""
    
    def setup_method(self):
        self.processor = StructuredDataProcessor()
    
    def test_malformed_csv_data_handling(self):
        """Test handling of malformed CSV data"""
        malformed_df = pd.DataFrame({
            'timestamp': ['invalid-date', '2024-01-02', '', None],
            'value': ['not-a-number', '100.5', '-999', 'inf'],
            'region': ['', 'INVALID_REGION', 'norte', None],
            'source': ['hidrica', '', None, 'UNKNOWN_SOURCE']
        })
        
        cleaned_df = self.processor._clean_and_validate_data(malformed_df, 'malformed.csv')
        
        # Should handle invalid data gracefully
        assert len(cleaned_df) > 0
        assert 'timestamp' in cleaned_df.columns
        assert 'value' in cleaned_df.columns
        
        # Check that invalid values are handled
        assert not cleaned_df['value'].isnull().all()
    
    def test_single_row_data(self):
        """Test handling of single row data"""
        single_row_df = pd.DataFrame({
            'timestamp': ['2024-01-01'],
            'value': [1000.0],
            'region': ['sudeste'],
            'source': ['hidrica']
        })
        
        cleaned_df = self.processor._clean_and_validate_data(single_row_df, 'single.csv')
        standardized_df = self.processor._standardize_data(cleaned_df, 'single.csv')
        
        assert len(standardized_df) == 1
        assert 'processing_metadata_processed_at' in standardized_df.columns
    
    def test_large_dataset_performance(self):
        """Test performance with larger dataset"""
        # Create larger dataset
        large_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5000, freq='H'),
            'value': [1000.0 + i * 0.1 for i in range(5000)],
            'region': (['norte', 'nordeste', 'sudeste', 'sul', 'centro-oeste'] * 1000),
            'source': (['hidrica', 'eolica', 'solar', 'termica'] * 1250)
        })
        
        # Should complete without timeout
        cleaned_df = self.processor._clean_and_validate_data(large_df, 'large.csv')
        assert len(cleaned_df) == 5000
        
        # Test standardization
        standardized_df = self.processor._standardize_data(cleaned_df, 'large.csv')
        assert len(standardized_df) == 5000
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters"""
        unicode_df = pd.DataFrame({
            'região': ['São Paulo', 'Brasília', 'Ceará', 'Paraná'],
            'fonte': ['Hidráulica', 'Eólica', 'Térmica', 'Biomassa'],
            'observações': ['Operação normal', 'Manutenção programada', 'Falha técnica', 'Teste de sistema'],
            'valor': [1500.5, 1200.3, 800.7, 950.2]
        })
        
        cleaned_df = self.processor._clean_and_validate_data(unicode_df, 'unicode.csv')
        
        # Should handle Unicode characters properly
        assert len(cleaned_df) == 4
        
        # Column names should be standardized (accents removed)
        expected_cols = ['region', 'source', 'observacoes', 'value']
        for col in expected_cols:
            assert col in cleaned_df.columns
    
    def test_mixed_data_types_in_columns(self):
        """Test handling of mixed data types in columns"""
        mixed_df = pd.DataFrame({
            'timestamp': ['2024-01-01', 1704067200, '01/01/2024', None],
            'value': [100, '200.5', 'invalid', None],
            'region': ['Norte', 123, None, 'Sul'],
            'flag': [True, 'yes', 0, 1]
        })
        
        cleaned_df = self.processor._clean_and_validate_data(mixed_df, 'mixed.csv')
        
        # Should handle mixed types gracefully
        assert len(cleaned_df) > 0
        
        # Check type conversions
        converted_df = self.processor._validate_and_convert_types(cleaned_df)
        assert pd.api.types.is_datetime64_any_dtype(converted_df['timestamp'])
        assert pd.api.types.is_numeric_dtype(converted_df['value'])
    
    def test_extreme_outliers(self):
        """Test handling of extreme outliers"""
        extreme_df = pd.DataFrame({
            'value': [100, 110, 105, 1e10, -1e10, 95, 102, 107],  # Extreme outliers
            'power': [500, 550, 525, 1e15, 475, 510, 520, 530],
            'region': ['norte'] * 8
        })
        
        cleaned_df = self.processor._remove_outliers(extreme_df)
        
        # Extreme outliers should be removed
        assert 1e10 not in cleaned_df['value'].values
        assert -1e10 not in cleaned_df['value'].values
        assert 1e15 not in cleaned_df['power'].values
        
        # Normal values should remain
        normal_values = [100, 110, 105, 95, 102, 107]
        for val in normal_values:
            assert val in cleaned_df['value'].values
    
    def test_duplicate_rows_handling(self):
        """Test duplicate row removal"""
        duplicate_df = pd.DataFrame({
            'timestamp': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-01'],
            'value': [100, 100, 200, 100],  # First and last rows are identical
            'region': ['norte', 'norte', 'sul', 'norte']
        })
        
        cleaned_df = self.processor._clean_and_validate_data(duplicate_df, 'duplicates.csv')
        
        # Should remove duplicate rows
        assert len(cleaned_df) < len(duplicate_df)
        
        # Should keep unique combinations
        unique_combinations = cleaned_df[['timestamp', 'value', 'region']].drop_duplicates()
        assert len(unique_combinations) == len(cleaned_df)
    
    def test_column_with_all_same_values(self):
        """Test handling of columns with all identical values"""
        same_values_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='H'),
            'constant_value': [100] * 5,  # All same values
            'constant_text': ['same'] * 5,  # All same text
            'varying_value': [100, 101, 102, 103, 104]
        })
        
        cleaned_df = self.processor._clean_and_validate_data(same_values_df, 'constant.csv')
        
        # Should handle constant columns without issues
        assert len(cleaned_df) == 5
        assert 'constant_value' in cleaned_df.columns
        assert 'constant_text' in cleaned_df.columns
        
        # Outlier removal should not affect constant columns
        no_outliers_df = self.processor._remove_outliers(cleaned_df)
        assert len(no_outliers_df) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])