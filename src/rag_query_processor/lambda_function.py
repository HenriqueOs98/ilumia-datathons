"""
RAG Query Processor Lambda Function

This Lambda function interfaces with Amazon Bedrock Knowledge Base to process
natural language queries using Retrieval-Augmented Generation (RAG) with
enhanced time series data integration.

Features:
- Query preprocessing and validation
- Knowledge Base retrieval and generation
- Time series context detection and InfluxDB query integration
- Enhanced response formatting with time series data
- Citation and source tracking for time series insights
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
import sys

# Import shared utilities for time series integration
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from shared_utils import (
        QueryTranslator,
        QueryLanguage,
        create_query_translator,
        translate_natural_language_query,
        determine_backend_for_query,
        DatabaseBackend,
        record_performance_metric
    )
    from shared_utils.logging_config import setup_logging
except ImportError:
    # Fallback for testing environment
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))
    from query_translator import (
        QueryTranslator,
        QueryLanguage,
        create_query_translator,
        translate_natural_language_query
    )
    from traffic_switch import (
        determine_backend_for_query,
        DatabaseBackend,
        record_performance_metric
    )
    from logging_config import setup_logging

# Configure logging
try:
    setup_logging()
    logger = logging.getLogger(__name__)
except:
    # Fallback logging setup
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
    """Handles RAG query processing with Knowledge Base and time series integration"""
    
    def __init__(self):
        global bedrock_runtime, cloudwatch
        if bedrock_runtime is None:
            bedrock_runtime = boto3.client('bedrock-agent-runtime')
        if cloudwatch is None:
            cloudwatch = boto3.client('cloudwatch')
        
        self.bedrock_runtime = bedrock_runtime
        self.cloudwatch = cloudwatch
        self.env_vars = get_env_vars()
        
        # Initialize time series query translator
        self.query_translator = None
        self.timeseries_lambda_name = os.environ.get('TIMESERIES_LAMBDA_NAME', 'ons-timeseries-query-processor')
        
        # Time series keywords for context detection
        self.timeseries_keywords = {
            'generation', 'consumption', 'demand', 'power', 'energy', 'capacity',
            'transmission', 'losses', 'efficiency', 'renewable', 'fossil', 'hydro',
            'solar', 'wind', 'thermal', 'nuclear', 'trend', 'peak', 'maximum',
            'minimum', 'average', 'total', 'hourly', 'daily', 'monthly', 'yearly',
            'region', 'southeast', 'northeast', 'north', 'south', 'central'
        }
        
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
        
        # Detect time series context
        result['has_timeseries_context'] = self._detect_timeseries_context(processed_query)
        result['timeseries_confidence'] = self._calculate_timeseries_confidence(processed_query)
        
        return result
    
    def _detect_timeseries_context(self, query: str) -> bool:
        """
        Detect if the query has time series context.
        
        Args:
            query: Processed query string
            
        Returns:
            True if query appears to be time series related
        """
        query_lower = query.lower()
        
        # Count time series keywords
        keyword_count = sum(1 for keyword in self.timeseries_keywords if keyword in query_lower)
        
        # Check for time-related patterns
        time_patterns = [
            r'\b(last|past|previous)\s+(hour|day|week|month|year)s?\b',
            r'\b(today|yesterday|tomorrow)\b',
            r'\b\d{4}-\d{2}-\d{2}\b',  # Date pattern
            r'\b(trend|pattern|history|over time)\b',
            r'\b(peak|maximum|minimum|average|total)\b',
            r'\b(generation|consumption|demand|power|energy)\b'
        ]
        
        time_pattern_matches = sum(1 for pattern in time_patterns if re.search(pattern, query_lower))
        
        # Determine if it's time series related
        # Need either multiple keywords OR strong time patterns
        return (keyword_count >= 2) or (time_pattern_matches >= 2) or (keyword_count >= 1 and time_pattern_matches >= 1)
    
    def _calculate_timeseries_confidence(self, query: str) -> float:
        """
        Calculate confidence score for time series context.
        
        Args:
            query: Processed query string
            
        Returns:
            Confidence score between 0 and 1
        """
        query_lower = query.lower()
        
        # Base score from keyword matches
        keyword_matches = sum(1 for keyword in self.timeseries_keywords if keyword in query_lower)
        keyword_score = min(0.8, keyword_matches * 0.15)
        
        # Boost for specific patterns
        pattern_boosts = {
            r'\b(generation|consumption|demand)\b': 0.3,
            r'\b(trend|pattern|over time)\b': 0.2,
            r'\b(peak|maximum|minimum)\b': 0.15,
            r'\b(last|past)\s+(day|week|month|year)\b': 0.2,
            r'\b(region|southeast|northeast)\b': 0.1,
            r'\b(hydro|solar|wind|thermal)\b': 0.15
        }
        
        pattern_score = 0
        for pattern, boost in pattern_boosts.items():
            if re.search(pattern, query_lower):
                pattern_score += boost
        
        total_score = min(1.0, keyword_score + pattern_score)
        return round(total_score, 3)
    
    def _get_query_translator(self):
        """Get or create query translator with lazy initialization."""
        if self.query_translator is None:
            try:
                self.query_translator = create_query_translator()
                logger.info("Query translator initialized for RAG processor")
            except Exception as e:
                logger.error(f"Failed to initialize query translator: {e}")
                self.query_translator = None
        
        return self.query_translator
    
    def query_timeseries_data(self, query: str, user_id: str = None) -> Dict[str, Any]:
        """
        Query time series data using traffic switching to determine backend.
        
        Args:
            query: Natural language query
            user_id: Optional user ID for consistent routing
            
        Returns:
            Time series query results
        """
        start_time = time.time()
        backend_used = None
        
        try:
            # Determine which backend to use based on traffic switching
            backend = determine_backend_for_query(user_id)
            backend_used = backend
            
            logger.info(f"Using {backend.value} for time series query")
            
            if backend == DatabaseBackend.INFLUXDB:
                return self._query_influxdb_data(query, start_time)
            else:
                return self._query_timestream_data(query, start_time)
                
        except Exception as e:
            # Record error metrics
            if backend_used:
                processing_time = (time.time() - start_time) * 1000
                record_performance_metric(backend_used, processing_time, False)
            
            logger.error(f"Time series query failed: {e}")
            return {'success': False, 'error': str(e), 'source': 'error'}
    
    def _query_influxdb_data(self, query: str, start_time: float) -> Dict[str, Any]:
        """
        Query InfluxDB for time series data.
        
        Args:
            query: Natural language query
            start_time: Query start time for metrics
            
        Returns:
            InfluxDB query results
        """
        try:
            # Try to use the query translator directly first
            translator = self._get_query_translator()
            if translator:
                try:
                    translation_result = translator.translate_query(query, QueryLanguage.FLUX)
                    
                    # Record successful performance metric
                    processing_time = (time.time() - start_time) * 1000
                    record_performance_metric(DatabaseBackend.INFLUXDB, processing_time, True)
                    
                    return {
                        'success': True,
                        'query_type': translation_result.get('query_type', 'unknown'),
                        'confidence_score': translation_result.get('confidence_score', 0),
                        'influxdb_query': translation_result.get('query', ''),
                        'parameters': translation_result.get('parameters', {}),
                        'template_description': translation_result.get('template_description', ''),
                        'time_series_data': [],  # Would be populated by actual InfluxDB execution
                        'source': 'influxdb_direct',
                        'backend_used': 'influxdb'
                    }
                except Exception as e:
                    logger.warning(f"Direct InfluxDB query translation failed: {e}")
            
            # Fallback to Lambda invocation if available
            return self._invoke_timeseries_lambda(query, start_time, 'influxdb')
                
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            record_performance_metric(DatabaseBackend.INFLUXDB, processing_time, False)
            raise
    
    def _query_timestream_data(self, query: str, start_time: float) -> Dict[str, Any]:
        """
        Query Timestream for time series data (legacy fallback).
        
        Args:
            query: Natural language query
            start_time: Query start time for metrics
            
        Returns:
            Timestream query results
        """
        try:
            # For Timestream, we'll use a simplified approach or fallback
            logger.info("Timestream queries not fully implemented in RAG processor")
            
            # Record performance metric
            processing_time = (time.time() - start_time) * 1000
            record_performance_metric(DatabaseBackend.TIMESTREAM, processing_time, True)
            
            return {
                'success': False,
                'error': 'Timestream queries not supported in RAG processor',
                'source': 'timestream_fallback',
                'backend_used': 'timestream'
            }
                
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            record_performance_metric(DatabaseBackend.TIMESTREAM, processing_time, False)
            raise
    
    def _invoke_timeseries_lambda(self, query: str, start_time: float, backend_hint: str = 'influxdb') -> Dict[str, Any]:
        """
        Invoke the time series Lambda function.
        
        Args:
            query: Natural language query
            start_time: Query start time for metrics
            backend_hint: Hint about which backend to use
            
        Returns:
            Lambda invocation results
        """
        try:
            lambda_client = boto3.client('lambda')
            
            payload = {
                'body': json.dumps({
                    'question': query,
                    'language': 'flux',
                    'use_cache': True
                })
            }
            
            response = lambda_client.invoke(
                FunctionName=self.timeseries_lambda_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            
            # Record performance metric
            processing_time = (time.time() - start_time) * 1000
            backend = DatabaseBackend.INFLUXDB if backend_hint == 'influxdb' else DatabaseBackend.TIMESTREAM
            record_performance_metric(backend, processing_time, result.get('statusCode') == 200)
            
            if result.get('statusCode') == 200:
                body = json.loads(result['body'])
                return {
                    'success': True,
                    'query_type': body.get('query_metadata', {}).get('query_type', 'unknown'),
                    'confidence_score': body.get('query_metadata', {}).get('confidence_score', 0),
                    'influxdb_query': body.get('influxdb_query', ''),
                    'time_series_data': body.get('time_series_data', []),
                    'record_count': body.get('record_count', 0),
                    'processing_time_ms': body.get('processing_time_ms', 0),
                    'source': 'lambda_invocation',
                    'backend_used': backend_hint
                }
            else:
                logger.error(f"Time series Lambda returned error: {result}")
                return {
                    'success': False, 
                    'error': 'Time series query failed', 
                    'source': 'lambda_invocation',
                    'backend_used': backend_hint
                }
                
        except Exception as e:
            logger.warning(f"Lambda invocation failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            backend = DatabaseBackend.INFLUXDB if backend_hint == 'influxdb' else DatabaseBackend.TIMESTREAM
            record_performance_metric(backend, processing_time, False)
            return {'success': False, 'error': str(e), 'source': 'lambda_invocation'}
        
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
            
    def generate_response(self, query: str, query_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate response using RAG with Knowledge Base and time series integration
        
        Args:
            query: Processed query string
            query_result: Query preprocessing results
            
        Returns:
            Dict containing generated response and metadata
        """
        try:
            start_time = time.time()
            
            # Check if this is a time series query
            timeseries_data = None
            if query_result.get('has_timeseries_context', False):
                logger.info(f"Detected time series context with confidence {query_result.get('timeseries_confidence', 0)}")
                # Extract user ID from query context if available
                user_id = query_result.get('user_id')
                timeseries_data = self.query_timeseries_data(query, user_id)
            
            # Enhance query with time series context if available
            enhanced_query = query
            if timeseries_data and timeseries_data.get('success', False):
                # Add time series context to the query for better RAG response
                ts_context = f"\n\nTime series analysis context:\n"
                ts_context += f"Query type: {timeseries_data.get('query_type', 'unknown')}\n"
                ts_context += f"Template: {timeseries_data.get('template_description', '')}\n"
                
                if timeseries_data.get('time_series_data'):
                    ts_context += f"Found {len(timeseries_data['time_series_data'])} time series data points.\n"
                    # Add sample data points for context
                    sample_data = timeseries_data['time_series_data'][:3]  # First 3 points
                    for i, point in enumerate(sample_data):
                        ts_context += f"Sample {i+1}: {point.get('timestamp', 'N/A')} - {point.get('field', 'value')}: {point.get('value', 'N/A')}\n"
                
                enhanced_query = f"{query}{ts_context}"
            
            response = self.bedrock_runtime.retrieve_and_generate(
                input={'text': enhanced_query},
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
                        'score': reference.get('metadata', {}).get('score', 0),
                        'source_type': 'knowledge_base'
                    })
            
            # Add time series data as citations if available
            if timeseries_data and timeseries_data.get('success', False):
                ts_citation = {
                    'content': f"Time series query: {timeseries_data.get('query_type', 'unknown')} analysis",
                    'location': {
                        'type': 'time_series_data',
                        'query_type': timeseries_data.get('query_type', 'unknown'),
                        'influxdb_query': timeseries_data.get('influxdb_query', ''),
                        'record_count': len(timeseries_data.get('time_series_data', []))
                    },
                    'score': timeseries_data.get('confidence_score', 0),
                    'source_type': 'time_series'
                }
                processed_citations.append(ts_citation)
            
            return {
                'success': True,
                'answer': output.get('text', ''),
                'citations': processed_citations,
                'generation_time_ms': round(generation_time * 1000, 2),
                'citation_count': len(processed_citations),
                'timeseries_data': timeseries_data,
                'has_timeseries_integration': timeseries_data is not None and timeseries_data.get('success', False)
            }
            
        except ClientError as e:
            logger.error(f"RAG generation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': '',
                'citations': [],
                'generation_time_ms': 0,
                'citation_count': 0,
                'timeseries_data': None,
                'has_timeseries_integration': False
            }
            
    def format_response(self, query_result: Dict[str, Any], 
                       generation_result: Dict[str, Any],
                       query_id: str) -> Dict[str, Any]:
        """
        Format the final response with all metadata including time series data
        
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
        
        # Boost confidence if time series data is integrated
        if generation_result.get('has_timeseries_integration', False):
            timeseries_confidence = query_result.get('timeseries_confidence', 0)
            confidence_score = min(0.98, confidence_score + (timeseries_confidence * 0.2))
        
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
                'model_used': self.env_vars['MODEL_ARN'].split('/')[-1] if self.env_vars['MODEL_ARN'] else 'unknown',
                'has_timeseries_context': query_result.get('has_timeseries_context', False),
                'timeseries_confidence': query_result.get('timeseries_confidence', 0),
                'has_timeseries_integration': generation_result.get('has_timeseries_integration', False)
            }
        }
        
        # Add time series data if available
        timeseries_data = generation_result.get('timeseries_data')
        if timeseries_data and timeseries_data.get('success', False):
            response['time_series_data'] = {
                'query_type': timeseries_data.get('query_type', 'unknown'),
                'confidence_score': timeseries_data.get('confidence_score', 0),
                'influxdb_query': timeseries_data.get('influxdb_query', ''),
                'data_points': timeseries_data.get('time_series_data', []),
                'record_count': len(timeseries_data.get('time_series_data', [])),
                'processing_time_ms': timeseries_data.get('processing_time_ms', 0),
                'source': timeseries_data.get('source', 'unknown')
            }
        
        # Format sources from citations
        for i, citation in enumerate(generation_result.get('citations', [])):
            source_type = citation.get('source_type', 'knowledge_base')
            
            if source_type == 'time_series':
                # Special formatting for time series sources
                source = {
                    'id': i + 1,
                    'type': 'time_series',
                    'relevance_score': round(citation.get('score', 0), 3),
                    'description': citation.get('content', ''),
                    'time_series_metadata': citation.get('location', {}),
                    'query_type': citation.get('location', {}).get('query_type', 'unknown'),
                    'record_count': citation.get('location', {}).get('record_count', 0)
                }
            else:
                # Standard knowledge base source formatting
                source = {
                    'id': i + 1,
                    'type': 'knowledge_base',
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
        
        # Generate response using RAG with time series integration
        generation_result = processor.generate_response(query_result['processed_query'], query_result)
        
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