# ONS Data Platform API Documentation - InfluxDB Edition

## Overview

This document describes the updated API capabilities after migrating from Amazon Timestream to Amazon Timestream for InfluxDB. The API now supports enhanced query capabilities including InfluxQL and Flux query languages while maintaining backward compatibility.

## Table of Contents

1. [Authentication](#authentication)
2. [Enhanced Query Capabilities](#enhanced-query-capabilities)
3. [API Endpoints](#api-endpoints)
4. [Query Examples](#query-examples)
5. [Response Formats](#response-formats)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Migration Notes](#migration-notes)

## Authentication

Authentication remains unchanged from the previous version:

```bash
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"question": "What is the current energy generation?"}'
```

## Enhanced Query Capabilities

### Supported Query Languages

The API now supports multiple query approaches:

1. **Natural Language** (Recommended for most users)
2. **Flux Queries** (Advanced users, full InfluxDB capabilities)
3. **InfluxQL** (SQL-like syntax for familiar users)
4. **Hybrid Queries** (Combines natural language with specific parameters)

### Query Translation Engine

The system automatically translates natural language questions into optimized InfluxDB queries:

```json
{
  "question": "Show me the average hydro generation in southeast region for the last week",
  "translation": {
    "query_type": "generation_trend",
    "language": "flux",
    "confidence_score": 0.95,
    "parameters": {
      "time_range": {"start": "-7d", "stop": "now()"},
      "regions": ["southeast"],
      "energy_sources": ["hydro"],
      "aggregation": "mean"
    }
  }
}
```

## API Endpoints

### 1. Natural Language Query Endpoint

**POST** `/query`

Enhanced with InfluxDB-specific capabilities:

```json
{
  "question": "What is the peak demand in northeast region today?",
  "options": {
    "include_raw_query": true,
    "cache_ttl": 300,
    "query_language": "flux"
  }
}
```

**Response:**
```json
{
  "query_id": "uuid-12345",
  "question": "What is the peak demand in northeast region today?",
  "answer": "The peak demand in the northeast region today was 2,450 MW at 14:30.",
  "confidence_score": 0.92,
  "time_series_data": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "measurement": "consumption_data",
      "value": 2450.0,
      "tags": {
        "region": "northeast",
        "measurement_type": "demand_mw"
      }
    }
  ],
  "flux_query_used": "from(bucket: \"energy_data\") |> range(start: today()) |> filter(fn: (r) => r[\"region\"] == \"northeast\") |> max()",
  "sources": [
    {
      "document": "consumption_report_2024.parquet",
      "relevance_score": 0.95,
      "time_range": "2024-01-15T00:00:00Z to 2024-01-15T23:59:59Z"
    }
  ],
  "processing_time_ms": 245,
  "cache_hit": false,
  "timestamp": "2024-01-15T15:00:00Z"
}
```

### 2. Direct Flux Query Endpoint

**POST** `/query/flux`

For advanced users who want to write Flux queries directly:

```json
{
  "query": "from(bucket: \"energy_data\") |> range(start: -24h) |> filter(fn: (r) => r[\"region\"] == \"southeast\") |> aggregateWindow(every: 1h, fn: mean)",
  "options": {
    "format": "json",
    "include_metadata": true
  }
}
```

**Response:**
```json
{
  "query_id": "uuid-67890",
  "query": "from(bucket: \"energy_data\")...",
  "execution_time_ms": 156,
  "result_count": 24,
  "data": [
    {
      "_time": "2024-01-15T00:00:00Z",
      "_value": 1250.5,
      "_field": "power_mw",
      "_measurement": "generation_data",
      "region": "southeast",
      "energy_source": "hydro"
    }
  ],
  "metadata": {
    "columns": ["_time", "_value", "_field", "_measurement", "region", "energy_source"],
    "data_types": ["datetime", "float", "string", "string", "string", "string"],
    "query_cost": 0.0012
  }
}
```

### 3. InfluxQL Query Endpoint

**POST** `/query/influxql`

For users familiar with SQL-like syntax:

```json
{
  "query": "SELECT mean(power_mw) FROM generation_data WHERE region = 'southeast' AND time > now() - 24h GROUP BY time(1h)",
  "database": "energy_data"
}
```

### 4. Enhanced Health Check Endpoint

**GET** `/health`

Now includes InfluxDB-specific health information:

```json
{
  "status": "healthy",
  "service": "ons-data-platform-api",
  "version": "2.0.0-influxdb",
  "timestamp": "2024-01-15T15:00:00Z",
  "components": {
    "api_gateway": "healthy",
    "lambda_functions": "healthy",
    "influxdb": {
      "status": "healthy",
      "response_time_ms": 45.2,
      "connection_pool": {
        "active": 5,
        "idle": 15,
        "max": 20
      },
      "last_write": "2024-01-15T14:59:30Z",
      "data_freshness_minutes": 0.5
    },
    "knowledge_base": "healthy",
    "s3_buckets": "healthy"
  },
  "performance_metrics": {
    "avg_query_time_ms": 234,
    "queries_per_minute": 45,
    "cache_hit_rate": 0.78
  }
}
```

## Query Examples

### Natural Language Examples

#### Energy Generation Queries

```bash
# Current generation by source
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "What is the current energy generation breakdown by source?",
    "options": {"include_raw_query": true}
  }'

# Historical trends
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "Show me the hydro generation trend in the southeast region for the last month",
    "options": {"query_language": "flux"}
  }'

# Peak analysis
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "When was the highest solar generation recorded this year?",
    "options": {"include_metadata": true}
  }'
```

#### Consumption Analysis Queries

```bash
# Regional consumption
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "Compare energy consumption between northeast and southeast regions today"
  }'

# Demand patterns
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "question": "What are the typical daily demand patterns for industrial consumers?"
  }'
```

### Direct Flux Query Examples

#### Time Series Aggregations

```bash
# Hourly averages
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -7d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> aggregateWindow(every: 1h, fn: mean) |> group(columns: [\"region\"])"
  }'

# Complex calculations
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> group(columns: [\"energy_source\"]) |> aggregateWindow(every: 1d, fn: sum) |> derivative(unit: 1d) |> sort(columns: [\"_value\"], desc: true)"
  }'
```

#### Advanced Analytics

```bash
# Capacity factor calculation
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "generation = from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_field\"] == \"power_mw\") capacity = from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_field\"] == \"capacity_mw\") join(tables: {generation: generation, capacity: capacity}, on: [\"_time\", \"plant_name\"]) |> map(fn: (r) => ({r with capacity_factor: r.generation_power_mw / r.capacity_capacity_mw}))"
  }'

# Correlation analysis
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -90d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> pivot(rowKey: [\"_time\"], columnKey: [\"energy_source\"], valueColumn: \"_value\") |> pearsonr(x: \"solar\", y: \"wind\")"
  }'
```

### InfluxQL Examples

```bash
# SQL-like queries for familiar users
curl -X POST "https://api.ons-platform.com/query/influxql" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "SELECT mean(power_mw) FROM generation_data WHERE region = '\''southeast'\'' AND time > now() - 7d GROUP BY time(1h), energy_source",
    "database": "energy_data"
  }'

# Subqueries and joins
curl -X POST "https://api.ons-platform.com/query/influxql" \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "query": "SELECT generation.mean_power, consumption.mean_demand FROM (SELECT mean(power_mw) AS mean_power FROM generation_data WHERE time > now() - 1d GROUP BY time(1h)) AS generation, (SELECT mean(demand_mw) AS mean_demand FROM consumption_data WHERE time > now() - 1d GROUP BY time(1h)) AS consumption",
    "database": "energy_data"
  }'
```

## Response Formats

### Standard Response Structure

All API responses follow this enhanced structure:

```json
{
  "query_id": "string",
  "question": "string",
  "answer": "string",
  "confidence_score": 0.95,
  "time_series_data": [
    {
      "timestamp": "2024-01-15T12:00:00Z",
      "measurement": "string",
      "value": 1234.56,
      "tags": {
        "region": "string",
        "energy_source": "string"
      },
      "fields": {
        "power_mw": 1234.56,
        "capacity_factor": 0.85
      }
    }
  ],
  "query_metadata": {
    "query_language": "flux",
    "query_used": "string",
    "execution_time_ms": 245,
    "result_count": 100,
    "cache_hit": false,
    "query_cost": 0.0012
  },
  "sources": [
    {
      "document": "string",
      "relevance_score": 0.92,
      "time_range": "string",
      "data_points": 1000
    }
  ],
  "performance_info": {
    "processing_time_ms": 245,
    "influxdb_query_time_ms": 156,
    "knowledge_base_time_ms": 89,
    "total_data_points": 1000
  },
  "timestamp": "2024-01-15T12:00:00Z"
}
```

### Time Series Data Format

Enhanced time series data includes more metadata:

```json
{
  "timestamp": "2024-01-15T12:00:00Z",
  "measurement": "generation_data",
  "value": 1234.56,
  "tags": {
    "region": "southeast",
    "energy_source": "hydro",
    "plant_name": "itaipu",
    "operator": "ons"
  },
  "fields": {
    "power_mw": 1234.56,
    "capacity_mw": 2000.0,
    "efficiency": 0.85,
    "availability": 0.98
  },
  "quality": {
    "flag": "good",
    "confidence": 0.95,
    "source": "sensor"
  }
}
```

## Error Handling

### Enhanced Error Responses

Error responses now include InfluxDB-specific error information:

```json
{
  "error": {
    "code": "INFLUXDB_QUERY_ERROR",
    "message": "Query execution failed",
    "details": {
      "influxdb_error": "syntax error: unexpected token",
      "query_line": 2,
      "query_position": 45,
      "suggested_fix": "Check filter syntax"
    },
    "timestamp": "2024-01-15T12:00:00Z",
    "query_id": "uuid-12345"
  },
  "status_code": 400
}
```

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `INFLUXDB_CONNECTION_ERROR` | Cannot connect to InfluxDB | Check service status |
| `INFLUXDB_QUERY_TIMEOUT` | Query execution timeout | Optimize query or increase timeout |
| `INFLUXDB_SYNTAX_ERROR` | Invalid Flux/InfluxQL syntax | Check query syntax |
| `INFLUXDB_PERMISSION_ERROR` | Insufficient permissions | Check authentication |
| `QUERY_TRANSLATION_ERROR` | Cannot translate natural language | Rephrase question |
| `DATA_NOT_FOUND` | No data matches query criteria | Check time range and filters |

## Rate Limiting

### Enhanced Rate Limits

Rate limits are now based on query complexity:

| Query Type | Requests/Minute | Burst Limit |
|------------|-----------------|-------------|
| Natural Language | 60 | 10 |
| Simple Flux | 120 | 20 |
| Complex Flux | 30 | 5 |
| InfluxQL | 90 | 15 |

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248000
X-RateLimit-Query-Cost: 1.5
```

## Migration Notes

### Backward Compatibility

The API maintains backward compatibility with existing clients:

- All existing endpoints continue to work
- Response formats are enhanced but not breaking
- Natural language queries are automatically optimized for InfluxDB

### New Capabilities

Enhanced capabilities available after migration:

1. **Advanced Time Series Functions**: Window functions, derivatives, correlations
2. **Better Performance**: Optimized queries with caching
3. **Flexible Query Languages**: Flux, InfluxQL, and natural language
4. **Enhanced Metadata**: Richer data context and quality information
5. **Real-time Analytics**: Streaming queries and live dashboards

### Performance Improvements

| Metric | Before (Timestream) | After (InfluxDB) | Improvement |
|--------|-------------------|------------------|-------------|
| Simple Queries | 500ms avg | 200ms avg | 60% faster |
| Complex Aggregations | 2000ms avg | 800ms avg | 60% faster |
| Concurrent Queries | 10 QPS | 25 QPS | 150% increase |
| Data Freshness | 5 minutes | 30 seconds | 90% improvement |

### Migration Checklist for API Users

- [ ] Test existing queries with new API
- [ ] Update error handling for new error codes
- [ ] Leverage new query capabilities (Flux/InfluxQL)
- [ ] Update monitoring for new performance metrics
- [ ] Consider using query caching for better performance

## Support and Resources

### Documentation Links

- [Flux Query Language Guide](https://docs.influxdata.com/flux/)
- [InfluxQL Reference](https://docs.influxdata.com/influxdb/v1.8/query_language/)
- [Natural Language Query Examples](./query-examples.md)

### Getting Help

- **API Issues**: api-support@ons-platform.com
- **Query Optimization**: query-help@ons-platform.com
- **Migration Support**: migration-support@ons-platform.com

---

**Last Updated**: $(date)
**API Version**: 2.0.0-influxdb
**Next Review**: $(date -d '+1 month')