# Plataforma de Dados ONS

## Visão Geral

A Plataforma de Dados ONS é uma solução completa para processamento, armazenamento e análise de dados de energia elétrica do Sistema Interligado Nacional (SIN). A plataforma utiliza tecnologias AWS modernas para fornecer insights em tempo real sobre geração, consumo e transmissão de energia.

## 🚀 Funcionalidades Principais

- **Processamento de Dados em Tempo Real**: Ingestão e processamento automático de dados de energia
- **Armazenamento de Séries Temporais**: Utiliza Amazon Timestream for InfluxDB para armazenamento otimizado
- **API de Consultas Inteligentes**: Suporte a linguagem natural, Flux e InfluxQL
- **Base de Conhecimento RAG**: Integração com Amazon Bedrock para consultas contextuais
- **Monitoramento Avançado**: Dashboards e alertas em tempo real
- **Implantação Blue-Green**: Estratégias de implantação seguras com rollback automático

## 🏗️ Arquitetura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Dados Brutos  │───▶│  Processamento   │───▶│  InfluxDB       │
│   (S3)          │    │  (Lambda)        │    │  (Timestream)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │◀───│  Query Processor │◀───│  Base de        │
│                 │    │  (Lambda)        │    │  Conhecimento   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 Pré-requisitos

- AWS CLI configurado
- Python 3.11+
- Terraform >= 1.0
- Docker (para desenvolvimento local)
- Node.js 18+ (para ferramentas de build)

## 🛠️ Instalação e Configuração

### 1. Clonar o Repositório

```bash
git clone https://github.com/ons/data-platform.git
cd data-platform
```

### 2. Configurar Ambiente

```bash
# Criar ambiente virtual Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configurar AWS

```bash
# Configurar credenciais AWS
aws configure

# Definir variáveis de ambiente
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
```

### 4. Implantar Infraestrutura

```bash
# Inicializar Terraform
cd infrastructure
terraform init

# Planejar implantação
terraform plan -var-file="environments/dev.tfvars"

# Aplicar mudanças
terraform apply -var-file="environments/dev.tfvars"
```

## 🚀 Uso Rápido

### Consultas via API

```bash
# Consulta em linguagem natural
curl -X POST "https://api.ons-platform.com/query" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "question": "Qual é a geração hidrelétrica atual na região sudeste?"
  }'

# Consulta Flux direta
curl -X POST "https://api.ons-platform.com/query/flux" \
  -H "Content-Type: application/json" \
  -H "x-api-key: SUA_CHAVE_API" \
  -d '{
    "query": "from(bucket: \"energy_data\") |> range(start: -1h) |> filter(fn: (r) => r[\"region\"] == \"sudeste\")"
  }'
```

### Verificação de Saúde

```bash
# Verificar saúde do sistema
python scripts/rollback.py --action health-check \
  --functions lambda_router structured_data_processor rag_query_processor influxdb_loader

# Verificar performance InfluxDB
python scripts/validate_influxdb_performance.py --health-check-only
```

## 📊 Monitoramento

### Dashboards Disponíveis

- **Dashboard Principal**: Visão geral do sistema
- **Performance InfluxDB**: Métricas específicas do banco de dados
- **API Analytics**: Estatísticas de uso da API
- **Processamento de Dados**: Status do pipeline de dados

### Alertas Configurados

- Taxa de erro > 5%
- Latência > 10 segundos
- Falhas de conexão InfluxDB
- Uso de memória > 80%

## 🔧 Desenvolvimento

### Estrutura do Projeto

```
├── src/                          # Código fonte
│   ├── lambda_router/           # Roteador de arquivos
│   ├── structured_data_processor/ # Processador de dados estruturados
│   ├── influxdb_loader/         # Carregador InfluxDB
│   ├── timeseries_query_processor/ # Processador de consultas
│   ├── rag_query_processor/     # Processador RAG
│   └── shared_utils/            # Utilitários compartilhados
├── tests/                       # Testes automatizados
├── infrastructure/              # Código Terraform
├── docs/                        # Documentação
├── scripts/                     # Scripts de automação
└── .github/workflows/           # CI/CD GitHub Actions
```

### Executar Testes

```bash
# Testes unitários
pytest tests/unit/ -v

# Testes de integração
pytest tests/integration/ -v

# Testes de performance
python scripts/validate_influxdb_performance.py

# Cobertura de código
pytest --cov=src tests/
```

### Desenvolvimento Local

```bash
# Iniciar ambiente local
docker-compose up -d

# Executar função Lambda localmente
sam local start-api

# Monitorar logs
aws logs tail /aws/lambda/lambda_router --follow
```

## 📚 Documentação

### Documentação Principal (Português)

- [Manual de Operações](docs/manual-operacoes.md)
- [Documentação da API](docs/documentacao-api-influxdb.md)
- [Manual de Operações InfluxDB](docs/manual-operacoes-influxdb.md)
- [Procedimentos de Rollback](docs/procedimentos-rollback-influxdb.md)
- [Guia de Implantação](docs/guia-implantacao.md)

### Documentação em Inglês

- [Operations Runbook](docs/operations-runbook.md)
- [API Documentation](docs/api-documentation-influxdb.md)
- [InfluxDB Operations](docs/influxdb-operations-runbook.md)
- [Rollback Procedures](docs/influxdb-rollback-procedures.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## 🔄 CI/CD

### Pipeline Automatizado

1. **Trigger**: Push para branch `main`
2. **Segurança**: Scan de vulnerabilidades
3. **Testes**: Unitários e integração
4. **Build**: Empacotamento de artefatos
5. **Deploy**: Implantação blue-green
6. **Validação**: Testes de saúde pós-implantação

### Comandos de Implantação

```bash
# Implantação manual
python scripts/deploy.py \
  --function-name lambda_router \
  --version 5 \
  --canary-percentage 10

# Rollback de emergência
python scripts/rollback.py --action rollback-function \
  --function-name lambda_router

# Gerenciar feature flags
python scripts/deploy.py --action update-flag \
  --flag-name enable_new_api_endpoint \
  --enabled true
```

## 🛡️ Segurança

### Práticas Implementadas

- **Criptografia**: Dados em repouso e em trânsito
- **IAM**: Princípio do menor privilégio
- **VPC**: Isolamento de rede
- **Secrets Manager**: Gerenciamento seguro de credenciais
- **CloudTrail**: Auditoria completa de ações

### Verificações de Segurança

```bash
# Scan de vulnerabilidades
bandit -r src/

# Auditoria de dependências
pip audit

# Verificar configurações de segurança
python scripts/security-check.py
```

## 💰 Otimização de Custos

### Estratégias Implementadas

- **Lifecycle Policies**: Transição automática para storage classes mais baratas
- **Spot Instances**: Para processamento batch não crítico
- **Auto Scaling**: Ajuste automático de recursos
- **Reserved Instances**: Para cargas de trabalho previsíveis

### Monitoramento de Custos

```bash
# Verificar custos atuais
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost

# Relatório de otimização
python scripts/cost-optimization-report.py
```

## 🤝 Contribuição

### Como Contribuir

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

### Padrões de Código

- **Python**: Seguir PEP 8
- **Documentação**: Docstrings obrigatórias
- **Testes**: Cobertura mínima de 80%
- **Commits**: Mensagens descritivas em português

## 📞 Suporte

### Contatos da Equipe

- **Operações**: ops-team@ons.org.br
- **Desenvolvimento**: dev-team@ons.org.br
- **Arquitetura**: arch-team@ons.org.br

### Canais de Comunicação

- **Slack**: #ons-data-platform
- **Email**: data-platform@ons.org.br
- **Issues**: GitHub Issues

### Escalação de Emergência

1. **Nível 1**: Equipe de Operações (+55 11 XXXX-XXXX)
2. **Nível 2**: Equipe de Engenharia (+55 11 YYYY-YYYY)
3. **Nível 3**: Arquitetura/Liderança (+55 11 ZZZZ-ZZZZ)

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🔄 Changelog

### v2.0.0 - Migração InfluxDB (2024-01-15)
- ✅ Migração completa para Amazon Timestream for InfluxDB
- ✅ Suporte a consultas Flux e InfluxQL
- ✅ API aprimorada com tradução de linguagem natural
- ✅ Performance melhorada em 60% nas consultas
- ✅ Documentação completa em português

### v1.5.0 - Melhorias de Performance (2023-12-01)
- ✅ Otimização de consultas Timestream
- ✅ Cache de resultados implementado
- ✅ Monitoramento aprimorado

### v1.0.0 - Release Inicial (2023-10-01)
- ✅ Pipeline de dados completo
- ✅ API REST funcional
- ✅ Integração com Knowledge Base
- ✅ Implantação automatizada

---

**Desenvolvido com ❤️ pela Equipe ONS**

**Última Atualização**: $(date)
**Versão**: 2.0.0-influxdb