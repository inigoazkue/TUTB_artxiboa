# TUTB — Txistularis Artxiboa · Guía de instalación

Sistema de gestión de partituras (MAM) para banda de txistularis.  
Backend: Python + Flask · Base de datos: MariaDB · Frontend: HTML estático

---

## Requisitos previos

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
    mariadb-server mariadb-client \
    git curl
```

> `mariadb-client` es imprescindible para la función de exportar/importar backups desde la interfaz web.

---

## 1. Estructura de ficheros del proyecto

```
/home/<usuario>/TUTB/
├── tutb_backend/
│   ├── app.py
│   ├── config.py
│   ├── db.py
│   ├── requirements.txt
│   ├── migrate_media.py
│   ├── set_admin_password.py
│   ├── version.json
│   ├── routes/
│   │   ├── auth.py
│   │   ├── obras.py
│   │   ├── versiones.py
│   │   ├── arreglos.py
│   │   ├── copias.py
│   │   ├── soportes.py
│   │   ├── conciertos.py
│   │   ├── lookups.py
│   │   ├── media.py
│   │   └── backup.py
│   └── utils/
│       └── auth.py
└── media/
    ├── obras/          ← organizados por obra/versión/arreglo/copia
    └── kontzertoak/    ← grabaciones y documentos de conciertos

/var/www/tutb/
├── tutb_frontend.html
└── (tutb_mobile.html — obsoleto, sustituido por diseño responsive)
```

### Descripción de cada fichero

#### Raíz del backend

| Fichero | Descripción |
|---------|-------------|
| `app.py` | Punto de entrada de la aplicación Flask. Crea la app, registra todos los blueprints y sirve los HTML estáticos en `/` y `/mobile`. Expone la variable global `app` para Gunicorn (`app:app`). |
| `config.py` | Configuración central: credenciales de BD, clave JWT, ruta de media (`MEDIA_ROOT`), tamaño máximo de subida (2 GB). Los valores se pueden sobreescribir con variables de entorno. |
| `db.py` | Gestión de la conexión a MariaDB. Funciones `get_db()`, `query()` (SELECT) y `execute()` (INSERT/UPDATE/DELETE). Usa `mysql-connector-python`. |
| `requirements.txt` | Dependencias Python: flask, flask-cors, mysql-connector-python, werkzeug, pyjwt, gunicorn. |
| `migrate_media.py` | Script de migración de ficheros de la estructura antigua (`copias/<id>/`) a la jerarquía nueva (`obras/<id>_<titulo>/v<vid>/a<aid>/c<cid>/`). Ejecutar con `--dry-run` primero. |
| `set_admin_password.py` | Utilidad para resetear la contraseña de un usuario admin directamente desde línea de comandos, sin necesidad de acceder a la BD manualmente. |

#### `routes/` — Blueprints de la API REST

| Fichero | Prefijo URL | Descripción |
|---------|-------------|-------------|
| `auth.py` | `/api/auth` | Login (devuelve JWT + usuario_id), `/me`, cambio de contraseña, CRUD completo de usuarios. Usa `werkzeug.security` para hashing. |
| `obras.py` | `/api/obras` | CRUD de obras musicales. Incluye `GET /obras/<id>/tree` que devuelve el árbol completo obra→versión→arreglo→copia→soporte. |
| `versiones.py` | `/api/versiones` | CRUD de versiones (una obra puede tener varias versiones con distintos compositores). |
| `arreglos.py` | `/api/arreglos` | CRUD de arreglos. Gestiona la tabla N:M de instrumentos (`ARREGLO_INSTRUMENTO`), las parejas de arreglos (`ARREGLO_PAREJA`) y el campo `context_id`. Endpoint `GET /arreglos/search` con filtros por género, tonalidad, arreglista, compositor, instrumento, ubicación, contexto, año y duración. |
| `copias.py` | `/api/copias` | CRUD de copias físicas/digitales de un arreglo. Incluye endpoint para descargar todas las copias PDF de un arreglo como ZIP. |
| `soportes.py` | `/api/soportes` | Subida de ficheros (`POST /soportes/upload/<copia_id>`) y creación de soportes con URL externa. Los ficheros se guardan en la jerarquía `media/obras/`. Borrado físico del fichero al eliminar un soporte. |
| `conciertos.py` | `/api/conciertos` | CRUD de conciertos y su programa. Subida de ficheros de concierto (grabación audio/vídeo, kartela, esku-programa) a `media/kontzertoak/`. Normalización de fechas con `_parse_fecha` para evitar errores de formato. |
| `lookups.py` | `/api/lookups` | CRUD genérico para todas las tablas de catálogo: géneros, tonalidades, tipos de copia, tipos de soporte, idiomas, compositores, arreglistas, ubicaciones, instrumentos y contextos (`erabilera-testuinguruak`). El instrumento `Gidoia` está protegido contra borrado. |
| `media.py` | `/api/media` | Sirve ficheros desde `MEDIA_ROOT`. Verifica que el fichero está registrado en `SOPORTE` o en `CONCIERTO` antes de servirlo. Soporta Range requests para streaming de audio y vídeo HTML5. |
| `backup.py` | `/api/backup` | Exportación (`GET /backup/export`) e importación (`POST /backup/import`) de la base de datos completa usando `/usr/bin/mysqldump` y `/usr/bin/mysql`. Solo accesible para admins. |

#### `utils/`

| Fichero | Descripción |
|---------|-------------|
| `utils/auth.py` | Generación y validación de tokens JWT. Decoradores `@login_required`, `@editor_required` y `@admin_required` para proteger endpoints. Función `get_current_user()` para obtener el usuario del token. |

#### Frontend

| Fichero | Descripción |
|---------|-------------|
| `tutb_frontend.html` | Aplicación web responsive en un único fichero HTML+CSS+JS. Interfaz en euskera. En escritorio: pestañas superiores (Nabigatu, Zuhaitz orokorra, Kontzertuak, Admin). En móvil: barra de navegación inferior (sin Admin). La versión actual se muestra en el footer, leyéndola de `version.json`. |
| `version.json` | Fichero con el número de versión actual (`{"version": "1.2"}`). El backend lo sirve en `GET /api/version`. El HTML lo carga al arrancar y lo muestra en el footer. Para publicar una nueva versión, basta con cambiar el número aquí. |

---

## 3. Directorios de datos

Crear directorios:

```bash
mkdir -p ~/TUTB/tutb_backend
mkdir -p ~/TUTB/media
sudo mkdir -p /var/www/tutb
```

---

## 3. Base de datos

### Iniciar MariaDB y crear BD + usuario

```bash
sudo systemctl enable --now mariadb
sudo mariadb -u root
```

```sql
CREATE DATABASE tutb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tutb_user'@'localhost' IDENTIFIED BY 'TU_PASSWORD_AQUI';
GRANT ALL PRIVILEGES ON tutb.* TO 'tutb_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Importar el schema

```bash
mariadb -u tutb_user -p tutb < tutb_database.sql
```

### Crear el primer usuario admin

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('admin123'))"
```

Copiar el hash resultante y ejecutar:

```bash
mariadb -u tutb_user -p tutb
```

```sql
INSERT INTO USUARIO (username, email, password_hash, role, activo)
VALUES ('admin', 'admin@ejemplo.com', 'HASH_COPIADO_AQUI', 'admin', 1);
EXIT;
```

> ⚠ Usa **werkzeug** para generar el hash, nunca bcrypt directamente. El sistema usa `werkzeug.security` en todo el backend.

---

## 4. Backend Python

### Entorno virtual e instalación de dependencias

```bash
cd ~/TUTB/tutb_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` debe contener al menos:

```
flask
flask-cors
mysql-connector-python
werkzeug
pyjwt
gunicorn
```

### Configuración: `config.py`

Editar los valores reales:

```python
MYSQL_HOST     = 'localhost'
MYSQL_PORT     = 3306
MYSQL_USER     = 'tutb_user'
MYSQL_PASSWORD = 'TU_PASSWORD_AQUI'       # ← cambiar
MYSQL_DB       = 'tutb'
JWT_SECRET_KEY = 'CLAVE_LARGA_Y_ALEATORIA' # ← cambiar
JWT_EXPIRY_HOURS = 8
MEDIA_ROOT     = '/home/TU_USUARIO/TUTB/media'  # ← ruta absoluta
```

Generar una clave JWT segura:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

También se pueden pasar como variables de entorno en lugar de editar el fichero.

### Copiar el frontend

```bash
sudo cp tutb_frontend.html /var/www/tutb/
```

### Cambiar la URL de la API en el frontend

Por defecto el frontend apunta a `http://localhost:5000/api`. En producción:

```bash
sudo sed -i "s|http://localhost:5000/api|https://TU_DOMINIO/api|g" \
    /var/www/tutb/tutb_frontend.html
```

### Probar manualmente

```bash
cd ~/TUTB/tutb_backend
source venv/bin/activate
python3 app.py
# Debería arrancar en http://0.0.0.0:5000
```

---

## 5. Servicio systemd (producción)

Crear `/etc/systemd/system/tutb.service`:

```ini
[Unit]
Description=TUTB Txistularis Artxiboa
After=network.target mariadb.service

[Service]
User=TU_USUARIO
WorkingDirectory=/home/TU_USUARIO/TUTB/tutb_backend
Environment="PATH=/home/TU_USUARIO/TUTB/tutb_backend/venv/bin"
ExecStart=/home/TU_USUARIO/TUTB/tutb_backend/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:5000 \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Activar e iniciar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tutb
sudo systemctl start tutb
sudo systemctl status tutb
```

Comandos útiles:

```bash
sudo systemctl restart tutb
sudo journalctl -u tutb -f              # logs en tiempo real
sudo journalctl -u tutb -n 50 --no-pager  # últimas 50 líneas
```

---

## 6. Servidor web

### Opción A: Nginx Proxy Manager (Docker) — configuración usada en producción

Si ya tienes Nginx Proxy Manager corriendo en Docker, añade un Proxy Host:

- **Domain Names:** `tutb.tudominio.org`
- **Scheme:** `http`
- **Forward Hostname/IP:** `172.17.0.1`  ← IP del host desde Docker
- **Forward Port:** `5000`
- Activar **Websockets Support**
- Pestaña SSL: solicitar certificado Let's Encrypt

> No usar `localhost` ni `192.168.x.x` como destino; desde Docker hay que usar `172.17.0.1` para apuntar al host.

### Opción B: Nginx directo (sin Docker)

Instalar Nginx:

```bash
sudo apt install -y nginx
```

Crear `/etc/nginx/sites-available/tutb`:

```nginx
server {
    listen 80;
    server_name tutb.tudominio.org;

    # Redirigir HTTP → HTTPS (si tienes SSL)
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name tutb.tudominio.org;

    ssl_certificate     /etc/letsencrypt/live/tutb.tudominio.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tutb.tudominio.org/privkey.pem;

    # Subidas grandes (partituras, vídeo)
    client_max_body_size 2G;

    # Frontend estático
    root /var/www/tutb;
    index tutb_frontend.html;

    location / {
        try_files $uri $uri/ @backend;
    }

    # API → Gunicorn
    location /api/ {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location @backend {
        proxy_pass http://127.0.0.1:5000;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/tutb /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

SSL con Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tutb.tudominio.org
```

### Opción C: Sin proxy (acceso directo por IP/puerto)

Útil para desarrollo o red local. Cambiar en `tutb.service`:

```ini
ExecStart=.../gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

Y en el frontend:

```bash
sudo sed -i "s|http://localhost:5000/api|http://IP_DEL_SERVIDOR:5000/api|g" \
    /var/www/tutb/tutb_frontend.html
```

Acceder en: `http://IP_DEL_SERVIDOR:5000`

---

## 7. Coexistencia con Nextcloud / Apache

Si el servidor ya tiene Apache sirviendo Nextcloud en el puerto 80/443, usar Nginx Proxy Manager en Docker (Opción A) es lo más limpio ya que gestiona sus propios puertos sin interferir con Apache.

Gunicorn solo escucha en `127.0.0.1:5000`, así que no hay conflicto de puertos.

---

## 8. Permisos del directorio media

```bash
chown -R TU_USUARIO:TU_USUARIO ~/TUTB/media
chmod -R 755 ~/TUTB/media
```

---

## 9. Backups y restauración

### Desde la interfaz web

En la pestaña **Admin** (solo usuarios con rol `admin`) hay dos botones:

- **⬇ Deskargatu babeskopia** — descarga un fichero `.sql` con fecha y hora.
- **⬆ Inportatu** — sube ese mismo `.sql` y restaura la base de datos completa. **Sobreescribe todos los datos.**

> Requiere que `mysqldump` y `mysql` estén instalados en el servidor:
> ```bash
> sudo apt install -y mariadb-client
> ```

### Desde línea de comandos

Exportar:

```bash
mysqldump -u tutb_user -p tutb > tutb_backup_$(date +%Y%m%d).sql
```

Importar en otra instancia:

```bash
mariadb -u tutb_user -p tutb < tutb_backup_20260101.sql
```

> El fichero `.sql` contiene estructura + datos. Al importar en una instancia nueva, la base de datos debe existir y estar vacía (o con el schema ya creado). Si se importa sobre una instancia existente, los datos se sobreescriben.

### Backup de ficheros media

Los ficheros subidos (partituras, grabaciones, etc.) están en `~/TUTB/media/` y **no se incluyen en el backup SQL**. Hacer copia aparte:

```bash
tar -czf tutb_media_$(date +%Y%m%d).tar.gz ~/TUTB/media/
```

Para restaurar en otro servidor:

```bash
tar -xzf tutb_media_20260101.tar.gz -C ~/TUTB/
```

---

## 10. Migración a otro servidor

1. Exportar backup SQL desde la interfaz web o con `mysqldump`.
2. Comprimir el directorio media: `tar -czf media.tar.gz ~/TUTB/media/`.
3. En el servidor destino, seguir los pasos 1–7 de esta guía.
4. Importar el SQL: `mariadb -u tutb_user -p tutb < backup.sql`.
5. Restaurar media: `tar -xzf media.tar.gz -C ~/TUTB/`.
6. Ajustar `config.py` con los datos del nuevo servidor.
7. `sudo systemctl restart tutb`.

---

## 11. Roles de usuario

| Rol | Permisos |
|-----|----------|
| `admin` | Todo: crear/editar/borrar cualquier cosa, gestionar usuarios, backups |
| `editor` | Crear y editar obras, arreglos, copias, soportes, conciertos |
| `reader` | Solo lectura, puede ver y descargar ficheros |
| `guest` | Solo lectura, sin descargas |

---

## 12. Gestión de versiones

El número de versión se mantiene en un único fichero dentro del backend:

```
~/TUTB/tutb_backend/version.json
```

Contenido:

```json
{"version": "1.2"}
```

El backend expone un endpoint público `GET /api/version` que devuelve ese JSON. El frontend lo lee al arrancar y lo muestra en el footer (`TUTB · Txistularis Artxiboa · v1.2`).

Para publicar una nueva versión, basta con editar ese fichero en el servidor:

```bash
echo '{"version": "1.3"}' > ~/TUTB/tutb_backend/version.json
```

No hace falta reiniciar ningún servicio — el navegador lo cargará en la próxima visita.

El endpoint se registra en `app.py`:

```python
@app.route('/api/version')
def get_version():
    import json, os
    vfile = os.path.join(os.path.dirname(__file__), 'version.json')
    try:
        with open(vfile) as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"version": "?"})
```

---

## 13. Solución de problemas habituales

**Error 1054 Unknown column 'notas' en INSERT**  
El `lookups.py` del servidor es una versión antigua que intenta insertar columnas inexistentes (`notas`, `descripcion`) en tablas de catálogo. Actualizar `routes/lookups.py`.

**Error de fecha: Incorrect date value 'Thu, 24 Dec...'**  
El frontend envía la fecha en formato HTTP. Actualizar `routes/conciertos.py` con la función `_parse_fecha`.

**Error 404 al servir media: "Fichero no registrado"**  
Los ficheros de conciertos (kartela, esku-programa, grabaciones) se buscan solo en `SOPORTE`. Actualizar `routes/media.py` para que también busque en `CONCIERTO`.

**mysqldump: command not found**  
```bash
sudo apt install -y mariadb-client
```
Además, en `routes/backup.py` usar la ruta absoluta `/usr/bin/mysqldump` y `/usr/bin/mysql`.

**Error de bcrypt / contraseña incorrecta tras cambio**  
Todo el sistema debe usar `werkzeug.security` (`generate_password_hash` / `check_password_hash`). Asegurarse de que `routes/auth.py` no importa ni usa `bcrypt` directamente en ningún punto.

**Gunicorn no arranca / variable `app` no encontrada**  
`app.py` debe tener `app = create_app()` a nivel de módulo (fuera del bloque `if __name__`), para que gunicorn pueda importarlo con `app:app`.

**NPM (Nginx Proxy Manager en Docker) no conecta con el backend**  
Usar `172.17.0.1:5000` como destino, no `localhost` ni la IP de la red local.
