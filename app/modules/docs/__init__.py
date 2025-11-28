from flask import Blueprint

bp = Blueprint('docs', __name__, url_prefix='/docs')

# Import routes after bp is defined to avoid circular import
from app.modules.docs import routes

