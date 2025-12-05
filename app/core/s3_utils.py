"""
S3 utility functions for handling file uploads, downloads, and deletions.
"""
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from flask import current_app
from app.core.models import Setting


def is_s3_enabled():
    """Check if S3 storage is enabled in settings."""
    setting = Setting.query.filter_by(key='s3_enabled').first()
    return setting and setting.value == 'true'


def get_s3_client():
    """Get configured S3 client."""
    if not is_s3_enabled():
        return None
    
    # Get S3 settings
    settings = {}
    for key in ['s3_access_key', 's3_secret_key', 's3_region', 's3_bucket']:
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            settings[key] = setting.value
        else:
            return None
    
    # Check if all required settings are present
    required_keys = ['s3_access_key', 's3_secret_key', 's3_region', 's3_bucket']
    if not all(settings.get(key) for key in required_keys):
        return None
    
    try:
        client = boto3.client(
            's3',
            aws_access_key_id=settings['s3_access_key'],
            aws_secret_access_key=settings['s3_secret_key'],
            region_name=settings['s3_region']
        )
        return client, settings['s3_bucket']
    except Exception as e:
        current_app.logger.error(f"Error creating S3 client: {str(e)}")
        return None


def upload_file_to_s3(file_obj, s3_key, content_type=None):
    """
    Upload a file to S3.
    
    Args:
        file_obj: File-like object to upload
        s3_key: S3 object key (path in bucket)
        content_type: Optional MIME type
    
    Returns:
        S3 URL if successful, None otherwise
    """
    result = get_s3_client()
    if not result:
        return None
    
    client, bucket = result
    
    try:
        # Reset file pointer to beginning
        file_obj.seek(0)
        
        # Upload file
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        client.upload_fileobj(
            file_obj,
            bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        
        # Generate URL
        setting = Setting.query.filter_by(key='s3_region').first()
        region = setting.value if setting else 'us-east-1'
        
        # If custom domain is configured, use it
        custom_domain_setting = Setting.query.filter_by(key='s3_custom_domain').first()
        if custom_domain_setting and custom_domain_setting.value:
            domain = custom_domain_setting.value.rstrip('/')
            url = f"{domain}/{s3_key}"
        else:
            # Use standard S3 URL
            # URL encode the key for proper handling of special characters
            from urllib.parse import quote
            encoded_key = quote(s3_key, safe='/')
            url = f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}"
        
        return url
    except ClientError as e:
        current_app.logger.error(f"Error uploading to S3: {str(e)}")
        return None
    except Exception as e:
        current_app.logger.error(f"Unexpected error uploading to S3: {str(e)}")
        return None


def delete_file_from_s3(s3_key):
    """
    Delete a file from S3.
    
    Args:
        s3_key: S3 object key (path in bucket)
    
    Returns:
        True if successful, False otherwise
    """
    result = get_s3_client()
    if not result:
        return False
    
    client, bucket = result
    
    try:
        client.delete_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError as e:
        current_app.logger.error(f"Error deleting from S3: {str(e)}")
        return False
    except Exception as e:
        current_app.logger.error(f"Unexpected error deleting from S3: {str(e)}")
        return False


def get_s3_key_from_url(url):
    """
    Extract S3 key from a URL.
    
    Args:
        url: S3 URL or local URL
    
    Returns:
        S3 key if it's an S3 URL, None otherwise
    """
    if not url:
        return None
    
    # Check if it's an S3 URL (starts with http/https)
    if url.startswith('http://') or url.startswith('https://'):
        # Extract key from URL
        # Format: https://bucket.s3.region.amazonaws.com/key
        # or: https://custom-domain.com/key
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        # Get path and remove leading slash, then URL decode
        key = unquote(parsed.path.lstrip('/'))
        return key if key else None
    
    return None


def upload_file(file_obj, filename, folder='uploads', content_type=None):
    """
    Upload a file to either S3 or local storage based on settings.
    
    Args:
        file_obj: File-like object to upload
        filename: Filename to use
        folder: Folder/subfolder name (default: 'uploads')
        content_type: Optional MIME type
    
    Returns:
        URL to access the file, or None if upload failed
    """
    if is_s3_enabled():
        # Upload to S3
        s3_key = f"{folder}/{filename}"
        url = upload_file_to_s3(file_obj, s3_key, content_type)
        if url:
            return url
        # Fall back to local if S3 upload fails
        current_app.logger.warning("S3 upload failed, falling back to local storage")
    
    # Upload to local storage
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if folder != 'uploads':
        upload_folder = os.path.join(upload_folder, folder)
    os.makedirs(upload_folder, exist_ok=True)
    
    filepath = os.path.join(upload_folder, filename)
    file_obj.seek(0)
    
    # Save file to disk
    with open(filepath, 'wb') as f:
        f.write(file_obj.read())
    
    # Return local URL
    from flask import url_for
    if folder == 'uploads':
        return url_for('static', filename=f'uploads/{filename}')
    else:
        return url_for('static', filename=f'uploads/{folder}/{filename}')


def delete_file(file_path_or_url):
    """
    Delete a file from either S3 or local storage.
    
    Args:
        file_path_or_url: Local file path or S3 URL
    
    Returns:
        True if successful, False otherwise
    """
    if is_s3_enabled():
        # Check if it's an S3 URL
        s3_key = get_s3_key_from_url(file_path_or_url)
        if s3_key:
            return delete_file_from_s3(s3_key)
    
    # Delete from local storage
    if os.path.exists(file_path_or_url):
        try:
            os.remove(file_path_or_url)
            return True
        except OSError:
            return False
    
    return False


def get_file_url(file_path_or_url):
    """
    Get the URL for a file, whether it's stored locally or in S3.
    
    Args:
        file_path_or_url: Local file path or S3 URL
    
    Returns:
        URL to access the file
    """
    # If it's already a URL (S3 or local), return it
    if file_path_or_url.startswith('http://') or file_path_or_url.startswith('https://'):
        return file_path_or_url
    
    # If it's a local path, convert to URL
    if file_path_or_url.startswith('/'):
        # Already a URL path
        return file_path_or_url
    
    # Convert local file path to URL
    from flask import url_for
    
    # Extract relative path from absolute path
    static_folder = current_app.static_folder
    if file_path_or_url.startswith(static_folder):
        relative_path = file_path_or_url[len(static_folder):].lstrip('/')
        return url_for('static', filename=relative_path)
    
    return file_path_or_url


def download_file_from_s3(s3_key):
    """
    Download a file from S3 and return its contents.
    
    Args:
        s3_key: S3 object key (path in bucket)
    
    Returns:
        File contents as bytes, or None if failed
    """
    result = get_s3_client()
    if not result:
        return None
    
    client, bucket = result
    
    try:
        response = client.get_object(Bucket=bucket, Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        current_app.logger.error(f"Error downloading from S3: {str(e)}")
        return None
    except Exception as e:
        current_app.logger.error(f"Unexpected error downloading from S3: {str(e)}")
        return None


def is_s3_url(url_or_path):
    """Check if a URL/path is an S3 URL."""
    if not url_or_path:
        return False
    return url_or_path.startswith('http://') or url_or_path.startswith('https://')


def file_exists(file_path_or_url):
    """
    Check if a file exists, whether it's in S3 or local storage.
    
    Args:
        file_path_or_url: Local file path or S3 URL
    
    Returns:
        True if file exists, False otherwise
    """
    if is_s3_url(file_path_or_url):
        # For S3 URLs, we assume they exist if the URL is valid
        # (we could verify by checking S3, but that's expensive)
        return True
    
    # Check local file
    return os.path.exists(file_path_or_url)
