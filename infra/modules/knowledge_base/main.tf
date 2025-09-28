# Data source for current AWS region and account
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# IAM role for Knowledge Base
resource "aws_iam_role" "knowledge_base_role" {
  name = "${var.project_name}-${var.environment}-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-kb-role"
  }
}

# IAM policy for Knowledge Base to access S3
resource "aws_iam_role_policy" "knowledge_base_s3_policy" {
  name = "${var.project_name}-${var.environment}-kb-s3-policy"
  role = aws_iam_role.knowledge_base_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_processed_bucket}",
          "arn:aws:s3:::${var.s3_processed_bucket}/*"
        ]
      }
    ]
  })
}

# IAM policy for Knowledge Base to access OpenSearch Serverless
resource "aws_iam_role_policy" "knowledge_base_opensearch_policy" {
  name = "${var.project_name}-${var.environment}-kb-opensearch-policy"
  role = aws_iam_role.knowledge_base_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "aoss:APIAccessAll"
        ]
        Resource = aws_opensearchserverless_collection.knowledge_base.arn
      }
    ]
  })
}

# IAM policy for Knowledge Base to access Bedrock models
resource "aws_iam_role_policy" "knowledge_base_bedrock_policy" {
  name = "${var.project_name}-${var.environment}-kb-bedrock-policy"
  role = aws_iam_role.knowledge_base_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-text-v1"
        ]
      }
    ]
  })
}

# OpenSearch Serverless encryption policy
resource "aws_opensearchserverless_security_policy" "knowledge_base_encryption" {
  name = "${var.project_name}-${var.environment}-kb-encryption"
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        Resource = [
          "collection/${var.project_name}-${var.environment}-kb"
        ]
        ResourceType = "collection"
      }
    ]
    AWSOwnedKey = true
  })
}

# OpenSearch Serverless network policy
resource "aws_opensearchserverless_security_policy" "knowledge_base_network" {
  name = "${var.project_name}-${var.environment}-kb-network"
  type = "network"

  policy = jsonencode([
    {
      Rules = [
        {
          Resource = [
            "collection/${var.project_name}-${var.environment}-kb"
          ]
          ResourceType = "collection"
        }
      ]
      AllowFromPublic = true
    }
  ])
}

# OpenSearch Serverless data access policy
resource "aws_opensearchserverless_access_policy" "knowledge_base_data_access" {
  name = "${var.project_name}-${var.environment}-kb-data-access"
  type = "data"

  policy = jsonencode([
    {
      Rules = [
        {
          Resource = [
            "collection/${var.project_name}-${var.environment}-kb"
          ]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems"
          ]
          ResourceType = "collection"
        },
        {
          Resource = [
            "index/${var.project_name}-${var.environment}-kb/*"
          ]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument"
          ]
          ResourceType = "index"
        }
      ]
      Principal = [
        aws_iam_role.knowledge_base_role.arn,
        data.aws_caller_identity.current.arn
      ]
    }
  ])
}

# OpenSearch Serverless collection for vector storage
resource "aws_opensearchserverless_collection" "knowledge_base" {
  name = "${var.project_name}-${var.environment}-kb"
  type = "VECTORSEARCH"

  description = "Vector database for ONS Data Platform Knowledge Base"

  depends_on = [
    aws_opensearchserverless_security_policy.knowledge_base_encryption,
    aws_opensearchserverless_security_policy.knowledge_base_network,
    aws_opensearchserverless_access_policy.knowledge_base_data_access
  ]

  tags = {
    Name = "${var.project_name}-${var.environment}-kb-collection"
  }
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "ons_knowledge_base" {
  name     = "${var.project_name}-${var.environment}-knowledge-base"
  role_arn = aws_iam_role.knowledge_base_role.arn

  description = "Knowledge Base for ONS energy data with RAG capabilities"

  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-text-v1"
    }
    type = "VECTOR"
  }

  storage_configuration {
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.knowledge_base.arn
      vector_index_name = "ons-energy-index"
      field_mapping {
        vector_field   = "vector"
        text_field     = "text"
        metadata_field = "metadata"
      }
    }
    type = "OPENSEARCH_SERVERLESS"
  }

  depends_on = [
    aws_opensearchserverless_collection.knowledge_base,
    aws_iam_role_policy.knowledge_base_s3_policy,
    aws_iam_role_policy.knowledge_base_opensearch_policy,
    aws_iam_role_policy.knowledge_base_bedrock_policy
  ]

  tags = {
    Name = "${var.project_name}-${var.environment}-knowledge-base"
  }
}

# Bedrock Knowledge Base Data Source
resource "aws_bedrockagent_data_source" "s3_data_source" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.ons_knowledge_base.id
  name              = "${var.project_name}-${var.environment}-s3-data-source"
  
  description = "S3 data source for processed ONS energy data"

  data_source_configuration {
    s3_configuration {
      bucket_arn = "arn:aws:s3:::${var.s3_processed_bucket}"
      
      # Include only Parquet files from processed zone
      inclusion_prefixes = ["processed/"]
    }
    type = "S3"
  }

  # Chunking strategy configuration
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens     = 300
        overlap_percentage = 20
      }
    }
  }

  depends_on = [
    aws_bedrockagent_knowledge_base.ons_knowledge_base
  ]

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-data-source"
  }
}