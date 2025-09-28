"""
Data Validation and Integrity Checking Tools

This module provides functionality to validate data migration between
Amazon Timestream and InfluxDB, including checksum validation, row count
verification, and automated accuracy testing.

Requirements addressed: 2.2, 2.3
"""

import boto3
import hashlib
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Results of data validation between Timestream and InfluxDB"""
    validation_id: str
    source_database: str
    source_table: str
    target_bucket: str
    start_time: str
    end_time: str
    
    # Count validation
    source_record_count: int = 0
    target_record_count: int = 0
    count_match: bool = False
    
    # Checksum validation
    source_checksum: str = ""
    target_checksum: str = ""
    checksum_match: bool = False
    
    # Sample validation
    sample_size: int = 0
    sample_matches: int = 0
    sample_accuracy: float = 0.0
    
    # Field validation
    missing_fields: List[str] = None
    extra_fields: List[str] = None
    field_type_mismatches: Dict[str, Tuple[str, str]] = None
    
    # Time range validation
    source_time_range: Tuple[str, str] = None
    target_time_range: Tuple[str, str] = None
    time_range_match: bool = False
    
    # Overall validation
    overall_status: str = "pending"  # pending, passed, failed, warning
    validation_errors: List[str] = None
    validation_warnings: List[str] = None
    
    # Metadata
    validation_timestamp: str = None
    validation_duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.validation_timestamp is None:
            self.validation_timestamp = datetime.utcnow().isoformat()
        if self.validation_errors is None:
            self.validation_errors = []
        if self.validation_warnings is None:
            self.validation_warnings = []
        if self.missing_fields is None:
            self.missing_fields = []
        if self.extra_fields is None:
            self.extra_fields = []
        if self.field_type_mismatches is None:
            self.field_type_mismatches = {}


class DataValidator:
    """
    Validate data migration between Timestream and InfluxDB
    """
    
    def __init__(self,
                 timestream_region: str = 'us-east-1',
                 influxdb_url: str = None,
                 influxdb_token: str = None,
                 influxdb_org: str = None,
                 sample_size: int = 1000):
        """
        Initialize the data validator
        
        Args:
            timestream_region: AWS region for Timestream
            influxdb_url: InfluxDB connection URL
            influxdb_token: InfluxDB authentication token
            influxdb_org: InfluxDB organization
            sample_size: Number of records to sample for detailed validation
        """
        self.timestream_region = timestream_region
        self.sample_size = sample_size
        
        # Initialize Timestream client
        self.timestream_query = boto3.client('timestream-query', region_name=timestream_region)
        
        # Initialize InfluxDB client
        if influxdb_url and influxdb_token and influxdb_org:
            self.influxdb_client = InfluxDBClient(
                url=influxdb_url,
                token=influxdb_token,
                org=influxdb_org
            )
            self.influxdb_query_api = self.influxdb_client.query_api()
        else:
            self.influxdb_client = None
            self.influxdb_query_api = None
            logger.warning("InfluxDB client not initialized - some validations will be skipped")
    
    def validate_migration(self,
                          source_database: str,
                          source_table: str,
                          target_bucket: str,
                          start_time: datetime,
                          end_time: datetime,
                          validation_id: str = None) -> ValidationResult:
        """
        Perform comprehensive validation between Timestream and InfluxDB data
        
        Args:
            source_database: Timestream database name
            source_table: Timestream table name
            target_bucket: InfluxDB bucket name
            start_time: Start time for validation
            end_time: End time for validation
            validation_id: Unique identifier for this validation
            
        Returns:
            ValidationResult with comprehensive validation results
        """
        if validation_id is None:
            validation_id = f"validation_{source_database}_{source_table}_{int(datetime.utcnow().timestamp())}"
        
        logger.info(f"Starting validation {validation_id} for {source_database}.{source_table} -> {target_bucket}")
        
        start_validation_time = datetime.utcnow()
        
        result = ValidationResult(
            validation_id=validation_id,
            source_database=source_database,
            source_table=source_table,
            target_bucket=target_bucket,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )
        
        try:
            # 1. Count validation
            logger.info("Performing count validation...")
            self._validate_record_counts(result, start_time, end_time)
            
            # 2. Time range validation
            logger.info("Performing time range validation...")
            self._validate_time_ranges(result, start_time, end_time)
            
            # 3. Schema validation
            logger.info("Performing schema validation...")
            self._validate_schemas(result, start_time, end_time)
            
            # 4. Sample data validation
            logger.info("Performing sample data validation...")
            self._validate_sample_data(result, start_time, end_time)
            
            # 5. Checksum validation
            logger.info("Performing checksum validation...")
            self._validate_checksums(result, start_time, end_time)
            
            # 6. Determine overall status
            self._determine_overall_status(result)
            
            # Calculate validation duration
            end_validation_time = datetime.utcnow()
            result.validation_duration_seconds = (end_validation_time - start_validation_time).total_seconds()
            
            logger.info(f"Validation completed with status: {result.overall_status}")
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            result.overall_status = "failed"
            result.validation_errors.append(f"Validation failed: {str(e)}")
            return result
    
    def _validate_record_counts(self, result: ValidationResult, start_time: datetime, end_time: datetime):
        """Validate record counts between source and target"""
        try:
            # Get Timestream count
            timestream_query = f"""
                SELECT COUNT(*) as record_count
                FROM "{result.source_database}"."{result.source_table}"
                WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
            """
            
            response = self.timestream_query.query(QueryString=timestream_query)
            if response['Rows']:
                result.source_record_count = int(response['Rows'][0]['Data'][0]['ScalarValue'])
            
            # Get InfluxDB count if client is available
            if self.influxdb_query_api:
                influx_query = f'''
                    from(bucket: "{result.target_bucket}")
                    |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                    |> count()
                '''
                
                influx_result = self.influxdb_query_api.query(influx_query)
                count = 0
                for table in influx_result:
                    for record in table.records:
                        count += record.get_value()
                result.target_record_count = count
            
            result.count_match = result.source_record_count == result.target_record_count
            
            if not result.count_match:
                result.validation_errors.append(
                    f"Record count mismatch: Timestream={result.source_record_count}, "
                    f"InfluxDB={result.target_record_count}"
                )
            
        except Exception as e:
            result.validation_errors.append(f"Count validation failed: {str(e)}")
    
    def _validate_time_ranges(self, result: ValidationResult, start_time: datetime, end_time: datetime):
        """Validate time ranges between source and target"""
        try:
            # Get Timestream time range
            timestream_query = f"""
                SELECT MIN(time) as min_time, MAX(time) as max_time
                FROM "{result.source_database}"."{result.source_table}"
                WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
            """
            
            response = self.timestream_query.query(QueryString=timestream_query)
            if response['Rows'] and len(response['Rows'][0]['Data']) >= 2:
                min_time = response['Rows'][0]['Data'][0]['ScalarValue']
                max_time = response['Rows'][0]['Data'][1]['ScalarValue']
                result.source_time_range = (min_time, max_time)
            
            # Get InfluxDB time range if client is available
            if self.influxdb_query_api:
                influx_query = f'''
                    from(bucket: "{result.target_bucket}")
                    |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                    |> group()
                    |> min(column: "_time")
                '''
                
                min_result = self.influxdb_query_api.query(influx_query)
                
                influx_query = f'''
                    from(bucket: "{result.target_bucket}")
                    |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                    |> group()
                    |> max(column: "_time")
                '''
                
                max_result = self.influxdb_query_api.query(influx_query)
                
                min_time = None
                max_time = None
                
                for table in min_result:
                    for record in table.records:
                        min_time = record.get_time().isoformat()
                        break
                
                for table in max_result:
                    for record in table.records:
                        max_time = record.get_time().isoformat()
                        break
                
                if min_time and max_time:
                    result.target_time_range = (min_time, max_time)
            
            # Compare time ranges
            if result.source_time_range and result.target_time_range:
                result.time_range_match = (
                    result.source_time_range[0] == result.target_time_range[0] and
                    result.source_time_range[1] == result.target_time_range[1]
                )
                
                if not result.time_range_match:
                    result.validation_warnings.append(
                        f"Time range mismatch: Timestream={result.source_time_range}, "
                        f"InfluxDB={result.target_time_range}"
                    )
            
        except Exception as e:
            result.validation_errors.append(f"Time range validation failed: {str(e)}")
    
    def _validate_schemas(self, result: ValidationResult, start_time: datetime, end_time: datetime):
        """Validate schema compatibility between source and target"""
        try:
            # Get Timestream schema
            timestream_query = f"""
                SELECT *
                FROM "{result.source_database}"."{result.source_table}"
                WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
                LIMIT 1
            """
            
            response = self.timestream_query.query(QueryString=timestream_query)
            timestream_fields = set()
            
            if response.get('ColumnInfo'):
                for col in response['ColumnInfo']:
                    timestream_fields.add(col['Name'])
            
            # Get InfluxDB schema if client is available
            influxdb_fields = set()
            if self.influxdb_query_api:
                influx_query = f'''
                    from(bucket: "{result.target_bucket}")
                    |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                    |> limit(n: 1)
                '''
                
                influx_result = self.influxdb_query_api.query(influx_query)
                for table in influx_result:
                    for record in table.records:
                        influxdb_fields.update(record.values.keys())
                        break
            
            # Compare schemas
            if timestream_fields and influxdb_fields:
                result.missing_fields = list(timestream_fields - influxdb_fields)
                result.extra_fields = list(influxdb_fields - timestream_fields)
                
                if result.missing_fields:
                    result.validation_errors.append(f"Missing fields in InfluxDB: {result.missing_fields}")
                
                if result.extra_fields:
                    result.validation_warnings.append(f"Extra fields in InfluxDB: {result.extra_fields}")
            
        except Exception as e:
            result.validation_errors.append(f"Schema validation failed: {str(e)}")
    
    def _validate_sample_data(self, result: ValidationResult, start_time: datetime, end_time: datetime):
        """Validate a sample of data records between source and target"""
        try:
            # Get sample from Timestream
            timestream_query = f"""
                SELECT *
                FROM "{result.source_database}"."{result.source_table}"
                WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
                ORDER BY time ASC
                LIMIT {self.sample_size}
            """
            
            response = self.timestream_query.query(QueryString=timestream_query)
            timestream_sample = self._parse_timestream_response(response)
            
            if not timestream_sample:
                result.validation_warnings.append("No sample data available from Timestream")
                return
            
            result.sample_size = len(timestream_sample)
            
            # Get corresponding sample from InfluxDB if client is available
            if self.influxdb_query_api:
                matches = 0
                
                for record in timestream_sample[:min(100, len(timestream_sample))]:  # Limit to 100 for performance
                    timestamp = record.get('time')
                    if timestamp:
                        # Query InfluxDB for this specific timestamp
                        influx_query = f'''
                            from(bucket: "{result.target_bucket}")
                            |> range(start: {timestamp}, stop: {timestamp})
                            |> limit(n: 1)
                        '''
                        
                        influx_result = self.influxdb_query_api.query(influx_query)
                        
                        # Check if record exists in InfluxDB
                        found = False
                        for table in influx_result:
                            if table.records:
                                found = True
                                break
                        
                        if found:
                            matches += 1
                
                result.sample_matches = matches
                result.sample_accuracy = matches / min(100, len(timestream_sample)) if timestream_sample else 0.0
                
                if result.sample_accuracy < 0.95:
                    result.validation_errors.append(
                        f"Low sample accuracy: {result.sample_accuracy:.2%} "
                        f"({result.sample_matches}/{min(100, len(timestream_sample))} matches)"
                    )
            
        except Exception as e:
            result.validation_errors.append(f"Sample validation failed: {str(e)}")
    
    def _validate_checksums(self, result: ValidationResult, start_time: datetime, end_time: datetime):
        """Validate data integrity using checksums"""
        try:
            # Generate checksum for Timestream data
            timestream_query = f"""
                SELECT *
                FROM "{result.source_database}"."{result.source_table}"
                WHERE time BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
                ORDER BY time ASC
            """
            
            response = self.timestream_query.query(QueryString=timestream_query)
            timestream_data = self._parse_timestream_response(response)
            
            if timestream_data:
                # Create deterministic string representation for checksum
                timestream_str = json.dumps(timestream_data, sort_keys=True, default=str)
                result.source_checksum = hashlib.md5(timestream_str.encode()).hexdigest()
            
            # Generate checksum for InfluxDB data if client is available
            if self.influxdb_query_api:
                influx_query = f'''
                    from(bucket: "{result.target_bucket}")
                    |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
                    |> sort(columns: ["_time"])
                '''
                
                influx_result = self.influxdb_query_api.query(influx_query)
                influx_data = []
                
                for table in influx_result:
                    for record in table.records:
                        influx_data.append({
                            'time': record.get_time().isoformat(),
                            'measurement': record.get_measurement(),
                            'field': record.get_field(),
                            'value': record.get_value(),
                            'tags': record.values
                        })
                
                if influx_data:
                    influx_str = json.dumps(influx_data, sort_keys=True, default=str)
                    result.target_checksum = hashlib.md5(influx_str.encode()).hexdigest()
            
            # Compare checksums
            if result.source_checksum and result.target_checksum:
                result.checksum_match = result.source_checksum == result.target_checksum
                
                if not result.checksum_match:
                    result.validation_warnings.append(
                        f"Checksum mismatch - data may have been transformed during migration"
                    )
            
        except Exception as e:
            result.validation_errors.append(f"Checksum validation failed: {str(e)}")
    
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
    
    def _determine_overall_status(self, result: ValidationResult):
        """Determine overall validation status based on individual checks"""
        if result.validation_errors:
            result.overall_status = "failed"
        elif result.validation_warnings:
            result.overall_status = "warning"
        else:
            result.overall_status = "passed"
    
    def generate_validation_report(self, result: ValidationResult) -> str:
        """Generate a human-readable validation report"""
        report = []
        report.append(f"Data Migration Validation Report")
        report.append(f"=" * 40)
        report.append(f"Validation ID: {result.validation_id}")
        report.append(f"Source: {result.source_database}.{result.source_table}")
        report.append(f"Target: {result.target_bucket}")
        report.append(f"Time Range: {result.start_time} to {result.end_time}")
        report.append(f"Overall Status: {result.overall_status.upper()}")
        report.append(f"Validation Duration: {result.validation_duration_seconds:.2f} seconds")
        report.append("")
        
        # Count validation
        report.append("Record Count Validation:")
        report.append(f"  Timestream Records: {result.source_record_count:,}")
        report.append(f"  InfluxDB Records: {result.target_record_count:,}")
        report.append(f"  Count Match: {'✓' if result.count_match else '✗'}")
        report.append("")
        
        # Time range validation
        if result.source_time_range and result.target_time_range:
            report.append("Time Range Validation:")
            report.append(f"  Timestream Range: {result.source_time_range[0]} to {result.source_time_range[1]}")
            report.append(f"  InfluxDB Range: {result.target_time_range[0]} to {result.target_time_range[1]}")
            report.append(f"  Range Match: {'✓' if result.time_range_match else '✗'}")
            report.append("")
        
        # Schema validation
        if result.missing_fields or result.extra_fields:
            report.append("Schema Validation:")
            if result.missing_fields:
                report.append(f"  Missing Fields: {', '.join(result.missing_fields)}")
            if result.extra_fields:
                report.append(f"  Extra Fields: {', '.join(result.extra_fields)}")
            report.append("")
        
        # Sample validation
        if result.sample_size > 0:
            report.append("Sample Data Validation:")
            report.append(f"  Sample Size: {result.sample_size:,}")
            report.append(f"  Sample Matches: {result.sample_matches:,}")
            report.append(f"  Sample Accuracy: {result.sample_accuracy:.2%}")
            report.append("")
        
        # Checksum validation
        if result.source_checksum or result.target_checksum:
            report.append("Checksum Validation:")
            report.append(f"  Timestream Checksum: {result.source_checksum}")
            report.append(f"  InfluxDB Checksum: {result.target_checksum}")
            report.append(f"  Checksum Match: {'✓' if result.checksum_match else '✗'}")
            report.append("")
        
        # Errors and warnings
        if result.validation_errors:
            report.append("Validation Errors:")
            for error in result.validation_errors:
                report.append(f"  ✗ {error}")
            report.append("")
        
        if result.validation_warnings:
            report.append("Validation Warnings:")
            for warning in result.validation_warnings:
                report.append(f"  ⚠ {warning}")
            report.append("")
        
        return "\n".join(report)


def validate_multiple_tables(tables_config: List[Dict[str, Any]],
                            influxdb_url: str,
                            influxdb_token: str,
                            influxdb_org: str,
                            timestream_region: str = 'us-east-1') -> List[ValidationResult]:
    """
    Validate multiple table migrations in parallel
    
    Args:
        tables_config: List of table configurations with database, table, bucket, start_time, end_time
        influxdb_url: InfluxDB connection URL
        influxdb_token: InfluxDB authentication token
        influxdb_org: InfluxDB organization
        timestream_region: AWS region for Timestream
        
    Returns:
        List of ValidationResult objects
    """
    validator = DataValidator(
        timestream_region=timestream_region,
        influxdb_url=influxdb_url,
        influxdb_token=influxdb_token,
        influxdb_org=influxdb_org
    )
    
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_config = {}
        
        for config in tables_config:
            future = executor.submit(
                validator.validate_migration,
                config['database'],
                config['table'],
                config['bucket'],
                datetime.fromisoformat(config['start_time']),
                datetime.fromisoformat(config['end_time'])
            )
            future_to_config[future] = config
        
        for future in as_completed(future_to_config):
            config = future_to_config[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(f"Validation completed for {config['database']}.{config['table']}: {result.overall_status}")
            except Exception as e:
                logger.error(f"Validation failed for {config['database']}.{config['table']}: {str(e)}")
    
    return results


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Timestream to InfluxDB migration')
    parser.add_argument('--database', required=True, help='Timestream database name')
    parser.add_argument('--table', required=True, help='Timestream table name')
    parser.add_argument('--bucket', required=True, help='InfluxDB bucket name')
    parser.add_argument('--start-time', required=True, help='Start time (ISO format)')
    parser.add_argument('--end-time', required=True, help='End time (ISO format)')
    parser.add_argument('--influxdb-url', required=True, help='InfluxDB URL')
    parser.add_argument('--influxdb-token', required=True, help='InfluxDB token')
    parser.add_argument('--influxdb-org', required=True, help='InfluxDB organization')
    parser.add_argument('--output-file', help='Output file for validation report')
    
    args = parser.parse_args()
    
    validator = DataValidator(
        influxdb_url=args.influxdb_url,
        influxdb_token=args.influxdb_token,
        influxdb_org=args.influxdb_org
    )
    
    start_time = datetime.fromisoformat(args.start_time)
    end_time = datetime.fromisoformat(args.end_time)
    
    result = validator.validate_migration(
        source_database=args.database,
        source_table=args.table,
        target_bucket=args.bucket,
        start_time=start_time,
        end_time=end_time
    )
    
    report = validator.generate_validation_report(result)
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(report)
        print(f"Validation report saved to {args.output_file}")
    else:
        print(report)