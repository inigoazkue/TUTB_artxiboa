cd /home/inigoazkue/TUTB/tutb_backend
source venv/bin/activate
python3 -c "
import bcrypt
from db import get_db
app_module = __import__('app')
with app_module.app.app_context():
    from db import query, execute
    pw = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
    execute('INSERT INTO USUARIO (username, email, password_hash, role, activo) VALUES (%s,%s,%s,%s,1)',
        ('admin', 'admin@tutb.local', pw, 'admin'))
    print('Usuario admin creado OK')
"
