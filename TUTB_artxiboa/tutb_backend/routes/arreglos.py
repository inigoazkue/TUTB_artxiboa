from flask import Blueprint, request, jsonify
from db import query, execute
from utils.auth import editor_required, admin_required

arreglos_bp = Blueprint('arreglos', __name__)

def _sync_instrumentos(arreglo_id, instrumento_ids):
    """Actualiza los instrumentos de un arreglo (borra y reinserta)."""
    execute('DELETE FROM ARREGLO_INSTRUMENTO WHERE arreglo_id = %s', (arreglo_id,))
    for iid in instrumento_ids:
        if iid:
            execute(
                'INSERT IGNORE INTO ARREGLO_INSTRUMENTO (arreglo_id, instrumento_id) VALUES (%s, %s)',
                (arreglo_id, iid)
            )

def _get_instrumentos(arreglo_id):
    rows = query(
        '''SELECT i.instrumento_id, i.nombre
           FROM ARREGLO_INSTRUMENTO ai
           JOIN INSTRUMENTO i ON i.instrumento_id = ai.instrumento_id
           WHERE ai.arreglo_id = %s ORDER BY i.nombre''',
        (arreglo_id,)
    )
    return rows

def _get_parejas(arreglo_id):
    """Devuelve los arreglos enlazados como pareja."""
    return query(
        '''SELECT ar2.arreglo_id, ar2.anyo,
                  o.title AS obra_title,
                  a.nombre AS arreglista_nombre,
                  g.nombre AS genero_nombre,
                  t.nombre AS tonalidad_nombre
           FROM ARREGLO_PAREJA ap
           JOIN ARREGLO ar2 ON ar2.arreglo_id = IF(ap.arreglo_id_a=%s, ap.arreglo_id_b, ap.arreglo_id_a)
           JOIN `VERSION` v  ON v.version_id   = ar2.version_id
           JOIN OBRA o        ON o.obra_id      = v.obra_id
           LEFT JOIN ARREGLISTA a ON a.arreglista_id = ar2.arreglista_id
           LEFT JOIN GENERO     g ON g.genero_id     = ar2.genero_id
           LEFT JOIN TONALIDAD  t ON t.tonalidad_id  = ar2.tonalidad_id
           WHERE ap.arreglo_id_a=%s OR ap.arreglo_id_b=%s''',
        (arreglo_id, arreglo_id, arreglo_id)
    )

def _sync_parejas(arreglo_id, pareja_ids):
    """Reemplaza todas las parejas de un arreglo."""
    execute('DELETE FROM ARREGLO_PAREJA WHERE arreglo_id_a=%s OR arreglo_id_b=%s',
            (arreglo_id, arreglo_id))
    for pid in pareja_ids:
        pid = int(pid)
        if pid == arreglo_id:
            continue
        a, b = (arreglo_id, pid) if arreglo_id < pid else (pid, arreglo_id)
        execute('INSERT IGNORE INTO ARREGLO_PAREJA (arreglo_id_a, arreglo_id_b) VALUES (%s,%s)', (a, b))

@arreglos_bp.route('/<int:arreglo_id>/parejas', methods=['GET'])
def get_parejas(arreglo_id):
    return jsonify(_get_parejas(arreglo_id))

@arreglos_bp.route('/<int:arreglo_id>/parejas', methods=['PUT'])
@editor_required
def set_parejas(arreglo_id):
    data = request.get_json()
    _sync_parejas(arreglo_id, data.get('pareja_ids', []))
    return jsonify({'ok': True})

@arreglos_bp.route('/all-for-select', methods=['GET'])
def all_for_select():
    """Lista ligera de todos los arreglos para el selector de parejas."""
    rows = query(
        '''SELECT ar.arreglo_id, ar.anyo,
                  o.title AS obra_title,
                  a.nombre AS arreglista_nombre,
                  g.nombre AS genero_nombre
           FROM ARREGLO ar
           JOIN `VERSION` v  ON v.version_id   = ar.version_id
           JOIN OBRA o        ON o.obra_id      = v.obra_id
           LEFT JOIN ARREGLISTA a ON a.arreglista_id = ar.arreglista_id
           LEFT JOIN GENERO     g ON g.genero_id     = ar.genero_id
           ORDER BY o.title, ar.arreglo_id'''
    )
    return jsonify(rows)

@arreglos_bp.route('', methods=['POST'])
@editor_required
def create_arreglo():
    data = request.get_json()
    aid = execute(
        '''INSERT INTO ARREGLO
           (version_id, arreglista_id, tonalidad_id, genero_id, context_id, anyo, duracion)
           VALUES (%s, %s, %s, %s, %s, %s, %s)''',
        (data.get('version_id'), data.get('arreglista_id'), data.get('tonalidad_id'),
         data.get('genero_id'), data.get('context_id'), data.get('anyo'), data.get('duracion'))
    )
    _sync_instrumentos(aid, data.get('instrumento_ids', []))
    return jsonify({'arreglo_id': aid}), 201

@arreglos_bp.route('/<int:arreglo_id>', methods=['PUT'])
@editor_required
def update_arreglo(arreglo_id):
    data = request.get_json()
    execute(
        '''UPDATE ARREGLO SET arreglista_id=%s, tonalidad_id=%s, genero_id=%s, context_id=%s,
           anyo=%s, duracion=%s WHERE arreglo_id=%s''',
        (data.get('arreglista_id'), data.get('tonalidad_id'), data.get('genero_id'),
         data.get('context_id'), data.get('anyo'), data.get('duracion'), arreglo_id)
    )
    if 'instrumento_ids' in data:
        _sync_instrumentos(arreglo_id, data['instrumento_ids'])
    return jsonify({'ok': True})

@arreglos_bp.route('/<int:arreglo_id>', methods=['DELETE'])
@admin_required
def delete_arreglo(arreglo_id):
    execute('DELETE FROM ARREGLO WHERE arreglo_id = %s', (arreglo_id,))
    return jsonify({'ok': True})

@arreglos_bp.route('/<int:arreglo_id>/instrumentos', methods=['GET'])
def get_instrumentos(arreglo_id):
    return jsonify(_get_instrumentos(arreglo_id))

@arreglos_bp.route('/search', methods=['GET'])
def search_arreglos():
    args = request.args
    conditions = []
    params = []

    if args.get('q'):
        conditions.append('(o.title LIKE %s OR oat.title LIKE %s)')
        params += [f"%{args['q']}%", f"%{args['q']}%"]
    if args.get('genero_id'):
        conditions.append('ar.genero_id = %s')
        params.append(args['genero_id'])
    if args.get('tonalidad_id'):
        conditions.append('ar.tonalidad_id = %s')
        params.append(args['tonalidad_id'])
    if args.get('arreglista_id'):
        conditions.append('ar.arreglista_id = %s')
        params.append(args['arreglista_id'])
    if args.get('compositor_id'):
        conditions.append('v.compositor_id = %s')
        params.append(args['compositor_id'])
    if args.get('instrumento_id'):
        conditions.append('EXISTS (SELECT 1 FROM ARREGLO_INSTRUMENTO ai WHERE ai.arreglo_id=ar.arreglo_id AND ai.instrumento_id=%s)')
        params.append(args['instrumento_id'])
    if args.get('context_id'):
        conditions.append('ar.context_id = %s')
        params.append(args['context_id'])
    if args.get('ubicacion_id'):
        conditions.append('s.ubicacion_id = %s')
        params.append(args['ubicacion_id'])
    if args.get('anyo_min'):
        conditions.append('ar.anyo >= %s')
        params.append(args['anyo_min'])
    if args.get('anyo_max'):
        conditions.append('ar.anyo <= %s')
        params.append(args['anyo_max'])
    if args.get('dur_min'):
        conditions.append('ar.duracion >= %s')
        params.append(args['dur_min'])
    if args.get('dur_max'):
        conditions.append('ar.duracion <= %s')
        params.append(args['dur_max'])

    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    rows = query(f'''
        SELECT DISTINCT
               o.obra_id, o.title AS obra_title,
               ar.arreglo_id, ar.anyo,
               CAST(ar.duracion AS CHAR) AS duracion,
               v.version_id, v.description AS version_desc,
               c.nombre AS compositor_nombre,
               a.nombre AS arreglista_nombre,
               t.nombre AS tonalidad_nombre,
               g.nombre AS genero_nombre,
               cx.nombre AS context_nombre
        FROM ARREGLO ar
        LEFT JOIN `VERSION`        v   ON v.version_id      = ar.version_id
        LEFT JOIN OBRA             o   ON o.obra_id         = v.obra_id
        LEFT JOIN OBRA_ALT_TITULO  oat ON oat.obra_id       = o.obra_id
        LEFT JOIN COMPOSITOR       c   ON c.compositor_id   = v.compositor_id
        LEFT JOIN ARREGLISTA       a   ON a.arreglista_id   = ar.arreglista_id
        LEFT JOIN TONALIDAD        t   ON t.tonalidad_id    = ar.tonalidad_id
        LEFT JOIN GENERO           g   ON g.genero_id       = ar.genero_id
        LEFT JOIN CONTEXT          cx  ON cx.context_id     = ar.context_id
        LEFT JOIN COPIA            cp  ON cp.arreglo_id     = ar.arreglo_id
        LEFT JOIN SOPORTE          s   ON s.copia_id        = cp.copia_id
        {where}
        ORDER BY o.title, ar.arreglo_id
        LIMIT 200
    ''', params if params else None)

    # Instrumentos por arreglo
    arreglo_ids = list({r['arreglo_id'] for r in rows})
    instr_map = {}
    if arreglo_ids:
        placeholders = ','.join(['%s'] * len(arreglo_ids))
        instrs = query(f'''
            SELECT ai.arreglo_id, i.instrumento_id, i.nombre
            FROM ARREGLO_INSTRUMENTO ai
            JOIN INSTRUMENTO i ON i.instrumento_id = ai.instrumento_id
            WHERE ai.arreglo_id IN ({placeholders})
            ORDER BY i.nombre
        ''', arreglo_ids)
        for i in instrs:
            instr_map.setdefault(i['arreglo_id'], []).append(i['nombre'])

    # Copias y soportes por arreglo
    copias_map = {}
    if arreglo_ids:
        placeholders = ','.join(['%s'] * len(arreglo_ids))
        copias = query(f'''
            SELECT cp.copia_id, cp.arreglo_id, cp.notas,
                   tc.nombre AS tipo_copia_nombre,
                   s.soporte_id, s.file_path, s.url_externa,
                   s.instrumento_id,
                   i.nombre AS instrumento_nombre,
                   ts.nombre AS tipo_soporte_nombre, ts.es_digital,
                   uf.nombre AS ubicacion_nombre
            FROM COPIA cp
            LEFT JOIN TIPO_COPIA       tc ON tc.tipo_copia_id    = cp.tipo_copia_id
            LEFT JOIN SOPORTE          s  ON s.copia_id          = cp.copia_id
            LEFT JOIN INSTRUMENTO      i  ON i.instrumento_id    = s.instrumento_id
            LEFT JOIN TIPO_SOPORTE     ts ON ts.tipo_soporte_id  = s.tipo_soporte_id
            LEFT JOIN UBICACION_FISICA uf ON uf.ubicacion_id     = s.ubicacion_id
            WHERE cp.arreglo_id IN ({placeholders})
            ORDER BY cp.copia_id, s.soporte_id
        ''', arreglo_ids)

        for cp in copias:
            aid = cp['arreglo_id']
            cid = cp['copia_id']
            if aid not in copias_map:
                copias_map[aid] = {}
            if cid not in copias_map[aid]:
                copias_map[aid][cid] = {
                    'copia_id':          cid,
                    'tipo_copia_nombre': cp['tipo_copia_nombre'],
                    'notas':             cp['notas'],
                    'soportes': []
                }
            if cp['soporte_id']:
                copias_map[aid][cid]['soportes'].append({
                    'soporte_id':          cp['soporte_id'],
                    'file_path':           cp['file_path'],
                    'url_externa':         cp['url_externa'],
                    'tipo_soporte_nombre': cp['tipo_soporte_nombre'],
                    'es_digital':          cp['es_digital'],
                    'ubicacion_nombre':    cp['ubicacion_nombre'],
                    'instrumento_id':      cp['instrumento_id'],
                    'instrumento_nombre':  cp['instrumento_nombre'],
                })

    for r in rows:
        aid = r['arreglo_id']
        r['instrumentos'] = instr_map.get(aid, [])
        r['copias']       = list(copias_map.get(aid, {}).values())
        r['parejas']      = []

    # Parejas por arreglo
    if arreglo_ids:
        placeholders = ','.join(['%s'] * len(arreglo_ids))
        parejas_rows = query(f'''
            SELECT ap.arreglo_id_a, ap.arreglo_id_b,
                   ar2.arreglo_id AS pareja_id, ar2.anyo,
                   o.title AS obra_title,
                   a.nombre AS arreglista_nombre,
                   g.nombre AS genero_nombre
            FROM ARREGLO_PAREJA ap
            JOIN ARREGLO ar2 ON ar2.arreglo_id IN (ap.arreglo_id_a, ap.arreglo_id_b)
            JOIN `VERSION` v  ON v.version_id   = ar2.version_id
            JOIN OBRA o        ON o.obra_id      = v.obra_id
            LEFT JOIN ARREGLISTA a ON a.arreglista_id = ar2.arreglista_id
            LEFT JOIN GENERO     g ON g.genero_id     = ar2.genero_id
            WHERE (ap.arreglo_id_a IN ({placeholders}) OR ap.arreglo_id_b IN ({placeholders}))
        ''', arreglo_ids + arreglo_ids)
        # Map each arreglo to its partners
        pareja_map = {}
        for p in parejas_rows:
            for aid_key in [p['arreglo_id_a'], p['arreglo_id_b']]:
                if p['pareja_id'] != aid_key:
                    pareja_map.setdefault(aid_key, []).append({
                        'arreglo_id':       p['pareja_id'],
                        'obra_title':       p['obra_title'],
                        'arreglista_nombre': p['arreglista_nombre'],
                        'genero_nombre':    p['genero_nombre'],
                    })
        for r in rows:
            r['parejas'] = pareja_map.get(r['arreglo_id'], [])

    return jsonify(rows)

@arreglos_bp.route('/by-genero/<int:genero_id>', methods=['GET'])
def by_genero(genero_id):
    rows = query(
        '''SELECT ar.arreglo_id, ar.anyo,
                  t.nombre AS tonalidad, g.nombre AS genero,
                  a.nombre AS arreglista,
                  v.description AS version_desc,
                  o.title AS obra_title, o.obra_id
           FROM ARREGLO ar
           LEFT JOIN `VERSION`    v ON v.version_id    = ar.version_id
           LEFT JOIN OBRA         o ON o.obra_id       = v.obra_id
           LEFT JOIN ARREGLISTA   a ON a.arreglista_id = ar.arreglista_id
           LEFT JOIN TONALIDAD    t ON t.tonalidad_id  = ar.tonalidad_id
           LEFT JOIN GENERO       g ON g.genero_id     = ar.genero_id
           WHERE ar.genero_id = %s ORDER BY o.title''',
        (genero_id,)
    )
    return jsonify(rows)
