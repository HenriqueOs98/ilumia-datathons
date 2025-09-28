# Source Code

This directory contains the application source code for the ONS Data Platform, implementing serverless data processing and AI-powered querying capabilities.

## 🏗️ Architecture Overview

The source code is organized into modular components that handle different aspects of the data processing pipeline:

- **Data Routing**: Intelligent file routing based on type and size
- **Data Processing**: Specialized processors for different file formats
- **AI/ML Integration**: RAG-based query processing using Amazon Bedrock
- **Time Series Loading**: Efficient data loading into Amazon Timestream
- **Shared Utilities**: Common functionality across all components

## 📁 Structure

```
src/
├── batch_pdf_processor/       # PDF processing container
├── lambda_router/            # File routing logic (placeholder)
├── rag_query_processor/      # RAG query handling
├── shared_utils/             # Common utilities
├── structured_data_processor/ # CSV/XLSX processing
└── timestream_loader/        # Time series data loading
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- AWS CLI configured
- Docker (for PDF processing)

### Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Install development dependencies
pip install -r requirements-test.txt

# Run all tests
python -m pytest src/ -v --cov=src
```

## 🔧 Component Documentation

### Batch PDF Processor (`batch_pdf_processor/`)
**Purpose**: Processes PDF files using specialized libraries in a containerized environment.

### RAG Query Processor (`rag_query_processor/`)
**Purpose**: Handles natural language queries using Amazon Bedrock and Knowledge Bases.

### Shared Utilities (`shared_utils/`)
**Purpose**: Common functionality used across all components.

### Structured Data Processor (`structured_data_processor/`)
**Purpose**: Processes CSV and XLSX files using pandas and AWS Data Wrangler.

### Timestream Loader (`timestream_loader/`)
**Purpose**: Loads processed data into Amazon Timestream for time series analysis.

## 🧪 Testing

```bash
# Run all tests
python -m pytest src/ -v

# Run specific component tests
python -m pytest src/batch_pdf_processor/ -v

# Run with coverage
python -m pytest src/ --cov=src --cov-report=html
```

## 🔒 Security Best Practices

- Input validation for all components
- Comprehensive error handling with logging
- AWS Secrets Manager for sensitive data
- Structured logging for monitoring

## 🚀 Deployment

Components are automatically deployed via GitHub Actions when changes are detected in the `src/` directory.

---

**Maintained by**: Development Team