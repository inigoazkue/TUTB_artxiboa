import mysql.connector
from flask import g, current_app

def init_db(app):
    """Registra teardown para cerrar conexión al final de cada request."""
    @app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

def get_db():
    """Devuelve la conexión activa o abre una nueva."""
    if 'db' not in g:
        cfg = current_app.config
        g.db = mysql.connector.connect(
            host     = cfg['MYSQL_HOST'],
            port     = cfg['MYSQL_PORT'],
            user     = cfg['MYSQL_USER'],
            password = cfg['MYSQL_PASSWORD'],
            database = cfg['MYSQL_DB'],
            charset  = 'utf8mb4'
        )
    return g.db

def query(sql, params=None, fetchone=False):
    """Ejecuta una SELECT y devuelve lista de dicts (o un dict si fetchone)."""
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(sql, params or ())
    result = cur.fetchone() if fetchone else cur.fetchall()
    cur.close()
    return result

def execute(sql, params=None):
    """Ejecuta INSERT/UPDATE/DELETE y devuelve lastrowid."""
    db  = get_db()
    cur = db.cursor()
    cur.execute(sql, params or ())
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
