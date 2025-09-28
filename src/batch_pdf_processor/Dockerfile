FROM python:3.11-slim

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y \
    ghostscript \
    libpoppler-cpp-dev \
    libpoppler-utils \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-por \
    libreoffice \
    default-jre \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Install Java-based Tabula
RUN wget -O /usr/local/bin/tabula.jar https://github.com/tabulapdf/tabula-java/releases/download/v1.0.5/tabula-1.0.5-jar-with-dependencies.jar

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies using uv for faster installation
# Includes specialized PDF libraries: camelot-py, tabula-py, pdfplumber
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Create directories for processing
RUN mkdir -p /tmp/pdf_processing /tmp/output

# Set environment variables
ENV PYTHONPATH=/app
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Run the PDF processor
CMD ["python", "pdf_processor.py"]