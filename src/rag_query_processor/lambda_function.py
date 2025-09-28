"""
RAG Query Processor Lambda Function

This Lambda function interfaces with Amazon Bedrock Knowledge Base to process
natural language queries using Retrieval-Augmented Generation (RAG).

Features:
- Query preprocessing and validation
- Knowledge Base retrieval and generation
- Response formatting with source citations
- Comprehensive error handling and logging
- Query performance metrics
"""

import json
import boto3
import logging
import time
import uuid
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
import os
import re

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients will be initialized lazily
bedrock_runtime = None
cloudwatch = None

# Environment variable defaults
DEFAULT_MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
DEFAULT_MAX_QUERY_LENGTH = 1000
DEFAULT_MAX_RESULTS = 5
DEFAULT_MIN_CONFIDENCE_SCORE = 0.7

def get_env_vars():
    """Get environment variables at runtime"""
    return {
        'KNOWLEDGE_BASE_ID': os.environ.get('KNOWLEDGE_BASE_ID'),
        'MODEL_ARN': os.environ.get('MODEL_ARN', DEFAULT_MODEL_ARN),
        'MAX_QUERY_LENGTH': int(os.environ.get('MAX_QUERY_LENGTH', str(DEFAULT_MAX_QUERY_LENGTH))),
        'MAX_RESULTS': int(os.environ.get('MAX_RESULTS', str(DEFAULT_MAX_RESULTS))),
        'MIN_CONFIDENCE_SCORE': float(os.environ.get('MIN_CONFIDENCE_SCORE', str(DEFAULT_MIN_CONFIDENCE_SCORE)))
    }


class QueryProcessor:
    """Handles RAG query processing with Knowledge Base"""
    
    def __init__(self):
        global bedrock_runtime, cloudwatch
        if bedrock_runtime is None:
            bedrock_runtime = boto3.client('bedrock-agent-runtime')
        if cloudwatch is None:
            cloudwatch = boto3.client('cloudwatch')
        
        self.bedrock_runtime = bedrock_runtime
        self.cloudwatch = cloudwatch
        self.env_vars = get_env_vars()
        
    def preprocess_query(self, query: str) -> Dict[str, Any]:
        """
        Preprocess and validate the input query
        
        Args:
            query: Raw user query string
            
        Returns:
            Dict containing processed query and validation results
        """
        result = {
            'original_query': query,
            'processed_query': query.strip(),
            'is_valid': True,
            'validation_errors': []
        }
        
        # Basic validation
        if not query or not query.strip():
            result['is_valid'] = False
            result['validation_errors'].append('Query cannot be empty')
            return result
            
        # Length validation
        if len(query) > self.env_vars['MAX_QUERY_LENGTH']:
            result['is_valid'] = False
            result['validation_errors'].append(f'Query too long (max {self.env_vars["MAX_QUERY_LENGTH"]} characters)')
            return result
            
        # Clean up the query
        processed_query = query.strip()
        
        # Remove excessive whitespace
        processed_query = re.sub(r'\s+', ' ', processed_query)
        
        # Basic sanitization - remove potentially harmful characters
        processed_query = re.sub(r'[<>"\']', '', processed_query)
        
        result['processed_query'] = processed_query
        
        # Query type detection for better processing
        query_lower = processed_query.lower()
        if any(word in query_lower for word in ['show', 'list', 'find', 'get']):
            result['query_type'] = 'request'
        elif any(word in query_lower for word in ['what', 'how', 'when', 'where', 'why', 'which']):
            result['query_type'] = 'question'
        else:
            result['query_type'] = 'general'
            
        return result
        
    def retrieve_context(self, query: str) -> Dict[str, Any]:
        """
        Retrieve relevant context from Knowledge Base
        
        Args:
            query: Processed query string
            
        Returns:
            Dict containing retrieval results and metadata
        """
        try:
            start_time = time.time()
            
            response = self.bedrock_runtime.retrieve(
                knowledgeBaseId=self.env_vars['KNOWLEDGE_BASE_ID'],
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': self.env_vars['MAX_RESULTS']
                    }
                }
            )
            
            retrieval_time = time.time() - start_time
            
            # Process retrieval results
            results = response.get('retrievalResults', [])
            
            # Filter by confidence score
            filtered_results = [
                result for result in results 
                if result.get('score', 0) >= self.env_vars['MIN_CONFIDENCE_SCORE']
            ]
            
            return {
                'success': True,
                'results': filtered_results,
                'total_results': len(results),
                'filtered_results': len(filtered_results),
                'retrieval_time_ms': round(retrieval_time * 1000, 2),
                'max_score': max([r.get('score', 0) for r in results]) if results else 0
            }
            
        except ClientError as e:
            logger.error(f"Knowledge Base retrieval failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'total_results': 0,
                'filtered_results': 0,
                'retrieval_time_ms': 0,
                'max_score': 0
            }
            
    def generate_response(self, query: str) -> Dict[str, Any]:
        """
        Generate response using RAG with Knowledge Base
        
        Args:
            query: Processed query string
            
        Returns:
            Dict containing generated response and metadata
        """
        try:
            start_time = time.time()
            
            response = self.bedrock_runtime.retrieve_and_generate(
                input={'text': query},
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': self.env_vars['KNOWLEDGE_BASE_ID'],
                        'modelArn': self.env_vars['MODEL_ARN'],
                        'retrievalConfiguration': {
                            'vectorSearchConfiguration': {
                                'numberOfResults': self.env_vars['MAX_RESULTS']
                            }
                        }
                    }
                }
            )
            
            generation_time = time.time() - start_time
            
            # Extract response components
            output = response.get('output', {})
            citations = response.get('citations', [])
            
            # Process citations for better formatting
            processed_citations = []
            for citation in citations:
                for reference in citation.get('retrievedReferences', []):
                    processed_citations.append({
                        'content': reference.get('content', {}).get('text', ''),
                        'location': reference.get('location', {}),
                        'score': reference.get('metadata', {}).get('score', 0)
                    })
            
            return {
                'success': True,
                'answer': output.get('text', ''),
                'citations': processed_citations,
                'generation_time_ms': round(generation_time * 1000, 2),
                'citation_count': len(processed_citations)
            }
            
        except ClientError as e:
            logger.error(f"RAG generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': '',
                'citations': [],
                'generation_time_ms': 0,
                'citation_count': 0
            }
            
    def format_response(self, query_result: Dict[str, Any], 
                       generation_result: Dict[str, Any],
                       query_id: str) -> Dict[str, Any]:
        """
        Format the final response with all metadata
        
        Args:
            query_result: Query preprocessing results
            generation_result: RAG generation results
            query_id: Unique query identifier
            
        Returns:
            Formatted response dictionary
        """
        # Calculate confidence score based on citations and retrieval quality
        confidence_score = 0.0
        if generation_result['success'] and generation_result['citations']:
            # Base confidence on citation scores and count
            citation_scores = [c.get('score', 0) for c in generation_result['citations']]
            if citation_scores:
                confidence_score = min(0.95, max(citation_scores) * (1 + len(citation_scores) * 0.1))
        
        response = {
            'query_id': query_id,
            'question': query_result['original_query'],
            'answer': generation_result.get('answer', ''),
            'confidence_score': round(confidence_score, 3),
            'sources': [],
            'processing_time_ms': generation_result.get('generation_time_ms', 0),
            'timestamp': int(time.time()),
            'metadata': {
                'query_type': query_result.get('query_type', 'general'),
                'citation_count': generation_result.get('citation_count', 0),
                'model_used': self.env_vars['MODEL_ARN'].split('/')[-1] if self.env_vars['MODEL_ARN'] else 'unknown'
            }
        }
        
        # Format sources from citations
        for i, citation in enumerate(generation_result.get('citations', [])):
            source = {
                'id': i + 1,
                'relevance_score': round(citation.get('score', 0), 3),
                'excerpt': citation.get('content', '')[:200] + '...' if len(citation.get('content', '')) > 200 else citation.get('content', ''),
                'location': citation.get('location', {})
            }
            response['sources'].append(source)
            
        return response
        
    def send_metrics(self, query_result: Dict[str, Any], 
                    generation_result: Dict[str, Any]):
        """
        Send custom metrics to CloudWatch
        
        Args:
            query_result: Query processing results
            generation_result: Generation results
        """
        try:
            metrics = []
            
            # Query processing metrics
            metrics.append({
                'MetricName': 'QueryProcessed',
                'Value': 1,
                'Unit': 'Count'
            })
            
            if generation_result['success']:
                metrics.append({
                    'MetricName': 'QuerySuccess',
                    'Value': 1,
                    'Unit': 'Count'
                })
                
                metrics.append({
                    'MetricName': 'ResponseTime',
                    'Value': generation_result.get('generation_time_ms', 0),
                    'Unit': 'Milliseconds'
                })
                
                metrics.append({
                    'MetricName': 'CitationCount',
                    'Value': generation_result.get('citation_count', 0),
                    'Unit': 'Count'
                })
            else:
                metrics.append({
                    'MetricName': 'QueryFailure',
                    'Value': 1,
                    'Unit': 'Count'
                })
            
            # Send metrics to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace='ONS/RAGProcessor',
                MetricData=metrics
            )
            
        except Exception as e:
            logger.warning(f"Failed to send metrics: {e}")


def handle_health_check() -> Dict[str, Any]:
    """
    Handle health check endpoint
    
    Returns:
        Health status response
    """
    env_vars = get_env_vars()
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'healthy',
            'timestamp': int(time.time()),
            'service': 'ons-rag-query-processor',
            'version': '1.0.0',
            'knowledge_base_configured': bool(env_vars['KNOWLEDGE_BASE_ID'])
        })
    }


def handle_query_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle query processing request
    
    Args:
        event: Lambda event containing the query
        
    Returns:
        Formatted response with answer and sources
    """
    # Generate unique query ID
    query_id = str(uuid.uuid4())
    
    logger.info(f"Processing query {query_id}")
    
    try:
        # Get environment variables
        env_vars = get_env_vars()
        
        # Validate environment
        if not env_vars['KNOWLEDGE_BASE_ID']:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Knowledge Base ID not configured',
                    'query_id': query_id
                })
            }
        
        # Extract query from event
        if 'body' in event:
            # API Gateway event
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            query = body.get('question', body.get('query', ''))  # Support both 'question' and 'query' fields
        else:
            # Direct invocation
            query = event.get('question', event.get('query', ''))
            
        if not query:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Question parameter is required',
                    'query_id': query_id
                })
            }
        
        # Initialize processor
        processor = QueryProcessor()
        
        # Process query
        query_result = processor.preprocess_query(query)
        
        if not query_result['is_valid']:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Invalid query',
                    'validation_errors': query_result['validation_errors'],
                    'query_id': query_id
                })
            }
        
        # Generate response using RAG
        generation_result = processor.generate_response(query_result['processed_query'])
        
        if not generation_result['success']:
            logger.error(f"RAG generation failed for query {query_id}: {generation_result.get('error')}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Failed to generate response',
                    'details': generation_result.get('error'),
                    'query_id': query_id
                })
            }
        
        # Format final response
        response = processor.format_response(query_result, generation_result, query_id)
        
        # Send metrics
        processor.send_metrics(query_result, generation_result)
        
        logger.info(f"Successfully processed query {query_id} in {response['processing_time_ms']}ms")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'POST,GET,OPTIONS'
            },
            'body': json.dumps(response)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error processing query {query_id}: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'query_id': query_id
            })
        }


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for API requests
    
    Routes requests to appropriate handlers based on HTTP method and path
    
    Args:
        event: Lambda event from API Gateway
        context: Lambda context
        
    Returns:
        HTTP response for API Gateway
    """
    try:
        # Handle CORS preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'POST,GET,OPTIONS'
                },
                'body': ''
            }
        
        # Route based on path and method
        path = event.get('path', '/')
        method = event.get('httpMethod', 'POST')
        
        logger.info(f"Handling {method} request to {path}")
        
        # Health check endpoint
        if path == '/health' and method == 'GET':
            return handle_health_check()
        
        # Query endpoint
        elif path == '/query' and method == 'POST':
            return handle_query_request(event)
        
        # Direct invocation (no API Gateway)
        elif 'httpMethod' not in event:
            return handle_query_request(event)
        
        # Unknown endpoint
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Endpoint not found',
                    'path': path,
                    'method': method
                })
            }
            
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }