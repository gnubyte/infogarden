from flask import Blueprint

bp = Blueprint('orgs', __name__, url_prefix='/orgs')

# Import routes after bp is defined to avoid circular import
from app.modules.orgs import routes

