import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app
from db import query

def generate_token(usuario):
    payload = {
        'usuario_id': usuario['usuario_id'],
        'username':   usuario['username'],
        'role':       usuario['role'],
        'exp':        datetime.datetime.utcnow() + datetime.timedelta(
                          hours=current_app.config['JWT_EXPIRY_HOURS'])
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def decode_token(token):
    return jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])

def get_current_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        return decode_token(auth.split(' ')[1])
    except Exception:
        return None

# ── Decoradores de rol ─────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Autenticación requerida'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Autenticación requerida'}), 401
            if user['role'] not in roles:
                return jsonify({'error': 'Permisos insuficientes'}), 403
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator

# Shortcuts
editor_required = roles_required('admin', 'editor')
admin_required  = roles_required('admin')
