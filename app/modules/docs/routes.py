from flask import render_template, request, redirect, url_for, flash, send_file, session, jsonify
from flask_login import login_required, current_user
from io import BytesIO
from app.modules.docs import bp
from app.modules.docs.models import Document
from app.core import models
from app.core.auth import require_org_access
from app.core.activity_logger import log_activity
from app.modules.docs.pdf_export import export_document_to_pdf
from app.core.sidebar_utils import build_document_tree
from app import db_session, csrf
import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    doc_tree = build_document_tree(documents)
    
    # Get passwords and contacts for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    log_activity('view', 'document', None)
    return render_template('modules/docs/list.html', documents=documents, doc_tree=doc_tree, passwords=passwords, contacts=contacts)

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
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content', '')
        
        if not title:
            flash('Title is required', 'error')
            # Get sidebar data for error case
            from app.modules.passwords.models import PasswordEntry
            from app.modules.contacts.models import Contact
            documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
            doc_tree = build_document_tree(documents)
            passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
            contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
            return render_template('modules/docs/create.html', doc_tree=doc_tree, passwords=passwords, contacts=contacts)
        
        doc = Document(
            org_id=org_id,
            title=title,
            content=content,
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
    doc_tree = build_document_tree(documents)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/create.html', doc_tree=doc_tree, passwords=passwords, contacts=contacts)

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
    doc_tree = build_document_tree(documents)
    passwords = PasswordEntry.query.filter_by(org_id=doc.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=doc.org_id).order_by(Contact.name).all()
    
    log_activity('view', 'document', doc_id)
    return render_template('modules/docs/view.html', doc=doc, doc_tree=doc_tree, passwords=passwords, contacts=contacts, current_page='doc', current_id=doc.id)

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
        doc.updated_by = current_user.id
        db_session.commit()
        
        log_activity('update', 'document', doc_id)
        flash('Document updated successfully', 'success')
        return redirect(url_for('docs.view', doc_id=doc.id))
    
    # Get all documents, passwords, and contacts for sidebar
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=doc.org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents)
    passwords = PasswordEntry.query.filter_by(org_id=doc.org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=doc.org_id).order_by(Contact.name).all()
    
    return render_template('modules/docs/edit.html', doc=doc, doc_tree=doc_tree, passwords=passwords, contacts=contacts, current_page='doc', current_id=doc.id)

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

