"""Routes package with blueprints"""
from flask import Blueprint

# Create blueprints
auth_bp = Blueprint('auth', __name__)
products_bp = Blueprint('products', __name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
equipment_bp = Blueprint('equipment', __name__)
consulting_bp = Blueprint('consulting', __name__)

from routes import auth, products, admin, equipment, consulting
