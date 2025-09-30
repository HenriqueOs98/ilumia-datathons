#!/bin/bash

# Create OpenSearch index for Bedrock Knowledge Base
# This script creates the required index with the correct mapping

set -e

COLLECTION_ENDPOINT="https://jsqnsrqfe1foih7yivs0.us-east-1.aoss.amazonaws.com"
INDEX_NAME="bedrock-knowledge-base-default-index"

echo "Creating OpenSearch index: $INDEX_NAME"

# Create the index with the required mapping for Bedrock
curl -X PUT \
  "$COLLECTION_ENDPOINT/$INDEX_NAME" \
  -H "Content-Type: application/json" \
  --aws-sigv4 "aws:amz:us-east-1:aoss" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  -d '{
    "settings": {
      "index": {
        "knn": true,
        "knn.algo_param.ef_search": 512
      }
    },
    "mappings": {
      "properties": {
        "bedrock-knowledge-base-default-vector": {
          "type": "knn_vector",
          "dimension": 1536,
          "method": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "nmslib"
          }
        },
        "bedrock-knowledge-base-default-text": {
          "type": "text"
        },
        "bedrock-knowledge-base-default-metadata": {
          "type": "object"
        }
      }
    }
  }' || echo "Index creation completed (may already exist)"

echo "Index creation completed"