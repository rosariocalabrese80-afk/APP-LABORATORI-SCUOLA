import http.cookiejar
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import test_bookings
import app


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_bookings.BookingTests()
        self.fixture.setUp()
        app.create_user('secondo', 'Secondo docente', 'password-test-456')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_port)
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.fixture.tearDown()

    def request(self, path, data=None, method=None, client=None):
        req = urllib.request.Request(self.base+path, data=json.dumps(data).encode() if data is not None else None,
                                     method=method, headers={'Content-Type':'application/json'})
        try:
            with (client or self.client).open(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_access_and_ownership(self):
        self.assertEqual(self.request('/api/data')[0],401)
        self.assertEqual(self.request('/api/login',{'username':'docente','password':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login',{'username':'docente','password':'password-test-123'})[0],200)
        status, data = self.request('/api/data')
        self.assertEqual(status,200)
        self.assertEqual(data['user']['name'],'Docente')
        status, booking = self.request('/api/bookings',self.fixture.data)
        self.assertEqual(status,201)
        second = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.request('/api/login',{'username':'secondo','password':'password-test-456'},client=second)
        self.assertEqual(self.request('/api/bookings/'+str(booking['id']),method='DELETE',client=second)[0],404)
        self.assertEqual(self.request('/api/bookings/'+str(booking['id']),method='DELETE')[0],200)
        self.assertEqual(self.request('/api/logout',{})[0],200)
        self.assertEqual(self.request('/api/data')[0],401)

    def test_login_throttling(self):
        for _ in range(5):
            self.assertEqual(self.request('/api/login',{'username':'docente','password':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login',{'username':'docente','password':'password-test-123'})[0],429)


class AdministrationTests(AccessTests):
    def setUp(self):
        super().setUp()
        app.create_user('admin@example.org','Responsabile','admin-password-123',role='admin')
        self.admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.assertEqual(self.request('/api/login',{'username':'admin@example.org','password':'admin-password-123'},client=self.admin)[0],200)

    def test_registration_manual_approval_and_suspension(self):
        registration = dict(email='Docente@Gmail.com',name='Nuovo Docente',password='personal-password-123',confirm_password='personal-password-123',role='admin',status='active')
        self.assertEqual(self.request('/api/register',registration)[0],201)
        self.assertEqual(self.request('/api/register',registration)[0],409)
        credentials = dict(username='docente@gmail.com',password='personal-password-123')
        self.assertEqual(self.request('/api/login',credentials)[0],403)
        users = self.request('/api/admin',client=self.admin)[1]['users']
        user = next(u for u in users if u['username']=='docente@gmail.com')
        self.assertEqual((user['role'],user['status']),('teacher','pending'))
        self.assertNotIn('password_hash',user)
        self.assertEqual(self.request('/api/admin/users',dict(id=user['id'],action='approve'),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/login',credentials)[0],200)
        self.assertEqual(self.request('/api/admin')[0],403)
        self.assertEqual(self.request('/api/admin/users',dict(id=user['id'],action='role',role='admin'))[0],403)
        self.assertEqual(self.request('/api/admin/users',dict(id=user['id'],action='suspend'),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/data')[0],401)
        self.assertEqual(self.request('/api/login',credentials)[0],403)

    def test_admin_create_edit_delete_bookings_and_labs(self):
        self.assertEqual(self.request('/api/admin/labs',dict(action='create',name='Nuovo laboratorio'),client=self.admin)[0],200)
        labs = self.request('/api/admin',client=self.admin)[1]['labs']
        lab = next(l for l in labs if l['name']=='Nuovo laboratorio')
        self.assertEqual(self.request('/api/admin/bookings',{**self.fixture.data,'lab':lab['id'],'user_id':1},client=self.admin)[0],200)
        booking = self.request('/api/data',client=self.admin)[1]['bookings'][0]
        self.assertEqual(booking['teacher'],'Docente')
        self.assertEqual(self.request('/api/admin/bookings',{**self.fixture.data,'id':booking['id'],'lab':lab['id'],'user_id':1,'start':'2026-11-02T10:00','end':'2026-11-02T11:00'},client=self.admin)[0],200)
        self.assertEqual(self.request('/api/bookings/'+str(booking['id']),method='DELETE',client=self.admin)[0],200)
        self.assertEqual(self.request('/api/admin/labs',dict(action='toggle',id=lab['id']),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/admin/bookings',{**self.fixture.data,'lab':lab['id'],'user_id':1},client=self.admin)[0],400)
        app.init()
        self.assertEqual(next(l for l in self.request('/api/admin',client=self.admin)[1]['labs'] if l['id']==lab['id'])['active'],0)

    def test_admin_management_last_admin_and_password_reset(self):
        admin_id = next(u['id'] for u in self.request('/api/admin',client=self.admin)[1]['users'] if u['role']=='admin')
        for action in ('suspend','delete','role'):
            self.assertEqual(self.request('/api/admin/users',dict(id=admin_id,action=action,role='teacher'),client=self.admin)[0],400)
        self.assertEqual(self.request('/api/admin/create-user',dict(email='other@example.net',name='Altro Admin',password='other-admin-password',role='admin'),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/login',dict(username='other@example.net',password='other-admin-password'))[0],200)
        self.assertEqual(self.request('/api/admin')[0],200)
        self.assertEqual(self.request('/api/admin/users',dict(id=1,action='password',password='new-password-test'),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/login',dict(username='docente',password='password-test-123'))[0],401)
        self.assertEqual(self.request('/api/login',dict(username='docente',password='new-password-test'))[0],200)
        self.assertEqual(self.request('/api/admin/users',dict(id=1,action='delete'),client=self.admin)[0],200)
        self.assertEqual(self.request('/api/data')[0],401)

    def test_invalid_registration_and_password_change(self):
        for email in ('bad','a@','a@b','a b@example.com'):
            self.assertEqual(self.request('/api/register',dict(email=email,name='Test',password='long-password-123',confirm_password='long-password-123'))[0],400)
        self.request('/api/login',dict(username='docente',password='password-test-123'))
        self.assertEqual(self.request('/api/password',dict(current_password='wrong',password='new-long-password',confirm_password='new-long-password'))[0],400)
        self.assertEqual(self.request('/api/password',dict(current_password='password-test-123',password='new-long-password',confirm_password='new-long-password'))[0],200)
        self.assertEqual(self.request('/api/data')[0],401)
        self.assertEqual(self.request('/api/login',dict(username='docente',password='new-long-password'))[0],200)


class InitialSetupTests(AccessTests):
    def test_six_character_password_and_one_time_setup(self):
        self.assertTrue(self.request('/api/setup-status')[1]['required'])
        token = app.setup_file().read_text()
        data = dict(token=token,password='abcdef',confirm_password='abcdef')
        self.assertEqual(self.request('/api/setup',{**data,'token':'invalid'})[0],400)
        self.assertEqual(self.request('/api/setup',{**data,'password':'abcde','confirm_password':'abcde'})[0],400)
        self.assertEqual(self.request('/api/setup',{**data,'confirm_password':'different'})[0],400)
        self.assertEqual(self.request('/api/setup',data)[0],201)
        self.assertFalse(app.setup_file().exists())
        self.assertFalse(self.request('/api/setup-status')[1]['required'])
        self.assertEqual(self.request('/api/setup',data)[0],400)
        self.assertEqual(self.request('/api/login',dict(username='rosariocalabrese80@gmail.com',password='abcdef'))[0],200)
        self.assertEqual(self.request('/api/data')[1]['user']['role'],'admin')
        self.assertEqual(self.request('/api/admin/create-user',dict(email='other@example.com',name='Altro',password='123456',role='admin'))[0],200)
        self.assertEqual(self.request('/api/password',dict(current_password='abcdef',password='654321',confirm_password='654321'))[0],200)
        self.assertEqual(self.request('/api/login',dict(username='rosariocalabrese80@gmail.com',password='654321'))[0],200)

    def test_public_registration_six_characters(self):
        data = dict(email='short@example.com',name='Docente',password='aaaaaa',confirm_password='aaaaaa')
        self.assertEqual(self.request('/api/register',{**data,'password':'aaaaa','confirm_password':'aaaaa'})[0],400)
        self.assertEqual(self.request('/api/register',data)[0],201)
