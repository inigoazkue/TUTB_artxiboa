from flask import Blueprint, request, jsonify, send_file
from db import query, execute
from utils.auth import editor_required, admin_required
import os, zipfile, tempfile
from config import Config

copias_bp = Blueprint('copias', __name__)

@copias_bp.route('', methods=['POST'])
@editor_required
def create_copia():
    data = request.get_json()
    cid = execute(
        '''INSERT INTO COPIA (arreglo_id, tipo_copia_id, concierto_id, notas)
           VALUES (%s, %s, %s, %s)''',
        (data.get('arreglo_id'), data.get('tipo_copia_id'),
         data.get('concierto_id'), data.get('notas'))
    )
    return jsonify({'copia_id': cid}), 201

@copias_bp.route('/<int:copia_id>', methods=['PUT'])
@editor_required
def update_copia(copia_id):
    data = request.get_json()
    execute(
        '''UPDATE COPIA SET tipo_copia_id=%s, concierto_id=%s, notas=%s WHERE copia_id=%s''',
        (data.get('tipo_copia_id'), data.get('concierto_id'),
         data.get('notas'), copia_id)
    )
    return jsonify({'ok': True})

@copias_bp.route('/<int:copia_id>', methods=['DELETE'])
@admin_required
def delete_copia(copia_id):
    execute('DELETE FROM COPIA WHERE copia_id = %s', (copia_id,))
    return jsonify({'ok': True})

@copias_bp.route('/<int:copia_id>/conciertos', methods=['GET'])
def conciertos_de_copia(copia_id):
    rows = query(
        '''SELECT c.concierto_id, c.nombre, c.fecha, c.venue, cp.orden, cp.notas
           FROM CONCIERTO_PROGRAMA cp
           JOIN CONCIERTO c ON c.concierto_id = cp.concierto_id
           WHERE cp.copia_id = %s ORDER BY c.fecha DESC''',
        (copia_id,)
    )
    return jsonify(rows)

@copias_bp.route('/arreglo/<int:arreglo_id>/pdf-zip', methods=['GET'])
def pdf_zip(arreglo_id):
    """Descarga un ZIP con todos los PDFs del arreglo."""
    soportes = query(
        '''SELECT s.file_path, s.soporte_id,
                  COALESCE(i.nombre, tc.nombre, 'kopia') AS label,
                  cp.copia_id
           FROM COPIA cp
           LEFT JOIN SOPORTE      s  ON s.copia_id        = cp.copia_id
           LEFT JOIN TIPO_SOPORTE ts ON ts.tipo_soporte_id = s.tipo_soporte_id
           LEFT JOIN INSTRUMENTO  i  ON i.instrumento_id  = s.instrumento_id
           LEFT JOIN TIPO_COPIA   tc ON tc.tipo_copia_id  = cp.tipo_copia_id
           WHERE cp.arreglo_id = %s
             AND s.file_path IS NOT NULL
             AND LOWER(s.file_path) LIKE %s
           ORDER BY cp.copia_id, s.soporte_id''',
        (arreglo_id, '%.pdf')
    )

    if not soportes:
        return jsonify({'error': 'Ez dago PDF-rik'}), 404

    # Get obra title for zip name
    meta = query(
        '''SELECT o.title, ar.anyo
           FROM ARREGLO ar
           JOIN `VERSION` v ON v.version_id = ar.version_id
           JOIN OBRA o ON o.obra_id = v.obra_id
           WHERE ar.arreglo_id = %s''',
        (arreglo_id,)
    )
    zip_name = f"{meta[0]['title'] if meta else 'arreglo'}_{arreglo_id}.zip"
    zip_name = "".join(c if c.isalnum() or c in '-_. ' else '_' for c in zip_name)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        seen = {}
        for s in soportes:
            if not s['file_path']:
                continue
            full_path = os.path.join(Config.MEDIA_ROOT, s['file_path'])
            if not os.path.exists(full_path):
                continue
            base = s['label']
            if base in seen:
                seen[base] += 1
                arcname = f"{base}_{seen[base]}.pdf"
            else:
                seen[base] = 0
                arcname = f"{base}.pdf"
            zf.write(full_path, arcname)

    if os.path.getsize(tmp.name) < 100:
        os.unlink(tmp.name)
        return jsonify({'error': 'Ez dago fitxategirik zerbitzarian'}), 404

    return send_file(
        tmp.name,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_name
    )
