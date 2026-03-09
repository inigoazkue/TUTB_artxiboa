import os
from flask import Blueprint, current_app, send_file, jsonify, request, Response
from db import query
from utils.auth import get_current_user

media_bp = Blueprint('media', __name__)

def get_user_role():
    user = get_current_user()
    return user['role'] if user else 'guest'

def _is_registered(rel_path):
    """Comprueba que el fichero está registrado en alguna tabla de la BD."""
    # Ficheros de partituras/soportes
    if query('SELECT soporte_id FROM SOPORTE WHERE file_path = %s', (rel_path,), fetchone=True):
        return True
    # Ficheros de conciertos (grabaciones, kartela, esku-programa)
    if query(
        '''SELECT concierto_id FROM CONCIERTO
           WHERE grab_audio_path = %s OR grab_video_path = %s
              OR kartela_path    = %s OR esku_programa_path = %s''',
        (rel_path, rel_path, rel_path, rel_path), fetchone=True
    ):
        return True
    return False

@media_bp.route('/<path:rel_path>')
def serve_media(rel_path):
    """
    Sirve ficheros desde MEDIA_ROOT.
    El fichero debe estar registrado en SOPORTE o en CONCIERTO.
    """
    media_root = current_app.config['MEDIA_ROOT']
    abs_path   = os.path.join(media_root, rel_path)

    if not _is_registered(rel_path):
        return jsonify({'error': 'Fichero no registrado'}), 404

    if not os.path.exists(abs_path):
        return jsonify({'error': 'Fichero no encontrado en disco'}), 404

    # Streaming para audio y video (soporta range requests)
    ext = rel_path.rsplit('.', 1)[-1].lower()
    stream_types = {'mp3', 'wav', 'mp4', 'ogg', 'webm', 'mov', 'flac', 'm4a', 'aac'}

    if ext in stream_types:
        return _stream_file(abs_path, ext)

    # PDF e imágenes: inline; el resto: descarga
    inline = ext in {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp'}
    return send_file(abs_path, as_attachment=not inline)

def _stream_file(path, ext):
    """Streaming con soporte de Range para reproductores HTML5."""
    mime_map = {
        'mp3': 'audio/mpeg', 'wav': 'audio/wav',
        'mp4': 'video/mp4',  'ogg': 'audio/ogg',
        'webm': 'video/webm', 'mov': 'video/quicktime',
        'flac': 'audio/flac', 'm4a': 'audio/mp4', 'aac': 'audio/aac',
    }
    mime      = mime_map.get(ext, 'application/octet-stream')
    size      = os.path.getsize(path)
    range_hdr = request.headers.get('Range', None)

    if range_hdr:
        byte1, byte2 = 0, None
        m = range_hdr.replace('bytes=', '').split('-')
        byte1 = int(m[0])
        byte2 = int(m[1]) if m[1] else size - 1

        length = byte2 - byte1 + 1
        with open(path, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)

        rv = Response(data, 206, mimetype=mime, direct_passthrough=True)
        rv.headers['Content-Range']  = f'bytes {byte1}-{byte2}/{size}'
        rv.headers['Accept-Ranges']  = 'bytes'
        rv.headers['Content-Length'] = str(length)
        return rv

    return send_file(path, mimetype=mime)
