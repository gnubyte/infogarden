from flask import render_template, request, redirect, url_for, flash, session, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.modules.orgs import bp
from app.core import models
from app.core.auth import require_global_admin, require_org_access
from app.core.activity_logger import log_activity
from app import db_session
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from io import BytesIO
import threading
from app.modules.orgs.export_utils import generate_org_export

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/')
@login_required
def index():
    """List organizations"""
    if current_user.is_global_admin():
        orgs = models.Organization.query.all()
    else:
        if current_user.org_id:
            orgs = [models.Organization.query.get(current_user.org_id)]
        else:
            orgs = []
    
    log_activity('view', 'org', None)
    return render_template('modules/orgs/list.html', orgs=orgs)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_global_admin
def create():
    """Create new organization"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        status = request.form.get('status', 'active')
        
        if not name:
            flash('Organization name is required', 'error')
            return render_template('modules/orgs/create.html')
        
        org = models.Organization(name=name, description=description, status=status)
        
        # Handle custom links
        custom_link_labels = request.form.getlist('custom_link_label[]')
        custom_link_urls = request.form.getlist('custom_link_url[]')
        custom_links = []
        for label, url in zip(custom_link_labels, custom_link_urls):
            label = label.strip()
            url = url.strip()
            if label and url:
                # Ensure URL has protocol
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                custom_links.append({'label': label, 'url': url})
        if custom_links:
            org.custom_links = custom_links
        
        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = secure_filename(file.filename)
                filename = f'org_{timestamp}{filename}'
                
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                
                # Store relative path for URL generation
                org.logo_path = url_for('static', filename=f'uploads/{filename}')
        
        db_session.add(org)
        db_session.commit()
        
        log_activity('create', 'org', org.id)
        flash('Organization created successfully', 'success')
        return redirect(url_for('orgs.index'))
    
    return render_template('modules/orgs/create.html')

@bp.route('/<int:org_id>/edit', methods=['GET', 'POST'])
@login_required
@require_global_admin
def edit(org_id):
    """Edit organization"""
    from flask import abort
    from app.modules.contacts.models import Contact
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    if request.method == 'POST':
        org.name = request.form.get('name')
        org.description = request.form.get('description', '')
        org.status = request.form.get('status', 'active')
        
        # Handle custom links
        custom_link_labels = request.form.getlist('custom_link_label[]')
        custom_link_urls = request.form.getlist('custom_link_url[]')
        custom_links = []
        for label, url in zip(custom_link_labels, custom_link_urls):
            label = label.strip()
            url = url.strip()
            if label and url:
                # Ensure URL has protocol
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                custom_links.append({'label': label, 'url': url})
        org.custom_links = custom_links if custom_links else None
        
        # Handle pinned contacts
        pinned_contact_ids = request.form.getlist('pinned_contact_id[]')
        pinned_contact_notes = request.form.getlist('pinned_contact_note[]')
        pinned_contacts = []
        for contact_id, note in zip(pinned_contact_ids, pinned_contact_notes):
            try:
                contact_id = int(contact_id)
                # Verify contact exists and belongs to this org
                contact = Contact.query.filter_by(id=contact_id, org_id=org_id).first()
                if contact:
                    pinned_contacts.append({
                        'contact_id': contact_id,
                        'note': note.strip() if note else ''
                    })
            except (ValueError, TypeError):
                continue
        org.pinned_contacts = pinned_contacts if pinned_contacts else None
        
        # Handle must_knows (rich text)
        org.must_knows = request.form.get('must_knows', '').strip() or None
        
        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Delete old logo if it exists
                if org.logo_path:
                    # Extract filename from URL path (e.g., /static/uploads/filename.jpg -> uploads/filename.jpg)
                    if '/static/' in org.logo_path:
                        relative_path = org.logo_path.split('/static/')[-1]
                    else:
                        relative_path = org.logo_path.lstrip('/')
                    old_filepath = os.path.join(current_app.static_folder, relative_path)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except OSError:
                            pass  # Ignore errors deleting old file
                
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = secure_filename(file.filename)
                filename = f'org_{org_id}_{timestamp}{filename}'
                
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                
                # Store relative path for URL generation
                org.logo_path = url_for('static', filename=f'uploads/{filename}')
        
        db_session.commit()
        
        log_activity('update', 'org', org_id)
        flash('Organization updated successfully', 'success')
        return redirect(url_for('orgs.index'))
    
    # Load pinned contacts with full contact details for display
    pinned_contacts_data = []
    if org.pinned_contacts:
        for pinned in org.pinned_contacts:
            contact_id = pinned.get('contact_id')
            if contact_id:
                contact = Contact.query.get(contact_id)
                if contact and contact.org_id == org_id:
                    pinned_contacts_data.append({
                        'contact_id': contact_id,
                        'name': contact.name,
                        'email': contact.email or '',
                        'phone': contact.phone or '',
                        'note': pinned.get('note', '')
                    })
    
    return render_template('modules/orgs/edit.html', org=org, pinned_contacts=pinned_contacts_data)

@bp.route('/<int:org_id>/delete', methods=['POST'])
@login_required
@require_global_admin
def delete(org_id):
    """Delete organization"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    db_session.delete(org)
    db_session.commit()
    
    log_activity('delete', 'org', org_id)
    flash('Organization deleted successfully', 'success')
    return redirect(url_for('orgs.index'))

@bp.route('/switch/<int:org_id>', methods=['POST'])
@login_required
def switch(org_id):
    """Switch current organization context"""
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    session['current_org_id'] = org_id
    log_activity('view', 'org', org_id, {'action': 'switch_context'})
    flash('Organization context switched', 'success')
    return redirect(request.referrer or url_for('orgs.index'))

@bp.route('/switch', methods=['POST'])
@login_required
def switch_post():
    """Switch current organization context via POST with org_id in form"""
    org_id = request.form.get('org_id')
    if not org_id:
        return jsonify({'error': 'Organization ID required'}), 400
    
    try:
        org_id = int(org_id)
    except ValueError:
        return jsonify({'error': 'Invalid organization ID'}), 400
    
    if not current_user.can_access_org(org_id):
        return jsonify({'error': 'You do not have access to this organization'}), 403
    
    session['current_org_id'] = org_id
    org = models.Organization.query.get(org_id)
    log_activity('view', 'org', org_id, {'action': 'switch_context'})
    
    return jsonify({'success': True, 'org_name': org.name if org else ''})

@bp.route('/<int:org_id>')
@login_required
def view(org_id):
    """View organization details"""
    from flask import abort
    from app.modules.contacts.models import Contact
    from app.modules.docs.models import Document
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    if not current_user.can_access_org(org_id):
        flash('You do not have access to this organization', 'error')
        return redirect(url_for('orgs.index'))
    
    # Switch organization context when viewing details
    session['current_org_id'] = org_id
    
    # Load all contacts for this org to display pinned contact details
    contacts = Contact.query.filter_by(org_id=org_id).all()
    # Create a dict for easy lookup
    contacts_dict = {contact.id: contact for contact in contacts}
    
    # Count contacts and documents
    contact_count = Contact.query.filter_by(org_id=org_id).count()
    document_count = Document.query.filter_by(org_id=org_id).count()
    
    # Get locations for this org
    from app.modules.locations.models import Location
    locations = Location.query.filter_by(org_id=org_id).order_by(Location.name).all()
    
    # Get export job status if user is global admin
    export_job = None
    if current_user.is_global_admin():
        try:
            export_job = models.ExportJob.query.filter_by(org_id=org_id).order_by(
                models.ExportJob.created_at.desc()
            ).first()
        except Exception as e:
            # ExportJob table might not exist yet, or other error
            # Log error but don't fail the page
            current_app.logger.error(f"Error querying export job: {str(e)}")
            export_job = None
    
    log_activity('view', 'org', org_id)
    
    # Track recent visit
    from app.core.recent_visits import add_recent_visit
    add_recent_visit('org', org_id, org.name, url_for('orgs.view', org_id=org_id))
    
    return render_template('modules/orgs/view.html', org=org, contacts=contacts_dict, export_job=export_job, contact_count=contact_count, document_count=document_count, locations=locations)

@bp.route('/search')
@login_required
def search():
    """Search organizations (for dropdown)"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 3:
        return jsonify({'results': []})
    
    if current_user.is_global_admin():
        orgs = models.Organization.query.filter(
            models.Organization.name.ilike(f'%{query}%')
        ).limit(10).all()
    else:
        if current_user.org_id:
            org = models.Organization.query.get(current_user.org_id)
            if org and query.lower() in org.name.lower():
                orgs = [org]
            else:
                orgs = []
        else:
            orgs = []
    
    results = [{'id': org.id, 'name': org.name} for org in orgs]
    return jsonify({'results': results})

@bp.route('/<int:org_id>/export/start', methods=['POST'])
@login_required
@require_global_admin
def start_export(org_id):
    """Start an export job for an organization"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    # Check if there's an existing export job that's still active
    existing_job = models.ExportJob.query.filter_by(
        org_id=org_id
    ).filter(
        models.ExportJob.status.in_(['pending', 'processing'])
    ).first()
    
    if existing_job:
        return jsonify({'error': 'An export is already in progress'}), 400
    
    # Create new export job
    export_job = models.ExportJob(
        org_id=org_id,
        status='pending',
        progress=0,
        created_by=current_user.id
    )
    db_session.add(export_job)
    db_session.commit()
    
    # Get the ID before starting the thread to avoid session issues
    export_job_id = export_job.id
    export_job_status = export_job.status
    export_job_progress = export_job.progress
    
    # Log activity before starting thread
    log_activity('create', 'export_job', export_job_id, {'org_id': org_id})
    
    # Start export in background thread
    app = current_app._get_current_object()
    def run_export():
        with app.app_context():
            from app import db_session as thread_db_session
            generate_org_export(org_id, export_job_id, thread_db_session)
    
    thread = threading.Thread(target=run_export)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'export_job_id': export_job_id,
        'status': export_job_status,
        'progress': export_job_progress
    })

@bp.route('/<int:org_id>/export/cancel', methods=['POST'])
@login_required
@require_global_admin
def cancel_export(org_id):
    """Cancel an in-progress export job"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    # Get the most recent active export job
    export_job = models.ExportJob.query.filter_by(org_id=org_id).filter(
        models.ExportJob.status.in_(['pending', 'processing'])
    ).order_by(models.ExportJob.created_at.desc()).first()
    
    if not export_job:
        return jsonify({'error': 'No active export job found'}), 404
    
    # Mark as cancelled
    export_job.status = 'cancelled'
    export_job.error_message = 'Export cancelled by user'
    db_session.commit()
    
    log_activity('update', 'export_job', export_job.id, {'org_id': org_id, 'action': 'cancel'})
    
    return jsonify({
        'success': True,
        'message': 'Export cancelled successfully'
    })

@bp.route('/<int:org_id>/export/status')
@login_required
@require_global_admin
def export_status(org_id):
    """Get the status of the current export job"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    # Get the most recent export job
    export_job = models.ExportJob.query.filter_by(org_id=org_id).order_by(
        models.ExportJob.created_at.desc()
    ).first()
    
    if not export_job:
        return jsonify({
            'exists': False
        })
    
    return jsonify({
        'exists': True,
        'id': export_job.id,
        'status': export_job.status,
        'progress': export_job.progress,
        'created_at': export_job.created_at.isoformat() if export_job.created_at else None,
        'updated_at': export_job.updated_at.isoformat() if export_job.updated_at else None,
        'completed_at': export_job.completed_at.isoformat() if export_job.completed_at else None,
        'error_message': export_job.error_message,
        'has_file': export_job.file_path is not None and os.path.exists(export_job.file_path) if export_job.file_path else False
    })

@bp.route('/<int:org_id>/export/download')
@login_required
@require_global_admin
def download_export(org_id):
    """Download the completed export"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    # Get the most recent completed export job
    export_job = models.ExportJob.query.filter_by(
        org_id=org_id,
        status='completed'
    ).order_by(models.ExportJob.completed_at.desc()).first()
    
    if not export_job or not export_job.file_path:
        flash('No export file available', 'error')
        return redirect(url_for('orgs.view', org_id=org_id))
    
    if not os.path.exists(export_job.file_path):
        flash('Export file not found', 'error')
        return redirect(url_for('orgs.view', org_id=org_id))
    
    log_activity('view', 'export_job', export_job.id, {'action': 'download'})
    
    return send_file(
        export_job.file_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{org.name}_export_{export_job.id}.zip'
    )

@bp.route('/<int:org_id>/export/regenerate', methods=['POST'])
@login_required
@require_global_admin
def regenerate_export(org_id):
    """Delete existing export and create a new one"""
    from flask import abort
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    # Delete existing export jobs and files
    existing_jobs = models.ExportJob.query.filter_by(org_id=org_id).all()
    for job in existing_jobs:
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
            except:
                pass
        db_session.delete(job)
    db_session.commit()
    
    # Start new export
    export_job = models.ExportJob(
        org_id=org_id,
        status='pending',
        progress=0,
        created_by=current_user.id
    )
    db_session.add(export_job)
    db_session.commit()
    
    # Get the ID before starting the thread to avoid session issues
    export_job_id = export_job.id
    export_job_status = export_job.status
    export_job_progress = export_job.progress
    
    # Log activity before starting thread
    log_activity('create', 'export_job', export_job_id, {'org_id': org_id, 'action': 'regenerate'})
    
    # Start export in background thread
    app = current_app._get_current_object()
    def run_export():
        with app.app_context():
            from app import db_session as thread_db_session
            generate_org_export(org_id, export_job_id, thread_db_session)
    
    thread = threading.Thread(target=run_export)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'export_job_id': export_job_id,
        'status': export_job_status,
        'progress': export_job_progress
    })

