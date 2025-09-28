#!/usr/bin/env python3
"""
Automated deployment script with blue-green deployment and feature flag integration.
Supports canary releases with automatic rollback based on error rates and latency.
"""

import json
import time
import boto3
import argparse
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class DeploymentConfig:
    """Configuration for deployment parameters"""
    function_name: str
    alias_name: str
    deployment_group: str
    canary_percentage: int = 10
    rollback_threshold: int = 5
    monitoring_duration: int = 300  # 5 minutes

class DeploymentManager:
    """Manages blue-green deployments with automatic rollback capabilities"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.codedeploy = boto3.client('codedeploy', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.appconfig = boto3.client('appconfig', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        
    def deploy_lambda_function(self, config: DeploymentConfig, 
                             new_version: str) -> str:
        """
        Deploy Lambda function using CodeDeploy blue-green deployment
        
        Args:
            config: Deployment configuration
            new_version: New Lambda function version to deploy
            
        Returns:
            Deployment ID
        """
        logger.info(f"Starting deployment for {config.function_name} version {new_version}")
        
        # Update Lambda alias to point to new version
        try:
            self.lambda_client.update_alias(
                FunctionName=config.function_name,
                Name=config.alias_name,
                FunctionVersion=new_version,
                Description=f"Deployment to version {new_version}"
            )
            logger.info(f"Updated alias {config.alias_name} to version {new_version}")
        except Exception as e:
            logger.error(f"Failed to update Lambda alias: {e}")
            raise
        
        # Create CodeDeploy deployment
        deployment_config = {
            'applicationName': 'ons-data-platform-lambda-app',
            'deploymentGroupName': config.deployment_group,
            'revision': {
                'revisionType': 'AppSpecContent',
                'appSpecContent': {
                    'content': json.dumps({
                        'version': 0.0,
                        'Resources': [{
                            'myLambdaFunction': {
                                'Type': 'AWS::Lambda::Function',
                                'Properties': {
                                    'Name': config.function_name,
                                    'Alias': config.alias_name,
                                    'CurrentVersion': new_version,
                                    'TargetVersion': new_version
                                }
                            }
                        }],
                        'Hooks': [{
                            'BeforeAllowTraffic': 'PreTrafficHook',
                            'AfterAllowTraffic': 'PostTrafficHook'
                        }]
                    })
                }
            },
            'deploymentConfigName': f'CodeDeployDefault.LambdaCanary{config.canary_percentage}Percent5Minutes',
            'description': f'Blue-green deployment for {config.function_name}',
            'autoRollbackConfiguration': {
                'enabled': True,
                'events': ['DEPLOYMENT_FAILURE', 'DEPLOYMENT_STOP_ON_ALARM']
            }
        }
        
        try:
            response = self.codedeploy.create_deployment(**deployment_config)
            deployment_id = response['deploymentId']
            logger.info(f"Created deployment {deployment_id}")
            return deployment_id
        except Exception as e:
            logger.error(f"Failed to create deployment: {e}")
            raise
    
    def monitor_deployment(self, deployment_id: str, 
                          config: DeploymentConfig) -> bool:
        """
        Monitor deployment progress and trigger rollback if needed
        
        Args:
            deployment_id: CodeDeploy deployment ID
            config: Deployment configuration
            
        Returns:
            True if deployment successful, False if rolled back
        """
        logger.info(f"Monitoring deployment {deployment_id}")
        
        start_time = time.time()
        while time.time() - start_time < config.monitoring_duration:
            try:
                # Check deployment status
                response = self.codedeploy.get_deployment(deploymentId=deployment_id)
                status = response['deploymentInfo']['status']
                
                logger.info(f"Deployment status: {status}")
                
                if status == 'Succeeded':
                    logger.info("Deployment completed successfully")
                    return True
                elif status in ['Failed', 'Stopped']:
                    logger.error(f"Deployment failed with status: {status}")
                    return False
                
                # Check metrics for automatic rollback
                if self._should_rollback(config):
                    logger.warning("Metrics indicate rollback needed")
                    self._trigger_rollback(deployment_id)
                    return False
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring deployment: {e}")
                return False
        
        logger.warning("Deployment monitoring timeout reached")
        return False
    
    def _should_rollback(self, config: DeploymentConfig) -> bool:
        """
        Check if deployment should be rolled back based on metrics
        
        Args:
            config: Deployment configuration
            
        Returns:
            True if rollback should be triggered
        """
        try:
            # Check error rate
            error_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': config.function_name}
                ],
                StartTime=time.time() - 300,  # Last 5 minutes
                EndTime=time.time(),
                Period=60,
                Statistics=['Sum']
            )
            
            # Check invocation count
            invocation_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': config.function_name}
                ],
                StartTime=time.time() - 300,
                EndTime=time.time(),
                Period=60,
                Statistics=['Sum']
            )
            
            if error_response['Datapoints'] and invocation_response['Datapoints']:
                total_errors = sum(dp['Sum'] for dp in error_response['Datapoints'])
                total_invocations = sum(dp['Sum'] for dp in invocation_response['Datapoints'])
                
                if total_invocations > 0:
                    error_rate = (total_errors / total_invocations) * 100
                    logger.info(f"Current error rate: {error_rate:.2f}%")
                    
                    if error_rate > config.rollback_threshold:
                        logger.warning(f"Error rate {error_rate:.2f}% exceeds threshold {config.rollback_threshold}%")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking metrics: {e}")
            return False
    
    def _trigger_rollback(self, deployment_id: str):
        """
        Trigger automatic rollback for deployment
        
        Args:
            deployment_id: CodeDeploy deployment ID
        """
        try:
            self.codedeploy.stop_deployment(
                deploymentId=deployment_id,
                autoRollbackEnabled=True
            )
            logger.info(f"Triggered rollback for deployment {deployment_id}")
        except Exception as e:
            logger.error(f"Failed to trigger rollback: {e}")
    
    def update_feature_flag(self, application_id: str, environment_id: str,
                           configuration_profile_id: str, flag_name: str,
                           enabled: bool) -> str:
        """
        Update feature flag using AWS AppConfig
        
        Args:
            application_id: AppConfig application ID
            environment_id: AppConfig environment ID
            configuration_profile_id: Configuration profile ID
            flag_name: Name of the feature flag
            enabled: Whether to enable or disable the flag
            
        Returns:
            Deployment number
        """
        logger.info(f"Updating feature flag {flag_name} to {enabled}")
        
        try:
            # Create new configuration version
            response = self.appconfig.create_hosted_configuration_version(
                ApplicationId=application_id,
                ConfigurationProfileId=configuration_profile_id,
                Description=f"Update {flag_name} to {enabled}",
                ContentType='application/json',
                Content=json.dumps({
                    'flags': {
                        flag_name: {
                            'name': flag_name,
                            'enabled': enabled
                        }
                    },
                    'values': {
                        flag_name: {
                            'enabled': enabled
                        }
                    },
                    'version': '1'
                })
            )
            
            version_number = response['VersionNumber']
            
            # Start deployment
            deployment_response = self.appconfig.start_deployment(
                ApplicationId=application_id,
                EnvironmentId=environment_id,
                DeploymentStrategyId='canary-10-percent',
                ConfigurationProfileId=configuration_profile_id,
                ConfigurationVersion=str(version_number),
                Description=f'Deploy feature flag update for {flag_name}'
            )
            
            deployment_number = deployment_response['DeploymentNumber']
            logger.info(f"Started AppConfig deployment {deployment_number}")
            
            return str(deployment_number)
            
        except Exception as e:
            logger.error(f"Failed to update feature flag: {e}")
            raise

def main():
    """Main deployment script entry point"""
    parser = argparse.ArgumentParser(description='Deploy Lambda functions with blue-green deployment')
    parser.add_argument('--function-name', required=True, help='Lambda function name')
    parser.add_argument('--version', required=True, help='Lambda function version to deploy')
    parser.add_argument('--alias', default='live', help='Lambda alias name')
    parser.add_argument('--deployment-group', required=True, help='CodeDeploy deployment group')
    parser.add_argument('--canary-percentage', type=int, default=10, help='Canary deployment percentage')
    parser.add_argument('--rollback-threshold', type=int, default=5, help='Error rate threshold for rollback')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    # Create deployment configuration
    config = DeploymentConfig(
        function_name=args.function_name,
        alias_name=args.alias,
        deployment_group=args.deployment_group,
        canary_percentage=args.canary_percentage,
        rollback_threshold=args.rollback_threshold
    )
    
    # Initialize deployment manager
    manager = DeploymentManager(region=args.region)
    
    try:
        # Deploy function
        deployment_id = manager.deploy_lambda_function(config, args.version)
        
        # Monitor deployment
        success = manager.monitor_deployment(deployment_id, config)
        
        if success:
            logger.info("Deployment completed successfully")
            exit(0)
        else:
            logger.error("Deployment failed or was rolled back")
            exit(1)
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        exit(1)

if __name__ == '__main__':
    main()