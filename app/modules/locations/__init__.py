from flask import Blueprint

bp = Blueprint('locations', __name__, url_prefix='/locations')

# Import routes after bp is defined to avoid circular import
from app.modules.locations import routes


