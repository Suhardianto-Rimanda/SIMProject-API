from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

# Decorator Khusus ADMIN
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') != 'admin':
                return jsonify({'message': 'Akses Ditolak! Hanya Admin.'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# Decorator Khusus KASIR (Admin boleh intip)
def cashier_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') not in ['cashier', 'admin']:
                return jsonify({'message': 'Akses Ditolak! Hanya Kasir.'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# Decorator Khusus DAPUR (Admin boleh intip)
def kitchen_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') not in ['kitchen', 'admin']:
                return jsonify({'message': 'Akses Ditolak! Hanya Staff Dapur.'}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper