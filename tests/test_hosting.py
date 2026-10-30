import importlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

import app
import backup
import test_bookings


class HostingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_bookings.BookingTests()
        self.fixture.setUp()
        self.wsgi = importlib.import_module('wsgi')

    def tearDown(self):
        self.fixture.tearDown()

    def request(self, path, data=None, cookie='', method=None):
        environ = {}
        setup_testing_defaults(environ)
        raw = json.dumps(data).encode() if data is not None else b''
        environ.update(PATH_INFO=path, REQUEST_METHOD=method or ('POST' if data is not None else 'GET'),
                       CONTENT_LENGTH=str(len(raw)), CONTENT_TYPE='application/json',
                       HTTP_COOKIE=cookie, QUERY_STRING='', **{'wsgi.input': io.BytesIO(raw)})
        response = {}

        def start(status, headers, exc_info=None):
            response.update(status=int(status.split()[0]), headers=dict(headers))

        result = validator(self.wsgi.application)(environ, start)
        try:
            response['body'] = b''.join(result)
        finally:
            result.close()
        return response

    def test_wsgi_login_booking_and_secure_cookie(self):
        self.assertEqual(self.request('/')['status'], 200)
        self.assertEqual(self.request('/api/data')['status'], 401)
        with patch.dict(os.environ, {'COOKIE_SECURE': '1'}):
            login = self.request('/api/login', {'username': 'docente', 'password': 'password-test-123'})
        self.assertEqual(login['status'], 200)
        self.assertIn('; Secure', login['headers']['Set-Cookie'])
        cookie = login['headers']['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/api/bookings', self.fixture.data, cookie)['status'], 201)
        data = json.loads(self.request('/api/data', cookie=cookie)['body'])
        self.assertEqual(data['bookings'][0]['school_class'], '2B')
        self.assertEqual(self.request('/api/data', method='PUT')['status'], 405)
        self.assertEqual(self.request('/api/login', {'large': 'x' * 17000})['status'], 413)

    def test_backup_and_restart_preserve_data(self):
        app.book(self.fixture.data, self.fixture.user)
        destination = Path(self.fixture.tmp.name) / 'backup.sqlite3'
        backup.backup(destination)
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM bookings').fetchone()[0], 1)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        with self.assertRaises(ValueError):
            backup.backup(destination)
        with self.assertRaises(ValueError):
            backup.backup(app.DB)
        # A new interpreter initializes the same persistent DB, independently of this process.
        code = """
import app
from datetime import date
app.today = lambda: date(2026,10,30)
import wsgi
with app.connect() as db:
    assert db.execute('SELECT count(*) FROM bookings').fetchone()[0] == 1
    assert db.execute("SELECT name FROM users WHERE username='docente'").fetchone()[0] == 'Docente'
print('Persistenza verificata dopo nuovo processo WSGI')
"""
        result = subprocess.run([sys.executable, '-c', code], cwd=app.ROOT,
                                env={**os.environ, 'LAB_DB': str(app.DB)},
                                capture_output=True, text=True, check=True)
        self.assertIn('Persistenza verificata', result.stdout)

    def test_multiple_hours_wsgi(self):
        login = self.request('/api/login', {'username':'docente','password':'password-test-123'})
        cookie=login['headers']['Set-Cookie'].split(';')[0]
        data={**self.fixture.data,'date':'2026-11-02','hours':[8,10]}
        created=self.request('/api/bookings',data,cookie)
        self.assertEqual(created['status'],201)
        self.assertEqual(len(json.loads(created['body'])['ids']),2)
        failed=self.request('/api/bookings',{**data,'hours':[9,10,11]},cookie)
        self.assertEqual(failed['status'],400)
        rows=json.loads(self.request('/api/data',cookie=cookie)['body'])['bookings']
        self.assertEqual(len(rows),2)
