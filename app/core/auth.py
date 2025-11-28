from functools import wraps
from flask import abort, session, redirect, url_for
from flask_login import current_user

def require_global_admin(f):
    """Decorator to require global admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('core_auth.login'))
        if not current_user.is_global_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def require_org_admin(f):
    """Decorator to require org admin role (account_manager or it_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('core_auth.login'))
        if not (current_user.is_global_admin() or current_user.is_org_admin()):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def require_org_access(f):
    """Decorator to require access to the organization"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('core_auth.login'))
        
        # Global admin can access all orgs
        if current_user.is_global_admin():
            return f(*args, **kwargs)
        
        # Get org_id from kwargs or session
        org_id = kwargs.get('org_id') or session.get('current_org_id')
        
        if not org_id:
            abort(403)
        
        # Check if user can access this org
        if not current_user.can_access_org(org_id):
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def require_login(f):
    """Decorator to require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('core_auth.login'))
        return f(*args, **kwargs)
    return decorated_function

