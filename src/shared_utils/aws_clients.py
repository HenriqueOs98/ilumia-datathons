"""
AWS client utilities for consistent service access across the platform.
"""

import boto3
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AWSClients:
    """Centralized AWS client management."""
    
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._s3_client = None
        self._timestream_write_client = None
        self._bedrock_agent_runtime_client = None
        self._stepfunctions_client = None
    
    @property
    def s3(self):
        """Get S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client('s3', region_name=self.region)
        return self._s3_client
    
    @property
    def timestream_write(self):
        """Get Timestream Write client."""
        if self._timestream_write_client is None:
            self._timestream_write_client = boto3.client(
                'timestream-write', 
                region_name=self.region
            )
        return self._timestream_write_client
    
    @property
    def bedrock_agent_runtime(self):
        """Get Bedrock Agent Runtime client."""
        if self._bedrock_agent_runtime_client is None:
            self._bedrock_agent_runtime_client = boto3.client(
                'bedrock-agent-runtime',
                region_name=self.region
            )
        return self._bedrock_agent_runtime_client
    
    @property
    def stepfunctions(self):
        """Get Step Functions client."""
        if self._stepfunctions_client is None:
            self._stepfunctions_client = boto3.client(
                'stepfunctions',
                region_name=self.region
            )
        return self._stepfunctions_client


# Global instance for easy access
aws_clients = AWSClients()