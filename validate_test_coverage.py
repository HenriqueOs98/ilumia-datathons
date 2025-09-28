#!/usr/bin/env python3
"""
Test Coverage Validation Script for ONS Data Platform
Validates that all components meet the >90% test coverage requirement
"""

import subprocess
import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse


def run_coverage_analysis():
    """Run comprehensive coverage analysis"""
    print("Running comprehensive test coverage analysis...")
    
    # Run tests with coverage
    cmd = [
        "python", "-m", "pytest", 
        "tests/unit/",
        "--cov=src",
        "--cov-report=xml:coverage.xml",
        "--cov-report=json:coverage.json",
        "--cov-report=term-missing",
        "--cov-fail-under=90"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Coverage analysis completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage analysis failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def parse_coverage_xml():
    """Parse XML coverage report"""
    coverage_file = Path("coverage.xml")
    if not coverage_file.exists():
        print("❌ Coverage XML file not found")
        return None
    
    try:
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        coverage_data = {
            'overall': {
                'line_rate': float(root.get('line-rate', 0)) * 100,
                'branch_rate': float(root.get('branch-rate', 0)) * 100,
                'lines_covered': int(root.get('lines-covered', 0)),
                'lines_valid': int(root.get('lines-valid', 0))
            },
            'packages': {}
        }
        
        for package in root.findall('.//package'):
            package_name = package.get('name')
            coverage_data['packages'][package_name] = {
                'line_rate': float(package.get('line-rate', 0)) * 100,
                'branch_rate': float(package.get('branch-rate', 0)) * 100,
                'classes': {}
            }
            
            for class_elem in package.findall('.//class'):
                class_name = class_elem.get('name')
                coverage_data['packages'][package_name]['classes'][class_name] = {
                    'line_rate': float(class_elem.get('line-rate', 0)) * 100,
                    'branch_rate': float(class_elem.get('branch-rate', 0)) * 100
                }
        
        return coverage_data
    except Exception as e:
        print(f"❌ Error parsing coverage XML: {e}")
        return None


def parse_coverage_json():
    """Parse JSON coverage report"""
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print("❌ Coverage JSON file not found")
        return None
    
    try:
        with open(coverage_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error parsing coverage JSON: {e}")
        return None


def analyze_component_coverage(coverage_data):
    """Analyze coverage by component"""
    if not coverage_data:
        return False
    
    print("\n📊 Component Coverage Analysis:")
    print("=" * 60)
    
    components = [
        'src/lambda_router',
        'src/structured_data_processor', 
        'src/batch_pdf_processor',
        'src/rag_query_processor',
        'src/timestream_loader',
        'src/shared_utils'
    ]
    
    all_components_pass = True
    
    for component in components:
        if 'files' in coverage_data:
            # JSON format
            component_files = {k: v for k, v in coverage_data['files'].items() if component in k}
            
            if component_files:
                total_statements = sum(v['summary']['num_statements'] for v in component_files.values())
                covered_statements = sum(v['summary']['covered_lines'] for v in component_files.values())
                
                if total_statements > 0:
                    coverage_percent = (covered_statements / total_statements) * 100
                else:
                    coverage_percent = 0
                
                status = "✅ PASS" if coverage_percent >= 90 else "❌ FAIL"
                print(f"{component:<35} {coverage_percent:>6.1f}% {status}")
                
                if coverage_percent < 90:
                    all_components_pass = False
                    print(f"   Missing coverage: {90 - coverage_percent:.1f}%")
            else:
                print(f"{component:<35} {'N/A':>6} ⚠️  NO DATA")
    
    return all_components_pass


def generate_coverage_report():
    """Generate detailed coverage report"""
    print("\n📋 Generating detailed coverage report...")
    
    coverage_data = parse_coverage_json()
    if not coverage_data:
        return False
    
    report_lines = [
        "# Test Coverage Report",
        f"Generated: {coverage_data.get('meta', {}).get('timestamp', 'Unknown')}",
        "",
        "## Overall Coverage",
        f"- **Total Coverage**: {coverage_data.get('totals', {}).get('percent_covered', 0):.1f}%",
        f"- **Lines Covered**: {coverage_data.get('totals', {}).get('covered_lines', 0)}",
        f"- **Total Lines**: {coverage_data.get('totals', {}).get('num_statements', 0)}",
        f"- **Missing Lines**: {coverage_data.get('totals', {}).get('missing_lines', 0)}",
        "",
        "## Component Breakdown",
        ""
    ]
    
    # Add component details
    components = {}
    for file_path, file_data in coverage_data.get('files', {}).items():
        component = None
        if 'src/lambda_router' in file_path:
            component = 'Lambda Router'
        elif 'src/structured_data_processor' in file_path:
            component = 'Structured Data Processor'
        elif 'src/batch_pdf_processor' in file_path:
            component = 'Batch PDF Processor'
        elif 'src/rag_query_processor' in file_path:
            component = 'RAG Query Processor'
        elif 'src/timestream_loader' in file_path:
            component = 'Timestream Loader'
        elif 'src/shared_utils' in file_path:
            component = 'Shared Utils'
        
        if component:
            if component not in components:
                components[component] = {
                    'files': [],
                    'total_statements': 0,
                    'covered_lines': 0,
                    'missing_lines': 0
                }
            
            components[component]['files'].append(file_path)
            components[component]['total_statements'] += file_data['summary']['num_statements']
            components[component]['covered_lines'] += file_data['summary']['covered_lines']
            components[component]['missing_lines'] += file_data['summary']['missing_lines']
    
    for component, data in components.items():
        if data['total_statements'] > 0:
            coverage_percent = (data['covered_lines'] / data['total_statements']) * 100
        else:
            coverage_percent = 0
        
        status = "✅" if coverage_percent >= 90 else "❌"
        
        report_lines.extend([
            f"### {component} {status}",
            f"- **Coverage**: {coverage_percent:.1f}%",
            f"- **Files**: {len(data['files'])}",
            f"- **Lines Covered**: {data['covered_lines']}/{data['total_statements']}",
            ""
        ])
    
    # Write report
    with open('coverage_report.md', 'w') as f:
        f.write('\n'.join(report_lines))
    
    print("✅ Coverage report generated: coverage_report.md")
    return True


def validate_test_quality():
    """Validate test quality metrics"""
    print("\n🔍 Validating test quality metrics...")
    
    test_files = list(Path('tests').rglob('test_*.py'))
    
    quality_metrics = {
        'total_test_files': len(test_files),
        'total_test_functions': 0,
        'test_categories': {
            'unit': 0,
            'integration': 0,
            'performance': 0,
            'chaos': 0,
            'security': 0,
            'load': 0
        }
    }
    
    for test_file in test_files:
        try:
            with open(test_file, 'r') as f:
                content = f.read()
                
                # Count test functions
                test_functions = content.count('def test_')
                quality_metrics['total_test_functions'] += test_functions
                
                # Categorize tests
                if 'tests/unit/' in str(test_file):
                    quality_metrics['test_categories']['unit'] += test_functions
                elif 'tests/integration/' in str(test_file):
                    quality_metrics['test_categories']['integration'] += test_functions
                elif 'tests/performance/' in str(test_file):
                    quality_metrics['test_categories']['performance'] += test_functions
                elif 'tests/chaos/' in str(test_file):
                    quality_metrics['test_categories']['chaos'] += test_functions
                elif 'tests/security/' in str(test_file):
                    quality_metrics['test_categories']['security'] += test_functions
                elif 'tests/load/' in str(test_file):
                    quality_metrics['test_categories']['load'] += test_functions
                    
        except Exception as e:
            print(f"⚠️  Error reading {test_file}: {e}")
    
    print(f"📈 Test Quality Metrics:")
    print(f"   Total test files: {quality_metrics['total_test_files']}")
    print(f"   Total test functions: {quality_metrics['total_test_functions']}")
    print(f"   Test categories:")
    for category, count in quality_metrics['test_categories'].items():
        print(f"     {category}: {count}")
    
    # Quality thresholds
    min_total_tests = 100
    min_unit_tests = 50
    min_integration_tests = 10
    
    quality_pass = True
    if quality_metrics['total_test_functions'] < min_total_tests:
        print(f"❌ Insufficient total tests: {quality_metrics['total_test_functions']} < {min_total_tests}")
        quality_pass = False
    
    if quality_metrics['test_categories']['unit'] < min_unit_tests:
        print(f"❌ Insufficient unit tests: {quality_metrics['test_categories']['unit']} < {min_unit_tests}")
        quality_pass = False
    
    if quality_metrics['test_categories']['integration'] < min_integration_tests:
        print(f"❌ Insufficient integration tests: {quality_metrics['test_categories']['integration']} < {min_integration_tests}")
        quality_pass = False
    
    if quality_pass:
        print("✅ Test quality metrics meet requirements")
    
    return quality_pass


def main():
    parser = argparse.ArgumentParser(description="Validate test coverage for ONS Data Platform")
    parser.add_argument("--skip-run", action="store_true", help="Skip running tests, analyze existing coverage")
    parser.add_argument("--report-only", action="store_true", help="Only generate report from existing data")
    
    args = parser.parse_args()
    
    success = True
    
    if not args.report_only and not args.skip_run:
        print("🧪 Running comprehensive test coverage analysis...")
        if not run_coverage_analysis():
            success = False
    
    if not args.report_only:
        # Analyze coverage
        coverage_data = parse_coverage_json()
        if coverage_data:
            if not analyze_component_coverage(coverage_data):
                success = False
        else:
            success = False
    
    # Generate report
    if not generate_coverage_report():
        success = False
    
    # Validate test quality
    if not validate_test_quality():
        success = False
    
    if success:
        print("\n🎉 All coverage and quality requirements met!")
        return 0
    else:
        print("\n💥 Coverage or quality requirements not met!")
        return 1


if __name__ == "__main__":
    sys.exit(main())