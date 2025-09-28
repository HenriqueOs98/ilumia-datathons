#!/bin/bash
"""
Complete Migration Execution Script

This script orchestrates the complete Timestream to InfluxDB migration process
including pre-validation, execution, monitoring, and post-validation.

Requirements addressed: 2.1, 2.2, 2.3
"""

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${SCRIPT_DIR}/migration_config.yaml"
LOG_FILE="migration_execution_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check if required Python packages are installed
    python3 -c "import boto3, yaml, pandas" 2>/dev/null || {
        error "Required Python packages not installed. Run: pip install boto3 pyyaml pandas influxdb-client"
        exit 1
    }
    
    # Check if AWS CLI is configured
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS CLI not configured or credentials not available"
        exit 1
    fi
    
    # Check environment variables
    required_vars=(
        "MIGRATION_ORCHESTRATOR_LAMBDA_ARN"
        "MIGRATION_STATE_MACHINE_ARN"
        "S3_EXPORT_BUCKET"
        "INFLUXDB_URL"
        "INFLUXDB_TOKEN"
        "INFLUXDB_ORG"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    success "Prerequisites check passed"
}

# Function to validate configuration
validate_configuration() {
    log "Validating migration configuration..."
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Run dry-run validation
    if python3 "${SCRIPT_DIR}/execute_migration.py" --config "$CONFIG_FILE" --dry-run; then
        success "Configuration validation passed"
    else
        error "Configuration validation failed"
        exit 1
    fi
}

# Function to execute migration
execute_migration() {
    log "Starting migration execution..."
    
    # Start migration in background and capture PID
    python3 "${SCRIPT_DIR}/execute_migration.py" --config "$CONFIG_FILE" > "migration_output_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
    MIGRATION_PID=$!
    
    log "Migration started with PID: $MIGRATION_PID"
    
    # Wait a moment for migration to initialize
    sleep 10
    
    # Start monitoring in background
    python3 "${SCRIPT_DIR}/monitor_migration.py" --auto-discover --update-interval 30 > "migration_monitor_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
    MONITOR_PID=$!
    
    log "Monitoring started with PID: $MONITOR_PID"
    
    # Wait for migration to complete
    if wait $MIGRATION_PID; then
        success "Migration execution completed successfully"
        
        # Stop monitoring
        kill $MONITOR_PID 2>/dev/null || true
        
        return 0
    else
        error "Migration execution failed"
        
        # Stop monitoring
        kill $MONITOR_PID 2>/dev/null || true
        
        return 1
    fi
}

# Function to validate migration results
validate_results() {
    log "Validating migration results..."
    
    if python3 "${SCRIPT_DIR}/validate_migration.py" --config "$CONFIG_FILE" --parallel; then
        success "Migration validation passed"
        return 0
    else
        error "Migration validation failed"
        return 1
    fi
}

# Function to generate final report
generate_report() {
    log "Generating final migration report..."
    
    REPORT_FILE="migration_final_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$REPORT_FILE" << EOF
# Migration Execution Report

**Execution Date:** $(date)
**Configuration File:** $CONFIG_FILE
**Log File:** $LOG_FILE

## Summary

EOF
    
    if [[ $MIGRATION_SUCCESS -eq 0 && $VALIDATION_SUCCESS -eq 0 ]]; then
        echo "✅ **Overall Status:** SUCCESS" >> "$REPORT_FILE"
    elif [[ $MIGRATION_SUCCESS -eq 0 && $VALIDATION_SUCCESS -ne 0 ]]; then
        echo "⚠️ **Overall Status:** PARTIAL SUCCESS (Migration completed, validation issues)" >> "$REPORT_FILE"
    else
        echo "❌ **Overall Status:** FAILED" >> "$REPORT_FILE"
    fi
    
    cat >> "$REPORT_FILE" << EOF

## Migration Results

- Migration Execution: $([ $MIGRATION_SUCCESS -eq 0 ] && echo "✅ SUCCESS" || echo "❌ FAILED")
- Data Validation: $([ $VALIDATION_SUCCESS -eq 0 ] && echo "✅ SUCCESS" || echo "❌ FAILED")

## Files Generated

- Execution Log: $LOG_FILE
- Migration Output: migration_output_*.log
- Monitor Output: migration_monitor_*.log
- Validation Results: migration_validation_results_*.json
- HTML Report: migration_validation_report_*.html

## Next Steps

EOF
    
    if [[ $MIGRATION_SUCCESS -eq 0 && $VALIDATION_SUCCESS -eq 0 ]]; then
        cat >> "$REPORT_FILE" << EOF
1. Review validation reports for any warnings
2. Update application configurations to use InfluxDB
3. Test application functionality with migrated data
4. Schedule cleanup of temporary migration resources
5. Update monitoring and alerting for InfluxDB
EOF
    else
        cat >> "$REPORT_FILE" << EOF
1. Review error logs to identify issues
2. Address any infrastructure or configuration problems
3. Consider running migration for individual tables
4. Contact support team if issues persist
EOF
    fi
    
    success "Final report generated: $REPORT_FILE"
}

# Function to cleanup on exit
cleanup() {
    log "Cleaning up background processes..."
    
    # Kill any remaining background processes
    if [[ -n "$MIGRATION_PID" ]]; then
        kill $MIGRATION_PID 2>/dev/null || true
    fi
    
    if [[ -n "$MONITOR_PID" ]]; then
        kill $MONITOR_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    log "Starting complete migration execution process"
    log "Project root: $PROJECT_ROOT"
    log "Configuration file: $CONFIG_FILE"
    log "Log file: $LOG_FILE"
    
    # Initialize status variables
    MIGRATION_SUCCESS=1
    VALIDATION_SUCCESS=1
    
    # Step 1: Check prerequisites
    check_prerequisites
    
    # Step 2: Validate configuration
    validate_configuration
    
    # Step 3: Execute migration
    if execute_migration; then
        MIGRATION_SUCCESS=0
        
        # Step 4: Validate results
        if validate_results; then
            VALIDATION_SUCCESS=0
        else
            warning "Migration completed but validation failed"
        fi
    else
        error "Migration execution failed"
    fi
    
    # Step 5: Generate final report
    generate_report
    
    # Final status
    if [[ $MIGRATION_SUCCESS -eq 0 && $VALIDATION_SUCCESS -eq 0 ]]; then
        success "Complete migration process finished successfully!"
        exit 0
    elif [[ $MIGRATION_SUCCESS -eq 0 ]]; then
        warning "Migration completed with validation issues"
        exit 1
    else
        error "Migration process failed"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--config CONFIG_FILE] [--help]"
            echo ""
            echo "Options:"
            echo "  --config CONFIG_FILE    Path to migration configuration file"
            echo "  --help                  Show this help message"
            echo ""
            echo "Environment variables required:"
            echo "  MIGRATION_ORCHESTRATOR_LAMBDA_ARN"
            echo "  MIGRATION_STATE_MACHINE_ARN"
            echo "  S3_EXPORT_BUCKET"
            echo "  INFLUXDB_URL"
            echo "  INFLUXDB_TOKEN"
            echo "  INFLUXDB_ORG"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main