import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from db import query, execute
from utils.auth import editor_required, admin_required, login_required

soportes_bp = Blueprint('soportes', __name__)

ALLOWED_EXTENSIONS = {
    'pdf', 'mp3', 'wav', 'mid', 'midi',
    'mscz', 'mxl', 'xml', 'sib', 'musx',
    'mp4', 'mov', 'webm', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import re as _re

def _slug(text, maxlen=40):
    """Convierte texto a slug seguro para carpeta."""
    text = str(text or '').strip()
    text = _re.sub(r'[^\w\s\-]', '', text, flags=_re.UNICODE)
    text = _re.sub(r'[\s\-]+', '_', text).strip('_')
    return text[:maxlen] or 'untitled'

def build_media_path(copia_id, filename, soporte_id=None):
    """
    Ruta jerárquica:
    MEDIA_ROOT/obras/<obra_id>_<titulo>/v<version_id>/a<arreglo_id>/c<copia_id>/s<soporte_id>_<filename>
    """
    media_root = current_app.config['MEDIA_ROOT']

    # Fetch hierarchy
    row = query(
        '''SELECT o.obra_id, o.title,
                  v.version_id,
                  ar.arreglo_id
           FROM COPIA cp
           JOIN ARREGLO ar   ON ar.arreglo_id  = cp.arreglo_id
           JOIN `VERSION` v  ON v.version_id   = ar.version_id
           JOIN OBRA o        ON o.obra_id      = v.obra_id
           WHERE cp.copia_id = %s''',
        (copia_id,), fetchone=True
    )
    if row:
        obra_folder    = f"{row['obra_id']:04d}_{_slug(row['title'])}"
        version_folder = f"v{row['version_id']:03d}"
        arreglo_folder = f"a{row['arreglo_id']:03d}"
    else:
        obra_folder    = 'unknown'
        version_folder = 'v000'
        arreglo_folder = 'a000'

    copia_folder = f"c{copia_id:03d}"

    folder = os.path.join(media_root, 'obras', obra_folder,
                          version_folder, arreglo_folder, copia_folder)
    os.makedirs(folder, exist_ok=True)

    # Prefix filename with soporte_id to guarantee uniqueness
    if soporte_id:
        safe_name = f"s{soporte_id:04d}_{filename}"
    else:
        safe_name = filename

    rel_path = '/'.join(['obras', obra_folder, version_folder,
                         arreglo_folder, copia_folder, safe_name])
    return os.path.join(folder, safe_name), rel_path


@soportes_bp.route('/upload/<int:copia_id>', methods=['POST'])
@editor_required
def upload_soporte(copia_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún fichero'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de fichero vacío'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de fichero no permitido'}), 400

    filename        = secure_filename(file.filename)
    tipo_soporte_id = request.form.get('tipo_soporte_id')
    ubicacion_id    = request.form.get('ubicacion_id')
    created_date    = request.form.get('created_date')
    instrumento_id  = request.form.get('instrumento_id') or None
    created_by      = request.current_user['usuario_id']

    # Insert first to get soporte_id, then build path and update
    sid = execute(
        '''INSERT INTO SOPORTE
           (copia_id, tipo_soporte_id, file_path, ubicacion_id, instrumento_id, created_by, created_date)
           VALUES (%s, %s, %s, %s, %s, %s, %s)''',
        (copia_id, tipo_soporte_id, '__pending__', ubicacion_id, instrumento_id, created_by, created_date)
    )

    abs_path, rel_path = build_media_path(copia_id, filename, soporte_id=sid)
    file.save(abs_path)

    execute('UPDATE SOPORTE SET file_path=%s WHERE soporte_id=%s', (rel_path, sid))
    return jsonify({'soporte_id': sid, 'file_path': rel_path}), 201

@soportes_bp.route('', methods=['POST'])
@editor_required
def create_soporte_url():
    """Crea un soporte con URL externa (sin subir fichero)."""
    data = request.get_json()
    sid = execute(
        '''INSERT INTO SOPORTE
           (copia_id, tipo_soporte_id, url_externa, ubicacion_id, instrumento_id, created_by, created_date)
           VALUES (%s, %s, %s, %s, %s, %s, %s)''',
        (data.get('copia_id'), data.get('tipo_soporte_id'), data.get('url_externa'),
         data.get('ubicacion_id'), data.get('instrumento_id') or None,
         request.current_user['usuario_id'], data.get('created_date'))
    )
    return jsonify({'soporte_id': sid}), 201

@soportes_bp.route('/<int:soporte_id>', methods=['PUT'])
@editor_required
def update_soporte(soporte_id):
    data = request.get_json()
    execute(
        '''UPDATE SOPORTE SET tipo_soporte_id=%s, url_externa=%s,
           ubicacion_id=%s, instrumento_id=%s, created_date=%s
           WHERE soporte_id=%s''',
        (data.get('tipo_soporte_id') or None,
         data.get('url_externa') or None,
         data.get('ubicacion_id') or None,
         data.get('instrumento_id') or None,
         data.get('created_date') or None,
         soporte_id)
    )
    return jsonify({'ok': True})

@soportes_bp.route('/<int:soporte_id>', methods=['DELETE'])
@admin_required
def delete_soporte(soporte_id):
    soporte = query('SELECT * FROM SOPORTE WHERE soporte_id = %s', (soporte_id,), fetchone=True)
    if soporte and soporte.get('file_path'):
        full = os.path.join(current_app.config['MEDIA_ROOT'], soporte['file_path'])
        if os.path.exists(full):
            os.remove(full)
    execute('DELETE FROM SOPORTE WHERE soporte_id = %s', (soporte_id,))
    return jsonify({'ok': True})
