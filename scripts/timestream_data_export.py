#!/usr/bin/env python3
"""
Timestream Data Export Script for Compliance

This script exports all data from Amazon Timestream tables to S3 for compliance
archiving before decommissioning the Timestream resources.
"""

import boto3
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimestreamExporter:
    """Export data from Timestream to S3 for compliance archiving."""
    
    def __init__(self, database_name: str, archive_bucket: str, region: str = 'us-east-1'):
        """
        Initialize the Timestream exporter.
        
        Args:
            database_name: Name of the Timestream database
            archive_bucket: S3 bucket for archiving exported data
            region: AWS region
        """
        self.database_name = database_name
        self.archive_bucket = archive_bucket
        self.region = region
        
        # Initialize AWS clients
        self.timestream_query = boto3.client('timestream-query', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        
        # Export metadata
        self.export_metadata = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'database_name': database_name,
            'region': region,
            'tables_exported': [],
            'total_records': 0,
            'export_status': 'in_progress'
        }
    
    def export_all_tables(self, tables: List[str]) -> Dict[str, Any]:
        """
        Export all specified tables from Timestream.
        
        Args:
            tables: List of table names to export
            
        Returns:
            Export summary with metadata
        """
        logger.info(f"Starting export of {len(tables)} tables from database {self.database_name}")
        
        try:
            for table_name in tables:
                logger.info(f"Exporting table: {table_name}")
                table_summary = self._export_table(table_name)
                self.export_metadata['tables_exported'].append(table_summary)
                self.export_metadata['total_records'] += table_summary['record_count']
            
            self.export_metadata['export_status'] = 'completed'
            logger.info(f"Export completed. Total records: {self.export_metadata['total_records']}")
            
            # Save export metadata
            self._save_export_metadata()
            
            return self.export_metadata
            
        except Exception as e:
            self.export_metadata['export_status'] = 'failed'
            self.export_metadata['error'] = str(e)
            logger.error(f"Export failed: {str(e)}")
            raise
    
    def _export_table(self, table_name: str) -> Dict[str, Any]:
        """Export a single table from Timestream."""
        table_summary = {
            'table_name': table_name,
            'export_timestamp': datetime.utcnow().isoformat(),
            'record_count': 0,
            'file_count': 0,
            'size_bytes': 0
        }
        
        try:
            # Get table schema and data range
            schema_info = self._get_table_schema(table_name)
            date_range = self._get_table_date_range(table_name)
            
            if not date_range:
                logger.warning(f"No data found in table {table_name}")
                return table_summary
            
            # Export data in monthly chunks to manage memory
            current_date = date_range['start_date']
            end_date = date_range['end_date']
            
            while current_date < end_date:
                chunk_end = min(current_date + timedelta(days=30), end_date)
                
                logger.info(f"Exporting {table_name} data from {current_date} to {chunk_end}")
                
                chunk_summary = self._export_table_chunk(
                    table_name, current_date, chunk_end, schema_info
                )
                
                table_summary['record_count'] += chunk_summary['record_count']
                table_summary['file_count'] += 1
                table_summary['size_bytes'] += chunk_summary['size_bytes']
                
                current_date = chunk_end
            
            return table_summary
            
        except Exception as e:
            logger.error(f"Error exporting table {table_name}: {str(e)}")
            table_summary['error'] = str(e)
            return table_summary
    
    def _export_table_chunk(self, table_name: str, start_date: datetime, 
                           end_date: datetime, schema_info: Dict) -> Dict[str, Any]:
        """Export a chunk of table data."""
        
        # Build query for the time range
        query = f"""
        SELECT * FROM "{self.database_name}"."{table_name}"
        WHERE time BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
        ORDER BY time
        """
        
        try:
            # Execute query with pagination
            records = []
            next_token = None
            
            while True:
                query_params = {
                    'QueryString': query,
                    'MaxRows': 10000
                }
                
                if next_token:
                    query_params['NextToken'] = next_token
                
                response = self.timestream_query.query(**query_params)
                
                # Process rows
                for row in response.get('Rows', []):
                    record = self._parse_timestream_row(row, response['ColumnInfo'])
                    records.append(record)
                
                next_token = response.get('NextToken')
                if not next_token:
                    break
            
            if not records:
                return {'record_count': 0, 'size_bytes': 0}
            
            # Convert to DataFrame and save as Parquet
            df = pd.DataFrame(records)
            
            # Generate S3 key
            s3_key = f"timestream-archive/{self.database_name}/{table_name}/" \
                    f"year={start_date.year}/month={start_date.month:02d}/" \
                    f"{table_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.parquet"
            
            # Save to S3
            parquet_buffer = df.to_parquet(index=False)
            
            self.s3_client.put_object(
                Bucket=self.archive_bucket,
                Key=s3_key,
                Body=parquet_buffer,
                Metadata={
                    'source_database': self.database_name,
                    'source_table': table_name,
                    'export_timestamp': datetime.utcnow().isoformat(),
                    'record_count': str(len(records)),
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            )
            
            logger.info(f"Exported {len(records)} records to s3://{self.archive_bucket}/{s3_key}")
            
            return {
                'record_count': len(records),
                'size_bytes': len(parquet_buffer),
                's3_key': s3_key
            }
            
        except Exception as e:
            logger.error(f"Error exporting chunk: {str(e)}")
            raise
    
    def _get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get table schema information."""
        query = f'DESCRIBE "{self.database_name}"."{table_name}"'
        
        try:
            response = self.timestream_query.query(QueryString=query)
            
            schema = {
                'columns': [],
                'dimensions': [],
                'measures': []
            }
            
            for row in response.get('Rows', []):
                column_info = self._parse_timestream_row(row, response['ColumnInfo'])
                schema['columns'].append(column_info)
                
                if column_info.get('Type') == 'DIMENSION':
                    schema['dimensions'].append(column_info['Name'])
                elif column_info.get('Type') == 'MEASURE':
                    schema['measures'].append(column_info['Name'])
            
            return schema
            
        except Exception as e:
            logger.warning(f"Could not get schema for table {table_name}: {str(e)}")
            return {'columns': [], 'dimensions': [], 'measures': []}
    
    def _get_table_date_range(self, table_name: str) -> Optional[Dict[str, datetime]]:
        """Get the date range of data in the table."""
        query = f"""
        SELECT 
            min(time) as min_time,
            max(time) as max_time,
            count(*) as record_count
        FROM "{self.database_name}"."{table_name}"
        """
        
        try:
            response = self.timestream_query.query(QueryString=query)
            
            if not response.get('Rows'):
                return None
            
            row = response['Rows'][0]
            parsed_row = self._parse_timestream_row(row, response['ColumnInfo'])
            
            if parsed_row.get('record_count', 0) == 0:
                return None
            
            return {
                'start_date': datetime.fromisoformat(parsed_row['min_time'].replace('Z', '+00:00')),
                'end_date': datetime.fromisoformat(parsed_row['max_time'].replace('Z', '+00:00')),
                'record_count': parsed_row['record_count']
            }
            
        except Exception as e:
            logger.error(f"Error getting date range for table {table_name}: {str(e)}")
            return None
    
    def _parse_timestream_row(self, row: Dict, column_info: List[Dict]) -> Dict[str, Any]:
        """Parse a Timestream query result row."""
        parsed_row = {}
        
        for i, data in enumerate(row['Data']):
            column_name = column_info[i]['Name']
            column_type = column_info[i]['Type']['ScalarType']
            
            if 'ScalarValue' in data:
                value = data['ScalarValue']
                
                # Type conversion
                if column_type == 'BIGINT':
                    parsed_row[column_name] = int(value)
                elif column_type == 'DOUBLE':
                    parsed_row[column_name] = float(value)
                elif column_type == 'BOOLEAN':
                    parsed_row[column_name] = value.lower() == 'true'
                else:
                    parsed_row[column_name] = value
            else:
                parsed_row[column_name] = None
        
        return parsed_row
    
    def _save_export_metadata(self):
        """Save export metadata to S3."""
        metadata_key = f"timestream-archive/{self.database_name}/export_metadata.json"
        
        try:
            self.s3_client.put_object(
                Bucket=self.archive_bucket,
                Key=metadata_key,
                Body=json.dumps(self.export_metadata, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"Export metadata saved to s3://{self.archive_bucket}/{metadata_key}")
            
        except Exception as e:
            logger.error(f"Error saving export metadata: {str(e)}")


def main():
    """Main function to run the export."""
    
    # Configuration - these should be provided as environment variables or CLI args
    database_name = os.environ.get('TIMESTREAM_DATABASE_NAME', 'ons-data-platform_dev_energy_data')
    archive_bucket = os.environ.get('ARCHIVE_BUCKET_NAME')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not archive_bucket:
        logger.error("ARCHIVE_BUCKET_NAME environment variable is required")
        sys.exit(1)
    
    # Tables to export
    tables_to_export = [
        'generation_data',
        'consumption_data', 
        'transmission_data'
    ]
    
    try:
        # Initialize exporter
        exporter = TimestreamExporter(database_name, archive_bucket, region)
        
        # Run export
        export_summary = exporter.export_all_tables(tables_to_export)
        
        # Print summary
        print("\n" + "="*50)
        print("TIMESTREAM DATA EXPORT SUMMARY")
        print("="*50)
        print(f"Database: {database_name}")
        print(f"Archive Bucket: {archive_bucket}")
        print(f"Export Status: {export_summary['export_status']}")
        print(f"Total Records: {export_summary['total_records']:,}")
        print(f"Tables Exported: {len(export_summary['tables_exported'])}")
        print(f"Export Timestamp: {export_summary['export_timestamp']}")
        
        for table_info in export_summary['tables_exported']:
            print(f"\n  {table_info['table_name']}:")
            print(f"    Records: {table_info['record_count']:,}")
            print(f"    Files: {table_info['file_count']}")
            print(f"    Size: {table_info['size_bytes']:,} bytes")
        
        print("\n" + "="*50)
        
        if export_summary['export_status'] == 'completed':
            print("✅ Export completed successfully!")
            print(f"Data archived to: s3://{archive_bucket}/timestream-archive/")
            sys.exit(0)
        else:
            print("❌ Export failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Export failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()