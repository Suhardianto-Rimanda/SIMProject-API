from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import satu per satu, pastikan tidak ada yang diduplikasi
from . import user_routes
from . import master_routes
from . import dashboard_routes
from . import report_routes