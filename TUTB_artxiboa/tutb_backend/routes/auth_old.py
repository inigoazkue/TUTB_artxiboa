from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import query, execute
from utils.auth import generate_token, login_required, admin_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Usuario y contraseña requeridos'}), 400

    user = query(
        'SELECT * FROM USUARIO WHERE username = %s AND activo = 1',
        (username,), fetchone=True
    )
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Credenciales incorrectas'}), 401

    token = generate_token(user)
    return jsonify({
        'token':      token,
        'usuario_id': user['usuario_id'],
        'username':   user['username'],
        'role':       user['role']
    })

@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify(request.current_user)

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data        = request.get_json()
    old_pass    = data.get('old_password', '')
    new_pass    = data.get('new_password', '')

    if len(new_pass) < 8:
        return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400

    user = query(
        'SELECT * FROM USUARIO WHERE usuario_id = %s',
        (request.current_user['usuario_id'],), fetchone=True
    )
    if not check_password_hash(user['password_hash'], old_pass):
        return jsonify({'error': 'Contraseña actual incorrecta'}), 401

    execute(
        'UPDATE USUARIO SET password_hash = %s WHERE usuario_id = %s',
        (generate_password_hash(new_pass), user['usuario_id'])
    )
    return jsonify({'ok': True})

@auth_bp.route('/usuarios', methods=['GET'])
@admin_required
def list_usuarios():
    users = query('SELECT usuario_id, username, email, role, activo, created_at FROM USUARIO')
    return jsonify(users)

@auth_bp.route('/usuarios', methods=['POST'])
@admin_required
def create_usuario():
    data = request.get_json()
    username = data.get('username', '').strip()
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    role     = data.get('role', 'reader')

    if not username or not email or not password:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
    if role not in ('admin', 'editor', 'reader', 'guest'):
        return jsonify({'error': 'Rol no válido'}), 400

    uid = execute(
        'INSERT INTO USUARIO (username, email, password_hash, role) VALUES (%s, %s, %s, %s)',
        (username, email, generate_password_hash(password), role)
    )
    return jsonify({'usuario_id': uid}), 201

@auth_bp.route('/usuarios/<int:uid>', methods=['PUT'])
@admin_required
def update_usuario(uid):
    data    = request.get_json()
    current = request.current_user
    fields, params = [], []
    if 'username' in data and data['username']:
        fields.append('username = %s'); params.append(data['username'].strip())
    if 'email' in data:
        fields.append('email = %s');    params.append(data['email'].strip() or None)
    if 'role' in data and data['role']:
        fields.append('role = %s');     params.append(data['role'])
    if 'activo' in data:
        fields.append('activo = %s');   params.append(int(data['activo']))
    if 'password' in data and data['password']:
        import bcrypt as _bcrypt
        pw_hash = _bcrypt.hashpw(data['password'].encode(), _bcrypt.gensalt()).decode()
        fields.append('password_hash = %s'); params.append(pw_hash)
    if fields:
        params.append(uid)
        execute(f'UPDATE USUARIO SET {", ".join(fields)} WHERE usuario_id = %s', params)
    return jsonify({'ok': True})

@auth_bp.route('/usuarios/<int:uid>', methods=['DELETE'])
@admin_required
def delete_usuario(uid):
    current = request.current_user
    if current['usuario_id'] == uid:
        return jsonify({'error': 'Ezin duzu zure burua ezabatu'}), 400
    execute('DELETE FROM USUARIO WHERE usuario_id = %s', (uid,))
    return jsonify({'ok': True})
