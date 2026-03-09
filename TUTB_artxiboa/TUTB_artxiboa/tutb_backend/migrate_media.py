#!/usr/bin/env python3
"""
Migra los ficheros de media de la estructura antigua (copias/<copia_id>/<filename>)
a la nueva jerarquía (obras/<obra_id>_<titulo>/v<vid>/a<aid>/c<cid>/s<sid>_<filename>).

Uso:
  source venv/bin/activate
  python3 migrate_media.py [--dry-run]
"""
import os, sys, re, shutil
sys.path.insert(0, os.path.dirname(__file__))

DRY_RUN = '--dry-run' in sys.argv

from app import create_app
app = create_app()

def slug(text, maxlen=40):
    text = str(text or '').strip()
    text = re.sub(r'[^\w\s\-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[\s\-]+', '_', text).strip('_')
    return text[:maxlen] or 'untitled'

def new_rel_path(soporte_id, copia_id, filename, obra_id, title, version_id, arreglo_id):
    obra_folder    = f"{obra_id:04d}_{slug(title)}"
    version_folder = f"v{version_id:03d}"
    arreglo_folder = f"a{arreglo_id:03d}"
    copia_folder   = f"c{copia_id:03d}"
    safe_name      = f"s{soporte_id:04d}_{filename}"
    return '/'.join(['obras', obra_folder, version_folder, arreglo_folder, copia_folder, safe_name])

with app.app_context():
    from config import Config
    from db import query, execute

    media_root = Config.MEDIA_ROOT

    soportes = query(
        '''SELECT s.soporte_id, s.copia_id, s.file_path,
                  o.obra_id, o.title,
                  v.version_id,
                  ar.arreglo_id
           FROM SOPORTE s
           JOIN COPIA cp      ON cp.copia_id    = s.copia_id
           JOIN ARREGLO ar    ON ar.arreglo_id  = cp.arreglo_id
           JOIN `VERSION` v   ON v.version_id   = ar.version_id
           JOIN OBRA o        ON o.obra_id      = v.obra_id
           WHERE s.file_path IS NOT NULL
             AND s.file_path != '__pending__'
        '''
    )

    moved = 0
    skipped = 0
    errors = 0

    for s in soportes:
        old_rel = s['file_path']
        old_abs = os.path.join(media_root, old_rel)

        if not os.path.exists(old_abs):
            print(f"  SKIP (no file): {old_rel}")
            skipped += 1
            continue

        filename = os.path.basename(old_rel)
        filename = re.sub(r'^s\d{4}_', '', filename)  # strip prefix if already migrated

        new_rel = new_rel_path(
            s['soporte_id'], s['copia_id'], filename,
            s['obra_id'], s['title'], s['version_id'], s['arreglo_id']
        )
        new_abs = os.path.join(media_root, new_rel)

        if old_rel == new_rel:
            print(f"  ALREADY OK: {new_rel}")
            skipped += 1
            continue

        print(f"  MOVE: {old_rel}")
        print(f"     -> {new_rel}")

        if not DRY_RUN:
            try:
                os.makedirs(os.path.dirname(new_abs), exist_ok=True)
                shutil.move(old_abs, new_abs)
                execute('UPDATE SOPORTE SET file_path=%s WHERE soporte_id=%s',
                        (new_rel, s['soporte_id']))
                moved += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1
        else:
            moved += 1

    print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Listo: {moved} movidos, {skipped} saltados, {errors} errores")
    if DRY_RUN:
        print("Ejecuta sin --dry-run para aplicar los cambios.")
