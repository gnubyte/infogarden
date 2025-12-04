from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from app.core import models
from app.core.auth import require_global_admin
from app.core.activity_logger import log_activity
from app.core.backup import create_backup, restore_backup
from app.core.smtp_utils import get_smtp_settings, test_smtp_connection, send_test_email, send_email
from app import db_session
from werkzeug.utils import secure_filename
import os
import secrets

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
            # Check if SMTP is configured
            smtp_configured = get_smtp_settings() is not None
            return render_template('login.html', brand_name=brand_name, brand_logo=brand_logo, smtp_configured=smtp_configured)
        
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
    
    # Check if SMTP is configured
    smtp_configured = get_smtp_settings() is not None
    
    return render_template('login.html', brand_name=brand_name, brand_logo=brand_logo, smtp_configured=smtp_configured)

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password - send reset email"""
    # Get branding for template
    brand_name = 'InfoGarden'
    brand_logo = None
    for setting in models.Setting.query.filter(models.Setting.key.in_(['brand_name', 'brand_logo'])).all():
        if setting.key == 'brand_name' and setting.value:
            brand_name = setting.value
        elif setting.key == 'brand_logo' and setting.value:
            brand_logo = setting.value
    
    # Check if SMTP is configured
    smtp_settings = get_smtp_settings()
    if not smtp_settings:
        flash('Password reset is not available. SMTP is not configured.', 'error')
        return redirect(url_for('core_auth.login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('core_auth.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Email address is required', 'error')
            return render_template('forgot_password.html', brand_name=brand_name, brand_logo=brand_logo)
        
        # Find user by email
        user = models.User.query.filter_by(email=email).first()
        
        # Always show success message (security: don't reveal if email exists)
        if user:
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
            db_session.commit()
            
            # Create reset URL
            reset_url = url_for('core_auth.reset_password', token=reset_token, _external=True)
            
            # Send reset email
            subject = f"Password Reset Request - {brand_name}"
            body = f"""Hello,

You have requested to reset your password for your {brand_name} account.

Click the following link to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

Best regards,
{brand_name} Team"""
            
            body_html = f"""<html>
<body>
    <h2>Password Reset Request</h2>
    <p>Hello,</p>
    <p>You have requested to reset your password for your {brand_name} account.</p>
    <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a></p>
    <p>Or copy and paste this link into your browser:</p>
    <p><small>{reset_url}</small></p>
    <p>This link will expire in 1 hour.</p>
    <p>If you did not request this password reset, please ignore this email.</p>
    <p>Best regards,<br>{brand_name} Team</p>
</body>
</html>"""
            
            success, message = send_email(user.email, subject, body, body_html)
            if not success:
                flash(f'Failed to send reset email: {message}', 'error')
                # Clear the token if email failed
                user.reset_token = None
                user.reset_token_expires = None
                db_session.commit()
                return render_template('forgot_password.html', brand_name=brand_name, brand_logo=brand_logo)
        
        # Always show success (security best practice)
        flash('If an account with that email exists, a password reset link has been sent.', 'success')
        return redirect(url_for('core_auth.login'))
    
    return render_template('forgot_password.html', brand_name=brand_name, brand_logo=brand_logo)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    # Get branding for template
    brand_name = 'InfoGarden'
    brand_logo = None
    for setting in models.Setting.query.filter(models.Setting.key.in_(['brand_name', 'brand_logo'])).all():
        if setting.key == 'brand_name' and setting.value:
            brand_name = setting.value
        elif setting.key == 'brand_logo' and setting.value:
            brand_logo = setting.value
    
    if current_user.is_authenticated:
        return redirect(url_for('core_auth.dashboard'))
    
    # Find user with valid token
    user = models.User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        flash('Invalid or expired reset token', 'error')
        return redirect(url_for('core_auth.login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        
        if not password or not password_confirm:
            flash('Both password fields are required', 'error')
            return render_template('reset_password.html', token=token, brand_name=brand_name, brand_logo=brand_logo)
        
        if password != password_confirm:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token, brand_name=brand_name, brand_logo=brand_logo)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('reset_password.html', token=token, brand_name=brand_name, brand_logo=brand_logo)
        
        # Update password
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db_session.commit()
        
        flash('Password has been reset successfully. You can now log in.', 'success')
        log_activity('update', 'user', user.id, {'action': 'password_reset'})
        return redirect(url_for('core_auth.login'))
    
    return render_template('reset_password.html', token=token, brand_name=brand_name, brand_logo=brand_logo)

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
        # Only update settings that are present in the form
        settings_map = {}
        
        # Update backup settings if present
        if 'backup_enabled' in request.form:
            settings_map['backup_enabled'] = str(request.form.get('backup_enabled') == 'on').lower()
        if 'backup_day' in request.form:
            settings_map['backup_day'] = request.form.get('backup_day', 'sunday')
        if 'backup_hour' in request.form:
            try:
                settings_map['backup_hour'] = str(int(request.form.get('backup_hour', 0)))
            except ValueError:
                pass
        if 'backup_minute' in request.form:
            try:
                settings_map['backup_minute'] = str(int(request.form.get('backup_minute', 0)))
            except ValueError:
                pass
        if 'retention_days' in request.form:
            try:
                settings_map['retention_days'] = str(int(request.form.get('retention_days', 30)))
            except ValueError:
                pass
        
        # Update brand name if present
        if 'brand_name' in request.form:
            settings_map['brand_name'] = request.form.get('brand_name', '').strip()
        
        # Update email domain restriction settings if present
        if 'email_domain_restriction_enabled' in request.form:
            settings_map['email_domain_restriction_enabled'] = str(request.form.get('email_domain_restriction_enabled') == 'on').lower()
        if 'email_domain_restriction' in request.form:
            settings_map['email_domain_restriction'] = request.form.get('email_domain_restriction', '').strip()
        
        # Store in settings table
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

@bp.route('/settings/smtp', methods=['POST'])
@login_required
@require_global_admin
def smtp_settings_save():
    """Save SMTP settings"""
    # Get SMTP settings from form
    smtp_settings = {
        'smtp_server': request.form.get('smtp_server', '').strip(),
        'smtp_port': request.form.get('smtp_port', '587').strip(),
        'smtp_use_tls': 'true' if request.form.get('smtp_use_tls') == 'on' else 'false',
        'smtp_username': request.form.get('smtp_username', '').strip(),
        'smtp_password': request.form.get('smtp_password', '').strip(),
        'smtp_from_email': request.form.get('smtp_from_email', '').strip(),
        'smtp_from_name': request.form.get('smtp_from_name', '').strip()
    }
    
    # Validate required fields
    required_fields = ['smtp_server', 'smtp_port', 'smtp_from_email']
    for field in required_fields:
        if not smtp_settings.get(field):
            flash(f'{field.replace("_", " ").title()} is required', 'error')
            return redirect(url_for('core_auth.settings'))
    
    # Validate port is a number
    try:
        port = int(smtp_settings['smtp_port'])
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        flash('SMTP port must be a valid number between 1 and 65535', 'error')
        return redirect(url_for('core_auth.settings'))
    
    # Store in settings table
    for key, value in smtp_settings.items():
        setting = models.Setting.query.filter_by(key=key).first()
        if setting:
            # Don't update password if it's empty (user wants to keep existing)
            if key == 'smtp_password' and not value:
                continue
            setting.value = value
        else:
            # Don't create password setting if it's empty
            if key == 'smtp_password' and not value:
                continue
            setting = models.Setting(key=key, value=value)
            db_session.add(setting)
    
    db_session.commit()
    flash('SMTP settings saved successfully', 'success')
    log_activity('update', 'settings', None, {'action': 'smtp_settings'})
    return redirect(url_for('core_auth.settings'))

@bp.route('/settings/smtp/test', methods=['POST'])
@login_required
@require_global_admin
def smtp_test():
    """Test SMTP connection and send test email"""
    # Get test email address
    test_email = request.form.get('test_email', '').strip()
    if not test_email:
        return jsonify({'success': False, 'message': 'Test email address is required'}), 400
    
    # Get SMTP settings from form (for testing before saving)
    smtp_settings = {
        'smtp_server': request.form.get('smtp_server', '').strip(),
        'smtp_port': request.form.get('smtp_port', '587').strip(),
        'smtp_use_tls': 'true' if request.form.get('smtp_use_tls') == 'on' else 'false',
        'smtp_username': request.form.get('smtp_username', '').strip(),
        'smtp_password': request.form.get('smtp_password', '').strip(),
        'smtp_from_email': request.form.get('smtp_from_email', '').strip(),
        'smtp_from_name': request.form.get('smtp_from_name', '').strip()
    }
    
    # If password is empty, try to get from database
    if not smtp_settings['smtp_password']:
        existing_setting = models.Setting.query.filter_by(key='smtp_password').first()
        if existing_setting:
            smtp_settings['smtp_password'] = existing_setting.value
    
    # Validate required fields
    required_fields = ['smtp_server', 'smtp_port', 'smtp_from_email']
    for field in required_fields:
        if not smtp_settings.get(field):
            return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400
    
    # Validate port
    try:
        port = int(smtp_settings['smtp_port'])
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
    except ValueError:
        return jsonify({'success': False, 'message': 'SMTP port must be a valid number between 1 and 65535'}), 400
    
    # Test connection first
    success, message = test_smtp_connection(smtp_settings)
    if not success:
        return jsonify({'success': False, 'message': f'Connection test failed: {message}'}), 200
    
    # If connection test passed, try sending test email
    success, message = send_test_email(test_email, smtp_settings)
    if success:
        log_activity('update', 'settings', None, {'action': 'smtp_test', 'test_email': test_email})
        return jsonify({'success': True, 'message': f'Test email sent successfully to {test_email}'}), 200
    else:
        return jsonify({'success': False, 'message': f'Failed to send test email: {message}'}), 200

@bp.route('/settings/email-restriction', methods=['GET'])
@login_required
def get_email_restriction_settings():
    """Get email domain restriction settings"""
    settings_dict = {}
    for setting in models.Setting.query.filter(models.Setting.key.in_(['email_domain_restriction_enabled', 'email_domain_restriction'])).all():
        settings_dict[setting.key] = setting.value
    
    return jsonify({
        'enabled': settings_dict.get('email_domain_restriction_enabled', 'false') == 'true',
        'domain': settings_dict.get('email_domain_restriction', '')
    })

