from flask import Blueprint, request, jsonify
from db import query, execute
from utils.auth import login_required, editor_required, admin_required

obras_bp = Blueprint('obras', __name__)

@obras_bp.route('', methods=['GET'])
def list_obras():
    search = request.args.get('q', '').strip()
    if search:
        rows = query(
            '''SELECT DISTINCT o.obra_id, o.title
               FROM OBRA o
               LEFT JOIN OBRA_ALT_TITULO a ON a.obra_id = o.obra_id
               WHERE o.title LIKE %s OR a.title LIKE %s
               ORDER BY o.title''',
            (f'%{search}%', f'%{search}%')
        )
    else:
        rows = query('SELECT obra_id, title FROM OBRA ORDER BY title')
    return jsonify(rows)

@obras_bp.route('/<int:obra_id>', methods=['GET'])
def get_obra(obra_id):
    obra = query('SELECT * FROM OBRA WHERE obra_id = %s', (obra_id,), fetchone=True)
    if not obra:
        return jsonify({'error': 'Obra no encontrada'}), 404
    obra['alt_titles'] = query(
        '''SELECT a.alt_titulo_id, a.title, i.nombre AS idioma
           FROM OBRA_ALT_TITULO a
           LEFT JOIN IDIOMA i ON i.idioma_id = a.idioma_id
           WHERE a.obra_id = %s''',
        (obra_id,)
    )
    return jsonify(obra)

@obras_bp.route('/<int:obra_id>/tree', methods=['GET'])
def get_obra_tree(obra_id):
    """Devuelve el árbol completo: Obra > Versiones > Arreglos > Copias > Soportes."""
    obra = query('SELECT * FROM OBRA WHERE obra_id = %s', (obra_id,), fetchone=True)
    if not obra:
        return jsonify({'error': 'Obra no encontrada'}), 404

    obra['alt_titles'] = query(
        '''SELECT a.title, i.nombre AS idioma
           FROM OBRA_ALT_TITULO a
           LEFT JOIN IDIOMA i ON i.idioma_id = a.idioma_id
           WHERE a.obra_id = %s''', (obra_id,)
    )

    versiones = query(
        '''SELECT v.*, c.nombre AS compositor_nombre
           FROM `VERSION` v
           LEFT JOIN COMPOSITOR c ON c.compositor_id = v.compositor_id
           WHERE v.obra_id = %s ORDER BY v.version_id''', (obra_id,)
    )

    for v in versiones:
        arreglos = query(
            '''SELECT ar.*, a.nombre AS arreglista_nombre,
                      t.nombre AS tonalidad_nombre,
                      g.nombre AS genero_nombre,
                      cx.nombre AS context_nombre,
                      CAST(ar.duracion AS CHAR) AS duracion
               FROM ARREGLO ar
               LEFT JOIN ARREGLISTA a ON a.arreglista_id = ar.arreglista_id
               LEFT JOIN TONALIDAD  t ON t.tonalidad_id  = ar.tonalidad_id
               LEFT JOIN GENERO     g ON g.genero_id     = ar.genero_id
               LEFT JOIN CONTEXT    cx ON cx.context_id  = ar.context_id
               WHERE ar.version_id = %s ORDER BY ar.arreglo_id''',
            (v['version_id'],)
        )
        for ar in arreglos:
            ar['instrumentos'] = query(
                '''SELECT i.instrumento_id, i.nombre
                   FROM ARREGLO_INSTRUMENTO ai
                   JOIN INSTRUMENTO i ON i.instrumento_id = ai.instrumento_id
                   WHERE ai.arreglo_id = %s ORDER BY i.nombre''',
                (ar['arreglo_id'],)
            )
            ar['parejas'] = query(
                '''SELECT ar2.arreglo_id, ar2.anyo,
                          o.title AS obra_title,
                          a.nombre AS arreglista_nombre,
                          g.nombre AS genero_nombre
                   FROM ARREGLO_PAREJA ap
                   JOIN ARREGLO ar2 ON ar2.arreglo_id = IF(ap.arreglo_id_a=%s, ap.arreglo_id_b, ap.arreglo_id_a)
                   JOIN `VERSION` v  ON v.version_id  = ar2.version_id
                   JOIN OBRA o        ON o.obra_id     = v.obra_id
                   LEFT JOIN ARREGLISTA a ON a.arreglista_id = ar2.arreglista_id
                   LEFT JOIN GENERO     g ON g.genero_id     = ar2.genero_id
                   WHERE ap.arreglo_id_a=%s OR ap.arreglo_id_b=%s''',
                (ar['arreglo_id'], ar['arreglo_id'], ar['arreglo_id'])
            )
        for ar in arreglos:
            copias = query(
                '''SELECT cp.*, tc.nombre AS tipo_copia_nombre,
                          con.nombre AS concierto_nombre
                   FROM COPIA cp
                   LEFT JOIN TIPO_COPIA tc  ON tc.tipo_copia_id  = cp.tipo_copia_id
                   LEFT JOIN CONCIERTO con  ON con.concierto_id   = cp.concierto_id
                   WHERE cp.arreglo_id = %s ORDER BY cp.copia_id''',
                (ar['arreglo_id'],)
            )
            for cp in copias:
                cp['soportes'] = query(
                    '''SELECT s.*, ts.nombre AS tipo_soporte_nombre,
                              ts.es_digital,
                              uf.nombre AS ubicacion_nombre,
                              u.username AS creado_por,
                              i.nombre AS instrumento_nombre
                       FROM SOPORTE s
                       LEFT JOIN TIPO_SOPORTE    ts ON ts.tipo_soporte_id = s.tipo_soporte_id
                       LEFT JOIN UBICACION_FISICA uf ON uf.ubicacion_id   = s.ubicacion_id
                       LEFT JOIN USUARIO           u  ON u.usuario_id      = s.created_by
                       LEFT JOIN INSTRUMENTO       i  ON i.instrumento_id  = s.instrumento_id
                       WHERE s.copia_id = %s ORDER BY s.soporte_id''',
                    (cp['copia_id'],)
                )
            ar['copias'] = copias
        v['arreglos'] = arreglos

    obra['versiones'] = versiones
    return jsonify(obra)

@obras_bp.route('', methods=['POST'])
@editor_required
def create_obra():
    data  = request.get_json()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'El título es obligatorio'}), 400
    obra_id = execute('INSERT INTO OBRA (title) VALUES (%s)', (title,))

    for alt in data.get('alt_titles', []):
        execute(
            'INSERT INTO OBRA_ALT_TITULO (obra_id, title, idioma_id) VALUES (%s, %s, %s)',
            (obra_id, alt.get('title'), alt.get('idioma_id'))
        )
    return jsonify({'obra_id': obra_id}), 201

@obras_bp.route('/<int:obra_id>', methods=['PUT'])
@editor_required
def update_obra(obra_id):
    data  = request.get_json()
    title = data.get('title', '').strip()
    if title:
        execute('UPDATE OBRA SET title = %s WHERE obra_id = %s', (title, obra_id))
    return jsonify({'ok': True})

@obras_bp.route('/<int:obra_id>', methods=['DELETE'])
@admin_required
def delete_obra(obra_id):
    execute('DELETE FROM OBRA WHERE obra_id = %s', (obra_id,))
    return jsonify({'ok': True})

# ── Títulos alternativos ───────────────────────────────────────────────────

@obras_bp.route('/<int:obra_id>/alt-titulos', methods=['POST'])
@editor_required
def add_alt_titulo(obra_id):
    data = request.get_json()
    execute(
        'INSERT INTO OBRA_ALT_TITULO (obra_id, title, idioma_id) VALUES (%s, %s, %s)',
        (obra_id, data.get('title'), data.get('idioma_id'))
    )
    return jsonify({'ok': True}), 201

@obras_bp.route('/alt-titulos/<int:alt_id>', methods=['DELETE'])
@editor_required
def delete_alt_titulo(alt_id):
    execute('DELETE FROM OBRA_ALT_TITULO WHERE alt_titulo_id = %s', (alt_id,))
    return jsonify({'ok': True})
