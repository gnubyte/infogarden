from flask import Blueprint

bp = Blueprint('search', __name__, url_prefix='/search')

# Import routes after bp is defined to avoid circular import
from app.modules.search import routes

