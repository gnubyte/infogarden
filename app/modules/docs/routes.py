from flask import render_template, request, redirect, url_for, flash, send_file, session, jsonify
from flask_login import login_required, current_user
from io import BytesIO, SEEK_END
from app.modules.docs import bp
from app.modules.docs.models import Document, DocumentFolder, Software, DocumentFile
from app.core import models
from app.core.auth import require_org_access
from app.core.activity_logger import log_activity
from app.modules.docs.pdf_export import export_document_to_pdf
from app.modules.docs.word_export import export_document_to_word
from app.core.sidebar_utils import build_document_tree
from app.core.smtp_utils import send_email, get_smtp_settings
from app import db_session, csrf
import os
import re
import html
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'rtf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'webp'}

def allowed_document_file(filename):
    """Check if file extension is allowed for document uploads"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS

def get_mime_type(filename):
    """Get MIME type from filename"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    mime_types = {
        'pdf': 'application/pdf',
        'rtf': 'application/rtf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp'
    }
    return mime_types.get(ext, 'application/octet-stream')

def html_to_markdown(html_content):
    """Convert HTML to Markdown (basic conversion)"""
    if not html_content:
        return ''
    
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
    html_content = html.unescape(html_content)
    
    # Clean up extra whitespace
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    html_content = html_content.strip()
    
    return html_content

@bp.route('/convert-content', methods=['POST'])
@csrf.exempt
@login_required
def convert_content():
    """Convert content between markdown and HTML"""
    data = request.get_json()
    content = data.get('content', '')
    from_type = data.get('from_type', 'markdown')
    to_type = data.get('to_type', 'html')
    
    if from_type == 'markdown' and to_type == 'html':
        import markdown
        html_content = markdown.markdown(content, extensions=['extra', 'codehilite'])
        return jsonify({'content': html_content, 'content_type': 'html'})
    elif from_type == 'html' and to_type == 'markdown':
        markdown_content = html_to_markdown(content)
        return jsonify({'content': markdown_content, 'content_type': 'markdown'})
    else:
        return jsonify({'error': 'Invalid conversion'}), 400

@bp.route('/')
@login_required
def index():
    """List documents for current org"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
    doc_tree = build_document_tree(documents, org_id)
    
    # Get passwords, contacts, and locations for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    from app.modules.locations.models import Location
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    locations = Location.query.filter_by(org_id=org_id).order_by(Location.name).limit(20).all()
    
    log_activity('view', 'document', None)
    return render_template('modules/docs/list.html', documents=documents, folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts, locations=locations, current_folder=None, breadcrumb_path=[])

@bp.route('/folder/<int:folder_id>')
@login_required
def folder_view(folder_id):
    """View documents in a specific folder"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    # Get the folder
    folder = DocumentFolder.query.filter_by(id=folder_id, org_id=org_id).first()
    if not folder:
        flash('Folder not found', 'error')
        return redirect(url_for('docs.index'))
    
    # Get documents in this folder only
    documents = Document.query.filter_by(org_id=org_id, folder_id=folder_id).order_by(Document.title).all()
    
    # Get all folders for the org (for sidebar)
    folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
    
    # Get subfolders (folders that have this folder as parent)
    subfolders = DocumentFolder.query.filter_by(org_id=org_id, parent_id=folder_id).order_by(DocumentFolder.name).all()
    
    # Build document tree for sidebar
    all_documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(all_documents, org_id)
    
    # Build breadcrumb path
    breadcrumb_path = []
    current = folder
    while current:
        breadcrumb_path.insert(0, current)
        current = current.parent
    
    # Get passwords, contacts, and locations for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    from app.modules.locations.models import Location
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    locations = Location.query.filter_by(org_id=org_id).order_by(Location.name).limit(20).all()
    
    # Get files in this folder
    folder_files = DocumentFile.query.filter_by(org_id=org_id, folder_id=folder_id).order_by(DocumentFile.name).all()
    
    log_activity('view', 'folder', folder_id)
    return render_template('modules/docs/list.html', documents=documents, folders=subfolders, doc_tree=doc_tree, passwords=passwords, contacts=contacts, locations=locations, current_folder=folder, breadcrumb_path=breadcrumb_path, folder_files=folder_files)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new document"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    # Get folder_id from query parameter (for contextual folder creation)
    default_folder_id = request.args.get('folder_id', type=int)
    
    # Validate default_folder_id belongs to the org if provided
    if default_folder_id:
        folder = DocumentFolder.query.get(default_folder_id)
        if not folder or folder.org_id != org_id:
            default_folder_id = None  # Invalid folder, ignore it
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content', '')
        content_type = request.form.get('content_type', 'markdown')
        folder_id = request.form.get('folder_id')
        folder_id = int(folder_id) if folder_id and folder_id != 'None' else None
        
        if not title:
            flash('Title is required', 'error')
            # Get sidebar data for error case
            from app.modules.passwords.models import PasswordEntry
            from app.modules.contacts.models import Contact
            documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
            folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
            doc_tree = build_document_tree(documents, org_id)
            passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
            contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
            return render_template('modules/docs/create.html', folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts, default_folder_id=default_folder_id)
        
        # Validate folder belongs to same org
        if folder_id:
            folder = DocumentFolder.query.get(folder_id)
            if not folder or folder.org_id != org_id:
                flash('Invalid folder selected', 'error')
                return redirect(url_for('docs.create'))
        
        # Strip base64 images from content as a fallback (should be handled client-side, but this prevents DB errors)
        if content_type == 'html' and 'data:image/' in content:
            import re
            # Remove base64 image tags
            content = re.sub(r'<img[^>]+src="data:image/[^"]+"[^>]*>', '', content)
            flash('Warning: Some images were removed because they were too large. Please upload images using the image button instead.', 'warning')
        
        doc = Document(
            org_id=org_id,
            folder_id=folder_id,
            title=title,
            content=content,
            content_type=content_type,
            created_by=current_user.id
        )
        db_session.add(doc)
        db_session.commit()
        
        log_activity('create', 'document', doc.id)
        flash('Document created successfully', 'success')
        return redirect(url_for('docs.view', doc_id=doc.id))
    
    # Get sidebar data for GET request
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
    doc_tree = build_document_tree(documents, org_id)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/create.html', folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts, default_folder_id=default_folder_id)

@bp.route('/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(doc_id):
    """Edit document"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        flash('You do not have access to this document', 'error')
        return redirect(url_for('docs.index'))
    
    if request.method == 'POST':
        doc.title = request.form.get('title')
        doc.content = request.form.get('content', '')
        doc.content_type = request.form.get('content_type', 'markdown')
        folder_id = request.form.get('folder_id')
        folder_id = int(folder_id) if folder_id and folder_id != 'None' else None
        
        # Validate folder belongs to same org
        if folder_id:
            folder = DocumentFolder.query.get(folder_id)
            if not folder or folder.org_id != doc.org_id:
                flash('Invalid folder selected', 'error')
                return redirect(url_for('docs.edit', doc_id=doc_id))
        
        # Strip base64 images from content as a fallback (should be handled client-side, but this prevents DB errors)
        content = request.form.get('content', '')
        if doc.content_type == 'html' and 'data:image/' in content:
            import re
            # Remove base64 image tags
            content = re.sub(r'<img[^>]+src="data:image/[^"]+"[^>]*>', '', content)
            flash('Warning: Some images were removed because they were too large. Please upload images using the image button instead.', 'warning')
        
        doc.folder_id = folder_id
        doc.content = content
        doc.updated_by = current_user.id
        db_session.commit()
        
        log_activity('update', 'document', doc_id)
        flash('Document updated successfully', 'success')
        return redirect(url_for('docs.view', doc_id=doc.id))
    
    # Get all documents, passwords, and contacts for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=doc.org_id).order_by(Document.title).all()
    folders = DocumentFolder.query.filter_by(org_id=doc.org_id).order_by(DocumentFolder.name).all()
    doc_tree = build_document_tree(documents, doc.org_id)
    passwords = PasswordEntry.query.filter_by(org_id=doc.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=doc.org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/edit.html', doc=doc, folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts, current_page='doc', current_id=doc.id)

@bp.route('/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete(doc_id):
    """Delete document"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        flash('You do not have access to this document', 'error')
        return redirect(url_for('docs.index'))
    
    db_session.delete(doc)
    db_session.commit()
    
    log_activity('delete', 'document', doc_id)
    flash('Document deleted successfully', 'success')
    return redirect(url_for('docs.index'))

@bp.route('/<int:doc_id>/export')
@login_required
def export_pdf(doc_id):
    """Export document to PDF"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        flash('You do not have access to this document', 'error')
        return redirect(url_for('docs.index'))
    
    org = models.Organization.query.get(doc.org_id)
    pdf_data = export_document_to_pdf(doc, org)
    
    log_activity('view', 'document', doc_id, {'action': 'export_pdf'})
    
    return send_file(
        BytesIO(pdf_data),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{doc.title}.pdf'
    )

@bp.route('/<int:doc_id>/export-word')
@login_required
def export_word(doc_id):
    """Export document to Word"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        flash('You do not have access to this document', 'error')
        return redirect(url_for('docs.index'))
    
    org = models.Organization.query.get(doc.org_id)
    word_data = export_document_to_word(doc, org)
    
    log_activity('view', 'document', doc_id, {'action': 'export_word'})
    
    return send_file(
        BytesIO(word_data),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f'{doc.title}.docx'
    )

@bp.route('/upload-image', methods=['POST'])
@csrf.exempt
@login_required
def upload_image():
    """Handle image upload for markdown editor"""
    from flask import current_app
    
    if 'image' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Return URL for markdown
        url = url_for('static', filename=f'uploads/{filename}')
        return jsonify({'url': url}), 200
    
    return jsonify({'error': 'Invalid file type'}), 400

@bp.route('/folder/create', methods=['GET', 'POST'])
@login_required
def create_folder():
    """Create new folder"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('docs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('docs.index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        parent_id = request.form.get('parent_id')
        parent_id = int(parent_id) if parent_id and parent_id != 'None' else None
        
        if not name:
            flash('Folder name is required', 'error')
            return redirect(url_for('docs.create_folder'))
        
        # Validate parent folder belongs to same org
        if parent_id:
            parent = DocumentFolder.query.get(parent_id)
            if not parent or parent.org_id != org_id:
                flash('Invalid parent folder', 'error')
                return redirect(url_for('docs.create_folder'))
        
        # Check for duplicate name in same parent
        existing = DocumentFolder.query.filter_by(
            org_id=org_id,
            parent_id=parent_id,
            name=name
        ).first()
        
        if existing:
            flash('A folder with this name already exists in this location', 'error')
            return redirect(url_for('docs.create_folder'))
        
        folder = DocumentFolder(
            org_id=org_id,
            name=name,
            parent_id=parent_id,
            created_by=current_user.id
        )
        db_session.add(folder)
        db_session.commit()
        
        log_activity('create', 'document_folder', folder.id)
        flash('Folder created successfully', 'success')
        return redirect(url_for('docs.index'))
    
    # Get all folders for parent selection
    folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
    
    # Get sidebar data
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, org_id)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/create_folder.html', folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts)

@bp.route('/folder/<int:folder_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_folder(folder_id):
    """Edit folder"""
    from flask import abort
    folder = DocumentFolder.query.get(folder_id)
    if not folder:
        abort(404)
    
    if not current_user.can_access_org(folder.org_id):
        flash('You do not have access to this folder', 'error')
        return redirect(url_for('docs.index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        parent_id = request.form.get('parent_id')
        parent_id = int(parent_id) if parent_id and parent_id != 'None' else None
        
        if not name:
            flash('Folder name is required', 'error')
            return redirect(url_for('docs.edit_folder', folder_id=folder_id))
        
        # Prevent moving folder into itself or its descendants
        if parent_id:
            if parent_id == folder.id:
                flash('A folder cannot be moved into itself', 'error')
                return redirect(url_for('docs.edit_folder', folder_id=folder_id))
            
            # Check if parent_id is a descendant
            current = DocumentFolder.query.get(parent_id)
            while current:
                if current.parent_id == folder.id:
                    flash('A folder cannot be moved into its own subfolder', 'error')
                    return redirect(url_for('docs.edit_folder', folder_id=folder_id))
                current = current.parent
            
            # Validate parent folder belongs to same org
            parent = DocumentFolder.query.get(parent_id)
            if not parent or parent.org_id != folder.org_id:
                flash('Invalid parent folder', 'error')
                return redirect(url_for('docs.edit_folder', folder_id=folder_id))
        
        # Check for duplicate name in same parent (excluding current folder)
        existing = DocumentFolder.query.filter(
            DocumentFolder.org_id == folder.org_id,
            DocumentFolder.parent_id == parent_id,
            DocumentFolder.name == name,
            DocumentFolder.id != folder.id
        ).first()
        
        if existing:
            flash('A folder with this name already exists in this location', 'error')
            return redirect(url_for('docs.edit_folder', folder_id=folder_id))
        
        folder.name = name
        folder.parent_id = parent_id
        db_session.commit()
        
        log_activity('update', 'document_folder', folder_id)
        flash('Folder updated successfully', 'success')
        return redirect(url_for('docs.index'))
    
    # Get all folders for parent selection (excluding current folder and its descendants)
    all_folders = DocumentFolder.query.filter_by(org_id=folder.org_id).order_by(DocumentFolder.name).all()
    folders = [f for f in all_folders if f.id != folder.id]
    
    # Get sidebar data
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=folder.org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, folder.org_id)
    passwords = PasswordEntry.query.filter_by(org_id=folder.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=folder.org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/edit_folder.html', folder=folder, folders=folders, doc_tree=doc_tree, passwords=passwords, contacts=contacts)

@bp.route('/folder/<int:folder_id>/stats', methods=['GET'])
@login_required
def folder_stats(folder_id):
    """Get folder statistics (document count, subfolder count)"""
    from flask import abort
    folder = DocumentFolder.query.get(folder_id)
    if not folder:
        abort(404)
    
    if not current_user.can_access_org(folder.org_id):
        return jsonify({'error': 'You do not have access to this folder'}), 403
    
    def count_recursive(folder_obj):
        """Recursively count documents and subfolders"""
        doc_count = len(folder_obj.documents)
        subfolder_count = len(folder_obj.children)
        
        # Recursively count in subfolders
        for child_folder in folder_obj.children:
            child_docs, child_folders = count_recursive(child_folder)
            doc_count += child_docs
            subfolder_count += child_folders
        
        return doc_count, subfolder_count
    
    doc_count, subfolder_count = count_recursive(folder)
    
    return jsonify({
        'folder_name': folder.name,
        'document_count': doc_count,
        'subfolder_count': subfolder_count
    })

@bp.route('/folder/<int:folder_id>/delete', methods=['POST'])
@login_required
def delete_folder(folder_id):
    """Delete folder and all its contents recursively"""
    from flask import abort
    folder = DocumentFolder.query.get(folder_id)
    if not folder:
        abort(404)
    
    if not current_user.can_access_org(folder.org_id):
        flash('You do not have access to this folder', 'error')
        return redirect(url_for('docs.index'))
    
    def delete_recursive(folder_obj):
        """Recursively delete all subfolders and documents"""
        deleted_docs = 0
        deleted_folders = 0
        
        # Delete all documents in this folder
        for doc in list(folder_obj.documents):
            db_session.delete(doc)
            deleted_docs += 1
        
        # Recursively delete all subfolders
        for child_folder in list(folder_obj.children):
            child_docs, child_folders = delete_recursive(child_folder)
            deleted_docs += child_docs
            deleted_folders += child_folders
            db_session.delete(child_folder)
            deleted_folders += 1
        
        return deleted_docs, deleted_folders
    
    # Delete all contents recursively
    deleted_docs, deleted_folders = delete_recursive(folder)
    
    # Delete the folder itself
    db_session.delete(folder)
    db_session.commit()
    
    log_activity('delete', 'document_folder', folder_id, {
        'deleted_documents': deleted_docs,
        'deleted_subfolders': deleted_folders
    })
    flash(f'Folder deleted successfully. {deleted_docs} document(s) and {deleted_folders} subfolder(s) were also deleted.', 'success')
    return redirect(url_for('docs.index'))

@bp.route('/move', methods=['POST'])
@csrf.exempt
@login_required
def move_document():
    """Move a document to a different folder"""
    data = request.get_json()
    doc_id = data.get('doc_id')
    folder_id = data.get('folder_id')
    
    if not doc_id:
        return jsonify({'success': False, 'error': 'Document ID is required'}), 400
    
    # Convert folder_id to None if it's empty or None
    if folder_id == '' or folder_id is None:
        folder_id = None
    else:
        try:
            folder_id = int(folder_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid folder ID'}), 400
    
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    
    if not current_user.can_access_org(doc.org_id):
        return jsonify({'success': False, 'error': 'You do not have access to this document'}), 403
    
    # Validate folder if provided
    if folder_id:
        folder = DocumentFolder.query.get(folder_id)
        if not folder:
            return jsonify({'success': False, 'error': 'Folder not found'}), 404
        if folder.org_id != doc.org_id:
            return jsonify({'success': False, 'error': 'Folder does not belong to the same organization'}), 400
    
    # Update document folder
    doc.folder_id = folder_id
    doc.updated_by = current_user.id
    db_session.commit()
    
    log_activity('update', 'document', doc_id, {'action': 'move', 'folder_id': folder_id})
    return jsonify({'success': True, 'message': 'Document moved successfully'})

@bp.route('/software')
@login_required
def software_index():
    """List software for current org"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    software_list = Software.query.filter_by(org_id=org_id).order_by(Software.title).all()
    
    # Get sidebar data
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    from app.modules.locations.models import Location
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, org_id)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    locations = Location.query.filter_by(org_id=org_id).order_by(Location.name).limit(20).all()
    
    log_activity('view', 'software', None)
    return render_template('modules/docs/software_list.html', software_list=software_list, doc_tree=doc_tree, passwords=passwords, contacts=contacts, locations=locations)

@bp.route('/software/create', methods=['GET', 'POST'])
@login_required
def software_create():
    """Create/upload new software"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        note = request.form.get('note', '')
        link = request.form.get('link', '')
        
        if not title:
            flash('Title is required', 'error')
            # Get sidebar data for error case
            from app.modules.passwords.models import PasswordEntry
            from app.modules.contacts.models import Contact
            documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
            doc_tree = build_document_tree(documents, org_id)
            passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
            contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
            return render_template('modules/docs/software_create.html', doc_tree=doc_tree, passwords=passwords, contacts=contacts)
        
        if 'file' not in request.files:
            flash('No file provided', 'error')
            return redirect(url_for('docs.software_create'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('docs.software_create'))
        
        # Check file size (2GB = 2 * 1024 * 1024 * 1024 bytes)
        from flask import current_app
        file.seek(0, SEEK_END)
        file_size = file.tell()
        file.seek(0)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        
        if file_size > max_size:
            flash('File size exceeds 2GB limit', 'error')
            return redirect(url_for('docs.software_create'))
        
        # Save file
        filename = secure_filename(file.filename)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        software_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'software')
        os.makedirs(software_folder, exist_ok=True)
        filepath = os.path.join(software_folder, filename)
        file.save(filepath)
        
        software = Software(
            org_id=org_id,
            title=title,
            note=note,
            file_path=filepath,
            file_name=file.filename,
            file_size=file_size,
            link=link if link else None,
            uploaded_by=current_user.id
        )
        db_session.add(software)
        db_session.commit()
        
        log_activity('create', 'software', software.id)
        flash('Software uploaded successfully', 'success')
        return redirect(url_for('docs.software_index'))
    
    # Get sidebar data for GET request
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, org_id)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/software_create.html', doc_tree=doc_tree, passwords=passwords, contacts=contacts)

@bp.route('/software/<int:software_id>/edit', methods=['GET', 'POST'])
@login_required
def software_edit(software_id):
    """Edit software metadata"""
    from flask import abort
    software = Software.query.get(software_id)
    if not software:
        abort(404)
    
    if not current_user.can_access_org(software.org_id):
        flash('You do not have access to this software', 'error')
        return redirect(url_for('docs.software_index'))
    
    if request.method == 'POST':
        software.title = request.form.get('title')
        software.note = request.form.get('note', '')
        software.link = request.form.get('link', '') or None
        
        # Handle file replacement if new file is uploaded
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                # Check file size (2GB)
                from flask import current_app
                file.seek(0, SEEK_END)
                file_size = file.tell()
                file.seek(0)
                max_size = 2 * 1024 * 1024 * 1024  # 2GB
                
                if file_size > max_size:
                    flash('File size exceeds 2GB limit', 'error')
                    return redirect(url_for('docs.software_edit', software_id=software_id))
                
                # Delete old file
                if os.path.exists(software.file_path):
                    try:
                        os.remove(software.file_path)
                    except Exception as e:
                        print(f"Error deleting old file: {e}")
                
                # Save new file
                filename = secure_filename(file.filename)
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                
                software_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'software')
                os.makedirs(software_folder, exist_ok=True)
                filepath = os.path.join(software_folder, filename)
                file.save(filepath)
                
                software.file_path = filepath
                software.file_name = file.filename
                software.file_size = file_size
                software.uploaded_by = current_user.id
                software.last_uploaded = datetime.utcnow()
        
        db_session.commit()
        
        log_activity('update', 'software', software_id)
        flash('Software updated successfully', 'success')
        return redirect(url_for('docs.software_index'))
    
    # Get sidebar data
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=software.org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, software.org_id)
    passwords = PasswordEntry.query.filter_by(org_id=software.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=software.org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/software_edit.html', software=software, doc_tree=doc_tree, passwords=passwords, contacts=contacts)

@bp.route('/software/<int:software_id>/delete', methods=['POST'])
@login_required
def software_delete(software_id):
    """Delete software"""
    from flask import abort
    software = Software.query.get(software_id)
    if not software:
        abort(404)
    
    if not current_user.can_access_org(software.org_id):
        flash('You do not have access to this software', 'error')
        return redirect(url_for('docs.software_index'))
    
    # Delete file
    if os.path.exists(software.file_path):
        try:
            os.remove(software.file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    db_session.delete(software)
    db_session.commit()
    
    log_activity('delete', 'software', software_id)
    flash('Software deleted successfully', 'success')
    return redirect(url_for('docs.software_index'))

@bp.route('/software/<int:software_id>/download')
@login_required
def software_download(software_id):
    """Download software and increment download count"""
    from flask import abort
    software = Software.query.get(software_id)
    if not software:
        abort(404)
    
    if not current_user.can_access_org(software.org_id):
        flash('You do not have access to this software', 'error')
        return redirect(url_for('docs.software_index'))
    
    if not os.path.exists(software.file_path):
        flash('File not found', 'error')
        return redirect(url_for('docs.software_index'))
    
    # Increment download count
    software.download_count += 1
    db_session.commit()
    
    log_activity('view', 'software', software_id, {'action': 'download'})
    
    return send_file(
        software.file_path,
        as_attachment=True,
        download_name=software.file_name
    )

@bp.route('/<int:doc_id>/email', methods=['POST'])
@login_required
def email_document(doc_id):
    """Email document as PDF"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        return jsonify({'success': False, 'message': 'You do not have access to this document'}), 403
    
    # Check if SMTP is configured
    smtp_settings = get_smtp_settings()
    if not smtp_settings:
        return jsonify({'success': False, 'message': 'SMTP is not configured. Please configure SMTP settings in Settings.'}), 400
    
    # Get recipient email
    recipient_email = request.form.get('recipient_email', '').strip()
    if not recipient_email:
        return jsonify({'success': False, 'message': 'Recipient email address is required'}), 400
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, recipient_email):
        return jsonify({'success': False, 'message': 'Invalid email address format'}), 400
    
    # Check email domain restriction if enabled
    email_restriction_enabled = False
    email_restriction_domain = ''
    restriction_setting = models.Setting.query.filter_by(key='email_domain_restriction_enabled').first()
    if restriction_setting and restriction_setting.value == 'true':
        email_restriction_enabled = True
        domain_setting = models.Setting.query.filter_by(key='email_domain_restriction').first()
        if domain_setting and domain_setting.value:
            email_restriction_domain = domain_setting.value.strip().lower()
    
    if email_restriction_enabled and email_restriction_domain:
        recipient_domain = recipient_email.split('@')[1].lower() if '@' in recipient_email else ''
        if recipient_domain != email_restriction_domain:
            return jsonify({'success': False, 'message': f'Only emails from @{email_restriction_domain} are allowed'}), 400
    
    try:
        # Generate PDF
        org = models.Organization.query.get(doc.org_id)
        pdf_data = export_document_to_pdf(doc, org)
        
        # Get brand name for email
        brand_name = 'InfoGarden'
        brand_setting = models.Setting.query.filter_by(key='brand_name').first()
        if brand_setting and brand_setting.value:
            brand_name = brand_setting.value
        
        # Prepare email
        subject = f"{doc.title} - {brand_name}"
        body = f"""Hello,

Please find attached the document "{doc.title}" from {brand_name}.

Document Details:
- Title: {doc.title}
- Created: {doc.created_at.strftime('%Y-%m-%d %H:%M:%S') if doc.created_at else 'N/A'}
- Last Updated: {doc.updated_at.strftime('%Y-%m-%d %H:%M:%S') if doc.updated_at else 'N/A'}

This email was sent by {current_user.username}.

Best regards,
{brand_name}"""
        
        body_html = f"""<html>
<body>
    <h2>{doc.title}</h2>
    <p>Please find attached the document from {brand_name}.</p>
    <p><strong>Document Details:</strong></p>
    <ul>
        <li><strong>Title:</strong> {doc.title}</li>
        <li><strong>Created:</strong> {doc.created_at.strftime('%Y-%m-%d %H:%M:%S') if doc.created_at else 'N/A'}</li>
        <li><strong>Last Updated:</strong> {doc.updated_at.strftime('%Y-%m-%d %H:%M:%S') if doc.updated_at else 'N/A'}</li>
    </ul>
    <p>This email was sent by {current_user.username}.</p>
    <p>Best regards,<br>{brand_name}</p>
</body>
</html>"""
        
        # Prepare attachment
        pdf_filename = f"{doc.title}.pdf"
        attachments = [(pdf_filename, pdf_data, 'application/pdf')]
        
        # Send email
        success, message = send_email(
            recipient_email,
            subject,
            body,
            body_html,
            smtp_settings,
            attachments
        )
        
        if success:
            # Log activity
            log_activity('view', 'document', doc_id, {
                'action': 'email_document',
                'recipient_email': recipient_email
            })
            return jsonify({'success': True, 'message': f'Document sent successfully to {recipient_email}'}), 200
        else:
            return jsonify({'success': False, 'message': f'Failed to send email: {message}'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error sending email: {str(e)}'}), 500

@bp.route('/<int:doc_id>')
@login_required
def view(doc_id):
    """View document"""
    from flask import abort
    doc = Document.query.get(doc_id)
    if not doc:
        abort(404)
    
    if not current_user.can_access_org(doc.org_id):
        flash('You do not have access to this document', 'error')
        return redirect(url_for('docs.index'))
    
    # Get all documents, passwords, and contacts for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=doc.org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, doc.org_id)
    passwords = PasswordEntry.query.filter_by(org_id=doc.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=doc.org_id).order_by(Contact.name).all()
    
    log_activity('view', 'document', doc_id)
    
    # Track recent visit
    from app.core.recent_visits import add_recent_visit
    add_recent_visit('document', doc_id, doc.title, url_for('docs.view', doc_id=doc_id))
    
    return render_template('modules/docs/view.html', doc=doc, doc_tree=doc_tree, passwords=passwords, contacts=contacts, current_page='doc', current_id=doc.id)

@bp.route('/folder/<int:folder_id>/upload', methods=['POST'])
@login_required
def upload_file(folder_id):
    """Upload file to a document folder"""
    from flask import current_app, abort
    
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    # Get the folder
    folder = DocumentFolder.query.filter_by(id=folder_id, org_id=org_id).first()
    if not folder:
        abort(404)
    
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('docs.folder_view', folder_id=folder_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('docs.folder_view', folder_id=folder_id))
    
    if not allowed_document_file(file.filename):
        flash('File type not allowed. Allowed types: PDF, RTF, DOC, DOCX, JPG, JPEG, PNG, WEBP', 'error')
        return redirect(url_for('docs.folder_view', folder_id=folder_id))
    
    # Check file size (2GB limit)
    file.seek(0, SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    if file_size > max_size:
        flash('File size exceeds 2GB limit', 'error')
        return redirect(url_for('docs.folder_view', folder_id=folder_id))
    
    # Save file
    original_filename = file.filename
    filename = secure_filename(original_filename)
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    filename = timestamp + filename
    
    documents_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    os.makedirs(documents_folder, exist_ok=True)
    filepath = os.path.join(documents_folder, filename)
    file.save(filepath)
    
    # Get MIME type
    mime_type = get_mime_type(original_filename)
    
    # Create DocumentFile record
    doc_file = DocumentFile(
        org_id=org_id,
        folder_id=folder_id,
        name=original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename,
        original_filename=original_filename,
        file_path=filepath,
        file_size=file_size,
        mime_type=mime_type,
        uploaded_by=current_user.id
    )
    db_session.add(doc_file)
    db_session.commit()
    
    log_activity('create', 'document_file', doc_file.id)
    flash('File uploaded successfully', 'success')
    return redirect(url_for('docs.folder_view', folder_id=folder_id))

@bp.route('/file/<int:file_id>/preview')
@login_required
def preview_file(file_id):
    """Preview a document file"""
    from flask import current_app, abort, Response
    
    doc_file = DocumentFile.query.get(file_id)
    if not doc_file:
        abort(404)
    
    if not current_user.can_access_org(doc_file.org_id):
        flash('You do not have access to this file', 'error')
        return redirect(url_for('docs.index'))
    
    if not os.path.exists(doc_file.file_path):
        flash('File not found', 'error')
        return redirect(url_for('docs.folder_view', folder_id=doc_file.folder_id))
    
    # Increment download count
    doc_file.download_count += 1
    db_session.commit()
    
    log_activity('view', 'document_file', file_id)
    
    # Return file for preview
    return send_file(
        doc_file.file_path,
        mimetype=doc_file.mime_type,
        as_attachment=False,
        download_name=doc_file.original_filename
    )

@bp.route('/file/<int:file_id>/download')
@login_required
def download_file(file_id):
    """Download a document file"""
    from flask import current_app, abort
    
    doc_file = DocumentFile.query.get(file_id)
    if not doc_file:
        abort(404)
    
    if not current_user.can_access_org(doc_file.org_id):
        flash('You do not have access to this file', 'error')
        return redirect(url_for('docs.index'))
    
    if not os.path.exists(doc_file.file_path):
        flash('File not found', 'error')
        return redirect(url_for('docs.folder_view', folder_id=doc_file.folder_id))
    
    # Increment download count
    doc_file.download_count += 1
    db_session.commit()
    
    log_activity('view', 'document_file', file_id, {'action': 'download'})
    
    return send_file(
        doc_file.file_path,
        mimetype=doc_file.mime_type,
        as_attachment=True,
        download_name=doc_file.original_filename
    )

@bp.route('/file/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    """Delete a document file"""
    from flask import abort
    
    doc_file = DocumentFile.query.get(file_id)
    if not doc_file:
        abort(404)
    
    if not current_user.can_access_org(doc_file.org_id):
        flash('You do not have access to this file', 'error')
        return redirect(url_for('docs.index'))
    
    folder_id = doc_file.folder_id
    
    # Delete physical file
    if os.path.exists(doc_file.file_path):
        try:
            os.remove(doc_file.file_path)
        except OSError:
            pass  # Ignore errors deleting file
    
    db_session.delete(doc_file)
    db_session.commit()
    
    log_activity('delete', 'document_file', file_id)
    flash('File deleted successfully', 'success')
    return redirect(url_for('docs.folder_view', folder_id=folder_id))

