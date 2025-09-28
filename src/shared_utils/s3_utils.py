"""
S3 utilities for the ONS Data Platform.
"""

import boto3
from typing import Dict, List, Optional, Any
import logging
from urllib.parse import unquote_plus
import os

from .aws_clients import aws_clients

logger = logging.getLogger(__name__)


class S3Utils:
    """S3 utility functions."""
    
    @staticmethod
    def parse_s3_event(event: Dict[str, Any]) -> Dict[str, str]:
        """
        Parse S3 event to extract bucket and key information.
        
        Args:
            event: Lambda event from S3
        
        Returns:
            Dictionary with bucket and key information
        """
        try:
            # Handle direct S3 event
            if 'Records' in event:
                record = event['Records'][0]
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
            # Handle Step Functions input
            elif 'bucket' in event and 'key' in event:
                bucket = event['bucket']
                key = event['key']
            else:
                raise ValueError("Invalid event format")
            
            return {
                'bucket': bucket,
                'key': key,
                'file_name': os.path.basename(key),
                'file_extension': os.path.splitext(key)[1].lower()
            }
        except Exception as e:
            logger.error(f"Error parsing S3 event: {str(e)}")
            raise
    
    @staticmethod
    def get_object_metadata(bucket: str, key: str) -> Dict[str, Any]:
        """
        Get S3 object metadata.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
        
        Returns:
            Object metadata dictionary
        """
        try:
            response = aws_clients.s3.head_object(Bucket=bucket, Key=key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
        except Exception as e:
            logger.error(f"Error getting object metadata: {str(e)}")
            raise
    
    @staticmethod
    def download_file(bucket: str, key: str, local_path: str) -> str:
        """
        Download file from S3 to local path.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            local_path: Local file path
        
        Returns:
            Local file path
        """
        try:
            aws_clients.s3.download_file(bucket, key, local_path)
            logger.info(f"Downloaded {bucket}/{key} to {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise
    
    @staticmethod
    def upload_file(local_path: str, bucket: str, key: str, metadata: Optional[Dict[str, str]] = None) -> str:
        """
        Upload file from local path to S3.
        
        Args:
            local_path: Local file path
            bucket: S3 bucket name
            key: S3 object key
            metadata: Optional metadata dictionary
        
        Returns:
            S3 URI
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            aws_clients.s3.upload_file(local_path, bucket, key, ExtraArgs=extra_args)
            s3_uri = f"s3://{bucket}/{key}"
            logger.info(f"Uploaded {local_path} to {s3_uri}")
            return s3_uri
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise
    
    @staticmethod
    def list_objects(bucket: str, prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
        """
        List objects in S3 bucket with optional prefix.
        
        Args:
            bucket: S3 bucket name
            prefix: Object key prefix
            max_keys: Maximum number of keys to return
        
        Returns:
            List of object information dictionaries
        """
        try:
            response = aws_clients.s3.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            return objects
        except Exception as e:
            logger.error(f"Error listing objects: {str(e)}")
            raise