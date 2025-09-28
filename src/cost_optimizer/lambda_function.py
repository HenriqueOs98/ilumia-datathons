"""
Cost Optimization Lambda Function for ONS Data Platform
Analyzes resource utilization and provides cost optimization recommendations
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
ce = boto3.client('ce')
lambda_client = boto3.client('lambda')
s3 = boto3.client('s3')
sns = boto3.client('sns')

def lambda_handler(event, context):
    """
    Main handler for cost optimization analysis
    """
    try:
        environment = os.environ.get('ENVIRONMENT', 'dev')
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        
        logger.info(f"Starting cost optimization analysis for environment: {environment}")
        
        # Analyze different cost components
        recommendations = []
        
        # 1. Lambda function optimization
        lambda_recommendations = analyze_lambda_costs(environment)
        recommendations.extend(lambda_recommendations)
        
        # 2. S3 storage optimization
        s3_recommendations = analyze_s3_costs(environment)
        recommendations.extend(s3_recommendations)
        
        # 3. CloudWatch logs optimization
        logs_recommendations = analyze_logs_costs(environment)
        recommendations.extend(logs_recommendations)
        
        # 4. Overall cost trends
        cost_trends = analyze_cost_trends(environment)
        
        # Generate report
        report = generate_cost_report(recommendations, cost_trends, environment)
        
        # Send notification if there are actionable recommendations
        if recommendations:
            send_cost_optimization_notification(report, sns_topic_arn)
        
        logger.info(f"Cost optimization analysis completed. Found {len(recommendations)} recommendations")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Cost optimization analysis completed',
                'recommendations_count': len(recommendations),
                'report': report
            })
        }
        
    except Exception as e:
        logger.error(f"Error in cost optimization analysis: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def analyze_lambda_costs(environment: str) -> List[Dict[str, Any]]:
    """
    Analyze Lambda function costs and provide optimization recommendations
    """
    recommendations = []
    
    try:
        # Get Lambda functions for this environment
        functions = lambda_client.list_functions()
        
        for function in functions['Functions']:
            function_name = function['FunctionName']
            
            if environment not in function_name:
                continue
                
            # Get CloudWatch metrics for the function
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=7)
            
            # Check memory utilization
            memory_stats = get_metric_statistics(
                'AWS/Lambda',
                'Duration',
                [{'Name': 'FunctionName', 'Value': function_name}],
                start_time,
                end_time
            )
            
            # Check invocation count
            invocation_stats = get_metric_statistics(
                'AWS/Lambda',
                'Invocations',
                [{'Name': 'FunctionName', 'Value': function_name}],
                start_time,
                end_time
            )
            
            # Analyze and provide recommendations
            if memory_stats and len(memory_stats) > 0:
                avg_duration = sum(point['Average'] for point in memory_stats) / len(memory_stats)
                configured_memory = function['MemorySize']
                
                # If function consistently runs under 30 seconds with high memory, suggest optimization
                if avg_duration < 30000 and configured_memory > 1024:
                    recommendations.append({
                        'type': 'lambda_memory_optimization',
                        'resource': function_name,
                        'current_memory': configured_memory,
                        'suggested_memory': max(512, configured_memory // 2),
                        'potential_savings': f"~{((configured_memory - max(512, configured_memory // 2)) / configured_memory) * 100:.1f}%",
                        'description': f"Function {function_name} may be over-provisioned for memory"
                    })
            
            # Check for unused functions
            if invocation_stats and len(invocation_stats) == 0:
                recommendations.append({
                    'type': 'lambda_unused_function',
                    'resource': function_name,
                    'description': f"Function {function_name} has not been invoked in the last 7 days",
                    'suggestion': "Consider removing if no longer needed"
                })
                
    except Exception as e:
        logger.error(f"Error analyzing Lambda costs: {str(e)}")
    
    return recommendations

def analyze_s3_costs(environment: str) -> List[Dict[str, Any]]:
    """
    Analyze S3 storage costs and provide optimization recommendations
    """
    recommendations = []
    
    try:
        # List buckets for this environment
        buckets = s3.list_buckets()
        
        for bucket in buckets['Buckets']:
            bucket_name = bucket['Name']
            
            if environment not in bucket_name:
                continue
            
            try:
                # Get bucket size metrics
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                size_stats = get_metric_statistics(
                    'AWS/S3',
                    'BucketSizeBytes',
                    [
                        {'Name': 'BucketName', 'Value': bucket_name},
                        {'Name': 'StorageType', 'Value': 'StandardStorage'}
                    ],
                    start_time,
                    end_time,
                    period=86400  # Daily
                )
                
                if size_stats and len(size_stats) > 0:
                    latest_size = size_stats[-1]['Average']
                    size_gb = latest_size / (1024**3)
                    
                    # Recommend lifecycle policies for large buckets
                    if size_gb > 100:  # 100 GB threshold
                        recommendations.append({
                            'type': 's3_lifecycle_policy',
                            'resource': bucket_name,
                            'current_size_gb': round(size_gb, 2),
                            'description': f"Bucket {bucket_name} is {size_gb:.1f} GB",
                            'suggestion': "Consider implementing lifecycle policies to transition old data to cheaper storage classes"
                        })
                
            except Exception as e:
                logger.warning(f"Could not analyze bucket {bucket_name}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error analyzing S3 costs: {str(e)}")
    
    return recommendations

def analyze_logs_costs(environment: str) -> List[Dict[str, Any]]:
    """
    Analyze CloudWatch Logs costs and provide optimization recommendations
    """
    recommendations = []
    
    try:
        logs_client = boto3.client('logs')
        
        # Get log groups for this environment
        log_groups = logs_client.describe_log_groups()
        
        for log_group in log_groups['logGroups']:
            log_group_name = log_group['logGroupName']
            
            if environment not in log_group_name:
                continue
            
            # Check retention policy
            retention_days = log_group.get('retentionInDays')
            stored_bytes = log_group.get('storedBytes', 0)
            
            # Recommend retention policies for log groups without them
            if not retention_days and stored_bytes > 1024**3:  # 1 GB
                recommendations.append({
                    'type': 'logs_retention_policy',
                    'resource': log_group_name,
                    'stored_gb': round(stored_bytes / (1024**3), 2),
                    'description': f"Log group {log_group_name} has no retention policy",
                    'suggestion': "Set appropriate retention policy to control storage costs"
                })
            
            # Recommend shorter retention for very long retention periods
            elif retention_days and retention_days > 365 and stored_bytes > 5 * 1024**3:  # 5 GB
                recommendations.append({
                    'type': 'logs_retention_optimization',
                    'resource': log_group_name,
                    'current_retention': retention_days,
                    'stored_gb': round(stored_bytes / (1024**3), 2),
                    'suggested_retention': 90,
                    'description': f"Log group {log_group_name} has {retention_days} days retention",
                    'suggestion': "Consider reducing retention period if long-term storage is not required"
                })
                
    except Exception as e:
        logger.error(f"Error analyzing CloudWatch Logs costs: {str(e)}")
    
    return recommendations

def analyze_cost_trends(environment: str) -> Dict[str, Any]:
    """
    Analyze overall cost trends for the platform
    """
    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['BlendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ],
            Filter={
                'Tags': {
                    'Key': 'Project',
                    'Values': ['ons-data-platform']
                }
            }
        )
        
        # Process cost data
        total_cost = 0
        service_costs = {}
        
        for result in response['ResultsByTime']:
            for group in result['Groups']:
                service = group['Keys'][0]
                cost = float(group['Metrics']['BlendedCost']['Amount'])
                total_cost += cost
                
                if service not in service_costs:
                    service_costs[service] = 0
                service_costs[service] += cost
        
        return {
            'total_cost_30_days': round(total_cost, 2),
            'service_breakdown': {k: round(v, 2) for k, v in sorted(service_costs.items(), key=lambda x: x[1], reverse=True)},
            'analysis_period': f"{start_date} to {end_date}"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing cost trends: {str(e)}")
        return {}

def get_metric_statistics(namespace: str, metric_name: str, dimensions: List[Dict], 
                         start_time: datetime, end_time: datetime, period: int = 300) -> List[Dict]:
    """
    Get CloudWatch metric statistics
    """
    try:
        response = cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Average', 'Sum']
        )
        return response['Datapoints']
    except Exception as e:
        logger.error(f"Error getting metric statistics: {str(e)}")
        return []

def generate_cost_report(recommendations: List[Dict], cost_trends: Dict, environment: str) -> Dict[str, Any]:
    """
    Generate a comprehensive cost optimization report
    """
    report = {
        'environment': environment,
        'analysis_date': datetime.utcnow().isoformat(),
        'summary': {
            'total_recommendations': len(recommendations),
            'recommendation_types': {}
        },
        'recommendations': recommendations,
        'cost_trends': cost_trends
    }
    
    # Count recommendation types
    for rec in recommendations:
        rec_type = rec['type']
        if rec_type not in report['summary']['recommendation_types']:
            report['summary']['recommendation_types'][rec_type] = 0
        report['summary']['recommendation_types'][rec_type] += 1
    
    return report

def send_cost_optimization_notification(report: Dict, sns_topic_arn: str):
    """
    Send cost optimization notification via SNS
    """
    try:
        if not sns_topic_arn:
            logger.warning("No SNS topic ARN provided, skipping notification")
            return
        
        subject = f"ONS Data Platform Cost Optimization Report - {report['environment']}"
        
        message = f"""
Cost Optimization Analysis Complete

Environment: {report['environment']}
Analysis Date: {report['analysis_date']}

Summary:
- Total Recommendations: {report['summary']['total_recommendations']}

Cost Trends (Last 30 days):
- Total Cost: ${report['cost_trends'].get('total_cost_30_days', 'N/A')}

Top Recommendations:
"""
        
        for i, rec in enumerate(report['recommendations'][:5], 1):
            message += f"\n{i}. {rec['type']}: {rec['description']}"
        
        if len(report['recommendations']) > 5:
            message += f"\n... and {len(report['recommendations']) - 5} more recommendations"
        
        message += "\n\nPlease review the full report in CloudWatch Logs for detailed recommendations."
        
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info("Cost optimization notification sent successfully")
        
    except Exception as e:
        logger.error(f"Error sending cost optimization notification: {str(e)}")