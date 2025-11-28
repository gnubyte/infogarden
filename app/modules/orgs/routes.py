from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from app.modules.orgs import bp
from app.core import models
from app.core.auth import require_global_admin, require_org_access
from app.core.activity_logger import log_activity
from app import db_session

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
        
        if not name:
            flash('Organization name is required', 'error')
            return render_template('modules/orgs/create.html')
        
        org = models.Organization(name=name, description=description)
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
    org = models.Organization.query.get(org_id)
    if not org:
        abort(404)
    
    if request.method == 'POST':
        org.name = request.form.get('name')
        org.description = request.form.get('description', '')
        db_session.commit()
        
        log_activity('update', 'org', org_id)
        flash('Organization updated successfully', 'success')
        return redirect(url_for('orgs.index'))
    
    return render_template('modules/orgs/edit.html', org=org)

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

