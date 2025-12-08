from flask import Flask
from config import config_by_name
from .extensions import db, migrate, jwt

# 1. TAMBAHKAN IMPORT INI
from flask_cors import CORS 

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # 2. AKTIFKAN CORS DI SINI
    # Ini mengizinkan semua domain (*) mengakses API. Aman untuk development.
    CORS(app, resources={r"/*": {"origins": "*"}})

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app import models

    from app.modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.modules.admin import admin_bp 
    app.register_blueprint(admin_bp)

    from app.modules.sales.routes import sales_bp
    app.register_blueprint(sales_bp)

    from app.modules.production.routes import production_bp
    app.register_blueprint(production_bp)

    @app.route('/')
    def hello():
        return "Mini-ERP Backend is Running!"

    return app