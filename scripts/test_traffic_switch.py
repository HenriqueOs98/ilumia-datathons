#!/usr/bin/env python3
"""
Test script for traffic switching functionality.

This script validates that the traffic switching components are working correctly
by testing feature flag retrieval, backend determination, and performance monitoring.
"""

import json
import logging
import sys
import time
from typing import Dict, Any
import os

# Add src to path for testing
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from shared_utils.traffic_switch import (
        TrafficSwitchManager,
        DatabaseBackend,
        get_traffic_switch_manager
    )
except ImportError as e:
    print(f"Failed to import traffic switch utilities: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_traffic_switch_manager():
    """Test TrafficSwitchManager functionality."""
    print("=" * 60)
    print("Testing TrafficSwitchManager")
    print("=" * 60)
    
    try:
        # Initialize manager
        manager = TrafficSwitchManager(
            app_name='test-app',
            environment='development'
        )
        
        print(f"✅ TrafficSwitchManager initialized successfully")
        print(f"   App: {manager.app_name}")
        print(f"   Environment: {manager.environment}")
        
        # Test configuration retrieval (will use defaults if AppConfig not available)
        try:
            config = manager._get_configuration()
            print(f"✅ Configuration retrieved successfully")
            print(f"   Config keys: {list(config.keys())}")
        except Exception as e:
            print(f"⚠️  Configuration retrieval failed (expected in test environment): {e}")
            print("   Using default configuration")
        
        # Test feature flag methods
        ingestion_enabled = manager.should_use_influxdb_for_ingestion()
        queries_enabled = manager.should_use_influxdb_for_queries()
        traffic_percentage = manager.get_traffic_percentage()
        
        print(f"✅ Feature flags retrieved:")
        print(f"   InfluxDB ingestion enabled: {ingestion_enabled}")
        print(f"   InfluxDB queries enabled: {queries_enabled}")
        print(f"   Traffic percentage: {traffic_percentage}%")
        
        # Test backend determination
        backend = manager.determine_backend_for_query("test-user-123")
        print(f"✅ Backend determination: {backend.value}")
        
        # Test performance metrics
        manager.record_performance_metric(DatabaseBackend.INFLUXDB, 150.5, True)
        manager.record_performance_metric(DatabaseBackend.TIMESTREAM, 200.0, True)
        manager.record_performance_metric(DatabaseBackend.INFLUXDB, 300.0, False)
        
        performance_summary = manager.get_performance_summary()
        print(f"✅ Performance metrics recorded:")
        for backend, metrics in performance_summary.items():
            print(f"   {backend}: {metrics}")
        
        # Test health check
        health = manager.health_check()
        print(f"✅ Health check completed:")
        print(f"   Status: {health['status']}")
        print(f"   Components: {list(health['components'].keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ TrafficSwitchManager test failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions."""
    print("\n" + "=" * 60)
    print("Testing Convenience Functions")
    print("=" * 60)
    
    try:
        from shared_utils.traffic_switch import (
            should_use_influxdb_for_ingestion,
            should_use_influxdb_for_queries,
            determine_backend_for_query,
            record_performance_metric
        )
        
        # Test convenience functions
        ingestion = should_use_influxdb_for_ingestion()
        queries = should_use_influxdb_for_queries()
        backend = determine_backend_for_query("test-user-456")
        
        print(f"✅ Convenience functions work:")
        print(f"   should_use_influxdb_for_ingestion(): {ingestion}")
        print(f"   should_use_influxdb_for_queries(): {queries}")
        print(f"   determine_backend_for_query(): {backend.value}")
        
        # Test performance recording
        record_performance_metric(DatabaseBackend.INFLUXDB, 125.0, True)
        print(f"✅ Performance metric recorded via convenience function")
        
        return True
        
    except Exception as e:
        print(f"❌ Convenience functions test failed: {e}")
        return False


def test_backend_determination_consistency():
    """Test that backend determination is consistent for the same user."""
    print("\n" + "=" * 60)
    print("Testing Backend Determination Consistency")
    print("=" * 60)
    
    try:
        manager = get_traffic_switch_manager()
        
        # Test consistency for the same user
        user_id = "consistent-user-test"
        backends = []
        
        for i in range(10):
            backend = manager.determine_backend_for_query(user_id)
            backends.append(backend)
        
        # All backends should be the same for the same user
        unique_backends = set(backends)
        if len(unique_backends) == 1:
            print(f"✅ Backend determination is consistent for user {user_id}")
            print(f"   Backend: {backends[0].value}")
        else:
            print(f"❌ Backend determination is inconsistent for user {user_id}")
            print(f"   Backends: {[b.value for b in unique_backends]}")
            return False
        
        # Test different users get potentially different backends
        different_users = [f"user-{i}" for i in range(5)]
        user_backends = {}
        
        for user in different_users:
            backend = manager.determine_backend_for_query(user)
            user_backends[user] = backend
        
        print(f"✅ Different users backend assignment:")
        for user, backend in user_backends.items():
            print(f"   {user}: {backend.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend determination consistency test failed: {e}")
        return False


def test_performance_metrics():
    """Test performance metrics functionality."""
    print("\n" + "=" * 60)
    print("Testing Performance Metrics")
    print("=" * 60)
    
    try:
        manager = get_traffic_switch_manager()
        
        # Clear existing metrics
        manager._performance_metrics = {
            'timestream': {'total_requests': 0, 'total_time': 0, 'errors': 0},
            'influxdb': {'total_requests': 0, 'total_time': 0, 'errors': 0}
        }
        
        # Record various metrics
        test_metrics = [
            (DatabaseBackend.INFLUXDB, 100.0, True),
            (DatabaseBackend.INFLUXDB, 150.0, True),
            (DatabaseBackend.INFLUXDB, 200.0, False),  # Error
            (DatabaseBackend.TIMESTREAM, 120.0, True),
            (DatabaseBackend.TIMESTREAM, 180.0, True),
        ]
        
        for backend, response_time, success in test_metrics:
            manager.record_performance_metric(backend, response_time, success)
        
        # Get performance summary
        summary = manager.get_performance_summary()
        
        print(f"✅ Performance metrics summary:")
        for backend_name, metrics in summary.items():
            print(f"   {backend_name}:")
            print(f"     Total requests: {metrics['total_requests']}")
            print(f"     Average response time: {metrics['average_response_time_ms']}ms")
            print(f"     Error rate: {metrics['error_rate']:.2%}")
            print(f"     Total errors: {metrics['total_errors']}")
        
        # Validate calculations
        influx_metrics = summary['influxdb']
        expected_avg = (100.0 + 150.0 + 200.0) / 3
        expected_error_rate = 1 / 3
        
        if abs(influx_metrics['average_response_time_ms'] - expected_avg) < 0.01:
            print(f"✅ Average response time calculation is correct")
        else:
            print(f"❌ Average response time calculation is incorrect")
            return False
        
        if abs(influx_metrics['error_rate'] - expected_error_rate) < 0.01:
            print(f"✅ Error rate calculation is correct")
        else:
            print(f"❌ Error rate calculation is incorrect")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Performance metrics test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Traffic Switching Functionality Test")
    print("=" * 60)
    
    tests = [
        test_traffic_switch_manager,
        test_convenience_functions,
        test_backend_determination_consistency,
        test_performance_metrics,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test.__name__}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())