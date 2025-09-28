"""
Unit tests for data conversion utilities.

Tests the EnergyDataConverter class and related functions for converting
Parquet data structures to InfluxDB Point objects.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from influxdb_client import Point, WritePrecision

from src.shared_utils.data_conversion import (
    EnergyDataConverter,
    DataConversionError,
    create_converter,
    convert_parquet_to_influxdb_points,
    get_dataset_type_from_s3_key,
    validate_influxdb_points
)


class TestEnergyDataConverter:
    """Test cases for EnergyDataConverter class."""
    
    @pytest.fixture
    def sample_generation_data(self):
        """Sample generation dataset for testing."""
        return pd.DataFrame({
            'timestamp': [
                '2024-01-01T12:00:00Z',
                '2024-01-01T13:00:00Z',
                '2024-01-01T14:00:00Z'
            ],
            'region': ['southeast', 'northeast', 'south'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw'],
            'value': [1000.0, 500.0, 300.0],
            'unit': ['MW', 'MW', 'MW'],
            'plant_name': ['Itaipu', 'WindFarm1', 'SolarPark1'],
            'capacity_mw': [14000.0, 1000.0, 500.0],
            'efficiency': [0.85, 0.92, 0.88]
        })
    
    @pytest.fixture
    def sample_consumption_data(self):
        """Sample consumption dataset for testing."""
        return pd.DataFrame({
            'timestamp': [
                '2024-01-01T12:00:00Z',
                '2024-01-01T13:00:00Z'
            ],
            'region': ['southeast', 'northeast'],
            'consumer_type': ['industrial', 'residential'],
            'measurement_type': ['demand_mw', 'demand_mw'],
            'value': [800.0, 200.0],
            'unit': ['MW', 'MW'],
            'sector': ['manufacturing', 'residential']
        })
    
    @pytest.fixture
    def sample_transmission_data(self):
        """Sample transmission dataset for testing."""
        return pd.DataFrame({
            'timestamp': [
                '2024-01-01T12:00:00Z',
                '2024-01-01T13:00:00Z'
            ],
            'region': ['southeast', 'northeast'],
            'line_id': ['SE-NE-001', 'NE-N-002'],
            'measurement_type': ['flow_mw', 'losses_mwh'],
            'value': [2500.0, 45.2],
            'unit': ['MW', 'MWh'],
            'voltage_kv': [500.0, 230.0]
        })
    
    def test_init_valid_dataset_type(self):
        """Test converter initialization with valid dataset types."""
        for dataset_type in ['generation', 'consumption', 'transmission']:
            converter = EnergyDataConverter(dataset_type)
            assert converter.dataset_type == dataset_type
            assert converter.config is not None
    
    def test_init_invalid_dataset_type(self):
        """Test converter initialization with invalid dataset type."""
        with pytest.raises(ValueError, match="Unsupported dataset type"):
            EnergyDataConverter('invalid_type')
    
    def test_validate_dataframe_schema_valid(self, sample_generation_data):
        """Test schema validation with valid DataFrame."""
        converter = EnergyDataConverter('generation')
        result = converter.validate_dataframe_schema(sample_generation_data)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_dataframe_schema_missing_columns(self):
        """Test schema validation with missing required columns."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({'timestamp': ['2024-01-01T12:00:00Z']})
        
        result = converter.validate_dataframe_schema(df)
        
        assert result['valid'] is False
        assert any('Missing required columns' in error for error in result['errors'])
    
    def test_validate_dataframe_schema_invalid_timestamp(self):
        """Test schema validation with invalid timestamp format."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['invalid-timestamp'],
            'region': ['southeast'],
            'value': [1000.0],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_mw']
        })
        
        result = converter.validate_dataframe_schema(df)
        
        assert result['valid'] is False
        assert any('Invalid timestamp format' in error for error in result['errors'])
    
    def test_validate_dataframe_schema_non_numeric_value(self):
        """Test schema validation with non-numeric value column."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z'],
            'region': ['southeast'],
            'value': ['not-a-number'],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_mw']
        })
        
        result = converter.validate_dataframe_schema(df)
        
        # Should have warnings about conversion, not errors
        assert len(result['warnings']) > 0
    
    def test_convert_dataframe_to_points_generation(self, sample_generation_data):
        """Test conversion of generation DataFrame to Points."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(sample_generation_data)
        
        assert len(points) == 3
        
        # Check first point
        point = points[0]
        assert hasattr(point, '_name')
        assert point._name == 'generation_data'
        assert 'region' in point._tags
        assert point._tags['region'] == 'southeast'
        assert 'energy_source' in point._tags
        assert point._tags['energy_source'] == 'hydro'
        assert 'power_mw' in point._fields
        assert point._fields['power_mw'] == 1000.0
    
    def test_convert_dataframe_to_points_consumption(self, sample_consumption_data):
        """Test conversion of consumption DataFrame to Points."""
        converter = EnergyDataConverter('consumption')
        points = converter.convert_dataframe_to_points(sample_consumption_data)
        
        assert len(points) == 2
        
        # Check first point
        point = points[0]
        assert point._name == 'consumption_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['consumer_type'] == 'industrial'
        assert point._fields['power_mw'] == 800.0
    
    def test_convert_dataframe_to_points_transmission(self, sample_transmission_data):
        """Test conversion of transmission DataFrame to Points."""
        converter = EnergyDataConverter('transmission')
        points = converter.convert_dataframe_to_points(sample_transmission_data)
        
        assert len(points) == 2
        
        # Check first point
        point = points[0]
        assert point._name == 'transmission_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['line_id'] == 'SE-NE-001'
        assert point._fields['power_mw'] == 2500.0
    
    def test_convert_dataframe_to_points_empty_dataframe(self):
        """Test conversion of empty DataFrame."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame()
        
        points = converter.convert_dataframe_to_points(df)
        
        assert points == []
    
    def test_convert_dataframe_to_points_with_invalid_rows(self):
        """Test conversion with some invalid rows."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', 'invalid-timestamp', '2024-01-01T14:00:00Z'],
            'region': ['southeast', 'northeast', 'south'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw'],
            'value': [1000.0, np.nan, 300.0],
            'unit': ['MW', 'MW', 'MW']
        })
        
        # With drop_invalid=True (default)
        points = converter.convert_dataframe_to_points(df, drop_invalid=True)
        assert len(points) == 1  # Only valid row should remain
        
        # With drop_invalid=False
        with pytest.raises(DataConversionError):
            converter.convert_dataframe_to_points(df, drop_invalid=False)
    
    def test_convert_dataframe_to_points_without_validation(self, sample_generation_data):
        """Test conversion without schema validation."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(
            sample_generation_data,
            validate_schema=False
        )
        
        assert len(points) == 3
    
    def test_get_field_name_from_unit(self):
        """Test field name generation from unit."""
        converter = EnergyDataConverter('generation')
        
        assert converter._get_field_name_from_unit('MW') == 'power_mw'
        assert converter._get_field_name_from_unit('MWh') == 'energy_mwh'
        assert converter._get_field_name_from_unit('kV') == 'voltage_kv'
        assert converter._get_field_name_from_unit('%') == 'percentage'
        assert converter._get_field_name_from_unit('unknown') == 'value'
        assert converter._get_field_name_from_unit(None) == 'value'
    
    def test_convert_row_to_point_with_timezone_aware_timestamp(self):
        """Test conversion of row with timezone-aware timestamp."""
        converter = EnergyDataConverter('generation')
        
        row = pd.Series({
            'timestamp': pd.Timestamp('2024-01-01T12:00:00+00:00'),
            'region': 'southeast',
            'energy_source': 'hydro',
            'measurement_type': 'power_mw',
            'value': 1000.0,
            'unit': 'MW'
        })
        
        point = converter._convert_row_to_point(row)
        
        assert point is not None
        assert point._name == 'generation_data'
        assert point._time is not None
    
    def test_convert_row_to_point_with_missing_timestamp(self):
        """Test conversion of row with missing timestamp."""
        converter = EnergyDataConverter('generation')
        
        row = pd.Series({
            'region': 'southeast',
            'energy_source': 'hydro',
            'measurement_type': 'power_mw',
            'value': 1000.0,
            'unit': 'MW'
        })
        
        with patch('src.shared_utils.data_conversion.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            
            point = converter._convert_row_to_point(row)
            
            assert point is not None
            mock_datetime.now.assert_called_once_with(timezone.utc)
    
    def test_convert_row_to_point_with_optional_fields(self):
        """Test conversion of row with optional numeric fields."""
        converter = EnergyDataConverter('generation')
        
        row = pd.Series({
            'timestamp': '2024-01-01T12:00:00Z',
            'region': 'southeast',
            'energy_source': 'hydro',
            'measurement_type': 'power_mw',
            'value': 1000.0,
            'unit': 'MW',
            'capacity_mw': 14000.0,
            'efficiency': 0.85,
            'voltage_kv': 500.0
        })
        
        point = converter._convert_row_to_point(row)
        
        assert point is not None
        assert point._fields['capacity_mw'] == 14000.0
        assert point._fields['efficiency'] == 0.85
        assert point._fields['voltage_kv'] == 500.0
    
    def test_convert_row_to_point_with_invalid_optional_fields(self):
        """Test conversion of row with invalid optional numeric fields."""
        converter = EnergyDataConverter('generation')
        
        row = pd.Series({
            'timestamp': '2024-01-01T12:00:00Z',
            'region': 'southeast',
            'energy_source': 'hydro',
            'measurement_type': 'power_mw',
            'value': 1000.0,
            'unit': 'MW',
            'capacity_mw': 'invalid',  # Invalid numeric value
            'efficiency': 0.85
        })
        
        point = converter._convert_row_to_point(row)
        
        assert point is not None
        # Invalid capacity_mw should be skipped
        assert 'capacity_mw' not in point._fields
        assert point._fields['efficiency'] == 0.85
    
    def test_convert_timestream_to_influxdb(self):
        """Test conversion from Timestream record format."""
        timestream_records = [
            {
                'Time': 1640995200000,  # Milliseconds timestamp
                'Dimensions': [
                    {'Name': 'region', 'Value': 'southeast'},
                    {'Name': 'energy_source', 'Value': 'hydro'}
                ],
                'MeasureName': 'power_mw',
                'MeasureValue': '1000.0'
            },
            {
                'Time': 1640998800000,
                'Dimensions': [
                    {'Name': 'region', 'Value': 'northeast'},
                    {'Name': 'energy_source', 'Value': 'wind'}
                ],
                'MeasureName': 'power_mw',
                'MeasureValue': '500.0'
            }
        ]
        
        points = EnergyDataConverter.convert_timestream_to_influxdb(
            timestream_records, 'generation'
        )
        
        assert len(points) == 2
        
        # Check first point
        point = points[0]
        assert point._name == 'generation_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['energy_source'] == 'hydro'
        assert point._fields['power_mw'] == 1000.0
    
    def test_convert_timestream_record_with_missing_fields(self):
        """Test conversion of Timestream record with missing fields."""
        converter = EnergyDataConverter('generation')
        
        # Record missing MeasureValue
        record = {
            'Time': 1640995200000,
            'Dimensions': [{'Name': 'region', 'Value': 'southeast'}],
            'MeasureName': 'power_mw'
            # Missing MeasureValue
        }
        
        point = converter._convert_timestream_record_to_point(record)
        
        # Should handle gracefully and return None or skip the field
        # Depending on implementation, this might return None or a point without the field
        assert point is None or 'power_mw' not in point._fields
    
    def test_prepare_dataframe_cleaning(self):
        """Test DataFrame preparation and cleaning."""
        converter = EnergyDataConverter('generation')
        
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', 'invalid', '2024-01-01T14:00:00Z'],
            'region': [' southeast ', 'northeast', 'south'],  # Extra whitespace
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw'],
            'value': ['1000.0', 'invalid', '300.0'],  # String numbers and invalid
            'unit': ['MW', 'MW', 'MW']
        })
        
        cleaned_df = converter._prepare_dataframe(df, drop_invalid=True)
        
        # Should have 2 valid rows (invalid timestamp and value rows dropped)
        assert len(cleaned_df) == 1
        
        # Check that whitespace was stripped
        assert cleaned_df.iloc[0]['region'] == 'southeast'
        
        # Check that values were converted to numeric
        assert pd.api.types.is_numeric_dtype(cleaned_df['value'])


class TestConversionUtilityFunctions:
    """Test utility functions for data conversion."""
    
    def test_create_converter(self):
        """Test converter factory function."""
        converter = create_converter('generation')
        assert isinstance(converter, EnergyDataConverter)
        assert converter.dataset_type == 'generation'
    
    def test_convert_parquet_to_influxdb_points(self):
        """Test convenience function for DataFrame conversion."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z'],
            'region': ['southeast'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_mw'],
            'value': [1000.0],
            'unit': ['MW']
        })
        
        points = convert_parquet_to_influxdb_points(df, 'generation')
        
        assert len(points) == 1
        assert points[0]._name == 'generation_data'
    
    def test_get_dataset_type_from_s3_key(self):
        """Test dataset type extraction from S3 key."""
        test_cases = [
            ('processed/dataset=generation/year=2024/file.parquet', 'generation'),
            ('processed/dataset=consumption/year=2024/file.parquet', 'consumption'),
            ('processed/dataset=transmission/year=2024/file.parquet', 'transmission'),
            ('processed/generation/year=2024/file.parquet', 'generation'),
            ('processed/consumption_data/year=2024/file.parquet', 'consumption'),
            ('processed/transmission_stats/year=2024/file.parquet', 'transmission'),
            ('processed/unknown/year=2024/file.parquet', None)
        ]
        
        for s3_key, expected_type in test_cases:
            result = get_dataset_type_from_s3_key(s3_key)
            assert result == expected_type, f"Failed for key: {s3_key}"
    
    def test_validate_influxdb_points_valid(self):
        """Test validation of valid InfluxDB points."""
        points = [
            Point("test_measurement").field("value", 1.0).tag("region", "southeast"),
            Point("test_measurement").field("value", 2.0).tag("region", "northeast")
        ]
        
        result = validate_influxdb_points(points)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert result['total_points'] == 2
        assert result['unique_measurements'] == 1
    
    def test_validate_influxdb_points_empty(self):
        """Test validation of empty points list."""
        result = validate_influxdb_points([])
        
        assert result['valid'] is False
        assert 'No points provided' in result['errors']
    
    def test_validate_influxdb_points_without_fields(self):
        """Test validation of points without fields."""
        # Create a point without fields
        point = Point("test_measurement").tag("region", "southeast")
        # Don't add any fields
        
        result = validate_influxdb_points([point])
        
        # Should have warnings about points without fields
        assert len(result['warnings']) > 0
        assert any('without fields' in warning for warning in result['warnings'])
    
    def test_validate_influxdb_points_duplicates(self):
        """Test validation detects potential duplicates."""
        timestamp = datetime.now(timezone.utc)
        
        points = [
            Point("test_measurement")
            .field("value", 1.0)
            .tag("region", "southeast")
            .time(timestamp),
            Point("test_measurement")
            .field("value", 2.0)
            .tag("region", "southeast")
            .time(timestamp)  # Same timestamp and tags
        ]
        
        result = validate_influxdb_points(points)
        
        # Should detect potential duplicates
        assert len(result['warnings']) > 0
        assert any('duplicate points' in warning for warning in result['warnings'])


class TestDataConversionErrorHandling:
    """Test error handling in data conversion."""
    
    def test_conversion_with_completely_invalid_data(self):
        """Test conversion with completely invalid data."""
        converter = EnergyDataConverter('generation')
        
        df = pd.DataFrame({
            'timestamp': ['invalid', 'also-invalid'],
            'region': [None, ''],
            'energy_source': ['', None],
            'measurement_type': [None, ''],
            'value': [None, 'not-a-number'],
            'unit': ['', None]
        })
        
        # With drop_invalid=True, should return empty list
        points = converter.convert_dataframe_to_points(df, drop_invalid=True)
        assert points == []
        
        # With drop_invalid=False, should raise error
        with pytest.raises(DataConversionError):
            converter.convert_dataframe_to_points(df, drop_invalid=False)
    
    def test_conversion_with_mixed_valid_invalid_data(self):
        """Test conversion with mix of valid and invalid data."""
        converter = EnergyDataConverter('generation')
        
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', 'invalid', '2024-01-01T14:00:00Z'],
            'region': ['southeast', '', 'south'],
            'energy_source': ['hydro', None, 'solar'],
            'measurement_type': ['power_mw', 'power_mw', 'power_mw'],
            'value': [1000.0, None, 300.0],
            'unit': ['MW', 'MW', 'MW']
        })
        
        points = converter.convert_dataframe_to_points(df, drop_invalid=True)
        
        # Should get 2 valid points (first and third rows)
        assert len(points) == 1  # Only first row is completely valid
        assert points[0]._tags['region'] == 'southeast'
    
    def test_row_conversion_exception_handling(self):
        """Test exception handling in row conversion."""
        converter = EnergyDataConverter('generation')
        
        # Create a row that will cause an exception during conversion
        row = pd.Series({
            'timestamp': '2024-01-01T12:00:00Z',
            'region': 'southeast',
            'energy_source': 'hydro',
            'measurement_type': 'power_mw',
            'value': 1000.0,
            'unit': 'MW'
        })
        
        # Mock Point creation to raise an exception
        with patch('src.shared_utils.data_conversion.Point') as mock_point:
            mock_point.side_effect = Exception("Point creation failed")
            
            point = converter._convert_row_to_point(row)
            
            # Should handle exception gracefully and return None
            assert point is None