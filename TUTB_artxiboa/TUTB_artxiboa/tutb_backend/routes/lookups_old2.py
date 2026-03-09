from flask import Blueprint, request, jsonify
from db import query, execute
from utils.auth import admin_required

lookups_bp = Blueprint('lookups', __name__)

TABLES = {
    'idiomas':       ('IDIOMA',          'idioma_id'),
    'compositores':  ('COMPOSITOR',      'compositor_id'),
    'arreglistas':   ('ARREGLISTA',      'arreglista_id'),
    'tonalidades':   ('TONALIDAD',       'tonalidad_id'),
    'generos':       ('GENERO',          'genero_id'),
    'tipos-copia':   ('TIPO_COPIA',      'tipo_copia_id'),
    'tipos-soporte': ('TIPO_SOPORTE',    'tipo_soporte_id'),
    'ubicaciones':   ('UBICACION_FISICA','ubicacion_id'),
    'instrumentos':  ('INSTRUMENTO',     'instrumento_id'),
    'contexts':      ('CONTEXT',         'context_id'),
}

@lookups_bp.route('/<string:lookup>', methods=['GET'])
def get_lookup(lookup):
    if lookup not in TABLES:
        return jsonify({'error': 'Catálogo no encontrado'}), 404
    table, _ = TABLES[lookup]
    return jsonify(query(f'SELECT * FROM {table} ORDER BY nombre'))

@lookups_bp.route('/<string:lookup>', methods=['POST'])
@admin_required
def create_lookup(lookup):
    if lookup not in TABLES:
        return jsonify({'error': 'Catálogo no encontrado'}), 404
    table, pk = TABLES[lookup]
    data = request.get_json()

    if lookup == 'tipos-soporte':
        new_id = execute(
            f'INSERT INTO {table} (nombre, es_digital) VALUES (%s, %s)',
            (data.get('nombre'), int(data.get('es_digital', 1)))
        )
    elif lookup == 'idiomas':
        new_id = execute(
            f'INSERT INTO {table} (nombre, codigo) VALUES (%s, %s)',
            (data.get('nombre'), data.get('codigo'))
        )
    else:
        new_id = execute(
            f'INSERT INTO {table} (nombre) VALUES (%s)',
            (data.get('nombre'),)
        )
    return jsonify({pk: new_id}), 201

@lookups_bp.route('/<string:lookup>/<int:item_id>', methods=['PUT'])
@admin_required
def update_lookup(lookup, item_id):
    if lookup not in TABLES:
        return jsonify({'error': 'Catálogo no encontrado'}), 404
    table, pk = TABLES[lookup]
    data = request.get_json()
    execute(
        f'UPDATE {table} SET nombre = %s WHERE {pk} = %s',
        (data.get('nombre'), item_id)
    )
    return jsonify({'ok': True})

@lookups_bp.route('/<string:lookup>/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_lookup(lookup, item_id):
    if lookup not in TABLES:
        return jsonify({'error': 'Catálogo no encontrado'}), 404
    table, pk = TABLES[lookup]
    if lookup == 'instrumentos':
        row = query(f'SELECT nombre FROM {table} WHERE {pk} = %s', (item_id,), fetchone=True)
        if row and row['nombre'] == 'Gidoia':
            return jsonify({'error': 'Ezin da ezabatu'}), 403
    execute(f'DELETE FROM {table} WHERE {pk} = %s', (item_id,))
    return jsonify({'ok': True})
