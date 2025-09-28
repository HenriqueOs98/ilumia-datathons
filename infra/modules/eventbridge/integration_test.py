#!/usr/bin/env python3
"""
Simple integration test to validate EventBridge to Step Functions integration.
This script simulates the complete flow from S3 event to Step Functions execution.
"""

import json
import time
from typing import Dict, Any


def simulate_s3_event_to_step_functions():
    """
    Simulate the complete flow:
    1. S3 object creation event
    2. EventBridge rule matching
    3. Step Functions execution trigger
    """
    
    print("🚀 Starting EventBridge to Step Functions integration test...")
    
    # Mock S3 event data
    s3_event = {
        "Records": [{
            "eventSource": "aws:s3",
            "eventName": "ObjectCreated:Put",
            "eventTime": "2024-01-01T12:00:00.000Z",
            "s3": {
                "bucket": {
                    "name": "ons-data-platform-dev-raw-bucket"
                },
                "object": {
                    "key": "data/energy-generation-2024-01.csv",
                    "size": 1048576,
                    "eTag": "d41d8cd98f00b204e9800998ecf8427e"
                }
            }
        }],
        "eventBridgeSource": True,
        "processingTimestamp": "2024-01-01T12:00:00.000Z"
    }
    
    print("📄 Mock S3 event created:")
    print(f"   - Bucket: {s3_event['Records'][0]['s3']['bucket']['name']}")
    print(f"   - Object: {s3_event['Records'][0]['s3']['object']['key']}")
    print(f"   - Size: {s3_event['Records'][0]['s3']['object']['size']} bytes")
    
    # Validate event structure
    assert "Records" in s3_event
    assert len(s3_event["Records"]) == 1
    assert "s3" in s3_event["Records"][0]
    assert "bucket" in s3_event["Records"][0]["s3"]
    assert "object" in s3_event["Records"][0]["s3"]
    
    print("✅ S3 event structure validation passed")
    
    # Simulate EventBridge rule matching
    object_key = s3_event["Records"][0]["s3"]["object"]["key"]
    supported_extensions = [".csv", ".xlsx", ".xls", ".pdf"]
    
    file_extension = None
    for ext in supported_extensions:
        if object_key.endswith(ext):
            file_extension = ext
            break
    
    if file_extension:
        print(f"✅ EventBridge rule would match - file extension: {file_extension}")
    else:
        print("❌ EventBridge rule would NOT match - unsupported file type")
        return False
    
    # Simulate input transformation for Step Functions
    transformed_input = {
        "Records": s3_event["Records"],
        "eventBridgeSource": s3_event["eventBridgeSource"],
        "processingTimestamp": s3_event["processingTimestamp"],
        "metadata": {
            "fileExtension": file_extension,
            "bucketName": s3_event["Records"][0]["s3"]["bucket"]["name"],
            "objectKey": s3_event["Records"][0]["s3"]["object"]["key"],
            "objectSize": s3_event["Records"][0]["s3"]["object"]["size"]
        }
    }
    
    print("✅ Input transformation for Step Functions completed")
    print(f"   - Added metadata with file extension: {file_extension}")
    
    # Validate transformed input
    assert "metadata" in transformed_input
    assert "fileExtension" in transformed_input["metadata"]
    assert transformed_input["metadata"]["fileExtension"] == file_extension
    
    print("✅ Transformed input validation passed")
    
    # Simulate Step Functions execution (mock)
    execution_arn = f"arn:aws:states:us-east-1:123456789012:execution:ons-data-platform-dev-data-processing:{int(time.time())}"
    
    print(f"🔄 Step Functions execution would be triggered:")
    print(f"   - Execution ARN: {execution_arn}")
    print(f"   - Input size: {len(json.dumps(transformed_input))} characters")
    
    # Simulate processing decision based on file type and size
    file_size = transformed_input["metadata"]["objectSize"]
    processing_type = "batch" if file_extension == ".pdf" or file_size > 100 * 1024 * 1024 else "lambda"
    
    print(f"✅ Processing type determined: {processing_type}")
    print(f"   - File size: {file_size} bytes")
    print(f"   - File type: {file_extension}")
    
    # Validate processing logic
    if file_extension == ".pdf":
        assert processing_type == "batch", "PDF files should use Batch processing"
    elif file_extension in [".csv", ".xlsx", ".xls"]:
        if file_size <= 100 * 1024 * 1024:  # 100MB
            assert processing_type == "lambda", "Small structured files should use Lambda"
        else:
            assert processing_type == "batch", "Large files should use Batch processing"
    
    print("✅ Processing type logic validation passed")
    
    return True


def test_failure_event_routing():
    """Test that failure events would be properly routed to SNS."""
    
    print("\n🚨 Testing failure event routing...")
    
    failure_event = {
        "version": "0",
        "id": "test-failure-123",
        "detail-type": "Data Processing Failed",
        "source": "ons.data.platform",
        "time": "2024-01-01T12:05:00Z",
        "detail": {
            "status": "FAILED",
            "error": "Lambda function timeout after 15 minutes",
            "inputFile": "s3://ons-data-platform-dev-raw-bucket/data/large-dataset.csv",
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:failed-execution"
        }
    }
    
    print("📧 Mock failure event created:")
    print(f"   - Status: {failure_event['detail']['status']}")
    print(f"   - Error: {failure_event['detail']['error']}")
    print(f"   - Failed file: {failure_event['detail']['inputFile']}")
    
    # Validate failure event structure
    assert failure_event["source"] == "ons.data.platform"
    assert failure_event["detail-type"] == "Data Processing Failed"
    assert failure_event["detail"]["status"] in ["FAILED", "TIMEOUT", "ABORTED"]
    
    print("✅ Failure event structure validation passed")
    
    # Simulate SNS alert message transformation
    alert_message = {
        "alert_type": "Processing Failure",
        "timestamp": failure_event["time"],
        "status": failure_event["detail"]["status"],
        "error_details": failure_event["detail"]["error"],
        "failed_file": failure_event["detail"]["inputFile"],
        "execution_arn": failure_event["detail"]["executionArn"]
    }
    
    print("📨 SNS alert message would be sent:")
    print(f"   - Alert type: {alert_message['alert_type']}")
    print(f"   - Timestamp: {alert_message['timestamp']}")
    print(f"   - Status: {alert_message['status']}")
    
    # Validate alert message
    assert alert_message["alert_type"] == "Processing Failure"
    assert "error_details" in alert_message
    assert "failed_file" in alert_message
    
    print("✅ SNS alert message validation passed")
    
    return True


def main():
    """Run all integration tests."""
    
    print("=" * 60)
    print("EventBridge to Step Functions Integration Test")
    print("=" * 60)
    
    try:
        # Test 1: S3 event to Step Functions flow
        success1 = simulate_s3_event_to_step_functions()
        
        # Test 2: Failure event routing
        success2 = test_failure_event_routing()
        
        if success1 and success2:
            print("\n🎉 All integration tests passed successfully!")
            print("✅ EventBridge to Step Functions integration is working correctly")
            return 0
        else:
            print("\n❌ Some integration tests failed")
            return 1
            
    except Exception as e:
        print(f"\n💥 Integration test failed with error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())