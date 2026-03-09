from flask import Blueprint, request, jsonify
from db import query, execute
from utils.auth import editor_required, admin_required

versiones_bp = Blueprint('versiones', __name__)

@versiones_bp.route('', methods=['POST'])
@editor_required
def create_version():
    data = request.get_json()
    vid = execute(
        'INSERT INTO `VERSION` (obra_id, compositor_id, description) VALUES (%s, %s, %s)',
        (data.get('obra_id'), data.get('compositor_id'), data.get('description'))
    )
    return jsonify({'version_id': vid}), 201

@versiones_bp.route('/<int:version_id>', methods=['PUT'])
@editor_required
def update_version(version_id):
    data = request.get_json()
    execute(
        'UPDATE `VERSION` SET compositor_id=%s, description=%s WHERE version_id=%s',
        (data.get('compositor_id'), data.get('description'), version_id)
    )
    return jsonify({'ok': True})

@versiones_bp.route('/<int:version_id>', methods=['DELETE'])
@admin_required
def delete_version(version_id):
    execute('DELETE FROM `VERSION` WHERE version_id = %s', (version_id,))
    return jsonify({'ok': True})
