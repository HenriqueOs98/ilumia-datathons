# Batch Pdf Processor

# AWS Batch PDF Processor

This component processes PDF files containing energy data tables from ONS (Operador Nacional do Sistema Elétrico) and converts them to standardized Parquet format for the ONS Data Platform.

## Overview

The PDF processor is designed to run as an AWS Batch job and handles complex PDF table extraction using multiple specialized libraries:

- **Camelot**: Best for well-formatted tables with clear borders
- **Tabula**: Java-based extraction, good for complex layouts
- **pdfplumber**: Text-based extraction for simple tables

## Features

- **Multi-method extraction**: Uses multiple PDF processing libraries for maximum coverage
- **Data standardization**: Converts extracted data to ONS standard schema
- **Error handling**: Robust error handling for malformed PDFs and extraction failures
- **Brazilian format support**: Handles Brazilian number formats and date formats
- **Automatic data type inference**: Identifies energy sources, regions, and measurement units
- **Quality flags**: Tracks data quality and extraction methods

## Architecture

```
PDF File (S3) → AWS Batch Job → Standardized Parquet (S3)
                     ↓
              Multiple Extraction Methods:
              - Camelot (lattice/stream)
              - Tabula (Java-based)
              - pdfplumber (text-based)
                     ↓
              Data Standardization:
              - Timestamp extraction
              - Numeric conversion
              - Unit inference
              - Region/source detection
                     ↓
              Parquet Output with Metadata
```

## Docker Container

The processor runs in a Docker container with:

- Python 3.11 runtime
- **uv package manager**: For faster, more reliable dependency installation
- System dependencies: ghostscript, poppler-utils, tesseract-ocr
- Java runtime for Tabula
- Specialized Python libraries for PDF processing

### Benefits of using uv:
- **Faster installs**: 10-100x faster than pip
- **Better dependency resolution**: More reliable conflict resolution
- **Reproducible builds**: Consistent dependency versions
- **Smaller Docker layers**: More efficient caching

## Data Schema

### Input
- PDF files from ONS with energy data tables
- Various formats: generation, consumption, transmission data

### Output (Parquet)
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "dataset_type": "generation|consumption|transmission",
  "region": "sudeste|nordeste|norte|sul|centro-oeste|brasil",
  "energy_source": "hidrica|termica|eolica|solar|nuclear|outras",
  "measurement_type": "string",
  "value": 1234.56,
  "unit": "MW|GW|MWh|GWh|%",
  "quality_flag": "extracted|validated|estimated",
  "processing_metadata": {
    "processed_at": "2024-01-01T00:00:00Z",
    "processor_version": "1.0.0",
    "source_file": "filename.pdf",
    "extraction_method": "camelot_lattice|tabula|pdfplumber",
    "table_index": 0
  }
}
```

## Environment Variables

- `INPUT_S3_URI`: S3 URI of input PDF file
- `OUTPUT_S3_URI`: S3 URI for output Parquet file

## Usage

### Local Development

#### Quick Setup (Recommended)
```bash
# Run the automated setup script
./setup_dev.sh
```

#### Manual Setup
1. Install dependencies using uv (recommended):
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -r requirements.txt
```

Or using pip:
```bash
pip install -r requirements.txt
```

2. Create sample PDFs for testing:
```bash
python create_sample_pdfs.py
```

3. Run tests:
```bash
# Using uv (recommended)
uv run pytest test_pdf_processor.py -v

# Or using python directly
python -m pytest test_pdf_processor.py -v
```

4. Process a PDF file:
```bash
export INPUT_S3_URI="s3://bucket/input.pdf"
export OUTPUT_S3_URI="s3://bucket/output.parquet"

# Using uv (recommended)
uv run python pdf_processor.py

# Or using python directly
python pdf_processor.py
```

### Docker Build

```bash
docker build -t ons-pdf-processor .
```

### AWS Batch Deployment

The container is deployed as an AWS Batch job definition and triggered by Step Functions when PDF files are detected.

## Error Handling

The processor handles various error scenarios:

- **Malformed PDFs**: Logs error and returns failure status
- **No tables found**: Attempts multiple extraction methods before failing
- **Data validation errors**: Applies quality flags and continues processing
- **S3 access errors**: Proper error reporting for debugging
- **Memory/timeout issues**: Configurable resource limits in Batch

## Testing

### Unit Tests
- PDF parsing and table extraction
- Data standardization logic
- Error handling scenarios
- S3 integration mocking

### Integration Tests
- End-to-end processing with sample PDFs
- Multiple extraction method validation
- Error scenario testing
- Performance testing with large files

### Sample Test Files

The `create_sample_pdfs.py` script generates various test scenarios:

1. **Normal generation data**: Standard energy generation tables
2. **Regional consumption**: Multi-region consumption data
3. **Complex layout**: Multiple tables with mixed content
4. **Empty document**: PDF without tables
5. **Malformed file**: Corrupted PDF for error testing

## Performance Considerations

- **Memory usage**: Configurable based on PDF size (8-16 GB recommended)
- **Processing time**: Typically 2-5 minutes per PDF
- **Concurrent processing**: Multiple Batch jobs can run in parallel
- **Cost optimization**: Uses Fargate Spot instances when possible

## Monitoring

The processor outputs structured JSON logs for monitoring:

- Processing start/completion times
- Extraction method success rates
- Data quality metrics
- Error details and stack traces

## Dependencies

### System Dependencies
- ghostscript: PDF rendering
- poppler-utils: PDF utilities
- tesseract-ocr: OCR capabilities
- default-jre: Java runtime for Tabula

### Python Dependencies
- boto3: AWS SDK
- pandas: Data manipulation
- camelot-py: PDF table extraction
- tabula-py: Java-based PDF processing
- pdfplumber: Text-based PDF parsing
- pyarrow: Parquet file format

## Troubleshooting

### Common Issues

1. **No tables extracted**: Try different extraction methods or check PDF quality
2. **Memory errors**: Increase Batch job memory allocation
3. **Java errors**: Ensure Java runtime is properly installed
4. **S3 permissions**: Verify IAM roles have proper S3 access

### Debug Mode

Set logging level to DEBUG for detailed extraction information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

When adding new features:

1. Update extraction methods in `_extract_tables_multi_method()`
2. Add data standardization logic in `_standardize_data()`
3. Include comprehensive tests for new functionality
4. Update Docker dependencies if needed
5. Document new environment variables or configuration options
## Code Documentation

### validate_implementation.py

Validation script for AWS Batch PDF Processor implementation
Checks if all requirements from task 2.3 are met

**Functions:**

#### `validate_dockerfile`

Validate Dockerfile exists and contains required components

#### `validate_requirements`

Validate requirements.txt contains necessary libraries

#### `validate_pdf_processor`

Validate PDF processor implementation

#### `validate_tests`

Validate test implementation

#### `validate_sample_pdfs`

Validate sample PDF creation script

#### `validate_readme`

Validate README documentation

#### `main`

Run all validations

### pdf_processor.py

AWS Batch PDF Processor for ONS Data Platform
Extracts tables from PDF files and converts to standardized Parquet format

**Functions:**

#### `main`

Main entry point for AWS Batch job

#### `__init__`

**Parameters:**
- `self` (Any): 

#### `process_pdf_file`

Main processing function for PDF files

Args:
    input_s3_uri: S3 URI of input PDF file
    output_s3_uri: S3 URI for output Parquet file
    
Returns:
    Processing result dictionary

**Parameters:**
- `self` (Any): 
- `input_s3_uri` (Any): 
- `output_s3_uri` (Any): 

#### `_parse_s3_uri`

Parse S3 URI into bucket and key

**Parameters:**
- `self` (Any): 
- `s3_uri` (Any): 

#### `_download_pdf`

Download PDF file from S3 to local temporary directory

**Parameters:**
- `self` (Any): 
- `bucket` (Any): 
- `key` (Any): 

#### `_extract_tables_multi_method`

Extract tables using multiple methods for better coverage

**Parameters:**
- `self` (Any): 
- `pdf_path` (Any): 

#### `_standardize_data`

Standardize extracted table data to ONS format

**Parameters:**
- `self` (Any): 
- `tables` (Any): 
- `source_file` (Any): 

#### `_identify_timestamp_column`

Identify which column contains timestamp data

**Parameters:**
- `self` (Any): 
- `df` (Any): 

#### `_is_header_row`

Check if row appears to be a header

**Parameters:**
- `self` (Any): 
- `row` (Any): 

#### `_extract_timestamp`

Extract timestamp from row

**Parameters:**
- `self` (Any): 
- `row` (Any): 
- `timestamp_col` (Any): 

#### `_convert_to_numeric`

Convert value to numeric, handling Brazilian number formats

**Parameters:**
- `self` (Any): 
- `value` (Any): 

#### `_infer_dataset_type`

Infer dataset type from filename and column name

**Parameters:**
- `self` (Any): 
- `filename` (Any): 
- `column` (Any): 

#### `_extract_region`

Extract region information

**Parameters:**
- `self` (Any): 
- `filename` (Any): 
- `row` (Any): 

#### `_extract_energy_source`

Extract energy source from column name or row data

**Parameters:**
- `self` (Any): 
- `column` (Any): 
- `row` (Any): 

#### `_infer_unit`

Infer measurement unit from column name and value

**Parameters:**
- `self` (Any): 
- `column` (Any): 
- `value` (Any): 

#### `_save_as_parquet`

Save DataFrame as Parquet file

**Parameters:**
- `self` (Any): 
- `df` (Any): 

#### `_upload_to_s3`

Upload file to S3

**Parameters:**
- `self` (Any): 
- `local_path` (Any): 
- `bucket` (Any): 
- `key` (Any): 

#### `_cleanup_temp_files`

Clean up temporary files

**Parameters:**
- `self` (Any): 
- `file_paths` (Any): 

#### `setup_logging`

**Classes:**

#### `PDFProcessor`

Main PDF processing class for extracting tables and standardizing data

### create_sample_pdfs.py

Create sample PDF files for testing PDF processor
Generates PDFs with tables similar to ONS data format

**Functions:**

#### `create_sample_generation_data`

Create sample energy generation data

#### `create_sample_consumption_data`

Create sample energy consumption data

#### `create_pdf_with_table`

Create PDF file with table data

**Parameters:**
- `filename` (Any): 
- `title` (Any): 
- `df` (Any): 

#### `create_malformed_pdf`

Create a malformed PDF for error testing

**Parameters:**
- `filename` (Any): 

#### `create_empty_pdf`

Create an empty PDF with no tables

**Parameters:**
- `filename` (Any): 

#### `create_complex_layout_pdf`

Create PDF with complex layout (multiple tables, mixed content)

**Parameters:**
- `filename` (Any): 

#### `main`

Create all sample PDF files

## Dependencies

- `boto3==1.34.0`
- `pandas==2.1.4`
- `pyarrow==14.0.2`
- `camelot-py[cv]==0.11.0`
- `tabula-py==2.9.0`
- `PyPDF2==3.0.1`
- `pdfplumber==0.10.3`
- `numpy==1.24.4`
- `openpyxl==3.1.2`
- `awswrangler==3.5.2`
- `python-dotenv==1.0.0`
- `pytest==7.4.3`
- `pytest-mock==3.12.0`
- `moto[s3]==4.2.14`
- `reportlab==4.0.7`

