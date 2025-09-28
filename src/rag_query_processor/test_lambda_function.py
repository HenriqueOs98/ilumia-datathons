"""
Comprehensive tests for RAG Query Processor Lambda function
Tests various query types, edge cases, and error scenarios
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import os
import sys
import time

# Add the lambda function to the path
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import lambda_handler, QueryProcessor


class TestQueryProcessor:
    """Test suite for QueryProcessor class"""
    
    def setup_method(self):
        """Setup test environment"""
        # Set up environment variables for testing
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        os.environ['KNOWLEDGE_BASE_ID'] = 'test-kb-id'
        os.environ['MODEL_ARN'] = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
        
        # Mock AWS clients to avoid actual AWS calls
        with patch('boto3.client') as mock_client:
            mock_bedrock = MagicMock()
            mock_cloudwatch = MagicMock()
            
            def client_side_effect(service_name):
                if service_name == 'bedrock-agent-runtime':
                    return mock_bedrock
                elif service_name == 'cloudwatch':
                    return mock_cloudwatch
                return MagicMock()
            
            mock_client.side_effect = client_side_effect
            self.processor = QueryProcessor()
        
    def test_preprocess_query_valid(self):
        """Test query preprocessing with valid input"""
        query = "What is the energy generation data for 2024?"
        result = self.processor.preprocess_query(query)
        
        assert result['is_valid'] is True
        assert result['processed_query'] == query
        assert result['query_type'] == 'question'
        assert len(result['validation_errors']) == 0
        
    def test_preprocess_query_empty(self):
        """Test query preprocessing with empty input"""
        result = self.processor.preprocess_query("")
        
        assert result['is_valid'] is False
        assert 'Query cannot be empty' in result['validation_errors']
        
    def test_preprocess_query_too_long(self):
        """Test query preprocessing with overly long input"""
        long_query = "x" * 1001  # Exceeds MAX_QUERY_LENGTH
        result = self.processor.preprocess_query(long_query)
        
        assert result['is_valid'] is False
        assert any('too long' in error for error in result['validation_errors'])
        
    def test_preprocess_query_sanitization(self):
        """Test query sanitization removes harmful characters"""
        query = 'What is <script>alert("test")</script> the energy data?'
        result = self.processor.preprocess_query(query)
        
        assert result['is_valid'] is True
        assert '<script>' not in result['processed_query']
        assert '</script>' not in result['processed_query']
        # The current sanitization removes <, >, ", ' but not parentheses
        assert 'scriptalert(test)/script' in result['processed_query']
        
    def test_preprocess_query_whitespace_cleanup(self):
        """Test query whitespace cleanup"""
        query = "  What   is    the   energy   data?  "
        result = self.processor.preprocess_query(query)
        
        assert result['is_valid'] is True
        assert result['processed_query'] == "What is the energy data?"
        
    def test_query_type_detection(self):
        """Test different query type detection"""
        test_cases = [
            ("What is the energy data?", "question"),
            ("How does the system work?", "question"),
            ("Show me the generation data", "request"),
            ("List all available datasets", "request"),
            ("Energy consumption trends", "general")
        ]
        
        for query, expected_type in test_cases:
            result = self.processor.preprocess_query(query)
            assert result['query_type'] == expected_type
            
    def test_retrieve_context_success(self):
        """Test successful context retrieval"""
        # Mock the bedrock runtime client
        mock_response = {
            'retrievalResults': [
                {
                    'content': {'text': 'Sample energy data content'},
                    'location': {'s3Location': {'uri': 's3://bucket/file.parquet'}},
                    'score': 0.85
                },
                {
                    'content': {'text': 'Another relevant content'},
                    'location': {'s3Location': {'uri': 's3://bucket/file2.parquet'}},
                    'score': 0.75
                }
            ]
        }
        
        with patch.object(self.processor.bedrock_runtime, 'retrieve', return_value=mock_response):
            result = self.processor.retrieve_context("test query")
            
            assert result['success'] is True
            assert result['total_results'] == 2
            assert result['filtered_results'] == 2  # Both above MIN_CONFIDENCE_SCORE
            assert result['max_score'] == 0.85
            assert result['retrieval_time_ms'] > 0
            
    def test_retrieve_context_low_confidence(self):
        """Test context retrieval with low confidence results"""
        mock_response = {
            'retrievalResults': [
                {
                    'content': {'text': 'Low confidence content'},
                    'location': {'s3Location': {'uri': 's3://bucket/file.parquet'}},
                    'score': 0.5  # Below MIN_CONFIDENCE_SCORE (0.7)
                }
            ]
        }
        
        with patch.object(self.processor.bedrock_runtime, 'retrieve', return_value=mock_response):
            result = self.processor.retrieve_context("test query")
            
            assert result['success'] is True
            assert result['total_results'] == 1
            assert result['filtered_results'] == 0  # Filtered out due to low score
            
    def test_generate_response_success(self):
        """Test successful RAG response generation"""
        mock_response = {
            'output': {
                'text': 'Based on the available data, the energy generation in 2024 shows...'
            },
            'citations': [
                {
                    'retrievedReferences': [
                        {
                            'content': {'text': 'Energy generation data for 2024'},
                            'location': {'s3Location': {'uri': 's3://bucket/energy-2024.parquet'}},
                            'metadata': {'score': 0.9}
                        }
                    ]
                }
            ]
        }
        
        with patch.object(self.processor.bedrock_runtime, 'retrieve_and_generate', return_value=mock_response):
            result = self.processor.generate_response("What is the energy generation for 2024?")
            
            assert result['success'] is True
            assert 'energy generation in 2024' in result['answer']
            assert len(result['citations']) == 1
            assert result['citation_count'] == 1
            assert result['generation_time_ms'] > 0
            
    def test_format_response(self):
        """Test response formatting"""
        query_result = {
            'original_query': 'What is the energy data?',
            'query_type': 'question'
        }
        
        generation_result = {
            'success': True,
            'answer': 'The energy data shows...',
            'citations': [
                {
                    'content': 'Sample content for citation',
                    'location': {'s3Location': {'uri': 's3://bucket/file.parquet'}},
                    'score': 0.85
                }
            ],
            'generation_time_ms': 1500,
            'citation_count': 1
        }
        
        query_id = 'test-query-id'
        
        response = self.processor.format_response(query_result, generation_result, query_id)
        
        assert response['query_id'] == query_id
        assert response['question'] == 'What is the energy data?'
        assert response['answer'] == 'The energy data shows...'
        assert response['confidence_score'] > 0
        assert len(response['sources']) == 1
        assert response['sources'][0]['relevance_score'] == 0.85
        assert response['metadata']['query_type'] == 'question'
        assert response['metadata']['citation_count'] == 1
        
    def test_send_metrics_success(self):
        """Test successful metrics sending"""
        query_result = {'query_type': 'question'}
        generation_result = {
            'success': True,
            'generation_time_ms': 1200,
            'citation_count': 2
        }
        
        with patch.object(self.processor.cloudwatch, 'put_metric_data') as mock_put_metric:
            # This should not raise an exception
            self.processor.send_metrics(query_result, generation_result)
            mock_put_metric.assert_called_once()
        
    def test_send_metrics_failure(self):
        """Test metrics sending for failed queries"""
        query_result = {'query_type': 'question'}
        generation_result = {
            'success': False,
            'error': 'Test error'
        }
        
        with patch.object(self.processor.cloudwatch, 'put_metric_data') as mock_put_metric:
            # This should not raise an exception
            self.processor.send_metrics(query_result, generation_result)
            mock_put_metric.assert_called_once()


class TestLambdaHandler:
    """Test suite for Lambda handler function"""
    
    def setup_method(self):
        """Setup test environment"""
        # Store original values
        self.original_kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        self.original_model_arn = os.environ.get('MODEL_ARN')
        
        # Set test values
        os.environ['KNOWLEDGE_BASE_ID'] = 'test-kb-id'
        os.environ['MODEL_ARN'] = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
        
    def teardown_method(self):
        """Cleanup test environment"""
        # Restore original values
        if self.original_kb_id is not None:
            os.environ['KNOWLEDGE_BASE_ID'] = self.original_kb_id
        elif 'KNOWLEDGE_BASE_ID' in os.environ:
            del os.environ['KNOWLEDGE_BASE_ID']
            
        if self.original_model_arn is not None:
            os.environ['MODEL_ARN'] = self.original_model_arn
        elif 'MODEL_ARN' in os.environ:
            del os.environ['MODEL_ARN']
        
    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        # Ensure environment variable is set
        os.environ['KNOWLEDGE_BASE_ID'] = 'test-kb-id'
        
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['service'] == 'ons-rag-query-processor'
        assert body['version'] == '1.0.0'
        assert 'timestamp' in body
        assert body['knowledge_base_configured'] is True
        
    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'path': '/query'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        assert response['body'] == ''
        headers = response['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'POST,GET,OPTIONS' in headers['Access-Control-Allow-Methods']
        
    def test_unknown_endpoint(self):
        """Test request to unknown endpoint"""
        event = {
            'httpMethod': 'GET',
            'path': '/unknown'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'Endpoint not found' in body['error']
        assert body['path'] == '/unknown'
        assert body['method'] == 'GET'
        
    def test_lambda_handler_api_gateway_query_event(self):
        """Test Lambda handler with API Gateway query event"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'What is the energy generation data?'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            # Mock successful processing
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'What is the energy generation data?',
                'query_type': 'question'
            }
            
            mock_processor.generate_response.return_value = {
                'success': True,
                'answer': 'The energy generation data shows...',
                'citations': [],
                'generation_time_ms': 1000,
                'citation_count': 0
            }
            
            mock_processor.format_response.return_value = {
                'query_id': 'test-id',
                'question': 'What is the energy generation data?',
                'answer': 'The energy generation data shows...',
                'confidence_score': 0.8,
                'sources': [],
                'processing_time_ms': 1000
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'query_id' in body
            assert body['answer'] == 'The energy generation data shows...'
            
    def test_lambda_handler_direct_invocation(self):
        """Test Lambda handler with direct invocation"""
        event = {
            'query': 'What is the energy consumption trend?'
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            # Mock successful processing
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'What is the energy consumption trend?',
                'query_type': 'question'
            }
            
            mock_processor.generate_response.return_value = {
                'success': True,
                'answer': 'The energy consumption trend shows...',
                'citations': [],
                'generation_time_ms': 800,
                'citation_count': 0
            }
            
            mock_processor.format_response.return_value = {
                'query_id': 'test-id',
                'question': 'What is the energy consumption trend?',
                'answer': 'The energy consumption trend shows...',
                'confidence_score': 0.75,
                'sources': [],
                'processing_time_ms': 800
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['answer'] == 'The energy consumption trend shows...'
            
    def test_lambda_handler_missing_query(self):
        """Test Lambda handler with missing query"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Question parameter is required' in body['error']
        
    def test_lambda_handler_invalid_query(self):
        """Test Lambda handler with invalid query"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': ''})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Question parameter is required' in body['error']
            
    def test_lambda_handler_missing_knowledge_base_id(self):
        """Test Lambda handler without Knowledge Base ID configured"""
        # Temporarily remove the environment variable
        original_kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        if 'KNOWLEDGE_BASE_ID' in os.environ:
            del os.environ['KNOWLEDGE_BASE_ID']
            
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'test query'})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'Knowledge Base ID not configured' in body['error']
        
        # Restore the environment variable
        if original_kb_id is not None:
            os.environ['KNOWLEDGE_BASE_ID'] = original_kb_id
        
    def test_lambda_handler_generation_failure(self):
        """Test Lambda handler when RAG generation fails"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'What is the energy data?'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'What is the energy data?',
                'query_type': 'question'
            }
            
            mock_processor.generate_response.return_value = {
                'success': False,
                'error': 'Knowledge Base not available'
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Failed to generate response' in body['error']
            
    def test_lambda_handler_cors_headers(self):
        """Test that CORS headers are properly set"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'test query'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'test query',
                'query_type': 'general'
            }
            
            mock_processor.generate_response.return_value = {
                'success': True,
                'answer': 'Test answer',
                'citations': [],
                'generation_time_ms': 500,
                'citation_count': 0
            }
            
            mock_processor.format_response.return_value = {
                'query_id': 'test-id',
                'question': 'test query',
                'answer': 'Test answer',
                'confidence_score': 0.8,
                'sources': [],
                'processing_time_ms': 500,
                'timestamp': int(time.time()),
                'metadata': {
                    'query_type': 'general',
                    'citation_count': 0,
                    'model_used': 'claude-3-sonnet'
                }
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            headers = response['headers']
            assert headers['Access-Control-Allow-Origin'] == '*'
            assert 'Content-Type' in headers
            assert 'Access-Control-Allow-Headers' in headers
            assert 'Access-Control-Allow-Methods' in headers
            
    def test_api_gateway_question_field(self):
        """Test API Gateway event with 'question' field"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'What is renewable energy data?'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'What is renewable energy data?',
                'query_type': 'question'
            }
            
            mock_processor.generate_response.return_value = {
                'success': True,
                'answer': 'Renewable energy data shows...',
                'citations': [],
                'generation_time_ms': 900,
                'citation_count': 0
            }
            
            mock_processor.format_response.return_value = {
                'query_id': 'test-id',
                'question': 'What is renewable energy data?',
                'answer': 'Renewable energy data shows...',
                'confidence_score': 0.8,
                'sources': [],
                'processing_time_ms': 900
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['answer'] == 'Renewable energy data shows...'
            
    def test_api_gateway_legacy_query_field(self):
        """Test API Gateway event with legacy 'query' field for backward compatibility"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'query': 'Show transmission data'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'Show transmission data',
                'query_type': 'request'
            }
            
            mock_processor.generate_response.return_value = {
                'success': True,
                'answer': 'Transmission data includes...',
                'citations': [],
                'generation_time_ms': 750,
                'citation_count': 0
            }
            
            mock_processor.format_response.return_value = {
                'query_id': 'test-id',
                'question': 'Show transmission data',
                'answer': 'Transmission data includes...',
                'confidence_score': 0.85,
                'sources': [],
                'processing_time_ms': 750
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['answer'] == 'Transmission data includes...'
            
    def test_health_check_without_knowledge_base(self):
        """Test health check when Knowledge Base is not configured"""
        # Temporarily remove the environment variable
        original_kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        if 'KNOWLEDGE_BASE_ID' in os.environ:
            del os.environ['KNOWLEDGE_BASE_ID']
            
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['status'] == 'healthy'
        assert body['knowledge_base_configured'] is False
        
        # Restore the environment variable
        if original_kb_id is not None:
            os.environ['KNOWLEDGE_BASE_ID'] = original_kb_id
        
    def test_api_gateway_error_handling(self):
        """Test API Gateway error handling with proper HTTP status codes"""
        # Test 400 error
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': ''})
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Question parameter is required' in body['error']
            
        # Test 500 error
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'test query'})
        }
        
        with patch('lambda_function.QueryProcessor') as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor_class.return_value = mock_processor
            
            mock_processor.preprocess_query.return_value = {
                'is_valid': True,
                'processed_query': 'test query',
                'query_type': 'general'
            }
            
            mock_processor.generate_response.return_value = {
                'success': False,
                'error': 'Service unavailable'
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Failed to generate response' in body['error']


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def setup_method(self):
        """Setup test environment"""
        os.environ['KNOWLEDGE_BASE_ID'] = 'test-kb-id'
        self.processor = QueryProcessor()
        
    def test_special_characters_in_query(self):
        """Test queries with special characters"""
        queries = [
            "What's the energy data for São Paulo?",
            "Show me data with 100% renewable energy",
            "Energy costs in R$ (Brazilian Real)",
            "Data from 2020-2024 period"
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            assert result['is_valid'] is True
            
    def test_multilingual_queries(self):
        """Test queries in different languages"""
        queries = [
            "¿Cuál es la generación de energía?",  # Spanish
            "Qual é a geração de energia?",        # Portuguese
            "Quelle est la génération d'énergie?", # French
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            assert result['is_valid'] is True
            
    def test_very_long_valid_query(self):
        """Test with maximum allowed query length"""
        # Create a query that's exactly at the limit
        base_query = "What is the energy generation data for "
        remaining_chars = 1000 - len(base_query) - 1  # -1 for the question mark
        long_location = "x" * remaining_chars
        query = base_query + long_location + "?"
        
        result = self.processor.preprocess_query(query)
        assert result['is_valid'] is True
        assert len(result['processed_query']) == 1000
        
    def test_numeric_queries(self):
        """Test queries with numeric data"""
        queries = [
            "Show data for 2024",
            "What is the capacity of 1000 MW plants?",
            "Energy consumption of 50.5 GWh",
            "Plants with efficiency > 95%"
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            assert result['is_valid'] is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])