"""
reCAPTCHA utility functions for verifying Google reCAPTCHA v2 tokens
"""
import requests
from typing import Optional, Dict, Tuple
from app.core import models


def get_recaptcha_settings() -> Optional[Dict[str, str]]:
    """
    Retrieve reCAPTCHA settings from the database
    
    Returns:
        Dictionary with reCAPTCHA settings or None if not configured
    """
    recaptcha_enabled = models.Setting.query.filter_by(key='recaptcha_enabled').first()
    if not recaptcha_enabled or recaptcha_enabled.value != 'true':
        return None
    
    recaptcha_site_key = models.Setting.query.filter_by(key='recaptcha_site_key').first()
    recaptcha_secret_key = models.Setting.query.filter_by(key='recaptcha_secret_key').first()
    
    if not recaptcha_site_key or not recaptcha_site_key.value:
        return None
    if not recaptcha_secret_key or not recaptcha_secret_key.value:
        return None
    
    return {
        'enabled': True,
        'site_key': recaptcha_site_key.value,
        'secret_key': recaptcha_secret_key.value
    }


def verify_recaptcha(token: str, secret_key: Optional[str] = None) -> Tuple[bool, str]:
    """
    Verify a reCAPTCHA token with Google's API
    
    Args:
        token: The reCAPTCHA response token from the client
        secret_key: Optional secret key. If None, retrieves from database.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not token:
        return False, "reCAPTCHA token is missing"
    
    # Get secret key from database if not provided
    if secret_key is None:
        settings = get_recaptcha_settings()
        if not settings:
            return False, "reCAPTCHA is not configured"
        secret_key = settings['secret_key']
    
    try:
        # Verify with Google's reCAPTCHA API
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token
            },
            timeout=5
        )
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            return True, "reCAPTCHA verification successful"
        else:
            error_codes = result.get('error-codes', [])
            error_message = ', '.join(error_codes) if error_codes else 'Unknown error'
            return False, f"reCAPTCHA verification failed: {error_message}"
    
    except requests.exceptions.RequestException as e:
        return False, f"Error verifying reCAPTCHA: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
