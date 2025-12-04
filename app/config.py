import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 
        'mysql+pymysql://infogarden:infogarden@localhost/infogarden')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    BACKUP_FOLDER = os.path.join(os.path.dirname(__file__), 'backups')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB for software uploads
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '')
    
    # Backup settings (defaults)
    BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_DAY = os.getenv('BACKUP_DAY', 'sunday')  # sunday, monday, etc.
    BACKUP_HOUR = int(os.getenv('BACKUP_HOUR', '0'))  # 0 = midnight
    BACKUP_MINUTE = int(os.getenv('BACKUP_MINUTE', '0'))
    BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))  # Keep backups for 30 days

