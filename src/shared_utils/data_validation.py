"""
Data validation utilities for the ONS Data Platform.
"""

import pandas as pd
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataValidator:
    """Data validation utilities for energy data."""
    
    REQUIRED_COLUMNS = {
        'generation': ['timestamp', 'region', 'energy_source', 'value', 'unit'],
        'consumption': ['timestamp', 'region', 'value', 'unit'],
        'transmission': ['timestamp', 'from_region', 'to_region', 'value', 'unit']
    }
    
    VALID_ENERGY_SOURCES = [
        'hydro', 'thermal', 'wind', 'solar', 'nuclear', 'biomass', 'other'
    ]
    
    VALID_UNITS = ['MW', 'MWh', 'GW', 'GWh']
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, dataset_type: str) -> Dict[str, Any]:
        """
        Validate a DataFrame against expected schema.
        
        Args:
            df: DataFrame to validate
            dataset_type: Type of dataset (generation, consumption, transmission)
        
        Returns:
            Validation results dictionary
        """
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'row_count': len(df),
            'column_count': len(df.columns)
        }
        
        # Check if dataset type is supported
        if dataset_type not in DataValidator.REQUIRED_COLUMNS:
            results['is_valid'] = False
            results['errors'].append(f"Unsupported dataset type: {dataset_type}")
            return results
        
        # Check required columns
        required_cols = DataValidator.REQUIRED_COLUMNS[dataset_type]
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            results['is_valid'] = False
            results['errors'].append(f"Missing required columns: {missing_cols}")
        
        # Check for empty DataFrame
        if df.empty:
            results['is_valid'] = False
            results['errors'].append("DataFrame is empty")
            return results
        
        # Validate timestamp column
        if 'timestamp' in df.columns:
            try:
                pd.to_datetime(df['timestamp'])
            except Exception as e:
                results['errors'].append(f"Invalid timestamp format: {str(e)}")
                results['is_valid'] = False
        
        # Validate numeric values
        if 'value' in df.columns:
            non_numeric = df[~pd.to_numeric(df['value'], errors='coerce').notna()]
            if not non_numeric.empty:
                results['warnings'].append(f"Found {len(non_numeric)} non-numeric values")
        
        # Validate energy sources
        if 'energy_source' in df.columns:
            invalid_sources = df[~df['energy_source'].isin(DataValidator.VALID_ENERGY_SOURCES)]
            if not invalid_sources.empty:
                results['warnings'].append(f"Found {len(invalid_sources)} invalid energy sources")
        
        # Validate units
        if 'unit' in df.columns:
            invalid_units = df[~df['unit'].isin(DataValidator.VALID_UNITS)]
            if not invalid_units.empty:
                results['warnings'].append(f"Found {len(invalid_units)} invalid units")
        
        return results
    
    @staticmethod
    def clean_dataframe(df: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
        """
        Clean and standardize DataFrame.
        
        Args:
            df: DataFrame to clean
            dataset_type: Type of dataset
        
        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()
        
        # Convert timestamp to datetime
        if 'timestamp' in df_clean.columns:
            df_clean['timestamp'] = pd.to_datetime(df_clean['timestamp'], errors='coerce')
        
        # Convert value to numeric
        if 'value' in df_clean.columns:
            df_clean['value'] = pd.to_numeric(df_clean['value'], errors='coerce')
        
        # Standardize string columns
        string_columns = ['region', 'energy_source', 'unit', 'from_region', 'to_region']
        for col in string_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).str.strip().str.lower()
        
        # Remove rows with null timestamps or values
        df_clean = df_clean.dropna(subset=['timestamp', 'value'])
        
        # Add processing metadata
        df_clean['processed_at'] = datetime.utcnow()
        df_clean['dataset_type'] = dataset_type
        
        return df_clean