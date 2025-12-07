from flask import Blueprint

# Membuat Blueprint bernama 'auth' dengan prefix url '/auth'
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import routes