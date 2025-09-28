# ONS Data Platform

A serverless data platform for processing and analyzing Brazilian electrical sector data from ONS (Operador Nacional do Sistema Elétrico).

## 🏗️ Architecture

This platform implements a serverless, event-driven architecture on AWS for processing various data formats (CSV, XLSX, PDF) from ONS and providing intelligent query capabilities through a RAG (Retrieval-Augmented Generation) system.

### Key Components

- **Data Ingestion**: S3 + EventBridge for automated file processing
- **Processing**: Lambda functions + AWS Batch for different data types
- **Storage**: S3 Data Lake + Amazon Timestream for time series
- **AI/ML**: Amazon Bedrock + Knowledge Bases for intelligent querying
- **API**: API Gateway + Lambda for REST endpoints
- **Monitoring**: CloudWatch + SNS for comprehensive observability
- **Deployment**: CodeDeploy + AppConfig for blue-green deployments

## 🚀 Features

- **Automated Data Processing**: Event-driven processing of CSV, XLSX, and PDF files
- **Time Series Storage**: Amazon Timestream for high-performance time series data
- **Intelligent Querying**: RAG system using Amazon Bedrock and Knowledge Bases
- **Scalable Architecture**: Serverless components that scale automatically
- **Cost Optimization**: Pay-per-use model with intelligent resource management
- **Blue-Green Deployments**: Zero-downtime deployments with automatic rollback
- **Feature Flags**: Controlled rollouts using AWS AppConfig
- **Comprehensive Monitoring**: Real-time metrics and alerting

## 📁 Repository Structure

```
├── .github/workflows/          # CI/CD pipelines
├── docs/                      # Documentation
├── infra/                     # Terraform infrastructure code
│   ├── modules/              # Reusable Terraform modules
│   │   ├── api_gateway/      # API Gateway configuration
│   │   ├── appconfig/        # Feature flags and configuration
│   │   ├── codedeploy/       # Blue-green deployment setup
│   │   ├── eventbridge/      # Event routing
│   │   ├── knowledge_base/   # RAG system components
│   │   ├── lambda/           # Lambda functions
│   │   ├── monitoring/       # CloudWatch and alerting
│   │   ├── s3/              # Data lake storage
│   │   ├── step_functions/   # Workflow orchestration
│   │   └── timestream/       # Time series database
│   ├── environments/         # Environment-specific configs
│   ├── main.tf              # Main infrastructure definition
│   ├── variables.tf         # Input variables
│   └── outputs.tf           # Output values
├── scripts/                  # Deployment and utility scripts
├── src/                     # Application source code
│   ├── batch_pdf_processor/ # PDF processing container
│   ├── lambda_router/       # File routing logic
│   ├── rag_query_processor/ # RAG query handling
│   ├── shared_utils/        # Common utilities
│   ├── structured_data_processor/ # CSV/XLSX processing
│   └── timestream_loader/   # Time series data loading
└── tests/                   # Test suites
    ├── integration/         # End-to-end tests
    ├── performance/         # Load testing
    ├── security/           # Security compliance tests
    └── unit/               # Unit tests
```

## 🛠️ Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- Python 3.11+
- Docker (for local development)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ons-data-platform

# Install Python dependencies
pip install -r requirements-test.txt

# Setup pre-commit hooks
pre-commit install
```

### 2. Deploy Infrastructure

```bash
cd infra

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file="environments/dev.tfvars"

# Deploy
terraform apply -var-file="environments/dev.tfvars"
```

### 3. Test the Platform

```bash
# Run unit tests
python -m pytest tests/unit/ -v

# Run integration tests
python -m pytest tests/integration/ -v

# Upload test data
aws s3 cp sample-data/ s3://ons-data-platform-raw-dev/ --recursive
```

## 🔧 Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements-test.txt

# Run tests with coverage
python -m pytest --cov=src tests/
```

### Adding New Components

1. **Lambda Functions**: Add to `src/` directory with tests
2. **Infrastructure**: Create modules in `infra/modules/`
3. **Tests**: Add comprehensive test coverage
4. **Documentation**: Update relevant docs

### Code Quality

- **Linting**: `flake8`, `black`, `isort`
- **Security**: `bandit`, `safety`
- **Type Checking**: `mypy`
- **Testing**: `pytest` with coverage

## 🚢 Deployment

### Automated Deployment (Recommended)

Push to `main` branch triggers automatic deployment:

1. **Security Scanning**: CodeQL, Snyk, Checkov
2. **Testing**: Unit, integration, and security tests
3. **Building**: Package Lambda functions and containers
4. **Deployment**: Blue-green deployment with canary releases
5. **Monitoring**: Automatic rollback on errors

### Manual Deployment

```bash
# Deploy specific function
python scripts/deploy.py \
  --function-name lambda_router \
  --version 5 \
  --deployment-group lambda_router-deployment-group

# Emergency rollback
python scripts/rollback.py --action rollback-function \
  --function-name lambda_router
```

## 📊 Monitoring

### Key Metrics

- **Processing Success Rate**: > 95%
- **API Response Time**: < 2 seconds
- **Error Rate**: < 5%
- **Cost per GB Processed**: Tracked monthly

### Dashboards

- **Operational**: Real-time system health
- **Business**: Data processing volumes and trends
- **Cost**: Resource utilization and spending

### Alerts

- **Critical**: System failures, high error rates
- **Warning**: Performance degradation, cost anomalies
- **Info**: Deployment status, maintenance windows

## 🔒 Security

### Security Features

- **Encryption**: At rest and in transit
- **IAM**: Least privilege access
- **VPC**: Network isolation
- **Secrets**: AWS Secrets Manager
- **Compliance**: SOC 2, GDPR ready

### Security Testing

- **SAST**: Static analysis with CodeQL
- **DAST**: Dynamic testing with OWASP ZAP
- **Dependency**: Vulnerability scanning with Snyk
- **Infrastructure**: Compliance with Checkov

## 📚 Documentation

- [🏗️ Architecture Guide](docs/architecture.md) - System design and components
- [🚀 API Documentation](docs/api.md) - REST API reference
- [👨‍💻 Development Guide](docs/development.md) - Local development setup
- [🚢 Deployment Guide](docs/deployment-guide.md) - Deployment and rollback procedures
- [🔧 Operations Runbook](docs/operations-runbook.md) - Maintenance and troubleshooting
- [🧪 Testing Guide](docs/testing.md) - Testing strategies and procedures
- [🔒 Security Guide](docs/security.md) - Security best practices

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the full test suite
5. Submit a pull request

### Contribution Guidelines

- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Ensure all CI checks pass

## 📈 Performance

### Benchmarks

- **CSV Processing**: 1GB in ~30 seconds
- **PDF Processing**: 100 pages in ~2 minutes
- **API Response**: 95th percentile < 2 seconds
- **Concurrent Users**: 1000+ supported

### Optimization

- **Caching**: Intelligent caching strategies
- **Batching**: Optimal batch sizes for processing
- **Partitioning**: Efficient data partitioning
- **Scaling**: Auto-scaling based on demand

## 💰 Cost Management

### Cost Optimization Features

- **Serverless**: Pay only for what you use
- **Spot Instances**: For batch processing
- **Lifecycle Policies**: Automatic data archiving
- **Resource Tagging**: Detailed cost tracking

### Typical Costs (Monthly)

- **Small Workload** (< 1GB/day): $50-100
- **Medium Workload** (1-10GB/day): $200-500
- **Large Workload** (> 10GB/day): $500-2000

## 🆘 Support

### Getting Help

1. **Documentation**: Check the docs/ directory
2. **Issues**: Create a GitHub issue
3. **Discussions**: Use GitHub Discussions
4. **Emergency**: Follow the incident response procedures

### Troubleshooting

- [Operations Runbook](docs/operations-runbook.md)
- [Common Issues](docs/troubleshooting.md)
- [Performance Tuning](docs/performance.md)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- ONS (Operador Nacional do Sistema Elétrico) for providing open data
- AWS for the serverless platform
- Open source community for the tools and libraries used

---

**Built with ❤️ for the Brazilian energy sector**