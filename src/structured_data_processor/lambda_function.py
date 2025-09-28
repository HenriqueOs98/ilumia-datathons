"""
ONS Data Platform - Structured Data Processor Lambda
Processes CSV and XLSX files from ONS, applies data cleaning and validation,
and converts to optimized Parquet format with proper partitioning.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import unquote_plus

import boto3
import pandas as pd
import awswrangler as wr
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', 'ons-data-platform-processed')
FAILED_BUCKET = os.environ.get('FAILED_BUCKET', 'ons-data-platform-failed')

# AWS clients
s3_client = boto3.client('s3')

class DataProcessingError(Exception):
    """Custom exception for data processing errors"""
    pass

class StructuredDataProcessor:
    """Main class for processing structured data files (CSV/XLSX)"""
    
    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls']
        self.required_columns = ['timestamp', 'value']
        self.energy_sources = [
            'hidrica', 'termica', 'eolica', 'solar', 'nuclear', 
            'biomassa', 'gas_natural', 'carvao', 'oleo'
        ]
        self.regions = [
            'norte', 'nordeste', 'sudeste', 'sul', 'centro_oeste'
        ]
    
    def process_file(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Main processing function for structured data files
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Dict with processing results
        """
        try:
            logger.info(f"Processing file: s3://{bucket}/{key}")
            
            # Validate file format
            file_extension = self._get_file_extension(key)
            if file_extension not in self.supported_formats:
                raise DataProcessingError(f"Unsupported file format: {file_extension}")
            
            # Read file from S3
            df = self._read_file_from_s3(bucket, key, file_extension)
            
            # Apply data cleaning and validation
            df_cleaned = self._clean_and_validate_data(df, key)
            
            # Standardize data format
            df_standardized = self._standardize_data(df_cleaned, key)
            
            # Determine dataset type and partitioning
            dataset_info = self._determine_dataset_type(key, df_standardized)
            
            # Save as Parquet with optimal partitioning
            output_location = self._save_as_parquet(df_standardized, dataset_info)
            
            # Generate processing metadata
            metadata = self._generate_metadata(key, df_standardized, output_location)
            
            logger.info(f"Successfully processed {len(df_standardized)} records from {key}")
            
            return {
                'status': 'success',
                'input_file': f"s3://{bucket}/{key}",
                'output_location': output_location,
                'records_processed': len(df_standardized),
                'dataset_type': dataset_info['type'],
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing file {key}: {str(e)}")
            self._move_to_failed_bucket(bucket, key, str(e))
            raise DataProcessingError(f"Failed to process {key}: {str(e)}")
    
    def _get_file_extension(self, key: str) -> str:
        """Extract file extension from S3 key"""
        return os.path.splitext(key.lower())[1]
    
    def _read_file_from_s3(self, bucket: str, key: str, file_extension: str) -> pd.DataFrame:
        """Read CSV or XLSX file from S3 into pandas DataFrame"""
        s3_path = f"s3://{bucket}/{key}"
        
        try:
            if file_extension == '.csv':
                # Try different encodings and separators
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                    for sep in [',', ';', '\t']:
                        try:
                            df = wr.s3.read_csv(
                                path=s3_path,
                                encoding=encoding,
                                sep=sep,
                                low_memory=False
                            )
                            if len(df.columns) > 1:  # Valid CSV found
                                logger.info(f"Successfully read CSV with encoding={encoding}, sep='{sep}'")
                                return df
                        except Exception:
                            continue
                raise DataProcessingError("Could not read CSV with any encoding/separator combination")
                
            elif file_extension in ['.xlsx', '.xls']:
                df = wr.s3.read_excel(
                    path=s3_path,
                    engine='openpyxl' if file_extension == '.xlsx' else 'xlrd'
                )
                return df
                
        except Exception as e:
            raise DataProcessingError(f"Failed to read file from S3: {str(e)}")
    
    def _clean_and_validate_data(self, df: pd.DataFrame, filename: str) -> pd.DataFrame:
        """Apply data cleaning and validation rules"""
        logger.info(f"Cleaning data for {filename}. Initial shape: {df.shape}")
        
        # Make a copy to avoid modifying original
        df_clean = df.copy()
        
        # Remove completely empty rows and columns
        df_clean = df_clean.dropna(how='all').dropna(axis=1, how='all')
        
        # Standardize column names
        df_clean.columns = [self._standardize_column_name(col) for col in df_clean.columns]
        
        # Remove duplicate rows
        initial_rows = len(df_clean)
        df_clean = df_clean.drop_duplicates()
        if len(df_clean) < initial_rows:
            logger.info(f"Removed {initial_rows - len(df_clean)} duplicate rows")
        
        # Handle missing values based on column type
        df_clean = self._handle_missing_values(df_clean)
        
        # Validate data types and convert where possible
        df_clean = self._validate_and_convert_types(df_clean)
        
        # Remove outliers for numeric columns
        df_clean = self._remove_outliers(df_clean)
        
        logger.info(f"Data cleaning completed. Final shape: {df_clean.shape}")
        
        if len(df_clean) == 0:
            raise DataProcessingError("No valid data remaining after cleaning")
        
        return df_clean
    
    def _standardize_column_name(self, col_name: str) -> str:
        """Standardize column names to snake_case"""
        import unicodedata
        
        # Convert to string and strip whitespace
        name = str(col_name).strip()
        
        # Convert to lowercase
        name = name.lower()
        
        # Normalize Unicode characters (remove accents)
        name = unicodedata.normalize('NFD', name)
        name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
        
        # Replace common Portuguese terms
        replacements = {
            'data': 'timestamp',
            'hora': 'time',
            'valor': 'value',
            'quantidade': 'quantity',
            'potencia': 'power',
            'energia': 'energy',
            'regiao': 'region',
            'fonte': 'source',
            'tipo': 'type',
            'unidade': 'unit'
        }
        
        for pt_term, en_term in replacements.items():
            if pt_term in name:
                name = name.replace(pt_term, en_term)
        
        # Replace spaces and special characters with underscores
        name = re.sub(r'[^\w]', '_', name)
        
        # Remove multiple underscores
        name = re.sub(r'_+', '_', name)
        
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        return name
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values based on column characteristics"""
        df_filled = df.copy()
        
        for col in df_filled.columns:
            if df_filled[col].dtype in ['float64', 'int64']:
                # For numeric columns, fill with median
                median_val = df_filled[col].median()
                df_filled[col] = df_filled[col].fillna(median_val)
            elif df_filled[col].dtype == 'object':
                # For text columns, fill with 'unknown' or most frequent value
                if 'region' in col.lower():
                    df_filled[col] = df_filled[col].fillna('unknown')
                elif 'source' in col.lower() or 'type' in col.lower():
                    mode_val = df_filled[col].mode()
                    fill_val = mode_val[0] if len(mode_val) > 0 else 'unknown'
                    df_filled[col] = df_filled[col].fillna(fill_val)
                else:
                    df_filled[col] = df_filled[col].fillna('unknown')
        
        return df_filled
    
    def _validate_and_convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and convert data types"""
        df_converted = df.copy()
        
        for col in df_converted.columns:
            if 'timestamp' in col.lower() or 'data' in col.lower():
                # Convert timestamp columns
                df_converted[col] = pd.to_datetime(df_converted[col], errors='coerce')
            elif 'value' in col.lower() or 'power' in col.lower() or 'energy' in col.lower():
                # Convert numeric value columns
                df_converted[col] = pd.to_numeric(df_converted[col], errors='coerce')
            elif 'region' in col.lower():
                # Standardize region names
                df_converted[col] = df_converted[col].astype(str).str.lower().str.strip()
            elif 'source' in col.lower():
                # Standardize energy source names
                df_converted[col] = df_converted[col].astype(str).str.lower().str.strip()
        
        return df_converted
    
    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove statistical outliers from numeric columns"""
        df_no_outliers = df.copy()
        
        numeric_columns = df_no_outliers.select_dtypes(include=['float64', 'int64']).columns
        
        for col in numeric_columns:
            if 'value' in col.lower() or 'power' in col.lower() or 'energy' in col.lower():
                Q1 = df_no_outliers[col].quantile(0.25)
                Q3 = df_no_outliers[col].quantile(0.75)
                IQR = Q3 - Q1
                
                # Define outlier bounds
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # Remove outliers
                initial_count = len(df_no_outliers)
                df_no_outliers = df_no_outliers[
                    (df_no_outliers[col] >= lower_bound) & 
                    (df_no_outliers[col] <= upper_bound)
                ]
                
                removed_count = initial_count - len(df_no_outliers)
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} outliers from column {col}")
        
        return df_no_outliers
    
    def _standardize_data(self, df: pd.DataFrame, filename: str) -> pd.DataFrame:
        """Standardize data format according to the schema"""
        df_std = df.copy()
        
        # Add processing metadata
        df_std['processing_metadata_processed_at'] = datetime.utcnow()
        df_std['processing_metadata_processor_version'] = '1.0.0'
        df_std['processing_metadata_source_file'] = filename
        
        # Add quality flags
        df_std['quality_flag'] = 'valid'
        
        # Ensure required columns exist
        if 'timestamp' not in df_std.columns:
            # Try to find timestamp column
            timestamp_cols = [col for col in df_std.columns if 'time' in col.lower() or 'data' in col.lower()]
            if timestamp_cols:
                df_std['timestamp'] = df_std[timestamp_cols[0]]
            else:
                # Use current timestamp if no timestamp column found
                df_std['timestamp'] = datetime.utcnow()
        
        # Ensure unit column exists
        if 'unit' not in df_std.columns:
            df_std['unit'] = 'MW'  # Default unit for energy data
        
        return df_std
    
    def _determine_dataset_type(self, filename: str, df: pd.DataFrame) -> Dict[str, str]:
        """Determine dataset type and partitioning strategy based on filename and content"""
        filename_lower = filename.lower()
        
        # Determine dataset type from filename
        if any(term in filename_lower for term in ['geracao', 'generation', 'producao']):
            dataset_type = 'generation'
        elif any(term in filename_lower for term in ['consumo', 'consumption', 'demanda']):
            dataset_type = 'consumption'
        elif any(term in filename_lower for term in ['transmissao', 'transmission', 'rede']):
            dataset_type = 'transmission'
        else:
            dataset_type = 'general'
        
        # Determine time partitioning
        if 'timestamp' in df.columns and not df['timestamp'].isna().all():
            sample_date = df['timestamp'].dropna().iloc[0]
            if pd.notna(sample_date):
                year = str(sample_date.year)
                month = f"{sample_date.month:02d}"
            else:
                year = str(datetime.now().year)
                month = f"{datetime.now().month:02d}"
        else:
            year = str(datetime.now().year)
            month = f"{datetime.now().month:02d}"
        
        return {
            'type': dataset_type,
            'year': year,
            'month': month
        }
    
    def _save_as_parquet(self, df: pd.DataFrame, dataset_info: Dict[str, str]) -> str:
        """Save DataFrame as Parquet with optimal partitioning"""
        
        # Define output path with partitioning
        output_path = (
            f"s3://{PROCESSED_BUCKET}/"
            f"dataset={dataset_info['type']}/"
            f"year={dataset_info['year']}/"
            f"month={dataset_info['month']}/"
        )
        
        try:
            # Write to S3 as Parquet with partitioning
            wr.s3.to_parquet(
                df=df,
                path=output_path,
                dataset=True,
                partition_cols=['processing_metadata_processed_at'],
                compression='snappy',
                use_threads=True,
                boto3_session=boto3.Session()
            )
            
            logger.info(f"Successfully saved Parquet to {output_path}")
            return output_path
            
        except Exception as e:
            raise DataProcessingError(f"Failed to save Parquet file: {str(e)}")
    
    def _generate_metadata(self, filename: str, df: pd.DataFrame, output_location: str) -> Dict[str, Any]:
        """Generate processing metadata"""
        return {
            'source_file': filename,
            'output_location': output_location,
            'records_count': len(df),
            'columns_count': len(df.columns),
            'processing_timestamp': datetime.utcnow().isoformat(),
            'data_quality_score': self._calculate_quality_score(df),
            'column_names': list(df.columns)
        }
    
    def _calculate_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate a simple data quality score based on completeness"""
        total_cells = df.size
        non_null_cells = df.count().sum()
        return round((non_null_cells / total_cells) * 100, 2) if total_cells > 0 else 0.0
    
    def _move_to_failed_bucket(self, bucket: str, key: str, error_message: str):
        """Move failed file to failed bucket with error metadata"""
        try:
            failed_key = f"failed/{datetime.utcnow().strftime('%Y/%m/%d')}/{key}"
            
            # Copy file to failed bucket
            s3_client.copy_object(
                CopySource={'Bucket': bucket, 'Key': key},
                Bucket=FAILED_BUCKET,
                Key=failed_key,
                Metadata={
                    'error_message': error_message,
                    'failed_at': datetime.utcnow().isoformat(),
                    'original_bucket': bucket,
                    'original_key': key
                },
                MetadataDirective='REPLACE'
            )
            
            logger.info(f"Moved failed file to s3://{FAILED_BUCKET}/{failed_key}")
            
        except Exception as e:
            logger.error(f"Failed to move file to failed bucket: {str(e)}")


def lambda_handler(event, context):
    """
    AWS Lambda handler for structured data processing
    
    Expected event format:
    {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket-name"},
                    "object": {"key": "file-key"}
                }
            }
        ]
    }
    """
    
    processor = StructuredDataProcessor()
    results = []
    
    try:
        # Handle both S3 events and direct invocation
        if 'Records' in event:
            # S3 event format
            for record in event['Records']:
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
                
                result = processor.process_file(bucket, key)
                results.append(result)
        else:
            # Direct invocation format
            bucket = event.get('bucket')
            key = event.get('key')
            
            if not bucket or not key:
                raise ValueError("Missing required parameters: bucket and key")
            
            result = processor.process_file(bucket, key)
            results.append(result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing completed successfully',
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Processing failed'
            })
        }