"""
IP Whitelist middleware for Flask application
"""
import ipaddress
from flask import request, abort
from app.core import models


def get_client_ip():
    """
    Get the real client IP address, handling proxies and load balancers.
    Checks X-Forwarded-For, X-Real-IP headers, and falls back to remote_addr.
    """
    # Check for forwarded IPs (from proxies/load balancers)
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs, take the first one
        forwarded_ips = request.headers.get('X-Forwarded-For').split(',')
        client_ip = forwarded_ips[0].strip()
    elif request.headers.get('X-Real-IP'):
        client_ip = request.headers.get('X-Real-IP').strip()
    else:
        client_ip = request.remote_addr
    
    return client_ip


def is_ip_allowed(ip_address, whitelist):
    """
    Check if an IP address is allowed based on the whitelist.
    
    Args:
        ip_address: The IP address to check (string)
        whitelist: Comma-separated string of IP addresses or CIDR ranges
    
    Returns:
        bool: True if IP is allowed, False otherwise
    """
    if not whitelist or not whitelist.strip():
        # If whitelist is empty, allow all IPs
        return True
    
    try:
        client_ip_obj = ipaddress.ip_address(ip_address)
    except ValueError:
        # Invalid IP address format
        return False
    
    # Parse whitelist entries - support both comma-separated and newline-separated
    # First split by newlines, then by commas
    entries = []
    for line in whitelist.split('\n'):
        entries.extend([e.strip() for e in line.split(',') if e.strip()])
    whitelist_entries = entries
    
    for entry in whitelist_entries:
        try:
            # Check if entry is a CIDR range
            if '/' in entry:
                network = ipaddress.ip_network(entry, strict=False)
                if client_ip_obj in network:
                    return True
            else:
                # Single IP address
                allowed_ip = ipaddress.ip_address(entry)
                if client_ip_obj == allowed_ip:
                    return True
        except (ValueError, ipaddress.AddressValueError):
            # Invalid entry, skip it
            continue
    
    return False


def check_ip_whitelist():
    """
    Middleware function to check IP whitelist before processing requests.
    Should be registered as a before_request handler.
    
    Note: This allows access to login and settings pages so admins can configure
    the whitelist even if their IP is not yet added.
    """
    # Allow access to login, settings, and static files
    # This ensures admins can still configure the whitelist
    if (request.endpoint in ['core_auth.login', 'core_auth.settings', 'static'] or
        request.path.startswith('/static/')):
        return None
    
    try:
        # Get IP whitelist settings
        ip_whitelist_enabled = models.Setting.query.filter_by(key='ip_whitelist_enabled').first()
        ip_whitelist = models.Setting.query.filter_by(key='ip_whitelist').first()
        
        # Check if IP whitelist is enabled
        if ip_whitelist_enabled and ip_whitelist_enabled.value == 'true':
            whitelist_value = ip_whitelist.value if ip_whitelist and ip_whitelist.value else ''
            
            if whitelist_value:
                client_ip = get_client_ip()
                
                if not is_ip_allowed(client_ip, whitelist_value):
                    # IP is not in whitelist, deny access
                    abort(403, description=f'Access denied. Your IP address ({client_ip}) is not in the allowed list.')
    except Exception:
        # If there's an error accessing the database (e.g., during initialization),
        # allow the request to proceed to avoid blocking the application startup
        pass

