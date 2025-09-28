#!/bin/bash
# Test runner for EventBridge integration tests

set -e

echo "Setting up test environment for EventBridge integration..."

# Install test dependencies if not already installed
pip install -r ../step_functions/test_requirements.txt 2>/dev/null || echo "Dependencies already installed"

echo "Running EventBridge integration tests..."

# Run tests with verbose output
python -m pytest test_eventbridge_integration.py -v --tb=short

echo "EventBridge integration tests completed successfully!"