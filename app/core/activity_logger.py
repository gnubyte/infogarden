from functools import wraps
from flask import request, session
from datetime import datetime, timedelta
from app import db_session
from app.core import models

def log_activity(action_type, resource_type, resource_id=None, details=None):
    """Log user activity"""
    from flask_login import current_user
    
    if not current_user.is_authenticated:
        return
    
    # Get org_id from session or resource
    org_id = session.get('current_org_id')
    if not org_id and resource_type in ['document', 'contact', 'password']:
        # Try to get org_id from resource
        if resource_type == 'document' and resource_id:
            from app.modules.docs.models import Document
            doc = Document.query.get(resource_id)
            if doc:
                org_id = doc.org_id
        elif resource_type == 'contact' and resource_id:
            from app.modules.contacts.models import Contact
            contact = Contact.query.get(resource_id)
            if contact:
                org_id = contact.org_id
        elif resource_type == 'password' and resource_id:
            from app.modules.passwords.models import PasswordEntry
            pwd = PasswordEntry.query.get(resource_id)
            if pwd:
                org_id = pwd.org_id
    
    log = models.ActivityLog(
        user_id=current_user.id,
        org_id=org_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=request.remote_addr,
        details=details or {}
    )
    
    db_session.add(log)
    db_session.commit()
    
    # Cleanup old logs (older than 90 days)
    cleanup_old_logs()

def cleanup_old_logs():
    """Remove activity logs older than 90 days"""
    cutoff_date = datetime.utcnow() - timedelta(days=90)
    models.ActivityLog.query.filter(models.ActivityLog.timestamp < cutoff_date).delete()
    db_session.commit()

def track_page_view(f):
    """Decorator to track page views"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if current_user.is_authenticated:
            log_activity('view', request.endpoint or 'unknown')
        return f(*args, **kwargs)
    return decorated_function

