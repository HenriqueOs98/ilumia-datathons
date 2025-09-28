"""
Migration Orchestration Lambda Function

This Lambda function coordinates the entire migration process from
Amazon Timestream to InfluxDB using Step Functions, with error handling,
logging, SNS notifications, and rollback capabilities.

Requirements addressed: 2.1, 2.2, 2.3
"""

import json
import logging
import os
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
stepfunctions = boto3.client('stepfunctions')
sns = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')


@dataclass
class MigrationJob:
    """Migration job configuration and status"""
    job_id: str
    job_name: str
    source_database: str
    source_table: str
    target_bucket: str
    start_time: str
    end_time: str
    
    # Status tracking
    status: str = "pending"  # pending, running, completed, failed, cancelled
    current_step: str = "initialization"
    progress_percentage: float = 0.0
    
    # Step Functions execution
    execution_arn: str = ""
    state_machine_arn: str = ""
    
    # Configuration
    batch_size: int = 10000
    validation_enabled: bool = True
    rollback_enabled: bool = True
    notification_topic_arn: str = ""
    
    # Results
    exported_records: int = 0
    validation_results: Dict[str, Any] = None
    error_message: str = ""
    
    # Timestamps
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    
    def __post_init__(self):
        if self.created_at == "":
            self.created_at = datetime.utcnow().isoformat()
        if self.validation_results is None:
            self.validation_results = {}


class MigrationOrchestrator:
    """
    Orchestrate the complete migration process using Step Functions
    """
    
    def __init__(self):
        """Initialize the migration orchestrator"""
        self.state_machine_arn = os.environ.get('MIGRATION_STATE_MACHINE_ARN')
        self.jobs_table_name = os.environ.get('MIGRATION_JOBS_TABLE', 'migration-jobs')
        self.notification_topic_arn = os.environ.get('NOTIFICATION_TOPIC_ARN')
        self.s3_export_bucket = os.environ.get('S3_EXPORT_BUCKET')
        
        # Initialize DynamoDB table
        try:
            self.jobs_table = dynamodb.Table(self.jobs_table_name)
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB table: {str(e)}")
            self.jobs_table = None
    
    def start_migration(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new migration job
        
        Args:
            event: Lambda event containing migration configuration
            
        Returns:
            Dictionary with job details and execution information
        """
        try:
            # Parse migration configuration
            config = event.get('migration_config', {})
            
            # Create migration job
            job = MigrationJob(
                job_id=config.get('job_id', f"migration_{int(datetime.utcnow().timestamp())}"),
                job_name=config.get('job_name', 'Timestream to InfluxDB Migration'),
                source_database=config['source_database'],
                source_table=config['source_table'],
                target_bucket=config['target_bucket'],
                start_time=config['start_time'],
                end_time=config['end_time'],
                batch_size=config.get('batch_size', 10000),
                validation_enabled=config.get('validation_enabled', True),
                rollback_enabled=config.get('rollback_enabled', True),
                notification_topic_arn=config.get('notification_topic_arn', self.notification_topic_arn),
                state_machine_arn=self.state_machine_arn
            )
            
            logger.info(f"Starting migration job: {job.job_id}")
            
            # Save job to DynamoDB
            self._save_job(job)
            
            # Start Step Functions execution
            execution_input = {
                'job_id': job.job_id,
                'source_database': job.source_database,
                'source_table': job.source_table,
                'target_bucket': job.target_bucket,
                'start_time': job.start_time,
                'end_time': job.end_time,
                'batch_size': job.batch_size,
                'validation_enabled': job.validation_enabled,
                'rollback_enabled': job.rollback_enabled,
                's3_export_bucket': self.s3_export_bucket
            }
            
            response = stepfunctions.start_execution(
                stateMachineArn=self.state_machine_arn,
                name=f"{job.job_id}_{int(datetime.utcnow().timestamp())}",
                input=json.dumps(execution_input)
            )
            
            # Update job with execution details
            job.execution_arn = response['executionArn']
            job.status = "running"
            job.started_at = datetime.utcnow().isoformat()
            job.current_step = "export"
            
            self._save_job(job)
            
            # Send notification
            self._send_notification(
                job,
                "Migration Started",
                f"Migration job {job.job_id} has been started successfully."
            )
            
            return {
                'statusCode': 200,
                'body': {
                    'job_id': job.job_id,
                    'execution_arn': job.execution_arn,
                    'status': job.status,
                    'message': 'Migration job started successfully'
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to start migration: {str(e)}")
            logger.error(traceback.format_exc())
            
            return {
                'statusCode': 500,
                'body': {
                    'error': str(e),
                    'message': 'Failed to start migration job'
                }
            }
    
    def handle_step_completion(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle completion of individual migration steps
        
        Args:
            event: Step Functions callback event
            
        Returns:
            Dictionary with updated job status
        """
        try:
            job_id = event.get('job_id')
            step_name = event.get('step_name')
            step_status = event.get('step_status')
            step_results = event.get('step_results', {})
            
            if not job_id:
                raise ValueError("job_id is required")
            
            # Load job from DynamoDB
            job = self._load_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            logger.info(f"Handling step completion: {step_name} for job {job_id}")
            
            # Update job based on step completion
            if step_name == "export":
                self._handle_export_completion(job, step_status, step_results)
            elif step_name == "validation":
                self._handle_validation_completion(job, step_status, step_results)
            elif step_name == "migration":
                self._handle_migration_completion(job, step_status, step_results)
            else:
                logger.warning(f"Unknown step: {step_name}")
            
            # Save updated job
            self._save_job(job)
            
            return {
                'statusCode': 200,
                'body': {
                    'job_id': job_id,
                    'step_name': step_name,
                    'status': job.status,
                    'current_step': job.current_step,
                    'progress': job.progress_percentage
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to handle step completion: {str(e)}")
            logger.error(traceback.format_exc())
            
            return {
                'statusCode': 500,
                'body': {
                    'error': str(e),
                    'message': 'Failed to handle step completion'
                }
            }
    
    def handle_migration_failure(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle migration failure and initiate rollback if enabled
        
        Args:
            event: Failure event from Step Functions
            
        Returns:
            Dictionary with rollback status
        """
        try:
            job_id = event.get('job_id')
            error_details = event.get('error_details', {})
            failed_step = event.get('failed_step', 'unknown')
            
            if not job_id:
                raise ValueError("job_id is required")
            
            # Load job from DynamoDB
            job = self._load_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            logger.error(f"Migration failed for job {job_id} at step {failed_step}")
            
            # Update job status
            job.status = "failed"
            job.current_step = failed_step
            job.error_message = error_details.get('error', 'Unknown error')
            job.completed_at = datetime.utcnow().isoformat()
            
            # Send failure notification
            self._send_notification(
                job,
                "Migration Failed",
                f"Migration job {job_id} failed at step {failed_step}: {job.error_message}"
            )
            
            # Initiate rollback if enabled
            rollback_result = None
            if job.rollback_enabled:
                logger.info(f"Initiating rollback for job {job_id}")
                rollback_result = self._initiate_rollback(job)
            
            self._save_job(job)
            
            return {
                'statusCode': 200,
                'body': {
                    'job_id': job_id,
                    'status': job.status,
                    'error_message': job.error_message,
                    'rollback_initiated': job.rollback_enabled,
                    'rollback_result': rollback_result
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to handle migration failure: {str(e)}")
            logger.error(traceback.format_exc())
            
            return {
                'statusCode': 500,
                'body': {
                    'error': str(e),
                    'message': 'Failed to handle migration failure'
                }
            }
    
    def get_job_status(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the status of a migration job
        
        Args:
            event: Event containing job_id
            
        Returns:
            Dictionary with job status and details
        """
        try:
            job_id = event.get('job_id')
            if not job_id:
                raise ValueError("job_id is required")
            
            job = self._load_job(job_id)
            if not job:
                return {
                    'statusCode': 404,
                    'body': {
                        'error': f"Job {job_id} not found"
                    }
                }
            
            # Get Step Functions execution status if available
            execution_status = None
            if job.execution_arn:
                try:
                    response = stepfunctions.describe_execution(
                        executionArn=job.execution_arn
                    )
                    execution_status = {
                        'status': response['status'],
                        'start_date': response['startDate'].isoformat(),
                        'stop_date': response.get('stopDate', '').isoformat() if response.get('stopDate') else None
                    }
                except Exception as e:
                    logger.warning(f"Could not get execution status: {str(e)}")
            
            return {
                'statusCode': 200,
                'body': {
                    'job': asdict(job),
                    'execution_status': execution_status
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            
            return {
                'statusCode': 500,
                'body': {
                    'error': str(e),
                    'message': 'Failed to get job status'
                }
            }
    
    def cancel_migration(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cancel a running migration job
        
        Args:
            event: Event containing job_id
            
        Returns:
            Dictionary with cancellation status
        """
        try:
            job_id = event.get('job_id')
            if not job_id:
                raise ValueError("job_id is required")
            
            job = self._load_job(job_id)
            if not job:
                return {
                    'statusCode': 404,
                    'body': {
                        'error': f"Job {job_id} not found"
                    }
                }
            
            if job.status not in ['pending', 'running']:
                return {
                    'statusCode': 400,
                    'body': {
                        'error': f"Cannot cancel job in status: {job.status}"
                    }
                }
            
            # Stop Step Functions execution
            if job.execution_arn:
                try:
                    stepfunctions.stop_execution(
                        executionArn=job.execution_arn,
                        error='UserCancelled',
                        cause='Migration cancelled by user'
                    )
                except Exception as e:
                    logger.warning(f"Could not stop execution: {str(e)}")
            
            # Update job status
            job.status = "cancelled"
            job.completed_at = datetime.utcnow().isoformat()
            job.error_message = "Migration cancelled by user"
            
            self._save_job(job)
            
            # Send notification
            self._send_notification(
                job,
                "Migration Cancelled",
                f"Migration job {job_id} has been cancelled."
            )
            
            return {
                'statusCode': 200,
                'body': {
                    'job_id': job_id,
                    'status': job.status,
                    'message': 'Migration job cancelled successfully'
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel migration: {str(e)}")
            
            return {
                'statusCode': 500,
                'body': {
                    'error': str(e),
                    'message': 'Failed to cancel migration job'
                }
            }
    
    def _handle_export_completion(self, job: MigrationJob, status: str, results: Dict[str, Any]):
        """Handle completion of data export step"""
        if status == "success":
            job.current_step = "validation" if job.validation_enabled else "migration"
            job.progress_percentage = 30.0
            job.exported_records = results.get('exported_records', 0)
            
            logger.info(f"Export completed for job {job.job_id}: {job.exported_records} records")
        else:
            job.status = "failed"
            job.error_message = results.get('error', 'Export failed')
            job.completed_at = datetime.utcnow().isoformat()
    
    def _handle_validation_completion(self, job: MigrationJob, status: str, results: Dict[str, Any]):
        """Handle completion of data validation step"""
        job.validation_results = results
        
        if status == "success":
            validation_status = results.get('overall_status', 'unknown')
            
            if validation_status == "passed":
                job.current_step = "migration"
                job.progress_percentage = 60.0
                logger.info(f"Validation passed for job {job.job_id}")
            elif validation_status == "warning":
                job.current_step = "migration"
                job.progress_percentage = 60.0
                logger.warning(f"Validation completed with warnings for job {job.job_id}")
                
                # Send warning notification
                self._send_notification(
                    job,
                    "Validation Warning",
                    f"Migration job {job.job_id} validation completed with warnings. Proceeding with migration."
                )
            else:
                job.status = "failed"
                job.error_message = f"Validation failed: {validation_status}"
                job.completed_at = datetime.utcnow().isoformat()
                logger.error(f"Validation failed for job {job.job_id}")
        else:
            job.status = "failed"
            job.error_message = results.get('error', 'Validation failed')
            job.completed_at = datetime.utcnow().isoformat()
    
    def _handle_migration_completion(self, job: MigrationJob, status: str, results: Dict[str, Any]):
        """Handle completion of data migration step"""
        if status == "success":
            job.status = "completed"
            job.current_step = "completed"
            job.progress_percentage = 100.0
            job.completed_at = datetime.utcnow().isoformat()
            
            logger.info(f"Migration completed successfully for job {job.job_id}")
            
            # Send success notification
            self._send_notification(
                job,
                "Migration Completed",
                f"Migration job {job.job_id} has been completed successfully."
            )
        else:
            job.status = "failed"
            job.error_message = results.get('error', 'Migration failed')
            job.completed_at = datetime.utcnow().isoformat()
    
    def _initiate_rollback(self, job: MigrationJob) -> Dict[str, Any]:
        """Initiate rollback process for failed migration"""
        try:
            # Start rollback Step Functions execution
            rollback_input = {
                'job_id': job.job_id,
                'source_database': job.source_database,
                'source_table': job.source_table,
                'target_bucket': job.target_bucket,
                's3_export_bucket': self.s3_export_bucket
            }
            
            rollback_state_machine = os.environ.get('ROLLBACK_STATE_MACHINE_ARN')
            if rollback_state_machine:
                response = stepfunctions.start_execution(
                    stateMachineArn=rollback_state_machine,
                    name=f"rollback_{job.job_id}_{int(datetime.utcnow().timestamp())}",
                    input=json.dumps(rollback_input)
                )
                
                return {
                    'rollback_execution_arn': response['executionArn'],
                    'status': 'initiated'
                }
            else:
                logger.warning("Rollback state machine not configured")
                return {
                    'status': 'not_configured'
                }
                
        except Exception as e:
            logger.error(f"Failed to initiate rollback: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _save_job(self, job: MigrationJob):
        """Save job to DynamoDB"""
        if not self.jobs_table:
            logger.warning("Jobs table not available")
            return
        
        try:
            self.jobs_table.put_item(Item=asdict(job))
        except Exception as e:
            logger.error(f"Failed to save job: {str(e)}")
    
    def _load_job(self, job_id: str) -> Optional[MigrationJob]:
        """Load job from DynamoDB"""
        if not self.jobs_table:
            logger.warning("Jobs table not available")
            return None
        
        try:
            response = self.jobs_table.get_item(Key={'job_id': job_id})
            if 'Item' in response:
                return MigrationJob(**response['Item'])
            return None
        except Exception as e:
            logger.error(f"Failed to load job: {str(e)}")
            return None
    
    def _send_notification(self, job: MigrationJob, subject: str, message: str):
        """Send SNS notification"""
        if not job.notification_topic_arn:
            return
        
        try:
            sns.publish(
                TopicArn=job.notification_topic_arn,
                Subject=subject,
                Message=json.dumps({
                    'job_id': job.job_id,
                    'job_name': job.job_name,
                    'status': job.status,
                    'current_step': job.current_step,
                    'progress': job.progress_percentage,
                    'message': message,
                    'timestamp': datetime.utcnow().isoformat()
                }, indent=2)
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")


def lambda_handler(event, context):
    """
    Main Lambda handler for migration orchestration
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    orchestrator = MigrationOrchestrator()
    
    # Determine action based on event
    action = event.get('action', 'start_migration')
    
    try:
        if action == 'start_migration':
            return orchestrator.start_migration(event)
        elif action == 'step_completion':
            return orchestrator.handle_step_completion(event)
        elif action == 'migration_failure':
            return orchestrator.handle_migration_failure(event)
        elif action == 'get_status':
            return orchestrator.get_job_status(event)
        elif action == 'cancel_migration':
            return orchestrator.cancel_migration(event)
        else:
            return {
                'statusCode': 400,
                'body': {
                    'error': f"Unknown action: {action}"
                }
            }
    
    except Exception as e:
        logger.error(f"Lambda handler failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'Migration orchestration failed'
            }
        }