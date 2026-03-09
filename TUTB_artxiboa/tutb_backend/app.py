from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
from db import init_db
import os

from routes.auth       import auth_bp
from routes.obras      import obras_bp
from routes.versiones  import versiones_bp
from routes.arreglos   import arreglos_bp
from routes.copias     import copias_bp
from routes.soportes   import soportes_bp
from routes.conciertos import conciertos_bp
from routes.lookups    import lookups_bp
from routes.media      import media_bp
from routes.backup     import backup_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, supports_credentials=True, origins='*')

    init_db(app)

    app.register_blueprint(auth_bp,       url_prefix='/api/auth')
    app.register_blueprint(obras_bp,      url_prefix='/api/obras')
    app.register_blueprint(versiones_bp,  url_prefix='/api/versiones')
    app.register_blueprint(arreglos_bp,   url_prefix='/api/arreglos')
    app.register_blueprint(copias_bp,     url_prefix='/api/copias')
    app.register_blueprint(soportes_bp,   url_prefix='/api/soportes')
    app.register_blueprint(conciertos_bp, url_prefix='/api/conciertos')
    app.register_blueprint(lookups_bp,    url_prefix='/api/lookups')
    app.register_blueprint(media_bp,      url_prefix='/api/media')
    app.register_blueprint(backup_bp,     url_prefix='/api/backup')

    # Global error handler — always return JSON with CORS headers
    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        app.logger.error(traceback.format_exc())
        code = getattr(e, 'code', 500)
        resp = jsonify({'error': str(e)})
        resp.status_code = code
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        return resp

    # Frontend estático
    static_dir = app.config.get('STATIC_DIR', '/var/www/tutb')

    @app.route('/')
    def frontend():
        return send_from_directory(static_dir, 'tutb_frontend.html')

    @app.route('/mobile')
    def mobile():
        return send_from_directory(static_dir, 'tutb_mobile.html')

    return app

# Variable global para gunicorn (gunicorn app:app)
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
