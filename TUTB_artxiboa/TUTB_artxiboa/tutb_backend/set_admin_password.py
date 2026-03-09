#!/usr/bin/env python3
"""
Ejecuta este script una sola vez para hashear la contraseña del admin.
Uso: python3 set_admin_password.py
"""
import getpass
import mysql.connector
from werkzeug.security import generate_password_hash

host     = input("MySQL host [localhost]: ").strip() or "localhost"
user     = input("MySQL user [tutb_user]: ").strip() or "tutb_user"
password = getpass.getpass("MySQL password: ")
database = input("Base de datos [tutb]: ").strip() or "tutb"

admin_pass = getpass.getpass("Nueva contraseña para admin: ")
confirm    = getpass.getpass("Confirma contraseña: ")

if admin_pass != confirm:
    print("❌ Las contraseñas no coinciden.")
    exit(1)

if len(admin_pass) < 8:
    print("❌ La contraseña debe tener al menos 8 caracteres.")
    exit(1)

hashed = generate_password_hash(admin_pass)

db = mysql.connector.connect(host=host, user=user, password=password, database=database)
cur = db.cursor()
cur.execute("UPDATE USUARIO SET password_hash = %s WHERE username = 'admin'", (hashed,))
db.commit()
print(f"✅ Contraseña del admin actualizada correctamente. ({cur.rowcount} fila)")
cur.close()
db.close()
