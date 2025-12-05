from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.modules.locations import bp
from app.modules.locations.models import Location
from app.core.auth import require_org_access
from app.core.activity_logger import log_activity
from app.core.sidebar_utils import build_document_tree
from app import db_session

@bp.route('/')
@login_required
def index():
    """List locations for current org"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    locations = Location.query.filter_by(org_id=org_id).order_by(Location.name).all()
    
    # Get documents, passwords, contacts, and locations for sidebar
    from app.modules.docs.models import Document
    from app.modules.passwords.models import PasswordEntry
    from app.modules.contacts.models import Contact
    documents = Document.query.filter_by(org_id=org_id).order_by(Document.title).all()
    doc_tree = build_document_tree(documents, org_id)
    passwords = PasswordEntry.query.filter_by(org_id=org_id).order_by(PasswordEntry.title).all()
    contacts = Contact.query.filter_by(org_id=org_id).order_by(Contact.name).all()
    
    log_activity('view', 'location', None)
    return render_template('modules/locations/list.html', locations=locations, doc_tree=doc_tree, passwords=passwords, contacts=contacts)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new location"""
    org_id = session.get('current_org_id') or current_user.org_id
    if not org_id:
        flash('Please select an organization first', 'error')
        return redirect(url_for('orgs.index'))
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    if request.method == 'POST':
        location = Location(
            org_id=org_id,
            name=request.form.get('name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            zip_code=request.form.get('zip_code'),
            country=request.form.get('country'),
            notes=request.form.get('notes')
        )
        db_session.add(location)
        db_session.commit()
        
        log_activity('create', 'location', location.id)
        flash('Location created successfully', 'success')
        return redirect(url_for('locations.index'))
    
    return render_template('modules/locations/create.html')

@bp.route('/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(location_id):
    """Edit location"""
    from flask import abort
    location = Location.query.get(location_id)
    if not location:
        abort(404)
    
    if not current_user.can_access_org(location.org_id):
        flash('You do not have access to this location', 'error')
        return redirect(url_for('locations.index'))
    
    if request.method == 'POST':
        location.name = request.form.get('name')
        location.address = request.form.get('address')
        location.city = request.form.get('city')
        location.state = request.form.get('state')
        location.zip_code = request.form.get('zip_code')
        location.country = request.form.get('country')
        location.notes = request.form.get('notes')
        db_session.commit()
        
        log_activity('update', 'location', location_id)
        flash('Location updated successfully', 'success')
        return redirect(url_for('locations.index'))
    
    # Track recent visit when viewing edit page
    from app.core.recent_visits import add_recent_visit
    add_recent_visit('location', location_id, location.name, url_for('locations.edit', location_id=location_id))
    
    return render_template('modules/locations/edit.html', location=location)

@bp.route('/<int:location_id>/delete', methods=['POST'])
@login_required
def delete(location_id):
    """Delete location"""
    from flask import abort
    location = Location.query.get(location_id)
    if not location:
        abort(404)
    
    if not current_user.can_access_org(location.org_id):
        flash('You do not have access to this location', 'error')
        return redirect(url_for('locations.index'))
    
    db_session.delete(location)
    db_session.commit()
    
    log_activity('delete', 'location', location_id)
    flash('Location deleted successfully', 'success')
    return redirect(url_for('locations.index'))

