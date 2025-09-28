#!/bin/bash
# Test runner for Step Functions state machine integration tests

set -e

echo "Setting up test environment..."

# Install test dependencies
pip install -r test_requirements.txt

echo "Running Step Functions state machine tests..."

# Run tests with verbose output
python -m pytest test_state_machine.py -v --tb=short

echo "All tests completed successfully!"