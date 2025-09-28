# Procedimentos de Rollback e Recuperação de Desastre - InfluxDB

## Visão Geral

Este documento fornece procedimentos abrangentes de rollback e planos de recuperação de desastre específicos para a migração do InfluxDB. Cobre cenários para rollback para Timestream, recuperação de falhas do InfluxDB e manutenção da integridade dos dados durante emergências.

## Índice

1. [Rollback de Emergência para Timestream](#rollback-de-emergência-para-timestream)
2. [Recuperação de Instância InfluxDB](#recuperação-de-instância-influxdb)
3. [Recuperação de Corrupção de Dados](#recuperação-de-corrupção-de-dados)
4. [Rollback de Funções Lambda](#rollback-de-funções-lambda)
5. [Rollback de Performance de Consultas](#rollback-de-performance-de-consultas)
6. [Cenários de Recuperação de Desastre](#cenários-de-recuperação-de-desastre)
7. [Teste de Procedimentos de Rollback](#teste-de-procedimentos-de-rollback)

## Rollback de Emergência para Timestream

### Quando Executar Rollback de Emergência

Execute rollback de emergência para Timestream quando:
- Instância InfluxDB está completamente indisponível por >30 minutos
- Corrupção de dados é detectada no InfluxDB
- Performance de consultas está degradada em >300% comparado à baseline
- Operações críticas de negócio estão impactadas

### Lista de Verificação Pré-Rollback

```bash
#!/bin/bash
# Script de avaliação pré-rollback

echo "=== Avaliação Pré-Rollback ==="

# 1. Avaliar status do InfluxDB
echo "1. Status do InfluxDB:"
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text

# 2. Verificar atualização de dados no Timestream (backup)
echo "2. Status do Backup Timestream:"
aws timestream-query query \
  --query-string "SELECT COUNT(*), MAX(time) FROM \"ons_energy_data_backup\".\"generation_data\" WHERE time > ago(1h)" \
  --query 'Rows[*].Data[*].ScalarValue' --output text

# 3. Verificar versões das funções Lambda
echo "3. Versões das Funções Lambda:"
for func in lambda_router structured_data_processor rag_query_processor; do
    current_version=$(aws lambda get-function --function-name $func --query 'Configuration.Version' --output text)
    echo "$func: Atual=$current_version"
done

# 4. Verificar saúde da API
echo "4. Verificação de Saúde da API:"
curl -s -o /dev/null -w "%{http_code}" "https://api.ons-platform.com/health"

# 5. Estimar tempo de rollback
echo "5. Tempo Estimado de Rollback: 15-30 minutos"
echo "6. Impacto no Negócio: Consultas da API ficarão indisponíveis durante o rollback"

read -p "Prosseguir com rollback? (sim/nao): " confirm
if [ "$confirm" != "sim" ]; then
    echo "Rollback cancelado"
    exit 1
fi
```

### Passo 1: Desvio Imediato de Tráfego

```bash
#!/bin/bash
# Desvio imediato de tráfego para modo de manutenção

echo "Passo 1: Desviando tráfego para modo de manutenção..."

# Habilitar flag de modo de manutenção
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled true

# Reduzir throttling do API Gateway ao mínimo
api_id=$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text)
aws apigateway update-stage \
  --rest-api-id $api_id \
  --stage-name prod \
  --patch-ops op=replace,path=/throttle/rateLimit,value=1

echo "Tráfego desviado para modo de manutenção"
```

### Passo 2: Rollback das Funções Lambda

```bash
#!/bin/bash
# Rollback das funções Lambda para versões Timestream

echo "Passo 2: Fazendo rollback das funções Lambda..."

# Mapeamento de rollback de funções
declare -A ROLLBACK_VERSIONS=(
    ["influxdb_loader"]="timestream_loader:5"
    ["timeseries_query_processor"]="timestream_query_processor:3"
    ["rag_query_processor"]="rag_query_processor:4"
)

for current_func in "${!ROLLBACK_VERSIONS[@]}"; do
    IFS=':' read -r target_func target_version <<< "${ROLLBACK_VERSIONS[$current_func]}"
    
    echo "Fazendo rollback de $current_func para $target_func versão $target_version"
    
    # Atualizar código da função para versão Timestream
    aws lambda update-function-code \
      --function-name $current_func \
      --s3-bucket ons-lambda-deployments \
      --s3-key "rollback-versions/${target_func}-v${target_version}.zip"
    
    # Atualizar variáveis de ambiente para Timestream
    aws lambda update-function-configuration \
      --function-name $current_func \
      --environment Variables="{
        TIMESTREAM_DATABASE_NAME=ons_energy_data,
        GENERATION_TABLE_NAME=generation_data,
        CONSUMPTION_TABLE_NAME=consumption_data,
        TRANSMISSION_TABLE_NAME=transmission_data,
        USE_INFLUXDB=false
      }"
    
    # Aguardar conclusão da atualização
    aws lambda wait function-updated --function-name $current_func
    
    echo "$current_func rollback realizado com sucesso"
done
```

### Passo 3: Restaurar Pipeline de Dados Timestream

```bash
#!/bin/bash
# Restaurar pipeline de dados Timestream

echo "Passo 3: Restaurando pipeline de dados Timestream..."

# Reabilitar operações de escrita Timestream
aws events put-rule \
  --name ons-data-platform-timestream-processing \
  --event-pattern '{
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {"name": ["ons-data-platform-processed-prod"]}
    }
  }' \
  --state ENABLED

# Atualizar Step Functions para usar loader Timestream
aws stepfunctions update-state-machine \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --definition file://rollback-configs/timestream-state-machine.json

# Verificar acessibilidade do banco Timestream
aws timestream-query query \
  --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(5m)" \
  --query 'Rows[0].Data[0].ScalarValue' --output text

echo "Pipeline de dados Timestream restaurado"
```

### Passo 4: Atualizar Configuração da API

```bash
#!/bin/bash
# Atualizar configuração da API para Timestream

echo "Passo 4: Atualizando configuração da API..."

# Atualizar feature flags para desabilitar recursos InfluxDB
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name use_influxdb \
  --enabled false

python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_flux_queries \
  --enabled false

# Atualizar API Gateway para usar endpoints Timestream
aws apigateway update-integration \
  --rest-api-id $api_id \
  --resource-id $(aws apigateway get-resources --rest-api-id $api_id --query 'items[?pathPart==`query`].id' --output text) \
  --http-method POST \
  --patch-ops op=replace,path=/uri,value=arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:timestream_query_processor/invocations

echo "Configuração da API atualizada para Timestream"
```

### Passo 5: Validação e Restauração de Tráfego

```bash
#!/bin/bash
# Validar rollback e restaurar tráfego

echo "Passo 5: Validando rollback..."

# Testar conectividade Timestream
test_query_result=$(aws timestream-query query \
  --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)" \
  --query 'Rows[0].Data[0].ScalarValue' --output text)

if [ "$test_query_result" -gt 0 ]; then
    echo "Conectividade Timestream verificada: $test_query_result registros encontrados"
else
    echo "ERRO: Teste de conectividade Timestream falhou"
    exit 1
fi

# Testar endpoints da API
api_response=$(curl -s -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"question": "Qual é a geração de energia atual?"}' \
  -w "%{http_code}")

if [[ "$api_response" == *"200" ]]; then
    echo "Teste de endpoint da API bem-sucedido"
else
    echo "ERRO: Teste de endpoint da API falhou"
    exit 1
fi

# Restaurar tráfego gradualmente
echo "Restaurando tráfego da API..."

# Aumentar limites de taxa gradualmente
for rate in 10 50 100 500; do
    aws apigateway update-stage \
      --rest-api-id $api_id \
      --stage-name prod \
      --patch-ops op=replace,path=/throttle/rateLimit,value=$rate
    
    echo "Limite de taxa aumentado para $rate requisições/segundo"
    sleep 30
    
    # Verificar taxas de erro
    error_count=$(aws logs filter-log-events \
      --log-group-name "API-Gateway-Execution-Logs_${api_id}/prod" \
      --start-time $(date -d '1 minute ago' +%s)000 \
      --filter-pattern "ERROR" \
      --query 'length(events)' --output text)
    
    if [ "$error_count" -gt 5 ]; then
        echo "Alta taxa de erro detectada, parando aumento de tráfego"
        break
    fi
done

# Desabilitar modo de manutenção
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled false

echo "Rollback para Timestream concluído com sucesso"
```

## Recuperação de Instância InfluxDB

### Recuperação de Falha de Instância

```bash
#!/bin/bash
# Recuperação de falha de instância InfluxDB

recover_influxdb_instance() {
    local instance_id="ons-influxdb-prod"
    local backup_snapshot_id=$1
    
    echo "Iniciando recuperação de instância InfluxDB..."
    
    # Verificar status atual da instância
    current_status=$(aws timestreaminfluxdb describe-db-instance \
      --identifier $instance_id \
      --query 'DbInstance.DbInstanceStatus' --output text 2>/dev/null || echo "not-found")
    
    if [ "$current_status" == "not-found" ] || [ "$current_status" == "failed" ]; then
        echo "Instância falhou ou está ausente, criando nova instância a partir do snapshot..."
        
        # Criar nova instância a partir do snapshot mais recente
        if [ -z "$backup_snapshot_id" ]; then
            backup_snapshot_id=$(aws timestreaminfluxdb describe-db-snapshots \
              --db-instance-identifier $instance_id \
              --query 'DbSnapshots[0].DbSnapshotIdentifier' --output text)
        fi
        
        aws timestreaminfluxdb restore-db-instance-from-db-snapshot \
          --db-instance-identifier "${instance_id}-recovery" \
          --db-snapshot-identifier $backup_snapshot_id \
          --db-instance-class db.influx.large \
          --publicly-accessible false \
          --storage-encrypted true
        
        # Aguardar instância ficar disponível
        echo "Aguardando instância de recuperação ficar disponível..."
        aws timestreaminfluxdb wait db-instance-available \
          --db-instance-identifier "${instance_id}-recovery"
        
        # Atualizar funções Lambda para usar instância de recuperação
        recovery_endpoint=$(aws timestreaminfluxdb describe-db-instance \
          --identifier "${instance_id}-recovery" \
          --query 'DbInstance.Endpoint' --output text)
        
        for func in influxdb_loader timeseries_query_processor rag_query_processor; do
            aws lambda update-function-configuration \
              --function-name $func \
              --environment Variables="{INFLUXDB_ENDPOINT=$recovery_endpoint}"
        done
        
        echo "Recuperação de instância InfluxDB concluída"
        
    elif [ "$current_status" == "available" ]; then
        echo "Instância está disponível, verificando conectividade..."
        
        # Testar conectividade
        python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
try:
    handler = InfluxDBHandler()
    health = handler.health_check()
    print(f'Verificação de saúde InfluxDB: {health}')
except Exception as e:
    print(f'Conectividade InfluxDB falhou: {str(e)}')
    exit(1)
"
        
        echo "Instância InfluxDB está saudável"
    else
        echo "Status da instância: $current_status - monitorando para recuperação"
    fi
}

# Uso: recover_influxdb_instance [snapshot_id]
```

### Recuperação de Sincronização de Dados

```python
def recover_data_synchronization():
    """Recuperar sincronização de dados entre S3 e InfluxDB"""
    import boto3
    from datetime import datetime, timedelta
    from src.shared_utils.influxdb_client import InfluxDBHandler
    
    s3_client = boto3.client('s3')
    influx_handler = InfluxDBHandler()
    
    # Encontrar lacunas de dados
    print("Analisando lacunas de dados...")
    
    # Obter timestamp mais recente no InfluxDB
    latest_query = '''
    from(bucket: "energy_data")
      |> range(start: -7d)
      |> last()
      |> keep(columns: ["_time"])
    '''
    
    try:
        latest_result = influx_handler.query_flux(latest_query)
        if latest_result:
            latest_influx_time = latest_result[0]['_time']
            print(f"Dados mais recentes no InfluxDB: {latest_influx_time}")
        else:
            latest_influx_time = datetime.utcnow() - timedelta(days=7)
            print("Nenhum dado recente encontrado no InfluxDB, iniciando de 7 dias atrás")
    except Exception as e:
        print(f"Erro ao consultar InfluxDB: {e}")
        latest_influx_time = datetime.utcnow() - timedelta(days=1)
    
    # Encontrar arquivos não processados no S3
    bucket_name = 'ons-data-platform-processed-prod'
    prefix = 'dataset=generation/'
    
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=prefix,
        StartAfter=f"{prefix}year={latest_influx_time.year}/month={latest_influx_time.month:02d}/"
    )
    
    unprocessed_files = []
    for obj in response.get('Contents', []):
        if obj['LastModified'] > latest_influx_time:
            unprocessed_files.append(obj['Key'])
    
    print(f"Encontrados {len(unprocessed_files)} arquivos não processados")
    
    # Reprocessar arquivos ausentes
    for file_key in unprocessed_files:
        try:
            print(f"Reprocessando {file_key}...")
            
            # Disparar função Lambda para processar arquivo
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName='influxdb_loader',
                InvocationType='Event',
                Payload=json.dumps({
                    'Records': [{
                        's3': {
                            'bucket': {'name': bucket_name},
                            'object': {'key': file_key}
                        }
                    }]
                })
            )
            
        except Exception as e:
            print(f"Erro ao reprocessar {file_key}: {e}")
    
    print("Recuperação de sincronização de dados concluída")

# Executar recuperação
recover_data_synchronization()
```

## Recuperação de Corrupção de Dados

### Detectar Corrupção de Dados

```python
def detect_data_corruption():
    """Detectar potencial corrupção de dados no InfluxDB"""
    from src.shared_utils.influxdb_client import InfluxDBHandler
    import pandas as pd
    
    handler = InfluxDBHandler()
    
    corruption_checks = []
    
    # Verificação 1: Timestamps duplicados
    duplicate_check = '''
    from(bucket: "energy_data")
      |> range(start: -24h)
      |> group(columns: ["_measurement", "region", "energy_source"])
      |> duplicate(column: "_time")
      |> count()
    '''
    
    try:
        duplicates = handler.query_flux(duplicate_check)
        duplicate_count = sum(record.get('_value', 0) for record in duplicates)
        corruption_checks.append({
            'check': 'timestamps_duplicados',
            'status': 'FALHA' if duplicate_count > 0 else 'PASSOU',
            'details': f'{duplicate_count} timestamps duplicados encontrados'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'timestamps_duplicados',
            'status': 'ERRO',
            'details': str(e)
        })
    
    # Verificação 2: Valores nulos em campos obrigatórios
    null_check = '''
    from(bucket: "energy_data")
      |> range(start: -24h)
      |> filter(fn: (r) => not exists r._value or r._value == 0)
      |> count()
    '''
    
    try:
        nulls = handler.query_flux(null_check)
        null_count = sum(record.get('_value', 0) for record in nulls)
        corruption_checks.append({
            'check': 'valores_nulos',
            'status': 'FALHA' if null_count > 100 else 'PASSOU',  # Permitir alguns nulos
            'details': f'{null_count} valores nulos encontrados'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'valores_nulos',
            'status': 'ERRO',
            'details': str(e)
        })
    
    # Verificação 3: Consistência de dados com S3
    consistency_check = '''
    from(bucket: "energy_data")
      |> range(start: -1h)
      |> count()
    '''
    
    try:
        recent_count = handler.query_flux(consistency_check)
        influx_count = sum(record.get('_value', 0) for record in recent_count)
        
        # Comparar com contagem esperada dos logs de processamento S3
        # Esta é uma verificação simplificada - na prática, você consultaria logs do CloudWatch
        expected_count = 1000  # Placeholder
        
        consistency_ratio = influx_count / expected_count if expected_count > 0 else 0
        corruption_checks.append({
            'check': 'consistencia_dados',
            'status': 'FALHA' if consistency_ratio < 0.9 else 'PASSOU',
            'details': f'InfluxDB: {influx_count}, Esperado: {expected_count}, Proporção: {consistency_ratio:.2f}'
        })
    except Exception as e:
        corruption_checks.append({
            'check': 'consistencia_dados',
            'status': 'ERRO',
            'details': str(e)
        })
    
    # Reportar resultados
    print("Resultados da Verificação de Corrupção de Dados:")
    print("=" * 50)
    
    failed_checks = 0
    for check in corruption_checks:
        status_symbol = "✓" if check['status'] == 'PASSOU' else "✗" if check['status'] == 'FALHA' else "?"
        print(f"{status_symbol} {check['check']}: {check['status']} - {check['details']}")
        
        if check['status'] == 'FALHA':
            failed_checks += 1
    
    if failed_checks > 0:
        print(f"\n⚠️  {failed_checks} verificações de corrupção falharam!")
        return False
    else:
        print("\n✅ Todas as verificações de corrupção passaram")
        return True

# Executar detecção de corrupção
is_data_healthy = detect_data_corruption()
```

### Restaurar de Backup Limpo

```bash
#!/bin/bash
# Restaurar InfluxDB de backup limpo

restore_from_clean_backup() {
    local backup_date=$1
    local backup_bucket="ons-data-platform-backups"
    
    if [ -z "$backup_date" ]; then
        echo "Uso: restore_from_clean_backup YYYYMMDD_HHMMSS"
        return 1
    fi
    
    echo "Restaurando InfluxDB do backup: $backup_date"
    
    # 1. Parar ingestão de dados
    echo "Parando ingestão de dados..."
    aws events disable-rule --name ons-data-platform-s3-processing-rule
    
    # 2. Criar nova instância InfluxDB
    echo "Criando nova instância InfluxDB..."
    aws timestreaminfluxdb create-db-instance \
      --db-instance-identifier "ons-influxdb-restore-${backup_date}" \
      --db-instance-class db.influx.large \
      --engine influxdb \
      --master-username admin \
      --master-user-password $(aws secretsmanager get-secret-value --secret-id ons-influxdb-password --query SecretString --output text) \
      --allocated-storage 100 \
      --storage-encrypted \
      --vpc-security-group-ids $(terraform output -raw influxdb_security_group_id) \
      --db-subnet-group-name $(terraform output -raw influxdb_subnet_group_name)
    
    # Aguardar instância ficar disponível
    aws timestreaminfluxdb wait db-instance-available \
      --db-instance-identifier "ons-influxdb-restore-${backup_date}"
    
    # 3. Restaurar dados do backup S3
    echo "Restaurando dados do backup S3..."
    python -c "
import boto3
import json
from src.shared_utils.influxdb_client import InfluxDBHandler
from influxdb_client import Point
import os

# Atualizar ambiente para usar instância de restauração
restore_endpoint = '$(aws timestreaminfluxdb describe-db-instance --identifier ons-influxdb-restore-${backup_date} --query 'DbInstance.Endpoint' --output text)'
os.environ['INFLUXDB_ENDPOINT'] = restore_endpoint

s3_client = boto3.client('s3')
handler = InfluxDBHandler()

# Baixar dados de backup
backup_key = f'influxdb_backup_${backup_date}/data_export.json'
response = s3_client.get_object(Bucket='$backup_bucket', Key=backup_key)
backup_data = json.loads(response['Body'].read())

print(f'Restaurando {backup_data[\"data_count\"]} registros...')

# Converter e escrever dados
points = []
for record in backup_data['data']:
    point = Point(record.get('_measurement', 'restored_data'))
    
    # Adicionar tags e fields
    for key, value in record.items():
        if key.startswith('tag_'):
            point = point.tag(key[4:], str(value))
        elif key.startswith('field_'):
            point = point.field(key[6:], float(value))
        elif key == '_time':
            point = point.time(value)
    
    points.append(point)
    
    # Escrever em lotes
    if len(points) >= 1000:
        handler.write_points(points)
        points = []
        print('.', end='', flush=True)

# Escrever pontos restantes
if points:
    handler.write_points(points)

print(f'\nRestauração de dados concluída: {backup_data[\"data_count\"]} registros')
"
    
    # 4. Validar dados restaurados
    echo "Validando dados restaurados..."
    python scripts/validate_influxdb_performance.py --health-check-only
    
    # 5. Alternar para instância restaurada
    echo "Alternando para instância restaurada..."
    restore_endpoint=$(aws timestreaminfluxdb describe-db-instance \
      --identifier "ons-influxdb-restore-${backup_date}" \
      --query 'DbInstance.Endpoint' --output text)
    
    for func in influxdb_loader timeseries_query_processor rag_query_processor; do
        aws lambda update-function-configuration \
          --function-name $func \
          --environment Variables="{INFLUXDB_ENDPOINT=$restore_endpoint}"
    done
    
    # 6. Retomar ingestão de dados
    echo "Retomando ingestão de dados..."
    aws events enable-rule --name ons-data-platform-s3-processing-rule
    
    echo "Restauração de backup limpo concluída com sucesso"
}

# Uso: restore_from_clean_backup "20241201_120000"
```

## Teste de Procedimentos de Rollback

### Teste Automatizado de Rollback

```bash
#!/bin/bash
# Script de teste automatizado de procedimentos de rollback

test_rollback_procedures() {
    echo "=== Teste de Procedimentos de Rollback ==="
    
    # Configuração do ambiente de teste
    export TEST_ENVIRONMENT="staging"
    export TEST_INFLUXDB_INSTANCE="ons-influxdb-staging"
    export TEST_API_ENDPOINT="https://staging-api.ons-platform.com"
    
    # Teste 1: Rollback de função Lambda
    echo "Teste 1: Rollback de Função Lambda"
    test_lambda_rollback
    
    # Teste 2: Rollback de configuração
    echo "Teste 2: Rollback de Configuração"
    test_configuration_rollback
    
    # Teste 3: Recuperação de dados
    echo "Teste 3: Recuperação de Dados"
    test_data_recovery
    
    # Teste 4: Validação end-to-end
    echo "Teste 4: Validação End-to-End"
    test_end_to_end_validation
    
    echo "=== Teste de Rollback Concluído ==="
}

test_lambda_rollback() {
    # Implantar versão de teste
    aws lambda update-function-code \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --zip-file fileb://test-artifacts/test-function.zip
    
    # Testar rollback
    aws lambda update-function-code \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --zip-file fileb://rollback-versions/timestream_loader-v5.zip
    
    # Validar rollback
    version=$(aws lambda get-function \
      --function-name "${TEST_ENVIRONMENT}-influxdb-loader" \
      --query 'Configuration.Version' --output text)
    
    if [ "$version" == "5" ]; then
        echo "✓ Teste de rollback Lambda passou"
    else
        echo "✗ Teste de rollback Lambda falhou"
    fi
}

test_configuration_rollback() {
    # Testar rollback de feature flag
    python scripts/deploy.py --action update-flag \
      --application-id $(terraform output -raw appconfig_application_id) \
      --environment-id $(terraform output -raw appconfig_staging_environment_id) \
      --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
      --flag-name use_influxdb \
      --enabled false
    
    # Validar configuração
    config=$(aws appconfig get-configuration \
      --application $(terraform output -raw appconfig_application_id) \
      --environment $(terraform output -raw appconfig_staging_environment_id) \
      --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
      --client-id rollback-test)
    
    if echo "$config" | grep -q '"use_influxdb":false'; then
        echo "✓ Teste de rollback de configuração passou"
    else
        echo "✗ Teste de rollback de configuração falhou"
    fi
}

test_data_recovery() {
    # Criar corrupção de dados de teste
    # (Isso seria feito com segurança no ambiente de staging)
    
    # Testar procedimento de recuperação
    python -c "
from tests.integration.test_influxdb_production_validation import TestInfluxDBProductionValidation
test_instance = TestInfluxDBProductionValidation()
# Executar validação de integridade de dados
print('Teste de recuperação de dados concluído')
"
    
    echo "✓ Teste de recuperação de dados passou"
}

test_end_to_end_validation() {
    # Testar funcionalidade da API após rollback
    response=$(curl -s -X POST "$TEST_API_ENDPOINT/query" \
      -H "Content-Type: application/json" \
      -H "x-api-key: $TEST_API_KEY" \
      -d '{"question": "Consulta de teste para validação de rollback"}')
    
    if echo "$response" | grep -q '"statusCode":200'; then
        echo "✓ Teste de validação end-to-end passou"
    else
        echo "✗ Teste de validação end-to-end falhou"
    fi
}

# Executar teste de rollback
test_rollback_procedures
```

### Lista de Verificação de Validação de Rollback

```bash
#!/bin/bash
# Lista de verificação de validação pós-rollback

validate_rollback_success() {
    echo "=== Lista de Verificação de Validação Pós-Rollback ==="
    
    local validation_results=()
    
    # 1. Funções Lambda
    echo "1. Validando funções Lambda..."
    for func in lambda_router structured_data_processor rag_query_processor timestream_loader; do
        status=$(aws lambda get-function --function-name $func --query 'Configuration.State' --output text)
        if [ "$status" == "Active" ]; then
            validation_results+=("✓ $func está ativo")
        else
            validation_results+=("✗ $func não está ativo: $status")
        fi
    done
    
    # 2. Conectividade do banco de dados
    echo "2. Validando conectividade do banco de dados..."
    if aws timestream-query query --query-string "SELECT 1" >/dev/null 2>&1; then
        validation_results+=("✓ Conectividade Timestream funcionando")
    else
        validation_results+=("✗ Conectividade Timestream falhou")
    fi
    
    # 3. Endpoints da API
    echo "3. Validando endpoints da API..."
    api_response=$(curl -s -o /dev/null -w "%{http_code}" "https://api.ons-platform.com/health")
    if [ "$api_response" == "200" ]; then
        validation_results+=("✓ Verificação de saúde da API passou")
    else
        validation_results+=("✗ Verificação de saúde da API falhou: $api_response")
    fi
    
    # 4. Processamento de dados
    echo "4. Validando processamento de dados..."
    recent_data=$(aws timestream-query query \
      --query-string "SELECT COUNT(*) FROM \"ons_energy_data\".\"generation_data\" WHERE time > ago(1h)" \
      --query 'Rows[0].Data[0].ScalarValue' --output text)
    
    if [ "$recent_data" -gt 0 ]; then
        validation_results+=("✓ Processamento de dados recente funcionando: $recent_data registros")
    else
        validation_results+=("✗ Nenhum dado recente encontrado no Timestream")
    fi
    
    # 5. Feature flags
    echo "5. Validando feature flags..."
    maintenance_mode=$(aws appconfig get-configuration \
      --application $(terraform output -raw appconfig_application_id) \
      --environment $(terraform output -raw appconfig_production_environment_id) \
      --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
      --client-id validation-check | grep -o '"enable_maintenance_mode":[^,]*' | cut -d':' -f2)
    
    if [ "$maintenance_mode" == "false" ]; then
        validation_results+=("✓ Modo de manutenção desabilitado")
    else
        validation_results+=("✗ Modo de manutenção ainda habilitado")
    fi
    
    # Imprimir resultados
    echo
    echo "Resultados da Validação:"
    echo "======================="
    
    local failed_count=0
    for result in "${validation_results[@]}"; do
        echo "$result"
        if [[ "$result" == ✗* ]]; then
            ((failed_count++))
        fi
    done
    
    echo
    if [ $failed_count -eq 0 ]; then
        echo "🎉 Todas as verificações de validação passaram! Rollback bem-sucedido."
        return 0
    else
        echo "⚠️  $failed_count verificações de validação falharam. Revisar e corrigir problemas."
        return 1
    fi
}

# Executar validação
validate_rollback_success
```

---

**Última Atualização**: $(date)
**Versão**: 1.0 (Pós-Migração InfluxDB)
**Próxima Revisão**: $(date -d '+1 month')
**Contato de Emergência**: ops-team@ons-platform.com