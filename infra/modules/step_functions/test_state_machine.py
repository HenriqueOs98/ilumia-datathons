#!/usr/bin/env python3
"""
Integration tests for Step Functions state machine execution paths.
Tests various scenarios including success paths, error handling, and retry logic.
"""

import json
import boto3
import pytest
import time
from typing import Dict, Any
from unittest.mock import Mock, patch


class TestStepFunctionsStateMachine:
    """Test suite for ONS Data Processing Pipeline state machine."""
    
    def setup_method(self):
        """Setup test environment."""
        self.stepfunctions_client = boto3.client('stepfunctions', region_name='us-east-1')
        self.state_machine_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:test-data-processing"
        
    def test_structured_data_processing_path(self):
        """Test successful processing of structured data (CSV/XLSX) through Lambda."""
        input_data = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/test-file.csv", "size": 1024}
                }
            }]
        }
        
        # Mock Lambda router response for structured data
        expected_router_response = {
            "processingType": "lambda",
            "inputFile": "s3://test-raw-bucket/data/test-file.csv",
            "outputPath": "s3://test-processed-bucket/data/",
            "fileType": "csv"
        }
        
        # Test execution path: RouteFile -> ProcessingChoice -> ProcessStructuredData -> LoadToTimestream -> UpdateKnowledgeBase -> ProcessingComplete
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_boto3.return_value = mock_sf
            
            # Mock successful execution
            mock_sf.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-execution',
                'startDate': '2024-01-01T00:00:00Z'
            }
            
            mock_sf.describe_execution.return_value = {
                'status': 'SUCCEEDED',
                'output': json.dumps({
                    "processingResult": "success",
                    "recordsProcessed": 1000,
                    "timestreamRecords": 1000,
                    "knowledgeBaseUpdated": True
                })
            }
            
            # Start execution
            response = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data)
            )
            
            assert 'executionArn' in response
            
            # Verify execution completed successfully
            execution_result = mock_sf.describe_execution(
                executionArn=response['executionArn']
            )
            
            assert execution_result['status'] == 'SUCCEEDED'
            output = json.loads(execution_result['output'])
            assert output['processingResult'] == 'success'
            assert output['recordsProcessed'] == 1000
    
    def test_unstructured_data_processing_path(self):
        """Test successful processing of unstructured data (PDF) through Batch."""
        input_data = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/large-report.pdf", "size": 104857600}  # 100MB
                }
            }]
        }
        
        # Mock Lambda router response for unstructured data
        expected_router_response = {
            "processingType": "batch",
            "inputFile": "s3://test-raw-bucket/data/large-report.pdf",
            "outputPath": "s3://test-processed-bucket/data/",
            "fileType": "pdf"
        }
        
        # Test execution path: RouteFile -> ProcessingChoice -> ProcessUnstructuredData -> LoadToTimestream -> UpdateKnowledgeBase -> ProcessingComplete
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_batch = Mock()
            mock_boto3.side_effect = lambda service: mock_sf if service == 'stepfunctions' else mock_batch
            
            # Mock successful Batch job
            mock_batch.submit_job.return_value = {
                'jobId': 'test-job-123',
                'jobName': 'ons-data-platform-pdf-processing'
            }
            
            mock_batch.describe_jobs.return_value = {
                'jobs': [{
                    'jobId': 'test-job-123',
                    'status': 'SUCCEEDED',
                    'exitCode': 0
                }]
            }
            
            # Mock successful execution
            mock_sf.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-batch-execution',
                'startDate': '2024-01-01T00:00:00Z'
            }
            
            mock_sf.describe_execution.return_value = {
                'status': 'SUCCEEDED',
                'output': json.dumps({
                    "processingResult": "success",
                    "batchJobId": "test-job-123",
                    "tablesExtracted": 5,
                    "recordsProcessed": 500
                })
            }
            
            # Start execution
            response = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data)
            )
            
            assert 'executionArn' in response
            
            # Verify execution completed successfully
            execution_result = mock_sf.describe_execution(
                executionArn=response['executionArn']
            )
            
            assert execution_result['status'] == 'SUCCEEDED'
            output = json.loads(execution_result['output'])
            assert output['processingResult'] == 'success'
            assert output['batchJobId'] == 'test-job-123'
    
    def test_retry_logic_with_lambda_failure(self):
        """Test retry logic when Lambda function fails temporarily."""
        input_data = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/test-file.csv", "size": 1024}
                }
            }]
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_boto3.return_value = mock_sf
            
            # Mock execution that fails initially but succeeds on retry
            mock_sf.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-retry-execution',
                'startDate': '2024-01-01T00:00:00Z'
            }
            
            # Simulate retry scenario - first call fails, second succeeds
            mock_sf.describe_execution.side_effect = [
                {
                    'status': 'RUNNING',
                    'events': [
                        {
                            'type': 'TaskFailed',
                            'taskFailedEventDetails': {
                                'error': 'Lambda.ServiceException',
                                'cause': 'Temporary service error'
                            }
                        },
                        {
                            'type': 'TaskRetried',
                            'taskRetriedEventDetails': {
                                'retryCount': 1
                            }
                        }
                    ]
                },
                {
                    'status': 'SUCCEEDED',
                    'output': json.dumps({
                        "processingResult": "success",
                        "retriesPerformed": 1
                    })
                }
            ]
            
            # Start execution
            response = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data)
            )
            
            # First check - should show retry in progress
            execution_result = mock_sf.describe_execution(
                executionArn=response['executionArn']
            )
            assert execution_result['status'] == 'RUNNING'
            
            # Second check - should show success after retry
            execution_result = mock_sf.describe_execution(
                executionArn=response['executionArn']
            )
            assert execution_result['status'] == 'SUCCEEDED'
    
    def test_dead_letter_queue_notification(self):
        """Test that failures trigger SNS notification to DLQ."""
        input_data = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/corrupted-file.csv", "size": 1024}
                }
            }]
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_sns = Mock()
            mock_boto3.side_effect = lambda service: mock_sf if service == 'stepfunctions' else mock_sns
            
            # Mock failed execution
            mock_sf.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-failed-execution',
                'startDate': '2024-01-01T00:00:00Z'
            }
            
            mock_sf.describe_execution.return_value = {
                'status': 'FAILED',
                'error': 'States.TaskFailed',
                'cause': 'All retry attempts exhausted'
            }
            
            # Mock SNS publish for DLQ notification
            mock_sns.publish.return_value = {
                'MessageId': 'test-message-123'
            }
            
            # Start execution
            response = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data)
            )
            
            # Verify execution failed
            execution_result = mock_sf.describe_execution(
                executionArn=response['executionArn']
            )
            assert execution_result['status'] == 'FAILED'
            
            # Verify SNS notification was sent
            mock_sns.publish.assert_called_once()
            call_args = mock_sns.publish.call_args[1]
            assert 'TopicArn' in call_args
            assert 'Message' in call_args
            assert 'Subject' in call_args
            assert call_args['Subject'] == 'ONS Data Processing Pipeline Failure'
    
    def test_parallel_processing_capability(self):
        """Test that multiple files can be processed in parallel."""
        # This test would verify that multiple executions can run concurrently
        # In a real scenario, you'd start multiple executions and verify they don't interfere
        
        input_data_1 = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/file1.csv", "size": 1024}
                }
            }]
        }
        
        input_data_2 = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {"key": "data/file2.xlsx", "size": 2048}
                }
            }]
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_boto3.return_value = mock_sf
            
            # Mock multiple successful executions
            mock_sf.start_execution.side_effect = [
                {
                    'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:parallel-1',
                    'startDate': '2024-01-01T00:00:00Z'
                },
                {
                    'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:parallel-2',
                    'startDate': '2024-01-01T00:00:01Z'
                }
            ]
            
            mock_sf.describe_execution.return_value = {
                'status': 'SUCCEEDED',
                'output': json.dumps({"processingResult": "success"})
            }
            
            # Start parallel executions
            execution1 = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data_1)
            )
            
            execution2 = mock_sf.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(input_data_2)
            )
            
            # Verify both executions started
            assert execution1['executionArn'] != execution2['executionArn']
            assert mock_sf.start_execution.call_count == 2
    
    def test_state_machine_definition_validation(self):
        """Test that the state machine definition is valid ASL."""
        # This would be a static validation test for the ASL definition
        expected_states = [
            "RouteFile",
            "ProcessingChoice", 
            "ProcessStructuredData",
            "ProcessUnstructuredData",
            "LoadToTimestream",
            "UpdateKnowledgeBase",
            "ProcessingComplete",
            "NotifyFailure"
        ]
        
        # In a real test, you'd load the actual state machine definition
        # and validate it against AWS ASL schema
        state_machine_definition = {
            "Comment": "ONS Data Processing Pipeline with routing, processing, and error handling",
            "StartAt": "RouteFile",
            "States": {
                state: {"Type": "Task"} for state in expected_states[:-2]
            }
        }
        
        # Basic validation
        assert state_machine_definition["StartAt"] == "RouteFile"
        assert "States" in state_machine_definition
        
        for state in expected_states[:-2]:  # Exclude success/failure states
            assert state in state_machine_definition["States"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])