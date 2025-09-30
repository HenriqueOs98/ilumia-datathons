#!/usr/bin/env python3

import json
import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import time

def create_opensearch_index():
    # Configuration
    collection_id = "jsqnsrqfe1foih7yivs0"
    collection_endpoint = "https://jsqnsrqfe1foih7yivs0.us-east-1.aoss.amazonaws.com"
    index_name = "bedrock-knowledge-base-index"
    region = "us-east-1"
    
    # Wait a bit for collection to be ready
    print("Waiting for collection to be ready...")
    time.sleep(30)
    
    # Create index mapping
    index_body = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512
            }
        },
        "mappings": {
            "properties": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": 1536,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib"
                    }
                },
                "text": {
                    "type": "text"
                },
                "metadata": {
                    "type": "object"
                }
            }
        }
    }
    
    try:
        # Use boto3 session for authentication
        session = boto3.Session()
        credentials = session.get_credentials()
        
        # Create signed request
        url = f"{collection_endpoint}/{index_name}"
        request = AWSRequest(method='PUT', url=url, data=json.dumps(index_body))
        request.headers['Content-Type'] = 'application/json'
        
        SigV4Auth(credentials, 'aoss', region).add_auth(request)
        
        # Send request
        response = requests.put(
            url,
            data=json.dumps(index_body),
            headers=dict(request.headers)
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            print(f"Index {index_name} created successfully")
        else:
            print(f"Index creation may have failed, but continuing...")
            
    except Exception as e:
        print(f"Error creating index: {str(e)}")
        print("This may be expected if the index already exists")

if __name__ == "__main__":
    create_opensearch_index()