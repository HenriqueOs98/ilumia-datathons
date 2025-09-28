"""
InfluxDB Health Check and Metrics Lambda Function.

This Lambda function monitors InfluxDB connectivity, performance, and resource
utilization, publishing custom CloudWatch metrics for observability.
"""

import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

# Import shared utilities
import sys
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))

from influxdb_client import Point, WritePrecision
from shared_utils.influxdb_client import InfluxDBHandler, InfluxDBConnectionError
from shared_utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(__name__)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
pricing = boto3.client('pricing', region_name='us-east-1')  # Pricing API only available in us-east-1


class InfluxDBMonitor:
    """
    InfluxDB monitoring and health check service.
    
    Performs comprehensive health checks, collects performance metrics,
    and publishes CloudWatch metrics for monitoring and alerting.
    """
    
    def __init__(self):
        """Initialize InfluxDB monitor."""
        self.influx_handler = InfluxDBHandler()
        self.namespace = os.getenv('CLOUDWATCH_NAMESPACE', 'ONS/InfluxDB')
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Performance test queries
        self.test_queries = {
            'simple_query': '''
                from(bucket: "generation_data")
                |> range(start: -1h)
                |> filter(fn: (r) => r["_measurement"] == "power_mw")
                |> limit(n: 10)
            ''',
            'aggregation_query': '''
                from(bucket: "generation_data")
                |> range(start: -24h)
                |> filter(fn: (r) => r["_measurement"] == "power_mw")
                |> aggregateWindow(every: 1h, fn: mean)
                |> yield(name: "hourly_average")
            ''',
            'complex_query': '''
                from(bucket: "generation_data")
                |> range(start: -7d)
                |> filter(fn: (r) => r["_measurement"] == "power_mw")
                |> group(columns: ["region"])
                |> aggregateWindow(every: 1d, fn: mean)
                |> pivot(rowKey:["_time"], columnKey: ["region"], valueColumn: "_value")
            '''
        }
        
        logger.info(f"Initialized InfluxDB monitor for environment: {self.environment}")
    
    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive InfluxDB health check.
        
        Returns:
            Health check results with detailed metrics
        """
        logger.info("Starting InfluxDB health check")
        start_time = time.time()
        
        try:
            # Basic connectivity check
            health_result = self.influx_handler.health_check()
            
            # Additional health metrics
            health_result.update({
                'connectivity_status': 'connected' if health_result['status'] == 'healthy' else 'disconnected',
                'total_check_time_ms': round((time.time() - start_time) * 1000, 2),
                'environment': self.environment,
                'region': self.region
            })
            
            # Publish connectivity metrics
            self._publish_connectivity_metrics(health_result)
            
            logger.info(f"Health check completed: {health_result['status']}")
            return health_result
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            error_result = {
                'status': 'unhealthy',
                'error': str(e),
                'connectivity_status': 'disconnected',
                'total_check_time_ms': round((time.time() - start_time) * 1000, 2),
                'environment': self.environment,
                'region': self.region,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Publish error metrics
            self._publish_connectivity_metrics(error_result)
            return error_result
    
    def measure_query_performance(self) -> Dict[str, Any]:
        """
        Measure query performance across different query types.
        
        Returns:
            Performance metrics for various query types
        """
        logger.info("Starting query performance measurement")
        performance_results = {}
        
        for query_name, query in self.test_queries.items():
            start_time = time.time()
            try:
                # Execute query
                results = self.influx_handler.query_flux(query)
                
                # Calculate metrics
                execution_time = (time.time() - start_time) * 1000
                result_count = len(results)
                
                performance_results[query_name] = {
                    'execution_time_ms': round(execution_time, 2),
                    'result_count': result_count,
                    'throughput_results_per_sec': round(result_count / (execution_time / 1000), 2) if execution_time > 0 else 0,
                    'status': 'success'
                }
                
                logger.info(f"Query {query_name} completed in {execution_time:.2f}ms, {result_count} results")
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                performance_results[query_name] = {
                    'execution_time_ms': round(execution_time, 2),
                    'result_count': 0,
                    'throughput_results_per_sec': 0,
                    'status': 'error',
                    'error': str(e)
                }
                
                logger.error(f"Query {query_name} failed after {execution_time:.2f}ms: {e}")
        
        # Publish performance metrics
        self._publish_performance_metrics(performance_results)
        
        return performance_results
    
    def measure_write_performance(self) -> Dict[str, Any]:
        """
        Measure write performance with test data.
        
        Returns:
            Write performance metrics
        """
        logger.info("Starting write performance measurement")
        
        # Generate test data points
        test_points = []
        current_time = datetime.now(timezone.utc)
        
        for i in range(100):  # Test with 100 points
            point = Point("performance_test") \
                .tag("test_run", "monitor") \
                .tag("environment", self.environment) \
                .field("test_value", i * 1.5) \
                .field("sequence", i) \
                .time(current_time - timedelta(seconds=i), WritePrecision.NS)
            test_points.append(point)
        
        # Measure write performance
        start_time = time.time()
        try:
            success = self.influx_handler.write_points(test_points)
            write_time = (time.time() - start_time) * 1000
            
            write_results = {
                'write_time_ms': round(write_time, 2),
                'points_written': len(test_points),
                'write_throughput_points_per_sec': round(len(test_points) / (write_time / 1000), 2) if write_time > 0 else 0,
                'status': 'success' if success else 'failed'
            }
            
            logger.info(f"Write test completed: {len(test_points)} points in {write_time:.2f}ms")
            
        except Exception as e:
            write_time = (time.time() - start_time) * 1000
            write_results = {
                'write_time_ms': round(write_time, 2),
                'points_written': 0,
                'write_throughput_points_per_sec': 0,
                'status': 'error',
                'error': str(e)
            }
            
            logger.error(f"Write test failed after {write_time:.2f}ms: {e}")
        
        # Publish write performance metrics
        self._publish_write_metrics(write_results)
        
        return write_results
    
    def collect_resource_metrics(self) -> Dict[str, Any]:
        """
        Collect InfluxDB resource utilization metrics.
        
        Returns:
            Resource utilization metrics
        """
        logger.info("Collecting resource utilization metrics")
        
        try:
            # Query system metrics from InfluxDB internal buckets
            system_query = '''
                from(bucket: "_monitoring")
                |> range(start: -5m)
                |> filter(fn: (r) => r["_measurement"] == "system")
                |> last()
            '''
            
            system_metrics = self.influx_handler.query_flux(system_query)
            
            # Extract resource metrics
            resource_data = {
                'cpu_usage_percent': 0,
                'memory_usage_percent': 0,
                'disk_usage_percent': 0,
                'active_connections': 0,
                'query_queue_length': 0
            }
            
            for record in system_metrics:
                field = record.get('field', '')
                value = record.get('value', 0)
                
                if field == 'cpu_usage':
                    resource_data['cpu_usage_percent'] = float(value)
                elif field == 'memory_usage':
                    resource_data['memory_usage_percent'] = float(value)
                elif field == 'disk_usage':
                    resource_data['disk_usage_percent'] = float(value)
                elif field == 'connections':
                    resource_data['active_connections'] = int(value)
                elif field == 'query_queue':
                    resource_data['query_queue_length'] = int(value)
            
            # Publish resource metrics
            self._publish_resource_metrics(resource_data)
            
            logger.info("Resource metrics collected successfully")
            return resource_data
            
        except Exception as e:
            logger.warning(f"Could not collect resource metrics: {e}")
            # Return default values if system metrics are not available
            default_metrics = {
                'cpu_usage_percent': 0,
                'memory_usage_percent': 0,
                'disk_usage_percent': 0,
                'active_connections': 0,
                'query_queue_length': 0,
                'error': str(e)
            }
            
            self._publish_resource_metrics(default_metrics)
            return default_metrics
    
    def estimate_costs(self) -> Dict[str, Any]:
        """
        Estimate InfluxDB usage costs.
        
        Returns:
            Cost estimation metrics
        """
        logger.info("Estimating InfluxDB costs")
        
        try:
            # Get instance type from environment
            instance_type = os.getenv('INFLUXDB_INSTANCE_TYPE', 'db.influx.medium')
            
            # Query data volume metrics
            volume_query = '''
                from(bucket: "_monitoring")
                |> range(start: -1h)
                |> filter(fn: (r) => r["_measurement"] == "storage")
                |> filter(fn: (r) => r["_field"] == "bytes_used")
                |> last()
            '''
            
            volume_metrics = self.influx_handler.query_flux(volume_query)
            storage_bytes = 0
            
            if volume_metrics:
                storage_bytes = volume_metrics[0].get('value', 0)
            
            # Estimate costs (simplified calculation)
            storage_gb = storage_bytes / (1024 ** 3)
            
            # Rough cost estimates (these would need to be updated with actual AWS pricing)
            estimated_costs = {
                'instance_type': instance_type,
                'storage_gb': round(storage_gb, 2),
                'estimated_hourly_cost_usd': self._estimate_hourly_cost(instance_type),
                'estimated_daily_cost_usd': self._estimate_hourly_cost(instance_type) * 24,
                'estimated_monthly_cost_usd': self._estimate_hourly_cost(instance_type) * 24 * 30,
                'storage_cost_monthly_usd': storage_gb * 0.10,  # Rough estimate
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Publish cost metrics
            self._publish_cost_metrics(estimated_costs)
            
            logger.info(f"Cost estimation completed: ${estimated_costs['estimated_daily_cost_usd']:.2f}/day")
            return estimated_costs
            
        except Exception as e:
            logger.error(f"Cost estimation failed: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _estimate_hourly_cost(self, instance_type: str) -> float:
        """
        Estimate hourly cost for InfluxDB instance type.
        
        Args:
            instance_type: InfluxDB instance type
            
        Returns:
            Estimated hourly cost in USD
        """
        # Simplified cost mapping (would need actual AWS pricing API integration)
        cost_mapping = {
            'db.influx.small': 0.25,
            'db.influx.medium': 0.50,
            'db.influx.large': 1.00,
            'db.influx.xlarge': 2.00,
            'db.influx.2xlarge': 4.00
        }
        
        return cost_mapping.get(instance_type, 0.50)  # Default to medium cost
    
    def _publish_connectivity_metrics(self, health_data: Dict[str, Any]):
        """Publish connectivity metrics to CloudWatch."""
        try:
            metrics = [
                {
                    'MetricName': 'ConnectionStatus',
                    'Value': 1 if health_data['status'] == 'healthy' else 0,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment},
                        {'Name': 'Region', 'Value': self.region}
                    ]
                },
                {
                    'MetricName': 'HealthCheckResponseTime',
                    'Value': health_data.get('response_time_ms', 0),
                    'Unit': 'Milliseconds',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment},
                        {'Name': 'Region', 'Value': self.region}
                    ]
                }
            ]
            
            cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics
            )
            
            logger.debug("Published connectivity metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to publish connectivity metrics: {e}")
    
    def _publish_performance_metrics(self, performance_data: Dict[str, Any]):
        """Publish query performance metrics to CloudWatch."""
        try:
            metrics = []
            
            for query_type, data in performance_data.items():
                if data['status'] == 'success':
                    metrics.extend([
                        {
                            'MetricName': 'QueryExecutionTime',
                            'Value': data['execution_time_ms'],
                            'Unit': 'Milliseconds',
                            'Dimensions': [
                                {'Name': 'Environment', 'Value': self.environment},
                                {'Name': 'QueryType', 'Value': query_type}
                            ]
                        },
                        {
                            'MetricName': 'QueryThroughput',
                            'Value': data['throughput_results_per_sec'],
                            'Unit': 'Count/Second',
                            'Dimensions': [
                                {'Name': 'Environment', 'Value': self.environment},
                                {'Name': 'QueryType', 'Value': query_type}
                            ]
                        }
                    ])
                else:
                    metrics.append({
                        'MetricName': 'QueryErrors',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'Environment', 'Value': self.environment},
                            {'Name': 'QueryType', 'Value': query_type}
                        ]
                    })
            
            if metrics:
                cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metrics
                )
                
                logger.debug("Published performance metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to publish performance metrics: {e}")
    
    def _publish_write_metrics(self, write_data: Dict[str, Any]):
        """Publish write performance metrics to CloudWatch."""
        try:
            metrics = []
            
            if write_data['status'] == 'success':
                metrics.extend([
                    {
                        'MetricName': 'WriteLatency',
                        'Value': write_data['write_time_ms'],
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': 'Environment', 'Value': self.environment}
                        ]
                    },
                    {
                        'MetricName': 'WriteThroughput',
                        'Value': write_data['write_throughput_points_per_sec'],
                        'Unit': 'Count/Second',
                        'Dimensions': [
                            {'Name': 'Environment', 'Value': self.environment}
                        ]
                    }
                ])
            else:
                metrics.append({
                    'MetricName': 'WriteErrors',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                })
            
            if metrics:
                cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metrics
                )
                
                logger.debug("Published write metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to publish write metrics: {e}")
    
    def _publish_resource_metrics(self, resource_data: Dict[str, Any]):
        """Publish resource utilization metrics to CloudWatch."""
        try:
            metrics = [
                {
                    'MetricName': 'CPUUtilization',
                    'Value': resource_data.get('cpu_usage_percent', 0),
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                },
                {
                    'MetricName': 'MemoryUtilization',
                    'Value': resource_data.get('memory_usage_percent', 0),
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                },
                {
                    'MetricName': 'DiskUtilization',
                    'Value': resource_data.get('disk_usage_percent', 0),
                    'Unit': 'Percent',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                },
                {
                    'MetricName': 'ActiveConnections',
                    'Value': resource_data.get('active_connections', 0),
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                }
            ]
            
            cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics
            )
            
            logger.debug("Published resource metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to publish resource metrics: {e}")
    
    def _publish_cost_metrics(self, cost_data: Dict[str, Any]):
        """Publish cost estimation metrics to CloudWatch."""
        try:
            metrics = [
                {
                    'MetricName': 'EstimatedDailyCost',
                    'Value': cost_data.get('estimated_daily_cost_usd', 0),
                    'Unit': 'None',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment},
                        {'Name': 'InstanceType', 'Value': cost_data.get('instance_type', 'unknown')}
                    ]
                },
                {
                    'MetricName': 'StorageUsage',
                    'Value': cost_data.get('storage_gb', 0),
                    'Unit': 'None',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': self.environment}
                    ]
                }
            ]
            
            cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics
            )
            
            logger.debug("Published cost metrics to CloudWatch")
            
        except Exception as e:
            logger.error(f"Failed to publish cost metrics: {e}")


def lambda_handler(event, context):
    """
    Lambda handler for InfluxDB monitoring.
    
    Args:
        event: Lambda event data
        context: Lambda context object
        
    Returns:
        Monitoring results and metrics
    """
    logger.info("Starting InfluxDB monitoring Lambda")
    
    try:
        monitor = InfluxDBMonitor()
        
        # Perform all monitoring checks
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': monitor.environment,
            'health_check': monitor.perform_health_check(),
            'query_performance': monitor.measure_query_performance(),
            'write_performance': monitor.measure_write_performance(),
            'resource_metrics': monitor.collect_resource_metrics(),
            'cost_estimation': monitor.estimate_costs()
        }
        
        # Overall status
        overall_status = 'healthy' if results['health_check']['status'] == 'healthy' else 'unhealthy'
        results['overall_status'] = overall_status
        
        logger.info(f"InfluxDB monitoring completed successfully. Status: {overall_status}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(results, default=str),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
        
    except Exception as e:
        logger.error(f"InfluxDB monitoring failed: {e}")
        
        error_response = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'error',
            'error': str(e),
            'environment': os.getenv('ENVIRONMENT', 'unknown')
        }
        
        return {
            'statusCode': 500,
            'body': json.dumps(error_response),
            'headers': {
                'Content-Type': 'application/json'
            }
        }