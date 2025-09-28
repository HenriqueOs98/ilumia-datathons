# Manual de Operações - Plataforma de Dados ONS

## Visão Geral

Este manual fornece procedimentos passo a passo para tarefas operacionais comuns, guias de solução de problemas e procedimentos de resposta de emergência para a Plataforma de Dados ONS.

## Índice

1. [Verificações de Saúde do Sistema](#verificações-de-saúde-do-sistema)
2. [Tarefas de Manutenção Comuns](#tarefas-de-manutenção-comuns)
3. [Guias de Solução de Problemas](#guias-de-solução-de-problemas)
4. [Procedimentos de Emergência](#procedimentos-de-emergência)
5. [Monitoramento de Performance](#monitoramento-de-performance)
6. [Gestão de Custos](#gestão-de-custos)
7. [Operações de Segurança](#operações-de-segurança)

## Verificações de Saúde do Sistema

### Verificação Diária de Saúde

Execute esta verificação abrangente de saúde todas as manhãs:

```bash
#!/bin/bash
# Script de verificação diária de saúde

echo "=== Verificação de Saúde da Plataforma de Dados ONS ==="
echo "Data: $(date)"
echo

# 1. Verificar saúde das funções Lambda
echo "1. Saúde das Funções Lambda:"
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor influxdb_loader

# 2. Verificar saúde do API Gateway
echo "2. Saúde do API Gateway:"
curl -s -o /dev/null -w "%{http_code}" \
  "https://$(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text).execute-api.us-east-1.amazonaws.com/prod/health"

# 3. Verificar acessibilidade dos buckets S3
echo "3. Saúde dos Buckets S3:"
aws s3 ls s3://ons-data-platform-raw-prod/ > /dev/null && echo "✓ Bucket raw acessível" || echo "✗ Erro no bucket raw"
aws s3 ls s3://ons-data-platform-processed-prod/ > /dev/null && echo "✓ Bucket processado acessível" || echo "✗ Erro no bucket processado"

# 4. Verificar banco de dados InfluxDB
echo "4. Saúde do Banco InfluxDB:"
python scripts/validate_influxdb_performance.py --health-check-only

# 5. Verificar atividade de processamento recente
echo "5. Atividade de Processamento Recente:"
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "SUCCESS" \
  --query 'events[*].message' --output table

echo "=== Verificação de Saúde Completa ==="
```

### Verificação Semanal de Saúde

Verificação estendida para revisão semanal:

```bash
#!/bin/bash
# Script de verificação semanal de saúde

echo "=== Revisão Semanal de Saúde ==="

# 1. Verificar taxas de erro da última semana
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'length(events)' --output text

# 2. Revisar tendências de custo
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 3. Verificar utilização de armazenamento
aws s3api list-objects-v2 \
  --bucket ons-data-platform-raw-prod \
  --query 'sum(Contents[].Size)' --output text

# 4. Revisar alertas de segurança
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '7 days ago' +%s)000 \
  --filter-pattern "SECURITY" \
  --query 'length(events)' --output text
```

## Tarefas de Manutenção Comuns

### 1. Atualizar Código das Funções Lambda

```bash
# Atualizar uma função Lambda específica
cd src/lambda_router

# Empacotar a função
zip -r lambda_router.zip . -x "tests/*" "*.pyc" "__pycache__/*"

# Atualizar código da função
aws lambda update-function-code \
  --function-name lambda_router \
  --zip-file fileb://lambda_router.zip

# Publicar nova versão
VERSION=$(aws lambda publish-version \
  --function-name lambda_router \
  --description "Atualização manual $(date)" \
  --query 'Version' --output text)

echo "Versão publicada: $VERSION"

# Implantar com estratégia blue-green
python ../../scripts/deploy.py \
  --function-name lambda_router \
  --version $VERSION \
  --deployment-group lambda_router-deployment-group
```

### 2. Escalar Banco de Dados InfluxDB

```bash
# Verificar uso atual do InfluxDB
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.[DbInstanceStatus,AllocatedStorage,DbInstanceClass]' --output table

# Escalar instância se necessário
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.large \
  --allocated-storage 200 \
  --apply-immediately

# Atualizar políticas de retenção
python scripts/manage_influxdb_retention.py \
  --bucket energy_data \
  --retention-period 7y
```

### 3. Limpeza de Dados Antigos

```bash
# Limpar versões antigas do Lambda (manter últimas 5)
FUNCTION_NAME="lambda_router"
aws lambda list-versions-by-function \
  --function-name $FUNCTION_NAME \
  --query 'Versions[?Version!=`$LATEST`].Version' \
  --output text | \
  head -n -5 | \
  xargs -I {} aws lambda delete-function \
    --function-name $FUNCTION_NAME \
    --qualifier {}

# Limpar logs antigos do CloudWatch (mais antigos que período de retenção)
aws logs describe-log-groups \
  --query 'logGroups[?retentionInDays==`null`].logGroupName' \
  --output text | \
  xargs -I {} aws logs put-retention-policy \
    --log-group-name {} \
    --retention-in-days 30
```

### 4. Atualizar Feature Flags

```bash
# Habilitar uma feature flag
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_new_api_endpoint \
  --enabled true

# Verificar status da flag
aws appconfig get-configuration \
  --application $(terraform output -raw appconfig_application_id) \
  --environment $(terraform output -raw appconfig_production_environment_id) \
  --configuration $(terraform output -raw appconfig_feature_flags_profile_id) \
  --client-id operations-check
```

## Guias de Solução de Problemas

### Problema: Alta Taxa de Erro nas Funções Lambda

**Sintomas:**
- Alarmes do CloudWatch disparando
- Aumento nos logs de erro
- API retornando erros 5xx

**Passos de Investigação:**

1. **Verificar implantações recentes:**
```bash
aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses Succeeded Failed \
  --max-items 5
```

2. **Analisar logs de erro:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR" \
  --query 'events[*].[timestamp,message]' --output table
```

3. **Verificar métricas da função:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=lambda_router \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

**Resolução:**

1. **Se implantação recente causou problemas:**
```bash
python scripts/rollback.py --action rollback-function \
  --function-name lambda_router
```

2. **Se problema de configuração:**
```bash
# Desabilitar feature flag problemática
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_problematic_feature
```

### Problema: Falhas de Escrita no InfluxDB

**Sintomas:**
- Dados não aparecendo no InfluxDB
- Timeouts de conexão
- Alta latência de escrita

**Passos de Investigação:**

1. **Verificar métricas do InfluxDB:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Timestream \
  --metric-name InfluxDB_WriteLatency \
  --dimensions Name=DatabaseName,Value=ons_influxdb_prod \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum
```

2. **Verificar status do banco:**
```bash
aws timestreaminfluxdb describe-db-instance \
  --identifier ons-influxdb-prod \
  --query 'DbInstance.DbInstanceStatus' --output text
```

3. **Testar conectividade:**
```bash
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()
print(handler.health_check())
"
```

**Resolução:**

1. **Implementar escrita em lote com retry:**
```python
from src.shared_utils.influxdb_client import InfluxDBHandler
import time

def batch_write_with_retry(points, max_retries=3):
    handler = InfluxDBHandler()
    
    for attempt in range(max_retries):
        try:
            handler.write_points(points, batch_size=1000)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
            print(f"Tentativa de escrita {attempt + 1}/{max_retries} após {wait_time}s")
    
    return False
```

2. **Escalar instância do InfluxDB:**
```bash
aws timestreaminfluxdb modify-db-instance \
  --db-instance-identifier ons-influxdb-prod \
  --db-instance-class db.influx.xlarge \
  --apply-immediately
```

## Procedimentos de Emergência

### Falha Crítica do Sistema

**Ações Imediatas (Primeiros 5 minutos):**

1. **Avaliar impacto:**
```bash
# Verificar todos os componentes críticos
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor influxdb_loader timeseries_query_processor
```

2. **Parar implantações em andamento:**
```bash
# Listar implantações ativas
aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses InProgress

# Parar todas as implantações ativas
for deployment in $(aws codedeploy list-deployments \
  --application-name ons-data-platform-lambda-app \
  --include-only-statuses InProgress \
  --query 'deployments[]' --output text); do
  python scripts/rollback.py --action stop-deployment --deployment-id $deployment
done
```

3. **Desabilitar recursos problemáticos:**
```bash
# Desabilitar todas as feature flags não críticas
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_new_api_endpoint enable_enhanced_processing
```

### Prevenção de Perda de Dados

**Se suspeita de corrupção de dados:**

1. **Parar todo processamento:**
```bash
# Desabilitar regras do EventBridge
aws events disable-rule --name ons-data-platform-s3-processing-rule

# Parar execuções do Step Functions
for execution in $(aws stepfunctions list-executions \
  --state-machine-arn $(terraform output -raw step_function_arn) \
  --status-filter RUNNING \
  --query 'executions[].executionArn' --output text); do
  aws stepfunctions stop-execution --execution-arn $execution
done
```

2. **Criar snapshots de dados:**
```bash
# Snapshot dos buckets S3
aws s3 sync s3://$(terraform output -raw s3_processed_bucket_name) \
  s3://$(terraform output -raw s3_processed_bucket_name)-backup-$(date +%Y%m%d) \
  --storage-class GLACIER
```

3. **Verificar integridade dos dados:**
```bash
# Verificar qualidade dos dados recentes
python -c "
from src.shared_utils.influxdb_client import InfluxDBHandler
handler = InfluxDBHandler()
query = '''
from(bucket: \"energy_data\")
  |> range(start: -24h)
  |> count()
'''
result = handler.query_flux(query)
print(f'Registros nas últimas 24h: {len(result)}')
"
```

## Monitoramento de Performance

### Indicadores Chave de Performance (KPIs)

1. **Taxa de Processamento:**
```bash
# Arquivos processados por hora
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern "PROCESSED" \
  --query 'length(events)'
```

2. **Tempo de Resposta da API:**
```bash
# Latência média da API
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Latency \
  --dimensions Name=ApiName,Value=ons-data-platform-api \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average
```

3. **Taxas de Erro:**
```bash
# Taxa de erro do Lambda
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=lambda_router \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Sum
```

### Otimização de Performance

1. **Otimização de Cold Start do Lambda:**
```bash
# Habilitar concorrência provisionada para funções críticas
aws lambda put-provisioned-concurrency-config \
  --function-name lambda_router \
  --qualifier LIVE \
  --provisioned-concurrency-config ProvisionedConcurrencyConfigs=2
```

2. **Cache do API Gateway:**
```bash
# Habilitar cache para endpoints GET
aws apigateway update-stage \
  --rest-api-id $(aws apigateway get-rest-apis --query 'items[?name==`ons-data-platform-api`].id' --output text) \
  --stage-name prod \
  --patch-ops op=replace,path=/cacheClusterEnabled,value=true
```

## Gestão de Custos

### Monitoramento Diário de Custos

```bash
# Verificar custos diários
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '1 day ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.BlendedCost.Amount]' \
  --output table
```

### Ações de Otimização de Custos

1. **Limpar recursos não utilizados:**
```bash
# Remover versões antigas do Lambda
for function in lambda_router structured_data_processor rag_query_processor influxdb_loader; do
  aws lambda list-versions-by-function \
    --function-name $function \
    --query 'Versions[?Version!=`$LATEST`].Version' \
    --output text | \
    head -n -3 | \
    xargs -I {} aws lambda delete-function \
      --function-name $function \
      --qualifier {}
done
```

2. **Otimizar classes de armazenamento:**
```bash
# Mover dados antigos para armazenamento mais barato
aws s3api put-bucket-lifecycle-configuration \
  --bucket $(terraform output -raw s3_raw_bucket_name) \
  --lifecycle-configuration file://lifecycle-policy.json
```

## Operações de Segurança

### Verificações Diárias de Segurança

```bash
# Verificar alertas de segurança
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda_router \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --filter-pattern "SECURITY" \
  --query 'events[*].[timestamp,message]' --output table

# Verificar mudanças nas políticas IAM
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutUserPolicy \
  --start-time $(date -d '24 hours ago' --iso-8601) \
  --end-time $(date --iso-8601)
```

### Endurecimento de Segurança

1. **Atualizar grupos de segurança:**
```bash
# Revisar e apertar regras dos grupos de segurança
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=ons-data-platform-* \
  --query 'SecurityGroups[*].[GroupName,IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[*].CidrIp]]' \
  --output table
```

2. **Rotacionar chaves de acesso:**
```bash
# Listar chaves de acesso antigas
aws iam list-access-keys \
  --query 'AccessKeyMetadata[?Age>`90`].[AccessKeyId,CreateDate]' \
  --output table
```

## Janelas de Manutenção

### Procedimento de Manutenção Programada

1. **Pré-manutenção (30 minutos antes):**
```bash
# Notificar usuários
aws sns publish \
  --topic-arn $(terraform output -raw deployment_sns_topic_arn) \
  --message "Manutenção programada iniciando em 30 minutos. API pode ficar temporariamente indisponível."

# Criar backup
aws s3 sync s3://$(terraform output -raw s3_processed_bucket_name) \
  s3://$(terraform output -raw s3_processed_bucket_name)-maintenance-backup-$(date +%Y%m%d)
```

2. **Durante a manutenção:**
```bash
# Habilitar modo de manutenção
python scripts/rollback.py --action rollback-flags \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flags enable_maintenance_mode

# Executar tarefas de manutenção
terraform plan -var-file="environments/prod.tfvars"
terraform apply -var-file="environments/prod.tfvars"
```

3. **Pós-manutenção:**
```bash
# Desabilitar modo de manutenção
python scripts/deploy.py --action update-flag \
  --application-id $(terraform output -raw appconfig_application_id) \
  --environment-id $(terraform output -raw appconfig_production_environment_id) \
  --profile-id $(terraform output -raw appconfig_feature_flags_profile_id) \
  --flag-name enable_maintenance_mode \
  --enabled false

# Executar verificações de saúde
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor influxdb_loader

# Notificar conclusão
aws sns publish \
  --topic-arn $(terraform output -raw deployment_sns_topic_arn) \
  --message "Manutenção programada concluída com sucesso. Todos os sistemas operacionais."
```

## Informações de Contato

### Matriz de Escalação

1. **Nível 1 - Equipe de Operações**
   - Email: ops-team@company.com
   - Slack: #ops-alerts
   - Telefone: +55-11-XXXX-XXXX

2. **Nível 2 - Equipe de Engenharia**
   - Email: engineering@company.com
   - Slack: #engineering-alerts
   - Telefone: +55-11-YYYY-YYYY

3. **Nível 3 - Equipe de Arquitetura**
   - Email: architecture@company.com
   - Slack: #architecture-alerts
   - Telefone: +55-11-ZZZZ-ZZZZ

### Contatos de Emergência

- **Incidentes de Segurança**: security@company.com
- **Privacidade de Dados**: privacy@company.com
- **Jurídico/Compliance**: legal@company.com
- **Escalação Executiva**: executives@company.com

---

**Última Atualização**: $(date)
**Versão**: 1.0
**Próxima Revisão**: $(date -d '+3 months')