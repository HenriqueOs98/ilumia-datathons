#!/usr/bin/env python3
"""
Test Migration Infrastructure

This script tests the migration infrastructure components to ensure
they are properly configured and accessible before running the actual migration.

Requirements addressed: 2.1, 2.2, 2.3
"""

import argparse
import boto3
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InfrastructureTester:
    """
    Test migration infrastructure components
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize the infrastructure tester
        
        Args:
            region: AWS region
        """
        self.region = region
        
        # Initialize AWS clients
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.stepfunctions_client = boto3.client('stepfunctions', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.timestream_query = boto3.client('timestream-query', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        
        # Get infrastructure details from environment
        self.migration_orchestrator_arn = os.environ.get('MIGRATION_ORCHESTRATOR_LAMBDA_ARN', '')
        self.migration_state_machine_arn = os.environ.get('MIGRATION_STATE_MACHINE_ARN', '')
        self.s3_export_bucket = os.environ.get('S3_EXPORT_BUCKET', '')
        self.influxdb_url = os.environ.get('INFLUXDB_URL', '')
        self.influxdb_token = os.environ.get('INFLUXDB_TOKEN', '')
        self.influxdb_org = os.environ.get('INFLUXDB_ORG', '')
    
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all infrastructure tests
        
        Returns:
            Dictionary with test results
        """
        logger.info("Starting infrastructure tests...")
        
        test_results = {
            'overall_status': 'passed',
            'test_timestamp': datetime.utcnow().isoformat(),
            'tests': {}
        }
        
        # Test categories
        tests = [
            ('environment_variables', self._test_environment_variables),
            ('aws_credentials', self._test_aws_credentials),
            ('lambda_functions', self._test_lambda_functions),
            ('step_functions', self._test_step_functions),
            ('s3_buckets', self._test_s3_buckets),
            ('timestream_access', self._test_timestream_access),
            ('influxdb_connectivity', self._test_influxdb_connectivity),
            ('dynamodb_tables', self._test_dynamodb_tables)
        ]
        
        for test_name, test_function in tests:
            logger.info(f"Running test: {test_name}")
            
            try:
                result = test_function()
                test_results['tests'][test_name] = result
                
                if result['status'] == 'failed':
                    test_results['overall_status'] = 'failed'
                elif result['status'] == 'warning' and test_results['overall_status'] == 'passed':
                    test_results['overall_status'] = 'warning'
                
                logger.info(f"Test {test_name}: {result['status']}")
                
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {str(e)}")
                test_results['tests'][test_name] = {
                    'status': 'failed',
                    'error': str(e),
                    'details': {}
                }
                test_results['overall_status'] = 'failed'
        
        logger.info(f"Infrastructure tests completed with overall status: {test_results['overall_status']}")
        return test_results
    
    def _test_environment_variables(self) -> Dict[str, Any]:
        """Test required environment variables"""
        required_vars = {
            'MIGRATION_ORCHESTRATOR_LAMBDA_ARN': self.migration_orchestrator_arn,
            'MIGRATION_STATE_MACHINE_ARN': self.migration_state_machine_arn,
            'S3_EXPORT_BUCKET': self.s3_export_bucket,
            'INFLUXDB_URL': self.influxdb_url,
            'INFLUXDB_TOKEN': self.influxdb_token,
            'INFLUXDB_ORG': self.influxdb_org
        }
        
        missing_vars = []
        present_vars = []
        
        for var_name, var_value in required_vars.items():
            if not var_value:
                missing_vars.append(var_name)
            else:
                present_vars.append(var_name)
        
        if missing_vars:
            return {
                'status': 'failed',
                'error': f'Missing required environment variables: {", ".join(missing_vars)}',
                'details': {
                    'missing_variables': missing_vars,
                    'present_variables': present_vars
                }
            }
        
        return {
            'status': 'passed',
            'message': 'All required environment variables are set',
            'details': {
                'present_variables': present_vars
            }
        }
    
    def _test_aws_credentials(self) -> Dict[str, Any]:
        """Test AWS credentials and permissions"""
        try:
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            
            return {
                'status': 'passed',
                'message': 'AWS credentials are valid',
                'details': {
                    'account_id': identity.get('Account'),
                    'user_arn': identity.get('Arn'),
                    'region': self.region
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'AWS credentials test failed: {str(e)}',
                'details': {}
            }
    
    def _test_lambda_functions(self) -> Dict[str, Any]:
        """Test Lambda function accessibility"""
        if not self.migration_orchestrator_arn:
            return {
                'status': 'failed',
                'error': 'Migration orchestrator Lambda ARN not configured',
                'details': {}
            }
        
        try:
            # Test orchestrator function
            response = self.lambda_client.get_function(
                FunctionName=self.migration_orchestrator_arn
            )
            
            function_config = response['Configuration']
            
            # Test function invocation with a simple test payload
            test_response = self.lambda_client.invoke(
                FunctionName=self.migration_orchestrator_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'get_status',
                    'job_id': 'test-infrastructure-check'
                })
            )
            
            payload = json.loads(test_response['Payload'].read())
            
            return {
                'status': 'passed',
                'message': 'Lambda functions are accessible',
                'details': {
                    'function_name': function_config['FunctionName'],
                    'runtime': function_config['Runtime'],
                    'last_modified': function_config['LastModified'],
                    'test_invocation_status': test_response['StatusCode']
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Lambda function test failed: {str(e)}',
                'details': {}
            }
    
    def _test_step_functions(self) -> Dict[str, Any]:
        """Test Step Functions state machine"""
        if not self.migration_state_machine_arn:
            return {
                'status': 'failed',
                'error': 'Migration state machine ARN not configured',
                'details': {}
            }
        
        try:
            response = self.stepfunctions_client.describe_state_machine(
                stateMachineArn=self.migration_state_machine_arn
            )
            
            return {
                'status': 'passed',
                'message': 'Step Functions state machine is accessible',
                'details': {
                    'name': response['name'],
                    'status': response['status'],
                    'creation_date': response['creationDate'].isoformat(),
                    'role_arn': response['roleArn']
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Step Functions test failed: {str(e)}',
                'details': {}
            }
    
    def _test_s3_buckets(self) -> Dict[str, Any]:
        """Test S3 bucket accessibility"""
        if not self.s3_export_bucket:
            return {
                'status': 'warning',
                'error': 'S3 export bucket not configured',
                'details': {}
            }
        
        try:
            # Test bucket existence and access
            self.s3_client.head_bucket(Bucket=self.s3_export_bucket)
            
            # Test write permissions by creating a test object
            test_key = f"infrastructure-test/{datetime.utcnow().isoformat()}.txt"
            test_content = "Infrastructure test file"
            
            self.s3_client.put_object(
                Bucket=self.s3_export_bucket,
                Key=test_key,
                Body=test_content.encode('utf-8')
            )
            
            # Clean up test object
            self.s3_client.delete_object(
                Bucket=self.s3_export_bucket,
                Key=test_key
            )
            
            return {
                'status': 'passed',
                'message': 'S3 bucket is accessible with read/write permissions',
                'details': {
                    'bucket_name': self.s3_export_bucket,
                    'test_key': test_key
                }
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'S3 bucket test failed: {str(e)}',
                'details': {}
            }
    
    def _test_timestream_access(self) -> Dict[str, Any]:
        """Test Timestream query access"""
        try:
            # Test basic Timestream access by listing databases
            response = self.timestream_query.list_databases()
            
            databases = [db['DatabaseName'] for db in response.get('Databases', [])]
            
            # Check if the expected database exists
            expected_database = 'ons_energy_data'
            database_exists = expected_database in databases
            
            if not database_exists:
                return {
                    'status': 'warning',
                    'message': f'Expected database "{expected_database}" not found',
                    'details': {
                        'available_databases': databases,
                        'expected_database': expected_database
                    }
                }
            
            # Test table listing for the expected database
            try:
                tables_response = self.timestream_query.list_tables(
                    DatabaseName=expected_database
                )
                tables = [table['TableName'] for table in tables_response.get('Tables', [])]
                
                return {
                    'status': 'passed',
                    'message': 'Timestream access is working',
                    'details': {
                        'available_databases': databases,
                        'tables_in_target_database': tables
                    }
                }
                
            except Exception as e:
                return {
                    'status': 'warning',
                    'message': f'Can access Timestream but cannot list tables: {str(e)}',
                    'details': {
                        'available_databases': databases
                    }
                }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'Timestream access test failed: {str(e)}',
                'details': {}
            }
    
    def _test_influxdb_connectivity(self) -> Dict[str, Any]:
        """Test InfluxDB connectivity"""
        if not self.influxdb_url or not self.influxdb_token:
            return {
                'status': 'failed',
                'error': 'InfluxDB URL or token not configured',
                'details': {}
            }
        
        try:
            from influxdb_client import InfluxDBClient
            
            # Test InfluxDB connection
            client = InfluxDBClient(
                url=self.influxdb_url,
                token=self.influxdb_token,
                org=self.influxdb_org
            )
            
            # Test basic connectivity by getting health status
            health = client.health()
            
            # Test query API
            query_api = client.query_api()
            
            # Simple test query
            test_query = 'buckets() |> limit(n:1)'
            result = query_api.query(test_query)
            
            client.close()
            
            return {
                'status': 'passed',
                'message': 'InfluxDB connectivity is working',
                'details': {
                    'health_status': health.status,
                    'influxdb_url': self.influxdb_url,
                    'organization': self.influxdb_org,
                    'query_test': 'successful'
                }
            }
            
        except ImportError:
            return {
                'status': 'failed',
                'error': 'InfluxDB client library not installed. Run: pip install influxdb-client',
                'details': {}
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': f'InfluxDB connectivity test failed: {str(e)}',
                'details': {}
            }
    
    def _test_dynamodb_tables(self) -> Dict[str, Any]:
        """Test DynamoDB table access for migration tracking"""
        try:
            # List tables to check basic DynamoDB access
            tables = list(self.dynamodb.tables.all())
            table_names = [table.name for table in tables]
            
            # Look for migration-related tables
            migration_tables = [name for name in table_names if 'migration' in name.lower()]
            
            return {
                'status': 'passed',
                'message': 'DynamoDB access is working',
                'details': {
                    'total_tables': len(table_names),
                    'migration_related_tables': migration_tables
                }
            }
            
        except Exception as e:
            return {
                'status': 'warning',
                'error': f'DynamoDB test failed: {str(e)}',
                'details': {}
            }
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable test report"""
        report = []
        report.append("="*60)
        report.append("MIGRATION INFRASTRUCTURE TEST REPORT")
        report.append("="*60)
        report.append(f"Test Timestamp: {results['test_timestamp']}")
        report.append(f"Overall Status: {results['overall_status'].upper()}")
        report.append("")
        
        # Status summary
        passed_tests = len([t for t in results['tests'].values() if t['status'] == 'passed'])
        failed_tests = len([t for t in results['tests'].values() if t['status'] == 'failed'])
        warning_tests = len([t for t in results['tests'].values() if t['status'] == 'warning'])
        
        report.append("Test Summary:")
        report.append(f"  ✓ Passed: {passed_tests}")
        report.append(f"  ⚠ Warnings: {warning_tests}")
        report.append(f"  ✗ Failed: {failed_tests}")
        report.append("")
        
        # Detailed results
        report.append("Detailed Results:")
        report.append("-" * 40)
        
        for test_name, test_result in results['tests'].items():
            status_icon = {
                'passed': '✓',
                'warning': '⚠',
                'failed': '✗'
            }.get(test_result['status'], '?')
            
            report.append(f"{status_icon} {test_name.replace('_', ' ').title()}: {test_result['status'].upper()}")
            
            if test_result.get('message'):
                report.append(f"    {test_result['message']}")
            
            if test_result.get('error'):
                report.append(f"    Error: {test_result['error']}")
            
            report.append("")
        
        # Recommendations
        report.append("Recommendations:")
        report.append("-" * 20)
        
        if results['overall_status'] == 'passed':
            report.append("✓ All tests passed. Infrastructure is ready for migration.")
        elif results['overall_status'] == 'warning':
            report.append("⚠ Some tests have warnings. Review issues before migration.")
            report.append("  - Check warning messages above")
            report.append("  - Ensure all required resources are properly configured")
        else:
            report.append("✗ Some tests failed. Fix issues before attempting migration.")
            report.append("  - Review error messages above")
            report.append("  - Ensure all required environment variables are set")
            report.append("  - Verify AWS permissions and resource accessibility")
        
        report.append("")
        report.append("="*60)
        
        return "\n".join(report)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Test migration infrastructure')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--output-file', help='Save test results to file')
    parser.add_argument('--json-output', action='store_true', help='Output results in JSON format')
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = InfrastructureTester(region=args.region)
    
    try:
        # Run tests
        results = tester.run_all_tests()
        
        if args.json_output:
            # Output JSON results
            print(json.dumps(results, indent=2, default=str))
        else:
            # Generate and display report
            report = tester.generate_test_report(results)
            print(report)
        
        # Save to file if requested
        if args.output_file:
            with open(args.output_file, 'w') as f:
                if args.json_output:
                    json.dump(results, f, indent=2, default=str)
                else:
                    f.write(tester.generate_test_report(results))
            logger.info(f"Test results saved to: {args.output_file}")
        
        # Exit with appropriate code
        if results['overall_status'] == 'failed':
            sys.exit(1)
        elif results['overall_status'] == 'warning':
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("Infrastructure test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Infrastructure test failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()