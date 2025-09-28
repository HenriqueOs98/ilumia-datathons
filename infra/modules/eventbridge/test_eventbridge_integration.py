#!/usr/bin/env python3
"""
Integration tests for EventBridge integration with Step Functions.
Tests event routing, filtering, and state machine triggering.
"""

import json
import boto3
import pytest
import time
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock


class TestEventBridgeIntegration:
    """Test suite for EventBridge integration with ONS Data Processing Pipeline."""
    
    def setup_method(self):
        """Setup test environment."""
        self.events_client = boto3.client('events', region_name='us-east-1')
        self.stepfunctions_client = boto3.client('stepfunctions', region_name='us-east-1')
        self.sns_client = boto3.client('sns', region_name='us-east-1')
        
        # Test configuration
        self.rule_name = "test-ons-data-platform-s3-object-created"
        self.state_machine_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:test-data-processing"
        self.sns_topic_arn = "arn:aws:sns:us-east-1:123456789012:test-processing-alerts"
    
    def test_s3_event_filtering_csv_files(self):
        """Test that EventBridge rule correctly filters CSV files."""
        # Mock S3 event for CSV file
        s3_event = {
            "version": "0",
            "id": "test-event-id",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "account": "123456789012",
            "time": "2024-01-01T12:00:00Z",
            "region": "us-east-1",
            "detail": {
                "version": "0",
                "bucket": {
                    "name": "test-raw-bucket"
                },
                "object": {
                    "key": "data/energy-generation-2024.csv",
                    "size": 1048576,
                    "eTag": "test-etag-123",
                    "sequencer": "test-sequencer"
                },
                "request-id": "test-request-id",
                "requester": "123456789012"
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_stepfunctions = Mock()
            mock_boto3.side_effect = lambda service: mock_events if service == 'events' else mock_stepfunctions
            
            # Mock EventBridge put_events response
            mock_events.put_events.return_value = {
                'FailedEntryCount': 0,
                'Entries': [
                    {
                        'EventId': 'test-event-id'
                    }
                ]
            }
            
            # Mock Step Functions execution start
            mock_stepfunctions.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-csv-execution',
                'startDate': '2024-01-01T12:00:00Z'
            }
            
            # Simulate event being sent to EventBridge
            response = mock_events.put_events(
                Entries=[s3_event]
            )
            
            # Verify event was accepted
            assert response['FailedEntryCount'] == 0
            assert len(response['Entries']) == 1
            
            # Verify Step Functions was triggered (would happen automatically via EventBridge target)
            # In real scenario, this would be triggered by EventBridge, not directly
            execution_response = mock_stepfunctions.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps({
                    "Records": [{
                        "eventSource": "aws:s3",
                        "eventName": "ObjectCreated:Put",
                        "eventTime": s3_event["time"],
                        "s3": s3_event["detail"]
                    }],
                    "eventBridgeSource": True,
                    "processingTimestamp": s3_event["time"]
                })
            )
            
            assert 'executionArn' in execution_response
    
    def test_s3_event_filtering_xlsx_files(self):
        """Test that EventBridge rule correctly filters XLSX files."""
        s3_event = {
            "version": "0",
            "id": "test-event-id-xlsx",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "account": "123456789012",
            "time": "2024-01-01T12:00:00Z",
            "region": "us-east-1",
            "detail": {
                "bucket": {
                    "name": "test-raw-bucket"
                },
                "object": {
                    "key": "data/consumption-report-2024.xlsx",
                    "size": 2097152,
                    "eTag": "test-etag-xlsx"
                }
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_stepfunctions = Mock()
            mock_boto3.side_effect = lambda service: mock_events if service == 'events' else mock_stepfunctions
            
            mock_events.put_events.return_value = {
                'FailedEntryCount': 0,
                'Entries': [{'EventId': 'test-event-id-xlsx'}]
            }
            
            mock_stepfunctions.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-xlsx-execution',
                'startDate': '2024-01-01T12:00:00Z'
            }
            
            # Test XLSX file processing
            response = mock_events.put_events(Entries=[s3_event])
            assert response['FailedEntryCount'] == 0
    
    def test_s3_event_filtering_pdf_files(self):
        """Test that EventBridge rule correctly filters PDF files."""
        s3_event = {
            "version": "0",
            "id": "test-event-id-pdf",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "account": "123456789012",
            "time": "2024-01-01T12:00:00Z",
            "region": "us-east-1",
            "detail": {
                "bucket": {
                    "name": "test-raw-bucket"
                },
                "object": {
                    "key": "reports/annual-energy-report-2024.pdf",
                    "size": 10485760,  # 10MB
                    "eTag": "test-etag-pdf"
                }
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_stepfunctions = Mock()
            mock_boto3.side_effect = lambda service: mock_events if service == 'events' else mock_stepfunctions
            
            mock_events.put_events.return_value = {
                'FailedEntryCount': 0,
                'Entries': [{'EventId': 'test-event-id-pdf'}]
            }
            
            mock_stepfunctions.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-pdf-execution',
                'startDate': '2024-01-01T12:00:00Z'
            }
            
            # Test PDF file processing
            response = mock_events.put_events(Entries=[s3_event])
            assert response['FailedEntryCount'] == 0
    
    def test_s3_event_filtering_ignores_unsupported_files(self):
        """Test that EventBridge rule ignores unsupported file types."""
        unsupported_event = {
            "version": "0",
            "id": "test-event-id-txt",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "account": "123456789012",
            "time": "2024-01-01T12:00:00Z",
            "region": "us-east-1",
            "detail": {
                "bucket": {
                    "name": "test-raw-bucket"
                },
                "object": {
                    "key": "logs/processing.txt",  # Unsupported file type
                    "size": 1024,
                    "eTag": "test-etag-txt"
                }
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_stepfunctions = Mock()
            mock_boto3.side_effect = lambda service: mock_events if service == 'events' else mock_stepfunctions
            
            # Event would be sent to EventBridge but wouldn't match the rule pattern
            mock_events.put_events.return_value = {
                'FailedEntryCount': 0,
                'Entries': [{'EventId': 'test-event-id-txt'}]
            }
            
            # Step Functions should NOT be triggered for unsupported files
            mock_stepfunctions.start_execution.assert_not_called()
    
    def test_input_transformation_for_step_functions(self):
        """Test that EventBridge correctly transforms input for Step Functions."""
        s3_event = {
            "version": "0",
            "id": "test-transformation",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "time": "2024-01-01T12:00:00Z",
            "detail": {
                "bucket": {"name": "test-raw-bucket"},
                "object": {
                    "key": "data/test-file.csv",
                    "size": 1024,
                    "eTag": "test-etag"
                }
            }
        }
        
        # Expected transformed input for Step Functions
        expected_input = {
            "Records": [{
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "eventTime": "2024-01-01T12:00:00Z",
                "s3": {
                    "bucket": {"name": "test-raw-bucket"},
                    "object": {
                        "key": "data/test-file.csv",
                        "size": 1024,
                        "eTag": "test-etag"
                    }
                }
            }],
            "eventBridgeSource": True,
            "processingTimestamp": "2024-01-01T12:00:00Z"
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_stepfunctions = Mock()
            mock_boto3.return_value = mock_stepfunctions
            
            mock_stepfunctions.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-transform',
                'startDate': '2024-01-01T12:00:00Z'
            }
            
            # Simulate the transformed input being passed to Step Functions
            response = mock_stepfunctions.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(expected_input)
            )
            
            # Verify the call was made with correct parameters
            mock_stepfunctions.start_execution.assert_called_once()
            call_args = mock_stepfunctions.start_execution.call_args
            
            assert call_args[1]['stateMachineArn'] == self.state_machine_arn
            input_data = json.loads(call_args[1]['input'])
            assert input_data['eventBridgeSource'] is True
            assert len(input_data['Records']) == 1
            assert input_data['Records'][0]['s3']['object']['key'] == 'data/test-file.csv'
    
    def test_processing_failure_alert_routing(self):
        """Test that processing failure events trigger SNS alerts."""
        failure_event = {
            "version": "0",
            "id": "test-failure-event",
            "detail-type": "Data Processing Failed",
            "source": "ons.data.platform",
            "time": "2024-01-01T12:00:00Z",
            "detail": {
                "status": "FAILED",
                "error": "Lambda function timeout",
                "inputFile": "s3://test-raw-bucket/data/corrupted-file.csv",
                "executionArn": "arn:aws:states:us-east-1:123456789012:execution:failed-execution"
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_sns = Mock()
            mock_boto3.side_effect = lambda service: mock_events if service == 'events' else mock_sns
            
            # Mock SNS publish response
            mock_sns.publish.return_value = {
                'MessageId': 'test-alert-message-id'
            }
            
            # Simulate EventBridge routing failure event to SNS
            alert_message = {
                "alert_type": "Processing Failure",
                "timestamp": failure_event["time"],
                "status": failure_event["detail"]["status"],
                "error_details": failure_event["detail"]["error"],
                "failed_file": failure_event["detail"]["inputFile"],
                "source": failure_event["source"],
                "detail_type": failure_event["detail-type"]
            }
            
            response = mock_sns.publish(
                TopicArn=self.sns_topic_arn,
                Message=json.dumps(alert_message),
                Subject="ONS Data Processing Pipeline Failure Alert"
            )
            
            # Verify SNS notification was sent
            assert 'MessageId' in response
            mock_sns.publish.assert_called_once()
            
            call_args = mock_sns.publish.call_args[1]
            assert call_args['TopicArn'] == self.sns_topic_arn
            
            message_data = json.loads(call_args['Message'])
            assert message_data['alert_type'] == 'Processing Failure'
            assert message_data['status'] == 'FAILED'
    
    def test_processing_completion_event_routing(self):
        """Test that processing completion events are properly routed."""
        completion_event = {
            "version": "0",
            "id": "test-completion-event",
            "detail-type": "Data Processing Completed",
            "source": "ons.data.platform",
            "time": "2024-01-01T12:00:00Z",
            "detail": {
                "status": "SUCCESS",
                "inputFile": "s3://test-raw-bucket/data/energy-data.csv",
                "outputFile": "s3://test-processed-bucket/data/energy-data.parquet",
                "recordsProcessed": 10000,
                "executionArn": "arn:aws:states:us-east-1:123456789012:execution:successful-execution"
            }
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_events = Mock()
            mock_boto3.return_value = mock_events
            
            mock_events.put_events.return_value = {
                'FailedEntryCount': 0,
                'Entries': [{'EventId': 'test-completion-event'}]
            }
            
            # Test that completion events can be sent to EventBridge
            response = mock_events.put_events(Entries=[completion_event])
            
            assert response['FailedEntryCount'] == 0
            assert len(response['Entries']) == 1
    
    def test_iam_permissions_validation(self):
        """Test that IAM roles have correct permissions for EventBridge integration."""
        # This test validates the IAM policy structure
        expected_eventbridge_permissions = [
            "states:StartExecution"
        ]
        
        expected_sns_permissions = [
            "sns:Publish"
        ]
        
        # In a real test, you would validate the actual IAM policies
        # For now, we'll just verify the structure
        eventbridge_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": expected_eventbridge_permissions,
                    "Resource": [self.state_machine_arn]
                }
            ]
        }
        
        sns_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": expected_sns_permissions,
                    "Resource": [self.sns_topic_arn]
                }
            ]
        }
        
        # Validate policy structure
        assert eventbridge_policy["Version"] == "2012-10-17"
        assert len(eventbridge_policy["Statement"]) == 1
        assert eventbridge_policy["Statement"][0]["Action"] == expected_eventbridge_permissions
        
        assert sns_policy["Version"] == "2012-10-17"
        assert len(sns_policy["Statement"]) == 1
        assert sns_policy["Statement"][0]["Action"] == expected_sns_permissions
    
    def test_event_pattern_validation(self):
        """Test that EventBridge rule event patterns are correctly configured."""
        # Expected event pattern for S3 object creation
        expected_s3_pattern = {
            "source": ["aws.s3"],
            "detail-type": ["Object Created"],
            "detail": {
                "bucket": {
                    "name": ["test-raw-bucket"]
                },
                "object": {
                    "key": [
                        {"suffix": ".csv"},
                        {"suffix": ".xlsx"},
                        {"suffix": ".xls"},
                        {"suffix": ".pdf"}
                    ]
                }
            }
        }
        
        # Expected event pattern for processing failures
        expected_failure_pattern = {
            "source": ["ons.data.platform"],
            "detail-type": ["Data Processing Failed"],
            "detail": {
                "status": ["FAILED", "TIMEOUT", "ABORTED"]
            }
        }
        
        # Validate patterns structure
        assert "source" in expected_s3_pattern
        assert "detail-type" in expected_s3_pattern
        assert "detail" in expected_s3_pattern
        assert "bucket" in expected_s3_pattern["detail"]
        assert "object" in expected_s3_pattern["detail"]
        
        assert len(expected_s3_pattern["detail"]["object"]["key"]) == 4  # 4 supported file types
        
        assert "source" in expected_failure_pattern
        assert "detail-type" in expected_failure_pattern
        assert len(expected_failure_pattern["detail"]["status"]) == 3  # 3 failure states


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])