"""
Shared utilities for the ONS Data Platform.

This module provides common functionality used across Lambda functions,
Batch jobs, and other components of the platform, including traffic switching
for the InfluxDB migration.
"""

__version__ = "1.0.0"

# Import key classes for easy access
from .influxdb_client import InfluxDBHandler
from .data_conversion import EnergyDataConverter, convert_parquet_to_influxdb_points
from .query_translator import QueryTranslator, QueryLanguage, QueryType, create_query_translator, translate_natural_language_query
from .traffic_switch import (
    TrafficSwitchManager,
    DatabaseBackend,
    TrafficSwitchError,
    get_traffic_switch_manager,
    should_use_influxdb_for_ingestion,
    should_use_influxdb_for_queries,
    determine_backend_for_query,
    record_performance_metric
)

__all__ = [
    'InfluxDBHandler',
    'EnergyDataConverter', 
    'convert_parquet_to_influxdb_points',
    'QueryTranslator',
    'QueryLanguage',
    'QueryType',
    'create_query_translator',
    'translate_natural_language_query',
    'TrafficSwitchManager',
    'DatabaseBackend',
    'TrafficSwitchError',
    'get_traffic_switch_manager',
    'should_use_influxdb_for_ingestion',
    'should_use_influxdb_for_queries',
    'determine_backend_for_query',
    'record_performance_metric'
]