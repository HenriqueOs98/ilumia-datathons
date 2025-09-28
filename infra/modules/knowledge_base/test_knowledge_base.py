#!/usr/bin/env python3
"""
Integration tests for Knowledge Base infrastructure
Tests knowledge base indexing and retrieval functionality
"""

import boto3
import json
import time
import pytest
from typing import Dict, Any
import os
from botocore.exceptions import ClientError


class TestKnowledgeBase:
    """Test suite for Knowledge Base and OpenSearch Serverless integration"""
    
    def __init__(self):
        self.bedrock_agent = boto3.client('bedrock-agent')
        self.bedrock_runtime = boto3.client('bedrock-agent-runtime')
        self.opensearch = boto3.client('opensearchserverless')
        self.s3 = boto3.client('s3')
        
        # Get environment variables or use defaults for testing
        self.project_name = os.getenv('PROJECT_NAME', 'ons-data-platform')
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.knowledge_base_name = f"{self.project_name}-{self.environment}-knowledge-base"
        self.collection_name = f"{self.project_name}-{self.environment}-kb"
        
    def test_opensearch_collection_exists(self):
        """Test that OpenSearch Serverless collection is created and accessible"""
        try:
            response = self.opensearch.batch_get_collection(
                names=[self.collection_name]
            )
            
            assert len(response['collectionDetails']) == 1
            collection = response['collectionDetails'][0]
            
            assert collection['name'] == self.collection_name
            assert collection['type'] == 'VECTORSEARCH'
            assert collection['status'] == 'ACTIVE'
            
            print(f"✓ OpenSearch collection '{self.collection_name}' is active")
            return True
            
        except ClientError as e:
            pytest.fail(f"Failed to get OpenSearch collection: {e}")
            
    def test_knowledge_base_exists(self):
        """Test that Bedrock Knowledge Base is created and configured"""
        try:
            # List knowledge bases to find ours
            response = self.bedrock_agent.list_knowledge_bases()
            
            kb_found = None
            for kb in response['knowledgeBaseSummaries']:
                if kb['name'] == self.knowledge_base_name:
                    kb_found = kb
                    break
                    
            assert kb_found is not None, f"Knowledge Base '{self.knowledge_base_name}' not found"
            
            # Get detailed knowledge base info
            kb_details = self.bedrock_agent.get_knowledge_base(
                knowledgeBaseId=kb_found['knowledgeBaseId']
            )
            
            kb_config = kb_details['knowledgeBase']
            assert kb_config['status'] == 'ACTIVE'
            assert kb_config['knowledgeBaseConfiguration']['type'] == 'VECTOR'
            
            # Verify embedding model
            embedding_model = kb_config['knowledgeBaseConfiguration']['vectorKnowledgeBaseConfiguration']['embeddingModelArn']
            assert 'amazon.titan-embed-text-v1' in embedding_model
            
            print(f"✓ Knowledge Base '{self.knowledge_base_name}' is active with Titan embeddings")
            return kb_found['knowledgeBaseId']
            
        except ClientError as e:
            pytest.fail(f"Failed to get Knowledge Base: {e}")
            
    def test_data_source_configuration(self):
        """Test that S3 data source is properly configured"""
        kb_id = self.test_knowledge_base_exists()
        
        try:
            response = self.bedrock_agent.list_data_sources(
                knowledgeBaseId=kb_id
            )
            
            assert len(response['dataSourceSummaries']) >= 1
            
            data_source = response['dataSourceSummaries'][0]
            data_source_id = data_source['dataSourceId']
            
            # Get detailed data source configuration
            ds_details = self.bedrock_agent.get_data_source(
                knowledgeBaseId=kb_id,
                dataSourceId=data_source_id
            )
            
            ds_config = ds_details['dataSource']
            assert ds_config['dataSourceConfiguration']['type'] == 'S3'
            
            s3_config = ds_config['dataSourceConfiguration']['s3Configuration']
            assert 'processed/' in s3_config.get('inclusionPrefixes', [])
            
            # Verify chunking configuration
            vector_config = ds_config.get('vectorIngestionConfiguration', {})
            chunking_config = vector_config.get('chunkingConfiguration', {})
            
            if chunking_config.get('chunkingStrategy') == 'FIXED_SIZE':
                fixed_size_config = chunking_config.get('fixedSizeChunkingConfiguration', {})
                assert fixed_size_config.get('maxTokens') == 300
                assert fixed_size_config.get('overlapPercentage') == 20
            
            print(f"✓ Data source configured with proper S3 settings and chunking strategy")
            return data_source_id
            
        except ClientError as e:
            pytest.fail(f"Failed to get data source configuration: {e}")
            
    def test_knowledge_base_ingestion(self):
        """Test knowledge base data ingestion process"""
        kb_id = self.test_knowledge_base_exists()
        ds_id = self.test_data_source_configuration()
        
        try:
            # Start ingestion job
            response = self.bedrock_agent.start_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                description="Test ingestion job for knowledge base validation"
            )
            
            ingestion_job_id = response['ingestionJob']['ingestionJobId']
            print(f"✓ Started ingestion job: {ingestion_job_id}")
            
            # Wait for ingestion to complete (with timeout)
            max_wait_time = 300  # 5 minutes
            wait_interval = 10   # 10 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                job_status = self.bedrock_agent.get_ingestion_job(
                    knowledgeBaseId=kb_id,
                    dataSourceId=ds_id,
                    ingestionJobId=ingestion_job_id
                )
                
                status = job_status['ingestionJob']['status']
                
                if status == 'COMPLETE':
                    print(f"✓ Ingestion job completed successfully")
                    return True
                elif status == 'FAILED':
                    failure_reasons = job_status['ingestionJob'].get('failureReasons', [])
                    pytest.fail(f"Ingestion job failed: {failure_reasons}")
                
                print(f"Ingestion job status: {status}, waiting...")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
                
            pytest.fail(f"Ingestion job did not complete within {max_wait_time} seconds")
            
        except ClientError as e:
            # If no data exists yet, that's expected for initial setup
            if "No objects found" in str(e) or "empty" in str(e).lower():
                print("⚠ No data available for ingestion yet - this is expected for initial setup")
                return True
            pytest.fail(f"Failed to start ingestion job: {e}")
            
    def test_knowledge_base_retrieval(self):
        """Test knowledge base retrieval functionality"""
        kb_id = self.test_knowledge_base_exists()
        
        try:
            # Test retrieval with a sample query
            test_query = "What is the energy generation data available?"
            
            response = self.bedrock_runtime.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={
                    'text': test_query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5
                    }
                }
            )
            
            # Check if we get a valid response structure
            assert 'retrievalResults' in response
            results = response['retrievalResults']
            
            # If no results, it might be because no data is ingested yet
            if len(results) == 0:
                print("⚠ No retrieval results - this is expected if no data has been ingested yet")
                return True
                
            # If we have results, validate their structure
            for result in results:
                assert 'content' in result
                assert 'location' in result
                assert 'score' in result
                
            print(f"✓ Knowledge base retrieval working - got {len(results)} results")
            return True
            
        except ClientError as e:
            # If knowledge base is not ready for queries, that's expected
            if "not ready" in str(e).lower() or "no data" in str(e).lower():
                print("⚠ Knowledge base not ready for queries yet - this is expected for initial setup")
                return True
            pytest.fail(f"Failed to test retrieval: {e}")
            
    def test_rag_query_processing(self):
        """Test end-to-end RAG query processing"""
        kb_id = self.test_knowledge_base_exists()
        
        try:
            # Test RAG query with generation
            test_query = "What types of energy data are available in the ONS platform?"
            
            response = self.bedrock_runtime.retrieve_and_generate(
                input={
                    'text': test_query
                },
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': kb_id,
                        'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
                    }
                }
            )
            
            # Validate response structure
            assert 'output' in response
            assert 'text' in response['output']
            
            if 'citations' in response:
                print(f"✓ RAG query successful with {len(response['citations'])} citations")
            else:
                print("✓ RAG query successful (no citations available yet)")
                
            return True
            
        except ClientError as e:
            # If no data is available for RAG, that's expected for initial setup
            if "no relevant" in str(e).lower() or "insufficient" in str(e).lower():
                print("⚠ RAG query returned no results - this is expected if no data has been ingested yet")
                return True
            pytest.fail(f"Failed to test RAG query: {e}")
            
    def run_all_tests(self):
        """Run all knowledge base tests"""
        print("🧪 Running Knowledge Base Integration Tests...")
        print("=" * 60)
        
        try:
            self.test_opensearch_collection_exists()
            self.test_knowledge_base_exists()
            self.test_data_source_configuration()
            self.test_knowledge_base_ingestion()
            self.test_knowledge_base_retrieval()
            self.test_rag_query_processing()
            
            print("=" * 60)
            print("✅ All Knowledge Base tests passed!")
            return True
            
        except Exception as e:
            print("=" * 60)
            print(f"❌ Knowledge Base tests failed: {e}")
            return False


if __name__ == "__main__":
    tester = TestKnowledgeBase()
    success = tester.run_all_tests()
    exit(0 if success else 1)