# Manual de Operações InfluxDB

## Visão Geral

Este manual fornece procedimentos operacionais específicos para gerenciar a instância Amazon Timestream for InfluxDB usada na Plataforma de Dados ONS após a migração do Amazon Timestream regular.

## Índice

1. [Monitoramento de Saúde do InfluxDB](#monitoramento-de-saúde-do-influxdb)
2. [Otimização de Performance](#otimização-de-performance)
3. [Gestão de Dados](#gestão-de-dados)
4. [Otimização de Consultas](#otimização-de-consultas)
5. [Backup e Recuperação](#backup-e-recuperação)
6. [Solução de Problemas](#solução-de-problemas)
7. [Procedimentos de Manutenção](#procedimentos-de-manutenção)
8. [Monitoramento e Alertas](#monitoramento-e-alertas)

## Monitoramento de Saúde do InfluxDB

### Verificações Diárias de Saúde

```bash
#!/bin/bash
# Verificação Diária de Saúde do InfluxDB

echo "=== Verificação de Saúde do InfluxDB ==="
echo "Data: $(date)"
echo

# 1. Verificar status da instância do banco
echo "1. Status da Instância do Banco:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[DbInstanceStatus,DbInstanceClass,AllocatedStorage,AvailabilityZone]' \
  --output table

# 2. Verificar conectividade e tempo de resposta
echo "2. Teste de Conectividade:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import time
handler = InfluxDBHandler()
start = time.time()
health = handler.health_check()
response_time = (time.time() - start) * 1000
print(f'Status: {health[\"status\"]}')
print(f'Tempo de Resposta: {response_time:.2f}ms')
print(f'Pool de Conexões: {health.get(\"connection_pool_active\", \"N/A\")} ativas, {health.get(\"connection_pool_idle\", \"N/A\")} inativas')
"

# 3. Verificar ingestão de dados recente
echo "3. Ingestão de Dados Recente:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()
query = '''
from(bucket: \"energy_data\")
  |> range(start: -1h)
  |> count()
'''
result = handler.query_flux(query)
print(f'Registros na última hora: {len(result)}')
"

# 4. Verificar performance das consultas
echo "4. Teste de Performance de Consultas:"
python scripts/validate_influxdb_performance.py --quick-test

# 5. Verificar métricas do CloudWatch
echo "5. Métricas do CloudWatch:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_ResponseTime \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average,Maximum \
  --query 'Datapoints[0].[Average,Maximum]' --output text

echo "=== Verificação de Saúde Completa ==="
```

### Revisão Semanal de Performance

```bash
#!/bin/bash
# Revisão Semanal de Performance do InfluxDB

echo "=== Revisão Semanal de Performance do InfluxDB ==="

# 1. Tendências de performance de consultas (últimos 7 dias)
echo "1. Tendências de Performance de Consultas (Últimos 7 Dias):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_QueryLatency \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 86400 \
  --statistics Average,Maximum \
  --query 'Datapoints[*].[Timestamp,Average,Maximum]' --output table

# 2. Análise de throughput de escrita
echo "2. Análise de Throughput de Escrita:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_WritePoints \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 86400 \
  --statistics Sum \
  --query 'Datapoints[*].[Timestamp,Sum]' --output table

# 3. Utilização de armazenamento
echo "3. Utilização de Armazenamento:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[AllocatedStorage,StorageEncrypted,StorageType]' --output table

# 4. Análise do pool de conexões
echo "4. Análise do Pool de Conexões:"
python -c "
from src.influxdb_monitor.lambda_function import lambda_handler
import json
result = lambda_handler({'source': 'manual'}, {})
metrics = json.loads(result['body'])['metrics']
print(f'Conexões Ativas: {metrics.get(\"connection_pool_active\", \"N/A\")}')
print(f'Conexões Inativas: {metrics.get(\"connection_pool_idle\", \"N/A\")}')
print(f'Tempo Médio de Resposta: {metrics.get(\"response_time_ms\", \"N/A\")}ms')
"

# 5. Análise de taxa de erro
echo "5. Análise de Taxa de Erro:"
aws logs filter-log-events \
  --log-group-name /aws/lambda/influxdb_loader \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'length(events)' --output text
```

## Otimização de Performance

### Otimização de Performance de Consultas

1. **Analisar Consultas Lentas:**
```python
# Criar analisador de performance de consultas
def analyze_query_performance():
    """Analisar e otimizar consultas lentas"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import time
    
    handler = InfluxDBHandler()
    
    # Testar consultas com diferentes padrões
    test_queries = [
        {
            'name': 'Filtro Simples',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -1h)
                |> filter(fn: (r) => r["region"] == "sudeste")
            '''
        },
        {
            'name': 'Agregação',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -1d)
                |> aggregateWindow(every: 1h, fn: mean)
            '''
        },
        {
            'name': 'Agrupamento Complexo',
            'query': '''
                from(bucket: "energy_data")
                |> range(start: -7d)
                |> group(columns: ["region", "energy_source"])
                |> aggregateWindow(every: 6h, fn: mean)
            '''
        }
    ]
    
    results = []
    for test in test_queries:
        start_time = time.time()
        try:
            result = handler.query_flux(test['query'])
            execution_time = (time.time() - start_time) * 1000
            results.append({
                'name': test['name'],
                'execution_time_ms': execution_time,
                'result_count': len(result),
                'status': 'sucesso'
            })
        except Exception as e:
            results.append({
                'name': test['name'],
                'execution_time_ms': 0,
                'result_count': 0,
                'status': f'erro: {str(e)}'
            })
    
    return results

# Executar análise
performance_results = analyze_query_performance()
for result in performance_results:
    print(f"{result['name']}: {result['execution_time_ms']:.2f}ms ({result['status']})")
```

2. **Otimizar Schema de Dados:**
```python
def optimize_data_schema():
    """Otimizar schema de dados do InfluxDB para melhor performance"""
    
    # Recomendações de otimização de schema:
    schema_recommendations = {
        'tags': [
            'region',           # Baixa cardinalidade (5 regiões)
            'energy_source',    # Média cardinalidade (~10 fontes)
            'plant_name'        # Alta cardinalidade (mas necessária para consultas)
        ],
        'fields': [
            'power_mw',         # Medição numérica
            'capacity_mw',      # Medição numérica
            'efficiency',       # Medição numérica
            'availability'      # Medição numérica
        ],
        'timestamp': 'time'     # Usar timestamp nativo do InfluxDB
    }
    
    # Análise de cardinalidade
    print("Recomendações de Otimização de Schema:")
    print("=====================================")
    print("Tags (indexadas, cardinalidade baixa preferida):")
    for tag in schema_recommendations['tags']:
        print(f"  - {tag}")
    
    print("\nFields (não indexados, cardinalidade alta OK):")
    for field in schema_recommendations['fields']:
        print(f"  - {field}")
    
    return schema_recommendations
```

### Otimização de Performance de Escrita

1. **Otimização de Escrita em Lote:**
```python
def optimize_batch_writes():
    """Otimizar performance de escrita em lote"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    from influxdb_client import Point
    import time
    
    handler = InfluxDBHandler()
    
    # Testar diferentes tamanhos de lote
    batch_sizes = [100, 500, 1000, 2000]
    results = {}
    
    for batch_size in batch_sizes:
        # Criar pontos de teste
        points = []
        for i in range(batch_size):
            point = Point("performance_test") \
                .tag("region", f"region_{i % 5}") \
                .tag("source", f"source_{i % 3}") \
                .field("value", float(i)) \
                .time(time.time_ns() + i * 1000000)  # Precisão de nanossegundo
            points.append(point)
        
        # Medir performance de escrita
        start_time = time.time()
        try:
            handler.write_points(points, batch_size=batch_size)
            write_time = (time.time() - start_time) * 1000
            throughput = batch_size / (write_time / 1000)
            
            results[batch_size] = {
                'write_time_ms': write_time,
                'throughput_points_per_sec': throughput,
                'status': 'sucesso'
            }
        except Exception as e:
            results[batch_size] = {
                'write_time_ms': 0,
                'throughput_points_per_sec': 0,
                'status': f'erro: {str(e)}'
            }
    
    # Encontrar tamanho de lote ótimo
    optimal_batch_size = max(
        [k for k, v in results.items() if v['status'] == 'sucesso'],
        key=lambda k: results[k]['throughput_points_per_sec']
    )
    
    print("Resultados de Performance de Escrita em Lote:")
    print("============================================")
    for batch_size, result in results.items():
        print(f"Tamanho do Lote {batch_size}: {result['throughput_points_per_sec']:.2f} pontos/seg ({result['status']})")
    
    print(f"\nTamanho de lote ótimo: {optimal_batch_size}")
    return optimal_batch_size
```

## Gestão de Dados

### Gestão de Políticas de Retenção

```bash
#!/bin/bash
# Gerenciar políticas de retenção do InfluxDB

# Verificar configurações de retenção atuais
echo "Políticas de Retenção Atuais:"
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()

# Consultar informações do bucket
query = '''
buckets()
  |> filter(fn: (r) => r.name == \"energy_data\")
  |> yield()
'''

result = handler.query_flux(query)
for bucket in result:
    print(f'Bucket: {bucket.get(\"name\", \"N/A\")}')
    print(f'Período de Retenção: {bucket.get(\"retentionPeriod\", \"N/A\")}')
    print(f'Organização: {bucket.get(\"orgID\", \"N/A\")}')
"

# Atualizar política de retenção se necessário
update_retention_policy() {
    local bucket_name=$1
    local retention_period=$2
    
    echo "Atualizando política de retenção para bucket: $bucket_name"
    echo "Novo período de retenção: $retention_period"
    
    python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()

# Nota: Atualizações de política de retenção dependem da versão e configuração do InfluxDB
# Este é um placeholder para a implementação real
print('Atualização de política de retenção seria implementada aqui')
print('Bucket: $bucket_name')
print('Retenção: $retention_period')
"
}

# Exemplo de uso
# update_retention_policy "energy_data" "2555d"  # ~7 anos
```

### Limpeza e Arquivamento de Dados

```python
def cleanup_old_data():
    """Limpar dados antigos baseado em políticas de retenção"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    from datetime import datetime, timedelta
    
    handler = InfluxDBHandler()
    
    # Definir limites de limpeza
    cleanup_thresholds = {
        'test_data': timedelta(days=7),      # Dados de teste mantidos por 1 semana
        'debug_data': timedelta(days=30),    # Dados de debug mantidos por 1 mês
        'temp_data': timedelta(days=1)       # Dados temporários mantidos por 1 dia
    }
    
    for measurement, threshold in cleanup_thresholds.items():
        cutoff_time = datetime.utcnow() - threshold
        
        # Deletar dados antigos
        delete_query = f'''
        from(bucket: "energy_data")
          |> range(start: 1970-01-01T00:00:00Z, stop: {cutoff_time.isoformat()}Z)
          |> filter(fn: (r) => r["_measurement"] == "{measurement}")
          |> drop()
        '''
        
        try:
            result = handler.query_flux(delete_query)
            print(f"Limpeza de dados {measurement} mais antigos que {threshold}")
        except Exception as e:
            print(f"Falha ao limpar {measurement}: {str(e)}")

def archive_historical_data():
    """Arquivar dados históricos para S3 para armazenamento de longo prazo"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import boto3
    import json
    from datetime import datetime, timedelta
    
    handler = InfluxDBHandler()
    s3_client = boto3.client('s3')
    
    # Arquivar dados com mais de 1 ano
    archive_cutoff = datetime.utcnow() - timedelta(days=365)
    
    # Consultar dados históricos
    archive_query = f'''
    from(bucket: "energy_data")
      |> range(start: 1970-01-01T00:00:00Z, stop: {archive_cutoff.isoformat()}Z)
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    try:
        historical_data = handler.query_flux(archive_query)
        
        # Converter para JSON para arquivamento
        archive_data = {
            'archived_at': datetime.utcnow().isoformat(),
            'data_count': len(historical_data),
            'data': historical_data
        }
        
        # Upload para S3
        archive_key = f"archives/influxdb_archive_{archive_cutoff.strftime('%Y%m%d')}.json"
        s3_client.put_object(
            Bucket='ons-data-platform-archives',
            Key=archive_key,
            Body=json.dumps(archive_data, default=str),
            StorageClass='GLACIER'
        )
        
        print(f"Arquivados {len(historical_data)} registros para s3://ons-data-platform-archives/{archive_key}")
        
    except Exception as e:
        print(f"Falha ao arquivar dados históricos: {str(e)}")
```

## Otimização de Consultas

### Melhores Práticas de Performance de Consultas

1. **Otimização de Intervalo de Tempo:**
```flux
// Bom: Intervalo de tempo específico
from(bucket: "energy_data")
  |> range(start: -24h, stop: now())
  |> filter(fn: (r) => r["region"] == "sudeste")

// Ruim: Sem intervalo de tempo (escaneia todos os dados)
from(bucket: "energy_data")
  |> filter(fn: (r) => r["region"] == "sudeste")
```

2. **Otimização de Filtros:**
```flux
// Bom: Filtrar cedo e usar tags indexadas
from(bucket: "energy_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["region"] == "sudeste")
  |> filter(fn: (r) => r["energy_source"] == "hidrica")
  |> filter(fn: (r) => r["_field"] == "power_mw")

// Ruim: Filtrar tarde e usar campos não indexados
from(bucket: "energy_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_value"] > 1000.0)
  |> filter(fn: (r) => r["region"] == "sudeste")
```

3. **Otimização de Agregação:**
```flux
// Bom: Usar tamanhos de janela apropriados
from(bucket: "energy_data")
  |> range(start: -7d)
  |> aggregateWindow(every: 1h, fn: mean)
  |> group(columns: ["region"])

// Ruim: Agregação muito granular para intervalos grandes
from(bucket: "energy_data")
  |> range(start: -30d)
  |> aggregateWindow(every: 1m, fn: mean)  // Muitos pontos
```

### Implementação de Cache de Consultas

```python
def implement_query_caching():
    """Implementar cache de resultados de consultas para melhor performance"""
    import redis
    import json
    import hashlib
    from src.shared_utils.influxdb_client import InfluxDBHandler
    
    # Inicializar cliente Redis
    redis_client = redis.Redis(
        host='ons-elasticache-cluster.cache.amazonaws.com',
        port=6379,
        decode_responses=True
    )
    
    class CachedInfluxDBHandler(InfluxDBHandler):
        def __init__(self, cache_ttl=300):  # TTL padrão de 5 minutos
            super().__init__()
            self.cache_ttl = cache_ttl
        
        def query_flux_cached(self, query, cache_ttl=None):
            """Executar consulta Flux com cache"""
            # Gerar chave de cache
            cache_key = f"influxdb_query:{hashlib.md5(query.encode()).hexdigest()}"
            
            # Verificar cache primeiro
            try:
                cached_result = redis_client.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)
            except Exception as e:
                print(f"Erro de leitura do cache: {e}")
            
            # Executar consulta
            result = self.query_flux(query)
            
            # Cachear resultado
            try:
                ttl = cache_ttl or self.cache_ttl
                redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, default=str)
                )
            except Exception as e:
                print(f"Erro de escrita do cache: {e}")
            
            return result
        
        def invalidate_cache_pattern(self, pattern):
            """Invalidar entradas de cache que correspondem ao padrão"""
            try:
                keys = redis_client.keys(f"influxdb_query:*{pattern}*")
                if keys:
                    redis_client.delete(*keys)
                    print(f"Invalidadas {len(keys)} entradas de cache")
            except Exception as e:
                print(f"Erro de invalidação de cache: {e}")
    
    return CachedInfluxDBHandler
```

## Backup e Recuperação

### Procedimentos de Backup Automatizado

```bash
#!/bin/bash
# Script de Backup do InfluxDB

BACKUP_BUCKET="ons-data-platform-backups"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PREFIX="influxdb_backup_${BACKUP_DATE}"

echo "Iniciando backup do InfluxDB: $BACKUP_PREFIX"

# 1. Exportar dados para S3
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import boto3
import json
from datetime import datetime, timedelta

handler = InfluxDBHandler()
s3_client = boto3.client('s3')

# Exportar dados recentes (últimos 30 dias)
export_query = '''
from(bucket: \"energy_data\")
  |> range(start: -30d)
  |> pivot(rowKey:[\"_time\"], columnKey: [\"_field\"], valueColumn: \"_value\")
'''

try:
    data = handler.query_flux(export_query)
    
    backup_data = {
        'backup_timestamp': datetime.utcnow().isoformat(),
        'data_count': len(data),
        'data': data
    }
    
    # Upload para S3
    s3_client.put_object(
        Bucket='$BACKUP_BUCKET',
        Key='$BACKUP_PREFIX/data_export.json',
        Body=json.dumps(backup_data, default=str)
    )
    
    print(f'Backup de {len(data)} registros para S3')
    
except Exception as e:
    print(f'Backup falhou: {str(e)}')
    exit(1)
"

# 2. Backup da configuração
echo "Fazendo backup da configuração do InfluxDB..."
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod > "/tmp/influxdb_config_${BACKUP_DATE}.json"

aws s3 cp "/tmp/influxdb_config_${BACKUP_DATE}.json" \
  "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/configuration.json"

# 3. Criar snapshot se suportado
echo "Criando snapshot do banco de dados..."
aws timestreaminfluxdb create-db-snapshot \
  --db-instance-identifier ons-influxdb-prod \
  --db-snapshot-identifier "ons-influxdb-snapshot-${BACKUP_DATE}" \
  --tags Key=BackupDate,Value=$BACKUP_DATE Key=Environment,Value=prod

echo "Backup concluído: $BACKUP_PREFIX"

# 4. Limpeza de backups antigos (manter últimos 30 dias)
aws s3 ls "s3://${BACKUP_BUCKET}/" --recursive | \
  awk '{print $4}' | \
  grep "influxdb_backup_" | \
  head -n -30 | \
  xargs -I {} aws s3 rm "s3://${BACKUP_BUCKET}/{}"
```

### Procedimentos de Recuperação de Desastre

```bash
#!/bin/bash
# Script de Recuperação de Desastre do InfluxDB

restore_from_backup() {
    local backup_date=$1
    local backup_bucket="ons-data-platform-backups"
    local backup_prefix="influxdb_backup_${backup_date}"
    
    echo "Iniciando recuperação de desastre do backup: $backup_prefix"
    
    # 1. Parar ingestão de dados
    echo "Parando ingestão de dados..."
    aws events disable-rule --name ons-data-platform-s3-processing-rule
    
    # 2. Criar nova instância InfluxDB a partir do snapshot
    echo "Criando nova instância InfluxDB a partir do snapshot..."
    aws timestreaminfluxdb restore-db-instance-from-db-snapshot \
      --db-instance-identifier ons-influxdb-recovery \
      --db-snapshot-identifier "ons-influxdb-snapshot-${backup_date}" \
      --db-instance-class db.influx.large
    
    # Aguardar instância ficar disponível
    echo "Aguardando instância ficar disponível..."
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier ons-influxdb-recovery
    
    # 3. Atualizar funções Lambda para usar nova instância
    echo "Atualizando funções Lambda..."
    for func in influxdb_loader timeseries_query_processor rag_query_processor; do
        aws lambda update-function-configuration \
          --function-name $func \
          --environment Variables="{INFLUXDB_ENDPOINT=$(aws timestreaminfluxdb describe-db-instance --identifier ons-influxdb-recovery --query 'DbInstance.Endpoint' --output text)}"
    done
    
    # 4. Restaurar dados do backup S3
    echo "Restaurando dados do backup S3..."
    python -c "
import boto3
import json
from src.shared_utils.influxdb_client import InfluxDBHandler
from influxdb_client import Point

s3_client = boto3.client('s3')
handler = InfluxDBHandler()

# Baixar dados de backup
response = s3_client.get_object(
    Bucket='$backup_bucket',
    Key='$backup_prefix/data_export.json'
)

backup_data = json.loads(response['Body'].read())
data_points = backup_data['data']

# Converter para pontos InfluxDB
points = []
for record in data_points:
    point = Point('restored_data')
    
    # Adicionar tags
    for key, value in record.items():
        if key.startswith('tag_'):
            point = point.tag(key[4:], str(value))
        elif key.startswith('field_'):
            point = point.field(key[6:], float(value))
        elif key == '_time':
            point = point.time(value)

    points.append(point)

# Escrever para InfluxDB
handler.write_points(points, batch_size=1000)
print(f'Restaurados {len(points)} pontos de dados')
"
    
    # 5. Validar recuperação
    echo "Validando recuperação..."
    python scripts/validate_influxdb_performance.py --health-check-only
    
    # 6. Alternar tráfego para instância recuperada
    echo "Alternando tráfego para instância recuperada..."
    # Atualizar configuração Terraform ou usar implantação blue-green
    
    echo "Recuperação de desastre concluída com sucesso"
}

# Uso: restore_from_backup "20241201_120000"
```

## Solução de Problemas

### Problemas Comuns do InfluxDB

#### Timeouts de Conexão

**Sintomas:**
- Funções Lambda com timeout
- Erros de conexão recusada
- Problemas de conectividade intermitentes

**Diagnóstico:**
```bash
# Verificar status da instância
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text

# Testar conectividade
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
import time

handler = InfluxDBHandler()
start_time = time.time()
try:
    health = handler.health_check()
    response_time = (time.time() - start_time) * 1000
    print(f'Conexão bem-sucedida: {response_time:.2f}ms')
    print(f'Status: {health}')
except Exception as e:
    print(f'Conexão falhou: {str(e)}')
"

# Verificar grupos de segurança
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=ons-influxdb-sg \
  --query 'SecurityGroups[*].IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[*].CidrIp]' \
  --output table
```

**Soluções:**
1. **Aumentar timeout de conexão:**
```python
# Atualizar configuração do cliente InfluxDB
from influxdb_client import InfluxDBClient

client = InfluxDBClient(
    url=influxdb_url,
    token=influxdb_token,
    org=influxdb_org,
    timeout=30000  # 30 segundos
)
```

2. **Otimizar pool de conexões:**
```python
# Configurar pool de conexões
client = InfluxDBClient(
    url=influxdb_url,
    token=influxdb_token,
    org=influxdb_org,
    connection_pool_maxsize=20,
    connection_pool_block=True
)
```

#### Alto Uso de Memória

**Sintomas:**
- Erros de falta de memória
- Performance lenta de consultas
- Instância ficando sem resposta

**Diagnóstico:**
```bash
# Verificar métricas da instância
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_MemoryUtilization \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

**Soluções:**
1. **Escalar instância:**
```bash
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.xlarge \
  --apply-immediately
```

2. **Otimizar consultas:**
```flux
// Usar intervalos de tempo menores
from(bucket: "energy_data")
  |> range(start: -1h)  // Em vez de -30d
  |> limit(n: 1000)     // Limitar tamanho do resultado
```

## Procedimentos de Manutenção

### Manutenção Programada

```bash
#!/bin/bash
# Manutenção Programada do InfluxDB

maintenance_window() {
    echo "Iniciando janela de manutenção do InfluxDB..."
    
    # 1. Habilitar modo de manutenção
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_production_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name enable_maintenance_mode \
      --enabled true
    
    # 2. Criar backup antes da manutenção
    echo "Criando backup pré-manutenção..."
    ./backup_influxdb.sh
    
    # 3. Aplicar atualizações da instância
    echo "Aplicando atualizações da instância..."
    aws timestreaminfluxdb modify-db-instance \
      --db-instance-identifier ons-influxdb-prod \
      --auto-minor-version-upgrade \
      --apply-immediately
    
    # 4. Aguardar conclusão das atualizações
    echo "Aguardando conclusão das atualizações..."
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier ons-influxdb-prod
    
    # 5. Executar validação pós-manutenção
    echo "Executando validação pós-manutenção..."
    python scripts/validate_influxdb_performance.py
    
    # 6. Desabilitar modo de manutenção
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_production_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name enable_maintenance_mode \
      --enabled false
    
    echo "Janela de manutenção concluída com sucesso"
}

# Agendar manutenção (exemplo: primeiro domingo de cada mês às 2h)
# 0 2 1-7 * 0 /path/to/maintenance_window.sh
```

## Monitoramento e Alertas

### Alarmes do CloudWatch para InfluxDB

```bash
#!/bin/bash
# Criar alarmes do CloudWatch para monitoramento do InfluxDB

# 1. Alarme de alto tempo de resposta
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-TempoRespostaAlto" \
  --alarm-description "Tempo de resposta do InfluxDB está alto" \
  --metric-name InfluxDB_ResponseTime \
  --namespace AWS/Timestream \
  --statistic Average \
  --period 300 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 2. Alarme de falhas de conexão
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-FalhasConexao" \
  --alarm-description "Falhas de conexão do InfluxDB detectadas" \
  --metric-name InfluxDB_ConnectionErrors \
  --namespace AWS/Timestream \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 3. Alarme de alta utilização de memória
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-AltaUtilizacaoMemoria" \
  --alarm-description "Utilização de memória do InfluxDB está alta" \
  --metric-name InfluxDB_MemoryUtilization \
  --namespace AWS/Timestream \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 3 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod

# 4. Alarme de baixo throughput de escrita
aws cloudwatch put-metric-alarm \
  --alarm-name "InfluxDB-BaixoThroughputEscrita" \
  --alarm-description "Throughput de escrita do InfluxDB está baixo" \
  --metric-name InfluxDB_WritePoints \
  --namespace AWS/Timestream \
  --statistic Sum \
  --period 900 \
  --threshold 1000 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:influxdb-alerts \
  --dimensions Name=DatabaseName,Value=ons-influxdb-prod
```

### Dashboard de Monitoramento Personalizado

```python
def create_influxdb_dashboard():
    """Criar dashboard do CloudWatch para monitoramento do InfluxDB"""
    import boto3
    import json
    
    cloudwatch = boto3.client('cloudwatch')
    
    dashboard_body = {
        "widgets": [
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_ResponseTime", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_QueryLatency", ".", "."],
                        [".", "InfluxDB_WriteLatency", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Tempos de Resposta do InfluxDB"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_WritePoints", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_QueryCount", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "Throughput do InfluxDB"
                }
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Timestream", "InfluxDB_MemoryUtilization", "DatabaseName", "ons-influxdb-prod"],
                        [".", "InfluxDB_CPUUtilization", ".", "."]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "Utilização de Recursos do InfluxDB"
                }
            }
        ]
    }
    
    cloudwatch.put_dashboard(
        DashboardName='InfluxDB-Operacoes',
        DashboardBody=json.dumps(dashboard_body)
    )
    
    print("Dashboard de monitoramento do InfluxDB criado com sucesso")

# Criar o dashboard
create_influxdb_dashboard()
```

---

**Última Atualização**: $(date)
**Versão**: 1.0 (Pós-Migração InfluxDB)
**Próxima Revisão**: $(date -d '+1 month')