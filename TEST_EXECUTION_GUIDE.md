# ONS Data Platform - Test Execution Guide

## Overview

This guide provides comprehensive instructions for executing the test suites for the ONS Data Platform. The testing framework includes unit tests, integration tests, performance tests, chaos engineering tests, security tests, and load tests, all designed to achieve >90% code coverage and ensure system reliability.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_lambda_router.py
│   ├── test_structured_data_processor.py
│   ├── test_batch_pdf_processor.py
│   ├── test_rag_query_processor.py
│   └── test_timestream_loader.py
├── integration/             # End-to-end integration tests
│   └── test_end_to_end_workflows.py
├── performance/             # Performance and load testing
│   └── test_api_performance.py
├── chaos/                   # Chaos engineering tests
│   └── test_failure_scenarios.py
├── security/                # Security and compliance tests
│   ├── test_security_compliance.py
│   ├── test_owasp_zap_integration.py
│   ├── test_infrastructure_compliance.py
│   └── test_disaster_recovery.py
└── load/                    # Load testing scenarios
    └── test_load_scenarios.py
```

## Prerequisites

### 1. Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### 2. Environment Setup

Set up the following environment variables for testing:

```bash
export PROCESSED_BUCKET=ons-data-platform-processed-test
export FAILED_BUCKET=ons-data-platform-failed-test
export KNOWLEDGE_BASE_ID=test-kb-id
export TIMESTREAM_DATABASE_NAME=ons_energy_data_test
export GENERATION_TABLE_NAME=generation_data_test
export CONSUMPTION_TABLE_NAME=consumption_data_test
export TRANSMISSION_TABLE_NAME=transmission_data_test
```

### 3. AWS Credentials (for integration tests)

Ensure AWS credentials are configured for integration tests that require AWS services.

## Test Execution Commands

### Quick Test Execution

```bash
# Run all tests with coverage
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run fast tests (skip performance and chaos)
python run_tests.py all --fast
```

### Detailed Test Categories

#### 1. Unit Tests (>90% Coverage Target)

```bash
# Run all unit tests with coverage report
python run_tests.py unit

# Run specific component tests
python run_tests.py component router
python run_tests.py component processor
python run_tests.py component rag
python run_tests.py component timestream
python run_tests.py component pdf

# Run unit tests with detailed coverage
pytest tests/unit/ --cov=src --cov-report=html --cov-report=term-missing --cov-fail-under=90
```

#### 2. Integration Tests

```bash
# Run integration tests
python run_tests.py integration

# Run specific integration scenarios
pytest tests/integration/test_end_to_end_workflows.py::TestCompleteDataProcessingWorkflow -v
pytest tests/integration/test_end_to_end_workflows.py::TestRAGQueryProcessingWorkflow -v
```

#### 3. Performance Tests

```bash
# Run performance tests
python run_tests.py performance

# Run specific performance scenarios
pytest tests/performance/test_api_performance.py::TestAPIPerformanceBaseline -v
pytest tests/performance/test_api_performance.py::TestConcurrentLoadTesting -v
```

#### 4. Chaos Engineering Tests

```bash
# Run chaos engineering tests
python run_tests.py chaos

# Run specific failure scenarios
pytest tests/chaos/test_failure_scenarios.py::TestAWSServiceFailures -v
pytest tests/chaos/test_failure_scenarios.py::TestDataCorruptionScenarios -v
```

#### 5. Security and Compliance Tests

```bash
# Run security tests
python run_tests.py security

# Run specific security test categories
pytest tests/security/test_security_compliance.py -v
pytest tests/security/test_owasp_zap_integration.py -v
pytest tests/security/test_infrastructure_compliance.py -v
pytest tests/security/test_disaster_recovery.py -v
```

#### 6. Load Testing

```bash
# Run load tests
python run_tests.py load

# Run specific load scenarios
pytest tests/load/test_load_scenarios.py::TestHighVolumeDataProcessing -v
pytest tests/load/test_load_scenarios.py::TestConcurrencyStressTests -v
```

## Coverage Validation

### Automated Coverage Validation

```bash
# Run comprehensive coverage analysis
python validate_test_coverage.py

# Generate coverage report only
python validate_test_coverage.py --report-only

# Skip test execution, analyze existing coverage
python validate_test_coverage.py --skip-run
```

### Manual Coverage Analysis

```bash
# Generate detailed HTML coverage report
pytest tests/unit/ --cov=src --cov-report=html:htmlcov

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Configuration

### Pytest Configuration (pytest.ini)

Key configuration options:
- **Coverage Target**: 90% minimum
- **Test Timeout**: 300 seconds
- **Parallel Execution**: Supported with pytest-xdist
- **Test Markers**: Organized by category (unit, integration, performance, etc.)

### Test Markers

Use markers to run specific test categories:

```bash
# Run only unit tests
pytest -m unit

# Run only AWS-related tests
pytest -m aws

# Run only performance tests
pytest -m performance

# Run only security tests
pytest -m security

# Exclude slow tests
pytest -m "not slow"
```

## Continuous Integration

### GitHub Actions Integration

The test suite is designed to integrate with GitHub Actions:

```yaml
# Example workflow step
- name: Run Unit Tests
  run: python run_tests.py unit --verbose

- name: Run Integration Tests
  run: python run_tests.py integration --verbose

- name: Validate Coverage
  run: python validate_test_coverage.py
```

### Test Execution Strategy

1. **Pull Request Tests**: Unit + Integration + Security
2. **Nightly Tests**: All test categories including performance and chaos
3. **Release Tests**: Full test suite with extended chaos scenarios

## Test Data Management

### Mock Data

Tests use mock data and services to ensure:
- **Isolation**: No external dependencies
- **Speed**: Fast test execution
- **Reliability**: Consistent test results

### Test Fixtures

Common test fixtures are provided for:
- AWS service mocking (using moto)
- Sample data generation
- Test environment setup

## Troubleshooting

### Common Issues

#### 1. Coverage Below 90%

```bash
# Identify uncovered lines
pytest tests/unit/ --cov=src --cov-report=term-missing

# Generate detailed HTML report
pytest tests/unit/ --cov=src --cov-report=html
```

#### 2. Test Timeouts

```bash
# Run with increased timeout
pytest --timeout=600 tests/performance/

# Run specific slow tests
pytest -m slow --timeout=900
```

#### 3. AWS Service Mocking Issues

```bash
# Ensure moto is properly installed
pip install moto[all]

# Check mock service initialization
pytest tests/unit/test_timestream_loader.py -v -s
```

#### 4. Memory Issues in Load Tests

```bash
# Run load tests with memory monitoring
pytest tests/load/ --verbose --tb=short
```

### Debug Mode

```bash
# Run tests in debug mode
pytest --pdb tests/unit/test_lambda_router.py::TestFileInfoExtraction::test_extract_s3_event_records

# Run with detailed output
pytest -vvv -s tests/unit/
```

## Performance Benchmarks

### Expected Performance Metrics

- **Unit Tests**: < 2 minutes total execution
- **Integration Tests**: < 5 minutes total execution
- **Performance Tests**: < 10 minutes total execution
- **Full Test Suite**: < 30 minutes total execution

### Coverage Targets

- **Overall Coverage**: ≥ 90%
- **Component Coverage**: ≥ 90% per component
- **Critical Path Coverage**: ≥ 95%

## Security Testing

### OWASP ZAP Integration

For security testing with OWASP ZAP:

1. **Install OWASP ZAP**:
   ```bash
   # Using Docker
   docker run -d -p 8080:8080 owasp/zap2docker-stable zap.sh -daemon -host 0.0.0.0 -port 8080
   ```

2. **Run Security Tests**:
   ```bash
   pytest tests/security/test_owasp_zap_integration.py -v
   ```

### Compliance Testing

Run compliance tests for various frameworks:

```bash
# GDPR compliance
pytest tests/security/test_security_compliance.py::TestDataProtectionCompliance -v

# ISO 27001 compliance
pytest tests/security/test_infrastructure_compliance.py::TestComplianceFrameworks -v

# NIST Cybersecurity Framework
pytest tests/security/test_infrastructure_compliance.py::TestComplianceFrameworks::test_nist_cybersecurity_framework -v
```

## Reporting

### Test Reports

Generate comprehensive test reports:

```bash
# HTML report
pytest --html=test_report.html --self-contained-html

# JSON report
pytest --json-report --json-report-file=test_report.json

# JUnit XML (for CI/CD)
pytest --junitxml=test_results.xml
```

### Coverage Reports

Multiple coverage report formats:

```bash
# Terminal report
pytest --cov=src --cov-report=term

# HTML report
pytest --cov=src --cov-report=html

# XML report (for CI/CD)
pytest --cov=src --cov-report=xml
```

## Best Practices

### Writing Tests

1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Use Descriptive Names**: Test names should describe the scenario
3. **Mock External Dependencies**: Use moto for AWS services
4. **Test Edge Cases**: Include boundary conditions and error scenarios
5. **Maintain Test Independence**: Tests should not depend on each other

### Test Maintenance

1. **Regular Updates**: Keep tests updated with code changes
2. **Performance Monitoring**: Monitor test execution times
3. **Coverage Monitoring**: Maintain >90% coverage
4. **Documentation**: Keep test documentation current

## Support

For questions or issues with the test suite:

1. Check this guide for common solutions
2. Review test logs for specific error messages
3. Consult the test code for implementation details
4. Refer to the requirements and design documents for context

## Conclusion

This comprehensive test suite ensures the ONS Data Platform meets high standards for:

- **Reliability**: Through extensive unit and integration testing
- **Performance**: Through load and performance testing
- **Security**: Through security and compliance testing
- **Resilience**: Through chaos engineering testing
- **Quality**: Through >90% code coverage requirements

Regular execution of these tests helps maintain system quality and reliability throughout the development lifecycle.