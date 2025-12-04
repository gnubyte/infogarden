import os
import json
import zipfile
import threading
from datetime import datetime
from io import BytesIO
from flask import current_app
from app.core import models
from app.modules.docs.models import Document, DocumentFolder
from app.modules.contacts.models import Contact
from app.modules.passwords.models import PasswordEntry
from app.core.encryption import decrypt_data
from app.modules.docs.pdf_export import export_document_to_pdf
from app.modules.docs.word_export import export_document_to_word
def html_to_markdown(html_content):
    """Convert HTML to Markdown (basic conversion)"""
    if not html_content:
        return ''
    
    import html as html_module
    # Remove script and style tags
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert headings
    html_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1\n\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1\n\n', html_content, flags=re.IGNORECASE)
    
    # Convert bold and italic
    html_content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html_content, flags=re.IGNORECASE)
    
    # Convert links
    html_content = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)', html_content, flags=re.IGNORECASE)
    
    # Convert images
    html_content = re.sub(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>', r'![\2](\1)', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>', r'![](\1)', html_content, flags=re.IGNORECASE)
    
    # Convert lists
    html_content = re.sub(r'<ul[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ul>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<ol[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ol>', '\n', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', html_content, flags=re.IGNORECASE)
    
    # Convert paragraphs
    html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_content, flags=re.IGNORECASE)
    
    # Convert line breaks
    html_content = re.sub(r'<br[^>]*>', '\n', html_content, flags=re.IGNORECASE)
    
    # Convert code blocks
    html_content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_content, flags=re.IGNORECASE)
    
    # Convert blockquotes
    html_content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'> \1', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove remaining HTML tags
    html_content = re.sub(r'<[^>]+>', '', html_content)
    
    # Decode HTML entities
    html_content = html_module.unescape(html_content)
    
    # Clean up extra whitespace
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    html_content = html_content.strip()
    
    return html_content
import markdown
import re

def export_document_to_rtf(document, organization=None):
    """Export a document to RTF format"""
    # Convert content to HTML first
    if document.content_type == 'html':
        html_content = document.content or ''
    else:
        # Convert markdown to HTML
        html_content = markdown.markdown(document.content or '', extensions=['extra', 'codehilite'])
    
    # Convert HTML to RTF
    rtf_content = html_to_rtf(html_content)
    
    # Build RTF document
    rtf_doc = f"""{{\\rtf1\\ansi\\deff0
{{\\fonttbl{{\\f0 Times New Roman;}}}}
\\f0\\fs24

{{\\b {escape_rtf(document.title)}}}\\par\\par
"""
    
    if organization:
        rtf_doc += f"Organization: {escape_rtf(organization.name)}\\par"
    rtf_doc += f"Created: {document.created_at.strftime('%Y-%m-%d %H:%M:%S') if document.created_at else 'N/A'}\\par"
    rtf_doc += f"Last Updated: {document.updated_at.strftime('%Y-%m-%d %H:%M:%S') if document.updated_at else 'N/A'}\\par\\par"
    
    rtf_doc += rtf_content
    rtf_doc += f"\\par\\par\\par Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\par}}"
    
    return rtf_doc.encode('utf-8')

def html_to_rtf(html_content):
    """Convert HTML to RTF format"""
    if not html_content:
        return ""
    
    # Remove script and style tags
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Convert headings
    html_content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\\par\\par{\\b\\fs32 \1}\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\\par\\par{\\b\\fs28 \1}\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\\par{\\b\\fs24 \1}\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\\par{\\b \1}\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h5[^>]*>(.*?)</h5>', r'\\par{\\b \1}\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<h6[^>]*>(.*?)</h6>', r'\\par{\\b \1}\\par', html_content, flags=re.IGNORECASE)
    
    # Convert bold and italic
    html_content = re.sub(r'<strong[^>]*>(.*?)</strong>', r'{\\b \1}', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<b[^>]*>(.*?)</b>', r'{\\b \1}', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<em[^>]*>(.*?)</em>', r'{\\i \1}', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<i[^>]*>(.*?)</i>', r'{\\i \1}', html_content, flags=re.IGNORECASE)
    
    # Convert code blocks
    html_content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'\\par{\\f1\\fs20 \1}\\par', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<code[^>]*>(.*?)</code>', r'{\\f1 \1}', html_content, flags=re.IGNORECASE)
    
    # Convert paragraphs
    html_content = re.sub(r'<p[^>]*>(.*?)</p>', r'\\par\1\\par', html_content, flags=re.IGNORECASE)
    
    # Convert line breaks
    html_content = re.sub(r'<br[^>]*>', '\\par', html_content, flags=re.IGNORECASE)
    
    # Convert lists
    html_content = re.sub(r'<ul[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ul>', '\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<ol[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ol>', '\\par', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<li[^>]*>(.*?)</li>', r'\\par\\bullet \1', html_content, flags=re.IGNORECASE)
    
    # Convert blockquotes
    html_content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\\par{\\i \1}\\par', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove remaining HTML tags
    html_content = re.sub(r'<[^>]+>', '', html_content)
    
    # Escape RTF special characters
    html_content = escape_rtf(html_content)
    
    return html_content

def escape_rtf(text):
    """Escape RTF special characters"""
    if not text:
        return ""
    text = text.replace('\\', '\\\\')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('\n', '\\par ')
    return text

def get_folder_path(folder, folders_dict):
    """Get the full path of a folder"""
    path_parts = []
    current = folder
    while current:
        path_parts.insert(0, current.name)
        if current.parent_id and current.parent_id in folders_dict:
            current = folders_dict[current.parent_id]
        else:
            current = None
    return '/'.join(path_parts) if path_parts else ''

def build_hierarchy_text(org_id):
    """Build a text representation of the file and folder hierarchy"""
    folders = DocumentFolder.query.filter_by(org_id=org_id).all()
    documents = Document.query.filter_by(org_id=org_id).all()
    
    folders_dict = {f.id: f for f in folders}
    
    # Build folder tree
    root_folders = [f for f in folders if f.parent_id is None]
    
    lines = []
    lines.append("=" * 80)
    lines.append("FILE AND FOLDER HIERARCHY")
    lines.append("=" * 80)
    lines.append("")
    
    def add_folder(folder, indent=0):
        path = get_folder_path(folder, folders_dict)
        lines.append("  " * indent + f"[FOLDER] {path}/")
        # Add documents in this folder
        folder_docs = [d for d in documents if d.folder_id == folder.id]
        for doc in sorted(folder_docs, key=lambda x: x.title):
            lines.append("  " * (indent + 1) + f"[DOC] {doc.title}")
        # Add subfolders
        subfolders = [f for f in folders if f.parent_id == folder.id]
        for subfolder in sorted(subfolders, key=lambda x: x.name):
            add_folder(subfolder, indent + 1)
    
    # Add root folders
    for folder in sorted(root_folders, key=lambda x: x.name):
        add_folder(folder, 0)
    
    # Add documents without folders
    root_docs = [d for d in documents if d.folder_id is None]
    if root_docs:
        lines.append("")
        lines.append("[ROOT DOCUMENTS]")
        for doc in sorted(root_docs, key=lambda x: x.title):
            lines.append(f"  [DOC] {doc.title}")
    
    return "\n".join(lines)

def generate_org_export(org_id, export_job_id, db_session):
    """Generate the complete export for an organization"""
    try:
        # Update status to processing
        export_job = models.ExportJob.query.get(export_job_id)
        if not export_job:
            return
        
        # Check if already cancelled
        if export_job.status == 'cancelled':
            return
        
        export_job.status = 'processing'
        export_job.progress = 0
        db_session.commit()
        
        org = models.Organization.query.get(org_id)
        if not org:
            export_job.status = 'failed'
            export_job.error_message = 'Organization not found'
            db_session.commit()
            return
        
        # Create export directory
        export_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
        os.makedirs(export_folder, exist_ok=True)
        
        export_dir = os.path.join(export_folder, f'org_{org_id}_{export_job_id}')
        os.makedirs(export_dir, exist_ok=True)
        
        # Get all data
        folders = DocumentFolder.query.filter_by(org_id=org_id).all()
        documents = Document.query.filter_by(org_id=org_id).all()
        contacts = Contact.query.filter_by(org_id=org_id).all()
        passwords = PasswordEntry.query.filter_by(org_id=org_id).all()
        
        folders_dict = {f.id: f for f in folders}
        total_items = len(documents) * 4 + len(contacts) + len(passwords) + 2  # 4 formats per doc + contacts + passwords + hierarchy + contacts json
        processed = 0
        
        # Create folder structure in export directory
        for folder in folders:
            folder_path = get_folder_path(folder, folders_dict)
            if folder_path:
                full_path = os.path.join(export_dir, 'documents', folder_path)
                os.makedirs(full_path, exist_ok=True)
        
        # Ensure documents root exists
        os.makedirs(os.path.join(export_dir, 'documents'), exist_ok=True)
        
        # Export documents in all formats
        for doc in documents:
            folder_path = ''
            if doc.folder_id and doc.folder_id in folders_dict:
                folder_path = get_folder_path(folders_dict[doc.folder_id], folders_dict)
            
            # Sanitize filename
            safe_title = "".join(c for c in doc.title if c.isalnum() or c in (' ', '-', '_', '.')).strip()
            
            # Markdown
            if doc.content_type == 'html':
                md_content = html_to_markdown(doc.content or '')
            else:
                md_content = doc.content or ''
            
            # Determine markdown file path
            if folder_path:
                md_path = os.path.join(export_dir, 'documents', folder_path, f'{safe_title}.md')
            else:
                md_path = os.path.join(export_dir, 'documents', f'{safe_title}.md')
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            processed += 1
            # Check if cancelled before continuing
            db_session.refresh(export_job)
            if export_job.status == 'cancelled':
                return
            export_job.progress = int((processed / total_items) * 100)
            db_session.commit()
            
            # PDF
            db_session.refresh(export_job)
            if export_job.status == 'cancelled':
                return
            pdf_data = export_document_to_pdf(doc, org)
            pdf_path = md_path.replace('.md', '.pdf')
            with open(pdf_path, 'wb') as f:
                f.write(pdf_data)
            processed += 1
            export_job.progress = int((processed / total_items) * 100)
            db_session.commit()
            
            # Word
            db_session.refresh(export_job)
            if export_job.status == 'cancelled':
                return
            word_data = export_document_to_word(doc, org)
            word_path = md_path.replace('.md', '.docx')
            with open(word_path, 'wb') as f:
                f.write(word_data)
            processed += 1
            export_job.progress = int((processed / total_items) * 100)
            db_session.commit()
            
            # RTF
            db_session.refresh(export_job)
            if export_job.status == 'cancelled':
                return
            rtf_data = export_document_to_rtf(doc, org)
            rtf_path = md_path.replace('.md', '.rtf')
            with open(rtf_path, 'wb') as f:
                f.write(rtf_data)
            processed += 1
            export_job.progress = int((processed / total_items) * 100)
            db_session.commit()
        
        # Check if cancelled before exporting contacts
        db_session.refresh(export_job)
        if export_job.status == 'cancelled':
            return
        
        # Export contacts as JSON
        contacts_data = []
        for contact in contacts:
            contacts_data.append({
                'id': contact.id,
                'name': contact.name,
                'role': contact.role,
                'email': contact.email,
                'phone': contact.phone,
                'text_number': contact.text_number,
                'notes': contact.notes,
                'emergency_contact': contact.emergency_contact,
                'created_at': contact.created_at.isoformat() if contact.created_at else None
            })
        
        contacts_path = os.path.join(export_dir, 'contacts.json')
        with open(contacts_path, 'w', encoding='utf-8') as f:
            json.dump(contacts_data, f, indent=2, ensure_ascii=False)
        processed += 1
        export_job.progress = int((processed / total_items) * 100)
        db_session.commit()
        
        # Export passwords as JSON (decrypted)
        passwords_data = []
        for password in passwords:
            decrypted_password = None
            decrypted_2fa = None
            try:
                if password.encrypted_password:
                    decrypted_password = decrypt_data(password.encrypted_password)
            except:
                pass
            try:
                if password.encrypted_2fa_secret:
                    decrypted_2fa = decrypt_data(password.encrypted_2fa_secret)
            except:
                pass
            
            passwords_data.append({
                'id': password.id,
                'title': password.title,
                'link': password.link,
                'username': password.username,
                'email': password.email,
                'password': decrypted_password,
                '2fa_secret': decrypted_2fa,
                'date_added': password.date_added.isoformat() if password.date_added else None
            })
        
        passwords_path = os.path.join(export_dir, 'passwords.json')
        with open(passwords_path, 'w', encoding='utf-8') as f:
            json.dump(passwords_data, f, indent=2, ensure_ascii=False)
        processed += 1
        # Check if cancelled before continuing
        db_session.refresh(export_job)
        if export_job.status == 'cancelled':
            return
        export_job.progress = int((processed / total_items) * 100)
        db_session.commit()
        
        # Create hierarchy text file
        hierarchy_text = build_hierarchy_text(org_id)
        hierarchy_path = os.path.join(export_dir, 'hierarchy.txt')
        with open(hierarchy_path, 'w', encoding='utf-8') as f:
            f.write(hierarchy_text)
        processed += 1
        export_job.progress = int((processed / total_items) * 100)
        db_session.commit()
        
        # Check if cancelled before creating ZIP
        db_session.refresh(export_job)
        if export_job.status == 'cancelled':
            return
        
        # Create ZIP file
        zip_path = os.path.join(export_folder, f'org_{org_id}_export_{export_job_id}.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(export_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, export_dir)
                    zipf.write(file_path, arcname)
        
        # Clean up export directory (keep ZIP)
        import shutil
        shutil.rmtree(export_dir)
        
        # Update export job
        export_job.status = 'completed'
        export_job.progress = 100
        export_job.file_path = zip_path
        export_job.completed_at = datetime.utcnow()
        db_session.commit()
        
    except Exception as e:
        export_job = models.ExportJob.query.get(export_job_id)
        if export_job:
            export_job.status = 'failed'
            export_job.error_message = str(e)
            db_session.commit()

def cleanup_old_exports():
    """Remove export files and jobs older than 30 days"""
    try:
        from flask import current_app
        from datetime import timedelta
        from app import db_session
        
        with current_app.app_context():
            export_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')
            if not os.path.exists(export_folder):
                return
            
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            # Clean up old export files
            for filename in os.listdir(export_folder):
                if filename.startswith('org_') and filename.endswith('.zip'):
                    filepath = os.path.join(export_folder, filename)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_date:
                            os.remove(filepath)
                    except Exception:
                        pass  # Ignore errors deleting files
            
            # Clean up old export jobs from database
            old_jobs = models.ExportJob.query.filter(
                models.ExportJob.created_at < cutoff_date
            ).all()
            
            for job in old_jobs:
                # Delete associated file if it exists
                if job.file_path and os.path.exists(job.file_path):
                    try:
                        os.remove(job.file_path)
                    except:
                        pass
                db_session.delete(job)
            
            db_session.commit()
    except Exception as e:
        # Log error but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error cleaning up old exports: {str(e)}")

