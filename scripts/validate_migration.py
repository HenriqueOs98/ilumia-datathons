#!/usr/bin/env python3
"""
Post-Migration Data Validation Script

This script performs comprehensive validation of migrated data between
Timestream and InfluxDB to ensure data integrity and completeness.

Requirements addressed: 2.2, 2.3
"""

import argparse
import boto3
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the migration tools to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from migration_tools.data_validator import DataValidator, ValidationResult, validate_multiple_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration_validation.log')
    ]
)
logger = logging.getLogger(__name__)


class MigrationValidator:
    """
    Comprehensive migration validation orchestrator
    """
    
    def __init__(self, config_file: str = None, region: str = 'us-east-1'):
        """
        Initialize the migration validator
        
        Args:
            config_file: Path to validation configuration file
            region: AWS region
        """
        self.region = region
        self.config = self._load_config(config_file)
        
        # Get InfluxDB connection details
        self.influxdb_url = os.environ.get('INFLUXDB_URL', '')
        self.influxdb_token = os.environ.get('INFLUXDB_TOKEN', '')
        self.influxdb_org = os.environ.get('INFLUXDB_ORG', 'ons-energy')
        
        # Initialize validator
        self.validator = DataValidator(
            timestream_region=region,
            influxdb_url=self.influxdb_url,
            influxdb_token=self.influxdb_token,
            influxdb_org=self.influxdb_org,
            sample_size=self.config.get('validation_settings', {}).get('sample_size', 1000)
        )
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load validation configuration"""
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        
        # Default configuration
        return {
            "validation_tables": [
                {
                    "database": "ons_energy_data",
                    "table": "generation_data",
                    "bucket": "generation_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "description": "Power generation metrics validation"
                },
                {
                    "database": "ons_energy_data",
                    "table": "consumption_data",
                    "bucket": "consumption_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "description": "Energy consumption data validation"
                },
                {
                    "database": "ons_energy_data",
                    "table": "transmission_data",
                    "bucket": "transmission_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "description": "Grid transmission statistics validation"
                }
            ],
            "validation_settings": {
                "sample_size": 1000,
                "parallel_validations": 3,
                "timeout_minutes": 30,
                "detailed_reporting": True,
                "save_results": True
            },
            "validation_rules": {
                "record_count_tolerance": 0.001,
                "sample_accuracy_threshold": 0.95,
                "checksum_validation_enabled": True,
                "schema_validation_enabled": True,
                "time_range_validation_enabled": True
            },
            "reporting": {
                "generate_html_report": True,
                "generate_json_report": True,
                "send_email_report": False,
                "email_recipients": []
            }
        }
    
    def validate_all_tables(self, parallel: bool = True) -> Dict[str, Any]:
        """
        Validate all configured tables
        
        Args:
            parallel: Whether to run validations in parallel
            
        Returns:
            Dictionary with validation results summary
        """
        logger.info("Starting comprehensive migration validation")
        
        tables_config = self.config['validation_tables']
        validation_settings = self.config['validation_settings']
        
        start_time = datetime.utcnow()
        
        if parallel and validation_settings.get('parallel_validations', 1) > 1:
            results = self._validate_tables_parallel(tables_config)
        else:
            results = self._validate_tables_sequential(tables_config)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Generate summary
        summary = self._generate_validation_summary(results, duration)
        
        # Save results if configured
        if validation_settings.get('save_results', True):
            self._save_validation_results(summary)
        
        # Generate reports if configured
        reporting_config = self.config.get('reporting', {})
        if reporting_config.get('generate_html_report', True):
            self._generate_html_report(summary)
        
        if reporting_config.get('generate_json_report', True):
            self._generate_json_report(summary)
        
        logger.info(f"Validation completed in {duration:.2f} seconds")
        return summary
    
    def _validate_tables_sequential(self, tables_config: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Validate tables sequentially"""
        logger.info(f"Validating {len(tables_config)} tables sequentially")
        
        results = []
        
        for i, table_config in enumerate(tables_config):
            logger.info(f"Validating table {i+1}/{len(tables_config)}: {table_config['database']}.{table_config['table']}")
            
            try:
                result = self.validator.validate_migration(
                    source_database=table_config['database'],
                    source_table=table_config['table'],
                    target_bucket=table_config['bucket'],
                    start_time=datetime.fromisoformat(table_config['start_time'].replace('Z', '+00:00')),
                    end_time=datetime.fromisoformat(table_config['end_time'].replace('Z', '+00:00'))
                )
                
                results.append(result)
                logger.info(f"Validation completed for {table_config['database']}.{table_config['table']}: {result.overall_status}")
                
            except Exception as e:
                logger.error(f"Validation failed for {table_config['database']}.{table_config['table']}: {str(e)}")
                
                # Create error result
                error_result = ValidationResult(
                    validation_id=f"error_{table_config['database']}_{table_config['table']}",
                    source_database=table_config['database'],
                    source_table=table_config['table'],
                    target_bucket=table_config['bucket'],
                    start_time=table_config['start_time'],
                    end_time=table_config['end_time'],
                    overall_status='failed'
                )
                error_result.validation_errors.append(f"Validation exception: {str(e)}")
                results.append(error_result)
        
        return results
    
    def _validate_tables_parallel(self, tables_config: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Validate tables in parallel"""
        max_workers = self.config['validation_settings'].get('parallel_validations', 3)
        logger.info(f"Validating {len(tables_config)} tables with {max_workers} parallel workers")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all validation tasks
            future_to_config = {}
            
            for table_config in tables_config:
                future = executor.submit(
                    self.validator.validate_migration,
                    table_config['database'],
                    table_config['table'],
                    table_config['bucket'],
                    datetime.fromisoformat(table_config['start_time'].replace('Z', '+00:00')),
                    datetime.fromisoformat(table_config['end_time'].replace('Z', '+00:00'))
                )
                future_to_config[future] = table_config
            
            # Collect results as they complete
            for future in as_completed(future_to_config):
                table_config = future_to_config[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Validation completed for {table_config['database']}.{table_config['table']}: {result.overall_status}")
                    
                except Exception as e:
                    logger.error(f"Validation failed for {table_config['database']}.{table_config['table']}: {str(e)}")
                    
                    # Create error result
                    error_result = ValidationResult(
                        validation_id=f"error_{table_config['database']}_{table_config['table']}",
                        source_database=table_config['database'],
                        source_table=table_config['table'],
                        target_bucket=table_config['bucket'],
                        start_time=table_config['start_time'],
                        end_time=table_config['end_time'],
                        overall_status='failed'
                    )
                    error_result.validation_errors.append(f"Validation exception: {str(e)}")
                    results.append(error_result)
        
        return results
    
    def _generate_validation_summary(self, results: List[ValidationResult], duration: float) -> Dict[str, Any]:
        """Generate validation summary"""
        total_validations = len(results)
        passed_validations = len([r for r in results if r.overall_status == 'passed'])
        failed_validations = len([r for r in results if r.overall_status == 'failed'])
        warning_validations = len([r for r in results if r.overall_status == 'warning'])
        
        total_source_records = sum(r.source_record_count for r in results)
        total_target_records = sum(r.target_record_count for r in results)
        
        # Calculate overall status
        if failed_validations > 0:
            overall_status = 'failed'
        elif warning_validations > 0:
            overall_status = 'warning'
        else:
            overall_status = 'passed'
        
        summary = {
            'validation_summary': {
                'overall_status': overall_status,
                'total_validations': total_validations,
                'passed_validations': passed_validations,
                'failed_validations': failed_validations,
                'warning_validations': warning_validations,
                'validation_duration_seconds': duration,
                'total_source_records': total_source_records,
                'total_target_records': total_target_records,
                'record_count_match': total_source_records == total_target_records,
                'validation_timestamp': datetime.utcnow().isoformat()
            },
            'detailed_results': [self._result_to_dict(r) for r in results],
            'configuration': self.config
        }
        
        return summary
    
    def _result_to_dict(self, result: ValidationResult) -> Dict[str, Any]:
        """Convert ValidationResult to dictionary"""
        return {
            'validation_id': result.validation_id,
            'source_database': result.source_database,
            'source_table': result.source_table,
            'target_bucket': result.target_bucket,
            'start_time': result.start_time,
            'end_time': result.end_time,
            'overall_status': result.overall_status,
            'source_record_count': result.source_record_count,
            'target_record_count': result.target_record_count,
            'count_match': result.count_match,
            'sample_accuracy': result.sample_accuracy,
            'checksum_match': result.checksum_match,
            'time_range_match': result.time_range_match,
            'validation_errors': result.validation_errors,
            'validation_warnings': result.validation_warnings,
            'validation_duration_seconds': result.validation_duration_seconds,
            'validation_timestamp': result.validation_timestamp
        }
    
    def _save_validation_results(self, summary: Dict[str, Any]):
        """Save validation results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"migration_validation_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        logger.info(f"Validation results saved to: {filename}")
    
    def _generate_html_report(self, summary: Dict[str, Any]):
        """Generate HTML validation report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"migration_validation_report_{timestamp}.html"
        
        html_content = self._create_html_report(summary)
        
        with open(filename, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML validation report generated: {filename}")
    
    def _generate_json_report(self, summary: Dict[str, Any]):
        """Generate JSON validation report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"migration_validation_report_{timestamp}.json"
        
        # Create simplified report
        report = {
            'report_metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'report_type': 'migration_validation',
                'version': '1.0'
            },
            'executive_summary': summary['validation_summary'],
            'table_results': []
        }
        
        for result in summary['detailed_results']:
            table_result = {
                'table': f"{result['source_database']}.{result['source_table']}",
                'status': result['overall_status'],
                'record_counts': {
                    'source': result['source_record_count'],
                    'target': result['target_record_count'],
                    'match': result['count_match']
                },
                'validation_metrics': {
                    'sample_accuracy': result['sample_accuracy'],
                    'checksum_match': result['checksum_match'],
                    'time_range_match': result['time_range_match']
                },
                'issues': {
                    'errors': result['validation_errors'],
                    'warnings': result['validation_warnings']
                }
            }
            report['table_results'].append(table_result)
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"JSON validation report generated: {filename}")
    
    def _create_html_report(self, summary: Dict[str, Any]) -> str:
        """Create HTML validation report"""
        validation_summary = summary['validation_summary']
        detailed_results = summary['detailed_results']
        
        # Determine status color
        status_colors = {
            'passed': '#28a745',
            'warning': '#ffc107',
            'failed': '#dc3545'
        }
        status_color = status_colors.get(validation_summary['overall_status'], '#6c757d')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Migration Validation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
        .status {{ color: {status_color}; font-weight: bold; font-size: 1.2em; }}
        .summary {{ margin: 20px 0; }}
        .table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .table th {{ background-color: #f2f2f2; }}
        .passed {{ color: #28a745; }}
        .warning {{ color: #ffc107; }}
        .failed {{ color: #dc3545; }}
        .details {{ margin: 10px 0; }}
        .error {{ color: #dc3545; font-size: 0.9em; }}
        .warning-text {{ color: #ffc107; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Migration Validation Report</h1>
        <p>Generated: {validation_summary['validation_timestamp']}</p>
        <p class="status">Overall Status: {validation_summary['overall_status'].upper()}</p>
    </div>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <table class="table">
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Validations</td><td>{validation_summary['total_validations']}</td></tr>
            <tr><td>Passed</td><td class="passed">{validation_summary['passed_validations']}</td></tr>
            <tr><td>Warnings</td><td class="warning">{validation_summary['warning_validations']}</td></tr>
            <tr><td>Failed</td><td class="failed">{validation_summary['failed_validations']}</td></tr>
            <tr><td>Total Source Records</td><td>{validation_summary['total_source_records']:,}</td></tr>
            <tr><td>Total Target Records</td><td>{validation_summary['total_target_records']:,}</td></tr>
            <tr><td>Record Count Match</td><td>{'✓' if validation_summary['record_count_match'] else '✗'}</td></tr>
            <tr><td>Validation Duration</td><td>{validation_summary['validation_duration_seconds']:.2f} seconds</td></tr>
        </table>
    </div>
    
    <div class="details">
        <h2>Detailed Results</h2>
        <table class="table">
            <tr>
                <th>Table</th>
                <th>Status</th>
                <th>Source Records</th>
                <th>Target Records</th>
                <th>Count Match</th>
                <th>Sample Accuracy</th>
                <th>Issues</th>
            </tr>
        """
        
        for result in detailed_results:
            status_class = result['overall_status']
            count_match_icon = '✓' if result['count_match'] else '✗'
            
            issues_html = ""
            if result['validation_errors']:
                issues_html += f"<div class='error'>Errors: {len(result['validation_errors'])}</div>"
            if result['validation_warnings']:
                issues_html += f"<div class='warning-text'>Warnings: {len(result['validation_warnings'])}</div>"
            
            html += f"""
            <tr>
                <td>{result['source_database']}.{result['source_table']}</td>
                <td class="{status_class}">{result['overall_status'].upper()}</td>
                <td>{result['source_record_count']:,}</td>
                <td>{result['target_record_count']:,}</td>
                <td>{count_match_icon}</td>
                <td>{result['sample_accuracy']:.2%}</td>
                <td>{issues_html}</td>
            </tr>
            """
        
        html += """
        </table>
    </div>
    
    <div class="details">
        <h2>Error Details</h2>
        """
        
        for result in detailed_results:
            if result['validation_errors'] or result['validation_warnings']:
                html += f"""
                <h3>{result['source_database']}.{result['source_table']}</h3>
                """
                
                if result['validation_errors']:
                    html += "<h4>Errors:</h4><ul>"
                    for error in result['validation_errors']:
                        html += f"<li class='error'>{error}</li>"
                    html += "</ul>"
                
                if result['validation_warnings']:
                    html += "<h4>Warnings:</h4><ul>"
                    for warning in result['validation_warnings']:
                        html += f"<li class='warning-text'>{warning}</li>"
                    html += "</ul>"
        
        html += """
    </div>
</body>
</html>
        """
        
        return html
    
    def validate_single_table(self, database: str, table: str, bucket: str, 
                            start_time: str, end_time: str) -> ValidationResult:
        """Validate a single table migration"""
        logger.info(f"Validating single table: {database}.{table}")
        
        result = self.validator.validate_migration(
            source_database=database,
            source_table=table,
            target_bucket=bucket,
            start_time=datetime.fromisoformat(start_time.replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        )
        
        # Generate and display report
        report = self.validator.generate_validation_report(result)
        print(report)
        
        return result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Validate Timestream to InfluxDB migration')
    parser.add_argument('--config', help='Validation configuration file (JSON or YAML)')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--database', help='Single database to validate')
    parser.add_argument('--table', help='Single table to validate')
    parser.add_argument('--bucket', help='InfluxDB bucket name')
    parser.add_argument('--start-time', help='Start time (ISO format)')
    parser.add_argument('--end-time', help='End time (ISO format)')
    parser.add_argument('--parallel', action='store_true', help='Run validations in parallel')
    parser.add_argument('--no-reports', action='store_true', help='Skip report generation')
    
    args = parser.parse_args()
    
    # Initialize validator
    validator = MigrationValidator(config_file=args.config, region=args.region)
    
    try:
        if args.database and args.table and args.bucket and args.start_time and args.end_time:
            # Validate single table
            result = validator.validate_single_table(
                database=args.database,
                table=args.table,
                bucket=args.bucket,
                start_time=args.start_time,
                end_time=args.end_time
            )
            
            # Exit with appropriate code
            sys.exit(0 if result.overall_status in ['passed', 'warning'] else 1)
            
        else:
            # Validate all configured tables
            summary = validator.validate_all_tables(parallel=args.parallel)
            
            # Print summary
            validation_summary = summary['validation_summary']
            print("\n" + "="*60)
            print("MIGRATION VALIDATION SUMMARY")
            print("="*60)
            print(f"Overall Status: {validation_summary['overall_status'].upper()}")
            print(f"Total Validations: {validation_summary['total_validations']}")
            print(f"Passed: {validation_summary['passed_validations']}")
            print(f"Warnings: {validation_summary['warning_validations']}")
            print(f"Failed: {validation_summary['failed_validations']}")
            print(f"Total Source Records: {validation_summary['total_source_records']:,}")
            print(f"Total Target Records: {validation_summary['total_target_records']:,}")
            print(f"Record Count Match: {'✓' if validation_summary['record_count_match'] else '✗'}")
            print(f"Duration: {validation_summary['validation_duration_seconds']:.2f} seconds")
            print("="*60)
            
            # Exit with appropriate code
            overall_status = validation_summary['overall_status']
            sys.exit(0 if overall_status in ['passed', 'warning'] else 1)
            
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()