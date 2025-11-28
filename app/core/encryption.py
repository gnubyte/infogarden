from cryptography.fernet import Fernet
import os
import base64
from app import db_session

def get_encryption_key():
    """Get or generate encryption key from environment variable"""
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable must be set")
    
    # If key is not in base64 format, encode it
    try:
        # Try to decode to see if it's valid base64
        base64.b64decode(key)
        return key.encode()
    except:
        # If not valid base64, generate a key from the string
        # This is a fallback - ideally the key should be generated properly
        key_bytes = key.encode()
        # Pad or truncate to 32 bytes and base64 encode
        key_bytes = key_bytes[:32].ljust(32, b'0')
        return base64.urlsafe_b64encode(key_bytes)

def get_cipher():
    """Get Fernet cipher instance"""
    key = get_encryption_key()
    return Fernet(key)

def encrypt_data(data):
    """Encrypt data using Fernet"""
    if not data:
        return None
    cipher = get_cipher()
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    """Decrypt data using Fernet"""
    if not encrypted_data:
        return None
    cipher = get_cipher()
    try:
        return cipher.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

