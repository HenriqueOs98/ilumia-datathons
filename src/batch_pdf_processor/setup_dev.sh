#!/bin/bash
# Development setup script using uv for ONS PDF Processor

set -e

echo "🚀 Setting up ONS PDF Processor development environment"
echo "=================================================="

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "✅ uv installed successfully"
else
    echo "✅ uv already installed"
fi

# Install Python dependencies
echo "📚 Installing Python dependencies..."
uv pip install -r requirements.txt
echo "✅ Dependencies installed"

# Create sample PDFs for testing
echo "📄 Creating sample PDF files..."
uv run python create_sample_pdfs.py
echo "✅ Sample PDFs created"

# Run validation
echo "🔍 Validating implementation..."
uv run python validate_implementation.py
echo "✅ Validation complete"

# Run tests (if pytest is available)
echo "🧪 Running tests..."
if uv run python -c "import pytest" 2>/dev/null; then
    uv run pytest test_pdf_processor.py -v
    echo "✅ Tests completed"
else
    echo "⚠️  pytest not available, skipping tests"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set environment variables:"
echo "     export INPUT_S3_URI='s3://your-bucket/input.pdf'"
echo "     export OUTPUT_S3_URI='s3://your-bucket/output.parquet'"
echo ""
echo "  2. Run the processor:"
echo "     uv run python pdf_processor.py"
echo ""
echo "  3. Build Docker image:"
echo "     docker build -t ons-pdf-processor ."
echo ""
echo "Happy coding! 🐍📊"