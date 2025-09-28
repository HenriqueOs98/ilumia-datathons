#!/usr/bin/env python3
"""
Migration Progress Monitor

This script provides real-time monitoring of Timestream to InfluxDB migration progress
with detailed status reporting, progress visualization, and alerting capabilities.

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
import threading
from dataclasses import dataclass
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MigrationJobStatus:
    """Migration job status information"""
    job_id: str
    job_name: str
    status: str
    current_step: str
    progress_percentage: float
    exported_records: int
    validation_results: Dict[str, Any]
    error_message: str
    started_at: str
    last_updated: str
    execution_arn: str


class MigrationMonitor:
    """
    Monitor migration progress with real-time updates and alerting
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize the migration monitor
        
        Args:
            region: AWS region
        """
        self.region = region
        self.running = False
        self.job_statuses = {}
        
        # Initialize AWS clients
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.stepfunctions_client = boto3.client('stepfunctions', region_name=region)
        self.sns_client = boto3.client('sns', region_name=region)
        
        # Get infrastructure details
        self.migration_orchestrator_arn = os.environ.get('MIGRATION_ORCHESTRATOR_LAMBDA_ARN', '')
        self.notification_topic_arn = os.environ.get('NOTIFICATION_TOPIC_ARN', '')
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal, stopping monitor...")
        self.running = False
    
    def monitor_jobs(self, job_ids: List[str], update_interval: int = 30, max_duration: int = 14400):
        """
        Monitor multiple migration jobs
        
        Args:
            job_ids: List of job IDs to monitor
            update_interval: Seconds between status updates
            max_duration: Maximum monitoring duration in seconds (default 4 hours)
        """
        logger.info(f"Starting migration monitoring for {len(job_ids)} jobs")
        logger.info(f"Update interval: {update_interval} seconds")
        logger.info(f"Maximum monitoring duration: {max_duration} seconds")
        
        self.running = True
        start_time = datetime.utcnow()
        
        # Initialize job statuses
        for job_id in job_ids:
            self.job_statuses[job_id] = None
        
        # Start monitoring loop
        while self.running:
            current_time = datetime.utcnow()
            elapsed_seconds = (current_time - start_time).total_seconds()
            
            # Check if maximum duration exceeded
            if elapsed_seconds > max_duration:
                logger.warning(f"Maximum monitoring duration ({max_duration}s) exceeded")
                break
            
            # Update job statuses
            self._update_job_statuses(job_ids)
            
            # Display status summary
            self._display_status_summary()
            
            # Check for completion
            if self._all_jobs_completed():
                logger.info("All migration jobs completed")
                break
            
            # Wait for next update
            time.sleep(update_interval)
        
        # Final status report
        self._generate_final_report()
    
    def monitor_single_job(self, job_id: str, update_interval: int = 30, max_duration: int = 14400):
        """
        Monitor a single migration job with detailed progress
        
        Args:
            job_id: Job ID to monitor
            update_interval: Seconds between status updates
            max_duration: Maximum monitoring duration in seconds
        """
        logger.info(f"Starting detailed monitoring for job: {job_id}")
        
        self.running = True
        start_time = datetime.utcnow()
        previous_status = None
        
        while self.running:
            current_time = datetime.utcnow()
            elapsed_seconds = (current_time - start_time).total_seconds()
            
            # Check if maximum duration exceeded
            if elapsed_seconds > max_duration:
                logger.warning(f"Maximum monitoring duration ({max_duration}s) exceeded")
                break
            
            # Get job status
            status = self._get_job_status(job_id)
            
            if status:
                # Display detailed status if changed
                if not previous_status or self._status_changed(previous_status, status):
                    self._display_detailed_status(status)
                    previous_status = status
                
                # Check for completion
                if status.status in ['completed', 'failed', 'cancelled']:
                    logger.info(f"Job {job_id} finished with status: {status.status}")
                    break
            else:
                logger.warning(f"Could not retrieve status for job {job_id}")
            
            # Wait for next update
            time.sleep(update_interval)
        
        # Final detailed report
        if status:
            self._display_final_job_report(status)
    
    def _update_job_statuses(self, job_ids: List[str]):
        """Update status for all monitored jobs"""
        for job_id in job_ids:
            try:
                status = self._get_job_status(job_id)
                if status:
                    self.job_statuses[job_id] = status
            except Exception as e:
                logger.warning(f"Failed to update status for job {job_id}: {str(e)}")
    
    def _get_job_status(self, job_id: str) -> Optional[MigrationJobStatus]:
        """Get status for a specific job"""
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
            
            if payload.get('statusCode') == 200:
                job_data = payload.get('body', {}).get('job', {})
                execution_status = payload.get('body', {}).get('execution_status', {})
                
                return MigrationJobStatus(
                    job_id=job_data.get('job_id', job_id),
                    job_name=job_data.get('job_name', 'Unknown'),
                    status=job_data.get('status', 'unknown'),
                    current_step=job_data.get('current_step', 'unknown'),
                    progress_percentage=job_data.get('progress_percentage', 0.0),
                    exported_records=job_data.get('exported_records', 0),
                    validation_results=job_data.get('validation_results', {}),
                    error_message=job_data.get('error_message', ''),
                    started_at=job_data.get('started_at', ''),
                    last_updated=job_data.get('updated_at', ''),
                    execution_arn=job_data.get('execution_arn', '')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {str(e)}")
            return None
    
    def _status_changed(self, previous: MigrationJobStatus, current: MigrationJobStatus) -> bool:
        """Check if job status has changed significantly"""
        return (
            previous.status != current.status or
            previous.current_step != current.current_step or
            abs(previous.progress_percentage - current.progress_percentage) >= 5.0 or
            previous.exported_records != current.exported_records
        )
    
    def _display_status_summary(self):
        """Display summary of all monitored jobs"""
        print("\n" + "="*80)
        print(f"MIGRATION STATUS SUMMARY - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*80)
        
        if not self.job_statuses:
            print("No jobs being monitored")
            return
        
        # Count jobs by status
        status_counts = {}
        total_progress = 0
        total_records = 0
        
        for job_id, status in self.job_statuses.items():
            if status:
                job_status = status.status
                status_counts[job_status] = status_counts.get(job_status, 0) + 1
                total_progress += status.progress_percentage
                total_records += status.exported_records
        
        # Display summary statistics
        total_jobs = len([s for s in self.job_statuses.values() if s])
        avg_progress = total_progress / total_jobs if total_jobs > 0 else 0
        
        print(f"Total Jobs: {total_jobs}")
        print(f"Average Progress: {avg_progress:.1f}%")
        print(f"Total Records Exported: {total_records:,}")
        
        # Display status breakdown
        print("\nStatus Breakdown:")
        for status, count in status_counts.items():
            status_icon = self._get_status_icon(status)
            print(f"  {status_icon} {status.title()}: {count}")
        
        # Display individual job status
        print("\nJob Details:")
        print(f"{'Job Name':<30} {'Status':<12} {'Step':<15} {'Progress':<10} {'Records':<12}")
        print("-" * 80)
        
        for job_id, status in self.job_statuses.items():
            if status:
                status_icon = self._get_status_icon(status.status)
                progress_bar = self._create_progress_bar(status.progress_percentage)
                
                print(f"{status.job_name[:29]:<30} {status_icon} {status.status:<10} "
                      f"{status.current_step[:14]:<15} {progress_bar} {status.exported_records:>10,}")
                
                if status.error_message:
                    print(f"  Error: {status.error_message[:70]}")
    
    def _display_detailed_status(self, status: MigrationJobStatus):
        """Display detailed status for a single job"""
        print("\n" + "="*60)
        print(f"JOB STATUS UPDATE - {datetime.utcnow().strftime('%H:%M:%S')}")
        print("="*60)
        print(f"Job ID: {status.job_id}")
        print(f"Job Name: {status.job_name}")
        print(f"Status: {self._get_status_icon(status.status)} {status.status.upper()}")
        print(f"Current Step: {status.current_step}")
        print(f"Progress: {self._create_progress_bar(status.progress_percentage, width=40)}")
        print(f"Exported Records: {status.exported_records:,}")
        
        if status.started_at:
            started = datetime.fromisoformat(status.started_at.replace('Z', '+00:00'))
            elapsed = datetime.utcnow().replace(tzinfo=started.tzinfo) - started
            print(f"Elapsed Time: {self._format_duration(elapsed.total_seconds())}")
        
        if status.validation_results:
            print(f"Validation Status: {status.validation_results.get('overall_status', 'N/A')}")
        
        if status.error_message:
            print(f"Error: {status.error_message}")
        
        print("-" * 60)
    
    def _display_final_job_report(self, status: MigrationJobStatus):
        """Display final report for a completed job"""
        print("\n" + "="*60)
        print("FINAL JOB REPORT")
        print("="*60)
        print(f"Job ID: {status.job_id}")
        print(f"Job Name: {status.job_name}")
        print(f"Final Status: {self._get_status_icon(status.status)} {status.status.upper()}")
        print(f"Total Records Exported: {status.exported_records:,}")
        
        if status.started_at:
            started = datetime.fromisoformat(status.started_at.replace('Z', '+00:00'))
            if status.last_updated:
                ended = datetime.fromisoformat(status.last_updated.replace('Z', '+00:00'))
                duration = ended - started
                print(f"Total Duration: {self._format_duration(duration.total_seconds())}")
        
        # Validation results
        if status.validation_results:
            print("\nValidation Results:")
            validation = status.validation_results
            print(f"  Overall Status: {validation.get('overall_status', 'N/A')}")
            print(f"  Source Records: {validation.get('source_record_count', 0):,}")
            print(f"  Target Records: {validation.get('target_record_count', 0):,}")
            print(f"  Count Match: {'✓' if validation.get('count_match', False) else '✗'}")
            print(f"  Sample Accuracy: {validation.get('sample_accuracy', 0):.2%}")
            
            if validation.get('validation_errors'):
                print("  Errors:")
                for error in validation['validation_errors']:
                    print(f"    • {error}")
            
            if validation.get('validation_warnings'):
                print("  Warnings:")
                for warning in validation['validation_warnings']:
                    print(f"    • {warning}")
        
        if status.error_message:
            print(f"\nError Details: {status.error_message}")
        
        print("="*60)
    
    def _all_jobs_completed(self) -> bool:
        """Check if all monitored jobs are completed"""
        for status in self.job_statuses.values():
            if status and status.status not in ['completed', 'failed', 'cancelled']:
                return False
        return True
    
    def _generate_final_report(self):
        """Generate final monitoring report"""
        print("\n" + "="*80)
        print("FINAL MIGRATION MONITORING REPORT")
        print("="*80)
        
        completed_jobs = []
        failed_jobs = []
        total_records = 0
        
        for job_id, status in self.job_statuses.items():
            if status:
                if status.status == 'completed':
                    completed_jobs.append(status)
                    total_records += status.exported_records
                elif status.status == 'failed':
                    failed_jobs.append(status)
        
        print(f"Total Jobs Monitored: {len(self.job_statuses)}")
        print(f"Successfully Completed: {len(completed_jobs)}")
        print(f"Failed: {len(failed_jobs)}")
        print(f"Total Records Migrated: {total_records:,}")
        
        if completed_jobs:
            print("\nSuccessfully Completed Jobs:")
            for status in completed_jobs:
                print(f"  ✓ {status.job_name} - {status.exported_records:,} records")
        
        if failed_jobs:
            print("\nFailed Jobs:")
            for status in failed_jobs:
                print(f"  ✗ {status.job_name} - {status.error_message}")
        
        print("="*80)
    
    def _get_status_icon(self, status: str) -> str:
        """Get icon for job status"""
        icons = {
            'pending': '⏳',
            'running': '🔄',
            'completed': '✅',
            'failed': '❌',
            'cancelled': '⏹️',
            'timeout': '⏰'
        }
        return icons.get(status, '❓')
    
    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create a text-based progress bar"""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"{bar} {percentage:5.1f}%"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def get_active_migrations(self) -> List[str]:
        """Get list of active migration job IDs"""
        # This would typically query a database or API to find active migrations
        # For now, return empty list as this would be implementation-specific
        return []
    
    def send_alert(self, message: str, severity: str = 'info'):
        """Send alert notification"""
        if not self.notification_topic_arn:
            logger.warning("No notification topic configured")
            return
        
        try:
            subject = f"Migration Alert - {severity.upper()}"
            
            self.sns_client.publish(
                TopicArn=self.notification_topic_arn,
                Subject=subject,
                Message=json.dumps({
                    'severity': severity,
                    'message': message,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'migration_monitor'
                }, indent=2)
            )
            
            logger.info(f"Alert sent: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Monitor Timestream to InfluxDB migration progress')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--job-ids', nargs='+', help='Specific job IDs to monitor')
    parser.add_argument('--job-id', help='Single job ID for detailed monitoring')
    parser.add_argument('--update-interval', type=int, default=30, help='Update interval in seconds')
    parser.add_argument('--max-duration', type=int, default=14400, help='Maximum monitoring duration in seconds')
    parser.add_argument('--auto-discover', action='store_true', help='Auto-discover active migrations')
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = MigrationMonitor(region=args.region)
    
    try:
        if args.job_id:
            # Monitor single job with detailed output
            monitor.monitor_single_job(
                job_id=args.job_id,
                update_interval=args.update_interval,
                max_duration=args.max_duration
            )
            
        elif args.job_ids:
            # Monitor specific jobs
            monitor.monitor_jobs(
                job_ids=args.job_ids,
                update_interval=args.update_interval,
                max_duration=args.max_duration
            )
            
        elif args.auto_discover:
            # Auto-discover and monitor active migrations
            active_jobs = monitor.get_active_migrations()
            if active_jobs:
                logger.info(f"Found {len(active_jobs)} active migration jobs")
                monitor.monitor_jobs(
                    job_ids=active_jobs,
                    update_interval=args.update_interval,
                    max_duration=args.max_duration
                )
            else:
                logger.info("No active migration jobs found")
                
        else:
            print("Please specify --job-id, --job-ids, or --auto-discover")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Monitoring failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()