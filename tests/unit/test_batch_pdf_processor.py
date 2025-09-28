"""
Comprehensive unit tests for Batch PDF Processor
Tests PDF table extraction, data standardization, and error handling
"""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
import sys

# Add source path
sys.path.insert(0, 'src/batch_pdf_processor')

from pdf_processor import PDFProcessor


class TestPDFProcessor:
    """Test PDFProcessor class functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = PDFProcessor()
        
        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.processor.temp_dir = self.temp_dir
        self.processor.output_dir = self.temp_dir / 'output'
        self.processor.output_dir.mkdir(exist_ok=True)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_parse_s3_uri_valid(self):
        """Test S3 URI parsing with valid URIs"""
        test_cases = [
            ('s3://bucket/key', ('bucket', 'key')),
            ('s3://my-bucket/path/to/file.pdf', ('my-bucket', 'path/to/file.pdf')),
            ('s3://bucket-name/deep/nested/path/file.pdf', ('bucket-name', 'deep/nested/path/file.pdf'))
        ]
        
        for s3_uri, expected in test_cases:
            bucket, key = self.processor._parse_s3_uri(s3_uri)
            assert bucket == expected[0]
            assert key == expected[1]
    
    def test_parse_s3_uri_invalid(self):
        """Test S3 URI parsing with invalid URIs"""
        invalid_uris = [
            'http://bucket/key',
            's3://bucket',
            's3://',
            'bucket/key',
            ''
        ]
        
        for invalid_uri in invalid_uris:
            with pytest.raises(ValueError, match="Invalid S3 URI format"):
                self.processor._parse_s3_uri(invalid_uri)
    
    def test_download_pdf_success(self):
        """Test successful PDF download from S3"""
        test_content = b'PDF content for testing'
        
        with patch.object(self.processor, 's3_client') as mock_s3:
            mock_s3.download_file.return_value = None
            
            # Create a test file to simulate download
            test_file = self.temp_dir / 'test.pdf'
            test_file.write_bytes(test_content)
            
            # Mock the download to write to our test file
            def mock_download(bucket, key, local_path):
                Path(local_path).write_bytes(test_content)
            
            mock_s3.download_file.side_effect = mock_download
            
            result_path = self.processor._download_pdf('test-bucket', 'test.pdf')
            
            assert result_path.exists()
            assert result_path.read_bytes() == test_content
            mock_s3.download_file.assert_called_once_with('test-bucket', 'test.pdf', str(result_path))
    
    def test_download_pdf_failure(self):
        """Test PDF download failure handling"""
        with patch.object(self.processor, 's3_client') as mock_s3:
            mock_s3.download_file.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
                'download_file'
            )
            
            with pytest.raises(Exception, match="Failed to download PDF from S3"):
                self.processor._download_pdf('test-bucket', 'nonexistent.pdf')
    
    def test_identify_timestamp_column(self):
        """Test timestamp column identification"""
        test_cases = [
            (['data', 'valor', 'regiao'], 'data'),
            (['timestamp', 'value', 'region'], 'timestamp'),
            (['hora', 'potencia', 'fonte'], 'hora'),
            (['periodo', 'energia', 'tipo'], 'periodo'),
            (['value', 'region', 'source'], None)  # No timestamp column
        ]
        
        for columns, expected in test_cases:
            df = pd.DataFrame({col: [1, 2, 3] for col in columns})
            result = self.processor._identify_timestamp_column(df)
            assert result == expected
    
    def test_is_header_row(self):
        """Test header row identification"""
        # Header-like rows
        header_rows = [
            pd.Series(['Total', '1000', '2000']),
            pd.Series(['Subtotal', 'Hidrica', '500']),
            pd.Series(['Média', '750', 'MW']),
            pd.Series(['Fonte: ONS', '', ''])
        ]
        
        for row in header_rows:
            assert self.processor._is_header_row(row) is True
        
        # Data rows
        data_rows = [
            pd.Series(['2024-01-01', '1000', 'Sudeste']),
            pd.Series(['10:00', '1500', 'Hidrica']),
            pd.Series(['Janeiro', '2000', 'MW'])
        ]
        
        for row in data_rows:
            assert self.processor._is_header_row(row) is False
    
    def test_extract_timestamp_valid(self):
        """Test timestamp extraction with valid timestamps"""
        test_cases = [
            ('2024-01-01', '2024-01-01T00:00:00'),
            ('2024-01-01 10:30', '2024-01-01T10:30:00'),
            ('01/01/2024', '2024-01-01T00:00:00'),
            ('Jan 2024', '2024-01-01T00:00:00')
        ]
        
        for timestamp_val, expected_start in test_cases:
            row = pd.Series({'timestamp': timestamp_val, 'value': 1000})
            result = self.processor._extract_timestamp(row, 'timestamp')
            
            # Check that result is a valid ISO format timestamp
            assert 'T' in result
            assert result.startswith(expected_start[:10])  # Check date part
    
    def test_extract_timestamp_invalid(self):
        """Test timestamp extraction with invalid timestamps"""
        row = pd.Series({'timestamp': 'invalid-date', 'value': 1000})
        result = self.processor._extract_timestamp(row, 'timestamp')
        
        # Should return current timestamp when invalid
        assert 'T' in result
        assert result.endswith('Z') or '+' in result or result.count(':') >= 2
    
    def test_convert_to_numeric_valid(self):
        """Test numeric conversion with valid values"""
        test_cases = [
            ('1000', 1000.0),
            ('1.500,50', 1500.50),  # Brazilian format
            ('2,000.75', 2000.75),  # US format
            ('50%', 50.0),
            ('  1234.56  ', 1234.56),
            (1500, 1500.0),
            (1500.75, 1500.75)
        ]
        
        for input_val, expected in test_cases:
            result = self.processor._convert_to_numeric(input_val)
            assert result == expected
    
    def test_convert_to_numeric_invalid(self):
        """Test numeric conversion with invalid values"""
        invalid_values = [
            'not-a-number',
            '',
            None,
            'abc123',
            '12.34.56'
        ]
        
        for invalid_val in invalid_values:
            result = self.processor._convert_to_numeric(invalid_val)
            assert result is None
    
    def test_infer_dataset_type(self):
        """Test dataset type inference"""
        test_cases = [
            ('geracao_mensal.pdf', 'potencia_mw', 'generation'),
            ('generation_report.pdf', 'power', 'generation'),
            ('consumo_regional.pdf', 'demanda', 'consumption'),
            ('consumption_data.pdf', 'load', 'consumption'),
            ('transmissao_rede.pdf', 'fluxo', 'transmission'),
            ('transmission_lines.pdf', 'capacity', 'transmission'),
            ('outros_dados.pdf', 'value', 'other'),
            ('unknown_file.pdf', 'mw', 'generation')  # Inferred from column
        ]
        
        for filename, column, expected in test_cases:
            result = self.processor._infer_dataset_type(filename, column)
            assert result == expected
    
    def test_extract_region(self):
        """Test region extraction"""
        test_cases = [
            ('dados_sudeste.pdf', pd.Series([]), 'sudeste'),
            ('relatorio_nordeste.pdf', pd.Series([]), 'nordeste'),
            ('brasil_nacional.pdf', pd.Series([]), 'brasil'),
            ('sp_dados.pdf', pd.Series([]), 'sp'),
            ('unknown_file.pdf', pd.Series(['Norte', 'Sul']), 'norte'),
            ('generic.pdf', pd.Series(['data', 'value']), 'brasil')  # Default
        ]
        
        for filename, row, expected in test_cases:
            result = self.processor._extract_region(filename, row)
            assert result == expected
    
    def test_extract_energy_source(self):
        """Test energy source extraction"""
        test_cases = [
            ('hidrica_mw', pd.Series([]), 'hidrica'),
            ('eolica_capacity', pd.Series([]), 'eolica'),
            ('solar_power', pd.Series([]), 'solar'),
            ('termica_generation', pd.Series([]), 'termica'),
            ('nuclear_plant', pd.Series([]), 'nuclear'),
            ('biomassa_energy', pd.Series([]), 'biomassa'),
            ('total_capacity', pd.Series([]), 'total'),
            ('unknown_column', pd.Series([]), 'total')
        ]
        
        for column, row, expected in test_cases:
            result = self.processor._extract_energy_source(column, row)
            assert result == expected
    
    def test_infer_unit(self):
        """Test unit inference"""
        test_cases = [
            ('potencia_mw', '1000', 'MW'),
            ('capacity_gw', '1.5', 'GW'),
            ('energia_mwh', '5000', 'MWh'),
            ('consumption_gwh', '2.5', 'GWh'),
            ('percentage', '85%', '%'),
            ('unknown_column', '1000', 'MW')  # Default
        ]
        
        for column, value, expected in test_cases:
            result = self.processor._infer_unit(column, value)
            assert result == expected
    
    def test_standardize_data(self):
        """Test data standardization"""
        # Mock extracted tables
        mock_tables = [
            pd.DataFrame({
                'data': ['2024-01-01', '2024-01-02'],
                'hidrica_mw': [1500.0, 1600.0],
                'eolica_mw': [800.0, 850.0],
                'regiao': ['Sudeste', 'Nordeste']
            })
        ]
        
        # Set attributes for extraction method
        mock_tables[0].attrs = {'extraction_method': 'camelot_lattice', 'accuracy': 95.0}
        
        result_df = self.processor._standardize_data(mock_tables, 'test_generation.pdf')
        
        # Check basic structure
        assert len(result_df) > 0
        assert 'timestamp' in result_df.columns
        assert 'dataset_type' in result_df.columns
        assert 'region' in result_df.columns
        assert 'energy_source' in result_df.columns
        assert 'value' in result_df.columns
        assert 'unit' in result_df.columns
        assert 'quality_flag' in result_df.columns
        
        # Check metadata
        assert 'processing_metadata' in result_df.columns
        
        # Check data types and values
        assert result_df['quality_flag'].iloc[0] == 'extracted'
        assert result_df['dataset_type'].iloc[0] == 'generation'
        assert result_df['unit'].iloc[0] == 'MW'
    
    def test_standardize_data_empty_tables(self):
        """Test standardization with empty tables"""
        empty_tables = [pd.DataFrame()]
        
        with pytest.raises(ValueError, match="No valid data could be extracted"):
            self.processor._standardize_data(empty_tables, 'empty.pdf')
    
    def test_save_as_parquet(self):
        """Test saving DataFrame as Parquet"""
        test_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='H'),
            'dataset_type': ['generation'] * 3,
            'region': ['sudeste'] * 3,
            'energy_source': ['hidrica'] * 3,
            'value': [1500.0, 1600.0, 1550.0],
            'unit': ['MW'] * 3,
            'quality_flag': ['extracted'] * 3
        })
        
        output_path = self.processor._save_as_parquet(test_df)
        
        assert output_path.exists()
        assert output_path.suffix == '.parquet'
        
        # Verify file can be read back
        loaded_df = pd.read_parquet(output_path)
        assert len(loaded_df) == 3
        assert list(loaded_df.columns) == list(test_df.columns)
    
    def test_upload_to_s3_success(self):
        """Test successful S3 upload"""
        test_file = self.temp_dir / 'test_upload.parquet'
        test_file.write_text('test parquet content')
        
        with patch.object(self.processor, 's3_client') as mock_s3:
            mock_s3.upload_file.return_value = None
            
            self.processor._upload_to_s3(test_file, 'test-bucket', 'output/test.parquet')
            
            mock_s3.upload_file.assert_called_once_with(
                str(test_file), 'test-bucket', 'output/test.parquet'
            )
    
    def test_upload_to_s3_failure(self):
        """Test S3 upload failure handling"""
        test_file = self.temp_dir / 'test_upload.parquet'
        test_file.write_text('test content')
        
        with patch.object(self.processor, 's3_client') as mock_s3:
            mock_s3.upload_file.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'upload_file'
            )
            
            with pytest.raises(Exception, match="Failed to upload to S3"):
                self.processor._upload_to_s3(test_file, 'test-bucket', 'output/test.parquet')
    
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        # Create test files
        test_files = [
            self.temp_dir / 'file1.pdf',
            self.temp_dir / 'file2.parquet',
            self.temp_dir / 'nonexistent.txt'  # This one doesn't exist
        ]
        
        # Create the first two files
        test_files[0].write_text('pdf content')
        test_files[1].write_text('parquet content')
        
        # Cleanup should handle both existing and non-existing files
        self.processor._cleanup_temp_files(test_files)
        
        # Existing files should be deleted
        assert not test_files[0].exists()
        assert not test_files[1].exists()
        # Non-existing file should not cause error


class TestPDFTableExtraction:
    """Test PDF table extraction methods"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = PDFProcessor()
    
    @patch('camelot.read_pdf')
    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_extract_tables_multi_method_success(self, mock_pdfplumber, mock_tabula, mock_camelot):
        """Test successful table extraction using multiple methods"""
        # Mock Camelot extraction
        mock_camelot_table = Mock()
        mock_camelot_table.accuracy = 85.0
        mock_camelot_table.df = pd.DataFrame({
            'Data': ['2024-01-01', '2024-01-02'],
            'Hidrica (MW)': [1500.0, 1600.0]
        })
        mock_camelot.return_value = [mock_camelot_table]
        
        # Mock Tabula extraction
        mock_tabula.return_value = [
            pd.DataFrame({
                'Periodo': ['Jan/2024', 'Fev/2024'],
                'Eolica (MW)': [800.0, 850.0]
            })
        ]
        
        # Mock pdfplumber extraction
        mock_page = Mock()
        mock_page.extract_tables.return_value = [
            [
                ['Fonte', 'Capacidade (MW)'],
                ['Solar', '200'],
                ['Biomassa', '150']
            ]
        ]
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf
        
        # Create a dummy PDF file
        pdf_path = Path('/tmp/test.pdf')
        
        tables = self.processor._extract_tables_multi_method(pdf_path)
        
        # Should have extracted tables from all methods
        assert len(tables) >= 2  # At least Camelot and Tabula
        
        # Check that extraction methods are recorded
        for table in tables:
            assert hasattr(table, 'attrs')
            assert 'extraction_method' in table.attrs
    
    @patch('camelot.read_pdf')
    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_extract_tables_all_methods_fail(self, mock_pdfplumber, mock_tabula, mock_camelot):
        """Test when all extraction methods fail"""
        # All methods raise exceptions
        mock_camelot.side_effect = Exception("Camelot failed")
        mock_tabula.side_effect = Exception("Tabula failed")
        mock_pdfplumber.side_effect = Exception("pdfplumber failed")
        
        pdf_path = Path('/tmp/test.pdf')
        
        tables = self.processor._extract_tables_multi_method(pdf_path)
        
        # Should return empty list when all methods fail
        assert len(tables) == 0
    
    @patch('camelot.read_pdf')
    def test_extract_tables_low_accuracy_filtering(self, mock_camelot):
        """Test filtering of low accuracy tables"""
        # Mock tables with different accuracy levels
        high_accuracy_table = Mock()
        high_accuracy_table.accuracy = 85.0
        high_accuracy_table.df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
        
        low_accuracy_table = Mock()
        low_accuracy_table.accuracy = 25.0  # Below threshold
        low_accuracy_table.df = pd.DataFrame({'col1': [5, 6], 'col2': [7, 8]})
        
        mock_camelot.return_value = [high_accuracy_table, low_accuracy_table]
        
        pdf_path = Path('/tmp/test.pdf')
        
        tables = self.processor._extract_tables_multi_method(pdf_path)
        
        # Should only include high accuracy table
        assert len(tables) == 1
        assert tables[0].attrs['accuracy'] == 85.0


class TestPDFProcessingIntegration:
    """Test complete PDF processing integration"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = PDFProcessor()
        
        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.processor.temp_dir = self.temp_dir
        self.processor.output_dir = self.temp_dir / 'output'
        self.processor.output_dir.mkdir(exist_ok=True)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_process_pdf_file_success(self):
        """Test successful complete PDF processing"""
        input_s3_uri = 's3://input-bucket/reports/generation_report.pdf'
        output_s3_uri = 's3://output-bucket/processed/generation_data.parquet'
        
        # Mock the entire processing pipeline
        with patch.object(self.processor, '_download_pdf') as mock_download, \
             patch.object(self.processor, '_extract_tables_multi_method') as mock_extract, \
             patch.object(self.processor, '_standardize_data') as mock_standardize, \
             patch.object(self.processor, '_save_as_parquet') as mock_save, \
             patch.object(self.processor, '_upload_to_s3') as mock_upload, \
             patch.object(self.processor, '_cleanup_temp_files') as mock_cleanup:
            
            # Setup mocks
            mock_pdf_path = self.temp_dir / 'test.pdf'
            mock_pdf_path.write_text('mock pdf content')
            mock_download.return_value = mock_pdf_path
            
            mock_tables = [pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})]
            mock_extract.return_value = mock_tables
            
            mock_standardized = pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=2, freq='H'),
                'value': [1000.0, 1100.0],
                'region': ['sudeste', 'nordeste']
            })
            mock_standardize.return_value = mock_standardized
            
            mock_parquet_path = self.temp_dir / 'output.parquet'
            mock_save.return_value = mock_parquet_path
            
            # Execute processing
            result = self.processor.process_pdf_file(input_s3_uri, output_s3_uri)
            
            # Verify result
            assert result['status'] == 'success'
            assert result['input_file'] == input_s3_uri
            assert result['output_file'] == output_s3_uri
            assert result['tables_extracted'] == 1
            assert result['rows_processed'] == 2
            
            # Verify all steps were called
            mock_download.assert_called_once()
            mock_extract.assert_called_once()
            mock_standardize.assert_called_once()
            mock_save.assert_called_once()
            mock_upload.assert_called_once()
            mock_cleanup.assert_called_once()
    
    def test_process_pdf_file_no_tables_found(self):
        """Test processing when no tables are found"""
        input_s3_uri = 's3://input-bucket/reports/empty_report.pdf'
        output_s3_uri = 's3://output-bucket/processed/empty_data.parquet'
        
        with patch.object(self.processor, '_download_pdf') as mock_download, \
             patch.object(self.processor, '_extract_tables_multi_method') as mock_extract:
            
            mock_pdf_path = self.temp_dir / 'empty.pdf'
            mock_download.return_value = mock_pdf_path
            mock_extract.return_value = []  # No tables found
            
            result = self.processor.process_pdf_file(input_s3_uri, output_s3_uri)
            
            assert result['status'] == 'error'
            assert 'No tables found' in result['error_message']
    
    def test_process_pdf_file_download_failure(self):
        """Test processing with download failure"""
        input_s3_uri = 's3://input-bucket/reports/missing_report.pdf'
        output_s3_uri = 's3://output-bucket/processed/missing_data.parquet'
        
        with patch.object(self.processor, '_download_pdf') as mock_download:
            mock_download.side_effect = Exception("Download failed")
            
            result = self.processor.process_pdf_file(input_s3_uri, output_s3_uri)
            
            assert result['status'] == 'error'
            assert 'Download failed' in result['error_message']
    
    def test_process_pdf_file_standardization_failure(self):
        """Test processing with data standardization failure"""
        input_s3_uri = 's3://input-bucket/reports/corrupt_report.pdf'
        output_s3_uri = 's3://output-bucket/processed/corrupt_data.parquet'
        
        with patch.object(self.processor, '_download_pdf') as mock_download, \
             patch.object(self.processor, '_extract_tables_multi_method') as mock_extract, \
             patch.object(self.processor, '_standardize_data') as mock_standardize:
            
            mock_pdf_path = self.temp_dir / 'corrupt.pdf'
            mock_download.return_value = mock_pdf_path
            
            mock_tables = [pd.DataFrame({'col1': [1, 2]})]
            mock_extract.return_value = mock_tables
            
            mock_standardize.side_effect = Exception("Standardization failed")
            
            result = self.processor.process_pdf_file(input_s3_uri, output_s3_uri)
            
            assert result['status'] == 'error'
            assert 'Standardization failed' in result['error_message']


class TestMainFunction:
    """Test main function and command-line interface"""
    
    @patch.dict(os.environ, {
        'INPUT_S3_URI': 's3://input-bucket/test.pdf',
        'OUTPUT_S3_URI': 's3://output-bucket/test.parquet'
    })
    @patch('src.batch_pdf_processor.pdf_processor.PDFProcessor')
    def test_main_success(self, mock_processor_class):
        """Test successful main function execution"""
        from pdf_processor import main
        
        mock_processor = Mock()
        mock_processor.process_pdf_file.return_value = {
            'status': 'success',
            'input_file': 's3://input-bucket/test.pdf',
            'output_file': 's3://output-bucket/test.parquet',
            'tables_extracted': 2,
            'rows_processed': 100
        }
        mock_processor_class.return_value = mock_processor
        
        with patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)
    
    @patch.dict(os.environ, {
        'INPUT_S3_URI': 's3://input-bucket/test.pdf',
        'OUTPUT_S3_URI': 's3://output-bucket/test.parquet'
    })
    @patch('src.batch_pdf_processor.pdf_processor.PDFProcessor')
    def test_main_failure(self, mock_processor_class):
        """Test main function with processing failure"""
        from pdf_processor import main
        
        mock_processor = Mock()
        mock_processor.process_pdf_file.return_value = {
            'status': 'error',
            'error_message': 'Processing failed'
        }
        mock_processor_class.return_value = mock_processor
        
        with patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)
    
    def test_main_missing_environment_variables(self):
        """Test main function with missing environment variables"""
        from pdf_processor import main
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_once_with(1)


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases"""
    
    def setup_method(self):
        """Setup test environment"""
        self.processor = PDFProcessor()
    
    def test_malformed_pdf_handling(self):
        """Test handling of malformed PDF files"""
        with patch('camelot.read_pdf') as mock_camelot, \
             patch('tabula.read_pdf') as mock_tabula, \
             patch('pdfplumber.open') as mock_pdfplumber:
            
            # All extraction methods fail due to malformed PDF
            mock_camelot.side_effect = Exception("PDF parsing error")
            mock_tabula.side_effect = Exception("PDF parsing error")
            mock_pdfplumber.side_effect = Exception("PDF parsing error")
            
            pdf_path = Path('/tmp/malformed.pdf')
            
            tables = self.processor._extract_tables_multi_method(pdf_path)
            
            # Should handle gracefully and return empty list
            assert len(tables) == 0
    
    def test_empty_table_handling(self):
        """Test handling of empty tables"""
        empty_tables = [
            pd.DataFrame(),  # Completely empty
            pd.DataFrame({'col1': [], 'col2': []}),  # Empty with columns
            pd.DataFrame({'col1': [None, None], 'col2': [None, None]})  # Only nulls
        ]
        
        for table in empty_tables:
            table.attrs = {'extraction_method': 'test'}
        
        with pytest.raises(ValueError, match="No valid data could be extracted"):
            self.processor._standardize_data(empty_tables, 'empty.pdf')
    
    def test_unicode_handling_in_pdf_text(self):
        """Test handling of Unicode characters in PDF text"""
        unicode_df = pd.DataFrame({
            'região': ['São Paulo', 'Brasília'],
            'fonte_energia': ['Hidráulica', 'Eólica'],
            'potência_mw': [1500.0, 800.0]
        })
        unicode_df.attrs = {'extraction_method': 'test'}
        
        result_df = self.processor._standardize_data([unicode_df], 'unicode.pdf')
        
        # Should handle Unicode characters properly
        assert len(result_df) > 0
        assert 'region' in result_df.columns
        assert 'energy_source' in result_df.columns
    
    def test_large_table_processing(self):
        """Test processing of large tables"""
        # Create large table (1000 rows)
        large_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=1000, freq='H'),
            'hidrica_mw': [1500.0 + i for i in range(1000)],
            'eolica_mw': [800.0 + i * 0.5 for i in range(1000)],
            'regiao': ['Sudeste'] * 1000
        })
        large_df.attrs = {'extraction_method': 'test'}
        
        result_df = self.processor._standardize_data([large_df], 'large.pdf')
        
        # Should process large tables successfully
        assert len(result_df) >= 1000  # Should have many rows (2 columns * 1000 rows)
        assert 'timestamp' in result_df.columns
        assert 'value' in result_df.columns
    
    def test_mixed_data_types_in_table(self):
        """Test handling of mixed data types in table cells"""
        mixed_df = pd.DataFrame({
            'data': ['2024-01-01', 1704067200, '01/01/2024'],  # Mixed timestamp formats
            'valor': [1000.0, '1,500.50', 'N/A'],  # Mixed numeric formats
            'regiao': ['Sudeste', 123, None],  # Mixed types
            'observacao': ['Normal', '', 'Teste']
        })
        mixed_df.attrs = {'extraction_method': 'test'}
        
        result_df = self.processor._standardize_data([mixed_df], 'mixed.pdf')
        
        # Should handle mixed types gracefully
        assert len(result_df) > 0
        
        # Should convert and clean data appropriately
        assert 'timestamp' in result_df.columns
        assert 'value' in result_df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])