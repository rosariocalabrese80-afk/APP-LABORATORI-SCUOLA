#!/usr/bin/env bash
# Full PythonAnywhere installation. Optional destination root is for local validation.
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3.12 - "$package_dir" "${1:-$HOME}" <<'PY'
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
import shutil
import sqlite3
import sys

source = Path(sys.argv[1]).resolve()
base = Path(sys.argv[2]).expanduser().resolve()
base.mkdir(parents=True, exist_ok=True)
project = base / 'laboratori-app'
data = base / 'laboratori-data'
required = ('app.py','wsgi.py','school.py','reports.py','backup.py','web/index.html',
            'web/assets/school-header.jpg','web/assets/school-logo.png',
            'documents/regolamento-laboratori.docx','documents/regulations-summary.json')
for name in required:
    if not (source / name).is_file():
        raise SystemExit('Pacchetto incompleto: manca ' + name)
for name in ('app.py','wsgi.py','school.py','reports.py','backup.py'):
    compile((source / name).read_text(), name, 'exec')
if source == project or project in source.parents:
    raise SystemExit('Estrai prima lo ZIP in laboratori-pacchetto, fuori da laboratori-app.')

def snapshot(origin, destination):
    with sqlite3.connect(origin.resolve().as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Integrità del backup non valida.')
    destination.chmod(0o600)

stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
old_project = base / ('laboratori-app-precedente-' + stamp)
data.mkdir(exist_ok=True)
external_db = data / 'laboratori.sqlite3'
internal_db = project / 'data' / 'laboratori.sqlite3'
with TemporaryDirectory(prefix='.laboratori-install-', dir=base) as temporary:
    staged = Path(temporary) / 'app'
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','dist'))
    if external_db.is_file():
        snapshot(external_db, base / ('laboratori-backup-' + stamp + '.sqlite3'))
        print('Backup del database persistente verificato.')
    if internal_db.is_file():
        snapshot(internal_db, base / ('laboratori-backup-interno-' + stamp + '.sqlite3'))
        (staged / 'data').mkdir(exist_ok=True)
        snapshot(internal_db, staged / 'data' / 'laboratori.sqlite3')
        token = internal_db.with_suffix('.setup-token')
        if token.exists():
            shutil.copy2(token, staged / 'data' / token.name)
        if not external_db.exists():
            snapshot(internal_db, external_db)
            if token.exists():
                shutil.copy2(token, external_db.with_suffix('.setup-token'))
        print('Database interno conservato e verificato.')
    moved_old = False
    try:
        if project.exists():
            project.rename(old_project)
            moved_old = True
        staged.rename(project)
    except BaseException:
        if moved_old and not project.exists():
            old_project.rename(project)
        raise

print('Installazione COMPLETA terminata: ' + str(project))
print('Database persistente: ' + str(external_db))
if old_project.exists():
    print('Versione precedente conservata: ' + str(old_project))
print('Mantieni la configurazione WSGI esistente e premi Web → Reload.')
print('Non avviare app.py nella console: PythonAnywhere usa WSGI.')
PY
