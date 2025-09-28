#!/usr/bin/env python3
"""
AWS Batch PDF Processor for ONS Data Platform
Extracts tables from PDF files and converts to standardized Parquet format
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile

import boto3
import pandas as pd
import numpy as np
import camelot
import tabula
import PyPDF2
import pdfplumber
from botocore.exceptions import ClientError, NoCredentialsError

# Add shared utilities to path
sys.path.append('/app')
sys.path.append('/app/src/shared_utils')

try:
    from shared_utils.logging_config import setup_logging
    from shared_utils.s3_utils import S3Utils
    from shared_utils.data_validation import DataValidator
except ImportError:
    # Fallback if shared utils not available
    def setup_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)

class PDFProcessor:
    """Main PDF processing class for extracting tables and standardizing data"""
    
    def __init__(self):
        self.logger = setup_logging() if 'setup_logging' in globals() else logging.getLogger(__name__)
        self.s3_utils = S3Utils() if 'S3Utils' in globals() else None
        self.data_validator = DataValidator() if 'DataValidator' in globals() else None
        
        # AWS clients
        self.s3_client = boto3.client('s3')
        
        # Processing configuration
        self.temp_dir = Path('/tmp/pdf_processing')
        self.output_dir = Path('/tmp/output')
        self.temp_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
    def process_pdf_file(self, input_s3_uri: str, output_s3_uri: str) -> Dict[str, Any]:
        """
        Main processing function for PDF files
        
        Args:
            input_s3_uri: S3 URI of input PDF file
            output_s3_uri: S3 URI for output Parquet file
            
        Returns:
            Processing result dictionary
        """
        try:
            self.logger.info(f"Starting PDF processing: {input_s3_uri}")
            
            # Parse S3 URIs
            input_bucket, input_key = self._parse_s3_uri(input_s3_uri)
            output_bucket, output_key = self._parse_s3_uri(output_s3_uri)
            
            # Download PDF file
            local_pdf_path = self._download_pdf(input_bucket, input_key)
            
            # Extract tables using multiple methods
            tables_data = self._extract_tables_multi_method(local_pdf_path)
            
            if not tables_data:
                raise ValueError("No tables found in PDF file")
            
            # Standardize and validate data
            standardized_data = self._standardize_data(tables_data, input_key)
            
            # Convert to Parquet and upload
            parquet_path = self._save_as_parquet(standardized_data)
            self._upload_to_s3(parquet_path, output_bucket, output_key)
            
            # Cleanup temporary files
            self._cleanup_temp_files([local_pdf_path, parquet_path])
            
            result = {
                'status': 'success',
                'input_file': input_s3_uri,
                'output_file': output_s3_uri,
                'tables_extracted': len(tables_data),
                'rows_processed': len(standardized_data),
                'processing_time': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"PDF processing completed successfully: {result}")
            return result
            
        except Exception as e:
            error_msg = f"PDF processing failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            return {
                'status': 'error',
                'error_message': error_msg,
                'error_type': type(e).__name__,
                'input_file': input_s3_uri,
                'processing_time': datetime.utcnow().isoformat()
            }
    
    def _parse_s3_uri(self, s3_uri: str) -> Tuple[str, str]:
        """Parse S3 URI into bucket and key"""
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        return parts[0], parts[1]
    
    def _download_pdf(self, bucket: str, key: str) -> Path:
        """Download PDF file from S3 to local temporary directory"""
        local_path = self.temp_dir / Path(key).name
        
        try:
            self.logger.info(f"Downloading PDF from s3://{bucket}/{key}")
            self.s3_client.download_file(bucket, key, str(local_path))
            return local_path
        except ClientError as e:
            raise Exception(f"Failed to download PDF from S3: {e}")
    
    def _extract_tables_multi_method(self, pdf_path: Path) -> List[pd.DataFrame]:
        """
        Extract tables using multiple methods for better coverage
        """
        all_tables = []
        
        # Method 1: Camelot (best for well-formatted tables)
        try:
            self.logger.info("Attempting table extraction with Camelot")
            camelot_tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice')
            
            for table in camelot_tables:
                if table.accuracy > 50:  # Only use tables with reasonable accuracy
                    df = table.df
                    if not df.empty and len(df.columns) > 1:
                        df.attrs['extraction_method'] = 'camelot_lattice'
                        df.attrs['accuracy'] = table.accuracy
                        all_tables.append(df)
                        
            # Try stream flavor if lattice didn't work well
            if len(all_tables) == 0:
                camelot_tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='stream')
                for table in camelot_tables:
                    if table.accuracy > 30:
                        df = table.df
                        if not df.empty and len(df.columns) > 1:
                            df.attrs['extraction_method'] = 'camelot_stream'
                            df.attrs['accuracy'] = table.accuracy
                            all_tables.append(df)
                            
        except Exception as e:
            self.logger.warning(f"Camelot extraction failed: {e}")
        
        # Method 2: Tabula (Java-based, good for complex layouts)
        try:
            self.logger.info("Attempting table extraction with Tabula")
            tabula_tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
            
            for i, df in enumerate(tabula_tables):
                if not df.empty and len(df.columns) > 1:
                    df.attrs['extraction_method'] = 'tabula'
                    df.attrs['table_index'] = i
                    all_tables.append(df)
                    
        except Exception as e:
            self.logger.warning(f"Tabula extraction failed: {e}")
        
        # Method 3: pdfplumber (good for text-based tables)
        try:
            self.logger.info("Attempting table extraction with pdfplumber")
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables):
                        if table and len(table) > 1 and len(table[0]) > 1:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            df.attrs['extraction_method'] = 'pdfplumber'
                            df.attrs['page_number'] = page_num + 1
                            df.attrs['table_number'] = table_num + 1
                            all_tables.append(df)
                            
        except Exception as e:
            self.logger.warning(f"pdfplumber extraction failed: {e}")
        
        self.logger.info(f"Extracted {len(all_tables)} tables using multiple methods")
        return all_tables
    
    def _standardize_data(self, tables: List[pd.DataFrame], source_file: str) -> pd.DataFrame:
        """
        Standardize extracted table data to ONS format
        """
        standardized_rows = []
        
        for table_idx, df in enumerate(tables):
            try:
                # Clean column names
                df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
                
                # Remove empty rows and columns
                df = df.dropna(how='all').dropna(axis=1, how='all')
                
                if df.empty:
                    continue
                
                # Try to identify timestamp columns
                timestamp_col = self._identify_timestamp_column(df)
                
                # Process each row
                for idx, row in df.iterrows():
                    # Skip header-like rows
                    if self._is_header_row(row):
                        continue
                    
                    # Extract timestamp
                    timestamp = self._extract_timestamp(row, timestamp_col)
                    
                    # Process numeric columns
                    for col in df.columns:
                        if col == timestamp_col:
                            continue
                            
                        value = row[col]
                        if pd.isna(value) or value == '':
                            continue
                        
                        # Try to convert to numeric
                        numeric_value = self._convert_to_numeric(value)
                        if numeric_value is not None:
                            standardized_row = {
                                'timestamp': timestamp,
                                'dataset_type': self._infer_dataset_type(source_file, col),
                                'region': self._extract_region(source_file, row),
                                'energy_source': self._extract_energy_source(col, row),
                                'measurement_type': col,
                                'value': numeric_value,
                                'unit': self._infer_unit(col, value),
                                'quality_flag': 'extracted',
                                'processing_metadata': {
                                    'processed_at': datetime.utcnow().isoformat(),
                                    'processor_version': '1.0.0',
                                    'source_file': source_file,
                                    'extraction_method': df.attrs.get('extraction_method', 'unknown'),
                                    'table_index': table_idx
                                }
                            }
                            standardized_rows.append(standardized_row)
                            
            except Exception as e:
                self.logger.warning(f"Failed to standardize table {table_idx}: {e}")
                continue
        
        if not standardized_rows:
            raise ValueError("No valid data could be extracted and standardized")
        
        result_df = pd.DataFrame(standardized_rows)
        self.logger.info(f"Standardized {len(result_df)} data points")
        
        return result_df
    
    def _identify_timestamp_column(self, df: pd.DataFrame) -> Optional[str]:
        """Identify which column contains timestamp data"""
        timestamp_keywords = ['data', 'date', 'hora', 'time', 'timestamp', 'periodo']
        
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in timestamp_keywords):
                return col
        
        return None
    
    def _is_header_row(self, row: pd.Series) -> bool:
        """Check if row appears to be a header"""
        text_values = [str(val).lower() for val in row if pd.notna(val)]
        header_keywords = ['total', 'subtotal', 'média', 'media', 'sum', 'fonte']
        
        return any(keyword in ' '.join(text_values) for keyword in header_keywords)
    
    def _extract_timestamp(self, row: pd.Series, timestamp_col: Optional[str]) -> str:
        """Extract timestamp from row"""
        if timestamp_col and timestamp_col in row.index:
            timestamp_val = row[timestamp_col]
            if pd.notna(timestamp_val):
                try:
                    # Try to parse various timestamp formats
                    parsed_ts = pd.to_datetime(timestamp_val, errors='coerce')
                    if pd.notna(parsed_ts):
                        return parsed_ts.isoformat()
                except:
                    pass
        
        # Default to current timestamp if no valid timestamp found
        return datetime.utcnow().isoformat()
    
    def _convert_to_numeric(self, value: Any) -> Optional[float]:
        """Convert value to numeric, handling Brazilian number formats"""
        if pd.isna(value):
            return None
        
        try:
            # Handle string values
            if isinstance(value, str):
                # Remove common non-numeric characters
                cleaned = value.replace(',', '.').replace(' ', '').replace('%', '')
                # Remove currency symbols
                cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
                
                if cleaned:
                    return float(cleaned)
            else:
                return float(value)
        except (ValueError, TypeError):
            return None
        
        return None
    
    def _infer_dataset_type(self, filename: str, column: str) -> str:
        """Infer dataset type from filename and column name"""
        filename_lower = filename.lower()
        column_lower = column.lower()
        
        if any(word in filename_lower for word in ['geracao', 'generation', 'producao']):
            return 'generation'
        elif any(word in filename_lower for word in ['consumo', 'consumption', 'demanda']):
            return 'consumption'
        elif any(word in filename_lower for word in ['transmissao', 'transmission', 'rede']):
            return 'transmission'
        elif any(word in column_lower for word in ['mw', 'gw', 'potencia', 'power']):
            return 'generation'
        else:
            return 'other'
    
    def _extract_region(self, filename: str, row: pd.Series) -> str:
        """Extract region information"""
        # Common Brazilian regions/states
        regions = ['norte', 'nordeste', 'sudeste', 'sul', 'centro-oeste', 'brasil']
        states = ['sp', 'rj', 'mg', 'rs', 'pr', 'sc', 'ba', 'pe', 'ce', 'go']
        
        filename_lower = filename.lower()
        for region in regions:
            if region in filename_lower:
                return region
        
        for state in states:
            if state in filename_lower:
                return state
        
        # Check row values for region information
        for val in row:
            if pd.notna(val):
                val_lower = str(val).lower()
                for region in regions:
                    if region in val_lower:
                        return region
        
        return 'brasil'  # Default to national level
    
    def _extract_energy_source(self, column: str, row: pd.Series) -> str:
        """Extract energy source from column name or row data"""
        column_lower = column.lower()
        
        sources = {
            'hidrica': ['hidrica', 'hidro', 'water'],
            'termica': ['termica', 'thermal', 'gas', 'carvao', 'oleo'],
            'eolica': ['eolica', 'wind', 'vento'],
            'solar': ['solar', 'fotovoltaica'],
            'nuclear': ['nuclear'],
            'biomassa': ['biomassa', 'biomass'],
            'outras': ['outras', 'other']
        }
        
        for source, keywords in sources.items():
            if any(keyword in column_lower for keyword in keywords):
                return source
        
        return 'total'
    
    def _infer_unit(self, column: str, value: Any) -> str:
        """Infer measurement unit from column name and value"""
        column_lower = column.lower()
        
        if any(unit in column_lower for unit in ['mw', 'megawatt']):
            return 'MW'
        elif any(unit in column_lower for unit in ['gw', 'gigawatt']):
            return 'GW'
        elif any(unit in column_lower for unit in ['mwh', 'megawatt-hora']):
            return 'MWh'
        elif any(unit in column_lower for unit in ['gwh', 'gigawatt-hora']):
            return 'GWh'
        elif '%' in str(value):
            return '%'
        else:
            return 'MW'  # Default unit
    
    def _save_as_parquet(self, df: pd.DataFrame) -> Path:
        """Save DataFrame as Parquet file"""
        output_path = self.output_dir / 'processed_data.parquet'
        
        # Ensure proper data types
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        
        # Save with compression
        df.to_parquet(output_path, compression='snappy', index=False)
        
        self.logger.info(f"Saved {len(df)} rows to Parquet file: {output_path}")
        return output_path
    
    def _upload_to_s3(self, local_path: Path, bucket: str, key: str):
        """Upload file to S3"""
        try:
            self.logger.info(f"Uploading to s3://{bucket}/{key}")
            self.s3_client.upload_file(str(local_path), bucket, key)
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")
    
    def _cleanup_temp_files(self, file_paths: List[Path]):
        """Clean up temporary files"""
        for path in file_paths:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {path}: {e}")


def main():
    """Main entry point for AWS Batch job"""
    # Get job parameters from environment variables
    input_s3_uri = os.environ.get('INPUT_S3_URI')
    output_s3_uri = os.environ.get('OUTPUT_S3_URI')
    
    if not input_s3_uri or not output_s3_uri:
        print("ERROR: INPUT_S3_URI and OUTPUT_S3_URI environment variables are required")
        sys.exit(1)
    
    # Initialize processor
    processor = PDFProcessor()
    
    # Process the PDF file
    result = processor.process_pdf_file(input_s3_uri, output_s3_uri)
    
    # Output result as JSON for Step Functions
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    if result['status'] == 'success':
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()