import os

class Config:
    # ── Base de datos ──────────────────────────────────────
    # Cambia MYSQL_PASSWORD por la contraseña que pusiste al crear el usuario tutb_user
    MYSQL_HOST     = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT     = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER     = os.environ.get('MYSQL_USER', 'tutb_user')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'tutb_pwd')
    MYSQL_DB       = os.environ.get('MYSQL_DB', 'tutb')

    # ── JWT ────────────────────────────────────────────────
    # Cambia JWT_SECRET_KEY por una cadena larga y aleatoria (mínimo 32 caracteres)
    # Puedes generar una con: python3 -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY   = os.environ.get('JWT_SECRET_KEY', 'CAMBIA_ESTA_CLAVE_SECRETA')
    JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', 8))

    # ── Almacenamiento de ficheros ─────────────────────────
    # Ruta absoluta donde se guardan las partituras y grabaciones
    # En producción cámbiala por la ruta real, p.ej. /home/inigoazkue/TUTB/media
    MEDIA_ROOT = os.environ.get('MEDIA_ROOT', os.path.expanduser('~/TUTB/media'))

    # ── Subida de ficheros (2 GB máximo) ───────────────────
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024
