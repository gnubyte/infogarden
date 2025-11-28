"""
Database backup and restore functionality
"""
import os
import subprocess
import gzip
from datetime import datetime, timedelta
from app import db_session
from app.core import models
import logging

logger = logging.getLogger(__name__)

def get_db_config():
    """Extract database configuration from SQLAlchemy URI"""
    from flask import current_app
    from app import db_engine
    url = str(db_engine.url)
    # Parse mysql+pymysql://user:pass@host:port/dbname
    if 'mysql' in url:
        parts = url.replace('mysql+pymysql://', '').split('@')
        if len(parts) == 2:
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')
            if len(host_db) == 2:
                host_port = host_db[0].split(':')
                return {
                    'user': user_pass[0],
                    'password': user_pass[1] if len(user_pass) > 1 else '',
                    'host': host_port[0],
                    'port': int(host_port[1]) if len(host_port) > 1 else 3306,
                    'database': host_db[1]
                }
    return None

def create_backup():
    """Create a database backup"""
    try:
        db_config = get_db_config()
        if not db_config:
            logger.error("Could not extract database configuration")
            return None
        
        backup_folder = current_app.config.get('BACKUP_FOLDER', 'app/backups')
        os.makedirs(backup_folder, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_folder, f'backup_{timestamp}.sql')
        compressed_file = f'{backup_file}.gz'
        
        # Create mysqldump command
        cmd = [
            'mysqldump',
            f"--user={db_config['user']}",
            f"--password={db_config['password']}",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            '--single-transaction',
            '--routines',
            '--triggers',
            db_config['database']
        ]
        
        # Execute mysqldump
        with open(backup_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                logger.error(f"Backup failed: {result.stderr}")
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return None
        
        # Compress backup
        with open(backup_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Remove uncompressed file
        os.remove(backup_file)
        
        logger.info(f"Backup created: {compressed_file}")
        return compressed_file
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        return None

def restore_backup(backup_file):
    """Restore database from backup file"""
    try:
        from flask import current_app
        db_config = get_db_config()
        if not db_config:
            logger.error("Could not extract database configuration")
            return False
        
        # Decompress if needed
        if backup_file.endswith('.gz'):
            import tempfile
            with gzip.open(backup_file, 'rb') as f_in:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sql') as f_out:
                    f_out.write(f_in.read().decode('utf-8'))
                    temp_file = f_out.name
        else:
            temp_file = backup_file
        
        # Create mysql command
        cmd = [
            'mysql',
            f"--user={db_config['user']}",
            f"--password={db_config['password']}",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            db_config['database']
        ]
        
        # Execute restore
        with open(temp_file, 'r') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                logger.error(f"Restore failed: {result.stderr}")
                if temp_file != backup_file:
                    os.remove(temp_file)
                return False
        
        # Cleanup temp file
        if temp_file != backup_file:
            os.remove(temp_file)
        
        logger.info(f"Backup restored from: {backup_file}")
        return True
    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}")
        return False

def cleanup_old_backups():
    """Remove backups older than retention period"""
    try:
        backup_folder = current_app.config.get('BACKUP_FOLDER', 'app/backups')
        retention_days = current_app.config.get('BACKUP_RETENTION_DAYS', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        if not os.path.exists(backup_folder):
            return
        
        for filename in os.listdir(backup_folder):
            if filename.startswith('backup_') and filename.endswith('.sql.gz'):
                filepath = os.path.join(backup_folder, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_date:
                    os.remove(filepath)
                    logger.info(f"Removed old backup: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {str(e)}")

def setup_backup_scheduler(app, engine):
    """Setup scheduled backups using APScheduler"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = BackgroundScheduler()
        
        # Get backup schedule from config or settings
        backup_day = app.config.get('BACKUP_DAY', 'sunday').lower()
        backup_hour = app.config.get('BACKUP_HOUR', 0)
        backup_minute = app.config.get('BACKUP_MINUTE', 0)
        
        # Map day name to cron day
        day_map = {
            'sunday': 6,
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5
        }
        
        day_of_week = day_map.get(backup_day, 6)
        
        if app.config.get('BACKUP_ENABLED', True):
            scheduler.add_job(
                func=create_backup,
                trigger=CronTrigger(day_of_week=day_of_week, hour=backup_hour, minute=backup_minute),
                id='weekly_backup',
                name='Weekly Database Backup',
                replace_existing=True
            )
            
            # Also schedule cleanup
            scheduler.add_job(
                func=cleanup_old_backups,
                trigger=CronTrigger(hour=1, minute=0),  # Daily at 1 AM
                id='backup_cleanup',
                name='Backup Cleanup',
                replace_existing=True
            )
            
            scheduler.start()
            logger.info(f"Backup scheduler started: {backup_day} at {backup_hour:02d}:{backup_minute:02d}")
    except Exception as e:
        logger.error(f"Error setting up backup scheduler: {str(e)}")

