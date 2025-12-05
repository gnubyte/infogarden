from flask import jsonify, request, session
from flask_login import login_required, current_user
from app.modules.search import bp
from app.modules.docs.models import Document, Software, DocumentFile
from app.modules.contacts.models import Contact
from app.modules.passwords.models import PasswordEntry
from app.core.activity_logger import log_activity

@bp.route('/')
@login_required
def search():
    """Global search endpoint"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []})
    
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        return jsonify({'results': []})
    
    if not current_user.can_access_org(org_id):
        return jsonify({'results': []})
    
    results = []
    
    # Search documents
    if current_user.can_access_org(org_id):
        docs = Document.query.filter(
            Document.org_id == org_id,
            (Document.title.contains(query) | Document.content.contains(query))
        ).limit(5).all()
        
        for doc in docs:
            results.append({
                'type': 'document',
                'id': doc.id,
                'title': doc.title,
                'url': f'/docs/{doc.id}',
                'snippet': doc.content[:100] + '...' if doc.content and len(doc.content) > 100 else (doc.content or '')
            })
    
    # Search contacts
    contacts = Contact.query.filter(
        Contact.org_id == org_id,
        (Contact.name.contains(query) | 
         Contact.email.contains(query) | 
         Contact.phone.contains(query) |
         Contact.notes.contains(query))
    ).limit(5).all()
    
    for contact in contacts:
        results.append({
            'type': 'contact',
            'id': contact.id,
            'title': contact.name,
            'url': f'/contacts/{contact.id}/edit',
            'snippet': f"{contact.role or ''} - {contact.email or contact.phone or ''}"
        })
    
    # Search passwords (title and link only, not encrypted content)
    passwords = PasswordEntry.query.filter(
        PasswordEntry.org_id == org_id,
        (PasswordEntry.title.contains(query) | 
         PasswordEntry.link.contains(query) |
         PasswordEntry.username.contains(query) |
         PasswordEntry.email.contains(query))
    ).limit(5).all()
    
    for pwd in passwords:
        results.append({
            'type': 'password',
            'id': pwd.id,
            'title': pwd.title,
            'url': f'/passwords/{pwd.id}/edit',
            'snippet': pwd.link or pwd.username or pwd.email or ''
        })
    
    # Search software (title and file name)
    software_list = Software.query.filter(
        Software.org_id == org_id,
        (Software.title.contains(query) | 
         Software.file_name.contains(query))
    ).limit(5).all()
    
    for sw in software_list:
        results.append({
            'type': 'software',
            'id': sw.id,
            'title': sw.title,
            'url': f'/docs/software/{sw.id}/edit',
            'snippet': f"File: {sw.file_name}" + (f" - {sw.note[:50]}..." if sw.note and len(sw.note) > 50 else (f" - {sw.note}" if sw.note else ''))
        })
    
    # Search document files (name and original filename)
    document_files = DocumentFile.query.filter(
        DocumentFile.org_id == org_id,
        (DocumentFile.name.contains(query) | 
         DocumentFile.original_filename.contains(query))
    ).limit(5).all()
    
    for doc_file in document_files:
        # Get folder path for context
        folder_path = doc_file.folder.get_path() if doc_file.folder else 'Unknown'
        results.append({
            'type': 'file',
            'id': doc_file.id,
            'title': doc_file.name,
            'url': f'/docs/folder/{doc_file.folder_id}',
            'snippet': f"File: {doc_file.original_filename} - Folder: {folder_path}" + (f" ({doc_file.mime_type})" if doc_file.mime_type else '')
        })
    
    log_activity('view', 'search', None, {'query': query, 'result_count': len(results)})
    
    return jsonify({'results': results})

