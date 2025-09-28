#!/usr/bin/env python3
"""
Traffic Switching Deployment Script for InfluxDB Migration

This script manages the gradual rollout of traffic from Timestream to InfluxDB
by updating AppConfig feature flags and monitoring performance metrics.
"""

import argparse
import json
import logging
import time
import sys
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrafficSwitchDeployment:
    """
    Manages traffic switching deployment for InfluxDB migration.
    """
    
    def __init__(self, 
                 app_name: str,
                 environment: str,
                 region: str = 'us-east-1'):
        """
        Initialize the deployment manager.
        
        Args:
            app_name: AppConfig application name
            environment: Environment name (development/production)
            region: AWS region
        """
        self.app_name = app_name
        self.environment = environment
        self.region = region
        
        # AWS clients
        self.appconfig_client = boto3.client('appconfig', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        # Configuration
        self.config_profile = 'feature-flags'
        self.deployment_strategy = 'canary-10-percent'
        
        logger.info(f"Initialized traffic switch deployment for {app_name} in {environment}")
    
    def get_current_configuration(self) -> Dict[str, Any]:
        """
        Get current configuration from AppConfig.
        
        Returns:
            Current configuration dictionary
        """
        try:
            # Start configuration session
            session_response = self.appconfig_client.start_configuration_session(
                ApplicationIdentifier=self.app_name,
                EnvironmentIdentifier=self.environment,
                ConfigurationProfileIdentifier=self.config_profile,
                RequiredMinimumPollIntervalInSeconds=60
            )
            
            session_token = session_response['InitialConfigurationToken']
            
            # Get configuration
            config_response = self.appconfig_client.get_configuration(
                Application=self.app_name,
                Environment=self.environment,
                Configuration=self.config_profile,
                ClientId=f"traffic-switch-deploy-{int(time.time())}",
                ClientConfigurationVersion=session_token
            )
            
            # Parse configuration
            config_content = config_response['Content'].read()
            if isinstance(config_content, bytes):
                config_content = config_content.decode('utf-8')
            
            return json.loads(config_content)
            
        except Exception as e:
            logger.error(f"Failed to get current configuration: {e}")
            raise
    
    def update_traffic_percentage(self, percentage: int) -> str:
        """
        Update the traffic percentage for InfluxDB.
        
        Args:
            percentage: Percentage of traffic to route to InfluxDB (0-100)
            
        Returns:
            Configuration version number
        """
        try:
            # Get current configuration
            current_config = self.get_current_configuration()
            
            # Update traffic percentage
            current_config['values']['influxdb_traffic_percentage'] = {
                'enabled': True,
                'variant': str(percentage)
            }
            
            # Update version
            current_version = int(current_config.get('version', '1'))
            current_config['version'] = str(current_version + 1)
            
            # Create new configuration version
            response = self.appconfig_client.create_hosted_configuration_version(
                ApplicationId=self.app_name,
                ConfigurationProfileId=self.config_profile,
                Description=f"Update traffic percentage to {percentage}%",
                Content=json.dumps(current_config),
                ContentType='application/json'
            )
            
            version_number = response['VersionNumber']
            logger.info(f"Created configuration version {version_number} with {percentage}% traffic")
            
            return str(version_number)
            
        except Exception as e:
            logger.error(f"Failed to update traffic percentage: {e}")
            raise
    
    def enable_influxdb_queries(self) -> str:
        """
        Enable InfluxDB for API queries.
        
        Returns:
            Configuration version number
        """
        try:
            # Get current configuration
            current_config = self.get_current_configuration()
            
            # Enable InfluxDB queries
            current_config['values']['use_influxdb_for_api_queries'] = {
                'enabled': True
            }
            
            # Update version
            current_version = int(current_config.get('version', '1'))
            current_config['version'] = str(current_version + 1)
            
            # Create new configuration version
            response = self.appconfig_client.create_hosted_configuration_version(
                ApplicationId=self.app_name,
                ConfigurationProfileId=self.config_profile,
                Description="Enable InfluxDB for API queries",
                Content=json.dumps(current_config),
                ContentType='application/json'
            )
            
            version_number = response['VersionNumber']
            logger.info(f"Created configuration version {version_number} with InfluxDB queries enabled")
            
            return str(version_number)
            
        except Exception as e:
            logger.error(f"Failed to enable InfluxDB queries: {e}")
            raise
    
    def deploy_configuration(self, version_number: str) -> str:
        """
        Deploy configuration to the environment.
        
        Args:
            version_number: Configuration version to deploy
            
        Returns:
            Deployment number
        """
        try:
            response = self.appconfig_client.start_deployment(
                ApplicationId=self.app_name,
                EnvironmentId=self.environment,
                DeploymentStrategyId=self.deployment_strategy,
                ConfigurationProfileId=self.config_profile,
                ConfigurationVersion=version_number,
                Description=f"Deploy configuration version {version_number}"
            )
            
            deployment_number = response['DeploymentNumber']
            logger.info(f"Started deployment {deployment_number} for version {version_number}")
            
            return str(deployment_number)
            
        except Exception as e:
            logger.error(f"Failed to deploy configuration: {e}")
            raise
    
    def monitor_deployment(self, deployment_number: str, timeout_minutes: int = 30) -> bool:
        """
        Monitor deployment progress and health.
        
        Args:
            deployment_number: Deployment to monitor
            timeout_minutes: Maximum time to wait for deployment
            
        Returns:
            True if deployment succeeded, False otherwise
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        logger.info(f"Monitoring deployment {deployment_number} (timeout: {timeout_minutes} minutes)")
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Check deployment status
                response = self.appconfig_client.get_deployment(
                    ApplicationId=self.app_name,
                    EnvironmentId=self.environment,
                    DeploymentNumber=int(deployment_number)
                )
                
                state = response['State']
                logger.info(f"Deployment {deployment_number} state: {state}")
                
                if state == 'COMPLETE':
                    logger.info(f"Deployment {deployment_number} completed successfully")
                    return True
                elif state in ['ROLLED_BACK', 'BAKING']:
                    logger.warning(f"Deployment {deployment_number} was rolled back or is baking")
                    return False
                
                # Check performance metrics
                if not self._check_performance_metrics():
                    logger.error("Performance metrics indicate issues, considering rollback")
                    return False
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring deployment: {e}")
                time.sleep(30)
        
        logger.error(f"Deployment {deployment_number} timed out")
        return False
    
    def _check_performance_metrics(self) -> bool:
        """
        Check performance metrics to ensure deployment is healthy.
        
        Returns:
            True if metrics are healthy, False otherwise
        """
        try:
            end_time = time.time()
            start_time = end_time - 300  # Last 5 minutes
            
            # Check error rate
            error_rate_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='ONS/TrafficSwitching',
                MetricName='ErrorRate',
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )
            
            if error_rate_response['Datapoints']:
                latest_error_rate = error_rate_response['Datapoints'][-1]['Average']
                if latest_error_rate > 0.05:  # 5% error rate threshold
                    logger.warning(f"High error rate detected: {latest_error_rate:.2%}")
                    return False
            
            # Check response time
            response_time_response = self.cloudwatch_client.get_metric_statistics(
                Namespace='ONS/TrafficSwitching',
                MetricName='ResponseTime',
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Average']
            )
            
            if response_time_response['Datapoints']:
                latest_response_time = response_time_response['Datapoints'][-1]['Average']
                if latest_response_time > 10000:  # 10 second threshold
                    logger.warning(f"High response time detected: {latest_response_time:.0f}ms")
                    return False
            
            logger.info("Performance metrics are healthy")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to check performance metrics: {e}")
            return True  # Don't fail deployment on metrics check failure
    
    def rollback_deployment(self, deployment_number: str) -> bool:
        """
        Rollback a deployment.
        
        Args:
            deployment_number: Deployment to rollback
            
        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            self.appconfig_client.stop_deployment(
                ApplicationId=self.app_name,
                EnvironmentId=self.environment,
                DeploymentNumber=int(deployment_number)
            )
            
            logger.info(f"Initiated rollback for deployment {deployment_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback deployment: {e}")
            return False
    
    def gradual_rollout(self, target_percentage: int, step_size: int = 10, wait_minutes: int = 15) -> bool:
        """
        Perform gradual rollout to target percentage.
        
        Args:
            target_percentage: Target traffic percentage
            step_size: Percentage increase per step
            wait_minutes: Minutes to wait between steps
            
        Returns:
            True if rollout succeeded, False otherwise
        """
        current_config = self.get_current_configuration()
        current_percentage = int(current_config['values']['influxdb_traffic_percentage'].get('variant', '0'))
        
        logger.info(f"Starting gradual rollout from {current_percentage}% to {target_percentage}%")
        
        # First enable InfluxDB queries if not already enabled
        if not current_config['values']['use_influxdb_for_api_queries'].get('enabled', False):
            logger.info("Enabling InfluxDB queries")
            version = self.enable_influxdb_queries()
            deployment = self.deploy_configuration(version)
            
            if not self.monitor_deployment(deployment):
                logger.error("Failed to enable InfluxDB queries")
                return False
            
            time.sleep(wait_minutes * 60)
        
        # Gradual percentage increase
        while current_percentage < target_percentage:
            next_percentage = min(current_percentage + step_size, target_percentage)
            
            logger.info(f"Increasing traffic to {next_percentage}%")
            
            try:
                version = self.update_traffic_percentage(next_percentage)
                deployment = self.deploy_configuration(version)
                
                if not self.monitor_deployment(deployment):
                    logger.error(f"Deployment failed at {next_percentage}%, rolling back")
                    self.rollback_deployment(deployment)
                    return False
                
                current_percentage = next_percentage
                
                if current_percentage < target_percentage:
                    logger.info(f"Waiting {wait_minutes} minutes before next step")
                    time.sleep(wait_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error during rollout step: {e}")
                return False
        
        logger.info(f"Gradual rollout completed successfully at {target_percentage}%")
        return True


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Traffic Switching Deployment for InfluxDB Migration')
    parser.add_argument('--app-name', required=True, help='AppConfig application name')
    parser.add_argument('--environment', required=True, help='Environment (development/production)')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Enable queries command
    enable_parser = subparsers.add_parser('enable-queries', help='Enable InfluxDB for API queries')
    
    # Set percentage command
    percentage_parser = subparsers.add_parser('set-percentage', help='Set traffic percentage')
    percentage_parser.add_argument('--percentage', type=int, required=True, 
                                 help='Traffic percentage (0-100)')
    
    # Gradual rollout command
    rollout_parser = subparsers.add_parser('gradual-rollout', help='Perform gradual rollout')
    rollout_parser.add_argument('--target', type=int, required=True, 
                               help='Target traffic percentage (0-100)')
    rollout_parser.add_argument('--step-size', type=int, default=10, 
                               help='Percentage increase per step')
    rollout_parser.add_argument('--wait-minutes', type=int, default=15, 
                               help='Minutes to wait between steps')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show current configuration status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        deployment = TrafficSwitchDeployment(args.app_name, args.environment, args.region)
        
        if args.command == 'enable-queries':
            version = deployment.enable_influxdb_queries()
            deployment_num = deployment.deploy_configuration(version)
            success = deployment.monitor_deployment(deployment_num)
            return 0 if success else 1
            
        elif args.command == 'set-percentage':
            version = deployment.update_traffic_percentage(args.percentage)
            deployment_num = deployment.deploy_configuration(version)
            success = deployment.monitor_deployment(deployment_num)
            return 0 if success else 1
            
        elif args.command == 'gradual-rollout':
            success = deployment.gradual_rollout(
                args.target, 
                args.step_size, 
                args.wait_minutes
            )
            return 0 if success else 1
            
        elif args.command == 'status':
            config = deployment.get_current_configuration()
            print(json.dumps(config, indent=2))
            return 0
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())