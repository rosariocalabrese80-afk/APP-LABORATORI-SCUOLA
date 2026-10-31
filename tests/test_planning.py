"""Regression checks for PythonAnywhere routes, permissions and data preservation."""
import json
import sqlite3
import unittest
from pathlib import Path

import app
import reports
import test_hosting


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.host = test_hosting.HostingTests()
        self.host.setUp()
        self.fixture = self.host.fixture
        self.teacher = self.login('docente', 'password-test-123')
        app.create_user('other@example.org', 'Altro docente', 'abcdef')
        app.create_user('admin@example.org', 'Responsabile', 'abcdef', role='admin')
        self.other = self.login('other@example.org', 'abcdef')
        self.admin = self.login('admin@example.org', 'abcdef')
        self.slot = dict(lab=1, school_class='2B', date='2026-11-02', hours=[9], notes='Nota è (test) \\')

    def tearDown(self):
        self.host.tearDown()

    def request(self, path, data=None, cookie='', method=None):
        return self.host.request(path, data, cookie, method)

    def login(self, name, password):
        return self.request('/api/login', dict(username=name, password=password))['headers']['Set-Cookie'].split(';')[0]

    def body(self, response):
        return json.loads(response['body'])

    def closure(self, **overrides):
        return self.request('/api/admin/closures', dict(day='2026-11-02', blocked=True, visible=True, message='Chiusura prova', **overrides), self.admin)

    def test_closure_permissions_and_independent_options(self):
        data = dict(day='2026-11-02', blocked=True, visible=False, message='Messaggio riservato')
        self.assertEqual(self.request('/api/admin/closures', data)['status'], 401)
        self.assertEqual(self.request('/api/admin/closures', data, self.teacher)['status'], 403)
        self.assertEqual(self.request('/api/admin/closures', data, self.admin)['status'], 200)
        teacher_data = self.body(self.request('/api/data', cookie=self.teacher))
        self.assertEqual(teacher_data['closures'], [])
        self.assertIn(data['day'], teacher_data['unavailable_dates'])
        self.assertNotIn('Messaggio riservato', self.request('/api/report?date=2026-11-02', cookie=self.teacher)['body'].decode())
        self.assertEqual(self.request('/api/bookings', self.slot, self.teacher)['status'], 400)
        self.assertEqual(self.request('/api/admin/bookings', {**self.slot, 'user_id':1}, self.admin)['status'], 400)
        data.update(blocked=False, visible=True)
        self.assertEqual(self.request('/api/admin/closures', data, self.admin)['status'], 200)
        self.assertEqual(self.request('/api/bookings', self.slot, self.teacher)['status'], 201)
        self.assertEqual(len(self.body(self.request('/api/data', cookie=self.teacher))['closures']), 1)
        self.assertEqual(self.request('/api/admin/closures', dict(day=data['day'], action='delete'), self.admin)['status'], 200)

    def test_closure_keeps_existing_bookings_and_survives_init(self):
        ident = self.body(self.request('/api/bookings', self.slot, self.teacher))['ids'][0]
        self.closure()
        app.init()
        data = self.body(self.request('/api/data', cookie=self.teacher))
        self.assertEqual(data['bookings'][0]['id'], ident)
        self.assertEqual(data['closures'][0]['blocked'], 1)
        self.assertEqual(self.request('/api/bookings/edit', {**self.slot,'id':ident}, self.teacher)['status'], 400)
        self.assertEqual(self.request('/api/bookings/edit', {**self.slot,'id':ident,'date':'2026-11-03'}, self.teacher)['status'], 200)
        for invalid in ['2026-02-30', '2026-1-02', '<script>']:
            self.assertEqual(self.request('/api/admin/closures', dict(day=invalid, blocked=True, visible=True), self.admin)['status'], 400)

    def test_own_edit_atomic_ownership_and_conflicts(self):
        ident = self.body(self.request('/api/bookings', self.slot, self.teacher))['ids'][0]
        edit = {**self.slot, 'id':ident, 'hours':[10], 'school_class':'3C', 'user_id':2, 'teacher':'Impostore'}
        self.assertEqual(self.request('/api/bookings/edit', edit, self.other)['status'], 400)
        self.assertEqual(self.request('/api/bookings/edit', edit)['status'], 401)
        self.assertEqual(self.request('/api/bookings/edit', edit, self.teacher)['status'], 200)
        saved = self.body(self.request('/api/data', cookie=self.teacher))['bookings'][0]
        self.assertEqual((saved['id'], saved['user_id'], saved['teacher'], saved['school_class']), (ident, 1, 'Docente', '3C'))
        self.assertEqual(self.request('/api/bookings', {**self.slot,'hours':[11]}, self.other)['status'], 201)
        for change in [{'hours':[11]}, {'hours':[8,9]}, {'date':'2026-11-07'}, {'date':'2027-01-01'}]:
            self.assertEqual(self.request('/api/bookings/edit', {**edit, **change}, self.teacher)['status'], 400)
        unchanged = self.body(self.request('/api/data', cookie=self.teacher))['bookings'][0]
        self.assertEqual(saved, unchanged)

    def test_backup_admin_only_verified_and_complete(self):
        self.request('/api/bookings', self.slot, self.teacher)
        self.closure()
        self.assertEqual(self.request('/api/admin/backup')['status'], 401)
        self.assertEqual(self.request('/api/admin/backup', cookie=self.teacher)['status'], 403)
        result = self.request('/api/admin/backup', cookie=self.admin)
        self.assertEqual(result['status'], 200)
        self.assertIn('laboratori-2026-10-30.sqlite3', result['headers']['Content-Disposition'])
        self.assertEqual(result['headers']['Cache-Control'], 'no-store')
        destination = Path(self.fixture.tmp.name) / 'download.sqlite3'
        destination.write_bytes(result['body'])
        with sqlite3.connect(destination) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchone()[0], 'ok')
            for table in ['bookings','users','closures','school_assets','regulation_document']:
                self.assertGreater(db.execute('select count(*) from '+table).fetchone()[0], 0)

    def test_reports_period_scope_authorization_and_escaping(self):
        self.request('/api/bookings', {**self.slot,'school_class':'<script>2B</script>'}, self.teacher)
        self.request('/api/bookings', {**self.slot,'hours':[10], 'school_class':'OTHER-CLASS'}, self.other)
        self.request('/api/bookings', {**self.slot,'date':'2026-11-09','school_class':'NEXT-WEEK'}, self.teacher)
        self.assertEqual(self.request('/api/report')['status'],401)
        for period in ['day','week','month']:
            for scope in ['mine','all']:
                url=f'/api/report?date=2026-11-02&period={period}&scope={scope}'
                html=self.request(url,cookie=self.teacher)
                self.assertEqual(html['status'],200)
                self.assertNotIn('Content-Disposition', html['headers'])
                text=html['body'].decode()
                self.assertIn('&lt;script&gt;2B&lt;/script&gt;',text)
                self.assertEqual('OTHER-CLASS' in text, scope=='all')
                self.assertEqual('NEXT-WEEK' in text, period=='month')
                pdf=self.request(url+'&format=pdf',cookie=self.teacher)
                self.assertTrue(pdf['body'].startswith(b'%PDF-1.4'))
                self.assertTrue(pdf['body'].endswith(b'%%EOF\n'))
                self.assertEqual(pdf['headers']['Content-Type'],'application/pdf')
                self.assertEqual(b'OTHER-CLASS' in pdf['body'],scope=='all')
        for query in ['date=bad','period=year','scope=other','format=js']:
            self.assertEqual(self.request('/api/report?'+query,cookie=self.teacher)['status'],400)
        app.create_user('pending@example.org','Pending','abcdef',status='pending')
        self.assertEqual(self.request('/api/login',dict(username='pending@example.org',password='abcdef'))['status'],403)
        with app.connect() as db:
            db.execute("UPDATE users SET status='suspended' WHERE id=1")
        self.assertEqual(self.request('/api/report',cookie=self.teacher)['status'],401)

    def test_pending_notifications_permissions_and_counts(self):
        endpoint = '/api/admin/notifications'
        self.assertEqual(self.request(endpoint)['status'], 401)
        self.assertEqual(self.request(endpoint, cookie=self.teacher)['status'], 403)
        self.assertEqual(self.body(self.request(endpoint, cookie=self.admin)), {'pending_registrations':0})
        for letter in 'abc':
            response = self.request('/api/register', dict(email=letter+'@example.org', name='Richiesta '+letter, password='abcdef', confirm_password='abcdef'))
            self.assertEqual(response['status'], 201)
        app.create_user('excluded@example.org','Escluso','abcdef',status='suspended')
        result = self.request(endpoint, cookie=self.admin)
        self.assertEqual(result['headers']['Cache-Control'], 'no-store')
        self.assertEqual(self.body(result), {'pending_registrations':3})
        with app.connect() as db:
            identities = {r['username']:r['id'] for r in db.execute("SELECT id,username FROM users WHERE status='pending'")}
        for email,action,expected in [('a@example.org','approve',2),('b@example.org','suspend',1),('c@example.org','delete',0)]:
            self.assertEqual(self.request('/api/admin/users', dict(id=identities[email], action=action), self.admin)['status'], 200)
            self.assertEqual(self.body(self.request(endpoint, cookie=self.admin)), {'pending_registrations':expected})

    def test_profile_is_personal_and_password_revokes_all_sessions(self):
        import time
        profile = self.body(self.request('/api/data', cookie=self.teacher))['user']
        self.assertEqual(set(profile), {'id','username','name','role','status','session_expires'})
        self.assertEqual(profile['username'], 'docente')
        self.assertEqual(profile['role'], 'teacher')
        self.assertGreater(profile['session_expires'], int(time.time()))
        other = self.body(self.request('/api/data', cookie=self.other))['user']
        self.assertEqual(other['username'], 'other@example.org')
        second_session = self.login('docente', 'password-test-123')
        wrong = self.request('/api/password', dict(current_password='wrong', password='new-password', confirm_password='new-password'), self.teacher)
        self.assertEqual(wrong['status'], 400)
        self.assertEqual(self.request('/api/data', cookie=second_session)['status'], 200)
        changed = self.request('/api/password', dict(current_password='password-test-123', password='new-password', confirm_password='new-password', role='admin'), self.teacher)
        self.assertEqual(changed['status'], 200)
        self.assertEqual(self.request('/api/data', cookie=self.teacher)['status'], 401)
        self.assertEqual(self.request('/api/data', cookie=second_session)['status'], 401)
        new_session = self.login('docente', 'new-password')
        after = self.body(self.request('/api/data', cookie=new_session))['user']
        self.assertEqual(after['role'], 'teacher')
        self.assertEqual(self.request('/api/data', cookie=self.admin)['status'], 200)

    def test_pdf_pagination_and_offsets(self):
        raw=reports.pdf_document(['Riga è (test) \\ '+str(n) for n in range(140)])
        self.assertIn(b'/Count 3',raw)
        start=int(raw.split(b'startxref\n')[1].splitlines()[0])
        self.assertTrue(raw[start:].startswith(b'xref\n'))
        entries=raw[start:].splitlines()[3:]
        for number,line in enumerate(entries,1):
            if not line.endswith(b'n '):
                break
            offset=int(line[:10])
            self.assertTrue(raw[offset:].startswith(f'{number} 0 obj'.encode()))
