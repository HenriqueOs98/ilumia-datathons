"""
Timestream Data Export Functionality

This module provides functionality to export data from Amazon Timestream
to S3 for migration to InfluxDB. It includes pagination, batching, progress
tracking, and resumable migration capabilities.

Requirements addressed: 2.1, 2.3
"""

import boto3
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import pandas as pd
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExportProgress:
    """Track export progress for resumable migrations"""
    export_id: str
    database_name: str
    table_name: str
    start_time: str
    end_time: str
    total_records: int = 0
    exported_records: int = 0
    current_batch: int = 0
    last_timestamp: Optional[str] = None
    status: str = "in_progress"  # in_progress, completed, failed, paused
    error_message: Optional[str] = None
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()


class TimestreamExporter:
    """
    Export data from Amazon Timestream to S3 with pagination and progress tracking
    """
    
    def __init__(self, 
                 region_name: str = 'us-east-1',
                 batch_size: int = 10000,
                 s3_bucket: str = None,
                 progress_table: str = None):
        """
        Initialize the Timestream exporter
        
        Args:
            region_name: AWS region for Timestream
            batch_size: Number of records per batch
            s3_bucket: S3 bucket for exported data
            progress_table: DynamoDB table for progress tracking
        """
        self.region_name = region_name
        self.batch_size = batch_size
        self.s3_bucket = s3_bucket
        self.progress_table = progress_table
        
        # Initialize AWS clients
        self.timestream_query = boto3.client('timestream-query', region_name=region_name)
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        
        if progress_table:
            self.progress_table_resource = self.dynamodb.Table(progress_table)
        else:
            self.progress_table_resource = None
    
    def export_table_data(self,
                         database_name: str,
                         table_name: str,
                         start_time: datetime,
                         end_time: datetime,
                         export_id: str = None,
                         resume: bool = False) -> Dict[str, Any]:
        """
        Export all data from a Timestream table to S3
        
        Args:
            database_name: Timestream database name
            table_name: Timestream table name
            start_time: Start time for data export
            end_time: End time for data export
            export_id: Unique identifier for this export job
            resume: Whether to resume a previous export
            
        Returns:
            Dictionary with export results and statistics
        """
        if export_id is None:
            export_id = f"{database_name}_{table_name}_{int(time.time())}"
        
        logger.info(f"Starting export for {database_name}.{table_name} with ID: {export_id}")
        
        # Initialize or load progress
        progress = self._initialize_progress(
            export_id, database_name, table_name, 
            start_time.isoformat(), end_time.isoformat(), resume
        )
        
        try:
            # Get total record count for progress tracking
            if progress.total_records == 0:
                progress.total_records = self._get_record_count(
                    database_name, table_name, start_time, end_time
                )
                self._save_progress(progress)
            
            # Export data in batches
            current_start = start_time if not resume else datetime.fromisoformat(progress.last_timestamp or start_time.isoformat())
            
            while current_start < end_time:
                batch_end = min(current_start + timedelta(hours=1), end_time)
                
                logger.info(f"Exporting batch {progress.current_batch + 1}: {current_start} to {batch_end}")
                
                # Query batch data
                batch_data = self._query_batch_data(
                    database_name, table_name, current_start, batch_end
                )
                
                if batch_data:
                    # Save batch to S3
                    s3_key = self._save_batch_to_s3(
                        batch_data, export_id, progress.current_batch
                    )
                    
                    # Update progress
                    progress.exported_records += len(batch_data)
                    progress.current_batch += 1
                    progress.last_timestamp = batch_end.isoformat()
                    progress.updated_at = datetime.utcnow().isoformat()
                    
                    self._save_progress(progress)
                    
                    logger.info(f"Exported {len(batch_data)} records to {s3_key}")
                
                current_start = batch_end
                
                # Small delay to avoid overwhelming Timestream
                time.sleep(0.1)
            
            # Mark export as completed
            progress.status = "completed"
            progress.updated_at = datetime.utcnow().isoformat()
            self._save_progress(progress)
            
            logger.info(f"Export completed. Total records: {progress.exported_records}")
            
            return {
                'export_id': export_id,
                'status': 'completed',
                'total_records': progress.exported_records,
                'batches': progress.current_batch,
                's3_bucket': self.s3_bucket,
                's3_prefix': f"timestream-export/{export_id}/"
            }
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            progress.status = "failed"
            progress.error_message = str(e)
            progress.updated_at = datetime.utcnow().isoformat()
            self._save_progress(progress)
            raise
    
    def _get_record_count(self, 
                         database_name: str, 
                         table_name: str,
                         start_time: datetime,
                         end_time: datetime) -> int:
        """Get total record count for progress tracking"""
        query = f"""
            SELECT COUNT(*) as record_count
            FROM "{database_name}"."{table_name}"
            WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
        """
        
        try:
            response = self.timestream_query.query(QueryString=query)
            if response['Rows']:
                return int(response['Rows'][0]['Data'][0]['ScalarValue'])
            return 0
        except Exception as e:
            logger.warning(f"Could not get record count: {str(e)}")
            return 0
    
    def _query_batch_data(self,
                         database_name: str,
                         table_name: str,
                         start_time: datetime,
                         end_time: datetime) -> List[Dict[str, Any]]:
        """Query a batch of data from Timestream"""
        query = f"""
            SELECT *
            FROM "{database_name}"."{table_name}"
            WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
            ORDER BY time ASC
        """
        
        try:
            response = self.timestream_query.query(QueryString=query)
            return self._parse_timestream_response(response)
        except Exception as e:
            logger.error(f"Failed to query batch data: {str(e)}")
            raise
    
    def _parse_timestream_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Timestream query response into structured data"""
        if not response.get('Rows'):
            return []
        
        columns = [col['Name'] for col in response['ColumnInfo']]
        rows = []
        
        for row in response['Rows']:
            row_data = {}
            for i, data_point in enumerate(row['Data']):
                column_name = columns[i]
                
                # Extract value based on data type
                if 'ScalarValue' in data_point:
                    row_data[column_name] = data_point['ScalarValue']
                elif 'TimeSeriesValue' in data_point:
                    row_data[column_name] = data_point['TimeSeriesValue']
                elif 'ArrayValue' in data_point:
                    row_data[column_name] = data_point['ArrayValue']
                else:
                    row_data[column_name] = None
            
            rows.append(row_data)
        
        return rows
    
    def _save_batch_to_s3(self, 
                         batch_data: List[Dict[str, Any]], 
                         export_id: str, 
                         batch_number: int) -> str:
        """Save batch data to S3 as Parquet file"""
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        
        # Convert to DataFrame for Parquet export
        df = pd.DataFrame(batch_data)
        
        # Generate S3 key
        s3_key = f"timestream-export/{export_id}/batch_{batch_number:06d}.parquet"
        
        # Save to S3
        parquet_buffer = df.to_parquet(index=False)
        
        try:
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=parquet_buffer,
                ContentType='application/octet-stream'
            )
            return s3_key
        except Exception as e:
            logger.error(f"Failed to save batch to S3: {str(e)}")
            raise
    
    def _initialize_progress(self,
                           export_id: str,
                           database_name: str,
                           table_name: str,
                           start_time: str,
                           end_time: str,
                           resume: bool = False) -> ExportProgress:
        """Initialize or load export progress"""
        if resume and self.progress_table_resource:
            try:
                response = self.progress_table_resource.get_item(
                    Key={'export_id': export_id}
                )
                if 'Item' in response:
                    item = response['Item']
                    return ExportProgress(
                        export_id=item['export_id'],
                        database_name=item['database_name'],
                        table_name=item['table_name'],
                        start_time=item['start_time'],
                        end_time=item['end_time'],
                        total_records=item.get('total_records', 0),
                        exported_records=item.get('exported_records', 0),
                        current_batch=item.get('current_batch', 0),
                        last_timestamp=item.get('last_timestamp'),
                        status=item.get('status', 'in_progress'),
                        error_message=item.get('error_message'),
                        created_at=item.get('created_at'),
                        updated_at=item.get('updated_at')
                    )
            except Exception as e:
                logger.warning(f"Could not load progress: {str(e)}")
        
        # Create new progress record
        return ExportProgress(
            export_id=export_id,
            database_name=database_name,
            table_name=table_name,
            start_time=start_time,
            end_time=end_time
        )
    
    def _save_progress(self, progress: ExportProgress):
        """Save export progress to DynamoDB"""
        if not self.progress_table_resource:
            return
        
        try:
            self.progress_table_resource.put_item(Item=asdict(progress))
        except Exception as e:
            logger.warning(f"Could not save progress: {str(e)}")
    
    def get_export_status(self, export_id: str) -> Optional[ExportProgress]:
        """Get the status of an export job"""
        if not self.progress_table_resource:
            return None
        
        try:
            response = self.progress_table_resource.get_item(
                Key={'export_id': export_id}
            )
            if 'Item' in response:
                item = response['Item']
                return ExportProgress(**item)
            return None
        except Exception as e:
            logger.error(f"Could not get export status: {str(e)}")
            return None
    
    def list_exports(self, status_filter: str = None) -> List[ExportProgress]:
        """List all export jobs, optionally filtered by status"""
        if not self.progress_table_resource:
            return []
        
        try:
            if status_filter:
                response = self.progress_table_resource.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('status').eq(status_filter)
                )
            else:
                response = self.progress_table_resource.scan()
            
            exports = []
            for item in response.get('Items', []):
                exports.append(ExportProgress(**item))
            
            return exports
        except Exception as e:
            logger.error(f"Could not list exports: {str(e)}")
            return []
    
    def pause_export(self, export_id: str) -> bool:
        """Pause an ongoing export"""
        progress = self.get_export_status(export_id)
        if progress and progress.status == "in_progress":
            progress.status = "paused"
            progress.updated_at = datetime.utcnow().isoformat()
            self._save_progress(progress)
            return True
        return False
    
    def resume_export(self, export_id: str) -> Dict[str, Any]:
        """Resume a paused export"""
        progress = self.get_export_status(export_id)
        if not progress:
            raise ValueError(f"Export {export_id} not found")
        
        if progress.status != "paused":
            raise ValueError(f"Export {export_id} is not paused (status: {progress.status})")
        
        # Resume the export
        return self.export_table_data(
            database_name=progress.database_name,
            table_name=progress.table_name,
            start_time=datetime.fromisoformat(progress.start_time),
            end_time=datetime.fromisoformat(progress.end_time),
            export_id=export_id,
            resume=True
        )


def export_all_tables(databases_config: Dict[str, List[str]],
                     start_time: datetime,
                     end_time: datetime,
                     s3_bucket: str,
                     progress_table: str = None,
                     region_name: str = 'us-east-1') -> Dict[str, Any]:
    """
    Export data from multiple Timestream tables
    
    Args:
        databases_config: Dict mapping database names to lists of table names
        start_time: Start time for data export
        end_time: End time for data export
        s3_bucket: S3 bucket for exported data
        progress_table: DynamoDB table for progress tracking
        region_name: AWS region
        
    Returns:
        Dictionary with export results for all tables
    """
    exporter = TimestreamExporter(
        region_name=region_name,
        s3_bucket=s3_bucket,
        progress_table=progress_table
    )
    
    results = {}
    
    for database_name, table_names in databases_config.items():
        results[database_name] = {}
        
        for table_name in table_names:
            logger.info(f"Starting export for {database_name}.{table_name}")
            
            try:
                result = exporter.export_table_data(
                    database_name=database_name,
                    table_name=table_name,
                    start_time=start_time,
                    end_time=end_time
                )
                results[database_name][table_name] = result
                
            except Exception as e:
                logger.error(f"Failed to export {database_name}.{table_name}: {str(e)}")
                results[database_name][table_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
    
    return results


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Export Timestream data to S3')
    parser.add_argument('--database', required=True, help='Timestream database name')
    parser.add_argument('--table', required=True, help='Timestream table name')
    parser.add_argument('--start-time', required=True, help='Start time (ISO format)')
    parser.add_argument('--end-time', required=True, help='End time (ISO format)')
    parser.add_argument('--s3-bucket', required=True, help='S3 bucket for export')
    parser.add_argument('--progress-table', help='DynamoDB table for progress tracking')
    parser.add_argument('--export-id', help='Export job ID (for resume)')
    parser.add_argument('--resume', action='store_true', help='Resume previous export')
    
    args = parser.parse_args()
    
    exporter = TimestreamExporter(
        s3_bucket=args.s3_bucket,
        progress_table=args.progress_table
    )
    
    start_time = datetime.fromisoformat(args.start_time)
    end_time = datetime.fromisoformat(args.end_time)
    
    result = exporter.export_table_data(
        database_name=args.database,
        table_name=args.table,
        start_time=start_time,
        end_time=end_time,
        export_id=args.export_id,
        resume=args.resume
    )
    
    print(json.dumps(result, indent=2))