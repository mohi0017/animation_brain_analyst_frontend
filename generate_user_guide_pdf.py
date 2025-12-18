"""
Generate PDF User Guide from Markdown
Simple script to convert USER_GUIDE.md to PDF format for end clients.
"""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

def generate_pdf():
    """Convert USER_GUIDE.md to PDF with nice formatting."""
    
    # Read markdown file
    md_file = Path("USER_GUIDE.md")
    if not md_file.exists():
        print("❌ USER_GUIDE.md not found!")
        return
    
    md_content = md_file.read_text(encoding='utf-8')
    
    # Convert markdown to HTML
    html_content = markdown.markdown(
        md_content,
        extensions=['extra', 'codehilite', 'tables']
    )
    
    # Add CSS styling for professional look
    css_style = """
    @page {
        size: A4;
        margin: 2cm;
    }
    
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        font-size: 11pt;
    }
    
    h1 {
        color: #2c3e50;
        border-bottom: 3px solid #3498db;
        padding-bottom: 10px;
        font-size: 24pt;
        margin-top: 0;
    }
    
    h2 {
        color: #34495e;
        border-bottom: 2px solid #95a5a6;
        padding-bottom: 5px;
        margin-top: 20px;
        font-size: 16pt;
        page-break-after: avoid;
    }
    
    h3 {
        color: #7f8c8d;
        margin-top: 15px;
        font-size: 13pt;
        page-break-after: avoid;
    }
    
    h4 {
        color: #95a5a6;
        margin-top: 10px;
        font-size: 12pt;
    }
    
    p {
        margin: 8px 0;
        text-align: justify;
    }
    
    ul, ol {
        margin: 10px 0;
        padding-left: 25px;
    }
    
    li {
        margin: 5px 0;
    }
    
    code {
        background-color: #ecf0f1;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 10pt;
    }
    
    pre {
        background-color: #2c3e50;
        color: #ecf0f1;
        padding: 15px;
        border-radius: 5px;
        overflow-x: auto;
        page-break-inside: avoid;
    }
    
    blockquote {
        border-left: 4px solid #3498db;
        padding-left: 15px;
        margin: 15px 0;
        color: #555;
        font-style: italic;
    }
    
    hr {
        border: none;
        border-top: 2px solid #bdc3c7;
        margin: 20px 0;
    }
    
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 15px 0;
    }
    
    th, td {
        border: 1px solid #bdc3c7;
        padding: 8px;
        text-align: left;
    }
    
    th {
        background-color: #3498db;
        color: white;
        font-weight: bold;
    }
    
    .page-break {
        page-break-before: always;
    }
    
    /* Emoji support */
    .emoji {
        font-size: 1.2em;
    }
    """
    
    # Wrap HTML with proper structure
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>AI Animation Studio - User Guide</title>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Generate PDF
    output_file = Path("AI_Animation_Studio_User_Guide.pdf")
    
    try:
        HTML(string=full_html).write_pdf(
            output_file,
            stylesheets=[CSS(string=css_style)]
        )
        print(f"✅ PDF generated successfully: {output_file}")
        print(f"📄 File size: {output_file.stat().st_size / 1024:.1f} KB")
        
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        print("\n💡 Make sure you have installed:")
        print("   pip install markdown weasyprint")


if __name__ == "__main__":
    generate_pdf()

