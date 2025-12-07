import os
from dotenv import load_dotenv
from app import create_app

load_dotenv()

config_name = os.getenv('FLASK_ENV', 'development')
print(f"2. Mode Aplikasi: {config_name}")

try:
    app = create_app(config_name)
    print("3. Aplikasi berhasil di-inisialisasi.")
except Exception as e:
    print(f"!!! ERROR KRITIKAL saat create_app: {e}")
    exit(1)

if __name__ == '__main__':
    print("4. Menyalakan Server di http://localhost:5000 ...")
    print("   (Tekan CTRL+C untuk berhenti)")
    app.run(host='0.0.0.0', port=5000, debug=True)