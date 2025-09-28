"""
Time Series Query Processor Lambda Function.

This Lambda function processes time series queries by executing InfluxDB queries
with proper error handling, performance monitoring, result caching, and formatting
time series data for API responses.
"""

import json
import logging
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

# Import shared utilities
import sys
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))

from shared_utils import (
    InfluxDBHandler,
    QueryTranslator,
    QueryLanguage,
    create_query_translator,
    translate_natural_language_query
)
from shared_utils.logging_config import setup_logging

# Set up logging
logger = setup_logging(__name__)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client('ssm')

# Cache for query results
query_cache = {}
CACHE_TTL_SECONDS = int(os.getenv('QUERY_CACHE_TTL', '300'))  # 5 minutes default


class QueryProcessorError(Exception):
    """Custom exception for query processor errors."""
    pass


class TimeSeriesQueryProcessor:
    """
    Time series query processor with InfluxDB integration.
    
    Handles natural language query translation, InfluxDB query execution,
    result caching, and performance monitoring.
    """
    
    def __init__(self):
        """Initialize the query processor."""
        self.influxdb_handler = None
        self.query_translator = None
        self.metrics_namespace = os.getenv('CLOUDWATCH_NAMESPACE', 'ONS/TimeSeriesQueryProcessor')
        
        # Performance thresholds
        self.query_timeout_seconds = int(os.getenv('QUERY_TIMEOUT_SECONDS', '30'))
        self.max_result_size = int(os.getenv('MAX_RESULT_SIZE', '10000'))
        
        logger.info("TimeSeriesQueryProcessor initialized")
    
    def _get_influxdb_handler(self) -> InfluxDBHandler:
        """Get or create InfluxDB handler with lazy initialization."""
        if self.influxdb_handler is None:
            try:
                self.influxdb_handler = InfluxDBHandler()
                logger.info("InfluxDB handler initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize InfluxDB handler: {e}")
                raise QueryProcessorError(f"InfluxDB connection failed: {e}")
        
        return self.influxdb_handler
    
    def _get_query_translator(self) -> QueryTranslator:
        """Get or create query translator with lazy initialization."""
        if self.query_translator is None:
            try:
                self.query_translator = create_query_translator()
                logger.info("Query translator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize query translator: {e}")
                raise QueryProcessorError(f"Query translator initialization failed: {e}")
        
        return self.query_translator
    
    def _generate_cache_key(self, query: str, parameters: Dict[str, Any]) -> str:
        """Generate cache key for query results."""
        import hashlib
        
        cache_data = {
            'query': query,
            'parameters': parameters
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached query result if still valid."""
        if cache_key in query_cache:
            cached_data = query_cache[cache_key]
            cache_time = cached_data.get('timestamp', 0)
            
            if time.time() - cache_time < CACHE_TTL_SECONDS:
                logger.info(f"Cache hit for key: {cache_key}")
                return cached_data.get('result')
            else:
                # Remove expired cache entry
                del query_cache[cache_key]
                logger.info(f"Cache expired for key: {cache_key}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache query result with timestamp."""
        query_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        logger.info(f"Result cached with key: {cache_key}")
    
    def _publish_metrics(self, metrics: Dict[str, Any]) -> None:
        """Publish performance metrics to CloudWatch."""
        try:
            metric_data = []
            
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    metric_data.append({
                        'MetricName': metric_name,
                        'Value': value,
                        'Unit': 'Count' if metric_name.endswith('_count') else 'Milliseconds',
                        'Timestamp': datetime.now(timezone.utc)
                    })
            
            if metric_data:
                cloudwatch.put_metric_data(
                    Namespace=self.metrics_namespace,
                    MetricData=metric_data
                )
                logger.debug(f"Published {len(metric_data)} metrics to CloudWatch")
                
        except Exception as e:
            logger.warning(f"Failed to publish metrics: {e}")
    
    def _format_time_series_data(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format raw InfluxDB results for API response.
        
        Args:
            raw_results: Raw results from InfluxDB query
            
        Returns:
            Formatted time series data
        """
        formatted_data = []
        
        for record in raw_results:
            try:
                formatted_record = {
                    'timestamp': record.get('time', '').isoformat() if hasattr(record.get('time', ''), 'isoformat') else str(record.get('time', '')),
                    'measurement': record.get('measurement', ''),
                    'field': record.get('field', ''),
                    'value': record.get('value'),
                    'tags': {k: v for k, v in record.get('tags', {}).items() if k not in ['_measurement', '_field', '_time', '_value']}
                }
                
                # Clean up None values
                formatted_record = {k: v for k, v in formatted_record.items() if v is not None}
                formatted_data.append(formatted_record)
                
            except Exception as e:
                logger.warning(f"Failed to format record: {record}, error: {e}")
                continue
        
        return formatted_data
    
    def _validate_query_parameters(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and extract query parameters from event.
        
        Args:
            event: Lambda event
            
        Returns:
            Validated parameters
            
        Raises:
            QueryProcessorError: If validation fails
        """
        try:
            # Parse body if it's a string
            if isinstance(event.get('body'), str):
                body = json.loads(event['body'])
            else:
                body = event.get('body', {})
            
            # Extract required parameters
            question = body.get('question', '').strip()
            if not question:
                raise QueryProcessorError("Question parameter is required")
            
            # Extract optional parameters
            language = body.get('language', 'flux').lower()
            if language not in ['flux', 'influxql']:
                raise QueryProcessorError(f"Unsupported query language: {language}")
            
            context = body.get('context', {})
            use_cache = body.get('use_cache', True)
            
            return {
                'question': question,
                'language': QueryLanguage.FLUX if language == 'flux' else QueryLanguage.INFLUXQL,
                'context': context,
                'use_cache': use_cache
            }
            
        except json.JSONDecodeError as e:
            raise QueryProcessorError(f"Invalid JSON in request body: {e}")
        except Exception as e:
            raise QueryProcessorError(f"Parameter validation failed: {e}")
    
    def process_query(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process time series query request.
        
        Args:
            event: Lambda event containing query parameters
            
        Returns:
            Query results with metadata
            
        Raises:
            QueryProcessorError: If query processing fails
        """
        start_time = time.time()
        metrics = {
            'query_count': 1,
            'cache_hits': 0,
            'cache_misses': 0,
            'query_errors': 0
        }
        
        try:
            # Validate parameters
            params = self._validate_query_parameters(event)
            logger.info(f"Processing query: {params['question']}")
            
            # Translate natural language to InfluxDB query
            translator = self._get_query_translator()
            translation_start = time.time()
            
            translation_result = translator.translate_query(
                params['question'],
                params['language'],
                params['context']
            )
            
            translation_time = (time.time() - translation_start) * 1000
            metrics['translation_time_ms'] = translation_time
            
            influxdb_query = translation_result['query']
            query_metadata = {
                'query_type': translation_result['query_type'],
                'language': translation_result['language'],
                'confidence_score': translation_result['confidence_score'],
                'template_description': translation_result['template_description']
            }
            
            logger.info(f"Query translated in {translation_time:.2f}ms: {query_metadata['query_type']}")
            
            # Check cache if enabled
            cache_key = None
            cached_result = None
            
            if params['use_cache']:
                cache_key = self._generate_cache_key(influxdb_query, translation_result['parameters'])
                cached_result = self._get_cached_result(cache_key)
                
                if cached_result:
                    metrics['cache_hits'] = 1
                    metrics['query_time_ms'] = (time.time() - start_time) * 1000
                    self._publish_metrics(metrics)
                    
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            **cached_result,
                            'cached': True,
                            'processing_time_ms': metrics['query_time_ms']
                        })
                    }
                else:
                    metrics['cache_misses'] = 1
            
            # Execute InfluxDB query
            influxdb_handler = self._get_influxdb_handler()
            query_start = time.time()
            
            raw_results = influxdb_handler.query_flux(influxdb_query)
            
            query_time = (time.time() - query_start) * 1000
            metrics['influxdb_query_time_ms'] = query_time
            
            logger.info(f"InfluxDB query executed in {query_time:.2f}ms, returned {len(raw_results)} records")
            
            # Check result size limits
            if len(raw_results) > self.max_result_size:
                logger.warning(f"Query returned {len(raw_results)} records, truncating to {self.max_result_size}")
                raw_results = raw_results[:self.max_result_size]
                query_metadata['truncated'] = True
                query_metadata['total_records'] = len(raw_results)
            
            # Format results
            format_start = time.time()
            formatted_data = self._format_time_series_data(raw_results)
            format_time = (time.time() - format_start) * 1000
            metrics['format_time_ms'] = format_time
            
            # Prepare response
            response_data = {
                'question': params['question'],
                'query_metadata': query_metadata,
                'influxdb_query': influxdb_query,
                'time_series_data': formatted_data,
                'record_count': len(formatted_data),
                'cached': False
            }
            
            # Cache result if enabled
            if params['use_cache'] and cache_key:
                self._cache_result(cache_key, response_data)
            
            # Calculate total processing time
            total_time = (time.time() - start_time) * 1000
            metrics['query_time_ms'] = total_time
            
            # Publish metrics
            self._publish_metrics(metrics)
            
            logger.info(f"Query processed successfully in {total_time:.2f}ms")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    **response_data,
                    'processing_time_ms': total_time
                })
            }
            
        except QueryProcessorError as e:
            metrics['query_errors'] = 1
            metrics['query_time_ms'] = (time.time() - start_time) * 1000
            self._publish_metrics(metrics)
            
            logger.error(f"Query processing error: {e}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': str(e),
                    'error_type': 'QueryProcessorError',
                    'processing_time_ms': metrics['query_time_ms']
                })
            }
            
        except Exception as e:
            metrics['query_errors'] = 1
            metrics['query_time_ms'] = (time.time() - start_time) * 1000
            self._publish_metrics(metrics)
            
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Internal server error',
                    'error_type': 'InternalError',
                    'processing_time_ms': metrics['query_time_ms']
                })
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the query processor.
        
        Returns:
            Health check results
        """
        start_time = time.time()
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {}
        }
        
        try:
            # Check InfluxDB connection
            influxdb_handler = self._get_influxdb_handler()
            influxdb_health = influxdb_handler.health_check()
            health_status['components']['influxdb'] = influxdb_health
            
            if influxdb_health['status'] != 'healthy':
                health_status['status'] = 'degraded'
            
            # Check query translator
            try:
                translator = self._get_query_translator()
                test_result = translator.translate_query("test query", QueryLanguage.FLUX)
                health_status['components']['query_translator'] = {
                    'status': 'healthy',
                    'test_query_type': test_result.get('query_type', 'unknown')
                }
            except Exception as e:
                health_status['components']['query_translator'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['status'] = 'degraded'
            
            # Check cache status
            health_status['components']['cache'] = {
                'status': 'healthy',
                'cached_queries': len(query_cache),
                'cache_ttl_seconds': CACHE_TTL_SECONDS
            }
            
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        health_status['response_time_ms'] = (time.time() - start_time) * 1000
        return health_status


# Global processor instance
processor = TimeSeriesQueryProcessor()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for time series query processing.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        HTTP response
    """
    try:
        # Log request details
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Handle different event types
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
        
        if http_method == 'GET' and path.endswith('/health'):
            # Health check endpoint
            health_result = processor.health_check()
            status_code = 200 if health_result['status'] == 'healthy' else 503
            
            return {
                'statusCode': status_code,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(health_result)
            }
        
        elif http_method == 'POST':
            # Query processing endpoint
            return processor.process_query(event)
        
        elif http_method == 'OPTIONS':
            # CORS preflight
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': ''
            }
        
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Method {http_method} not allowed'
                })
            }
    
    except Exception as e:
        logger.error(f"Lambda handler error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'error_type': 'LambdaHandlerError'
            })
        }