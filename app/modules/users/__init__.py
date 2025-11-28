from flask import Blueprint

bp = Blueprint('users', __name__, url_prefix='/users')

# Import routes after bp is defined to avoid circular import
from app.modules.users import routes

