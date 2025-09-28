#!/usr/bin/env python3
"""
Create sample PDF files for testing PDF processor
Generates PDFs with tables similar to ONS data format
"""

import os
from pathlib import Path
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime, timedelta
import random


def create_sample_generation_data():
    """Create sample energy generation data"""
    dates = []
    start_date = datetime(2024, 1, 1)
    for i in range(30):
        dates.append((start_date + timedelta(days=i)).strftime('%d/%m/%Y'))
    
    data = {
        'Data': dates,
        'Hidrica (MW)': [random.randint(8000, 12000) for _ in range(30)],
        'Termica (MW)': [random.randint(2000, 5000) for _ in range(30)],
        'Eolica (MW)': [random.randint(1000, 3000) for _ in range(30)],
        'Solar (MW)': [random.randint(500, 1500) for _ in range(30)],
        'Nuclear (MW)': [random.randint(1800, 2000) for _ in range(30)]
    }
    
    return pd.DataFrame(data)


def create_sample_consumption_data():
    """Create sample energy consumption data"""
    regions = ['Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste']
    hours = [f'{h:02d}:00' for h in range(0, 24, 2)]
    
    data = []
    for region in regions:
        for hour in hours:
            data.append({
                'Região': region,
                'Hora': hour,
                'Consumo (MW)': random.randint(1000, 8000),
                'Demanda Máxima (MW)': random.randint(8000, 15000)
            })
    
    return pd.DataFrame(data)


def create_pdf_with_table(filename: str, title: str, df: pd.DataFrame):
    """Create PDF file with table data"""
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Add title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 20))
    
    # Convert DataFrame to table data
    table_data = [df.columns.tolist()] + df.values.tolist()
    
    # Create table
    table = Table(table_data)
    
    # Style the table
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # Add footer
    story.append(Spacer(1, 30))
    footer_text = f"Fonte: ONS - Operador Nacional do Sistema Elétrico<br/>Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    print(f"Created PDF: {filename}")


def create_malformed_pdf(filename: str):
    """Create a malformed PDF for error testing"""
    with open(filename, 'w') as f:
        f.write("This is not a valid PDF file content")
    print(f"Created malformed PDF: {filename}")


def create_empty_pdf(filename: str):
    """Create an empty PDF with no tables"""
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    story.append(Paragraph("Documento sem tabelas", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Este documento não contém tabelas de dados.", styles['Normal']))
    
    doc.build(story)
    print(f"Created empty PDF: {filename}")


def create_complex_layout_pdf(filename: str):
    """Create PDF with complex layout (multiple tables, mixed content)"""
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Title
    story.append(Paragraph("Relatório Complexo de Energia - Janeiro 2024", styles['Title']))
    story.append(Spacer(1, 20))
    
    # Introduction text
    intro_text = """
    Este relatório apresenta dados consolidados do setor elétrico brasileiro,
    incluindo informações de geração, consumo e transmissão de energia.
    Os dados são apresentados em múltiplas tabelas com diferentes formatos.
    """
    story.append(Paragraph(intro_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # First table - Generation summary
    gen_summary = pd.DataFrame({
        'Fonte': ['Hidráulica', 'Térmica', 'Eólica', 'Solar', 'Nuclear'],
        'Capacidade Instalada (MW)': [109000, 42000, 21000, 16000, 1990],
        'Geração Média (MW)': [65000, 8000, 12000, 8000, 1900],
        'Fator de Capacidade (%)': [59.6, 19.0, 57.1, 50.0, 95.5]
    })
    
    story.append(Paragraph("Tabela 1: Resumo da Geração por Fonte", styles['Heading2']))
    story.append(Spacer(1, 10))
    
    table1_data = [gen_summary.columns.tolist()] + gen_summary.values.tolist()
    table1 = Table(table1_data)
    table1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table1)
    story.append(Spacer(1, 30))
    
    # Second table - Regional consumption
    regional_data = pd.DataFrame({
        'Região': ['Norte', 'Nordeste', 'Sudeste', 'Sul', 'Centro-Oeste'],
        'População (milhões)': [18.9, 57.1, 89.6, 30.4, 16.7],
        'Consumo Total (GWh)': [2500, 4200, 12800, 3100, 1900],
        'Consumo per capita (kWh)': [132, 74, 143, 102, 114]
    })
    
    story.append(Paragraph("Tabela 2: Consumo Regional", styles['Heading2']))
    story.append(Spacer(1, 10))
    
    table2_data = [regional_data.columns.tolist()] + regional_data.values.tolist()
    table2 = Table(table2_data)
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table2)
    
    doc.build(story)
    print(f"Created complex PDF: {filename}")


def main():
    """Create all sample PDF files"""
    # Create samples directory
    samples_dir = Path('samples')
    samples_dir.mkdir(exist_ok=True)
    
    print("Creating sample PDF files for testing...")
    
    # 1. Simple generation data PDF
    gen_data = create_sample_generation_data()
    create_pdf_with_table(
        samples_dir / 'geracao_energia_janeiro_2024.pdf',
        'Geração de Energia Elétrica - Janeiro 2024',
        gen_data
    )
    
    # 2. Consumption data PDF
    cons_data = create_sample_consumption_data()
    create_pdf_with_table(
        samples_dir / 'consumo_regional_2024.pdf',
        'Consumo de Energia por Região - 2024',
        cons_data
    )
    
    # 3. Complex layout PDF
    create_complex_layout_pdf(samples_dir / 'relatorio_complexo_energia.pdf')
    
    # 4. Empty PDF (no tables)
    create_empty_pdf(samples_dir / 'documento_sem_tabelas.pdf')
    
    # 5. Malformed PDF for error testing
    create_malformed_pdf(samples_dir / 'arquivo_corrompido.pdf')
    
    print(f"\nSample PDF files created in '{samples_dir}' directory:")
    for pdf_file in samples_dir.glob('*.pdf'):
        print(f"  - {pdf_file.name}")
    
    print("\nThese files can be used to test the PDF processor with various scenarios:")
    print("  - Normal table extraction")
    print("  - Complex layouts with multiple tables")
    print("  - Empty documents")
    print("  - Malformed/corrupted files")


if __name__ == '__main__':
    main()