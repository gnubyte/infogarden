from flask import Blueprint

bp = Blueprint('contacts', __name__, url_prefix='/contacts')

# Import routes after bp is defined to avoid circular import
from app.modules.contacts import routes

