from flask import Flask
from config import config_by_name
# Hapus baris duplikat, cukup satu baris import ini:
from .extensions import db, migrate, jwt

def create_app(config_name):
    # 1. Inisialisasi Flask
    app = Flask(__name__)
    
    # 2. Muat Konfigurasi (Dev/Prod)
    app.config.from_object(config_by_name[config_name])
    
    # 3. Inisialisasi Plugin (Database & Migrasi)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # 4. Import Models
    from app import models

    # 5. REGISTER BLUEPRINTS (DAFTARKAN MODUL)

    # --- Modul Auth ---
    from app.modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    
    # --- Modul Admin (INI YANG HILANG TADI) ---
    # Pastikan import dari 'app.modules.admin', bukan 'routes' langsung
    # karena kita pakai __init__.py di folder admin sebagai penghubung
    from app.modules.admin import admin_bp 
    app.register_blueprint(admin_bp)
    
    # --- Modul Sales ---
    from app.modules.sales.routes import sales_bp
    app.register_blueprint(sales_bp)
    
    # --- Modul Production ---
    from app.modules.production.routes import production_bp
    app.register_blueprint(production_bp)
    
    @app.route('/')
    def hello():
        return "Mini-ERP Backend is Running!"

    return app