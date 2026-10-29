"""
Routes Package Initialization
"""

from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')
api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

from .upload_routes import *
from .ocr_routes import *
from .export_routes import *
from .history_routes import *
from .dashboard_routes import *
from .admin_routes import admin_bp, api_admin_bp
