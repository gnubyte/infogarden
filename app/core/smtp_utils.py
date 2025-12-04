"""
SMTP utility functions for sending emails
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from typing import Optional, Dict, Tuple
from app.core import models
from app import db_session


def get_smtp_settings() -> Optional[Dict[str, str]]:
    """
    Retrieve SMTP settings from the database
    
    Returns:
        Dictionary with SMTP settings or None if not configured
    """
    settings_keys = [
        'smtp_server',
        'smtp_port',
        'smtp_use_tls',
        'smtp_username',
        'smtp_password',
        'smtp_from_email',
        'smtp_from_name'
    ]
    
    settings = {}
    for key in settings_keys:
        setting = models.Setting.query.filter_by(key=key).first()
        if setting and setting.value:
            settings[key] = setting.value
        else:
            return None  # If any required setting is missing, return None
    
    return settings


def test_smtp_connection(settings: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
    """
    Test SMTP connection with provided settings or from database
    
    Args:
        settings: Optional dictionary of SMTP settings. If None, retrieves from database.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if settings is None:
        settings = get_smtp_settings()
        if settings is None:
            return False, "SMTP settings not configured"
    
    try:
        # Parse port
        port = int(settings.get('smtp_port', '587'))
        use_tls = settings.get('smtp_use_tls', 'true').lower() == 'true'
        
        # Create SMTP connection
        server = smtplib.SMTP(settings['smtp_server'], port, timeout=10)
        
        # Enable debug output (optional, can be removed in production)
        # server.set_debuglevel(1)
        
        # Start TLS if required
        if use_tls:
            server.starttls()
        
        # Authenticate
        username = settings.get('smtp_username', '')
        password = settings.get('smtp_password', '')
        
        if username and password:
            server.login(username, password)
        
        server.quit()
        return True, "SMTP connection successful"
    
    except smtplib.SMTPAuthenticationError as e:
        return False, f"SMTP authentication failed: {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"SMTP connection failed: {str(e)}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_email(
    to_email: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    settings: Optional[Dict[str, str]] = None,
    attachments: Optional[list] = None
) -> Tuple[bool, str]:
    """
    Send an email using SMTP settings
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text email body
        body_html: Optional HTML email body
        settings: Optional dictionary of SMTP settings. If None, retrieves from database.
        attachments: Optional list of tuples (filename, file_data, content_type) for attachments
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if settings is None:
        settings = get_smtp_settings()
        if settings is None:
            return False, "SMTP settings not configured"
    
    try:
        # Parse port
        port = int(settings.get('smtp_port', '587'))
        use_tls = settings.get('smtp_use_tls', 'true').lower() == 'true'
        
        # Create message
        msg = MIMEMultipart('mixed' if attachments else 'alternative')
        msg['Subject'] = subject
        msg['To'] = to_email
        
        # Set From field
        from_email = settings.get('smtp_from_email', '')
        from_name = settings.get('smtp_from_name', '')
        if from_name:
            msg['From'] = formataddr((from_name, from_email))
        else:
            msg['From'] = from_email
        
        # Create alternative part for text/html
        if body_html:
            alt_part = MIMEMultipart('alternative')
            alt_part.attach(MIMEText(body, 'plain'))
            alt_part.attach(MIMEText(body_html, 'html'))
            msg.attach(alt_part)
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # Add attachments if provided
        if attachments:
            for filename, file_data, content_type in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                msg.attach(part)
        
        # Create SMTP connection
        server = smtplib.SMTP(settings['smtp_server'], port, timeout=10)
        
        # Start TLS if required
        if use_tls:
            server.starttls()
        
        # Authenticate
        username = settings.get('smtp_username', '')
        password = settings.get('smtp_password', '')
        
        if username and password:
            server.login(username, password)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError as e:
        return False, f"SMTP authentication failed: {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"SMTP connection failed: {str(e)}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_test_email(test_email: str, settings: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
    """
    Send a test email to verify SMTP configuration
    
    Args:
        test_email: Email address to send test email to
        settings: Optional dictionary of SMTP settings. If None, retrieves from database.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    subject = "InfoGarden SMTP Test Email"
    body = f"""This is a test email from InfoGarden.

If you received this email, your SMTP settings are configured correctly.

Test sent at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    body_html = f"""<html>
<body>
    <h2>InfoGarden SMTP Test Email</h2>
    <p>This is a test email from InfoGarden.</p>
    <p>If you received this email, your SMTP settings are configured correctly.</p>
    <p><small>Test sent at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
</body>
</html>"""
    
    return send_email(test_email, subject, body, body_html, settings)

