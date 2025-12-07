from flask import request, jsonify
from app.extensions import db, jwt
from app.models import User, TokenBlocklist
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, 
    jwt_required, 
    get_jwt, 
    get_jwt_identity
)
from datetime import datetime, timezone
from . import auth_bp

# =====================================================
# KONFIGURASI JWT BLOCKLIST (Untuk Logout)
# =====================================================
# Fungsi ini otomatis dipanggil Flask setiap ada request masuk yang bawa token
# untuk mengecek apakah token tersebut sudah pernah di-logout.
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
    return token is not None  # Jika True, akses ditolak (Token hangus)

# =====================================================
# ROUTE REGISTER
# =====================================================
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validasi Username Unik
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username sudah ada'}), 409

    new_user = User(
        full_name=data.get('full_name', 'No Name'),
        username=data['username'],
        password=generate_password_hash(data['password']),
        role=data.get('role', 'kitchen') # Default ke kitchen jika kosong
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Registrasi berhasil'}), 201

# =====================================================
# ROUTE LOGIN (Updated: Tanpa Redirect URL)
# =====================================================
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()

    # Cek Password
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Login gagal, cek username/password.'}), 401

    # Buat Token (Identity = ID User, Claims = Role)
    access_token = create_access_token(
        identity=str(user.id), 
        additional_claims={"role": user.role} 
    )

    # Return JSON bersih (Frontend yang atur navigasi berdasarkan 'role')
    return jsonify({
        'message': 'Login berhasil',
        'access_token': access_token,
        'user': {
            'username': user.username, 
            'role': user.role
        }
    }), 200

# =====================================================
# ROUTE LOGOUT (Fitur Baru)
# =====================================================
@auth_bp.route('/logout', methods=['POST'])
@jwt_required() # Wajib bawa token kalau mau logout
def logout():
    jti = get_jwt()["jti"]  # Ambil ID unik token dari header
    now = datetime.now(timezone.utc)
    
    # Masukkan token ke daftar hitam (Blocklist) di database
    db.session.add(TokenBlocklist(jti=jti, created_at=now))
    db.session.commit()
    
    return jsonify(msg="Logout berhasil, token hangus."), 200