# API Documentation
This document describes the REST API endpoints and their usage.
## Overview
The ONS Data Platform provides a REST API for querying energy data using natural language.
The API is built using AWS API Gateway and Lambda functions.

## Authentication
All API requests require an API key passed in the `x-api-key` header.

```bash
curl -H "x-api-key: YOUR_API_KEY" https://api.ons-platform.com/query
```

## Endpoints

### Rag Query Processor

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

**Handler Function:**
- **Function**: `lambda_handler`
- **Description**: Main Lambda handler for API requests

Routes requests to appropriate handlers based on HTTP method and path

Args:
    event: Lambda event from API Gateway
    context: Lambda context
    
Returns:
    HTTP response for API Gateway
- **Parameters**:
  - `event`: Any - 
  - `context`: Any - 

### Lambda Router

Lambda Router Function for ONS Data Platform

This function analyzes incoming file metadata and determines the appropriate
processing path based on file type, size, and other characteristics.

Supported formats: CSV, XLSX, Parquet, PDF
Default output format: Parquet (optimized for analytics and storage)

Requirements: 2.1, 2.4, 8.1

**Handler Function:**
- **Function**: `lambda_handler`
- **Description**: Main Lambda handler for routing file processing decisions.

Args:
    event: Lambda event containing file metadata
    context: Lambda context object
    
Returns:
    Dict containing processing type and configuration
- **Parameters**:
  - `event`: Any - 
  - `context`: Any - 

## Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Rate Limiting

API requests are limited to:
- **Burst**: 2000 requests
- **Rate**: 1000 requests per second

## Examples

### Query Energy Data

```bash
curl -X POST https://api.ons-platform.com/query \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "What was the total energy generation in the Southeast region last month?"
  }'
```

**Response:**
```json
{
  "query_id": "uuid-string",
  "question": "What was the total energy generation in the Southeast region last month?",
  "answer": "The total energy generation in the Southeast region last month was 15,234 MW...",
  "confidence_score": 0.95,
  "sources": [
    {
      "document": "generation_data_2024_01.parquet",
      "relevance_score": 0.98,
      "excerpt": "Southeast region generation data..."
    }
  ],
  "processing_time_ms": 1250,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

