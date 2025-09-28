"""
Traffic Switching Utility for InfluxDB Migration

This module provides functionality to manage traffic switching between
Timestream and InfluxDB during the migration process. It integrates with
AWS AppConfig for feature flag management and provides monitoring capabilities.
"""

import json
import logging
import os
import time
import random
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DatabaseBackend(Enum):
    """Enumeration of available database backends."""
    TIMESTREAM = "timestream"
    INFLUXDB = "influxdb"


class TrafficSwitchError(Exception):
    """Custom exception for traffic switching errors."""
    pass


class TrafficSwitchManager:
    """
    Manages traffic switching between Timestream and InfluxDB.
    
    This class handles feature flag retrieval, traffic percentage calculations,
    performance monitoring, and automatic rollback capabilities.
    """
    
    def __init__(self, 
                 app_name: str = None,
                 environment: str = None,
                 config_profile: str = "feature-flags"):
        """
        Initialize the traffic switch manager.
        
        Args:
            app_name: AppConfig application name
            environment: Environment name (development/production)
            config_profile: Configuration profile name
        """
        self.app_name = app_name or os.getenv('APPCONFIG_APPLICATION', 'ons-data-platform-app')
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self.config_profile = config_profile
        
        # AWS clients (lazy-loaded)
        self._appconfig_client = None
        self._cloudwatch_client = None
        
        # Configuration cache
        self._config_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = int(os.getenv('CONFIG_CACHE_TTL', '300'))  # 5 minutes
        
        # Performance tracking
        self._performance_metrics = {
            'timestream': {'total_requests': 0, 'total_time': 0, 'errors': 0},
            'influxdb': {'total_requests': 0, 'total_time': 0, 'errors': 0}
        }
        
        logger.info(f"TrafficSwitchManager initialized for app: {self.app_name}, env: {self.environment}")
    
    @property
    def appconfig_client(self):
        """Get or create AppConfig client."""
        if self._appconfig_client is None:
            self._appconfig_client = boto3.client('appconfig')
        return self._appconfig_client
    
    @property
    def cloudwatch_client(self):
        """Get or create CloudWatch client."""
        if self._cloudwatch_client is None:
            self._cloudwatch_client = boto3.client('cloudwatch')
        return self._cloudwatch_client
    
    def _get_configuration(self) -> Dict[str, Any]:
        """
        Get configuration from AppConfig with caching.
        
        Returns:
            Configuration dictionary
            
        Raises:
            TrafficSwitchError: If configuration retrieval fails
        """
        current_time = time.time()
        
        # Check cache validity
        if (self._config_cache and 
            current_time - self._cache_timestamp < self._cache_ttl):
            logger.debug("Using cached configuration")
            return self._config_cache
        
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
                ClientId=f"traffic-switch-{int(current_time)}",
                ClientConfigurationVersion=session_token
            )
            
            # Parse configuration
            config_content = config_response['Content'].read()
            if isinstance(config_content, bytes):
                config_content = config_content.decode('utf-8')
            
            configuration = json.loads(config_content)
            
            # Update cache
            self._config_cache = configuration
            self._cache_timestamp = current_time
            
            logger.info("Configuration retrieved and cached successfully")
            return configuration
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"AppConfig resource not found: {e}")
                # Return default configuration
                return self._get_default_configuration()
            else:
                logger.error(f"Failed to retrieve configuration: {e}")
                raise TrafficSwitchError(f"Configuration retrieval failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving configuration: {e}")
            raise TrafficSwitchError(f"Configuration error: {e}")
    
    def _get_default_configuration(self) -> Dict[str, Any]:
        """
        Get default configuration when AppConfig is unavailable.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'flags': {
                'use_influxdb_for_data_ingestion': {'enabled': True},
                'use_influxdb_for_api_queries': {'enabled': False},
                'enable_query_performance_monitoring': {'enabled': True},
                'influxdb_traffic_percentage': {'enabled': True, 'variant': '0'}
            },
            'values': {
                'use_influxdb_for_data_ingestion': {'enabled': True},
                'use_influxdb_for_api_queries': {'enabled': False},
                'enable_query_performance_monitoring': {'enabled': True},
                'influxdb_traffic_percentage': {'enabled': True, 'variant': '0'}
            }
        }
    
    def should_use_influxdb_for_ingestion(self) -> bool:
        """
        Determine if InfluxDB should be used for data ingestion.
        
        Returns:
            True if InfluxDB should be used for ingestion
        """
        try:
            config = self._get_configuration()
            flag_value = config.get('values', {}).get('use_influxdb_for_data_ingestion', {})
            return flag_value.get('enabled', False)
        except Exception as e:
            logger.error(f"Error checking ingestion flag: {e}")
            # Default to InfluxDB for ingestion (migration is complete for ingestion)
            return True
    
    def should_use_influxdb_for_queries(self) -> bool:
        """
        Determine if InfluxDB should be used for API queries.
        
        Returns:
            True if InfluxDB should be used for queries
        """
        try:
            config = self._get_configuration()
            flag_value = config.get('values', {}).get('use_influxdb_for_api_queries', {})
            return flag_value.get('enabled', False)
        except Exception as e:
            logger.error(f"Error checking query flag: {e}")
            # Default to Timestream for queries (safer during migration)
            return False
    
    def get_traffic_percentage(self) -> int:
        """
        Get the current traffic percentage for InfluxDB.
        
        Returns:
            Percentage of traffic to route to InfluxDB (0-100)
        """
        try:
            config = self._get_configuration()
            flag_value = config.get('values', {}).get('influxdb_traffic_percentage', {})
            
            if not flag_value.get('enabled', False):
                return 0
            
            variant = flag_value.get('variant', '0')
            return int(variant)
            
        except Exception as e:
            logger.error(f"Error getting traffic percentage: {e}")
            return 0
    
    def determine_backend_for_query(self, user_id: str = None) -> DatabaseBackend:
        """
        Determine which backend to use for a query based on traffic switching rules.
        
        Args:
            user_id: Optional user ID for consistent routing
            
        Returns:
            Database backend to use
        """
        try:
            # Check if InfluxDB is enabled for queries
            if not self.should_use_influxdb_for_queries():
                logger.debug("InfluxDB queries disabled, using Timestream")
                return DatabaseBackend.TIMESTREAM
            
            # Get traffic percentage
            traffic_percentage = self.get_traffic_percentage()
            
            if traffic_percentage == 0:
                logger.debug("Traffic percentage is 0, using Timestream")
                return DatabaseBackend.TIMESTREAM
            elif traffic_percentage == 100:
                logger.debug("Traffic percentage is 100, using InfluxDB")
                return DatabaseBackend.INFLUXDB
            
            # Determine routing based on percentage
            if user_id:
                # Consistent routing based on user ID hash
                import hashlib
                hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
                routing_value = hash_value % 100
            else:
                # Random routing
                routing_value = random.randint(0, 99)
            
            if routing_value < traffic_percentage:
                logger.debug(f"Routing to InfluxDB (routing_value: {routing_value}, percentage: {traffic_percentage})")
                return DatabaseBackend.INFLUXDB
            else:
                logger.debug(f"Routing to Timestream (routing_value: {routing_value}, percentage: {traffic_percentage})")
                return DatabaseBackend.TIMESTREAM
                
        except Exception as e:
            logger.error(f"Error determining backend: {e}")
            # Default to Timestream on error
            return DatabaseBackend.TIMESTREAM
    
    def record_performance_metric(self, 
                                backend: DatabaseBackend, 
                                response_time_ms: float, 
                                success: bool = True):
        """
        Record performance metrics for monitoring.
        
        Args:
            backend: Database backend used
            response_time_ms: Response time in milliseconds
            success: Whether the operation was successful
        """
        try:
            backend_name = backend.value
            metrics = self._performance_metrics[backend_name]
            
            metrics['total_requests'] += 1
            metrics['total_time'] += response_time_ms
            
            if not success:
                metrics['errors'] += 1
            
            # Send metrics to CloudWatch
            self._send_performance_metrics(backend, response_time_ms, success)
            
        except Exception as e:
            logger.warning(f"Failed to record performance metric: {e}")
    
    def _send_performance_metrics(self, 
                                backend: DatabaseBackend, 
                                response_time_ms: float, 
                                success: bool):
        """
        Send performance metrics to CloudWatch.
        
        Args:
            backend: Database backend used
            response_time_ms: Response time in milliseconds
            success: Whether the operation was successful
        """
        try:
            metric_data = [
                {
                    'MetricName': 'ResponseTime',
                    'Dimensions': [
                        {'Name': 'Backend', 'Value': backend.value},
                        {'Name': 'Environment', 'Value': self.environment}
                    ],
                    'Value': response_time_ms,
                    'Unit': 'Milliseconds',
                    'Timestamp': time.time()
                },
                {
                    'MetricName': 'RequestCount',
                    'Dimensions': [
                        {'Name': 'Backend', 'Value': backend.value},
                        {'Name': 'Environment', 'Value': self.environment}
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': time.time()
                }
            ]
            
            if not success:
                metric_data.append({
                    'MetricName': 'ErrorCount',
                    'Dimensions': [
                        {'Name': 'Backend', 'Value': backend.value},
                        {'Name': 'Environment', 'Value': self.environment}
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': time.time()
                })
            
            # Calculate error rate
            backend_metrics = self._performance_metrics[backend.value]
            if backend_metrics['total_requests'] > 0:
                error_rate = backend_metrics['errors'] / backend_metrics['total_requests']
                metric_data.append({
                    'MetricName': 'ErrorRate',
                    'Dimensions': [
                        {'Name': 'Backend', 'Value': backend.value},
                        {'Name': 'Environment', 'Value': self.environment}
                    ],
                    'Value': error_rate,
                    'Unit': 'Percent',
                    'Timestamp': time.time()
                })
            
            self.cloudwatch_client.put_metric_data(
                Namespace='ONS/TrafficSwitching',
                MetricData=metric_data
            )
            
        except Exception as e:
            logger.warning(f"Failed to send CloudWatch metrics: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for both backends.
        
        Returns:
            Performance summary dictionary
        """
        summary = {}
        
        for backend_name, metrics in self._performance_metrics.items():
            if metrics['total_requests'] > 0:
                avg_response_time = metrics['total_time'] / metrics['total_requests']
                error_rate = metrics['errors'] / metrics['total_requests']
            else:
                avg_response_time = 0
                error_rate = 0
            
            summary[backend_name] = {
                'total_requests': metrics['total_requests'],
                'average_response_time_ms': round(avg_response_time, 2),
                'error_rate': round(error_rate, 4),
                'total_errors': metrics['errors']
            }
        
        return summary
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on traffic switching components.
        
        Returns:
            Health check results
        """
        health_status = {
            'status': 'healthy',
            'timestamp': time.time(),
            'components': {}
        }
        
        try:
            # Check AppConfig connectivity
            config = self._get_configuration()
            health_status['components']['appconfig'] = {
                'status': 'healthy',
                'config_version': config.get('version', 'unknown')
            }
        except Exception as e:
            health_status['components']['appconfig'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        try:
            # Check CloudWatch connectivity
            self.cloudwatch_client.list_metrics(Namespace='ONS/TrafficSwitching', MaxRecords=1)
            health_status['components']['cloudwatch'] = {
                'status': 'healthy'
            }
        except Exception as e:
            health_status['components']['cloudwatch'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Add current configuration status
        health_status['current_config'] = {
            'influxdb_ingestion_enabled': self.should_use_influxdb_for_ingestion(),
            'influxdb_queries_enabled': self.should_use_influxdb_for_queries(),
            'traffic_percentage': self.get_traffic_percentage()
        }
        
        # Add performance summary
        health_status['performance_summary'] = self.get_performance_summary()
        
        return health_status


# Global instance for easy access
_traffic_switch_manager = None


def get_traffic_switch_manager() -> TrafficSwitchManager:
    """
    Get or create global traffic switch manager instance.
    
    Returns:
        TrafficSwitchManager instance
    """
    global _traffic_switch_manager
    if _traffic_switch_manager is None:
        _traffic_switch_manager = TrafficSwitchManager()
    return _traffic_switch_manager


def should_use_influxdb_for_ingestion() -> bool:
    """
    Convenience function to check if InfluxDB should be used for ingestion.
    
    Returns:
        True if InfluxDB should be used for ingestion
    """
    return get_traffic_switch_manager().should_use_influxdb_for_ingestion()


def should_use_influxdb_for_queries() -> bool:
    """
    Convenience function to check if InfluxDB should be used for queries.
    
    Returns:
        True if InfluxDB should be used for queries
    """
    return get_traffic_switch_manager().should_use_influxdb_for_queries()


def determine_backend_for_query(user_id: str = None) -> DatabaseBackend:
    """
    Convenience function to determine backend for queries.
    
    Args:
        user_id: Optional user ID for consistent routing
        
    Returns:
        Database backend to use
    """
    return get_traffic_switch_manager().determine_backend_for_query(user_id)


def record_performance_metric(backend: DatabaseBackend, 
                            response_time_ms: float, 
                            success: bool = True):
    """
    Convenience function to record performance metrics.
    
    Args:
        backend: Database backend used
        response_time_ms: Response time in milliseconds
        success: Whether the operation was successful
    """
    get_traffic_switch_manager().record_performance_metric(backend, response_time_ms, success)