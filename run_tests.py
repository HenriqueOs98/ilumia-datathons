#!/usr/bin/env python3
"""
Test Runner for ONS Data Platform
Provides convenient commands to run different test suites
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def run_unit_tests(verbose=False, coverage=True):
    """Run unit tests"""
    cmd = ["python", "-m", "pytest", "tests/unit/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    
    cmd.extend(["-m", "unit"])
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False):
    """Run integration tests"""
    cmd = ["python", "-m", "pytest", "tests/integration/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["-m", "integration"])
    
    return run_command(cmd, "Integration Tests")


def run_performance_tests(verbose=False):
    """Run performance tests"""
    cmd = ["python", "-m", "pytest", "tests/performance/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["-m", "performance", "--durations=0"])
    
    return run_command(cmd, "Performance Tests")


def run_chaos_tests(verbose=False):
    """Run chaos engineering tests"""
    cmd = ["python", "-m", "pytest", "tests/chaos/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["-m", "chaos"])
    
    return run_command(cmd, "Chaos Engineering Tests")


def run_security_tests(verbose=False):
    """Run security and compliance tests"""
    cmd = ["python", "-m", "pytest", "tests/security/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["-m", "security"])
    
    return run_command(cmd, "Security and Compliance Tests")


def run_load_tests(verbose=False):
    """Run load testing scenarios"""
    cmd = ["python", "-m", "pytest", "tests/load/"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend(["-m", "load", "--durations=0"])
    
    return run_command(cmd, "Load Testing Scenarios")


def run_specific_component_tests(component, verbose=False):
    """Run tests for a specific component"""
    component_map = {
        'router': 'tests/unit/test_lambda_router.py',
        'processor': 'tests/unit/test_structured_data_processor.py',
        'rag': 'tests/unit/test_rag_query_processor.py',
        'timestream': 'tests/unit/test_timestream_loader.py',
        'pdf': 'tests/unit/test_batch_pdf_processor.py'
    }
    
    if component not in component_map:
        print(f"❌ Unknown component: {component}")
        print(f"Available components: {', '.join(component_map.keys())}")
        return False
    
    cmd = ["python", "-m", "pytest", component_map[component]]
    
    if verbose:
        cmd.append("-v")
    
    return run_command(cmd, f"{component.title()} Component Tests")


def run_all_tests(verbose=False, fast=False):
    """Run all test suites"""
    success = True
    
    # Unit tests (always run with coverage)
    if not run_unit_tests(verbose=verbose, coverage=True):
        success = False
    
    # Integration tests
    if not run_integration_tests(verbose=verbose):
        success = False
    
    if not fast:
        # Performance tests (skip in fast mode)
        if not run_performance_tests(verbose=verbose):
            success = False
        
        # Chaos tests (skip in fast mode)
        if not run_chaos_tests(verbose=verbose):
            success = False
        
        # Security tests (skip in fast mode)
        if not run_security_tests(verbose=verbose):
            success = False
        
        # Load tests (skip in fast mode)
        if not run_load_tests(verbose=verbose):
            success = False
    
    return success


def run_coverage_report():
    """Generate detailed coverage report"""
    cmd = ["python", "-m", "pytest", "tests/unit/", "--cov=src", "--cov-report=html", "--cov-report=term"]
    
    return run_command(cmd, "Coverage Report Generation")


def run_linting():
    """Run code linting"""
    success = True
    
    # Check if flake8 is available
    try:
        subprocess.run(["flake8", "--version"], check=True, capture_output=True)
        cmd = ["flake8", "src/", "tests/", "--max-line-length=120", "--ignore=E203,W503"]
        if not run_command(cmd, "Code Linting (flake8)"):
            success = False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  flake8 not available, skipping linting")
    
    # Check if black is available
    try:
        subprocess.run(["black", "--version"], check=True, capture_output=True)
        cmd = ["black", "--check", "--diff", "src/", "tests/"]
        if not run_command(cmd, "Code Formatting Check (black)"):
            success = False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  black not available, skipping format check")
    
    return success


def setup_test_environment():
    """Setup test environment"""
    print("Setting up test environment...")
    
    # Install test dependencies
    cmd = ["pip", "install", "-r", "requirements-test.txt"]
    try:
        subprocess.run(cmd, check=True)
        print("✅ Test dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install test dependencies")
        return False
    except FileNotFoundError:
        print("⚠️  requirements-test.txt not found, skipping dependency installation")
    
    # Create necessary directories
    os.makedirs("htmlcov", exist_ok=True)
    os.makedirs("test-results", exist_ok=True)
    
    print("✅ Test environment setup complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="ONS Data Platform Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests (performance, chaos)")
    
    subparsers = parser.add_subparsers(dest="command", help="Test commands")
    
    # Unit tests
    unit_parser = subparsers.add_parser("unit", help="Run unit tests")
    unit_parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    
    # Integration tests
    subparsers.add_parser("integration", help="Run integration tests")
    
    # Performance tests
    subparsers.add_parser("performance", help="Run performance tests")
    
    # Chaos tests
    subparsers.add_parser("chaos", help="Run chaos engineering tests")
    
    # Security tests
    subparsers.add_parser("security", help="Run security and compliance tests")
    
    # Load tests
    subparsers.add_parser("load", help="Run load testing scenarios")
    
    # Component tests
    component_parser = subparsers.add_parser("component", help="Run tests for specific component")
    component_parser.add_argument("name", choices=["router", "processor", "rag", "timestream", "pdf"],
                                help="Component name")
    
    # All tests
    subparsers.add_parser("all", help="Run all test suites")
    
    # Coverage
    subparsers.add_parser("coverage", help="Generate coverage report")
    
    # Linting
    subparsers.add_parser("lint", help="Run code linting")
    
    # Setup
    subparsers.add_parser("setup", help="Setup test environment")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Change to project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    success = True
    
    if args.command == "unit":
        success = run_unit_tests(verbose=args.verbose, coverage=not args.no_coverage)
    elif args.command == "integration":
        success = run_integration_tests(verbose=args.verbose)
    elif args.command == "performance":
        success = run_performance_tests(verbose=args.verbose)
    elif args.command == "chaos":
        success = run_chaos_tests(verbose=args.verbose)
    elif args.command == "security":
        success = run_security_tests(verbose=args.verbose)
    elif args.command == "load":
        success = run_load_tests(verbose=args.verbose)
    elif args.command == "component":
        success = run_specific_component_tests(args.name, verbose=args.verbose)
    elif args.command == "all":
        success = run_all_tests(verbose=args.verbose, fast=args.fast)
    elif args.command == "coverage":
        success = run_coverage_report()
    elif args.command == "lint":
        success = run_linting()
    elif args.command == "setup":
        success = setup_test_environment()
    
    if success:
        print(f"\n🎉 All tests completed successfully!")
        return 0
    else:
        print(f"\n💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())