"""Create a consistent SQLite backup, including while the app is running."""
import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

import app


def backup(destination):
    destination = Path(destination).expanduser().resolve()
    if destination == app.DB.resolve():
        raise ValueError('La destinazione non può essere il database originale.')
    if destination.exists():
        raise ValueError('Il file di destinazione esiste già. Scegli un nome diverso.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = app.DB.resolve().as_uri() + '?mode=ro'
    fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.sqlite3')
    os.close(fd)
    try:
        with sqlite3.connect(source_uri, uri=True) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Verifica del backup non riuscita.')
        # Fail if another process created the destination meanwhile.
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='Nome di un nuovo file .sqlite3 di backup')
    print('Backup verificato:', backup(parser.parse_args().destination))
