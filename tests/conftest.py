"""
Pytest configuration and shared fixtures for ONS Data Platform tests
"""

import pytest
import os
import boto3
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from moto import mock_s3, mock_timestream_write, mock_bedrock_agent_runtime, mock_cloudwatch
import tempfile
import json


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_s3_client(aws_credentials):
    """Mock S3 client with test data"""
    with mock_s3():
        s3_client = boto3.client('s3', region_name='us-east-1')
        
        # Create test buckets
        s3_client.create_bucket(Bucket='ons-data-platform-raw')
        s3_client.create_bucket(Bucket='ons-data-platform-processed')
        s3_client.create_bucket(Bucket='ons-data-platform-failed')
        
        yield s3_client


@pytest.fixture
def mock_timestream_client(aws_credentials):
    """Mock Timestream client"""
    with mock_timestream_write():
        client = boto3.client('timestream-write', region_name='us-east-1')
        yield client


@pytest.fixture
def mock_bedrock_client(aws_credentials):
    """Mock Bedrock client"""
    with mock_bedrock_agent_runtime():
        client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
        yield client


@pytest.fixture
def mock_cloudwatch_client(aws_credentials):
    """Mock CloudWatch client"""
    with mock_cloudwatch():
        client = boto3.client('cloudwatch', region_name='us-east-1')
        yield client


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='H'),
        'region': ['sudeste'] * 50 + ['nordeste'] * 50,
        'energy_source': ['hidrica'] * 25 + ['eolica'] * 25 + ['solar'] * 25 + ['termica'] * 25,
        'value': [1000 + i * 10 for i in range(100)],
        'unit': ['MW'] * 100
    })


@pytest.fixture
def sample_generation_data():
    """Sample generation data for testing"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50, freq='H'),
        'region': ['SE', 'NE', 'S', 'N', 'CO'] * 10,
        'energy_source': ['hydro', 'wind', 'solar', 'thermal', 'nuclear'] * 10,
        'measurement_type': ['power'] * 50,
        'value': [1500.0 + i * 50 for i in range(50)],
        'unit': ['MW'] * 50,
        'quality_flag': ['good'] * 50
    })


@pytest.fixture
def sample_consumption_data():
    """Sample consumption data for testing"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=30, freq='D'),
        'region': ['SE', 'NE', 'S'] * 10,
        'consumer_type': ['residential', 'commercial', 'industrial'] * 10,
        'measurement_type': ['consumption'] * 30,
        'value': [800.0 + i * 20 for i in range(30)],
        'unit': ['MWh'] * 30,
        'quality_flag': ['good'] * 30
    })


@pytest.fixture
def sample_pdf_tables():
    """Sample PDF table data for testing"""
    return [
        pd.DataFrame({
            'Data': ['01/01/2024', '02/01/2024', '03/01/2024'],
            'Hidrica (MW)': [1500.0, 1600.0, 1550.0],
            'Eolica (MW)': [800.0, 850.0, 900.0],
            'Solar (MW)': [200.0, 250.0, 300.0]
        }),
        pd.DataFrame({
            'Periodo': ['Jan/2024', 'Fev/2024', 'Mar/2024'],
            'Consumo SE (MWh)': [5000.0, 5200.0, 4800.0],
            'Consumo NE (MWh)': [3000.0, 3100.0, 2900.0]
        })
    ]


@pytest.fixture
def mock_lambda_context():
    """Mock Lambda context object"""
    context = Mock()
    context.function_name = 'test-function'
    context.function_version = '1'
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
    context.memory_limit_in_mb = 128
    context.get_remaining_time_in_millis = Mock(return_value=30000)
    context.aws_request_id = 'test-request-id'
    return context


@pytest.fixture
def s3_event():
    """Sample S3 event for testing"""
    return {
        'Records': [{
            's3': {
                'bucket': {'name': 'ons-data-platform-raw'},
                'object': {
                    'key': 'data/test-file.csv',
                    'size': 1048576
                }
            }
        }]
    }


@pytest.fixture
def api_gateway_event():
    """Sample API Gateway event for testing"""
    return {
        'httpMethod': 'POST',
        'path': '/query',
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'question': 'What is the energy generation data for 2024?'
        })
    }


@pytest.fixture
def step_functions_event():
    """Sample Step Functions event for testing"""
    return {
        'bucket': 'ons-data-platform-processed',
        'key': 'dataset=generation/year=2024/month=01/data.parquet',
        'processingType': 'lambda',
        'outputLocation': 's3://ons-data-platform-processed/dataset=generation/year=2024/month=01/'
    }


@pytest.fixture
def temp_file():
    """Temporary file for testing"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def environment_variables():
    """Set up environment variables for testing"""
    original_env = os.environ.copy()
    
    # Set test environment variables
    test_env = {
        'KNOWLEDGE_BASE_ID': 'test-kb-id',
        'MODEL_ARN': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
        'TIMESTREAM_DATABASE_NAME': 'test_database',
        'GENERATION_TABLE_NAME': 'generation_data',
        'CONSUMPTION_TABLE_NAME': 'consumption_data',
        'TRANSMISSION_TABLE_NAME': 'transmission_data',
        'PROCESSED_BUCKET': 'ons-data-platform-processed',
        'FAILED_BUCKET': 'ons-data-platform-failed',
        'MAX_BATCH_SIZE': '100',
        'MAX_RETRIES': '3'
    }
    
    os.environ.update(test_env)
    
    yield test_env
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def performance_test_data():
    """Large dataset for performance testing"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=10000, freq='H'),
        'region': (['SE', 'NE', 'S', 'N', 'CO'] * 2000),
        'energy_source': (['hydro', 'wind', 'solar', 'thermal'] * 2500),
        'value': [1000.0 + i * 0.1 for i in range(10000)],
        'unit': ['MW'] * 10000
    })


@pytest.fixture
def mock_pdf_tables():
    """Mock PDF table data for testing"""
    return [
        pd.DataFrame({
            'Data': ['01/01/2024', '02/01/2024', '03/01/2024'],
            'Hidrica (MW)': [1500.0, 1600.0, 1550.0],
            'Eolica (MW)': [800.0, 850.0, 900.0],
            'Solar (MW)': [200.0, 250.0, 300.0],
            'Região': ['Sudeste', 'Nordeste', 'Sul']
        }),
        pd.DataFrame({
            'Periodo': ['Jan/2024', 'Fev/2024', 'Mar/2024'],
            'Consumo SE (MWh)': [5000.0, 5200.0, 4800.0],
            'Consumo NE (MWh)': [3000.0, 3100.0, 2900.0],
            'Consumo S (MWh)': [2000.0, 2100.0, 1900.0]
        })
    ]


@pytest.fixture
def mock_timestream_data():
    """Mock Timestream-compatible data"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='H'),
        'region': (['sudeste', 'nordeste', 'sul', 'norte', 'centro_oeste'] * 20),
        'energy_source': (['hidrica', 'eolica', 'solar', 'termica'] * 25),
        'measurement_type': ['power'] * 100,
        'value': [1000.0 + i * 10 for i in range(100)],
        'unit': ['MW'] * 100,
        'quality_flag': ['good'] * 100
    })


@pytest.fixture
def mock_rag_response():
    """Mock RAG response from Bedrock"""
    return {
        'output': {
            'text': 'Based on the available data, Brazil\'s renewable energy capacity has grown significantly, reaching 85% of total installed capacity in 2024.'
        },
        'citations': [{
            'retrievedReferences': [{
                'content': {'text': 'Renewable energy statistics show 85% renewable capacity in Brazil for 2024.'},
                'location': {'s3Location': {'uri': 's3://processed/renewable-stats-2024.parquet'}},
                'metadata': {'score': 0.92}
            }, {
                'content': {'text': 'Hydroelectric power remains the dominant renewable source with 60% share.'},
                'location': {'s3Location': {'uri': 's3://processed/hydro-capacity-2024.parquet'}},
                'metadata': {'score': 0.88}
            }]
        }]
    }


@pytest.fixture
def corrupted_data():
    """Corrupted data for testing error handling"""
    return pd.DataFrame({
        'timestamp': ['2024-01-01', 'invalid-date', None, '2024-01-04'],
        'value': [1000.0, float('inf'), float('-inf'), 'not-a-number'],
        'region': ['sudeste', '', None, 'invalid-region'],
        'energy_source': [None, '', 'invalid-source', 'hidrica'],
        'unit': ['MW', '', None, 'invalid-unit']
    })


@pytest.fixture
def large_dataset():
    """Large dataset for performance and stress testing"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50000, freq='min'),
        'region': (['sudeste', 'nordeste', 'sul', 'norte', 'centro_oeste'] * 10000),
        'energy_source': (['hidrica', 'eolica', 'solar', 'termica', 'nuclear'] * 10000),
        'measurement_type': ['power'] * 50000,
        'value': [1000.0 + i * 0.01 for i in range(50000)],
        'unit': ['MW'] * 50000,
        'quality_flag': ['good'] * 50000
    })


@pytest.fixture
def batch_processing_event():
    """Event for batch processing testing"""
    return {
        'jobName': 'ons-pdf-processor-job',
        'jobQueue': 'ons-data-processing-queue',
        'jobDefinition': 'ons-pdf-processor-batch',
        'parameters': {
            'inputS3Uri': 's3://ons-data-platform-raw/reports/transmission_report.pdf',
            'outputS3Uri': 's3://ons-data-platform-processed/dataset=transmission/year=2024/month=01/processed_data.parquet'
        }
    }


@pytest.fixture
def chaos_scenarios():
    """Various chaos engineering scenarios"""
    return {
        'network_failure': {
            'error_type': 'EndpointConnectionError',
            'message': 'Could not connect to the endpoint URL'
        },
        'service_unavailable': {
            'error_type': 'ServiceUnavailable',
            'message': 'Service temporarily unavailable'
        },
        'throttling': {
            'error_type': 'ThrottlingException',
            'message': 'Rate exceeded'
        },
        'access_denied': {
            'error_type': 'AccessDenied',
            'message': 'Access denied'
        },
        'timeout': {
            'error_type': 'TimeoutError',
            'message': 'Request timed out'
        }
    }


# Utility functions for tests
def create_test_csv_content(data: pd.DataFrame) -> str:
    """Create CSV content from DataFrame for testing"""
    return data.to_csv(index=False)


def create_test_parquet_file(data: pd.DataFrame, path: str):
    """Create a test Parquet file"""
    data.to_parquet(path, compression='snappy', index=False)


def assert_dataframe_structure(df: pd.DataFrame, expected_columns: list, min_rows: int = 1):
    """Assert DataFrame has expected structure"""
    assert isinstance(df, pd.DataFrame)
    assert len(df) >= min_rows
    for col in expected_columns:
        assert col in df.columns
    assert not df.empty


def assert_s3_object_exists(s3_client, bucket: str, key: str):
    """Assert S3 object exists"""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except s3_client.exceptions.NoSuchKey:
        pytest.fail(f"S3 object s3://{bucket}/{key} does not exist")


def assert_lambda_response_format(response: dict, expected_status: int = 200):
    """Assert Lambda response has correct format"""
    assert 'statusCode' in response
    assert response['statusCode'] == expected_status
    assert 'body' in response or 'message' in response
    
    if 'headers' in response:
        assert 'Content-Type' in response['headers']