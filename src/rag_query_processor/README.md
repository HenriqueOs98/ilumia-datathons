# RAG Query Processor

This Lambda function implements Retrieval-Augmented Generation (RAG) query processing using Amazon Bedrock Knowledge Base. It processes natural language queries about ONS energy data and returns intelligent responses with source citations.

## Features

- **Natural Language Processing**: Handles questions in Portuguese and English
- **Query Preprocessing**: Validates, sanitizes, and optimizes user queries
- **RAG Integration**: Uses Amazon Bedrock Knowledge Base for context retrieval
- **Source Citations**: Provides references to original data sources
- **Error Handling**: Comprehensive error handling with meaningful messages
- **Performance Monitoring**: CloudWatch metrics for query processing
- **CORS Support**: Ready for web application integration

## Architecture

```
User Query → Query Preprocessing → Knowledge Base Retrieval → Response Generation → Formatted Response
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KNOWLEDGE_BASE_ID` | Amazon Bedrock Knowledge Base ID | Required |
| `MODEL_ARN` | Bedrock model ARN for generation | Claude 3.5 Sonnet |
| `MAX_QUERY_LENGTH` | Maximum query length in characters | 1000 |
| `MAX_RESULTS` | Maximum retrieval results | 5 |
| `MIN_CONFIDENCE_SCORE` | Minimum confidence for results | 0.7 |

## Input Format

### API Gateway Event
```json
{
  "body": "{\"query\": \"What is the energy generation data for 2024?\"}"
}
```

### Direct Invocation
```json
{
  "query": "What is the energy generation data for 2024?"
}
```

## Output Format

```json
{
  "query_id": "uuid",
  "question": "What is the energy generation data for 2024?",
  "answer": "Based on the available data, the energy generation in 2024...",
  "confidence_score": 0.85,
  "sources": [
    {
      "id": 1,
      "relevance_score": 0.9,
      "excerpt": "Energy generation data for 2024 shows...",
      "location": {
        "s3Location": {
          "uri": "s3://bucket/energy-gen-2024.parquet"
        }
      }
    }
  ],
  "processing_time_ms": 1200,
  "timestamp": 1703123456,
  "metadata": {
    "query_type": "question",
    "citation_count": 1,
    "model_used": "claude-3-sonnet"
  }
}
```

## Query Types

The system automatically detects and categorizes queries:

- **Question**: Queries starting with what, how, when, where, why, which
- **Request**: Queries with show, list, find, get
- **General**: Other types of queries

## Error Handling

### Client Errors (400)
- Empty or missing query
- Query too long (>1000 characters)
- Invalid query format

### Server Errors (500)
- Knowledge Base not configured
- Bedrock service unavailable
- Internal processing errors

## Performance Metrics

The function sends custom metrics to CloudWatch:

- `QueryProcessed`: Total queries processed
- `QuerySuccess`: Successful query responses
- `QueryFailure`: Failed query attempts
- `ResponseTime`: Query processing time in milliseconds
- `CitationCount`: Number of sources cited per response

## Security Features

- **Input Sanitization**: Removes potentially harmful characters
- **Query Validation**: Enforces length and format limits
- **CORS Headers**: Proper cross-origin resource sharing
- **Error Masking**: Doesn't expose internal system details

## Testing

### Unit Tests
```bash
cd src/rag_query_processor
python -m pytest test_lambda_function.py -v
```

### Validation Script
```bash
cd src/rag_query_processor
python validate_implementation.py
```

### Integration Testing
The function includes comprehensive tests for:
- Query preprocessing with various input types
- Response formatting and structure validation
- Error handling scenarios
- Edge cases and special characters

## Development

### Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables
3. Run tests: `python -m pytest`
4. Validate implementation: `python validate_implementation.py`

### Deployment
The function is deployed via Terraform as part of the ONS Data Platform infrastructure.

## Usage Examples

### Basic Energy Query
```json
{
  "query": "What is the current energy generation capacity in Brazil?"
}
```

### Specific Data Request
```json
{
  "query": "Show me renewable energy data for the Southeast region"
}
```

### Trend Analysis
```json
{
  "query": "How has solar energy generation changed over the past year?"
}
```

## Troubleshooting

### Common Issues

1. **Knowledge Base ID not configured**
   - Ensure `KNOWLEDGE_BASE_ID` environment variable is set
   - Verify Knowledge Base exists and is active

2. **No results returned**
   - Check if data has been ingested into Knowledge Base
   - Verify S3 data source configuration
   - Lower `MIN_CONFIDENCE_SCORE` if needed

3. **High latency**
   - Monitor CloudWatch metrics
   - Consider adjusting `MAX_RESULTS` parameter
   - Check Knowledge Base indexing status

4. **Authentication errors**
   - Verify Lambda execution role has Bedrock permissions
   - Check Knowledge Base access policies

### Monitoring

Monitor the following CloudWatch metrics:
- Function duration and errors
- Custom RAG processing metrics
- Knowledge Base query performance
- API Gateway integration metrics

## Contributing

When modifying this function:
1. Update tests in `test_lambda_function.py`
2. Run validation script to ensure compatibility
3. Update documentation for any new features
4. Test with various query types and edge cases