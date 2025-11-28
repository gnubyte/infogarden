from flask import Blueprint

bp = Blueprint('passwords', __name__, url_prefix='/passwords')

# Import routes after bp is defined to avoid circular import
from app.modules.passwords import routes

