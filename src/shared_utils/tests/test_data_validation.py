"""
Tests for data validation utilities.
"""

import pytest
import pandas as pd
from datetime import datetime

from ..data_validation import DataValidator


class TestDataValidator:
    """Test cases for DataValidator class."""
    
    def test_validate_generation_dataframe_valid(self):
        """Test validation of valid generation DataFrame."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00', '2024-01-01 01:00:00'],
            'region': ['southeast', 'northeast'],
            'energy_source': ['hydro', 'wind'],
            'value': [1000.5, 500.2],
            'unit': ['MW', 'MW']
        })
        
        result = DataValidator.validate_dataframe(df, 'generation')
        
        assert result['is_valid'] is True
        assert result['row_count'] == 2
        assert result['column_count'] == 5
        assert len(result['errors']) == 0
    
    def test_validate_dataframe_missing_columns(self):
        """Test validation with missing required columns."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00'],
            'value': [1000.5]
        })
        
        result = DataValidator.validate_dataframe(df, 'generation')
        
        assert result['is_valid'] is False
        assert 'Missing required columns' in result['errors'][0]
    
    def test_validate_dataframe_empty(self):
        """Test validation of empty DataFrame."""
        df = pd.DataFrame()
        
        result = DataValidator.validate_dataframe(df, 'generation')
        
        assert result['is_valid'] is False
        assert 'DataFrame is empty' in result['errors'][0]
    
    def test_clean_dataframe(self):
        """Test DataFrame cleaning functionality."""
        df = pd.DataFrame({
            'timestamp': ['2024-01-01 00:00:00', '2024-01-01 01:00:00'],
            'region': [' Southeast ', ' NORTHEAST '],
            'energy_source': ['HYDRO', 'wind'],
            'value': ['1000.5', '500.2'],
            'unit': ['MW', 'MW']
        })
        
        cleaned_df = DataValidator.clean_dataframe(df, 'generation')
        
        assert cleaned_df['region'].iloc[0] == 'southeast'
        assert cleaned_df['region'].iloc[1] == 'northeast'
        assert cleaned_df['energy_source'].iloc[0] == 'hydro'
        assert cleaned_df['value'].dtype == 'float64'
        assert 'processed_at' in cleaned_df.columns
        assert 'dataset_type' in cleaned_df.columns