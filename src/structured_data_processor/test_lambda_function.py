"""
Unit tests for the Structured Data Processor Lambda function
Tests data cleaning, validation, standardization, and Parquet conversion
"""

import json
import os
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from moto import mock_s3
import boto3

# Import the module under test
from lambda_function import StructuredDataProcessor, lambda_handler, DataProcessingError


class TestStructuredDataProcessor:
    """Test class for StructuredDataProcessor"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.processor = StructuredDataProcessor()
        
        # Sample test data
        self.sample_csv_data = pd.DataFrame({
            'Data': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'Valor': [100.5, 200.3, 150.7],
            'Região': ['sudeste', 'nordeste', 'sul'],
            'Fonte': ['hidrica', 'eolica', 'termica']
        })
        
        self.sample_xlsx_data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'power_mw': [1500.0, 1800.0, 1650.0],
            'region': ['norte', 'centro_oeste', 'sudeste'],
            'energy_source': ['hidrica', 'solar', 'biomassa']
        })
        
        # Dirty data for cleaning tests
        self.dirty_data = pd.DataFrame({
            'Data/Hora': ['2024-01-01 10:00', '', '2024-01-03 15:30'],
            'Potência (MW)': [1000.0, None, 2000.0],
            'Região ': [' SUDESTE ', 'nordeste', ''],
            'Tipo de Fonte': ['Hidrica', 'EOLICA', 'termica'],
            'Observações': ['', 'Manutenção', ''],
            '': [None, None, None]  # Empty column
        })
    
    def test_get_file_extension(self):
        """Test file extension extraction"""
        assert self.processor._get_file_extension('test.csv') == '.csv'
        assert self.processor._get_file_extension('data.XLSX') == '.xlsx'
        assert self.processor._get_file_extension('file.XLS') == '.xls'
        assert self.processor._get_file_extension('path/to/file.CSV') == '.csv'
    
    def test_standardize_column_name(self):
        """Test column name standardization"""
        test_cases = [
            ('Data', 'timestamp'),
            ('Valor (MW)', 'value_mw'),
            ('Região', 'region'),
            ('Fonte de Energia', 'source_de_energia'),
            ('Potência Total', 'power_total'),
            ('  Espaços  ', 'espacos'),
            ('Carácteres-Especiais!@#', 'caracteres_especiais'),
            ('múltiplos___underscores', 'multiplos_underscores')
        ]
        
        for input_name, expected in test_cases:
            result = self.processor._standardize_column_name(input_name)
            assert result == expected, f"Expected {expected}, got {result} for input {input_name}"
    
    def test_clean_and_validate_data(self):
        """Test data cleaning and validation"""
        cleaned_df = self.processor._clean_and_validate_data(self.dirty_data, 'test.csv')
        
        # Check that empty columns are removed
        assert '' not in cleaned_df.columns
        
        # Check column name standardization
        expected_columns = ['timestamp_hora', 'power_mw', 'region', 'tipo_de_source', 'observacoes']
        for col in expected_columns:
            assert col in cleaned_df.columns
        
        # Check that completely empty rows are handled
        assert len(cleaned_df) > 0
        
        # Check data type conversions
        assert pd.api.types.is_datetime64_any_dtype(cleaned_df['timestamp_hora'])
        assert pd.api.types.is_numeric_dtype(cleaned_df['power_mw'])
    
    def test_handle_missing_values(self):
        """Test missing value handling"""
        df_with_nulls = pd.DataFrame({
            'value': [100.0, None, 200.0, None, 150.0],
            'region': ['norte', None, 'sul', 'nordeste', None],
            'source': ['hidrica', 'eolica', None, 'solar', 'termica']
        })
        
        filled_df = self.processor._handle_missing_values(df_with_nulls)
        
        # Check that numeric nulls are filled with median
        assert filled_df['value'].isna().sum() == 0
        median_value = df_with_nulls['value'].median()
        assert filled_df['value'].iloc[1] == median_value
        
        # Check that categorical nulls are filled appropriately
        assert filled_df['region'].isna().sum() == 0
        assert filled_df['source'].isna().sum() == 0
    
    def test_validate_and_convert_types(self):
        """Test data type validation and conversion"""
        test_df = pd.DataFrame({
            'timestamp': ['2024-01-01', '2024-01-02'],
            'value_mw': ['100.5', '200.3'],
            'region': ['SUDESTE', 'nordeste'],
            'power_total': ['1500', '1800']
        })
        
        converted_df = self.processor._validate_and_convert_types(test_df)
        
        # Check timestamp conversion
        assert pd.api.types.is_datetime64_any_dtype(converted_df['timestamp'])
        
        # Check numeric conversions
        assert pd.api.types.is_numeric_dtype(converted_df['value_mw'])
        assert pd.api.types.is_numeric_dtype(converted_df['power_total'])
        
        # Check string standardization
        assert converted_df['region'].iloc[0] == 'sudeste'
        assert converted_df['region'].iloc[1] == 'nordeste'
    
    def test_remove_outliers(self):
        """Test outlier removal"""
        # Create data with obvious outliers
        df_with_outliers = pd.DataFrame({
            'value': [100, 110, 105, 108, 1000, 95, 102, 107],  # 1000 is an outlier
            'region': ['norte'] * 8
        })
        
        cleaned_df = self.processor._remove_outliers(df_with_outliers)
        
        # Check that outlier is removed
        assert len(cleaned_df) < len(df_with_outliers)
        assert 1000 not in cleaned_df['value'].values
    
    def test_standardize_data(self):
        """Test data standardization"""
        standardized_df = self.processor._standardize_data(self.sample_csv_data, 'test.csv')
        
        # Check that metadata columns are added
        assert 'processing_metadata_processed_at' in standardized_df.columns
        assert 'processing_metadata_processor_version' in standardized_df.columns
        assert 'processing_metadata_source_file' in standardized_df.columns
        assert 'quality_flag' in standardized_df.columns
        
        # Check metadata values
        assert standardized_df['processing_metadata_processor_version'].iloc[0] == '1.0.0'
        assert standardized_df['processing_metadata_source_file'].iloc[0] == 'test.csv'
        assert standardized_df['quality_flag'].iloc[0] == 'valid'
    
    def test_determine_dataset_type(self):
        """Test dataset type determination"""
        test_cases = [
            ('dados_geracao_2024.csv', 'generation'),
            ('consumo_energia_jan.xlsx', 'consumption'),
            ('transmissao_rede.csv', 'transmission'),
            ('outros_dados.csv', 'general')
        ]
        
        for filename, expected_type in test_cases:
            result = self.processor._determine_dataset_type(filename, self.sample_csv_data)
            assert result['type'] == expected_type
            assert 'year' in result
            assert 'month' in result
    
    def test_calculate_quality_score(self):
        """Test data quality score calculation"""
        # Perfect data (no nulls)
        perfect_df = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': ['a', 'b', 'c']
        })
        score = self.processor._calculate_quality_score(perfect_df)
        assert score == 100.0
        
        # Data with 50% nulls
        half_null_df = pd.DataFrame({
            'col1': [1, None, 3],
            'col2': ['a', None, 'c']
        })
        score = self.processor._calculate_quality_score(half_null_df)
        assert score == 66.67  # 4 non-null out of 6 total cells
    
    @mock_s3
    def test_read_file_from_s3_csv(self):
        """Test reading CSV file from S3"""
        # Setup mock S3
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-bucket'
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Create test CSV content
        csv_content = "Data,Valor,Região\n2024-01-01,100.5,sudeste\n2024-01-02,200.3,nordeste"
        s3_client.put_object(Bucket=bucket_name, Key='test.csv', Body=csv_content)
        
        # Test reading
        with patch('awswrangler.s3.read_csv') as mock_read_csv:
            mock_read_csv.return_value = self.sample_csv_data
            df = self.processor._read_file_from_s3(bucket_name, 'test.csv', '.csv')
            assert len(df) == 3
            mock_read_csv.assert_called()
    
    @mock_s3
    def test_read_file_from_s3_xlsx(self):
        """Test reading XLSX file from S3"""
        with patch('awswrangler.s3.read_excel') as mock_read_excel:
            mock_read_excel.return_value = self.sample_xlsx_data
            df = self.processor._read_file_from_s3('bucket', 'test.xlsx', '.xlsx')
            assert len(df) == 3
            mock_read_excel.assert_called()
    
    def test_save_as_parquet(self):
        """Test saving DataFrame as Parquet"""
        dataset_info = {
            'type': 'generation',
            'year': '2024',
            'month': '01'
        }
        
        with patch('awswrangler.s3.to_parquet') as mock_to_parquet:
            mock_to_parquet.return_value = None
            
            output_path = self.processor._save_as_parquet(self.sample_csv_data, dataset_info)
            
            expected_path = "s3://ons-data-platform-processed/dataset=generation/year=2024/month=01/"
            assert output_path == expected_path
            mock_to_parquet.assert_called_once()
    
    def test_generate_metadata(self):
        """Test metadata generation"""
        metadata = self.processor._generate_metadata(
            'test.csv', 
            self.sample_csv_data, 
            's3://bucket/output/'
        )
        
        assert metadata['source_file'] == 'test.csv'
        assert metadata['output_location'] == 's3://bucket/output/'
        assert metadata['records_count'] == 3
        assert metadata['columns_count'] == 4
        assert 'processing_timestamp' in metadata
        assert 'data_quality_score' in metadata
        assert 'column_names' in metadata
    
    @patch('src.structured_data_processor.lambda_function.s3_client')
    def test_move_to_failed_bucket(self, mock_s3_client):
        """Test moving failed files to failed bucket"""
        mock_s3_client.copy_object.return_value = None
        
        self.processor._move_to_failed_bucket('source-bucket', 'test.csv', 'Test error')
        
        mock_s3_client.copy_object.assert_called_once()
        call_args = mock_s3_client.copy_object.call_args
        
        assert call_args[1]['CopySource']['Bucket'] == 'source-bucket'
        assert call_args[1]['CopySource']['Key'] == 'test.csv'
        assert call_args[1]['Bucket'] == 'ons-data-platform-failed'
        assert 'error_message' in call_args[1]['Metadata']
    
    def test_process_file_success(self):
        """Test successful file processing end-to-end"""
        with patch.object(self.processor, '_read_file_from_s3') as mock_read, \
             patch.object(self.processor, '_save_as_parquet') as mock_save, \
             patch.object(self.processor, '_move_to_failed_bucket') as mock_move_failed:
            
            mock_read.return_value = self.sample_csv_data
            mock_save.return_value = 's3://processed/output/'
            
            result = self.processor.process_file('test-bucket', 'test.csv')
            
            assert result['status'] == 'success'
            assert result['records_processed'] == 3
            assert result['output_location'] == 's3://processed/output/'
            assert 'metadata' in result
            mock_move_failed.assert_not_called()
    
    def test_process_file_failure(self):
        """Test file processing failure handling"""
        with patch.object(self.processor, '_read_file_from_s3') as mock_read, \
             patch.object(self.processor, '_move_to_failed_bucket') as mock_move_failed:
            
            mock_read.side_effect = Exception("Read error")
            
            with pytest.raises(DataProcessingError):
                self.processor.process_file('test-bucket', 'test.csv')
            
            mock_move_failed.assert_called_once()


class TestLambdaHandler:
    """Test class for Lambda handler function"""
    
    def test_lambda_handler_s3_event(self):
        """Test Lambda handler with S3 event"""
        event = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': 'test-bucket'},
                        'object': {'key': 'test.csv'}
                    }
                }
            ]
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.return_value = {
                'status': 'success',
                'records_processed': 100
            }
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['message'] == 'Processing completed successfully'
            assert len(body['results']) == 1
    
    def test_lambda_handler_direct_invocation(self):
        """Test Lambda handler with direct invocation"""
        event = {
            'bucket': 'test-bucket',
            'key': 'test.csv'
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.return_value = {
                'status': 'success',
                'records_processed': 50
            }
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['message'] == 'Processing completed successfully'
    
    def test_lambda_handler_missing_parameters(self):
        """Test Lambda handler with missing parameters"""
        event = {'bucket': 'test-bucket'}  # Missing 'key'
        
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_lambda_handler_processing_error(self):
        """Test Lambda handler with processing error"""
        event = {
            'bucket': 'test-bucket',
            'key': 'test.csv'
        }
        
        with patch('lambda_function.StructuredDataProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.process_file.side_effect = DataProcessingError("Processing failed")
            mock_processor_class.return_value = mock_processor
            
            response = lambda_handler(event, {})
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body
            assert body['message'] == 'Processing failed'


class TestDataValidationScenarios:
    """Test various data validation scenarios"""
    
    def setup_method(self):
        self.processor = StructuredDataProcessor()
    
    def test_malformed_csv_data(self):
        """Test handling of malformed CSV data"""
        malformed_df = pd.DataFrame({
            'timestamp': ['invalid-date', '2024-01-02', ''],
            'value': ['not-a-number', '100.5', '-999'],
            'region': ['', 'INVALID_REGION', 'norte']
        })
        
        cleaned_df = self.processor._clean_and_validate_data(malformed_df, 'malformed.csv')
        
        # Should handle invalid data gracefully
        assert len(cleaned_df) > 0
        assert 'timestamp' in cleaned_df.columns
        assert 'value' in cleaned_df.columns
    
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame"""
        empty_df = pd.DataFrame()
        
        with pytest.raises(DataProcessingError):
            self.processor._clean_and_validate_data(empty_df, 'empty.csv')
    
    def test_single_column_data(self):
        """Test handling of single column data"""
        single_col_df = pd.DataFrame({
            'value': [100, 200, 300]
        })
        
        cleaned_df = self.processor._clean_and_validate_data(single_col_df, 'single.csv')
        standardized_df = self.processor._standardize_data(cleaned_df, 'single.csv')
        
        # Should add required columns
        assert 'timestamp' in standardized_df.columns
        assert 'unit' in standardized_df.columns
    
    def test_large_dataset_performance(self):
        """Test performance with larger dataset"""
        # Create a larger dataset for performance testing
        large_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10000, freq='H'),
            'value': range(10000),
            'region': ['norte'] * 10000,
            'source': ['hidrica'] * 10000
        })
        
        # This should complete without timeout
        cleaned_df = self.processor._clean_and_validate_data(large_df, 'large.csv')
        assert len(cleaned_df) == 10000
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters"""
        unicode_df = pd.DataFrame({
            'região': ['São Paulo', 'Brasília', 'Ceará'],
            'fonte': ['Hidráulica', 'Eólica', 'Térmica'],
            'observações': ['Manutenção programada', 'Operação normal', 'Falha técnica']
        })
        
        cleaned_df = self.processor._clean_and_validate_data(unicode_df, 'unicode.csv')
        
        # Should handle Unicode characters properly
        assert len(cleaned_df) == 3
        # Column names should be standardized
        expected_cols = ['region', 'source', 'observacoes']
        for col in expected_cols:
            assert col in cleaned_df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])