from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.modules.contacts import bp
from app.modules.contacts.models import Contact
from app.core.auth import require_org_access
from app.core.activity_logger import log_activity
from app.core.sidebar_utils import build_document_tree
from app import db_session

@bp.route('/')
@login_required
def index():
    """List contacts for current org"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    emergency_only = request.args.get('emergency', 'false') == 'true'
    
    query = Contact.query.filter_by(org_id=org_id)
    if emergency_only:
        query = query.filter_by(emergency_contact=True)
    
    contacts = query.order_by(Contact.name).all()
    
    # Get documents and passwords for sidebar
    from app.modules.docs.models import Document
    from app.modules.passwords.models import PasswordEntry
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    
    log_activity('view', 'contact', None)
    return render_template('modules/contacts/list.html', contacts=contacts, emergency_only=emergency_only, doc_tree=doc_tree, passwords=passwords)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new contact"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    if request.method == 'POST':
        contact = Contact(
            org_id=org_id,
            name=request.form.get('name'),
            role=request.form.get('role'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            text_number=request.form.get('text_number'),
            notes=request.form.get('notes'),
            emergency_contact=request.form.get('emergency_contact') == 'on'
        )
        db_session.add(contact)
        db_session.commit()
        
        log_activity('create', 'contact', contact.id)
        flash('Contact created successfully', 'success')
        return redirect(url_for('contacts.index'))
    
    return render_template('modules/contacts/create.html')

@bp.route('/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(contact_id):
    """Edit contact"""
    from flask import abort
    contact = Contact.query.get(contact_id)
    if not contact:
        abort(404)
    
    if not current_user.can_access_org(contact.org_id):
        flash('You do not have access to this contact', 'error')
        return redirect(url_for('contacts.index'))
    
    if request.method == 'POST':
        contact.name = request.form.get('name')
        contact.role = request.form.get('role')
        contact.email = request.form.get('email')
        contact.phone = request.form.get('phone')
        contact.text_number = request.form.get('text_number')
        contact.notes = request.form.get('notes')
        contact.emergency_contact = request.form.get('emergency_contact') == 'on'
        db_session.commit()
        
        log_activity('update', 'contact', contact_id)
        flash('Contact updated successfully', 'success')
        return redirect(url_for('contacts.index'))
    
    return render_template('modules/contacts/edit.html', contact=contact)

@bp.route('/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete(contact_id):
    """Delete contact"""
    from flask import abort
    contact = Contact.query.get(contact_id)
    if not contact:
        abort(404)
    
    if not current_user.can_access_org(contact.org_id):
        flash('You do not have access to this contact', 'error')
        return redirect(url_for('contacts.index'))
    
    db_session.delete(contact)
    db_session.commit()
    
    log_activity('delete', 'contact', contact_id)
    flash('Contact deleted successfully', 'success')
    return redirect(url_for('contacts.index'))

