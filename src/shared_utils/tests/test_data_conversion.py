"""
Unit tests for data conversion utilities.

Tests the EnergyDataConverter class and related functions for converting
Parquet data structures to InfluxDB Point objects.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch, Mock

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
            'timestamp': ['2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z', '2024-01-01T14:00:00Z'],
            'region': ['southeast', 'northeast', 'south'],
            'value': [1500.5, 2200.0, 1800.75],
            'unit': ['MW', 'MW', 'MW'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_output', 'power_output', 'power_output'],
            'plant_name': ['Itaipu', 'Wind Farm A', 'Solar Park B'],
            'quality_flag': ['good', 'good', 'estimated']
        })
    
    @pytest.fixture
    def sample_consumption_data(self):
        """Sample consumption dataset for testing."""
        return pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z'],
            'region': ['southeast', 'northeast'],
            'value': [850.2, 920.5],
            'unit': ['MWh', 'MWh'],
            'consumer_type': ['industrial', 'residential'],
            'measurement_type': ['consumption', 'consumption'],
            'sector': ['manufacturing', 'residential']
        })
    
    @pytest.fixture
    def sample_transmission_data(self):
        """Sample transmission dataset for testing."""
        return pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z'],
            'region': ['southeast', 'northeast'],
            'value': [2500.0, 1800.0],
            'unit': ['MW', 'MW'],
            'line_id': ['SE-NE-001', 'NE-N-002'],
            'measurement_type': ['flow', 'flow'],
            'voltage_kv': [500, 345]
        })
    
    def test_init_valid_dataset_type(self):
        """Test initialization with valid dataset types."""
        for dataset_type in ['generation', 'consumption', 'transmission']:
            converter = EnergyDataConverter(dataset_type)
            assert converter.dataset_type == dataset_type
            assert converter.config == EnergyDataConverter.MEASUREMENT_MAPPINGS[dataset_type]
    
    def test_init_invalid_dataset_type(self):
        """Test initialization with invalid dataset type."""
        with pytest.raises(ValueError, match="Unsupported dataset type"):
            EnergyDataConverter('invalid_type')
    
    def test_convert_generation_data(self, sample_generation_data):
        """Test conversion of generation data to InfluxDB points."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(sample_generation_data)
        
        assert len(points) == 3
        
        # Check first point
        point = points[0]
        assert hasattr(point, '_name')
        assert point._name == 'generation_data'
        
        # Check tags
        assert 'region' in point._tags
        assert point._tags['region'] == 'southeast'
        assert point._tags['energy_source'] == 'hydro'
        assert point._tags['measurement_type'] == 'power_output'
        assert point._tags['quality_flag'] == 'good'
        assert point._tags['plant_name'] == 'Itaipu'
        
        # Check fields
        assert 'power_mw' in point._fields
        assert point._fields['power_mw'] == 1500.5
        assert point._fields['unit'] == 'MW'
    
    def test_convert_consumption_data(self, sample_consumption_data):
        """Test conversion of consumption data to InfluxDB points."""
        converter = EnergyDataConverter('consumption')
        points = converter.convert_dataframe_to_points(sample_consumption_data)
        
        assert len(points) == 2
        
        point = points[0]
        assert point._name == 'consumption_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['consumer_type'] == 'industrial'
        assert point._tags['sector'] == 'manufacturing'
        assert point._fields['energy_mwh'] == 850.2
    
    def test_convert_transmission_data(self, sample_transmission_data):
        """Test conversion of transmission data to InfluxDB points."""
        converter = EnergyDataConverter('transmission')
        points = converter.convert_dataframe_to_points(sample_transmission_data)
        
        assert len(points) == 2
        
        point = points[0]
        assert point._name == 'transmission_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['line_id'] == 'SE-NE-001'
        assert point._fields['power_mw'] == 2500.0
        assert point._fields['voltage_kv'] == 500
    
    def test_convert_empty_dataframe(self):
        """Test conversion of empty DataFrame."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(pd.DataFrame())
        
        assert points == []
    
    def test_validate_schema_valid_data(self, sample_generation_data):
        """Test schema validation with valid data."""
        converter = EnergyDataConverter('generation')
        result = converter.validate_dataframe_schema(sample_generation_data)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_schema_missing_columns(self):
        """Test schema validation with missing required columns."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z'],
            'region': ['southeast'],
            # Missing 'value', 'unit', 'energy_source', 'measurement_type'
        })
        
        result = converter.validate_dataframe_schema(df)
        
        assert result['valid'] is False
        assert 'Missing required columns' in result['errors'][0]
    
    def test_validate_schema_invalid_timestamp(self):
        """Test schema validation with invalid timestamp."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['invalid-timestamp'],
            'region': ['southeast'],
            'value': [1500.0],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_output']
        })
        
        result = converter.validate_dataframe_schema(df)
        
        assert result['valid'] is False
        assert 'Invalid timestamp format' in result['errors'][0]
    
    def test_validate_schema_non_numeric_value(self):
        """Test schema validation with non-numeric value column."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z'],
            'region': ['southeast'],
            'value': ['not-a-number'],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_output']
        })
        
        result = converter.validate_dataframe_schema(df)
        
        # Should have warnings about conversion, not errors
        assert len(result['warnings']) > 0
    
    def test_prepare_dataframe_timestamp_conversion(self):
        """Test DataFrame preparation with timestamp conversion."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', 'invalid-timestamp', '2024-01-01T14:00:00Z'],
            'region': ['southeast', 'northeast', 'south'],
            'value': [1500.0, 2200.0, 1800.0],
            'unit': ['MW', 'MW', 'MW'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_output', 'power_output', 'power_output']
        })
        
        df_clean = converter._prepare_dataframe(df, drop_invalid=True)
        
        # Should drop the row with invalid timestamp
        assert len(df_clean) == 2
        assert df_clean['timestamp'].notna().all()
    
    def test_prepare_dataframe_value_conversion(self):
        """Test DataFrame preparation with value conversion."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z', '2024-01-01T14:00:00Z'],
            'region': ['southeast', 'northeast', 'south'],
            'value': [1500.0, 'invalid', 1800.0],
            'unit': ['MW', 'MW', 'MW'],
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_output', 'power_output', 'power_output']
        })
        
        df_clean = converter._prepare_dataframe(df, drop_invalid=True)
        
        # Should drop the row with invalid value
        assert len(df_clean) == 2
        assert df_clean['value'].notna().all()
    
    def test_convert_row_to_point_basic(self):
        """Test conversion of single row to Point."""
        converter = EnergyDataConverter('generation')
        row = pd.Series({
            'timestamp': '2024-01-01T12:00:00Z',
            'region': 'southeast',
            'value': 1500.5,
            'unit': 'MW',
            'energy_source': 'hydro',
            'measurement_type': 'power_output'
        })
        
        point = converter._convert_row_to_point(row)
        
        assert point is not None
        assert point._name == 'generation_data'
        assert point._tags['region'] == 'southeast'
        assert point._fields['power_mw'] == 1500.5
    
    def test_convert_row_to_point_missing_timestamp(self):
        """Test conversion of row without timestamp uses current time."""
        converter = EnergyDataConverter('generation')
        row = pd.Series({
            'region': 'southeast',
            'value': 1500.5,
            'unit': 'MW',
            'energy_source': 'hydro',
            'measurement_type': 'power_output'
        })
        
        point = converter._convert_row_to_point(row)
        
        assert point is not None
        assert hasattr(point, '_time')
        assert point._time is not None
    
    def test_get_field_name_from_unit(self):
        """Test field name generation from unit."""
        converter = EnergyDataConverter('generation')
        
        assert converter._get_field_name_from_unit('MW') == 'power_mw'
        assert converter._get_field_name_from_unit('MWh') == 'energy_mwh'
        assert converter._get_field_name_from_unit('kV') == 'voltage_kv'
        assert converter._get_field_name_from_unit('unknown') == 'value'
        assert converter._get_field_name_from_unit(None) == 'value'
    
    def test_convert_with_validation_disabled(self, sample_generation_data):
        """Test conversion with schema validation disabled."""
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(sample_generation_data, validate_schema=False)
        
        assert len(points) == 3
    
    def test_convert_with_drop_invalid_disabled(self):
        """Test conversion with drop_invalid disabled raises error on invalid data."""
        converter = EnergyDataConverter('generation')
        df = pd.DataFrame({
            'timestamp': ['invalid-timestamp'],
            'region': ['southeast'],
            'value': ['not-a-number'],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_output']
        })
        
        with pytest.raises(DataConversionError):
            converter.convert_dataframe_to_points(df, drop_invalid=False)
    
    def test_convert_timestream_to_influxdb(self):
        """Test conversion from Timestream record format."""
        timestream_records = [
            {
                'Time': '1640995200000',  # 2022-01-01 00:00:00 UTC in milliseconds
                'Dimensions': [
                    {'Name': 'region', 'Value': 'southeast'},
                    {'Name': 'energy_source', 'Value': 'hydro'}
                ],
                'MeasureName': 'power_mw',
                'MeasureValue': '1500.5'
            }
        ]
        
        points = EnergyDataConverter.convert_timestream_to_influxdb(timestream_records, 'generation')
        
        assert len(points) == 1
        point = points[0]
        assert point._name == 'generation_data'
        assert point._tags['region'] == 'southeast'
        assert point._tags['energy_source'] == 'hydro'
        assert point._fields['power_mw'] == 1500.5
    
    def test_convert_timestream_record_invalid(self):
        """Test conversion of invalid Timestream record."""
        converter = EnergyDataConverter('generation')
        invalid_record = {'invalid': 'data'}
        
        point = converter._convert_timestream_record_to_point(invalid_record)
        
        # Should return None for invalid record
        assert point is None


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
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
            'value': [1500.0],
            'unit': ['MW'],
            'energy_source': ['hydro'],
            'measurement_type': ['power_output']
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
            ('data/generation/2024/file.parquet', 'generation'),
            ('data/consumption_data/file.parquet', 'consumption'),
            ('transmission_stats/file.parquet', 'transmission'),
            ('unknown/path/file.parquet', None)
        ]
        
        for s3_key, expected in test_cases:
            result = get_dataset_type_from_s3_key(s3_key)
            assert result == expected, f"Failed for key: {s3_key}"
    
    def test_validate_influxdb_points_empty(self):
        """Test validation of empty points list."""
        result = validate_influxdb_points([])
        
        assert result['valid'] is False
        assert 'No points provided' in result['errors']
    
    def test_validate_influxdb_points_valid(self):
        """Test validation of valid points."""
        points = [
            Point('test_measurement').tag('region', 'southeast').field('value', 1.0),
            Point('test_measurement').tag('region', 'northeast').field('value', 2.0)
        ]
        
        result = validate_influxdb_points(points)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert result['total_points'] == 2
    
    def test_validate_influxdb_points_without_fields(self):
        """Test validation of points without fields."""
        # Create point without fields
        point = Point('test_measurement').tag('region', 'southeast')
        # Don't add any fields
        
        result = validate_influxdb_points([point])
        
        # Should have warnings about missing fields
        assert len(result['warnings']) > 0
        assert 'without fields' in result['warnings'][0]


class TestDataConversionIntegration:
    """Integration tests for data conversion workflow."""
    
    def test_full_conversion_workflow_generation(self):
        """Test complete conversion workflow for generation data."""
        # Create realistic generation data
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01T00:00:00Z', periods=24, freq='H'),
            'region': ['southeast'] * 24,
            'value': np.random.uniform(1000, 2000, 24),
            'unit': ['MW'] * 24,
            'energy_source': ['hydro'] * 12 + ['wind'] * 12,
            'measurement_type': ['power_output'] * 24,
            'plant_name': ['Plant A'] * 12 + ['Plant B'] * 12,
            'quality_flag': ['good'] * 20 + ['estimated'] * 4
        })
        
        # Convert to InfluxDB points
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(df)
        
        # Validate results
        assert len(points) == 24
        
        # Check that all points have required components
        for point in points:
            assert point._name == 'generation_data'
            assert 'region' in point._tags
            assert 'energy_source' in point._tags
            assert 'power_mw' in point._fields
            assert hasattr(point, '_time')
        
        # Validate the points
        validation = validate_influxdb_points(points)
        assert validation['valid'] is True
    
    def test_conversion_with_missing_data(self):
        """Test conversion handling missing/NaN data appropriately."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01T12:00:00Z', '2024-01-01T13:00:00Z', '2024-01-01T14:00:00Z'],
            'region': ['southeast', None, 'south'],  # Missing region
            'value': [1500.0, np.nan, 1800.0],  # Missing value
            'unit': ['MW', 'MW', None],  # Missing unit
            'energy_source': ['hydro', 'wind', 'solar'],
            'measurement_type': ['power_output', 'power_output', 'power_output']
        })
        
        converter = EnergyDataConverter('generation')
        points = converter.convert_dataframe_to_points(df, drop_invalid=True)
        
        # Should only get 1 valid point (first row)
        assert len(points) == 1
        assert points[0]._tags['region'] == 'southeast'
        assert points[0]._fields['power_mw'] == 1500.0
    
    def test_conversion_performance_large_dataset(self):
        """Test conversion performance with larger dataset."""
        # Create large dataset (1000 records)
        n_records = 1000
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01T00:00:00Z', periods=n_records, freq='min'),
            'region': np.random.choice(['southeast', 'northeast', 'south'], n_records),
            'value': np.random.uniform(1000, 3000, n_records),
            'unit': ['MW'] * n_records,
            'energy_source': np.random.choice(['hydro', 'wind', 'solar'], n_records),
            'measurement_type': ['power_output'] * n_records
        })
        
        converter = EnergyDataConverter('generation')
        
        import time
        start_time = time.time()
        points = converter.convert_dataframe_to_points(df)
        conversion_time = time.time() - start_time
        
        assert len(points) == n_records
        assert conversion_time < 5.0  # Should complete within 5 seconds
        
        # Validate a sample of points
        sample_points = points[:10]
        validation = validate_influxdb_points(sample_points)
        assert validation['valid'] is True