from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from app.core import models
from app.core.auth import require_global_admin
from app.core.activity_logger import log_activity
from app.core.backup import create_backup, restore_backup
from app import db_session
from werkzeug.utils import secure_filename
import os

bp = Blueprint('core_auth', __name__)

@bp.route('/')
def index():
    """Root route - redirect to login or dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('core_auth.dashboard'))
    return redirect(url_for('core_auth.login'))

@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """First-time setup - create initial admin user"""
    # Check if admin user already exists
    admin_exists = models.User.query.filter_by(role='global_admin').first() is not None
    
    if admin_exists:
        flash('Setup has already been completed. Please log in.', 'info')
        return redirect(url_for('core_auth.login'))
    
    # Also check if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('core_auth.dashboard'))
    
    if request.method == 'POST':
        # CSRF token is handled by Flask-WTF automatically via the form
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('setup.html')
        
        if password != password_confirm:
            flash('Passwords do not match', 'error')
            return render_template('setup.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('setup.html')
        
        # Check if username or email already exists
        if models.User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('setup.html')
        
        if models.User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('setup.html')
        
        # Create admin user
        admin_user = models.User(
            username=username,
            email=email,
            role='global_admin',
            org_id=None  # Global admin doesn't belong to a specific org
        )
        admin_user.set_password(password)
        db_session.add(admin_user)
        db_session.commit()
        
        flash('Admin user created successfully! You can now log in.', 'success')
        log_activity('create', 'user', admin_user.id, {'action': 'initial_setup'})
        return redirect(url_for('core_auth.login'))
    
    return render_template('setup.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('core_auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            # Get branding for template
            brand_name = 'InfoGarden'
            brand_logo = None
            for setting in models.Setting.query.filter(models.Setting.key.in_(['brand_name', 'brand_logo'])).all():
                if setting.key == 'brand_name' and setting.value:
                    brand_name = setting.value
                elif setting.key == 'brand_logo' and setting.value:
                    brand_logo = setting.value
            return render_template('login.html', brand_name=brand_name, brand_logo=brand_logo)
        
        user = models.User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db_session.commit()
            
            # Set default org context
            if user.org_id:
                session['current_org_id'] = user.org_id
            
            log_activity('view', 'login', user.id)
            flash('Logged in successfully', 'success')
            return redirect(url_for('core_auth.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    # Get branding for template
    brand_name = 'InfoGarden'
    brand_logo = None
    for setting in models.Setting.query.filter(models.Setting.key.in_(['brand_name', 'brand_logo'])).all():
        if setting.key == 'brand_name' and setting.value:
            brand_name = setting.value
        elif setting.key == 'brand_logo' and setting.value:
            brand_logo = setting.value
    
    return render_template('login.html', brand_name=brand_name, brand_logo=brand_logo)

@bp.route('/logout')
@login_required
def logout():
    """User logout"""
    log_activity('view', 'logout', current_user.id)
    logout_user()
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('core_auth.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard"""
    org_id = session.get('current_org_id') or current_user.org_id
    org = None
    if org_id:
        org = models.Organization.query.get(org_id)
    
    log_activity('view', 'dashboard', None)
    return render_template('dashboard.html', org=org)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@require_global_admin
def settings():
    """Global settings"""
    if request.method == 'POST':
        # Update backup settings
        backup_enabled = request.form.get('backup_enabled') == 'on'
        backup_day = request.form.get('backup_day', 'sunday')
        backup_hour = int(request.form.get('backup_hour', 0))
        backup_minute = int(request.form.get('backup_minute', 0))
        retention_days = int(request.form.get('retention_days', 30))
        
        # Update brand name
        brand_name = request.form.get('brand_name', '').strip()
        
        # Store in settings table
        settings_map = {
            'backup_enabled': str(backup_enabled).lower(),
            'backup_day': backup_day,
            'backup_hour': str(backup_hour),
            'backup_minute': str(backup_minute),
            'retention_days': str(retention_days),
            'brand_name': brand_name
        }
        
        for key, value in settings_map.items():
            setting = models.Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = models.Setting(key=key, value=value)
                db_session.add(setting)
        
        db_session.commit()
        flash('Settings updated successfully', 'success')
        log_activity('update', 'settings', None)
        return redirect(url_for('core_auth.settings'))
    
    # Get current settings
    settings_dict = {}
    for setting in models.Setting.query.all():
        settings_dict[setting.key] = setting.value
    
    return render_template('settings.html', settings=settings_dict)

@bp.route('/settings/upload-logo', methods=['POST'])
@login_required
@require_global_admin
def upload_logo():
    """Upload branding logo"""
    if 'logo' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('core_auth.settings'))
    
    file = request.files['logo']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('core_auth.settings'))
    
    # Check if it's a JPEG
    if file and file.filename.lower().endswith(('.jpg', '.jpeg')):
        filename = secure_filename('brand_logo.jpg')
        
        # Save to static/uploads directory
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Store logo path in settings
        logo_url = url_for('static', filename=f'uploads/{filename}')
        setting = models.Setting.query.filter_by(key='brand_logo').first()
        if setting:
            setting.value = logo_url
        else:
            setting = models.Setting(key='brand_logo', value=logo_url)
            db_session.add(setting)
        
        db_session.commit()
        flash('Logo uploaded successfully', 'success')
        log_activity('update', 'settings', None, {'action': 'logo_upload'})
    else:
        flash('Invalid file type. Please upload a JPEG image.', 'error')
    
    return redirect(url_for('core_auth.settings'))

@bp.route('/backup/create', methods=['POST'])
@login_required
@require_global_admin
def backup_create():
    """Create manual backup"""
    backup_file = create_backup()
    if backup_file:
        flash('Backup created successfully', 'success')
        log_activity('create', 'backup', None)
    else:
        flash('Backup failed', 'error')
    return redirect(url_for('core_auth.settings'))

@bp.route('/backup/list')
@login_required
@require_global_admin
def backup_list():
    """List available backups"""
    from flask import current_app
    backup_folder = current_app.config['BACKUP_FOLDER']
    backups = []
    
    if os.path.exists(backup_folder):
        for filename in os.listdir(backup_folder):
            if filename.endswith('.sql.gz'):
                filepath = os.path.join(backup_folder, filename)
                backups.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'created': datetime.fromtimestamp(os.path.getmtime(filepath))
                })
    
    backups.sort(key=lambda x: x['created'], reverse=True)
    return render_template('backup_list.html', backups=backups)

@bp.route('/backup/download/<filename>')
@login_required
@require_global_admin
def backup_download(filename):
    """Download backup file"""
    from flask import current_app
    backup_folder = current_app.config['BACKUP_FOLDER']
    filepath = os.path.join(backup_folder, filename)
    
    if os.path.exists(filepath) and filename.endswith('.sql.gz'):
        log_activity('view', 'backup', None, {'action': 'download', 'file': filename})
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        flash('Backup file not found', 'error')
        return redirect(url_for('core_auth.backup_list'))

@bp.route('/backup/restore/<filename>', methods=['POST'])
@login_required
@require_global_admin
def backup_restore(filename):
    """Restore from backup"""
    from flask import current_app
    backup_folder = current_app.config['BACKUP_FOLDER']
    filepath = os.path.join(backup_folder, filename)
    
    if os.path.exists(filepath) and filename.endswith('.sql.gz'):
        if restore_backup(filepath):
            flash('Backup restored successfully', 'success')
            log_activity('update', 'backup', None, {'action': 'restore', 'file': filename})
        else:
            flash('Backup restore failed', 'error')
    else:
        flash('Backup file not found', 'error')
    
    return redirect(url_for('core_auth.backup_list'))

