from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app.modules.passwords import bp
from app.modules.passwords.models import PasswordEntry
from app.core.encryption import encrypt_data, decrypt_data
from app.core.activity_logger import log_activity
from app.core.auth import require_org_access
from app.core.sidebar_utils import build_document_tree
from app import db_session
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image
import io
import base64

@bp.route('/')
@login_required
def index():
    """List passwords for current org"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    
    # Get documents and contacts for sidebar
    from app.modules.docs.models import Document
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, org_id)
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    log_activity('view', 'password', None)
    return render_template('modules/passwords/list.html', passwords=passwords, doc_tree=doc_tree, contacts=contacts)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new password entry"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        link = request.form.get('link')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        two_fa_secret = request.form.get('two_fa_secret')
        
        if not title:
            flash('Title is required', 'error')
            return render_template('modules/passwords/create.html')
        
        encrypted_password = encrypt_data(password) if password else None
        encrypted_2fa = encrypt_data(two_fa_secret) if two_fa_secret else None
        
        entry = PasswordEntry(
            org_id=org_id,
            title=title,
            link=link,
            username=username,
            email=email,
            encrypted_password=encrypted_password,
            encrypted_2fa_secret=encrypted_2fa,
            created_by=current_user.id
        )
        db_session.add(entry)
        db_session.commit()
        
        log_activity('create', 'password', entry.id)
        flash('Password entry created successfully', 'success')
        return redirect(url_for('passwords.index'))
    
    return render_template('modules/passwords/create.html')

@bp.route('/<int:entry_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(entry_id):
    """Edit password entry"""
    from flask import abort
    entry = PasswordEntry.query.get(entry_id)
    if not entry:
        abort(404)
    
    if not current_user.can_access_org(entry.org_id):
        flash('You do not have access to this password entry', 'error')
        return redirect(url_for('passwords.index'))
    
    if request.method == 'POST':
        entry.title = request.form.get('title')
        entry.link = request.form.get('link')
        entry.username = request.form.get('username')
        entry.email = request.form.get('email')
        
        password = request.form.get('password')
        if password:
            entry.encrypted_password = encrypt_data(password)
        
        two_fa_secret = request.form.get('two_fa_secret')
        if two_fa_secret:
            entry.encrypted_2fa_secret = encrypt_data(two_fa_secret)
        
        db_session.commit()
        
        log_activity('update', 'password', entry_id)
        flash('Password entry updated successfully', 'success')
        return redirect(url_for('passwords.index'))
    
    # Track recent visit when viewing edit page
    from app.core.recent_visits import add_recent_visit
    add_recent_visit('password', entry_id, entry.title, url_for('passwords.edit', entry_id=entry_id))
    
    # Decrypt for display (but don't show in form by default for security)
    decrypted_password = decrypt_data(entry.encrypted_password) if entry.encrypted_password else None
    decrypted_2fa = decrypt_data(entry.encrypted_2fa_secret) if entry.encrypted_2fa_secret else None
    
    return render_template('modules/passwords/edit.html', entry=entry, 
                         decrypted_password=decrypted_password, decrypted_2fa=decrypted_2fa)

@bp.route('/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete(entry_id):
    """Delete password entry"""
    from flask import abort
    entry = PasswordEntry.query.get(entry_id)
    if not entry:
        abort(404)
    
    if not current_user.can_access_org(entry.org_id):
        flash('You do not have access to this password entry', 'error')
        return redirect(url_for('passwords.index'))
    
    db_session.delete(entry)
    db_session.commit()
    
    log_activity('delete', 'password', entry_id)
    flash('Password entry deleted successfully', 'success')
    return redirect(url_for('passwords.index'))

@bp.route('/<int:entry_id>/reveal', methods=['POST'])
@login_required
def reveal(entry_id):
    """Reveal encrypted password (with audit log)"""
    from flask import abort
    entry = PasswordEntry.query.get(entry_id)
    if not entry:
        abort(404)
    
    if not current_user.can_access_org(entry.org_id):
        return jsonify({'error': 'Access denied'}), 403
    
    password = decrypt_data(entry.encrypted_password) if entry.encrypted_password else None
    two_fa = decrypt_data(entry.encrypted_2fa_secret) if entry.encrypted_2fa_secret else None
    
    log_activity('view', 'password', entry_id, {'action': 'password_revealed'})
    
    return jsonify({
        'password': password,
        'two_fa_secret': two_fa
    })

@bp.route('/parse-qr', methods=['POST'])
@login_required
def parse_qr():
    """Parse QR code image to extract 2FA secret"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read image
        image = Image.open(io.BytesIO(file.read()))
        
        # Decode QR code
        decoded_objects = pyzbar_decode(image)
        
        if not decoded_objects:
            return jsonify({'error': 'No QR code found in image'}), 400
        
        # Extract secret from QR code data
        # QR codes for 2FA typically contain otpauth:// URLs
        qr_data = decoded_objects[0].data.decode('utf-8')
        
        # Try to extract secret from otpauth URL
        if 'otpauth://' in qr_data:
            # Parse otpauth://totp/...?secret=...
            if 'secret=' in qr_data:
                secret = qr_data.split('secret=')[1].split('&')[0]
                return jsonify({'secret': secret}), 200
        
        return jsonify({'error': 'Could not extract secret from QR code', 'data': qr_data}), 400
    except Exception as e:
        return jsonify({'error': f'Error parsing QR code: {str(e)}'}), 500

