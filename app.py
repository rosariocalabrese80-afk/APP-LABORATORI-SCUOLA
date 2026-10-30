import re
import calendar
from zoneinfo import ZoneInfo
import hashlib
import hmac
import secrets
import time
import json
import os
import sqlite3
from datetime import datetime, timedelta
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LABS = ('Informatica · Aula 133', 'STEM/Coding · Aula 132', 'Arte · Aula 131',
        'Informatica · Carrello mobile n. 1', 'Informatica · Carrello mobile n. 2')
ROOT = Path(__file__).parent
DB = Path(os.environ.get('LAB_DB', ROOT / 'data' / 'laboratori.sqlite3'))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA secure_delete=ON')
    return db


def today():
    return datetime.now(ZoneInfo('Europe/Rome')).date()


def month_shift(day, offset):
    index = day.year * 12 + day.month - 1 + offset
    year, month = divmod(index, 12)
    month += 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def purge_old():
    cutoff = month_shift(today(), -1).isoformat()
    with connect() as db:
        db.execute('DELETE FROM bookings WHERE start<?', (cutoff,))


def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS labs(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS bookings(
          id INTEGER PRIMARY KEY, lab INTEGER NOT NULL REFERENCES labs(id),
          teacher TEXT NOT NULL, school_class TEXT NOT NULL,
          start TEXT NOT NULL, end TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(username TEXT NOT NULL, at INTEGER NOT NULL);
        ''')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(bookings)')}
        if 'user_id' not in columns:
            db.execute('ALTER TABLE bookings ADD COLUMN user_id INTEGER REFERENCES users(id)')
        user_columns = {r['name'] for r in db.execute('PRAGMA table_info(users)')}
        for column, definition in [('role', "TEXT NOT NULL DEFAULT 'teacher'"), ('status', "TEXT NOT NULL DEFAULT 'pending'")]:
            if column not in user_columns:
                db.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')
        if 'active' not in {r['name'] for r in db.execute('PRAGMA table_info(labs)')}:
            db.execute('ALTER TABLE labs ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        if not db.execute("SELECT 1 FROM settings WHERE key='catalog_seeded'").fetchone():
            db.executemany('INSERT OR IGNORE INTO labs(name) VALUES(?)', [(name,) for name in LABS])
            db.execute("INSERT INTO settings VALUES('catalog_seeded','1')")
    purge_old()
    prepare_setup()


def _book(db, data, user, booking_id=None):
    teacher = user['name']
    school_class = str(data.get('school_class', '')).strip()
    notes = str(data.get('notes', '')).strip()
    if not teacher or not school_class or max(len(teacher), len(school_class)) > 120 or len(notes) > 1000:
        raise ValueError('Inserisci docente e classe validi; note massimo 1000 caratteri.')
    try:
        start = datetime.fromisoformat(data['start'])
        end = datetime.fromisoformat(data['end'])
        lab = int(data['lab'])
    except (KeyError, ValueError, TypeError):
        raise ValueError('Laboratorio, data o orari non validi.')
    if start.tzinfo or end.tzinfo or start >= end or start.date() != end.date():
        raise ValueError('Scegli orari crescenti nella stessa giornata.')
    if (start.weekday() >= 5 or start.hour < 8 or end.hour > 14
            or start.minute or start.second or start.microsecond
            or end.minute or end.second or end.microsecond
            or end - start != timedelta(hours=1)):
        raise ValueError('Prenota una singola ora intera, dal lunedì al venerdì, tra le 08:00 e le 14:00.')
    if not today() <= start.date() <= month_shift(today(), 1):
        raise ValueError('Puoi prenotare da oggi fino a un mese di calendario in avanti.')
    start, end = start.isoformat(timespec='minutes'), end.isoformat(timespec='minutes')
    if not db.execute('SELECT id FROM labs WHERE id=? AND active=1', (lab,)).fetchone():
        raise ValueError('Laboratorio inesistente.')
    if db.execute('SELECT id FROM bookings WHERE lab=? AND start<? AND end>? AND id!=?', (lab, end, start, booking_id or -1)).fetchone():
        raise ValueError('Il laboratorio è già prenotato in questo intervallo.')
    if booking_id is not None:
        if not db.execute('SELECT 1 FROM bookings WHERE id=?', (booking_id,)).fetchone():
            raise ValueError('Prenotazione inesistente.')
        db.execute('UPDATE bookings SET lab=?,teacher=?,school_class=?,start=?,end=?,notes=?,user_id=? WHERE id=?',
                   (lab,teacher,school_class,start,end,notes,user['id'],booking_id))
        return booking_id
    cursor = db.execute('INSERT INTO bookings(lab,teacher,school_class,start,end,notes,user_id) VALUES(?,?,?,?,?,?,?)',
                        (lab, teacher, school_class, start, end, notes, user['id']))
    return cursor.lastrowid


def book(data, user, booking_id=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        return _book(db, data, user, booking_id)


def book_many(data, user, booking_id=None):
    hours = data.get('hours')
    if (not isinstance(hours,list) or not 1 <= len(hours) <= 6
            or any(type(hour) is not int or hour not in range(8,14) for hour in hours)
            or len(set(hours)) != len(hours)):
        raise ValueError('Seleziona almeno un’ora valida, senza duplicati, tra le 08:00 e le 14:00.')
    if booking_id is not None and len(hours) != 1:
        raise ValueError('Per modificare una prenotazione seleziona una sola ora.')
    day = data.get('date','')
    if not isinstance(day,str):
        raise ValueError('Data non valida.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        ids = []
        for hour in sorted(hours):
            slot = {**data,'start':f'{day}T{hour:02d}:00','end':f'{day}T{hour+1:02d}:00'}
            ids.append(_book(db,slot,user,booking_id))
        return ids


def create_user(username, name, password, role="teacher", status="active"):
    username, name = username.strip().lower(), name.strip()
    if not username or len(username) > 120 or not name or len(name) > 120 or not 6 <= len(password) <= 256:
        raise ValueError('Username e nome obbligatori; password di almeno 6 caratteri.')
    salt, digest = password_digest(password)
    with connect() as db:
        db.execute('INSERT INTO users(username,name,salt,password_hash,role,status) VALUES(?,?,?,?,?,?)', (username,name,salt,digest,role,status))
        if role == 'admin':
            db.execute("INSERT OR REPLACE INTO settings VALUES('setup_complete','1')")


def password_digest(password):
    if not 6 <= len(password) <= 256:
        raise ValueError('La password deve contenere da 6 a 256 caratteri, senza altri obblighi.')
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt, digest


def setup_file():
    return DB.with_suffix('.setup-token')


def prepare_setup():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        complete = db.execute("SELECT 1 FROM settings WHERE key='setup_complete'").fetchone()
        admins = db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone()
        if complete or admins:
            db.execute("INSERT OR IGNORE INTO settings VALUES('setup_complete','1')")
            setup_file().unlink(missing_ok=True)
            return
        saved = db.execute("SELECT value FROM settings WHERE key='setup_hash'").fetchone()
        if saved and setup_file().exists():
            return
        token = secrets.token_urlsafe(32)
        # The one-time credential stays in a local file, never in HTML or logs.
        fd = os.open(setup_file(),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as handle:
            handle.write(token)
        db.execute("INSERT OR REPLACE INTO settings VALUES('setup_hash',?)",(hashlib.sha256(token.encode()).hexdigest(),))


def setup_admin(data):
    password = str(data.get('password',''))
    if password != data.get('confirm_password'):
        raise ValueError('Le password non coincidono.')
    salt,digest = password_digest(password)
    token_hash = hashlib.sha256(str(data.get('token','')).encode()).hexdigest()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM settings WHERE key='setup_complete'").fetchone() or db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            raise ValueError('La configurazione iniziale è già stata completata.')
        expected = db.execute("SELECT value FROM settings WHERE key='setup_hash'").fetchone()
        if not expected or not hmac.compare_digest(token_hash,expected['value']):
            raise ValueError('Codice di configurazione non valido.')
        email = 'rosariocalabrese80@gmail.com'
        existing = db.execute('SELECT id FROM users WHERE username=?',(email,)).fetchone()
        if existing:
            db.execute('UPDATE users SET name=?,salt=?,password_hash=?,role=?,status=? WHERE id=?',
                       ('Rosario Calabrese',salt,digest,'admin','active',existing['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(existing['id'],))
        else:
            db.execute('INSERT INTO users(username,name,salt,password_hash,role,status) VALUES(?,?,?,?,?,?)',
                       (email,'Rosario Calabrese',salt,digest,'admin','active'))
        db.execute("INSERT INTO settings VALUES('setup_complete','1')")
        db.execute("DELETE FROM settings WHERE key='setup_hash'")
    setup_file().unlink(missing_ok=True)


def validate_email(value):
    email = str(value).strip().lower()
    if len(email) > 120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError('Inserisci un indirizzo email valido.')
    return email


def manage_user(data, actor):
    ident = int(data.get('id', 0))
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        target = db.execute('SELECT * FROM users WHERE id=?', (ident,)).fetchone()
        if not target:
            raise ValueError('Utente inesistente.')
        action = data.get('action')
        if action in ('approve','suspend','role','delete'):
            role = data.get('role',target['role']) if action == 'role' else target['role']
            status = 'active' if action == 'approve' else 'suspended' if action == 'suspend' else target['status']
            if role not in ('admin','teacher'):
                raise ValueError('Ruolo non valido.')
            if target['role']=='admin' and target['status']=='active' and (role!='admin' or status!='active' or action=='delete'):
                count = db.execute("SELECT count(*) FROM users WHERE role='admin' AND status='active'").fetchone()[0]
                if count <= 1:
                    raise ValueError('Deve rimanere almeno un amministratore attivo.')
            if action=='delete':
                if ident==actor['id']:
                    raise ValueError('Non puoi eliminare il tuo account dalla sessione corrente.')
                db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
                db.execute('DELETE FROM bookings WHERE user_id=?',(ident,))
                db.execute('DELETE FROM users WHERE id=?',(ident,))
            else:
                db.execute('UPDATE users SET role=?,status=? WHERE id=?',(role,status,ident))
                db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
        elif action=='password':
            password = str(data.get('password',''))
            if not 6 <= len(password) <= 256:
                raise ValueError('La password deve contenere da 6 a 256 caratteri.')
            salt = secrets.token_hex(16)
            digest = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?',(salt,digest,ident))
            db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
        else:
            raise ValueError('Azione utente non valida.')


class Handler(BaseHTTPRequestHandler):
    def user(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['session'].value
        except (KeyError, ValueError, CookieError):
            return None
        with connect() as db:
            return db.execute("SELECT u.id,u.name,u.role,u.status FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>? AND u.status='active'",
                              (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()

    def require_user(self):
        user = self.user()
        if user is None:
            self.reply(401, {'error': 'Accedi con il tuo account docente.'})
        return user

    def cookie(self, token, age):
        secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
        return f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}{secure}'

    def reply(self, status, body, cookie=None):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/api/setup-status':
            with connect() as db:
                complete = bool(db.execute("SELECT 1 FROM settings WHERE key='setup_complete'").fetchone())
            self.reply(200, {'required':not complete})
        elif self.path == '/api/admin':
            user = self.require_user()
            if user is None:
                return
            if user['role'] != 'admin':
                self.reply(403, {'error':'Accesso riservato agli amministratori.'})
                return
            with connect() as db:
                self.reply(200, {'users':[dict(r) for r in db.execute('SELECT id,username,name,role,status FROM users ORDER BY name')],
                                 'labs':[dict(r) for r in db.execute('SELECT * FROM labs ORDER BY name')]})
        elif self.path == '/api/data':
            purge_old()
            user = self.require_user()
            if user is None:
                return
            with connect() as db:
                self.reply(200, {'today': today().isoformat(), 'booking_until': month_shift(today(),1).isoformat(), 'history_from': month_shift(today(),-1).isoformat(), 'user': dict(user), 'labs': [dict(r) for r in db.execute('SELECT * FROM labs WHERE active=1 ORDER BY name')],
                                 'bookings': [dict(r) for r in db.execute('SELECT b.*, l.name AS lab_name FROM bookings b JOIN labs l ON l.id=b.lab ORDER BY start')]})
        elif self.path in ('/', '/index.html'):
            raw = (ROOT / 'web' / 'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.reply(404, {'error': 'Pagina inesistente.'})

    def do_POST(self):
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.reply(403, {'error': 'Richiesta non consentita.'})
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                raise ValueError('Richiesta non valida.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Richiesta non valida.')
            if self.path == '/api/setup':
                setup_admin(data)
                self.reply(201, {'ok':True})
                return
            if self.path == '/api/register':
                email = validate_email(data.get('email',''))
                if data.get('password') != data.get('confirm_password'):
                    raise ValueError('Le password non coincidono.')
                create_user(email,str(data.get('name','')),str(data.get('password','')),status='pending')
                self.reply(201, {'ok':True,'message':'Iscrizione ricevuta. Attendi l’approvazione dell’amministratore prima di accedere.'})
                return
            if self.path == '/api/login':
                username = str(data.get('username', '')).strip().lower()
                password = str(data.get('password', ''))
                now = int(time.time())
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('DELETE FROM attempts WHERE at<?', (now-900,))
                    if db.execute('SELECT count(*) FROM attempts WHERE username=?', (username,)).fetchone()[0] >= 5:
                        self.reply(429, {'error': 'Troppi tentativi. Riprova tra 15 minuti.'})
                        return
                    user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
                    salt = user['salt'] if user else '00'*16
                    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
                    if not user or not hmac.compare_digest(digest, user['password_hash']):
                        db.execute('INSERT INTO attempts VALUES(?,?)', (username,now))
                        self.reply(401, {'error': 'Credenziali non valide.'})
                        return
                    if user['status'] != 'active':
                        self.reply(403, {'error':'Account in attesa di approvazione o escluso. Contatta l’amministratore.'})
                        return
                    token = secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires<=?', (now,))
                    db.execute('DELETE FROM attempts WHERE username=?', (username,))
                    db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),user['id'],now+28800))
                self.reply(200, {'ok': True}, self.cookie(token,28800))
                return
            user = self.require_user()
            if user is None:
                return
            if self.path == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                with connect() as db:
                    db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(cookie['session'].value.encode()).hexdigest(),))
                self.reply(200, {'ok': True}, self.cookie('',0))
            elif self.path.startswith('/api/admin/'):
                if user['role'] != 'admin':
                    self.reply(403, {'error':'Accesso riservato agli amministratori.'})
                    return
                if self.path == '/api/admin/users':
                    manage_user(data,user)
                elif self.path == '/api/admin/create-user':
                    role = data.get('role','admin')
                    if role not in ('admin','teacher'):
                        raise ValueError('Ruolo non valido.')
                    create_user(validate_email(data.get('email','')),str(data.get('name','')),str(data.get('password','')),role=role)
                elif self.path == '/api/admin/labs':
                    action = data.get('action')
                    name = str(data.get('name','')).strip()
                    if action in ('create','rename') and not 1 <= len(name) <= 120:
                        raise ValueError('Nome laboratorio obbligatorio, massimo 120 caratteri.')
                    with connect() as db:
                        if action=='create':
                            db.execute('INSERT INTO labs(name) VALUES(?)',(name,))
                        elif action=='rename':
                            db.execute('UPDATE labs SET name=? WHERE id=?',(name,int(data['id'])))
                        elif action=='toggle':
                            db.execute('UPDATE labs SET active=1-active WHERE id=?',(int(data['id']),))
                        else:
                            raise ValueError('Azione laboratorio non valida.')
                elif self.path == '/api/admin/bookings':
                    with connect() as db:
                        target = db.execute("SELECT id,name FROM users WHERE id=? AND status='active'",(int(data.get('user_id',0)),)).fetchone()
                    if not target:
                        raise ValueError('Scegli un docente attivo.')
                    booking_id = int(data['id']) if data.get('id') else None
                    if 'hours' in data:
                        book_many(data,target,booking_id)
                    else:
                        book(data,target,booking_id)
                else:
                    self.reply(404, {'error':'Operazione inesistente.'})
                    return
                self.reply(200, {'ok':True})
            elif self.path == '/api/password':
                password = str(data.get('password',''))
                if password != data.get('confirm_password'):
                    raise ValueError('Le password non coincidono.')
                with connect() as db:
                    current = db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
                digest = hashlib.scrypt(str(data.get('current_password','')).encode(),salt=bytes.fromhex(current['salt']),n=16384,r=8,p=1).hex()
                if not hmac.compare_digest(digest,current['password_hash']):
                    raise ValueError('Password attuale non valida.')
                manage_user({'id':user['id'],'action':'password','password':password},user)
                self.reply(200, {'ok':True},self.cookie('',0))
            elif self.path == '/api/bookings':
                if 'hours' in data:
                    self.reply(201, {'ids': book_many(data, user)})
                else:
                    self.reply(201, {'id': book(data, user)})
            else:
                self.reply(404, {'error': 'Operazione inesistente.'})
        except sqlite3.IntegrityError:
            self.reply(409, {'error': 'Email o nome laboratorio già presente.'})
        except (ValueError, TypeError, KeyError):
            import sys
            self.reply(400, {'error': str(sys.exception())})

    def do_DELETE(self):
        if self.headers.get('Content-Type') != 'application/json':
            self.reply(403, {'error': 'Richiesta non consentita.'})
            return
        user = self.require_user()
        if user is None:
            return
        try:
            prefix, ident = self.path.rsplit('/', 1)
            if prefix != '/api/bookings':
                raise ValueError()
            with connect() as db:
                cursor = db.execute('DELETE FROM bookings WHERE id=? AND (user_id=? OR ?=1)', (int(ident), user['id'],int(user['role']=='admin')))
            self.reply(200 if cursor.rowcount else 404, {'ok': bool(cursor.rowcount)})
        except ValueError:
            self.reply(400, {'error': 'Prenotazione non valida.'})


class SchoolServer(ThreadingHTTPServer):
    last_cleanup = None

    def service_actions(self):
        if self.last_cleanup != today():
            purge_old()
            self.last_cleanup = today()


if __name__ == '__main__':
    init()
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ('create-user','create-admin'):
        import getpass
        username = validate_email(input('Email: '))
        name = input('Nome e cognome: ')
        password = getpass.getpass('Password (almeno 6 caratteri): ')
        if password != getpass.getpass('Conferma password: '):
            raise SystemExit('Le password non coincidono.')
        create_user(username, name, password, role='admin' if sys.argv[1]=='create-admin' else 'teacher')
        print('Account docente creato.')
        raise SystemExit(0)
    server = SchoolServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000'))), Handler)
    print('Laboratori avviato', flush=True)
    server.serve_forever()
