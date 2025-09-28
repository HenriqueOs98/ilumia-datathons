"""
Data conversion utilities for InfluxDB line protocol.

This module provides functions to convert Parquet data structures to InfluxDB
Point objects with proper tag and field mapping based on energy data schema.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from influxdb_client import Point, WritePrecision

logger = logging.getLogger(__name__)


class DataConversionError(Exception):
    """Raised when data conversion fails."""
    pass


class EnergyDataConverter:
    """
    Converter for energy data from Parquet format to InfluxDB line protocol.
    
    Handles conversion of ONS energy data including generation, consumption,
    and transmission datasets with proper tag and field mapping.
    """
    
    # Measurement mappings for different dataset types
    MEASUREMENT_MAPPINGS = {
        'generation': {
            'measurement_name': 'generation_data',
            'required_columns': ['timestamp', 'region', 'value', 'unit', 'energy_source', 'measurement_type'],
            'tag_columns': ['region', 'energy_source', 'measurement_type', 'quality_flag'],
            'field_columns': ['value'],
            'optional_columns': ['plant_name', 'operator', 'capacity_mw', 'efficiency']
        },
        'consumption': {
            'measurement_name': 'consumption_data',
            'required_columns': ['timestamp', 'region', 'value', 'unit', 'consumer_type', 'measurement_type'],
            'tag_columns': ['region', 'consumer_type', 'measurement_type', 'quality_flag'],
            'field_columns': ['value'],
            'optional_columns': ['sector', 'subsector', 'tariff_type']
        },
        'transmission': {
            'measurement_name': 'transmission_data',
            'required_columns': ['timestamp', 'region', 'value', 'unit', 'line_id', 'measurement_type'],
            'tag_columns': ['region', 'line_id', 'measurement_type', 'quality_flag'],
            'field_columns': ['value'],
            'optional_columns': ['voltage_kv', 'line_type', 'operator']
        }
    }
    
    # Unit mappings for field names
    UNIT_FIELD_MAPPINGS = {
        'MW': 'power_mw',
        'MWh': 'energy_mwh',
        'kV': 'voltage_kv',
        'A': 'current_a',
        'Hz': 'frequency_hz',
        '%': 'percentage',
        'ratio': 'ratio'
    }
    
    def __init__(self, dataset_type: str):
        """
        Initialize converter for specific dataset type.
        
        Args:
            dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
            
        Raises:
            ValueError: If dataset_type is not supported
        """
        if dataset_type not in self.MEASUREMENT_MAPPINGS:
            raise ValueError(f"Unsupported dataset type: {dataset_type}")
        
        self.dataset_type = dataset_type
        self.config = self.MEASUREMENT_MAPPINGS[dataset_type]
        
        logger.info(f"Initialized converter for dataset type: {dataset_type}")
    
    def convert_dataframe_to_points(
        self,
        df: pd.DataFrame,
        validate_schema: bool = True,
        drop_invalid: bool = True
    ) -> List[Point]:
        """
        Convert pandas DataFrame to InfluxDB Point objects.
        
        Args:
            df: Input DataFrame with energy data
            validate_schema: Whether to validate DataFrame schema
            drop_invalid: Whether to drop invalid rows or raise error
            
        Returns:
            List of InfluxDB Point objects
            
        Raises:
            DataConversionError: If conversion fails
        """
        if df.empty:
            logger.warning("Empty DataFrame provided for conversion")
            return []
        
        try:
            # Validate schema if requested
            if validate_schema:
                validation_result = self.validate_dataframe_schema(df)
                if not validation_result['valid']:
                    if drop_invalid:
                        logger.warning(f"Schema validation failed: {validation_result['errors']}")
                    else:
                        raise DataConversionError(f"Schema validation failed: {validation_result['errors']}")
            
            # Clean and prepare data
            df_clean = self._prepare_dataframe(df, drop_invalid)
            
            if df_clean.empty:
                logger.warning("No valid data remaining after cleaning")
                return []
            
            # Convert to Points
            points = []
            for idx, row in df_clean.iterrows():
                try:
                    point = self._convert_row_to_point(row)
                    if point:
                        points.append(point)
                except Exception as e:
                    if drop_invalid:
                        logger.warning(f"Failed to convert row {idx}: {e}")
                        continue
                    else:
                        raise DataConversionError(f"Failed to convert row {idx}: {e}")
            
            logger.info(f"Successfully converted {len(points)} points from {len(df)} rows")
            return points
            
        except Exception as e:
            logger.error(f"Error converting DataFrame to Points: {e}")
            raise DataConversionError(f"Conversion failed: {e}")
    
    def validate_dataframe_schema(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate DataFrame schema for InfluxDB conversion.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        # Check required columns
        missing_columns = [col for col in self.config['required_columns'] if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
        
        # Validate timestamp column
        if 'timestamp' in df.columns:
            try:
                # Try to convert timestamps
                pd.to_datetime(df['timestamp'].iloc[0] if not df.empty else None)
            except Exception as e:
                errors.append(f"Invalid timestamp format: {e}")
        
        # Validate numeric value column
        if 'value' in df.columns:
            if not pd.api.types.is_numeric_dtype(df['value']):
                # Try to convert to numeric
                try:
                    pd.to_numeric(df['value'], errors='coerce')
                    warnings.append("Value column converted to numeric, some values may be NaN")
                except Exception:
                    errors.append("Value column cannot be converted to numeric")
        
        # Check for completely empty required columns
        for col in self.config['required_columns']:
            if col in df.columns and df[col].isna().all():
                errors.append(f"Required column '{col}' is completely empty")
        
        # Validate unit column values
        if 'unit' in df.columns:
            invalid_units = df[~df['unit'].isin(self.UNIT_FIELD_MAPPINGS.keys())]['unit'].unique()
            if len(invalid_units) > 0:
                warnings.append(f"Unknown units found: {invalid_units.tolist()}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _prepare_dataframe(self, df: pd.DataFrame, drop_invalid: bool = True) -> pd.DataFrame:
        """
        Clean and prepare DataFrame for conversion.
        
        Args:
            df: Input DataFrame
            drop_invalid: Whether to drop invalid rows
            
        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()
        
        # Convert timestamp column
        if 'timestamp' in df_clean.columns:
            df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'], errors='coerce')
            
            if drop_invalid:
                # Drop rows with invalid timestamps
                invalid_timestamps = df_clean['timestamp'].isna()
                if invalid_timestamps.any():
                    logger.warning(f"Dropping {invalid_timestamps.sum()} rows with invalid timestamps")
                    df_clean = df_clean[~invalid_timestamps]
        
        # Convert value column to numeric
        if 'value' in df_clean.columns:
            df_clean['value'] = pd.to_numeric(df_clean['value'], errors='coerce')
            
            if drop_invalid:
                # Drop rows with invalid values
                invalid_values = df_clean['value'].isna()
                if invalid_values.any():
                    logger.warning(f"Dropping {invalid_values.sum()} rows with invalid values")
                    df_clean = df_clean[~invalid_values]
        
        # Clean string columns (remove leading/trailing whitespace)
        string_columns = df_clean.select_dtypes(include=['object']).columns
        for col in string_columns:
            if col != 'timestamp':  # Skip timestamp column
                df_clean[col] = df_clean[col].astype(str).str.strip()
        
        # Drop rows where all required columns are NaN
        if drop_invalid:
            required_cols_present = [col for col in self.config['required_columns'] if col in df_clean.columns]
            if required_cols_present:
                all_nan_mask = df_clean[required_cols_present].isna().all(axis=1)
                if all_nan_mask.any():
                    logger.warning(f"Dropping {all_nan_mask.sum()} rows with all required columns NaN")
                    df_clean = df_clean[~all_nan_mask]
        
        return df_clean
    
    def _convert_row_to_point(self, row: pd.Series) -> Optional[Point]:
        """
        Convert a single DataFrame row to InfluxDB Point.
        
        Args:
            row: DataFrame row as Series
            
        Returns:
            InfluxDB Point object or None if conversion fails
        """
        try:
            # Create Point with measurement name
            point = Point(self.config['measurement_name'])
            
            # Add timestamp
            if 'timestamp' in row and pd.notna(row['timestamp']):
                timestamp = pd.Timestamp(row['timestamp'])
                if timestamp.tz is None:
                    timestamp = timestamp.tz_localize('UTC')
                point = point.time(timestamp, WritePrecision.NS)
            else:
                # Use current time if timestamp is missing
                point = point.time(datetime.now(timezone.utc), WritePrecision.NS)
            
            # Add tags
            for tag_col in self.config['tag_columns']:
                if tag_col in row and pd.notna(row[tag_col]):
                    # Convert to string and clean
                    tag_value = str(row[tag_col]).strip()
                    if tag_value and tag_value.lower() not in ['nan', 'none', 'null', '']:
                        point = point.tag(tag_col, tag_value)
            
            # Add optional tag columns
            for opt_col in self.config.get('optional_columns', []):
                if opt_col in row and pd.notna(row[opt_col]):
                    tag_value = str(row[opt_col]).strip()
                    if tag_value and tag_value.lower() not in ['nan', 'none', 'null', '']:
                        point = point.tag(opt_col, tag_value)
            
            # Add fields
            # Primary value field with unit-based naming
            if 'value' in row and pd.notna(row['value']):
                field_name = self._get_field_name_from_unit(row.get('unit', 'value'))
                point = point.field(field_name, float(row['value']))
            
            # Add unit as a field for reference
            if 'unit' in row and pd.notna(row['unit']):
                point = point.field('unit', str(row['unit']))
            
            # Add additional numeric fields
            numeric_fields = ['capacity_mw', 'efficiency', 'voltage_kv', 'current_a', 'frequency_hz']
            for field_col in numeric_fields:
                if field_col in row and pd.notna(row[field_col]):
                    try:
                        field_value = float(row[field_col])
                        point = point.field(field_col, field_value)
                    except (ValueError, TypeError):
                        logger.debug(f"Could not convert {field_col} to float: {row[field_col]}")
            
            return point
            
        except Exception as e:
            logger.error(f"Error converting row to Point: {e}")
            return None
    
    def _get_field_name_from_unit(self, unit: str) -> str:
        """
        Get appropriate field name based on unit.
        
        Args:
            unit: Unit string
            
        Returns:
            Field name for the measurement
        """
        if pd.isna(unit) or not unit:
            return 'value'
        
        unit_str = str(unit).strip()
        return self.UNIT_FIELD_MAPPINGS.get(unit_str, 'value')
    
    @classmethod
    def convert_timestream_to_influxdb(
        cls,
        timestream_records: List[Dict[str, Any]],
        dataset_type: str
    ) -> List[Point]:
        """
        Convert Timestream record format to InfluxDB Points.
        
        This is useful for migrating existing Timestream data.
        
        Args:
            timestream_records: List of Timestream record dictionaries
            dataset_type: Type of dataset
            
        Returns:
            List of InfluxDB Point objects
        """
        converter = cls(dataset_type)
        points = []
        
        for record in timestream_records:
            try:
                point = converter._convert_timestream_record_to_point(record)
                if point:
                    points.append(point)
            except Exception as e:
                logger.warning(f"Failed to convert Timestream record: {e}")
                continue
        
        logger.info(f"Converted {len(points)} Timestream records to InfluxDB points")
        return points
    
    def _convert_timestream_record_to_point(self, record: Dict[str, Any]) -> Optional[Point]:
        """
        Convert single Timestream record to InfluxDB Point.
        
        Args:
            record: Timestream record dictionary
            
        Returns:
            InfluxDB Point object or None if conversion fails
        """
        try:
            point = Point(self.config['measurement_name'])
            
            # Add timestamp
            if 'Time' in record:
                # Timestream time is in milliseconds
                timestamp = datetime.fromtimestamp(int(record['Time']) / 1000, tz=timezone.utc)
                point = point.time(timestamp, WritePrecision.NS)
            
            # Add dimensions as tags
            if 'Dimensions' in record:
                for dim in record['Dimensions']:
                    tag_name = dim['Name']
                    tag_value = dim['Value']
                    if tag_value and str(tag_value).strip():
                        point = point.tag(tag_name, str(tag_value))
            
            # Add measure as field
            if 'MeasureValue' in record and 'MeasureName' in record:
                field_name = record['MeasureName']
                field_value = float(record['MeasureValue'])
                point = point.field(field_name, field_value)
            
            return point
            
        except Exception as e:
            logger.error(f"Error converting Timestream record to Point: {e}")
            return None


def create_converter(dataset_type: str) -> EnergyDataConverter:
    """
    Factory function to create data converter for specific dataset type.
    
    Args:
        dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
        
    Returns:
        EnergyDataConverter instance
    """
    return EnergyDataConverter(dataset_type)


def convert_parquet_to_influxdb_points(
    df: pd.DataFrame,
    dataset_type: str,
    validate_schema: bool = True,
    drop_invalid: bool = True
) -> List[Point]:
    """
    Convenience function to convert Parquet DataFrame to InfluxDB Points.
    
    Args:
        df: Input DataFrame with energy data
        dataset_type: Type of dataset ('generation', 'consumption', 'transmission')
        validate_schema: Whether to validate DataFrame schema
        drop_invalid: Whether to drop invalid rows or raise error
        
    Returns:
        List of InfluxDB Point objects
        
    Raises:
        DataConversionError: If conversion fails
    """
    converter = create_converter(dataset_type)
    return converter.convert_dataframe_to_points(df, validate_schema, drop_invalid)


def get_dataset_type_from_s3_key(s3_key: str) -> Optional[str]:
    """
    Extract dataset type from S3 object key.
    
    Args:
        s3_key: S3 object key
        
    Returns:
        Dataset type or None if not found
    """
    if 'dataset=generation' in s3_key:
        return 'generation'
    elif 'dataset=consumption' in s3_key:
        return 'consumption'
    elif 'dataset=transmission' in s3_key:
        return 'transmission'
    
    # Try to infer from path structure
    key_lower = s3_key.lower()
    if 'generation' in key_lower:
        return 'generation'
    elif 'consumption' in key_lower:
        return 'consumption'
    elif 'transmission' in key_lower:
        return 'transmission'
    
    return None


def validate_influxdb_points(points: List[Point]) -> Dict[str, Any]:
    """
    Validate list of InfluxDB Points for common issues.
    
    Args:
        points: List of InfluxDB Point objects
        
    Returns:
        Validation results dictionary
    """
    if not points:
        return {
            'valid': False,
            'errors': ['No points provided'],
            'warnings': []
        }
    
    errors = []
    warnings = []
    
    # Check for points without measurements
    points_without_measurement = [i for i, p in enumerate(points) if not hasattr(p, '_name') or not p._name]
    if points_without_measurement:
        errors.append(f"Points without measurement name: {len(points_without_measurement)}")
    
    # Check for points without fields
    points_without_fields = []
    for i, point in enumerate(points):
        if hasattr(point, '_fields') and not point._fields:
            points_without_fields.append(i)
    
    if points_without_fields:
        warnings.append(f"Points without fields: {len(points_without_fields)}")
    
    # Check for duplicate timestamps with same tags
    timestamp_tag_combinations = set()
    duplicates = 0
    
    for point in points:
        if hasattr(point, '_time') and hasattr(point, '_tags'):
            combo = (point._time, tuple(sorted(point._tags.items())) if point._tags else ())
            if combo in timestamp_tag_combinations:
                duplicates += 1
            else:
                timestamp_tag_combinations.add(combo)
    
    if duplicates > 0:
        warnings.append(f"Potential duplicate points (same timestamp and tags): {duplicates}")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'total_points': len(points),
        'unique_measurements': len(set(p._name for p in points if hasattr(p, '_name')))
    }