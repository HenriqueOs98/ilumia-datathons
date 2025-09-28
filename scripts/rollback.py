#!/usr/bin/env python3
"""
Emergency rollback script for Lambda functions and feature flags.
Provides immediate rollback capabilities for production incidents.
"""

import boto3
import argparse
import logging
import json
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RollbackManager:
    """Manages emergency rollbacks for Lambda functions and configurations"""
    
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.codedeploy = boto3.client('codedeploy', region_name=region)
        self.appconfig = boto3.client('appconfig', region_name=region)
        self.appconfig_data = boto3.client('appconfigdata', region_name=region)
        
    def rollback_lambda_function(self, function_name: str, 
                                target_version: Optional[str] = None) -> bool:
        """
        Rollback Lambda function to previous stable version
        
        Args:
            function_name: Name of the Lambda function
            target_version: Specific version to rollback to (optional)
            
        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Starting rollback for function {function_name}")
            
            # Get current alias configuration
            current_alias = self.lambda_client.get_alias(
                FunctionName=function_name,
                Name='live'
            )
            current_version = current_alias['FunctionVersion']
            
            if target_version is None:
                # Get previous version from version list
                versions = self.lambda_client.list_versions_by_function(
                    FunctionName=function_name
                )
                
                # Find the version before current
                version_numbers = [
                    int(v['Version']) for v in versions['Versions'] 
                    if v['Version'] != '$LATEST' and v['Version'] != current_version
                ]
                
                if not version_numbers:
                    logger.error("No previous version found for rollback")
                    return False
                
                target_version = str(max(version_numbers))
            
            logger.info(f"Rolling back from version {current_version} to {target_version}")
            
            # Update alias to point to target version
            self.lambda_client.update_alias(
                FunctionName=function_name,
                Name='live',
                FunctionVersion=target_version,
                Description=f"Emergency rollback from {current_version} to {target_version}"
            )
            
            logger.info(f"Successfully rolled back {function_name} to version {target_version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback function {function_name}: {e}")
            return False
    
    def stop_active_deployment(self, deployment_id: str) -> bool:
        """
        Stop active CodeDeploy deployment and trigger rollback
        
        Args:
            deployment_id: CodeDeploy deployment ID to stop
            
        Returns:
            True if deployment stopped successfully
        """
        try:
            logger.info(f"Stopping deployment {deployment_id}")
            
            self.codedeploy.stop_deployment(
                deploymentId=deployment_id,
                autoRollbackEnabled=True
            )
            
            logger.info(f"Successfully stopped deployment {deployment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop deployment {deployment_id}: {e}")
            return False
    
    def rollback_feature_flags(self, application_id: str, environment_id: str,
                              configuration_profile_id: str, 
                              flags_to_disable: List[str]) -> bool:
        """
        Disable specified feature flags immediately
        
        Args:
            application_id: AppConfig application ID
            environment_id: AppConfig environment ID
            configuration_profile_id: Configuration profile ID
            flags_to_disable: List of feature flag names to disable
            
        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Disabling feature flags: {flags_to_disable}")
            
            # Get current configuration
            current_config = self._get_current_configuration(
                application_id, environment_id, configuration_profile_id
            )
            
            # Update flags to disabled
            updated_config = current_config.copy()
            for flag_name in flags_to_disable:
                if flag_name in updated_config.get('flags', {}):
                    updated_config['flags'][flag_name]['enabled'] = False
                if flag_name in updated_config.get('values', {}):
                    updated_config['values'][flag_name]['enabled'] = False
            
            # Create new configuration version
            response = self.appconfig.create_hosted_configuration_version(
                ApplicationId=application_id,
                ConfigurationProfileId=configuration_profile_id,
                Description=f"Emergency rollback - disable flags: {', '.join(flags_to_disable)}",
                ContentType='application/json',
                Content=json.dumps(updated_config)
            )
            
            version_number = response['VersionNumber']
            
            # Deploy immediately (no canary for emergency rollback)
            self.appconfig.start_deployment(
                ApplicationId=application_id,
                EnvironmentId=environment_id,
                DeploymentStrategyId='AppConfig.AllAtOnce',  # Immediate deployment
                ConfigurationProfileId=configuration_profile_id,
                ConfigurationVersion=str(version_number),
                Description='Emergency feature flag rollback'
            )
            
            logger.info(f"Successfully disabled feature flags: {flags_to_disable}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback feature flags: {e}")
            return False
    
    def _get_current_configuration(self, application_id: str, environment_id: str,
                                  configuration_profile_id: str) -> Dict:
        """Get current configuration from AppConfig"""
        try:
            # Start configuration session
            session_response = self.appconfig_data.start_configuration_session(
                ApplicationIdentifier=application_id,
                EnvironmentIdentifier=environment_id,
                ConfigurationProfileIdentifier=configuration_profile_id
            )
            
            # Get configuration
            config_response = self.appconfig_data.get_configuration(
                ConfigurationToken=session_response['InitialConfigurationToken']
            )
            
            return json.loads(config_response['Configuration'].read())
            
        except Exception as e:
            logger.error(f"Failed to get current configuration: {e}")
            return {}
    
    def get_active_deployments(self, application_name: str) -> List[Dict]:
        """
        Get list of active deployments for an application
        
        Args:
            application_name: CodeDeploy application name
            
        Returns:
            List of active deployment information
        """
        try:
            response = self.codedeploy.list_deployments(
                applicationName=application_name,
                includeOnlyStatuses=['InProgress', 'Queued', 'Ready']
            )
            
            active_deployments = []
            for deployment_id in response['deployments']:
                deployment_info = self.codedeploy.get_deployment(
                    deploymentId=deployment_id
                )
                active_deployments.append({
                    'deploymentId': deployment_id,
                    'status': deployment_info['deploymentInfo']['status'],
                    'deploymentGroup': deployment_info['deploymentInfo']['deploymentGroupName'],
                    'createTime': deployment_info['deploymentInfo']['createTime']
                })
            
            return active_deployments
            
        except Exception as e:
            logger.error(f"Failed to get active deployments: {e}")
            return []
    
    def health_check(self, function_names: List[str]) -> Dict[str, bool]:
        """
        Perform health check on Lambda functions
        
        Args:
            function_names: List of function names to check
            
        Returns:
            Dictionary mapping function names to health status
        """
        health_status = {}
        
        for function_name in function_names:
            try:
                # Invoke function with test payload
                response = self.lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps({'test': True})
                )
                
                if response['StatusCode'] == 200:
                    health_status[function_name] = True
                    logger.info(f"Health check passed for {function_name}")
                else:
                    health_status[function_name] = False
                    logger.warning(f"Health check failed for {function_name}")
                    
            except Exception as e:
                health_status[function_name] = False
                logger.error(f"Health check error for {function_name}: {e}")
        
        return health_status

def main():
    """Main rollback script entry point"""
    parser = argparse.ArgumentParser(description='Emergency rollback for Lambda functions')
    parser.add_argument('--action', required=True, 
                       choices=['rollback-function', 'stop-deployment', 'rollback-flags', 'health-check'],
                       help='Rollback action to perform')
    parser.add_argument('--function-name', help='Lambda function name')
    parser.add_argument('--target-version', help='Target version for rollback')
    parser.add_argument('--deployment-id', help='CodeDeploy deployment ID to stop')
    parser.add_argument('--application-id', help='AppConfig application ID')
    parser.add_argument('--environment-id', help='AppConfig environment ID')
    parser.add_argument('--profile-id', help='AppConfig configuration profile ID')
    parser.add_argument('--flags', nargs='+', help='Feature flags to disable')
    parser.add_argument('--functions', nargs='+', help='Functions for health check')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    # Initialize rollback manager
    manager = RollbackManager(region=args.region)
    
    try:
        if args.action == 'rollback-function':
            if not args.function_name:
                logger.error("Function name required for rollback-function action")
                exit(1)
            
            success = manager.rollback_lambda_function(
                args.function_name, args.target_version
            )
            
        elif args.action == 'stop-deployment':
            if not args.deployment_id:
                logger.error("Deployment ID required for stop-deployment action")
                exit(1)
            
            success = manager.stop_active_deployment(args.deployment_id)
            
        elif args.action == 'rollback-flags':
            if not all([args.application_id, args.environment_id, args.profile_id, args.flags]):
                logger.error("AppConfig parameters and flags required for rollback-flags action")
                exit(1)
            
            success = manager.rollback_feature_flags(
                args.application_id, args.environment_id, 
                args.profile_id, args.flags
            )
            
        elif args.action == 'health-check':
            if not args.functions:
                logger.error("Function names required for health-check action")
                exit(1)
            
            health_status = manager.health_check(args.functions)
            
            print("\nHealth Check Results:")
            for function, status in health_status.items():
                status_text = "HEALTHY" if status else "UNHEALTHY"
                print(f"  {function}: {status_text}")
            
            success = all(health_status.values())
        
        if success:
            logger.info("Rollback operation completed successfully")
            exit(0)
        else:
            logger.error("Rollback operation failed")
            exit(1)
            
    except Exception as e:
        logger.error(f"Rollback operation failed: {e}")
        exit(1)

if __name__ == '__main__':
    main()