from flask import Blueprint, request, jsonify, current_app, Response
from utils.auth import admin_required
import subprocess, os, tempfile
from datetime import datetime

backup_bp = Blueprint('backup', __name__)

def _db_config():
    cfg = current_app.config
    return {
        'host':     cfg.get('MYSQL_HOST', 'localhost'),
        'port':     str(cfg.get('MYSQL_PORT', 3306)),
        'user':     cfg.get('MYSQL_USER', 'tutb_user'),
        'password': cfg.get('MYSQL_PASSWORD', ''),
        'db':       cfg.get('MYSQL_DB', 'tutb'),
    }

@backup_bp.route('/export', methods=['GET'])
@admin_required
def export_db():
    """Descarga un mysqldump completo (estructura + datos)."""
    c = _db_config()
    filename = f"tutb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

    env = os.environ.copy()
    env['MYSQL_PWD'] = c['password']

    try:
        result = subprocess.run(
            [
                'mysqldump',
                f"--host={c['host']}",
                f"--port={c['port']}",
                f"--user={c['user']}",
                '--single-transaction',
                '--routines',
                '--triggers',
                c['db'],
            ],
            capture_output=True,
            env=env,
            timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')
            return jsonify({'error': f'mysqldump huts egin du: {err}'}), 500

        sql = result.stdout

        return Response(
            sql,
            mimetype='application/sql',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(sql)),
            }
        )
    except FileNotFoundError:
        return jsonify({'error': 'mysqldump ez dago instalatuta zerbitzarian'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Denbora-muga gainditu da'}), 500


@backup_bp.route('/import', methods=['POST'])
@admin_required
def import_db():
    """Importa un fichero .sql subido por el usuario."""
    if 'file' not in request.files:
        return jsonify({'error': 'Fitxategirik ez'}), 400
    file = request.files['file']
    if not file.filename.endswith('.sql'):
        return jsonify({'error': 'Fitxategiak .sql izan behar du'}), 400

    c = _db_config()
    env = os.environ.copy()
    env['MYSQL_PWD'] = c['password']

    # Escribir el fichero a un temporal
    with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                'mysql',
                f"--host={c['host']}",
                f"--port={c['port']}",
                f"--user={c['user']}",
                c['db'],
            ],
            stdin=open(tmp_path, 'rb'),
            capture_output=True,
            env=env,
            timeout=300,
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')
            return jsonify({'error': f'Inportazioak huts egin du: {err}'}), 500

        return jsonify({'ok': True, 'message': 'Datu-basea berreskuratu da ✓'})
    except FileNotFoundError:
        return jsonify({'error': 'mysql ez dago instalatuta zerbitzarian'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Denbora-muga gainditu da'}), 500
    finally:
        os.unlink(tmp_path)
