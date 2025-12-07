import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from datetime import timedelta

# Load environment variables dari file .env
load_dotenv()

class Config:
    """Base configuration yang dipakai di semua environment"""
    # Kunci keamanan untuk session & enkripsi (Wajib ada)
    SECRET_KEY = os.getenv('SECRET_KEY', 'kunci_cadangan_jika_env_gagal')
    
    # Kunci Rahasia JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'kunci_jwt_rahasia_banget')
    
    # --- PENGATURAN DURASI TOKEN ---
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24) 
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def get_db_uri():
        """
        Fungsi pintar untuk menentukan Database URI:
        1. Cek apakah ada DATABASE_URL (dari Hosting/Railway/Render).
        2. Jika tidak ada, rakit manual dari variabel terpisah (Local/Laragon).
        """
        # 1. Cek URL Langsung (Biasanya dari Hosting)
        url = os.getenv('DB_URL')
        
        if url:
            # FIX PENTING: Hosting sering memberi 'mysql://', tapi Python butuh 'mysql+pymysql://'
            if url.startswith('mysql://'):
                url = url.replace('mysql://', 'mysql+pymysql://', 1)
            return url
        
        # 2. Jika tidak ada URL langsung, rakit manual (Mode Local)
        db_user = os.getenv('DB_USERNAME', 'root')
        db_pass = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '3306')
        db_name = os.getenv('DB_NAME', 'db_simproject') # Default nama DB

        # Encode password agar simbol spesial (seperti @) tidak merusak link
        if db_pass:
            db_pass = quote_plus(db_pass)

        return f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

class DevelopmentConfig(Config):
    """Konfigurasi untuk saat kita coding (Development)"""
    DEBUG = True
    # Panggil fungsi helper di atas
    SQLALCHEMY_DATABASE_URI = Config.get_db_uri()

class ProductionConfig(Config):
    """Konfigurasi untuk saat aplikasi sudah live"""
    DEBUG = False
    # Panggil fungsi helper yang sama (otomatis deteksi ENV production)
    SQLALCHEMY_DATABASE_URI = Config.get_db_uri()

# Dictionary untuk mapping nama konfigurasi
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}