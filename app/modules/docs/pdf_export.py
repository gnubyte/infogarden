from flask import render_template_string
from weasyprint import HTML
import markdown
from datetime import datetime

def export_document_to_pdf(document, organization=None):
    """Export a markdown document to PDF"""
    # Convert markdown to HTML
    html_content = markdown.markdown(document.content or '', extensions=['extra', 'codehilite'])
    
    # Create HTML template with styling
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
            }}
            h3 {{
                color: #555;
            }}
            code {{
                background-color: #f4f4f4;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #3498db;
                color: white;
            }}
            img {{
                max-width: 100%;
                height: auto;
            }}
            .header {{
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #ecf0f1;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ecf0f1;
                font-size: 0.9em;
                color: #7f8c8d;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{document.title}</h1>
            {f'<p><strong>Organization:</strong> {organization.name}</p>' if organization else ''}
            <p><strong>Created:</strong> {document.created_at.strftime('%Y-%m-%d %H:%M:%S') if document.created_at else 'N/A'}</p>
            <p><strong>Last Updated:</strong> {document.updated_at.strftime('%Y-%m-%d %H:%M:%S') if document.updated_at else 'N/A'}</p>
        </div>
        <div class="content">
            {html_content}
        </div>
        <div class="footer">
            <p>Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    
    # Generate PDF
    pdf = HTML(string=html_template).write_pdf()
    return pdf

