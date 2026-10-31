"""School documents and branding, persisted alongside the application data."""
import base64
import binascii
import io
import json
import re
import zipfile
from datetime import datetime, timezone

UPLOAD_PATHS = {'/api/admin/regulation-file', '/api/admin/branding'}


def request_limit(path):
    return 8 * 1024 * 1024 if path in UPLOAD_PATHS else 16384


def initialize(db, root):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS regulation_document(
          id INTEGER PRIMARY KEY CHECK(id=1), filename TEXT NOT NULL,
          mime TEXT NOT NULL, content BLOB NOT NULL, revision INTEGER NOT NULL,
          updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS regulation_summary(
          id INTEGER PRIMARY KEY CHECK(id=1), chapters TEXT NOT NULL,
          document_revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS school_assets(
          kind TEXT PRIMARY KEY, mime TEXT NOT NULL, content BLOB NOT NULL);
    ''')
    for kind, filename, mime in (
            ('header', 'school-header.jpg', 'image/jpeg'),
            ('logo', 'school-logo.png', 'image/png')):
        if not db.execute('SELECT 1 FROM school_assets WHERE kind=?', (kind,)).fetchone():
            content = (root / 'web' / 'assets' / filename).read_bytes()
            db.execute('INSERT INTO school_assets VALUES(?,?,?)', (kind, mime, content))
    if not db.execute('SELECT 1 FROM regulation_document').fetchone():
        db.execute('INSERT INTO regulation_document VALUES(1,?,?,?,?,?)', (
            'REGOLAMENTO LABORATORI(1).docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            (root / 'documents' / 'regolamento-laboratori.docx').read_bytes(),
            1, datetime.now(timezone.utc).isoformat()))
    if not db.execute('SELECT 1 FROM regulation_summary').fetchone():
        chapters = (root / 'documents' / 'regulations-summary.json').read_text()
        db.execute('INSERT INTO regulation_summary VALUES(1,?,1)', (chapters,))


def regulations(db):
    document = db.execute('SELECT filename,revision,updated_at,length(content) AS size FROM regulation_document').fetchone()
    summary = db.execute('SELECT chapters,document_revision FROM regulation_summary').fetchone()
    return {**dict(document), 'chapters': json.loads(summary['chapters']),
            'summary_current': summary['document_revision'] == document['revision']}


def decode_upload(data, limit):
    try:
        content = base64.b64decode(data.get('content', ''), validate=True)
    except (ValueError, TypeError, binascii.Error):
        raise ValueError('File non valido.') from None
    if not 0 < len(content) <= limit:
        raise ValueError(f'Il file deve essere non vuoto e non superare {limit // (1024*1024)} MB.')
    return content


def upload_regulation(db, data):
    filename = str(data.get('filename', '')).replace('\\', '/').rsplit('/', 1)[-1]
    if not filename or len(filename) > 180 or any(ord(c) < 32 for c in filename):
        raise ValueError('Nome file non valido.')
    content = decode_upload(data, 5 * 1024 * 1024)
    suffix = filename.rsplit('.', 1)[-1].lower()
    if suffix == 'pdf' and content.startswith(b'%PDF-'):
        mime = 'application/pdf'
    elif suffix == 'txt':
        try:
            content.decode('utf-8-sig')
        except UnicodeError:
            raise ValueError('Il file TXT deve usare la codifica UTF-8.') from None
        if b'\x00' in content:
            raise ValueError('Il file non contiene testo valido.')
        mime = 'text/plain; charset=utf-8'
    elif suffix == 'docx':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                if ('word/document.xml' not in names or '[Content_Types].xml' not in names
                        or len(names) > 1000
                        or sum(f.file_size for f in archive.infolist()) > 40*1024*1024
                        or any('vbaproject' in n.lower() for n in names)
                        or archive.testzip() is not None):
                    raise ValueError()
        except (zipfile.BadZipFile, RuntimeError, ValueError, NotImplementedError):
            raise ValueError('Documento DOCX non valido o troppo grande.') from None
        mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        raise ValueError('Carica un regolamento PDF, DOCX o TXT (massimo 5 MB).')
    db.execute('UPDATE regulation_document SET filename=?,mime=?,content=?,revision=revision+1,updated_at=? WHERE id=1',
               (filename, mime, content, datetime.now(timezone.utc).isoformat()))


def update_summary(db, data):
    chapters = data.get('chapters')
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 20:
        raise ValueError('Inserisci da 1 a 20 capitoli.')
    ids = set()
    clean = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            raise ValueError('Capitolo non valido.')
        ident = str(chapter.get('id', ''))
        title = str(chapter.get('title', '')).strip()
        source = str(chapter.get('source', '')).strip()
        paragraphs = chapter.get('paragraphs')
        if (not re.fullmatch('[a-z0-9-]{1,60}', ident) or ident in ids
                or not 1 <= len(title) <= 180 or len(source) > 180
                or not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 30
                or any(not isinstance(p, str) or not 1 <= len(p.strip()) <= 4000 for p in paragraphs)):
            raise ValueError('Controlla titolo e contenuto di ogni capitolo.')
        ids.add(ident)
        clean.append(dict(id=ident, title=title, source=source, paragraphs=[p.strip() for p in paragraphs]))
    revision = db.execute('SELECT revision FROM regulation_document').fetchone()[0]
    if data.get('document_revision') != revision:
        raise ValueError('Il documento è stato aggiornato da un altro amministratore. Ricarica la pagina e controlla la sintesi.')
    db.execute('UPDATE regulation_summary SET chapters=?,document_revision=? WHERE id=1',
               (json.dumps(clean, ensure_ascii=False), revision))


def upload_branding(db, data):
    kind = data.get('kind')
    if kind not in ('header', 'logo'):
        raise ValueError('Scegli intestazione o logo.')
    content = decode_upload(data, 2 * 1024 * 1024)
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif content.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValueError('Usa un’immagine PNG, JPG o WebP, massimo 2 MB.')
    db.execute('INSERT OR REPLACE INTO school_assets VALUES(?,?,?)', (kind, mime, content))
