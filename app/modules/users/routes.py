from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user, login_user
from datetime import datetime
from app.modules.users import bp
from app.core import models
from app.core.auth import require_global_admin, require_org_admin
from app.core.activity_logger import log_activity
from app import db_session

@bp.route('/')
@login_required
@require_global_admin
def index():
    """List all users"""
    users = models.User.query.all()
    log_activity('view', 'user', None)
    return render_template('modules/users/list.html', users=users)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_global_admin
def create():
    """Create new user"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'it_basic')
        org_id = request.form.get('org_id')
        
        if not username or not email or not password:
            flash('Username, email, and password are required', 'error')
            orgs = models.Organization.query.all()
            return render_template('modules/users/create.html', orgs=orgs, roles=['global_admin', 'account_manager', 'it_admin', 'it_basic'])
        
        # Check if username or email already exists
        if models.User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            orgs = models.Organization.query.all()
            return render_template('modules/users/create.html', orgs=orgs, roles=['global_admin', 'account_manager', 'it_admin', 'it_basic'])
        
        if models.User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            orgs = models.Organization.query.all()
            return render_template('modules/users/create.html', orgs=orgs, roles=['global_admin', 'account_manager', 'it_admin', 'it_basic'])
        
        user = models.User(
            username=username,
            email=email,
            role=role,
            org_id=int(org_id) if org_id else None
        )
        user.set_password(password)
        db_session.add(user)
        db_session.commit()
        
        log_activity('create', 'user', user.id)
        flash('User created successfully', 'success')
        return redirect(url_for('users.index'))
    
    orgs = models.Organization.query.all()
    return render_template('modules/users/create.html', orgs=orgs, roles=['global_admin', 'account_manager', 'it_admin', 'it_basic'])

@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@require_global_admin
def edit(user_id):
    """Edit user"""
    from flask import abort
    user = models.User.query.get(user_id)
    if not user:
        abort(404)
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        org_id = request.form.get('org_id')
        user.org_id = int(org_id) if org_id else None
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
        
        db_session.commit()
        
        log_activity('update', 'user', user_id)
        flash('User updated successfully', 'success')
        return redirect(url_for('users.index'))
    
    orgs = models.Organization.query.all()
    return render_template('modules/users/edit.html', user=user, orgs=orgs, roles=['global_admin', 'account_manager', 'it_admin', 'it_basic'])

@bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@require_global_admin
def delete(user_id):
    """Delete user"""
    from flask import abort
    if user_id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('users.index'))
    
    user = models.User.query.get(user_id)
    if not user:
        abort(404)
    db_session.delete(user)
    db_session.commit()
    
    log_activity('delete', 'user', user_id)
    flash('User deleted successfully', 'success')
    return redirect(url_for('users.index'))

@bp.route('/<int:user_id>/activity')
@login_required
@require_global_admin
def activity(user_id):
    """View user activity logs"""
    from flask import abort
    user = models.User.query.get(user_id)
    if not user:
        abort(404)
    
    # Get last 90 days of activity
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    logs = models.ActivityLog.query.filter(
        models.ActivityLog.user_id == user_id,
        models.ActivityLog.timestamp >= cutoff_date
    ).order_by(models.ActivityLog.timestamp.desc()).all()
    
    log_activity('view', 'user', user_id, {'action': 'view_activity'})
    return render_template('modules/users/activity.html', user=user, logs=logs)

