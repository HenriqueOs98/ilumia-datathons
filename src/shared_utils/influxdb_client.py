"""
InfluxDB client handler for the ONS Data Platform.

This module provides a robust InfluxDB client with connection management,
error handling, and retry logic for time series data operations.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone
import threading
from contextlib import contextmanager

try:
    import influxdb_client
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
    from influxdb_client.client.exceptions import InfluxDBError
    from influxdb_client.rest import ApiException
except ImportError:
    raise ImportError(
        "influxdb-client is required. Install with: pip install influxdb-client"
    )

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


class InfluxDBConnectionError(Exception):
    """Raised when InfluxDB connection fails."""
    pass


class InfluxDBWriteError(Exception):
    """Raised when InfluxDB write operation fails."""
    pass


class InfluxDBQueryError(Exception):
    """Raised when InfluxDB query operation fails."""
    pass


class InfluxDBHandler:
    """
    InfluxDB client handler with connection management and error handling.
    
    Provides robust connection management, automatic retries, and proper
    error handling for InfluxDB operations in the ONS Data Platform.
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None,
        timeout: int = 30000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_gzip: bool = True
    ):
        """
        Initialize InfluxDB handler.
        
        Args:
            url: InfluxDB URL (defaults to INFLUXDB_URL env var)
            token: InfluxDB token (defaults to INFLUXDB_TOKEN env var)
            org: InfluxDB organization (defaults to INFLUXDB_ORG env var)
            bucket: Default bucket name (defaults to INFLUXDB_BUCKET env var)
            timeout: Connection timeout in milliseconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
            enable_gzip: Enable gzip compression for requests
        """
        self.url = url or os.getenv('INFLUXDB_URL')
        self.token = token or self._get_token()
        self.org = org or os.getenv('INFLUXDB_ORG', 'ons-energy')
        self.bucket = bucket or os.getenv('INFLUXDB_BUCKET', 'energy_data')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_gzip = enable_gzip
        
        self._client = None
        self._write_api = None
        self._query_api = None
        self._lock = threading.Lock()
        
        # Validate required configuration
        if not self.url:
            raise ValueError("InfluxDB URL must be provided via parameter or INFLUXDB_URL env var")
        if not self.token:
            raise ValueError("InfluxDB token must be provided via parameter or INFLUXDB_TOKEN env var")
        
        logger.info(f"Initialized InfluxDB handler for {self.url}, org: {self.org}")
    
    def _get_token(self) -> str:
        """
        Retrieve InfluxDB token from environment or AWS Secrets Manager.
        
        Returns:
            InfluxDB authentication token
            
        Raises:
            ValueError: If token cannot be retrieved
        """
        # First try environment variable
        token = os.getenv('INFLUXDB_TOKEN')
        if token:
            return token
        
        # Try AWS Secrets Manager
        secret_name = os.getenv('INFLUXDB_TOKEN_SECRET_NAME')
        if secret_name:
            try:
                secrets_client = boto3.client('secretsmanager')
                response = secrets_client.get_secret_value(SecretId=secret_name)
                return response['SecretString']
            except ClientError as e:
                logger.error(f"Failed to retrieve InfluxDB token from Secrets Manager: {e}")
                raise ValueError(f"Could not retrieve InfluxDB token from secret {secret_name}")
        
        raise ValueError("InfluxDB token not found in environment or Secrets Manager")
    
    @property
    def client(self) -> InfluxDBClient:
        """
        Get or create InfluxDB client with connection pooling.
        
        Returns:
            InfluxDB client instance
        """
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        self._client = InfluxDBClient(
                            url=self.url,
                            token=self.token,
                            org=self.org,
                            timeout=self.timeout,
                            enable_gzip=self.enable_gzip
                        )
                        # Test connection
                        self._client.ping()
                        logger.info("InfluxDB client connected successfully")
                    except Exception as e:
                        logger.error(f"Failed to create InfluxDB client: {e}")
                        raise InfluxDBConnectionError(f"Could not connect to InfluxDB: {e}")
        
        return self._client
    
    @property
    def write_api(self):
        """Get write API instance."""
        if self._write_api is None:
            with self._lock:
                if self._write_api is None:
                    self._write_api = self.client.write_api(write_options=SYNCHRONOUS)
        return self._write_api
    
    @property
    def query_api(self):
        """Get query API instance."""
        if self._query_api is None:
            with self._lock:
                if self._query_api is None:
                    self._query_api = self.client.query_api()
        return self._query_api
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on InfluxDB connection.
        
        Returns:
            Health check results with status and metrics
        """
        start_time = time.time()
        try:
            # Test basic connectivity
            ping_result = self.client.ping()
            
            # Test write capability with a test point
            test_point = Point("health_check") \
                .tag("source", "ons_platform") \
                .field("status", 1) \
                .time(datetime.now(timezone.utc), WritePrecision.NS)
            
            self.write_api.write(bucket=self.bucket, record=test_point)
            
            # Test query capability
            query = f'''
                from(bucket: "{self.bucket}")
                |> range(start: -1m)
                |> filter(fn: (r) => r["_measurement"] == "health_check")
                |> limit(n: 1)
            '''
            self.query_api.query(query)
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "url": self.url,
                "org": self.org,
                "bucket": self.bucket,
                "ping_result": ping_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"InfluxDB health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(response_time, 2),
                "url": self.url,
                "org": self.org,
                "bucket": self.bucket,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def write_points(
        self,
        points: Union[Point, List[Point]],
        bucket: Optional[str] = None,
        precision: WritePrecision = WritePrecision.NS
    ) -> bool:
        """
        Write points to InfluxDB with retry logic.
        
        Args:
            points: Single point or list of points to write
            bucket: Target bucket (defaults to instance bucket)
            precision: Time precision for timestamps
            
        Returns:
            True if write successful
            
        Raises:
            InfluxDBWriteError: If write fails after all retries
        """
        target_bucket = bucket or self.bucket
        
        if not isinstance(points, list):
            points = [points]
        
        for attempt in range(self.max_retries + 1):
            try:
                self.write_api.write(
                    bucket=target_bucket,
                    record=points,
                    write_precision=precision
                )
                
                logger.debug(f"Successfully wrote {len(points)} points to bucket {target_bucket}")
                return True
                
            except (InfluxDBError, ApiException) as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed to write points after {self.max_retries + 1} attempts: {e}")
                    raise InfluxDBWriteError(f"Write failed: {e}")
                
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Write attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        return False
    
    def query_flux(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute Flux query with retry logic.
        
        Args:
            query: Flux query string
            params: Query parameters for parameterized queries
            
        Returns:
            List of query results as dictionaries
            
        Raises:
            InfluxDBQueryError: If query fails after all retries
        """
        for attempt in range(self.max_retries + 1):
            try:
                result = self.query_api.query(query, params=params)
                
                # Convert result to list of dictionaries
                records = []
                for table in result:
                    for record in table.records:
                        records.append({
                            'measurement': record.get_measurement(),
                            'time': record.get_time(),
                            'field': record.get_field(),
                            'value': record.get_value(),
                            'tags': record.values
                        })
                
                logger.debug(f"Query returned {len(records)} records")
                return records
                
            except (InfluxDBError, ApiException) as e:
                if attempt == self.max_retries:
                    logger.error(f"Query failed after {self.max_retries + 1} attempts: {e}")
                    raise InfluxDBQueryError(f"Query failed: {e}")
                
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Query attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        return []
    
    @contextmanager
    def batch_writer(self, batch_size: int = 1000, flush_interval: int = 1000):
        """
        Context manager for batch writing operations.
        
        Args:
            batch_size: Number of points per batch
            flush_interval: Flush interval in milliseconds
            
        Yields:
            Batch write API instance
        """
        from influxdb_client.client.write_api import WriteOptions
        
        write_options = WriteOptions(
            batch_size=batch_size,
            flush_interval=flush_interval,
            jitter_interval=200,
            retry_interval=5000,
            max_retries=3
        )
        
        batch_api = self.client.write_api(write_options=write_options)
        
        try:
            yield batch_api
        finally:
            batch_api.close()
    
    def close(self):
        """Close InfluxDB client and cleanup resources."""
        try:
            if self._write_api:
                self._write_api.close()
            if self._query_api:
                self._query_api.close()
            if self._client:
                self._client.close()
            
            self._write_api = None
            self._query_api = None
            self._client = None
            
            logger.info("InfluxDB client closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing InfluxDB client: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()