from flask import Blueprint, request, jsonify, current_app
import os, re
from email.utils import parsedate_to_datetime
from werkzeug.utils import secure_filename
from db import query, execute
from utils.auth import editor_required, admin_required

conciertos_bp = Blueprint('conciertos', __name__)

ALLOWED_AUDIO = {'mp3','wav','ogg','flac','m4a','aac'}
ALLOWED_VIDEO = {'mp4','mov','webm','avi','mkv'}
ALLOWED_IMAGE = {'jpg','jpeg','png','gif','webp','pdf'}

def _parse_fecha(val):
    """Convierte cualquier formato de fecha a YYYY-MM-DD para MariaDB."""
    if not val:
        return None
    s = str(val).strip()
    # Ya está en formato correcto
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    # Formato HTTP: Thu, 24 Dec 2026 00:00:00 GMT
    try:
        return parsedate_to_datetime(s).strftime('%Y-%m-%d')
    except Exception:
        pass
    # Cualquier otro formato con fecha parseable
    try:
        from datetime import datetime
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%d/%m/%Y', '%m/%d/%Y'):
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    except Exception:
        pass
    return None

def _slug(text, maxlen=60):
    text = str(text or '').strip()
    text = re.sub(r'[^\w\s\-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s\-]+', '_', text).strip('_')
    return text[:maxlen] or 'kontzertua'

def _concierto_folder(concierto_id, nombre):
    media_root = current_app.config['MEDIA_ROOT']
    folder_name = f"{concierto_id:04d}_{_slug(nombre)}"
    folder = os.path.join(media_root, 'kontzertoak', folder_name)
    os.makedirs(folder, exist_ok=True)
    return folder, f"kontzertoak/{folder_name}"

def _get_concierto_nombre(concierto_id):
    row = query('SELECT nombre FROM CONCIERTO WHERE concierto_id=%s', (concierto_id,), fetchone=True)
    return row['nombre'] if row else 'kontzertua'

@conciertos_bp.route('/<int:concierto_id>/upload/<tipo>', methods=['POST'])
@editor_required
def upload_concierto_media(concierto_id, tipo):
    """
    tipo: audio | video | kartela | esku_programa
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Fitxategirik ez'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Fitxategi hutsa'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    allowed = {
        'audio':         ALLOWED_AUDIO,
        'video':         ALLOWED_VIDEO,
        'kartela':       ALLOWED_IMAGE,
        'esku_programa': ALLOWED_IMAGE | {'pdf'},
    }.get(tipo, set())
    if ext not in allowed:
        return jsonify({'error': f'Fitxategi mota ez dago onartuta: .{ext}'}), 400

    nombre = _get_concierto_nombre(concierto_id)
    folder, rel_base = _concierto_folder(concierto_id, nombre)
    filename = secure_filename(f"{tipo}_{file.filename}")
    abs_path = os.path.join(folder, filename)
    rel_path = f"{rel_base}/{filename}"
    file.save(abs_path)

    col_map = {
        'audio':         'grab_audio_path',
        'video':         'grab_video_path',
        'kartela':       'kartela_path',
        'esku_programa': 'esku_programa_path',
    }
    col = col_map[tipo]
    execute(f'UPDATE CONCIERTO SET {col}=%s WHERE concierto_id=%s', (rel_path, concierto_id))
    return jsonify({'path': rel_path}), 200

@conciertos_bp.route('', methods=['GET'])
def list_conciertos():
    rows = query('SELECT * FROM CONCIERTO ORDER BY fecha DESC')
    return jsonify(rows)

@conciertos_bp.route('/<int:concierto_id>', methods=['GET'])
def get_concierto(concierto_id):
    c = query('SELECT * FROM CONCIERTO WHERE concierto_id = %s', (concierto_id,), fetchone=True)
    if not c:
        return jsonify({'error': 'Concierto no encontrado'}), 404

    c['programa'] = query(
        '''SELECT cp.programa_id, cp.orden, cp.notas,
                  cp.copia_id,
                  co.notas AS copia_notas,
                  tc.nombre AS tipo_copia,
                  ar.instrumentacion, ar.anyo,
                  CAST(ar.duracion AS CHAR) AS duracion,
                  t.nombre AS tonalidad, g.nombre AS genero,
                  v.description AS version_desc,
                  o.title AS obra_title, o.obra_id,
                  -- audio de referencia
                  s.soporte_id AS audio_ref_soporte_id,
                  s.file_path  AS audio_ref_path,
                  s.url_externa AS audio_ref_url
           FROM CONCIERTO_PROGRAMA cp
           JOIN COPIA      co ON co.copia_id     = cp.copia_id
           JOIN ARREGLO    ar ON ar.arreglo_id   = co.arreglo_id
           LEFT JOIN TIPO_COPIA tc ON tc.tipo_copia_id = co.tipo_copia_id
           LEFT JOIN TONALIDAD  t  ON t.tonalidad_id   = ar.tonalidad_id
           LEFT JOIN GENERO     g  ON g.genero_id      = ar.genero_id
           LEFT JOIN `VERSION`    v  ON v.version_id     = ar.version_id
           LEFT JOIN OBRA       o  ON o.obra_id        = v.obra_id
           LEFT JOIN SOPORTE    s  ON s.soporte_id     = cp.audio_ref_id
           WHERE cp.concierto_id = %s
           ORDER BY cp.orden''',
        (concierto_id,)
    )

    # Duración total del concierto (suma de duraciones de los arreglos)
    dur = query(
        '''SELECT CAST(SEC_TO_TIME(SUM(TIME_TO_SEC(ar.duracion))) AS CHAR) AS duracion_total
           FROM CONCIERTO_PROGRAMA cp
           JOIN COPIA   co ON co.copia_id   = cp.copia_id
           JOIN ARREGLO ar ON ar.arreglo_id = co.arreglo_id
           WHERE cp.concierto_id = %s AND ar.duracion IS NOT NULL''',
        (concierto_id,), fetchone=True
    )
    c['duracion_total'] = dur['duracion_total'] if dur else None

    return jsonify(c)

@conciertos_bp.route('', methods=['POST'])
@editor_required
def create_concierto():
    data = request.get_json()
    cid = execute(
        '''INSERT INTO CONCIERTO (nombre, fecha, venue, notas,
           grab_audio_path, grab_audio_url, grab_video_path, grab_video_url,
           kartela_path, esku_programa_path)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
        (data.get('nombre'), _parse_fecha(data.get('fecha')), data.get('venue'), data.get('notas'),
         data.get('grab_audio_path'), data.get('grab_audio_url'),
         data.get('grab_video_path'), data.get('grab_video_url'),
         None, None)
    )
    return jsonify({'concierto_id': cid}), 201

@conciertos_bp.route('/<int:concierto_id>', methods=['PUT'])
@editor_required
def update_concierto(concierto_id):
    data = request.get_json()
    execute(
        '''UPDATE CONCIERTO SET nombre=%s, fecha=%s, venue=%s, notas=%s,
           grab_audio_url=%s, grab_video_url=%s
           WHERE concierto_id=%s''',
        (data.get('nombre'), _parse_fecha(data.get('fecha')), data.get('venue'), data.get('notas'),
         data.get('grab_audio_url'), data.get('grab_video_url'), concierto_id)
    )
    return jsonify({'ok': True})

@conciertos_bp.route('/<int:concierto_id>', methods=['DELETE'])
@admin_required
def delete_concierto(concierto_id):
    execute('DELETE FROM CONCIERTO WHERE concierto_id = %s', (concierto_id,))
    return jsonify({'ok': True})

# ── Programa ───────────────────────────────────────────────────────────────

@conciertos_bp.route('/<int:concierto_id>/programa', methods=['POST'])
@editor_required
def add_programa(concierto_id):
    data = request.get_json()
    pid = execute(
        '''INSERT INTO CONCIERTO_PROGRAMA
           (concierto_id, copia_id, orden, audio_ref_id, notas)
           VALUES (%s, %s, %s, %s, %s)''',
        (concierto_id, data.get('copia_id'), data.get('orden'),
         data.get('audio_ref_id'), data.get('notas'))
    )
    return jsonify({'programa_id': pid}), 201

@conciertos_bp.route('/programa/<int:programa_id>', methods=['PUT'])
@editor_required
def update_programa(programa_id):
    data = request.get_json()
    execute(
        'UPDATE CONCIERTO_PROGRAMA SET orden=%s, audio_ref_id=%s, notas=%s WHERE programa_id=%s',
        (data.get('orden'), data.get('audio_ref_id'), data.get('notas'), programa_id)
    )
    return jsonify({'ok': True})

@conciertos_bp.route('/programa/<int:programa_id>', methods=['DELETE'])
@editor_required
def delete_programa(programa_id):
    execute('DELETE FROM CONCIERTO_PROGRAMA WHERE programa_id = %s', (programa_id,))
    return jsonify({'ok': True})
