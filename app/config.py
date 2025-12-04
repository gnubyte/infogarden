import os
from dotenv import load_dotenv

load_dotenv()

def get_database_uri():
    """
    Build database URI from environment variables.
    Supports both DATABASE_URL (full connection string) and individual components.
    Individual components take precedence if DATABASE_URL is not set.
    """
    # First, check if DATABASE_URL is explicitly set
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url
    
    # Otherwise, build from individual components
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    db_user = os.getenv('DB_USER', 'infogarden')
    db_password = os.getenv('DB_PASSWORD', 'infogarden')
    db_name = os.getenv('DB_NAME', 'infogarden')
    
    return f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = get_database_uri()
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

