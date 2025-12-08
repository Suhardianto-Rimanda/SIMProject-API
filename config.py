import os
from dotenv import load_dotenv
from datetime import timedelta  # <--- WAJIB DITAMBAHKAN

# Load environment variables dari file .env
load_dotenv()

class Config:
    """Base configuration yang dipakai di semua environment"""
    # Kunci keamanan untuk session & enkripsi (Wajib ada)
    SECRET_KEY = os.getenv('SECRET_KEY', 'kunci_cadangan_jika_env_gagal')
    
    # Kunci Rahasia JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'kunci_jwt_rahasia_banget')
    
    # --- PENGATURAN DURASI TOKEN ---
    # Access Token: Tiket utama (Saya set 1 Hari / 24 Jam agar aman seharian)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24) 
    
    # Refresh Token: Tiket cadangan (Opsional, default 30 hari)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Konfigurasi untuk saat kita coding (Development)"""
    DEBUG = True
    # Ambil link database dari .env
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

class ProductionConfig(Config):
    """Konfigurasi untuk saat aplikasi sudah live"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

# Dictionary untuk mapping nama konfigurasi
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}