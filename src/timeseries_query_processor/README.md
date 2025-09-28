# Time Series Query Processor Lambda

This Lambda function processes time series queries by translating natural language questions into InfluxDB queries and executing them with proper error handling, performance monitoring, and result caching.

## Features

- **Natural Language Processing**: Translates natural language questions into InfluxDB Flux or InfluxQL queries
- **Query Execution**: Executes queries against InfluxDB with timeout and error handling
- **Result Caching**: Caches query results to improve performance for repeated queries
- **Performance Monitoring**: Publishes detailed metrics to CloudWatch
- **Result Formatting**: Formats time series data for API consumption
- **Health Checks**: Provides health check endpoints for monitoring

## API Endpoints

### POST /query
Process a time series query.

**Request Body:**
```json
{
  "question": "Show hydro generation trend in southeast for last month",
  "language": "flux",
  "context": {
    "default_region": "southeast",
    "time_zone": "UTC"
  },
  "use_cache": true
}
```

**Response:**
```json
{
  "question": "Show hydro generation trend in southeast for last month",
  "query_metadata": {
    "query_type": "generation_trend",
    "language": "flux",
    "confidence_score": 0.95,
    "template_description": "Analyze power generation trends over time"
  },
  "influxdb_query": "from(bucket: \"energy_data\")...",
  "time_series_data": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "measurement": "generation_data",
      "field": "power_mw",
      "value": 14000.5,
      "tags": {
        "region": "southeast",
        "energy_source": "hydro"
      }
    }
  ],
  "record_count": 1,
  "cached": false,
  "processing_time_ms": 245
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "components": {
    "influxdb": {
      "status": "healthy",
      "response_time_ms": 15.2
    },
    "query_translator": {
      "status": "healthy",
      "test_query_type": "generation_trend"
    },
    "cache": {
      "status": "healthy",
      "cached_queries": 5,
      "cache_ttl_seconds": 300
    }
  },
  "response_time_ms": 25.8
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INFLUXDB_URL` | InfluxDB server URL | Required |
| `INFLUXDB_TOKEN` | InfluxDB authentication token | Required |
| `INFLUXDB_ORG` | InfluxDB organization | `ons-energy` |
| `INFLUXDB_BUCKET` | Default InfluxDB bucket | `energy_data` |
| `QUERY_CACHE_TTL` | Cache TTL in seconds | `300` |
| `QUERY_TIMEOUT_SECONDS` | Query timeout | `30` |
| `MAX_RESULT_SIZE` | Maximum result records | `10000` |
| `CLOUDWATCH_NAMESPACE` | CloudWatch metrics namespace | `ONS/TimeSeriesQueryProcessor` |

## Query Language Support

The processor supports both InfluxDB query languages:

### Flux (Default)
Modern functional query language with advanced analytics capabilities.

### InfluxQL
SQL-like query language for familiar syntax.

## Caching

Query results are cached in memory with configurable TTL to improve performance:

- Cache key is generated from query and parameters
- Expired entries are automatically removed
- Cache can be disabled per request with `use_cache: false`

## Performance Monitoring

The function publishes the following metrics to CloudWatch:

- `query_count`: Number of queries processed
- `cache_hits`: Number of cache hits
- `cache_misses`: Number of cache misses
- `query_errors`: Number of query errors
- `query_time_ms`: Total query processing time
- `translation_time_ms`: Query translation time
- `influxdb_query_time_ms`: InfluxDB execution time
- `format_time_ms`: Result formatting time

## Error Handling

The function handles various error scenarios:

- **QueryProcessorError**: Client errors (400) for invalid requests
- **InfluxDB Connection Errors**: Service errors (503) for database issues
- **Query Timeout**: Timeout errors for long-running queries
- **Result Size Limits**: Automatic truncation of large result sets

## Testing

Run unit tests:
```bash
python -m pytest src/timeseries_query_processor/test_lambda_function.py -v
```

Run integration tests:
```bash
python -m pytest src/timeseries_query_processor/integration_test.py -v
```

## Deployment

The function is deployed as part of the ONS Data Platform infrastructure using Terraform. It requires:

- VPC configuration for InfluxDB access
- IAM roles for CloudWatch metrics
- Lambda layer with shared utilities
- Environment variables for InfluxDB connection

## Dependencies

- **influxdb-client**: InfluxDB Python client
- **boto3**: AWS SDK for CloudWatch metrics
- **shared_utils**: Platform shared utilities (query translator, InfluxDB handler)

## Architecture

```
API Gateway → Lambda Function → InfluxDB
                ↓
            CloudWatch Metrics
                ↓
            In-Memory Cache
```

The function integrates with:
- InfluxDB for time series data storage
- CloudWatch for monitoring and alerting
- API Gateway for HTTP endpoints
- Shared utilities for common functionality