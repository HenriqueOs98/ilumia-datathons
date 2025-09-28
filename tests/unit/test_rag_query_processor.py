"""
Comprehensive unit tests for RAG Query Processor Lambda function
Tests query processing, RAG generation, error handling, and performance
"""

import pytest
import json
import time
import uuid
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
import sys
import os

# Add source path
sys.path.insert(0, 'src/rag_query_processor')

from lambda_function import (
    lambda_handler,
    QueryProcessor,
    handle_health_check,
    handle_query_request,
    get_env_vars
)


class TestQueryProcessor:
    """Test QueryProcessor class functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.mock_bedrock = MagicMock()
        self.mock_cloudwatch = MagicMock()
        
        with patch('boto3.client') as mock_client:
            def client_side_effect(service_name):
                if service_name == 'bedrock-agent-runtime':
                    return self.mock_bedrock
                elif service_name == 'cloudwatch':
                    return self.mock_cloudwatch
                return MagicMock()
            
            mock_client.side_effect = client_side_effect
            self.processor = QueryProcessor()
    
    def test_preprocess_query_valid_question(self):
        """Test preprocessing valid question queries"""
        queries = [
            "What is the energy generation data for 2024?",
            "How does renewable energy contribute to the grid?",
            "When was the peak consumption recorded?",
            "Where are the main transmission lines located?",
            "Why did energy consumption increase in Q3?",
            "Which regions have the highest solar capacity?"
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            
            assert result['is_valid'] is True
            assert result['processed_query'] == query
            assert result['query_type'] == 'question'
            assert len(result['validation_errors']) == 0
            assert result['original_query'] == query
    
    def test_preprocess_query_valid_request(self):
        """Test preprocessing valid request queries"""
        queries = [
            "Show me the generation data",
            "List all renewable energy sources",
            "Find the consumption trends",
            "Get the transmission capacity data"
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            
            assert result['is_valid'] is True
            assert result['query_type'] == 'request'
    
    def test_preprocess_query_general_type(self):
        """Test preprocessing general type queries"""
        queries = [
            "Energy consumption trends",
            "Solar power statistics",
            "Grid stability metrics"
        ]
        
        for query in queries:
            result = self.processor.preprocess_query(query)
            
            assert result['is_valid'] is True
            assert result['query_type'] == 'general'
    
    def test_preprocess_query_empty_input(self):
        """Test preprocessing empty or whitespace-only input"""
        invalid_queries = ["", "   ", "\t\n", None]
        
        for query in invalid_queries:
            if query is None:
                query = ""
            result = self.processor.preprocess_query(query)
            
            assert result['is_valid'] is False
            assert 'Query cannot be empty' in result['validation_errors']
    
    def test_preprocess_query_too_long(self):
        """Test preprocessing overly long queries"""
        long_query = "x" * 1001  # Exceeds default MAX_QUERY_LENGTH
        result = self.processor.preprocess_query(long_query)
        
        assert result['is_valid'] is False
        assert any('too long' in error for error in result['validation_errors'])
    
    def test_preprocess_query_sanitization(self):
        """Test query sanitization removes harmful characters"""
        malicious_queries = [
            'What is <script>alert("xss")</script> the data?',
            'Show me "dangerous" content',
            "What's the 'quoted' information?",
            'Data with <tags> and "quotes"'
        ]
        
        for query in malicious_queries:
            result = self.processor.preprocess_query(query)
            
            assert result['is_valid'] is True
            # Harmful characters should be removed
            assert '<script>' not in result['processed_query']
            assert '"' not in result['processed_query']
            assert "'" not in result['processed_query']
    
    def test_preprocess_query_whitespace_normalization(self):
        """Test whitespace normalization"""
        test_cases = [
            ("  What   is    the   data?  ", "What is the data?"),
            ("\t\nShow\n\tme\t\tdata\n", "Show me data"),
            ("Multiple     spaces     here", "Multiple spaces here")
        ]
        
        for input_query, expected_output in test_cases:
            result = self.processor.preprocess_query(input_query)
            
            assert result['is_valid'] is True
            assert result['processed_query'] == expected_output
    
    def test_retrieve_context_success(self):
        """Test successful context retrieval"""
        mock_response = {
            'retrievalResults': [
                {
                    'content': {'text': 'Energy generation data for 2024 shows...'},
                    'location': {'s3Location': {'uri': 's3://bucket/gen-2024.parquet'}},
                    'score': 0.95
                },
                {
                    'content': {'text': 'Renewable energy capacity increased...'},
                    'location': {'s3Location': {'uri': 's3://bucket/renewable.parquet'}},
                    'score': 0.82
                },
                {
                    'content': {'text': 'Low relevance content'},
                    'location': {'s3Location': {'uri': 's3://bucket/other.parquet'}},
                    'score': 0.45  # Below threshold
                }
            ]
        }
        
        self.mock_bedrock.retrieve.return_value = mock_response
        
        result = self.processor.retrieve_context("energy generation 2024")
        
        assert result['success'] is True
        assert result['total_results'] == 3
        assert result['filtered_results'] == 2  # Only 2 above threshold
        assert result['max_score'] == 0.95
        assert result['retrieval_time_ms'] > 0
        
        # Verify API call
        self.mock_bedrock.retrieve.assert_called_once()
        call_args = self.mock_bedrock.retrieve.call_args[1]
        assert call_args['retrievalQuery']['text'] == "energy generation 2024"
    
    def test_retrieve_context_no_results(self):
        """Test context retrieval with no results"""
        mock_response = {'retrievalResults': []}
        self.mock_bedrock.retrieve.return_value = mock_response
        
        result = self.processor.retrieve_context("nonexistent query")
        
        assert result['success'] is True
        assert result['total_results'] == 0
        assert result['filtered_results'] == 0
        assert result['max_score'] == 0
    
    def test_retrieve_context_client_error(self):
        """Test context retrieval with client error"""
        self.mock_bedrock.retrieve.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
            'retrieve'
        )
        
        result = self.processor.retrieve_context("test query")
        
        assert result['success'] is False
        assert 'error' in result
        assert result['total_results'] == 0
    
    def test_generate_response_success(self):
        """Test successful RAG response generation"""
        mock_response = {
            'output': {
                'text': 'Based on the available data, energy generation in 2024 increased by 15% compared to 2023, with renewable sources contributing 45% of total capacity.'
            },
            'citations': [
                {
                    'retrievedReferences': [
                        {
                            'content': {'text': 'Energy generation statistics for 2024'},
                            'location': {'s3Location': {'uri': 's3://bucket/gen-stats-2024.parquet'}},
                            'metadata': {'score': 0.92}
                        },
                        {
                            'content': {'text': 'Renewable energy capacity data'},
                            'location': {'s3Location': {'uri': 's3://bucket/renewable-capacity.parquet'}},
                            'metadata': {'score': 0.88}
                        }
                    ]
                }
            ]
        }
        
        self.mock_bedrock.retrieve_and_generate.return_value = mock_response
        
        result = self.processor.generate_response("What is the energy generation for 2024?")
        
        assert result['success'] is True
        assert 'energy generation in 2024 increased' in result['answer']
        assert len(result['citations']) == 2
        assert result['citation_count'] == 2
        assert result['generation_time_ms'] > 0
        
        # Verify citations are properly processed
        citations = result['citations']
        assert citations[0]['score'] == 0.92
        assert 'Energy generation statistics' in citations[0]['content']
    
    def test_generate_response_client_error(self):
        """Test RAG generation with client error"""
        self.mock_bedrock.retrieve_and_generate.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'retrieve_and_generate'
        )
        
        result = self.processor.generate_response("test query")
        
        assert result['success'] is False
        assert 'error' in result
        assert result['answer'] == ''
        assert result['citations'] == []
    
    def test_format_response_with_citations(self):
        """Test response formatting with citations"""
        query_result = {
            'original_query': 'What is renewable energy capacity?',
            'query_type': 'question'
        }
        
        generation_result = {
            'success': True,
            'answer': 'Renewable energy capacity reached 150 GW in 2024.',
            'citations': [
                {
                    'content': 'Detailed renewable capacity analysis showing 150 GW total installed capacity across wind, solar, and hydro sources.',
                    'location': {'s3Location': {'uri': 's3://bucket/renewable-analysis.parquet'}},
                    'score': 0.94
                },
                {
                    'content': 'Wind energy contributed 60 GW, solar 45 GW, and hydro 45 GW to the total renewable capacity.',
                    'location': {'s3Location': {'uri': 's3://bucket/source-breakdown.parquet'}},
                    'score': 0.87
                }
            ],
            'generation_time_ms': 1250,
            'citation_count': 2
        }
        
        query_id = 'test-query-123'
        
        response = self.processor.format_response(query_result, generation_result, query_id)
        
        # Verify response structure
        assert response['query_id'] == query_id
        assert response['question'] == 'What is renewable energy capacity?'
        assert response['answer'] == 'Renewable energy capacity reached 150 GW in 2024.'
        assert response['confidence_score'] > 0.9  # High confidence due to good citations
        assert len(response['sources']) == 2
        assert response['processing_time_ms'] == 1250
        assert 'timestamp' in response
        
        # Verify sources formatting
        sources = response['sources']
        assert sources[0]['id'] == 1
        assert sources[0]['relevance_score'] == 0.94
        assert 'Detailed renewable capacity analysis' in sources[0]['excerpt']
        assert sources[1]['id'] == 2
        assert sources[1]['relevance_score'] == 0.87
        
        # Verify metadata
        metadata = response['metadata']
        assert metadata['query_type'] == 'question'
        assert metadata['citation_count'] == 2
    
    def test_format_response_no_citations(self):
        """Test response formatting without citations"""
        query_result = {
            'original_query': 'General energy question',
            'query_type': 'general'
        }
        
        generation_result = {
            'success': True,
            'answer': 'General information about energy.',
            'citations': [],
            'generation_time_ms': 800,
            'citation_count': 0
        }
        
        response = self.processor.format_response(query_result, generation_result, 'test-id')
        
        assert response['confidence_score'] == 0.0  # No citations = low confidence
        assert len(response['sources']) == 0
        assert response['metadata']['citation_count'] == 0
    
    def test_send_metrics_success(self):
        """Test successful metrics sending"""
        query_result = {'query_type': 'question'}
        generation_result = {
            'success': True,
            'generation_time_ms': 1500,
            'citation_count': 3
        }
        
        self.processor.send_metrics(query_result, generation_result)
        
        # Verify CloudWatch call
        self.mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = self.mock_cloudwatch.put_metric_data.call_args[1]
        
        assert call_args['Namespace'] == 'ONS/RAGProcessor'
        metrics = call_args['MetricData']
        
        # Verify expected metrics
        metric_names = [metric['MetricName'] for metric in metrics]
        assert 'QueryProcessed' in metric_names
        assert 'QuerySuccess' in metric_names
        assert 'ResponseTime' in metric_names
        assert 'CitationCount' in metric_names
    
    def test_send_metrics_failure(self):
        """Test metrics sending for failed queries"""
        query_result = {'query_type': 'question'}
        generation_result = {
            'success': False,
            'error': 'Service unavailable'
        }
        
        self.processor.send_metrics(query_result, generation_result)
        
        call_args = self.mock_cloudwatch.put_metric_data.call_args[1]
        metrics = call_args['MetricData']
        
        metric_names = [metric['MetricName'] for metric in metrics]
        assert 'QueryFailure' in metric_names
        assert 'QuerySuccess' not in metric_names


class TestLambdaHandlerFunctions:
    """Test Lambda handler and related functions"""
    
    def test_handle_health_check(self):
        """Test health check endpoint"""
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            response = handle_health_check()
            
            assert response['statusCode'] == 200
            assert 'headers' in response
            
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
            assert body['service'] == 'ons-rag-query-processor'
            assert body['version'] == '1.0.0'
            assert body['knowledge_base_configured'] is True
            assert 'timestamp' in body
    
    def test_handle_health_check_no_kb(self):
        """Test health check without Knowledge Base configured"""
        with patch.dict(os.environ, {}, clear=True):
            response = handle_health_check()
            
            body = json.loads(response['body'])
            assert body['knowledge_base_configured'] is False
    
    def test_handle_query_request_success(self):
        """Test successful query request handling"""
        event = {
            'body': json.dumps({'question': 'What is the energy data?'})
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            with patch('lambda_function.QueryProcessor') as mock_processor_class:
                mock_processor = MagicMock()
                mock_processor_class.return_value = mock_processor
                
                # Mock successful processing
                mock_processor.preprocess_query.return_value = {
                    'is_valid': True,
                    'processed_query': 'What is the energy data?',
                    'query_type': 'question'
                }
                
                mock_processor.generate_response.return_value = {
                    'success': True,
                    'answer': 'Energy data shows...',
                    'citations': [],
                    'generation_time_ms': 1000,
                    'citation_count': 0
                }
                
                mock_processor.format_response.return_value = {
                    'query_id': 'test-id',
                    'question': 'What is the energy data?',
                    'answer': 'Energy data shows...',
                    'confidence_score': 0.8,
                    'sources': [],
                    'processing_time_ms': 1000,
                    'timestamp': int(time.time()),
                    'metadata': {'query_type': 'question', 'citation_count': 0}
                }
                
                response = handle_query_request(event)
                
                assert response['statusCode'] == 200
                body = json.loads(response['body'])
                assert body['answer'] == 'Energy data shows...'
                assert 'query_id' in body
    
    def test_handle_query_request_missing_question(self):
        """Test query request with missing question"""
        event = {
            'body': json.dumps({})
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            response = handle_query_request(event)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'Question parameter is required' in body['error']
    
    def test_handle_query_request_invalid_query(self):
        """Test query request with invalid query"""
        event = {
            'body': json.dumps({'question': ''})
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb-id'}):
            with patch('lambda_function.QueryProcessor') as mock_processor_class:
                mock_processor = MagicMock()
                mock_processor_class.return_value = mock_processor
                
                mock_processor.preprocess_query.return_value = {
                    'is_valid': False,
                    'validation_errors': ['Query cannot be empty']
                }
                
                response = handle_query_request(event)
                
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'Invalid query' in body['error']
    
    def test_lambda_handler_cors_preflight(self):
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
    
    def test_lambda_handler_health_endpoint(self):
        """Test health endpoint routing"""
        event = {
            'httpMethod': 'GET',
            'path': '/health'
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb'}):
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['status'] == 'healthy'
    
    def test_lambda_handler_query_endpoint(self):
        """Test query endpoint routing"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'test query'})
        }
        
        with patch('lambda_function.handle_query_request') as mock_handle:
            mock_handle.return_value = {
                'statusCode': 200,
                'body': json.dumps({'answer': 'test answer'})
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            mock_handle.assert_called_once_with(event)
    
    def test_lambda_handler_unknown_endpoint(self):
        """Test unknown endpoint handling"""
        event = {
            'httpMethod': 'GET',
            'path': '/unknown'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'Endpoint not found' in body['error']
    
    def test_lambda_handler_direct_invocation(self):
        """Test direct Lambda invocation (no API Gateway)"""
        event = {
            'question': 'Direct invocation query'
        }
        
        with patch('lambda_function.handle_query_request') as mock_handle:
            mock_handle.return_value = {
                'statusCode': 200,
                'body': json.dumps({'answer': 'direct answer'})
            }
            
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            mock_handle.assert_called_once_with(event)


class TestEnvironmentConfiguration:
    """Test environment variable handling"""
    
    def test_get_env_vars_defaults(self):
        """Test environment variables with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            env_vars = get_env_vars()
            
            assert env_vars['KNOWLEDGE_BASE_ID'] is None
            assert 'anthropic.claude-3-sonnet' in env_vars['MODEL_ARN']
            assert env_vars['MAX_QUERY_LENGTH'] == 1000
            assert env_vars['MAX_RESULTS'] == 5
            assert env_vars['MIN_CONFIDENCE_SCORE'] == 0.7
    
    def test_get_env_vars_custom(self):
        """Test environment variables with custom values"""
        custom_env = {
            'KNOWLEDGE_BASE_ID': 'custom-kb-id',
            'MODEL_ARN': 'custom-model-arn',
            'MAX_QUERY_LENGTH': '2000',
            'MAX_RESULTS': '10',
            'MIN_CONFIDENCE_SCORE': '0.8'
        }
        
        with patch.dict(os.environ, custom_env):
            env_vars = get_env_vars()
            
            assert env_vars['KNOWLEDGE_BASE_ID'] == 'custom-kb-id'
            assert env_vars['MODEL_ARN'] == 'custom-model-arn'
            assert env_vars['MAX_QUERY_LENGTH'] == 2000
            assert env_vars['MAX_RESULTS'] == 10
            assert env_vars['MIN_CONFIDENCE_SCORE'] == 0.8


class TestPerformanceAndStress:
    """Test performance and stress scenarios"""
    
    def test_large_query_processing(self):
        """Test processing of maximum-length queries"""
        # Create query at maximum length
        base_query = "What is the detailed energy generation data for "
        remaining_chars = 1000 - len(base_query) - 1
        large_query = base_query + "x" * remaining_chars + "?"
        
        with patch('boto3.client'):
            processor = QueryProcessor()
            result = processor.preprocess_query(large_query)
            
            assert result['is_valid'] is True
            assert len(result['processed_query']) == 1000
    
    def test_multiple_concurrent_queries_simulation(self):
        """Test simulation of multiple concurrent queries"""
        queries = [
            "What is energy generation?",
            "Show consumption data",
            "How does transmission work?",
            "List renewable sources",
            "Find peak demand periods"
        ]
        
        with patch('boto3.client'):
            processor = QueryProcessor()
            
            results = []
            for query in queries:
                result = processor.preprocess_query(query)
                results.append(result)
            
            # All should be processed successfully
            assert len(results) == 5
            for result in results:
                assert result['is_valid'] is True
    
    def test_response_time_measurement(self):
        """Test response time measurement accuracy"""
        with patch('boto3.client'):
            processor = QueryProcessor()
            
            # Mock a slow response
            with patch.object(processor, 'bedrock_runtime') as mock_bedrock:
                def slow_response(*args, **kwargs):
                    time.sleep(0.1)  # 100ms delay
                    return {
                        'output': {'text': 'Test response'},
                        'citations': []
                    }
                
                mock_bedrock.retrieve_and_generate.side_effect = slow_response
                
                result = processor.generate_response("test query")
                
                assert result['success'] is True
                assert result['generation_time_ms'] >= 100  # Should measure the delay


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios"""
    
    def test_bedrock_service_unavailable(self):
        """Test handling of Bedrock service unavailability"""
        with patch('boto3.client') as mock_client:
            mock_bedrock = MagicMock()
            mock_bedrock.retrieve_and_generate.side_effect = ClientError(
                {'Error': {'Code': 'ServiceUnavailableException', 'Message': 'Service temporarily unavailable'}},
                'retrieve_and_generate'
            )
            
            mock_client.return_value = mock_bedrock
            processor = QueryProcessor()
            
            result = processor.generate_response("test query")
            
            assert result['success'] is False
            assert 'Service temporarily unavailable' in result['error']
    
    def test_knowledge_base_not_found(self):
        """Test handling of missing Knowledge Base"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': json.dumps({'question': 'test query'})
        }
        
        with patch.dict(os.environ, {}, clear=True):  # No KNOWLEDGE_BASE_ID
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Knowledge Base ID not configured' in body['error']
    
    def test_malformed_json_body(self):
        """Test handling of malformed JSON in request body"""
        event = {
            'httpMethod': 'POST',
            'path': '/query',
            'body': 'invalid json{'
        }
        
        with patch.dict(os.environ, {'KNOWLEDGE_BASE_ID': 'test-kb'}):
            response = lambda_handler(event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])