from flask import jsonify
from app.decorators import admin_required
from . import admin_bp

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required()
def admin_dashboard():
    return jsonify({
        "title": "ADMIN DASHBOARD",
        "menu": ["Manajemen User", "Master Bahan", "Master Resep", "Laporan Keuangan"]
    }), 200