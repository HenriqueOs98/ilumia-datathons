# Documentação da API - Plataforma de Dados ONS - Edição InfluxDB

## Visão Geral

Este documento descreve as capacidades atualizadas da API após a migração do Amazon Timestream para Amazon Timestream for InfluxDB. A API agora suporta capacidades de consulta aprimoradas incluindo linguagens de consulta InfluxQL e Flux, mantendo compatibilidade com versões anteriores.

## Índice

1. [Autenticação](#autenticação)
2. [Capacidades de Consulta Aprimoradas](#capacidades-de-consulta-aprimoradas)
3. [Endpoints da API](#endpoints-da-api)
4. [Exemplos de Consultas](#exemplos-de-consultas)
5. [Formatos de Resposta](#formatos-de-resposta)
6. [Tratamento de Erros](#tratamento-de-erros)
7. [Limitação de Taxa](#limitação-de-taxa)
8. [Notas de Migração](#notas-de-migração)

## Autenticação

A autenticação permanece inalterada da versão anterior:

```bash
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{"question": "Qual é a geração de energia atual?"}'
```

## Capacidades de Consulta Aprimoradas

### Linguagens de Consulta Suportadas

A API agora suporta múltiplas abordagens de consulta:

1. **Linguagem Natural** (Recomendado para a maioria dos usuários)
2. **Consultas Flux** (Usuários avançados, capacidades completas do InfluxDB)
3. **InfluxQL** (Sintaxe similar ao SQL para usuários familiarizados)
4. **Consultas Híbridas** (Combina linguagem natural com parâmetros específicos)

### Motor de Tradução de Consultas

O sistema traduz automaticamente perguntas em linguagem natural para consultas InfluxDB otimizadas:

```json
{
  "question": "Mostre-me a geração hidrelétrica média na região sudeste na última semana",
  "translation": {
    "query_type": "generation_trend",
    "language": "flux",
    "confidence_score": 0.95,
    "parameters": {
      "time_range": {"start": "-7d", "stop": "now()"},
      "regions": ["sudeste"],
      "energy_sources": ["hidrica"],
      "aggregation": "mean"
    }
  }
}
```

## Endpoints da API

### 1. Endpoint de Consulta em Linguagem Natural

**POST** `/query`

Aprimorado com capacidades específicas do InfluxDB:

```json
{
  "question": "Qual é o pico de demanda na região nordeste hoje?",
  "options": {
    "include_raw_query": true,
    "cache_ttl": 300,
    "query_language": "flux"
  }
}
```

**Resposta:**
```json
{
  "query_id": "uuid-12345",
  "question": "Qual é o pico de demanda na região nordeste hoje?",
  "answer": "O pico de demanda na região nordeste hoje foi de 2.450 MW às 14:30.",
  "confidence_score": 0.92,
  "time_series_data": [
    {
      "timestamp": "2024-01-15T14:30:00Z",
      "measurement": "consumption_data",
      "value": 2450.0,
      "tags": {
        "region": "nordeste",
        "measurement_type": "demand_mw"
      }
    }
  ],
  "flux_query_used": "from(bucket: \"energy_data\") |> range(start: today()) |> filter(fn: (r) => r[\"region\"] == \"nordeste\") |> max()",
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

### 2. Endpoint de Consulta Flux Direta

**POST** `/query/flux`

Para usuários avançados que querem escrever consultas Flux diretamente:

```json
{
  "query": "from(bucket: \"energy_data\") |> range(start: -24h) |> filter(fn: (r) => r[\"region\"] == \"sudeste\") |> aggregateWindow(every: 1h, fn: mean)",
  "options": {
    "format": "json",
    "include_metadata": true
  }
}
```

**Resposta:**
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
      "region": "sudeste",
      "energy_source": "hidrica"
    }
  ],
  "metadata": {
    "columns": ["_time", "_value", "_field", "_measurement", "region", "energy_source"],
    "data_types": ["datetime", "float", "string", "string", "string", "string"],
    "query_cost": 0.0012
  }
}
```

### 3. Endpoint de Consulta InfluxQL

**POST** `/query/influxql`

Para usuários familiarizados com sintaxe similar ao SQL:

```json
{
  "query": "SELECT mean(power_mw) FROM generation_data WHERE region = 'sudeste' AND time > now() - 24h GROUP BY time(1h)",
  "database": "energy_data"
}
```

### 4. Endpoint de Verificação de Saúde Aprimorado

**GET** `/health`

Agora inclui informações específicas de saúde do InfluxDB:

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

## Exemplos de Consultas

### Exemplos em Linguagem Natural

#### Consultas de Geração de Energia

```bash
# Geração atual por fonte
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Qual é a distribuição atual de geração de energia por fonte?",
    "options": {"include_raw_query": true}
  }'

# Tendências históricas
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Mostre-me a tendência de geração hidrelétrica na região sudeste no último mês",
    "options": {"query_language": "flux"}
  }'

# Análise de picos
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Quando foi registrada a maior geração solar este ano?",
    "options": {"include_metadata": true}
  }'
```

#### Consultas de Análise de Consumo

```bash
# Consumo regional
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Compare o consumo de energia entre as regiões nordeste e sudeste hoje"
  }'

# Padrões de demanda
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Quais são os padrões típicos de demanda diária para consumidores industriais?"
  }'
```

### Exemplos de Consultas Flux Diretas

#### Agregações de Séries Temporais

```bash
# Médias horárias
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -7d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> aggregateWindow(every: 1h, fn: mean) |> group(columns: [\"region\"])"
  }'

# Cálculos complexos
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> group(columns: [\"energy_source\"]) |> aggregateWindow(every: 1d, fn: sum) |> derivative(unit: 1d) |> sort(columns: [\"_value\"], desc: true)"
  }'
```

#### Análises Avançadas

```bash
# Cálculo de fator de capacidade
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "generation = from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_field\"] == \"power_mw\") capacity = from(bucket: \"energy_data\") |> range(start: -30d) |> filter(fn: (r) => r[\"_field\"] == \"capacity_mw\") join(tables: {generation: generation, capacity: capacity}, on: [\"_time\", \"plant_name\"]) |> map(fn: (r) => ({r with capacity_factor: r.generation_power_mw / r.capacity_capacity_mw}))"
  }'

# Análise de correlação
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -90d) |> filter(fn: (r) => r[\"_measurement\"] == \"generation_data\") |> pivot(rowKey: [\"_time\"], columnKey: [\"energy_source\"], valueColumn: \"_value\") |> pearsonr(x: \"solar\", y: \"eolica\")"
  }'
```

### Exemplos InfluxQL

```bash
# Consultas similares ao SQL para usuários familiarizados
curl -X POST "https://api.ons-platform.com/query/influxql" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "SELECT mean(power_mw) FROM generation_data WHERE region = '\''sudeste'\'' AND time > now() - 7d GROUP BY time(1h), energy_source",
    "database": "energy_data"
  }'

# Subconsultas e joins
curl -X POST "https://api.ons-platform.com/query/influxql" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "SELECT generation.mean_power, consumption.mean_demand FROM (SELECT mean(power_mw) AS mean_power FROM generation_data WHERE time > now() - 1d GROUP BY time(1h)) AS generation, (SELECT mean(demand_mw) AS mean_demand FROM consumption_data WHERE time > now() - 1d GROUP BY time(1h)) AS consumption",
    "database": "energy_data"
  }'
```

## Formatos de Resposta

### Estrutura de Resposta Padrão

Todas as respostas da API seguem esta estrutura aprimorada:

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

### Formato de Dados de Séries Temporais

Dados de séries temporais aprimorados incluem mais metadados:

```json
{
  "timestamp": "2024-01-15T12:00:00Z",
  "measurement": "generation_data",
  "value": 1234.56,
  "tags": {
    "region": "sudeste",
    "energy_source": "hidrica",
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

## Tratamento de Erros

### Respostas de Erro Aprimoradas

Respostas de erro agora incluem informações específicas de erro do InfluxDB:

```json
{
  "error": {
    "code": "INFLUXDB_QUERY_ERROR",
    "message": "Falha na execução da consulta",
    "details": {
      "influxdb_error": "erro de sintaxe: token inesperado",
      "query_line": 2,
      "query_position": 45,
      "suggested_fix": "Verificar sintaxe do filtro"
    },
    "timestamp": "2024-01-15T12:00:00Z",
    "query_id": "uuid-12345"
  },
  "status_code": 400
}
```

### Códigos de Erro Comuns

| Código | Descrição | Solução |
|--------|-----------|---------|
| `INFLUXDB_CONNECTION_ERROR` | Não é possível conectar ao InfluxDB | Verificar status do serviço |
| `INFLUXDB_QUERY_TIMEOUT` | Timeout na execução da consulta | Otimizar consulta ou aumentar timeout |
| `INFLUXDB_SYNTAX_ERROR` | Sintaxe inválida Flux/InfluxQL | Verificar sintaxe da consulta |
| `INFLUXDB_PERMISSION_ERROR` | Permissões insuficientes | Verificar autenticação |
| `QUERY_TRANSLATION_ERROR` | Não é possível traduzir linguagem natural | Reformular pergunta |
| `DATA_NOT_FOUND` | Nenhum dado corresponde aos critérios da consulta | Verificar intervalo de tempo e filtros |

## Limitação de Taxa

### Limites de Taxa Aprimorados

Os limites de taxa agora são baseados na complexidade da consulta:

| Tipo de Consulta | Requisições/Minuto | Limite de Rajada |
|------------------|-------------------|------------------|
| Linguagem Natural | 60 | 10 |
| Flux Simples | 120 | 20 |
| Flux Complexo | 30 | 5 |
| InfluxQL | 90 | 15 |

### Cabeçalhos de Limite de Taxa

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642248000
X-RateLimit-Query-Cost: 1.5
```

## Notas de Migração

### Compatibilidade com Versões Anteriores

A API mantém compatibilidade com clientes existentes:

- Todos os endpoints existentes continuam funcionando
- Formatos de resposta são aprimorados mas não quebram compatibilidade
- Consultas em linguagem natural são automaticamente otimizadas para InfluxDB

### Novas Capacidades

Capacidades aprimoradas disponíveis após a migração:

1. **Funções Avançadas de Séries Temporais**: Funções de janela, derivadas, correlações
2. **Melhor Performance**: Consultas otimizadas com cache
3. **Linguagens de Consulta Flexíveis**: Flux, InfluxQL e linguagem natural
4. **Metadados Aprimorados**: Contexto de dados mais rico e informações de qualidade
5. **Análises em Tempo Real**: Consultas de streaming e dashboards ao vivo

### Melhorias de Performance

| Métrica | Antes (Timestream) | Depois (InfluxDB) | Melhoria |
|---------|-------------------|------------------|----------|
| Consultas Simples | 500ms média | 200ms média | 60% mais rápido |
| Agregações Complexas | 2000ms média | 800ms média | 60% mais rápido |
| Consultas Concorrentes | 10 QPS | 25 QPS | 150% de aumento |
| Atualização de Dados | 5 minutos | 30 segundos | 90% de melhoria |

### Lista de Verificação de Migração para Usuários da API

- [ ] Testar consultas existentes com nova API
- [ ] Atualizar tratamento de erros para novos códigos de erro
- [ ] Aproveitar novas capacidades de consulta (Flux/InfluxQL)
- [ ] Atualizar monitoramento para novas métricas de performance
- [ ] Considerar usar cache de consultas para melhor performance

## Suporte e Recursos

### Links de Documentação

- [Guia da Linguagem de Consulta Flux](https://docs.influxdata.com/flux/)
- [Referência InfluxQL](https://docs.influxdata.com/influxdb/v1.8/query_language/)
- [Exemplos de Consultas em Linguagem Natural](./exemplos-consultas.md)

### Obtendo Ajuda

- **Problemas da API**: api-support@ons-platform.com
- **Otimização de Consultas**: query-help@ons-platform.com
- **Suporte de Migração**: migration-support@ons-platform.com

---

**Última Atualização**: $(date)
**Versão da API**: 2.0.0-influxdb
**Próxima Revisão**: $(date -d '+1 month')