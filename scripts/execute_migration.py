#!/usr/bin/env python3
"""
Execute Timestream to InfluxDB Data Migration

This script coordinates the execution of the complete data migration process
from Amazon Timestream to InfluxDB using the existing migration infrastructure.

Requirements addressed: 2.1, 2.2, 2.3
"""

import argparse
import boto3
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration_execution.log')
    ]
)
logger = logging.getLogger(__name__)


class MigrationExecutor:
    """
    Execute the complete Timestream to InfluxDB migration process
    """
    
    def __init__(self, config_file: str = None, region: str = 'us-east-1'):
        """
        Initialize the migration executor
        
        Args:
            config_file: Path to migration configuration file
            region: AWS region
        """
        self.region = region
        self.config = self._load_config(config_file)
        
        # Initialize AWS clients
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.stepfunctions_client = boto3.client('stepfunctions', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Get infrastructure details from Terraform outputs
        self._load_infrastructure_details()
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load migration configuration"""
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        
        # Default configuration
        return {
            "migration_jobs": [
                {
                    "job_name": "Generation Data Migration",
                    "source_database": "ons_energy_data",
                    "source_table": "generation_data",
                    "target_bucket": "generation_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "batch_size": 10000,
                    "validation_enabled": True,
                    "rollback_enabled": True
                },
                {
                    "job_name": "Consumption Data Migration",
                    "source_database": "ons_energy_data",
                    "source_table": "consumption_data",
                    "target_bucket": "consumption_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "batch_size": 10000,
                    "validation_enabled": True,
                    "rollback_enabled": True
                },
                {
                    "job_name": "Transmission Data Migration",
                    "source_database": "ons_energy_data",
                    "source_table": "transmission_data",
                    "target_bucket": "transmission_data",
                    "start_time": "2023-01-01T00:00:00Z",
                    "end_time": "2024-12-31T23:59:59Z",
                    "batch_size": 10000,
                    "validation_enabled": True,
                    "rollback_enabled": True
                }
            ],
            "migration_settings": {
                "parallel_jobs": 2,
                "notification_topic_arn": "",
                "s3_export_bucket": "",
                "progress_monitoring_interval": 60,
                "max_retry_attempts": 3,
                "retry_delay_seconds": 300
            }
        }
    
    def _load_infrastructure_details(self):
        """Load infrastructure details from Terraform outputs"""
        try:
            # Try to get Terraform outputs
            import subprocess
            result = subprocess.run(
                ['terraform', 'output', '-json'],
                cwd='infra',
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                outputs = json.loads(result.stdout)
                
                # Extract relevant infrastructure details
                self.migration_orchestrator_arn = outputs.get('migration_orchestrator_lambda_arn', {}).get('value', '')
                self.migration_state_machine_arn = outputs.get('migration_state_machine_arn', {}).get('value', '')
                self.s3_export_bucket = outputs.get('migration_export_bucket', {}).get('value', '')
                self.notification_topic_arn = outputs.get('migration_notification_topic_arn', {}).get('value', '')
                
                logger.info("Loaded infrastructure details from Terraform outputs")
            else:
                logger.warning("Could not load Terraform outputs, using environment variables")
                self._load_from_environment()
                
        except Exception as e:
            logger.warning(f"Could not load Terraform outputs: {str(e)}, using environment variables")
            self._load_from_environment()
    
    def _load_from_environment(self):
        """Load infrastructure details from environment variables"""
        self.migration_orchestrator_arn = os.environ.get('MIGRATION_ORCHESTRATOR_LAMBDA_ARN', '')
        self.migration_state_machine_arn = os.environ.get('MIGRATION_STATE_MACHINE_ARN', '')
        self.s3_export_bucket = os.environ.get('S3_EXPORT_BUCKET', '')
        self.notification_topic_arn = os.environ.get('NOTIFICATION_TOPIC_ARN', '')
        
        # Update config with environment values
        if self.s3_export_bucket:
            self.config['migration_settings']['s3_export_bucket'] = self.s3_export_bucket
        if self.notification_topic_arn:
            self.config['migration_settings']['notification_topic_arn'] = self.notification_topic_arn
    
    def execute_migration(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the complete migration process
        
        Args:
            dry_run: If True, validate configuration without executing migration
            
        Returns:
            Dictionary with migration execution results
        """
        logger.info("Starting Timestream to InfluxDB migration execution")
        
        if dry_run:
            logger.info("DRY RUN MODE - Validating configuration only")
            return self._validate_configuration()
        
        # Validate prerequisites
        validation_result = self._validate_prerequisites()
        if not validation_result['valid']:
            logger.error("Prerequisites validation failed")
            return {
                'status': 'failed',
                'error': 'Prerequisites validation failed',
                'details': validation_result
            }
        
        # Execute migration jobs
        migration_results = []
        jobs = self.config['migration_jobs']
        parallel_jobs = self.config['migration_settings'].get('parallel_jobs', 1)
        
        if parallel_jobs > 1:
            migration_results = self._execute_parallel_migrations(jobs, parallel_jobs)
        else:
            migration_results = self._execute_sequential_migrations(jobs)
        
        # Generate summary report
        summary = self._generate_migration_summary(migration_results)
        
        logger.info(f"Migration execution completed with status: {summary['overall_status']}")
        return summary
    
    def _validate_configuration(self) -> Dict[str, Any]:
        """Validate migration configuration"""
        logger.info("Validating migration configuration...")
        
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'jobs_validated': 0
        }
        
        # Validate migration jobs
        for i, job in enumerate(self.config['migration_jobs']):
            job_errors = []
            
            # Required fields
            required_fields = ['job_name', 'source_database', 'source_table', 'target_bucket', 'start_time', 'end_time']
            for field in required_fields:
                if not job.get(field):
                    job_errors.append(f"Missing required field: {field}")
            
            # Validate time format
            try:
                datetime.fromisoformat(job['start_time'].replace('Z', '+00:00'))
                datetime.fromisoformat(job['end_time'].replace('Z', '+00:00'))
            except (ValueError, KeyError) as e:
                job_errors.append(f"Invalid time format: {str(e)}")
            
            # Validate batch size
            batch_size = job.get('batch_size', 10000)
            if not isinstance(batch_size, int) or batch_size <= 0:
                job_errors.append("Invalid batch_size: must be positive integer")
            
            if job_errors:
                validation_results['errors'].extend([f"Job {i+1} ({job.get('job_name', 'Unknown')}): {error}" for error in job_errors])
                validation_results['valid'] = False
            else:
                validation_results['jobs_validated'] += 1
        
        # Validate infrastructure
        if not self.migration_orchestrator_arn:
            validation_results['errors'].append("Migration orchestrator Lambda ARN not found")
            validation_results['valid'] = False
        
        if not self.migration_state_machine_arn:
            validation_results['errors'].append("Migration state machine ARN not found")
            validation_results['valid'] = False
        
        if not self.config['migration_settings'].get('s3_export_bucket'):
            validation_results['warnings'].append("S3 export bucket not configured")
        
        logger.info(f"Configuration validation completed: {validation_results['jobs_validated']} jobs validated")
        
        return validation_results
    
    def _validate_prerequisites(self) -> Dict[str, Any]:
        """Validate migration prerequisites"""
        logger.info("Validating migration prerequisites...")
        
        validation_result = {
            'valid': True,
            'checks': {}
        }
        
        # Check Lambda function exists and is accessible
        try:
            response = self.lambda_client.get_function(FunctionName=self.migration_orchestrator_arn)
            validation_result['checks']['orchestrator_lambda'] = {
                'status': 'passed',
                'details': f"Function found: {response['Configuration']['FunctionName']}"
            }
        except Exception as e:
            validation_result['valid'] = False
            validation_result['checks']['orchestrator_lambda'] = {
                'status': 'failed',
                'details': f"Cannot access orchestrator Lambda: {str(e)}"
            }
        
        # Check Step Functions state machine exists
        try:
            response = self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.migration_state_machine_arn
            )
            validation_result['checks']['state_machine'] = {
                'status': 'passed',
                'details': f"State machine found: {response['name']}"
            }
        except Exception as e:
            validation_result['valid'] = False
            validation_result['checks']['state_machine'] = {
                'status': 'failed',
                'details': f"Cannot access state machine: {str(e)}"
            }
        
        # Check S3 export bucket access
        s3_bucket = self.config['migration_settings'].get('s3_export_bucket')
        if s3_bucket:
            try:
                s3_client = boto3.client('s3', region_name=self.region)
                s3_client.head_bucket(Bucket=s3_bucket)
                validation_result['checks']['s3_export_bucket'] = {
                    'status': 'passed',
                    'details': f"S3 bucket accessible: {s3_bucket}"
                }
            except Exception as e:
                validation_result['valid'] = False
                validation_result['checks']['s3_export_bucket'] = {
                    'status': 'failed',
                    'details': f"Cannot access S3 bucket {s3_bucket}: {str(e)}"
                }
        
        return validation_result
    
    def _execute_sequential_migrations(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute migration jobs sequentially"""
        logger.info(f"Executing {len(jobs)} migration jobs sequentially")
        
        results = []
        
        for i, job in enumerate(jobs):
            logger.info(f"Starting migration job {i+1}/{len(jobs)}: {job['job_name']}")
            
            result = self._execute_single_migration(job)
            results.append(result)
            
            # Stop on failure if rollback is not enabled
            if result['status'] == 'failed' and not job.get('rollback_enabled', True):
                logger.error(f"Migration job failed and rollback is disabled. Stopping execution.")
                break
            
            # Add delay between jobs
            if i < len(jobs) - 1:
                time.sleep(30)
        
        return results
    
    def _execute_parallel_migrations(self, jobs: List[Dict[str, Any]], max_parallel: int) -> List[Dict[str, Any]]:
        """Execute migration jobs in parallel"""
        logger.info(f"Executing {len(jobs)} migration jobs with max {max_parallel} parallel")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self._execute_single_migration, job): job 
                for job in jobs
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Completed migration job: {job['job_name']} - Status: {result['status']}")
                except Exception as e:
                    logger.error(f"Migration job failed: {job['job_name']} - Error: {str(e)}")
                    results.append({
                        'job_name': job['job_name'],
                        'status': 'failed',
                        'error': str(e),
                        'job_id': None
                    })
        
        return results
    
    def _execute_single_migration(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single migration job"""
        job_id = f"migration_{job['source_database']}_{job['source_table']}_{int(time.time())}"
        
        try:
            # Prepare migration configuration
            migration_config = {
                'job_id': job_id,
                'job_name': job['job_name'],
                'source_database': job['source_database'],
                'source_table': job['source_table'],
                'target_bucket': job['target_bucket'],
                'start_time': job['start_time'],
                'end_time': job['end_time'],
                'batch_size': job.get('batch_size', 10000),
                'validation_enabled': job.get('validation_enabled', True),
                'rollback_enabled': job.get('rollback_enabled', True),
                'notification_topic_arn': self.config['migration_settings'].get('notification_topic_arn', ''),
                's3_export_bucket': self.config['migration_settings'].get('s3_export_bucket', '')
            }
            
            # Start migration via orchestrator Lambda
            response = self.lambda_client.invoke(
                FunctionName=self.migration_orchestrator_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'start_migration',
                    'migration_config': migration_config
                })
            )
            
            # Parse response
            payload = json.loads(response['Payload'].read())
            
            if payload.get('statusCode') == 200:
                body = payload.get('body', {})
                execution_arn = body.get('execution_arn')
                
                logger.info(f"Migration job started: {job_id} - Execution ARN: {execution_arn}")
                
                # Monitor migration progress
                result = self._monitor_migration_progress(job_id, execution_arn)
                result['job_name'] = job['job_name']
                result['job_id'] = job_id
                
                return result
            else:
                error_msg = payload.get('body', {}).get('error', 'Unknown error')
                logger.error(f"Failed to start migration job {job_id}: {error_msg}")
                
                return {
                    'job_name': job['job_name'],
                    'job_id': job_id,
                    'status': 'failed',
                    'error': error_msg
                }
        
        except Exception as e:
            logger.error(f"Exception during migration job {job_id}: {str(e)}")
            return {
                'job_name': job['job_name'],
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            }
    
    def _monitor_migration_progress(self, job_id: str, execution_arn: str) -> Dict[str, Any]:
        """Monitor migration progress until completion"""
        logger.info(f"Monitoring migration progress for job {job_id}")
        
        monitoring_interval = self.config['migration_settings'].get('progress_monitoring_interval', 60)
        max_wait_time = 3600 * 4  # 4 hours maximum
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                # Get job status from orchestrator
                response = self.lambda_client.invoke(
                    FunctionName=self.migration_orchestrator_arn,
                    InvocationType='RequestResponse',
                    Payload=json.dumps({
                        'action': 'get_status',
                        'job_id': job_id
                    })
                )
                
                payload = json.loads(response['Payload'].read())
                
                if payload.get('statusCode') == 200:
                    job_data = payload.get('body', {}).get('job', {})
                    status = job_data.get('status', 'unknown')
                    current_step = job_data.get('current_step', 'unknown')
                    progress = job_data.get('progress_percentage', 0.0)
                    
                    logger.info(f"Job {job_id} - Status: {status}, Step: {current_step}, Progress: {progress:.1f}%")
                    
                    # Check if migration is complete
                    if status in ['completed', 'failed', 'cancelled']:
                        logger.info(f"Migration job {job_id} finished with status: {status}")
                        
                        return {
                            'status': status,
                            'current_step': current_step,
                            'progress_percentage': progress,
                            'exported_records': job_data.get('exported_records', 0),
                            'validation_results': job_data.get('validation_results', {}),
                            'error_message': job_data.get('error_message', ''),
                            'execution_arn': execution_arn,
                            'duration_seconds': elapsed_time
                        }
                
                # Wait before next check
                time.sleep(monitoring_interval)
                elapsed_time += monitoring_interval
                
            except Exception as e:
                logger.warning(f"Error monitoring job {job_id}: {str(e)}")
                time.sleep(monitoring_interval)
                elapsed_time += monitoring_interval
        
        # Timeout reached
        logger.error(f"Migration monitoring timeout reached for job {job_id}")
        return {
            'status': 'timeout',
            'error_message': f'Monitoring timeout after {max_wait_time} seconds',
            'execution_arn': execution_arn,
            'duration_seconds': elapsed_time
        }
    
    def _generate_migration_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate migration execution summary"""
        total_jobs = len(results)
        completed_jobs = len([r for r in results if r['status'] == 'completed'])
        failed_jobs = len([r for r in results if r['status'] == 'failed'])
        
        total_records = sum(r.get('exported_records', 0) for r in results)
        
        overall_status = 'completed' if failed_jobs == 0 else 'partial' if completed_jobs > 0 else 'failed'
        
        summary = {
            'overall_status': overall_status,
            'total_jobs': total_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'total_exported_records': total_records,
            'execution_timestamp': datetime.utcnow().isoformat(),
            'job_results': results
        }
        
        return summary
    
    def get_migration_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a specific migration job"""
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.migration_orchestrator_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'get_status',
                    'job_id': job_id
                })
            )
            
            payload = json.loads(response['Payload'].read())
            return payload.get('body', {})
            
        except Exception as e:
            logger.error(f"Failed to get migration status: {str(e)}")
            return {'error': str(e)}
    
    def cancel_migration(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running migration job"""
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.migration_orchestrator_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'cancel_migration',
                    'job_id': job_id
                })
            )
            
            payload = json.loads(response['Payload'].read())
            return payload.get('body', {})
            
        except Exception as e:
            logger.error(f"Failed to cancel migration: {str(e)}")
            return {'error': str(e)}


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Execute Timestream to InfluxDB migration')
    parser.add_argument('--config', help='Migration configuration file (JSON or YAML)')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--dry-run', action='store_true', help='Validate configuration without executing')
    parser.add_argument('--job-id', help='Get status of specific job')
    parser.add_argument('--cancel-job', help='Cancel specific job')
    parser.add_argument('--parallel-jobs', type=int, help='Number of parallel migration jobs')
    
    args = parser.parse_args()
    
    # Initialize executor
    executor = MigrationExecutor(config_file=args.config, region=args.region)
    
    # Override parallel jobs if specified
    if args.parallel_jobs:
        executor.config['migration_settings']['parallel_jobs'] = args.parallel_jobs
    
    try:
        if args.job_id:
            # Get job status
            result = executor.get_migration_status(args.job_id)
            print(json.dumps(result, indent=2))
            
        elif args.cancel_job:
            # Cancel job
            result = executor.cancel_migration(args.cancel_job)
            print(json.dumps(result, indent=2))
            
        else:
            # Execute migration
            result = executor.execute_migration(dry_run=args.dry_run)
            
            # Print summary
            print("\n" + "="*60)
            print("MIGRATION EXECUTION SUMMARY")
            print("="*60)
            print(f"Overall Status: {result['overall_status'].upper()}")
            print(f"Total Jobs: {result.get('total_jobs', 0)}")
            print(f"Completed Jobs: {result.get('completed_jobs', 0)}")
            print(f"Failed Jobs: {result.get('failed_jobs', 0)}")
            print(f"Total Records Exported: {result.get('total_exported_records', 0):,}")
            print(f"Execution Time: {result.get('execution_timestamp', 'Unknown')}")
            
            if result.get('job_results'):
                print("\nJob Details:")
                for job_result in result['job_results']:
                    status_icon = "✓" if job_result['status'] == 'completed' else "✗"
                    print(f"  {status_icon} {job_result['job_name']}: {job_result['status']}")
                    if job_result.get('error'):
                        print(f"    Error: {job_result['error']}")
            
            # Save detailed results
            output_file = f"migration_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\nDetailed results saved to: {output_file}")
            
            # Exit with appropriate code
            sys.exit(0 if result['overall_status'] in ['completed', 'partial'] else 1)
            
    except KeyboardInterrupt:
        logger.info("Migration execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()