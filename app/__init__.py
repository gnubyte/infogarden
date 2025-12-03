from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
from dotenv import load_dotenv
from app.config import Config

load_dotenv()

login_manager = LoginManager()
csrf = CSRFProtect()
db_session = None
db_engine = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    login_manager.init_app(app)
    login_manager.login_view = 'core_auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    csrf.init_app(app)
    
    # Setup database session
    global db_session, db_engine
    db_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], pool_pre_ping=True)
    db_session = scoped_session(sessionmaker(bind=db_engine))
    
    # Import core models first
    from app.core import models as core_models
    
    # Import module models to ensure all relationships can be resolved
    from app.modules.docs.models import Document
    from app.modules.contacts.models import Contact
    from app.modules.passwords.models import PasswordEntry
    
    # Run auto-migration on startup
    from app.core.migration import run_auto_migration
    run_auto_migration(db_engine, db_session)
    
    # Create tables for all models
    core_models.Base.metadata.create_all(db_engine)
    
    # Dynamically load and register modules
    from app.modules import load_modules
    load_modules(app, db_engine)
    
    # Register core blueprint
    from app.core.routes import bp as core_bp
    app.register_blueprint(core_bp)
    
    # Register user loader
    @login_manager.user_loader
    def load_user(user_id):
        return core_models.User.query.get(int(user_id))
    
    # CSRF error handler
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import flash, request, redirect, url_for
        flash('CSRF token missing or invalid. Please try again.', 'error')
        # Try to redirect back to the referrer or dashboard
        if request.referrer:
            return redirect(request.referrer)
        return redirect(url_for('core_auth.dashboard'))
    
    # Context processor to make current org and branding available in all templates
    @app.context_processor
    def inject_template_vars():
        from flask import session
        from flask_login import current_user
        org = None
        org_id = session.get('current_org_id') or (current_user.org_id if current_user.is_authenticated else None)
        if org_id:
            org = core_models.Organization.query.get(org_id)
        
        # Get branding settings
        brand_name = 'InfoGarden'
        brand_logo = None
        for setting in core_models.Setting.query.filter(core_models.Setting.key.in_(['brand_name', 'brand_logo'])).all():
            if setting.key == 'brand_name' and setting.value:
                brand_name = setting.value
            elif setting.key == 'brand_logo' and setting.value:
                brand_logo = setting.value
        
        return dict(current_org=org, brand_name=brand_name, brand_logo=brand_logo)
    
    # Setup scheduled backups
    from app.core.backup import setup_backup_scheduler
    setup_backup_scheduler(app, db_engine)
    
    # Add markdown filter with YouTube video support
    import markdown
    import re
    
    def convert_youtube_links(text):
        """Convert YouTube URLs to embedded iframes"""
        # Pattern for various YouTube URL formats:
        # - https://www.youtube.com/watch?v=VIDEO_ID
        # - https://youtu.be/VIDEO_ID
        # - www.youtube.com/watch?v=VIDEO_ID
        # - youtube.com/watch?v=VIDEO_ID
        # Also handles URLs with additional parameters
        youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})(?:[^\s<>"]*)?'
        
        def replace_youtube(match):
            video_id = match.group(1)
            return f'<div class="youtube-embed"><iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'
        
        return re.sub(youtube_pattern, replace_youtube, text)
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text:
            return ''
        # First convert YouTube links
        text = convert_youtube_links(text)
        # Then render markdown
        html = markdown.markdown(text, extensions=['extra', 'codehilite'])
        return html
    
    return app
