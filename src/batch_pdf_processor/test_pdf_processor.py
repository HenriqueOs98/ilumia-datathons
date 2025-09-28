#!/usr/bin/env python3
"""
Integration tests for PDF Processor
Tests with sample PDF files and various error scenarios
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import pandas as pd
import boto3
from moto import mock_s3
import pytest

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_processor import PDFProcessor


class TestPDFProcessor(unittest.TestCase):
    """Test cases for PDF processor functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.processor = PDFProcessor()
        
        # Create test data
        self.sample_table_data = pd.DataFrame({
            'data': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'geracao_hidrica_mw': [1000.5, 1100.2, 950.8],
            'geracao_termica_mw': [500.0, 450.5, 600.3],
            'consumo_total_mw': [1500.5, 1550.7, 1551.1]
        })
        
    @mock_s3
    def test_process_pdf_file_success(self):
        """Test successful PDF processing end-to-end"""
        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-input-bucket')
        s3_client.create_bucket(Bucket='test-output-bucket')
        
        # Mock PDF content
        pdf_content = b'%PDF-1.4 mock pdf content'
        s3_client.put_object(
            Bucket='test-input-bucket',
            Key='test-file.pdf',
            Body=pdf_content
        )
        
        # Mock table extraction methods
        with patch.object(self.processor, '_extract_tables_multi_method') as mock_extract:
            mock_extract.return_value = [self.sample_table_data]
            
            result = self.processor.process_pdf_file(
                's3://test-input-bucket/test-file.pdf',
                's3://test-output-bucket/processed/test-file.parquet'
            )
            
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['tables_extracted'], 1)
            self.assertGreater(result['rows_processed'], 0)
    
    def test_parse_s3_uri_valid(self):
        """Test S3 URI parsing with valid URIs"""
        bucket, key = self.processor._parse_s3_uri('s3://my-bucket/path/to/file.pdf')
        self.assertEqual(bucket, 'my-bucket')
        self.assertEqual(key, 'path/to/file.pdf')
    
    def test_parse_s3_uri_invalid(self):
        """Test S3 URI parsing with invalid URIs"""
        with self.assertRaises(ValueError):
            self.processor._parse_s3_uri('invalid-uri')
        
        with self.assertRaises(ValueError):
            self.processor._parse_s3_uri('s3://bucket-only')
    
    def test_standardize_data_success(self):
        """Test data standardization with valid table data"""
        tables = [self.sample_table_data]
        result = self.processor._standardize_data(tables, 'test_geracao.pdf')
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)
        
        # Check required columns exist
        required_columns = [
            'timestamp', 'dataset_type', 'region', 'energy_source',
            'measurement_type', 'value', 'unit', 'quality_flag'
        ]
        for col in required_columns:
            self.assertIn(col, result.columns)
    
    def test_standardize_data_empty_tables(self):
        """Test standardization with empty tables"""
        empty_tables = [pd.DataFrame()]
        
        with self.assertRaises(ValueError):
            self.processor._standardize_data(empty_tables, 'test.pdf')
    
    def test_identify_timestamp_column(self):
        """Test timestamp column identification"""
        df_with_date = pd.DataFrame({
            'data': ['2024-01-01'],
            'valor': [100]
        })
        
        timestamp_col = self.processor._identify_timestamp_column(df_with_date)
        self.assertEqual(timestamp_col, 'data')
        
        df_without_date = pd.DataFrame({
            'valor1': [100],
            'valor2': [200]
        })
        
        timestamp_col = self.processor._identify_timestamp_column(df_without_date)
        self.assertIsNone(timestamp_col)
    
    def test_convert_to_numeric_various_formats(self):
        """Test numeric conversion with various Brazilian formats"""
        test_cases = [
            ('1.234,56', 1234.56),
            ('1,234.56', 1234.56),
            ('100%', 100.0),
            ('R$ 1.000,00', 1000.0),
            ('invalid', None),
            (None, None),
            (123.45, 123.45)
        ]
        
        for input_val, expected in test_cases:
            result = self.processor._convert_to_numeric(input_val)
            if expected is None:
                self.assertIsNone(result)
            else:
                self.assertAlmostEqual(result, expected, places=2)
    
    def test_infer_dataset_type(self):
        """Test dataset type inference"""
        test_cases = [
            ('geracao_hidrica_2024.pdf', 'potencia_mw', 'generation'),
            ('consumo_brasil.pdf', 'demanda', 'consumption'),
            ('transmissao_se.pdf', 'fluxo', 'transmission'),
            ('other_file.pdf', 'valor', 'other')
        ]
        
        for filename, column, expected in test_cases:
            result = self.processor._infer_dataset_type(filename, column)
            self.assertEqual(result, expected)
    
    def test_extract_region(self):
        """Test region extraction from filename and data"""
        test_cases = [
            ('dados_sudeste_2024.pdf', 'sudeste'),
            ('consumo_sp.pdf', 'sp'),
            ('nacional_brasil.pdf', 'brasil'),
            ('unknown_file.pdf', 'brasil')  # default
        ]
        
        empty_row = pd.Series([])
        
        for filename, expected in test_cases:
            result = self.processor._extract_region(filename, empty_row)
            self.assertEqual(result, expected)
    
    def test_extract_energy_source(self):
        """Test energy source extraction"""
        test_cases = [
            ('geracao_hidrica_mw', 'hidrica'),
            ('eolica_total', 'eolica'),
            ('solar_fotovoltaica', 'solar'),
            ('termica_gas', 'termica'),
            ('nuclear_angra', 'nuclear'),
            ('total_geral', 'total')
        ]
        
        empty_row = pd.Series([])
        
        for column, expected in test_cases:
            result = self.processor._extract_energy_source(column, empty_row)
            self.assertEqual(result, expected)
    
    def test_infer_unit(self):
        """Test unit inference"""
        test_cases = [
            ('potencia_mw', '1000', 'MW'),
            ('energia_gwh', '500', 'GWh'),
            ('percentual', '50%', '%'),
            ('valor_generico', '100', 'MW')  # default
        ]
        
        for column, value, expected in test_cases:
            result = self.processor._infer_unit(column, value)
            self.assertEqual(result, expected)
    
    def test_is_header_row(self):
        """Test header row detection"""
        header_row = pd.Series(['Total Geral', '1000', '2000'])
        data_row = pd.Series(['2024-01-01', '100', '200'])
        
        self.assertTrue(self.processor._is_header_row(header_row))
        self.assertFalse(self.processor._is_header_row(data_row))
    
    @patch('camelot.read_pdf')
    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_extract_tables_multi_method_success(self, mock_pdfplumber, mock_tabula, mock_camelot):
        """Test table extraction using multiple methods"""
        # Mock Camelot
        mock_camelot_table = MagicMock()
        mock_camelot_table.accuracy = 80
        mock_camelot_table.df = self.sample_table_data.copy()
        mock_camelot.return_value = [mock_camelot_table]
        
        # Mock Tabula
        mock_tabula.return_value = [self.sample_table_data.copy()]
        
        # Mock pdfplumber
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [['data', 'valor1', 'valor2'], ['2024-01-01', '100', '200']]
        ]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf
        
        test_path = Path('/tmp/test.pdf')
        tables = self.processor._extract_tables_multi_method(test_path)
        
        self.assertGreater(len(tables), 0)
        for table in tables:
            self.assertIsInstance(table, pd.DataFrame)
            self.assertIn('extraction_method', table.attrs)
    
    @patch('camelot.read_pdf')
    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_extract_tables_all_methods_fail(self, mock_pdfplumber, mock_tabula, mock_camelot):
        """Test behavior when all extraction methods fail"""
        # Make all methods raise exceptions
        mock_camelot.side_effect = Exception("Camelot failed")
        mock_tabula.side_effect = Exception("Tabula failed")
        mock_pdfplumber.side_effect = Exception("pdfplumber failed")
        
        test_path = Path('/tmp/test.pdf')
        tables = self.processor._extract_tables_multi_method(test_path)
        
        self.assertEqual(len(tables), 0)
    
    @mock_s3
    def test_download_pdf_success(self):
        """Test successful PDF download from S3"""
        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')
        
        pdf_content = b'%PDF-1.4 test content'
        s3_client.put_object(
            Bucket='test-bucket',
            Key='test.pdf',
            Body=pdf_content
        )
        
        local_path = self.processor._download_pdf('test-bucket', 'test.pdf')
        
        self.assertTrue(local_path.exists())
        with open(local_path, 'rb') as f:
            self.assertEqual(f.read(), pdf_content)
    
    @mock_s3
    def test_download_pdf_not_found(self):
        """Test PDF download when file doesn't exist"""
        # Setup S3 mock without the file
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')
        
        with self.assertRaises(Exception):
            self.processor._download_pdf('test-bucket', 'nonexistent.pdf')
    
    def test_save_as_parquet(self):
        """Test saving DataFrame as Parquet file"""
        test_df = pd.DataFrame({
            'timestamp': ['2024-01-01T00:00:00', '2024-01-02T00:00:00'],
            'value': [100.5, 200.3],
            'dataset_type': ['generation', 'generation']
        })
        
        parquet_path = self.processor._save_as_parquet(test_df)
        
        self.assertTrue(parquet_path.exists())
        
        # Verify file can be read back
        loaded_df = pd.read_parquet(parquet_path)
        self.assertEqual(len(loaded_df), len(test_df))
    
    @mock_s3
    def test_upload_to_s3_success(self):
        """Test successful file upload to S3"""
        # Setup S3 mock
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b'test content')
            tmp_path = Path(tmp_file.name)
        
        try:
            self.processor._upload_to_s3(tmp_path, 'test-bucket', 'test-key')
            
            # Verify file was uploaded
            response = s3_client.get_object(Bucket='test-bucket', Key='test-key')
            self.assertEqual(response['Body'].read(), b'test content')
        finally:
            tmp_path.unlink()
    
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        # Create temporary files
        temp_files = []
        for i in range(3):
            tmp_file = tempfile.NamedTemporaryFile(delete=False)
            tmp_file.close()
            temp_files.append(Path(tmp_file.name))
        
        # Verify files exist
        for path in temp_files:
            self.assertTrue(path.exists())
        
        # Cleanup
        self.processor._cleanup_temp_files(temp_files)
        
        # Verify files are deleted
        for path in temp_files:
            self.assertFalse(path.exists())


class TestPDFProcessorIntegration(unittest.TestCase):
    """Integration tests with sample PDF scenarios"""
    
    def setUp(self):
        self.processor = PDFProcessor()
    
    @patch.dict(os.environ, {
        'INPUT_S3_URI': 's3://test-bucket/input.pdf',
        'OUTPUT_S3_URI': 's3://test-bucket/output.parquet'
    })
    @patch('sys.exit')
    @patch('builtins.print')
    def test_main_function_success(self, mock_print, mock_exit):
        """Test main function with successful processing"""
        with patch.object(PDFProcessor, 'process_pdf_file') as mock_process:
            mock_process.return_value = {
                'status': 'success',
                'tables_extracted': 2,
                'rows_processed': 100
            }
            
            from pdf_processor import main
            main()
            
            mock_exit.assert_called_with(0)
    
    @patch.dict(os.environ, {
        'INPUT_S3_URI': 's3://test-bucket/input.pdf',
        'OUTPUT_S3_URI': 's3://test-bucket/output.parquet'
    })
    @patch('sys.exit')
    @patch('builtins.print')
    def test_main_function_failure(self, mock_print, mock_exit):
        """Test main function with processing failure"""
        with patch.object(PDFProcessor, 'process_pdf_file') as mock_process:
            mock_process.return_value = {
                'status': 'error',
                'error_message': 'Processing failed'
            }
            
            from pdf_processor import main
            main()
            
            mock_exit.assert_called_with(1)
    
    @patch.dict(os.environ, {})
    @patch('sys.exit')
    @patch('builtins.print')
    def test_main_function_missing_env_vars(self, mock_print, mock_exit):
        """Test main function with missing environment variables"""
        from pdf_processor import main
        main()
        
        mock_exit.assert_called_with(1)
        mock_print.assert_called_with(
            "ERROR: INPUT_S3_URI and OUTPUT_S3_URI environment variables are required"
        )


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)