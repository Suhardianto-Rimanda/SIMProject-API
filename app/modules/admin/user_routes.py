from flask import request, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User
from app.decorators import admin_required  # <--- IMPOR INI
from . import admin_bp

# --- ENDPOINT BUAT USER BARU ---
@admin_bp.route('/users', methods=['POST'])
@admin_required()  # <--- GEMBOKNYA DI SINI
def create_user():
    data = request.get_json()
    
    # Validasi Input
    if not data.get('username') or not data.get('password') or not data.get('role'):
        return jsonify({'message': 'Data tidak lengkap!'}), 400

    # Cek Duplikat
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username sudah ada!'}), 409

    # Simpan
    new_user = User(
        full_name=data.get('full_name', 'Staff'),
        username=data['username'],
        password=generate_password_hash(data['password']),
        role=data['role']
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': f'User {new_user.username} berhasil dibuat!'}), 201

# --- ENDPOINT LIHAT SEMUA USER ---
@admin_bp.route('/users', methods=['GET'])
@admin_required() # Hanya admin yang boleh lihat daftar pegawai
def get_all_users():
    users = User.query.filter(User.role.in_(["kitchen", "cashier"])).all()
    output = []
    for u in users:
        output.append({
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'full_name': u.full_name
        })
    return jsonify(output), 200

# --- ENDPOINT EDIT USER (UPDATE) ---
@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required()
def update_user(user_id):
    # 1. Cari user yang mau diedit
    user = User.query.get_or_404(user_id)
    
    data = request.get_json()

    # 2. Logic Ganti Username (Cek duplikasi dulu)
    if 'username' in data and data['username'] != user.username:
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'message': 'Username sudah dipakai orang lain!'}), 409
        user.username = data['username']

    # 3. Logic Ganti Password (Harus di-hash ulang)
    if 'password' in data and data['password']:
        # Pastikan password tidak kosong stringnya
        if len(data['password'].strip()) > 0:
            user.password = generate_password_hash(data['password'])

    # 4. Update data profil standar
    if 'full_name' in data:
        user.full_name = data['full_name']
        
    if 'role' in data:
        if data['role'] not in ['admin', 'cashier', 'kitchen']:
            return jsonify({'message': 'Role tidak valid (pilih: admin, cashier, kitchen)'}), 400
        user.role = data['role']

    # 5. Simpan Perubahan
    try:
        db.session.commit()
        return jsonify({
            'message': 'Data user berhasil diperbarui.',
            'data': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Gagal update: {str(e)}'}), 500
# --- ENDPOINT HAPUS USER ---
@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required() # Hanya admin yang boleh pecat pegawai
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User dihapus.'}), 200