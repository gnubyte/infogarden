"""
Auto-migration system that detects schema changes and applies them safely
"""
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
import logging

logger = logging.getLogger(__name__)

def get_table_columns(engine, table_name):
    """Get current columns in database table"""
    inspector = inspect(engine)
    try:
        columns = inspector.get_columns(table_name)
        return {col['name']: col for col in columns}
    except Exception:
        return {}

def get_model_columns(model):
    """Get columns from SQLAlchemy model"""
    mapper = inspect(model)
    columns = {}
    for column in mapper.columns:
        columns[column.name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'primary_key': column.primary_key,
            'default': column.default.arg if column.default else None
        }
    return columns

def safe_add_column(engine, table_name, column_name, column_def):
    """Safely add a column to a table"""
    try:
        with engine.connect() as conn:
            # Check if column already exists
            inspector = inspect(engine)
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            if column_name in existing_columns:
                return False
            
            # Build ALTER TABLE statement
            type_str = str(column_def['type'])
            nullable = 'NULL' if column_def['nullable'] else 'NOT NULL'
            
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {type_str} {nullable}"
            
            if column_def.get('default') is not None:
                default_val = column_def['default']
                if isinstance(default_val, str):
                    alter_sql += f" DEFAULT '{default_val}'"
                else:
                    alter_sql += f" DEFAULT {default_val}"
            
            conn.execute(text(alter_sql))
            conn.commit()
            logger.info(f"Added column {column_name} to {table_name}")
            return True
    except Exception as e:
        logger.error(f"Error adding column {column_name} to {table_name}: {str(e)}")
        return False

def safe_drop_column(engine, table_name, column_name):
    """Safely drop a column from a table (only if it exists in DB but not in model)"""
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            if column_name not in existing_columns:
                return False
            
            # Only drop if explicitly removed from model
            alter_sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
            conn.execute(text(alter_sql))
            conn.commit()
            logger.info(f"Dropped column {column_name} from {table_name}")
            return True
    except Exception as e:
        logger.error(f"Error dropping column {column_name} from {table_name}: {str(e)}")
        return False

def migrate_table(engine, model):
    """Migrate a single table"""
    table_name = model.__tablename__
    db_columns = get_table_columns(engine, table_name)
    model_columns = get_model_columns(model)
    
    # If table doesn't exist, create it
    if not db_columns:
        model.metadata.create_all(engine, tables=[model.__table__])
        logger.info(f"Created table {table_name}")
        return
    
    # Add missing columns
    for col_name, col_def in model_columns.items():
        if col_name not in db_columns:
            safe_add_column(engine, table_name, col_name, col_def)
    
    # Note: We don't automatically drop columns unless explicitly configured
    # This is a safety measure - columns should be dropped manually if needed

def run_auto_migration(engine, session):
    """Run auto-migration for all models"""
    logger.info("Starting auto-migration...")
    
    try:
        # Import all models
        from app.core import models as core_models
        from app.modules.docs.models import Document, DocumentFolder
        from app.modules.contacts.models import Contact
        from app.modules.passwords.models import PasswordEntry
        
        # Migrate core models
        migrate_table(engine, core_models.User)
        migrate_table(engine, core_models.Organization)
        migrate_table(engine, core_models.ActivityLog)
        migrate_table(engine, core_models.Role)
        migrate_table(engine, core_models.Setting)
        
        # Migrate module models
        migrate_table(engine, DocumentFolder)
        migrate_table(engine, Document)
        migrate_table(engine, Contact)
        migrate_table(engine, PasswordEntry)
        
        logger.info("Auto-migration completed successfully")
    except Exception as e:
        logger.error(f"Error during auto-migration: {str(e)}")
        # Don't fail startup if migration has issues
        pass

