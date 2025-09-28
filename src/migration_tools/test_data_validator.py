"""
Unit tests for data validation functionality

Tests the data validation and integrity checking tools for
Timestream to InfluxDB migration validation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import hashlib

from data_validator import DataValidator, ValidationResult, validate_multiple_tables


class TestDataValidator(unittest.TestCase):
    """Test cases for DataValidator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = DataValidator(
            timestream_region='us-east-1',
            influxdb_url='http://localhost:8086',
            influxdb_token='test-token',
            influxdb_org='test-org',
            sample_size=100
        )
        
        self.start_time = datetime(2024, 1, 1, 0, 0, 0)
        self.end_time = datetime(2024, 1, 2, 0, 0, 0)
    
    @patch('boto3.client')
    def test_init_timestream_client(self, mock_boto_client):
        """Test Timestream client initialization"""
        validator = DataValidator(timestream_region='us-west-2')
        mock_boto_client.assert_called_with('timestream-query', region_name='us-west-2')
    
    def test_validation_result_initialization(self):
        """Test ValidationResult dataclass initialization"""
        result = ValidationResult(
            validation_id='test-123',
            source_database='test_db',
            source_table='test_table',
            target_bucket='test_bucket',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00'
        )
        
        self.assertEqual(result.validation_id, 'test-123')
        self.assertEqual(result.source_database, 'test_db')
        self.assertEqual(result.overall_status, 'pending')
        self.assertEqual(result.validation_errors, [])
        self.assertEqual(result.validation_warnings, [])
        self.assertIsNotNone(result.validation_timestamp)
    
    @patch('src.migration_tools.data_validator.DataValidator._validate_record_counts')
    @patch('src.migration_tools.data_validator.DataValidator._validate_time_ranges')
    @patch('src.migration_tools.data_validator.DataValidator._validate_schemas')
    @patch('src.migration_tools.data_validator.DataValidator._validate_sample_data')
    @patch('src.migration_tools.data_validator.DataValidator._validate_checksums')
    @patch('src.migration_tools.data_validator.DataValidator._determine_overall_status')
    def test_validate_migration_success(self, mock_status, mock_checksums, mock_sample,
                                       mock_schemas, mock_time_ranges, mock_counts):
        """Test successful migration validation"""
        result = self.validator.validate_migration(
            source_database='test_db',
            source_table='test_table',
            target_bucket='test_bucket',
            start_time=self.start_time,
            end_time=self.end_time,
            validation_id='test-validation'
        )
        
        self.assertEqual(result.validation_id, 'test-validation')
        self.assertEqual(result.source_database, 'test_db')
        self.assertEqual(result.source_table, 'test_table')
        self.assertEqual(result.target_bucket, 'test_bucket')
        
        # Verify all validation methods were called
        mock_counts.assert_called_once()
        mock_time_ranges.assert_called_once()
        mock_schemas.assert_called_once()
        mock_sample.assert_called_once()
        mock_checksums.assert_called_once()
        mock_status.assert_called_once()
    
    def test_validate_migration_exception_handling(self):
        """Test validation exception handling"""
        with patch.object(self.validator, '_validate_record_counts', side_effect=Exception('Test error')):
            result = self.validator.validate_migration(
                source_database='test_db',
                source_table='test_table',
                target_bucket='test_bucket',
                start_time=self.start_time,
                end_time=self.end_time
            )
            
            self.assertEqual(result.overall_status, 'failed')
            self.assertIn('Validation failed: Test error', result.validation_errors)
    
    @patch('boto3.client')
    def test_validate_record_counts_match(self, mock_boto_client):
        """Test record count validation when counts match"""
        # Mock Timestream response
        mock_timestream = Mock()
        mock_timestream.query.return_value = {
            'Rows': [{'Data': [{'ScalarValue': '1000'}]}]
        }
        mock_boto_client.return_value = mock_timestream
        
        # Mock InfluxDB response
        mock_record = Mock()
        mock_record.get_value.return_value = 1000
        mock_table = Mock()
        mock_table.records = [mock_record]
        
        with patch.object(self.validator, 'influxdb_query_api') as mock_influx_api:
            mock_influx_api.query.return_value = [mock_table]
            
            result = ValidationResult(
                validation_id='test',
                source_database='test_db',
                source_table='test_table',
                target_bucket='test_bucket',
                start_time=self.start_time.isoformat(),
                end_time=self.end_time.isoformat()
            )
            
            self.validator._validate_record_counts(result, self.start_time, self.end_time)
            
            self.assertEqual(result.source_record_count, 1000)
            self.assertEqual(result.target_record_count, 1000)
            self.assertTrue(result.count_match)
            self.assertEqual(len(result.validation_errors), 0)
    
    @patch('boto3.client')
    def test_validate_record_counts_mismatch(self, mock_boto_client):
        """Test record count validation when counts don't match"""
        # Mock Timestream response
        mock_timestream = Mock()
        mock_timestream.query.return_value = {
            'Rows': [{'Data': [{'ScalarValue': '1000'}]}]
        }
        mock_boto_client.return_value = mock_timestream
        
        # Mock InfluxDB response with different count
        mock_record = Mock()
        mock_record.get_value.return_value = 950
        mock_table = Mock()
        mock_table.records = [mock_record]
        
        with patch.object(self.validator, 'influxdb_query_api') as mock_influx_api:
            mock_influx_api.query.return_value = [mock_table]
            
            result = ValidationResult(
                validation_id='test',
                source_database='test_db',
                source_table='test_table',
                target_bucket='test_bucket',
                start_time=self.start_time.isoformat(),
                end_time=self.end_time.isoformat()
            )
            
            self.validator._validate_record_counts(result, self.start_time, self.end_time)
            
            self.assertEqual(result.source_record_count, 1000)
            self.assertEqual(result.target_record_count, 950)
            self.assertFalse(result.count_match)
            self.assertIn('Record count mismatch', result.validation_errors[0])
    
    def test_parse_timestream_response(self):
        """Test parsing of Timestream query response"""
        response = {
            'ColumnInfo': [
                {'Name': 'time'},
                {'Name': 'measure_name'},
                {'Name': 'measure_value::double'}
            ],
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': '2024-01-01T00:00:00.000000000'},
                        {'ScalarValue': 'temperature'},
                        {'ScalarValue': '25.5'}
                    ]
                },
                {
                    'Data': [
                        {'ScalarValue': '2024-01-01T01:00:00.000000000'},
                        {'ScalarValue': 'humidity'},
                        {'ScalarValue': '60.0'}
                    ]
                }
            ]
        }
        
        result = self.validator._parse_timestream_response(response)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['time'], '2024-01-01T00:00:00.000000000')
        self.assertEqual(result[0]['measure_name'], 'temperature')
        self.assertEqual(result[0]['measure_value::double'], '25.5')
        self.assertEqual(result[1]['measure_name'], 'humidity')
    
    def test_parse_timestream_response_empty(self):
        """Test parsing empty Timestream response"""
        response = {'Rows': []}
        result = self.validator._parse_timestream_response(response)
        self.assertEqual(result, [])
        
        response = {}
        result = self.validator._parse_timestream_response(response)
        self.assertEqual(result, [])
    
    def test_determine_overall_status(self):
        """Test overall status determination logic"""
        # Test passed status
        result = ValidationResult(
            validation_id='test',
            source_database='test_db',
            source_table='test_table',
            target_bucket='test_bucket',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00'
        )
        
        self.validator._determine_overall_status(result)
        self.assertEqual(result.overall_status, 'passed')
        
        # Test warning status
        result.validation_warnings.append('Test warning')
        self.validator._determine_overall_status(result)
        self.assertEqual(result.overall_status, 'warning')
        
        # Test failed status
        result.validation_errors.append('Test error')
        self.validator._determine_overall_status(result)
        self.assertEqual(result.overall_status, 'failed')
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        result = ValidationResult(
            validation_id='test-123',
            source_database='test_db',
            source_table='test_table',
            target_bucket='test_bucket',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00',
            source_record_count=1000,
            target_record_count=1000,
            count_match=True,
            overall_status='passed',
            validation_duration_seconds=45.5
        )
        
        report = self.validator.generate_validation_report(result)
        
        self.assertIn('Data Migration Validation Report', report)
        self.assertIn('test-123', report)
        self.assertIn('test_db.test_table', report)
        self.assertIn('test_bucket', report)
        self.assertIn('PASSED', report)
        self.assertIn('1,000', report)
        self.assertIn('45.50 seconds', report)
        self.assertIn('✓', report)
    
    def test_generate_validation_report_with_errors(self):
        """Test validation report generation with errors and warnings"""
        result = ValidationResult(
            validation_id='test-456',
            source_database='test_db',
            source_table='test_table',
            target_bucket='test_bucket',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00',
            overall_status='failed',
            validation_errors=['Count mismatch', 'Schema error'],
            validation_warnings=['Performance warning']
        )
        
        report = self.validator.generate_validation_report(result)
        
        self.assertIn('FAILED', report)
        self.assertIn('Validation Errors:', report)
        self.assertIn('Count mismatch', report)
        self.assertIn('Schema error', report)
        self.assertIn('Validation Warnings:', report)
        self.assertIn('Performance warning', report)
        self.assertIn('✗', report)
        self.assertIn('⚠', report)


class TestValidateMultipleTables(unittest.TestCase):
    """Test cases for validate_multiple_tables function"""
    
    @patch('src.migration_tools.data_validator.DataValidator')
    def test_validate_multiple_tables(self, mock_validator_class):
        """Test validation of multiple tables"""
        # Mock validator instance
        mock_validator = Mock()
        mock_result1 = ValidationResult(
            validation_id='test-1',
            source_database='db1',
            source_table='table1',
            target_bucket='bucket1',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00',
            overall_status='passed'
        )
        mock_result2 = ValidationResult(
            validation_id='test-2',
            source_database='db2',
            source_table='table2',
            target_bucket='bucket2',
            start_time='2024-01-01T00:00:00',
            end_time='2024-01-02T00:00:00',
            overall_status='warning'
        )
        
        mock_validator.validate_migration.side_effect = [mock_result1, mock_result2]
        mock_validator_class.return_value = mock_validator
        
        tables_config = [
            {
                'database': 'db1',
                'table': 'table1',
                'bucket': 'bucket1',
                'start_time': '2024-01-01T00:00:00',
                'end_time': '2024-01-02T00:00:00'
            },
            {
                'database': 'db2',
                'table': 'table2',
                'bucket': 'bucket2',
                'start_time': '2024-01-01T00:00:00',
                'end_time': '2024-01-02T00:00:00'
            }
        ]
        
        results = validate_multiple_tables(
            tables_config=tables_config,
            influxdb_url='http://localhost:8086',
            influxdb_token='test-token',
            influxdb_org='test-org'
        )
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].overall_status, 'passed')
        self.assertEqual(results[1].overall_status, 'warning')
        
        # Verify validator was called correctly
        self.assertEqual(mock_validator.validate_migration.call_count, 2)


if __name__ == '__main__':
    unittest.main()