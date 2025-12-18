#!/usr/bin/env python3
"""
Markdown to PDF Converter
Converts markdown documentation files to PDF format with proper styling.
"""

import os
import sys
import argparse
from pathlib import Path

try:
    import markdown
    from weasyprint import HTML, CSS
except ImportError:
    print("Required packages not installed. Installing...")
    os.system("pip install markdown weasyprint")
    import markdown
    from weasyprint import HTML, CSS


def create_pdf_style():
    """Create CSS styling for PDF output."""
    return """
    @page {
        size: A4;
        margin: 2cm;
        @top-center {
            content: "AI Animation Studio - Technical Documentation";
            font-size: 10pt;
            color: #666;
        }
        @bottom-right {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 10pt;
            color: #666;
        }
    }
    
    body {
        font-family: 'DejaVu Sans', 'Arial', sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #333;
        max-width: 100%;
    }
    
    h1 {
        font-size: 24pt;
        color: #2c3e50;
        border-bottom: 3px solid #3498db;
        padding-bottom: 10px;
        margin-top: 30px;
        margin-bottom: 20px;
        page-break-after: avoid;
    }
    
    h2 {
        font-size: 20pt;
        color: #34495e;
        border-bottom: 2px solid #ecf0f1;
        padding-bottom: 8px;
        margin-top: 25px;
        margin-bottom: 15px;
        page-break-after: avoid;
    }
    
    h3 {
        font-size: 16pt;
        color: #34495e;
        margin-top: 20px;
        margin-bottom: 12px;
        page-break-after: avoid;
    }
    
    h4 {
        font-size: 14pt;
        color: #555;
        margin-top: 15px;
        margin-bottom: 10px;
        page-break-after: avoid;
    }
    
    p {
        margin-bottom: 12px;
        text-align: justify;
    }
    
    code {
        font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
        font-size: 10pt;
        background-color: #f4f4f4;
        padding: 2px 6px;
        border-radius: 3px;
        color: #c7254e;
    }
    
    pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 15px;
        overflow-x: auto;
        page-break-inside: avoid;
        margin: 15px 0;
    }
    
    pre code {
        background-color: transparent;
        padding: 0;
        color: #333;
    }
    
    blockquote {
        border-left: 4px solid #3498db;
        margin: 15px 0;
        padding-left: 20px;
        color: #555;
        font-style: italic;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 20px 0;
        page-break-inside: avoid;
    }
    
    th, td {
        border: 1px solid #ddd;
        padding: 10px;
        text-align: left;
    }
    
    th {
        background-color: #3498db;
        color: white;
        font-weight: bold;
    }
    
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    ul, ol {
        margin: 15px 0;
        padding-left: 30px;
    }
    
    li {
        margin-bottom: 8px;
    }
    
    a {
        color: #3498db;
        text-decoration: none;
    }
    
    a:hover {
        text-decoration: underline;
    }
    
    hr {
        border: none;
        border-top: 2px solid #ecf0f1;
        margin: 30px 0;
    }
    
    .toc {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 5px;
        padding: 20px;
        margin: 20px 0;
        page-break-inside: avoid;
    }
    
    .toc ul {
        list-style-type: none;
        padding-left: 0;
    }
    
    .toc li {
        margin: 8px 0;
    }
    
    .toc a {
        color: #2c3e50;
        text-decoration: none;
    }
    
    .highlight {
        background-color: #fff3cd;
        padding: 2px 4px;
        border-radius: 3px;
    }
    
    .warning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px;
        margin: 15px 0;
    }
    
    .error {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 10px;
        margin: 15px 0;
    }
    
    .success {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px;
        margin: 15px 0;
    }
    """


def markdown_to_html(md_content, style_css):
    """Convert markdown content to HTML with styling."""
    # Convert markdown to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=[
            'extra',  # Tables, fenced code blocks, etc.
            'codehilite',  # Syntax highlighting
            'toc',  # Table of contents
            'tables',  # Better table support
        ],
        extension_configs={
            'codehilite': {
                'css_class': 'highlight',
                'use_pygments': False,
            },
            'toc': {
                'permalink': True,
            },
        }
    )
    
    # Wrap in full HTML document
    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>AI Animation Studio - Technical Documentation</title>
        <style>
            {style_css}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    
    return html_doc


def convert_md_to_pdf(md_file_path, output_pdf_path=None):
    """Convert markdown file to PDF."""
    md_path = Path(md_file_path)
    
    if not md_path.exists():
        print(f"Error: File '{md_file_path}' not found.")
        return False
    
    # Read markdown content
    print(f"Reading markdown file: {md_path}")
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Generate output PDF path if not provided
    if output_pdf_path is None:
        output_pdf_path = md_path.with_suffix('.pdf')
    else:
        output_pdf_path = Path(output_pdf_path)
    
    print(f"Converting to PDF: {output_pdf_path}")
    
    # Create CSS styling
    style_css = create_pdf_style()
    
    # Convert markdown to HTML
    html_doc = markdown_to_html(md_content, style_css)
    
    # Convert HTML to PDF
    try:
        HTML(string=html_doc).write_pdf(
            output_pdf_path,
            stylesheets=[CSS(string=style_css)]
        )
        print(f"✅ Successfully created PDF: {output_pdf_path}")
        print(f"   File size: {output_pdf_path.stat().st_size / 1024:.2f} KB")
        return True
    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        return False


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert Markdown files to PDF',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_md_to_pdf.py TECHNICAL_REPORT.md
  python convert_md_to_pdf.py TECHNICAL_REPORT.md -o report.pdf
  python convert_md_to_pdf.py *.md
        """
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='Markdown file(s) to convert'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output PDF file path (only for single file)'
    )
    
    args = parser.parse_args()
    
    # Convert each file
    success_count = 0
    for md_file in args.files:
        if len(args.files) == 1 and args.output:
            # Single file with custom output
            if convert_md_to_pdf(md_file, args.output):
                success_count += 1
        else:
            # Multiple files or default output
            if convert_md_to_pdf(md_file):
                success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Conversion complete: {success_count}/{len(args.files)} files converted")
    print(f"{'='*60}")
    
    return 0 if success_count == len(args.files) else 1


if __name__ == '__main__':
    sys.exit(main())

