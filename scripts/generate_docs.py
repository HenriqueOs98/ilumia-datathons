#!/usr/bin/env python3
"""
Automated documentation generation script for the ONS Data Platform.
Generates documentation from code comments, docstrings, and infrastructure definitions.
"""

import os
import ast
import json
import yaml
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class FunctionDoc:
    """Documentation for a Python function"""
    name: str
    docstring: str
    parameters: List[Dict[str, str]]
    returns: str
    file_path: str

@dataclass
class ModuleDoc:
    """Documentation for a Python module"""
    name: str
    docstring: str
    functions: List[FunctionDoc]
    classes: List[Dict[str, Any]]
    file_path: str

@dataclass
class TerraformResource:
    """Documentation for a Terraform resource"""
    type: str
    name: str
    description: str
    variables: List[Dict[str, str]]
    outputs: List[Dict[str, str]]
    file_path: str

class DocumentationGenerator:
    """Generates comprehensive documentation from source code and infrastructure"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.docs_dir = self.project_root / "docs"
        self.src_dir = self.project_root / "src"
        self.infra_dir = self.project_root / "infra"
        
        # Ensure docs directory exists
        self.docs_dir.mkdir(exist_ok=True)
    
    def generate_all_docs(self):
        """Generate all documentation"""
        logger.info("Starting documentation generation...")
        
        # Generate API documentation
        self.generate_api_docs()
        
        # Generate infrastructure documentation
        self.generate_infrastructure_docs()
        
        # Generate component documentation
        self.generate_component_docs()
        
        # Generate architecture documentation
        self.generate_architecture_docs()
        
        # Generate index
        self.generate_index()
        
        logger.info("Documentation generation completed!")
    
    def generate_api_docs(self):
        """Generate API documentation from Lambda functions"""
        logger.info("Generating API documentation...")
        
        api_functions = [
            'rag_query_processor',
            'lambda_router'
        ]
        
        api_doc = []
        api_doc.append("# API Documentation\n")
        api_doc.append("This document describes the REST API endpoints and their usage.\n")
        
        # API Overview
        api_doc.append("## Overview\n")
        api_doc.append("The ONS Data Platform provides a REST API for querying energy data using natural language.\n")
        api_doc.append("The API is built using AWS API Gateway and Lambda functions.\n\n")
        
        # Authentication
        api_doc.append("## Authentication\n")
        api_doc.append("All API requests require an API key passed in the `x-api-key` header.\n\n")
        api_doc.append("```bash\n")
        api_doc.append('curl -H "x-api-key: YOUR_API_KEY" https://api.ons-platform.com/query\n')
        api_doc.append("```\n\n")
        
        # Endpoints
        api_doc.append("## Endpoints\n\n")
        
        for func_name in api_functions:
            func_path = self.src_dir / func_name / "lambda_function.py"
            if func_path.exists():
                module_doc = self._parse_python_file(func_path)
                api_doc.append(f"### {func_name.replace('_', ' ').title()}\n\n")
                
                if module_doc.docstring:
                    api_doc.append(f"{module_doc.docstring}\n\n")
                
                # Extract endpoint information from function
                for func in module_doc.functions:
                    if func.name == "lambda_handler":
                        api_doc.append("**Handler Function:**\n")
                        api_doc.append(f"- **Function**: `{func.name}`\n")
                        api_doc.append(f"- **Description**: {func.docstring or 'Main Lambda handler'}\n")
                        
                        if func.parameters:
                            api_doc.append("- **Parameters**:\n")
                            for param in func.parameters:
                                api_doc.append(f"  - `{param['name']}`: {param['type']} - {param['description']}\n")
                        
                        if func.returns:
                            api_doc.append(f"- **Returns**: {func.returns}\n")
                        
                        api_doc.append("\n")
        
        # Error Handling
        api_doc.append("## Error Handling\n\n")
        api_doc.append("The API uses standard HTTP status codes:\n\n")
        api_doc.append("- `200 OK`: Request successful\n")
        api_doc.append("- `400 Bad Request`: Invalid request parameters\n")
        api_doc.append("- `401 Unauthorized`: Invalid or missing API key\n")
        api_doc.append("- `429 Too Many Requests`: Rate limit exceeded\n")
        api_doc.append("- `500 Internal Server Error`: Server error\n\n")
        
        # Rate Limiting
        api_doc.append("## Rate Limiting\n\n")
        api_doc.append("API requests are limited to:\n")
        api_doc.append("- **Burst**: 2000 requests\n")
        api_doc.append("- **Rate**: 1000 requests per second\n\n")
        
        # Examples
        api_doc.append("## Examples\n\n")
        api_doc.append("### Query Energy Data\n\n")
        api_doc.append("```bash\n")
        api_doc.append("curl -X POST https://api.ons-platform.com/query \\\n")
        api_doc.append('  -H "Content-Type: application/json" \\\n')
        api_doc.append('  -H "x-api-key: YOUR_API_KEY" \\\n')
        api_doc.append('  -d \'{\n')
        api_doc.append('    "question": "What was the total energy generation in the Southeast region last month?"\n')
        api_doc.append('  }\'\n')
        api_doc.append("```\n\n")
        
        api_doc.append("**Response:**\n")
        api_doc.append("```json\n")
        api_doc.append("{\n")
        api_doc.append('  "query_id": "uuid-string",\n')
        api_doc.append('  "question": "What was the total energy generation in the Southeast region last month?",\n')
        api_doc.append('  "answer": "The total energy generation in the Southeast region last month was 15,234 MW...",\n')
        api_doc.append('  "confidence_score": 0.95,\n')
        api_doc.append('  "sources": [\n')
        api_doc.append('    {\n')
        api_doc.append('      "document": "generation_data_2024_01.parquet",\n')
        api_doc.append('      "relevance_score": 0.98,\n')
        api_doc.append('      "excerpt": "Southeast region generation data..."\n')
        api_doc.append('    }\n')
        api_doc.append('  ],\n')
        api_doc.append('  "processing_time_ms": 1250,\n')
        api_doc.append('  "timestamp": "2024-01-15T10:30:00Z"\n')
        api_doc.append("}\n")
        api_doc.append("```\n\n")
        
        # Write API documentation
        with open(self.docs_dir / "api.md", "w") as f:
            f.write("".join(api_doc))
        
        logger.info("API documentation generated")
    
    def generate_infrastructure_docs(self):
        """Generate infrastructure documentation from Terraform files"""
        logger.info("Generating infrastructure documentation...")
        
        infra_doc = []
        infra_doc.append("# Infrastructure Documentation\n\n")
        infra_doc.append("This document describes the AWS infrastructure components and their configurations.\n\n")
        
        # Parse Terraform modules
        modules_dir = self.infra_dir / "modules"
        if modules_dir.exists():
            infra_doc.append("## Terraform Modules\n\n")
            
            for module_dir in modules_dir.iterdir():
                if module_dir.is_dir():
                    infra_doc.append(f"### {module_dir.name.replace('_', ' ').title()}\n\n")
                    
                    # Parse main.tf
                    main_tf = module_dir / "main.tf"
                    if main_tf.exists():
                        resources = self._parse_terraform_file(main_tf)
                        if resources:
                            infra_doc.append("**Resources:**\n")
                            for resource in resources:
                                infra_doc.append(f"- `{resource.type}.{resource.name}`: {resource.description}\n")
                            infra_doc.append("\n")
                    
                    # Parse variables.tf
                    variables_tf = module_dir / "variables.tf"
                    if variables_tf.exists():
                        variables = self._parse_terraform_variables(variables_tf)
                        if variables:
                            infra_doc.append("**Variables:**\n")
                            for var in variables:
                                infra_doc.append(f"- `{var['name']}`: {var['description']} (Type: {var['type']})\n")
                            infra_doc.append("\n")
                    
                    # Parse outputs.tf
                    outputs_tf = module_dir / "outputs.tf"
                    if outputs_tf.exists():
                        outputs = self._parse_terraform_outputs(outputs_tf)
                        if outputs:
                            infra_doc.append("**Outputs:**\n")
                            for output in outputs:
                                infra_doc.append(f"- `{output['name']}`: {output['description']}\n")
                            infra_doc.append("\n")
        
        # Write infrastructure documentation
        with open(self.docs_dir / "infrastructure.md", "w") as f:
            f.write("".join(infra_doc))
        
        logger.info("Infrastructure documentation generated")
    
    def generate_component_docs(self):
        """Generate component documentation from source code"""
        logger.info("Generating component documentation...")
        
        components = [
            'batch_pdf_processor',
            'rag_query_processor',
            'shared_utils',
            'structured_data_processor',
            'timestream_loader'
        ]
        
        for component in components:
            component_dir = self.src_dir / component
            if component_dir.exists():
                self._generate_component_doc(component, component_dir)
        
        logger.info("Component documentation generated")
    
    def _generate_component_doc(self, component_name: str, component_dir: Path):
        """Generate documentation for a specific component"""
        doc = []
        doc.append(f"# {component_name.replace('_', ' ').title()}\n\n")
        
        # Component overview
        readme_path = component_dir / "README.md"
        if readme_path.exists():
            with open(readme_path, "r") as f:
                doc.append(f.read())
                doc.append("\n")
        
        # Parse Python files
        python_files = list(component_dir.glob("*.py"))
        if python_files:
            doc.append("## Code Documentation\n\n")
            
            for py_file in python_files:
                if py_file.name.startswith("test_"):
                    continue
                
                module_doc = self._parse_python_file(py_file)
                doc.append(f"### {py_file.name}\n\n")
                
                if module_doc.docstring:
                    doc.append(f"{module_doc.docstring}\n\n")
                
                # Functions
                if module_doc.functions:
                    doc.append("**Functions:**\n\n")
                    for func in module_doc.functions:
                        doc.append(f"#### `{func.name}`\n\n")
                        if func.docstring:
                            doc.append(f"{func.docstring}\n\n")
                        
                        if func.parameters:
                            doc.append("**Parameters:**\n")
                            for param in func.parameters:
                                doc.append(f"- `{param['name']}` ({param['type']}): {param['description']}\n")
                            doc.append("\n")
                        
                        if func.returns:
                            doc.append(f"**Returns:** {func.returns}\n\n")
                
                # Classes
                if module_doc.classes:
                    doc.append("**Classes:**\n\n")
                    for cls in module_doc.classes:
                        doc.append(f"#### `{cls['name']}`\n\n")
                        if cls['docstring']:
                            doc.append(f"{cls['docstring']}\n\n")
        
        # Requirements
        requirements_path = component_dir / "requirements.txt"
        if requirements_path.exists():
            doc.append("## Dependencies\n\n")
            with open(requirements_path, "r") as f:
                requirements = f.read().strip().split("\n")
                for req in requirements:
                    if req.strip():
                        doc.append(f"- `{req.strip()}`\n")
                doc.append("\n")
        
        # Write component documentation
        with open(self.docs_dir / f"{component_name}.md", "w") as f:
            f.write("".join(doc))
    
    def generate_architecture_docs(self):
        """Generate architecture documentation"""
        logger.info("Generating architecture documentation...")
        
        arch_doc = []
        arch_doc.append("# Architecture Documentation\n\n")
        arch_doc.append("This document describes the overall system architecture and design decisions.\n\n")
        
        # System Overview
        arch_doc.append("## System Overview\n\n")
        arch_doc.append("The ONS Data Platform is a serverless, event-driven system built on AWS that processes ")
        arch_doc.append("energy sector data and provides intelligent querying capabilities through a RAG system.\n\n")
        
        # Architecture Diagram
        arch_doc.append("## Architecture Diagram\n\n")
        arch_doc.append("```mermaid\n")
        arch_doc.append("graph TB\n")
        arch_doc.append("    subgraph \"Data Ingestion\"\n")
        arch_doc.append("        S3[S3 Raw Bucket]\n")
        arch_doc.append("        EB[EventBridge]\n")
        arch_doc.append("        SF[Step Functions]\n")
        arch_doc.append("    end\n")
        arch_doc.append("    \n")
        arch_doc.append("    subgraph \"Processing\"\n")
        arch_doc.append("        LR[Lambda Router]\n")
        arch_doc.append("        LP[Lambda Processor]\n")
        arch_doc.append("        BATCH[AWS Batch]\n")
        arch_doc.append("    end\n")
        arch_doc.append("    \n")
        arch_doc.append("    subgraph \"Storage\"\n")
        arch_doc.append("        S3P[S3 Processed]\n")
        arch_doc.append("        TS[Timestream]\n")
        arch_doc.append("        OS[OpenSearch]\n")
        arch_doc.append("    end\n")
        arch_doc.append("    \n")
        arch_doc.append("    subgraph \"API & AI\"\n")
        arch_doc.append("        APIGW[API Gateway]\n")
        arch_doc.append("        LA[Lambda API]\n")
        arch_doc.append("        KB[Knowledge Base]\n")
        arch_doc.append("        BR[Bedrock]\n")
        arch_doc.append("    end\n")
        arch_doc.append("    \n")
        arch_doc.append("    S3 --> EB\n")
        arch_doc.append("    EB --> SF\n")
        arch_doc.append("    SF --> LR\n")
        arch_doc.append("    LR --> LP\n")
        arch_doc.append("    LR --> BATCH\n")
        arch_doc.append("    LP --> S3P\n")
        arch_doc.append("    BATCH --> S3P\n")
        arch_doc.append("    S3P --> TS\n")
        arch_doc.append("    S3P --> KB\n")
        arch_doc.append("    KB --> OS\n")
        arch_doc.append("    APIGW --> LA\n")
        arch_doc.append("    LA --> KB\n")
        arch_doc.append("    KB --> BR\n")
        arch_doc.append("```\n\n")
        
        # Components
        arch_doc.append("## Components\n\n")
        
        components = {
            "Data Ingestion Layer": [
                "S3 Raw Bucket: Stores incoming data files from ONS",
                "EventBridge: Routes S3 events to processing workflows",
                "Step Functions: Orchestrates the entire processing pipeline"
            ],
            "Processing Layer": [
                "Lambda Router: Routes files based on type and size",
                "Lambda Processor: Handles structured data (CSV, XLSX)",
                "AWS Batch: Processes unstructured data (PDF)"
            ],
            "Storage Layer": [
                "S3 Processed: Stores processed data in Parquet format",
                "Timestream: Time series database for energy data",
                "OpenSearch: Vector database for semantic search"
            ],
            "API & AI Layer": [
                "API Gateway: REST API endpoints",
                "Lambda API: Handles API requests",
                "Knowledge Base: RAG system for intelligent querying",
                "Bedrock: Large language model for answer generation"
            ]
        }
        
        for layer, components_list in components.items():
            arch_doc.append(f"### {layer}\n\n")
            for component in components_list:
                arch_doc.append(f"- **{component}**\n")
            arch_doc.append("\n")
        
        # Design Decisions
        arch_doc.append("## Design Decisions\n\n")
        
        decisions = [
            {
                "title": "Serverless Architecture",
                "rationale": "Chosen for automatic scaling, cost efficiency, and reduced operational overhead"
            },
            {
                "title": "Event-Driven Processing",
                "rationale": "Enables real-time processing and loose coupling between components"
            },
            {
                "title": "Multi-Format Support",
                "rationale": "Different processing strategies for CSV/XLSX (Lambda) vs PDF (Batch) based on complexity"
            },
            {
                "title": "RAG Implementation",
                "rationale": "Combines retrieval and generation for accurate, contextual responses"
            },
            {
                "title": "Time Series Database",
                "rationale": "Timestream optimized for time-based energy data queries"
            }
        ]
        
        for decision in decisions:
            arch_doc.append(f"### {decision['title']}\n\n")
            arch_doc.append(f"{decision['rationale']}\n\n")
        
        # Write architecture documentation
        with open(self.docs_dir / "architecture.md", "w") as f:
            f.write("".join(arch_doc))
        
        logger.info("Architecture documentation generated")
    
    def generate_index(self):
        """Generate documentation index"""
        logger.info("Generating documentation index...")
        
        index_doc = []
        index_doc.append("# Documentation Index\n\n")
        index_doc.append("Welcome to the ONS Data Platform documentation.\n\n")
        
        # Quick Links
        index_doc.append("## Quick Links\n\n")
        index_doc.append("- [🏗️ Architecture Overview](architecture.md) - System design and components\n")
        index_doc.append("- [🚀 API Documentation](api.md) - REST API reference\n")
        index_doc.append("- [🔧 Infrastructure](infrastructure.md) - AWS resources and Terraform modules\n")
        index_doc.append("- [🚢 Deployment Guide](deployment-guide.md) - Deployment and rollback procedures\n")
        index_doc.append("- [🔧 Operations Runbook](operations-runbook.md) - Maintenance and troubleshooting\n")
        index_doc.append("- [🧪 Troubleshooting](troubleshooting.md) - Common issues and solutions\n\n")
        
        # Component Documentation
        index_doc.append("## Component Documentation\n\n")
        
        # List all component docs
        component_docs = list(self.docs_dir.glob("*.md"))
        component_docs = [doc for doc in component_docs if doc.name not in ['index.md', 'api.md', 'architecture.md', 'infrastructure.md', 'deployment-guide.md', 'operations-runbook.md', 'troubleshooting.md']]
        
        for doc in sorted(component_docs):
            component_name = doc.stem.replace('_', ' ').title()
            index_doc.append(f"- [{component_name}]({doc.name})\n")
        
        index_doc.append("\n")
        
        # Getting Started
        index_doc.append("## Getting Started\n\n")
        index_doc.append("1. **Setup**: Follow the [deployment guide](deployment-guide.md) to deploy the platform\n")
        index_doc.append("2. **API Usage**: Check the [API documentation](api.md) for endpoint details\n")
        index_doc.append("3. **Troubleshooting**: Use the [troubleshooting guide](troubleshooting.md) for common issues\n")
        index_doc.append("4. **Operations**: Refer to the [operations runbook](operations-runbook.md) for maintenance\n\n")
        
        # Write index
        with open(self.docs_dir / "index.md", "w") as f:
            f.write("".join(index_doc))
        
        logger.info("Documentation index generated")
    
    def _parse_python_file(self, file_path: Path) -> ModuleDoc:
        """Parse Python file and extract documentation"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Extract module docstring
            module_docstring = ast.get_docstring(tree) or ""
            
            # Extract functions
            functions = []
            classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_doc = self._parse_function(node)
                    functions.append(func_doc)
                elif isinstance(node, ast.ClassDef):
                    class_doc = self._parse_class(node)
                    classes.append(class_doc)
            
            return ModuleDoc(
                name=file_path.stem,
                docstring=module_docstring,
                functions=functions,
                classes=classes,
                file_path=str(file_path)
            )
        
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return ModuleDoc(
                name=file_path.stem,
                docstring="",
                functions=[],
                classes=[],
                file_path=str(file_path)
            )
    
    def _parse_function(self, node: ast.FunctionDef) -> FunctionDoc:
        """Parse function node and extract documentation"""
        docstring = ast.get_docstring(node) or ""
        
        # Extract parameters
        parameters = []
        for arg in node.args.args:
            param_info = {
                'name': arg.arg,
                'type': 'Any',  # Type hints would require more complex parsing
                'description': ''
            }
            parameters.append(param_info)
        
        # Extract return type from docstring (simple parsing)
        returns = ""
        if "Returns:" in docstring:
            returns_section = docstring.split("Returns:")[-1].split("\n")[0].strip()
            returns = returns_section
        
        return FunctionDoc(
            name=node.name,
            docstring=docstring,
            parameters=parameters,
            returns=returns,
            file_path=""
        )
    
    def _parse_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Parse class node and extract documentation"""
        docstring = ast.get_docstring(node) or ""
        
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        return {
            'name': node.name,
            'docstring': docstring,
            'methods': methods
        }
    
    def _parse_terraform_file(self, file_path: Path) -> List[TerraformResource]:
        """Parse Terraform file and extract resource information"""
        try:
            with open(file_path, "r") as f:
                content = f.read()
            
            resources = []
            
            # Simple regex parsing for Terraform resources
            resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*{'
            matches = re.finditer(resource_pattern, content)
            
            for match in matches:
                resource_type = match.group(1)
                resource_name = match.group(2)
                
                # Extract description from comments (simple approach)
                description = f"{resource_type} resource"
                
                resources.append(TerraformResource(
                    type=resource_type,
                    name=resource_name,
                    description=description,
                    variables=[],
                    outputs=[],
                    file_path=str(file_path)
                ))
            
            return resources
        
        except Exception as e:
            logger.warning(f"Failed to parse Terraform file {file_path}: {e}")
            return []
    
    def _parse_terraform_variables(self, file_path: Path) -> List[Dict[str, str]]:
        """Parse Terraform variables file"""
        try:
            with open(file_path, "r") as f:
                content = f.read()
            
            variables = []
            
            # Simple regex parsing for variables
            var_pattern = r'variable\s+"([^"]+)"\s*{[^}]*description\s*=\s*"([^"]*)"[^}]*type\s*=\s*([^}\n]*)'
            matches = re.finditer(var_pattern, content, re.DOTALL)
            
            for match in matches:
                variables.append({
                    'name': match.group(1),
                    'description': match.group(2),
                    'type': match.group(3).strip()
                })
            
            return variables
        
        except Exception as e:
            logger.warning(f"Failed to parse variables file {file_path}: {e}")
            return []
    
    def _parse_terraform_outputs(self, file_path: Path) -> List[Dict[str, str]]:
        """Parse Terraform outputs file"""
        try:
            with open(file_path, "r") as f:
                content = f.read()
            
            outputs = []
            
            # Simple regex parsing for outputs
            output_pattern = r'output\s+"([^"]+)"\s*{[^}]*description\s*=\s*"([^"]*)"'
            matches = re.finditer(output_pattern, content, re.DOTALL)
            
            for match in matches:
                outputs.append({
                    'name': match.group(1),
                    'description': match.group(2)
                })
            
            return outputs
        
        except Exception as e:
            logger.warning(f"Failed to parse outputs file {file_path}: {e}")
            return []

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Generate documentation for ONS Data Platform')
    parser.add_argument('--project-root', default='.', help='Project root directory')
    parser.add_argument('--output-dir', help='Output directory for documentation')
    parser.add_argument('--component', help='Generate docs for specific component only')
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = DocumentationGenerator(args.project_root)
    
    if args.output_dir:
        generator.docs_dir = Path(args.output_dir)
        generator.docs_dir.mkdir(exist_ok=True)
    
    if args.component:
        # Generate docs for specific component
        component_dir = generator.src_dir / args.component
        if component_dir.exists():
            generator._generate_component_doc(args.component, component_dir)
        else:
            logger.error(f"Component {args.component} not found")
            return 1
    else:
        # Generate all documentation
        generator.generate_all_docs()
    
    return 0

if __name__ == '__main__':
    exit(main())