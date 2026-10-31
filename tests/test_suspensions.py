import json
import unittest
import app
import test_hosting


class SuspensionTests(unittest.TestCase):
    def setUp(self):
        self.host=test_hosting.HostingTests()
        self.host.setUp()
        app.create_user('admin@example.com','Amministratore','abcdef',role='admin')
        self.admin=self.login('admin@example.com','abcdef')
        self.teacher=self.login('docente','password-test-123')
        self.notice='Laboratorio sospeso temporaneamente per manutenzione delle postazioni.'

    def tearDown(self):
        self.host.tearDown()

    def login(self,email,password):
        result=self.host.request('/api/login',dict(username=email,password=password))
        self.assertEqual(result['status'],200)
        return result['headers']['Set-Cookie'].split(';')[0]

    def action(self,data,cookie=None):
        return self.host.request('/api/admin/labs',data,cookie if cookie is not None else self.admin)

    def lab(self):
        data=json.loads(self.host.request('/api/data',cookie=self.teacher)['body'])
        return next(l for l in data['labs'] if l['id']==1)

    def test_suspension_persists_and_preserves_existing_bookings(self):
        app.book(self.host.fixture.data,self.host.fixture.user)
        result=self.action(dict(id=1,action='suspend',message=self.notice))
        self.assertEqual(result['status'],200)
        self.assertEqual(self.lab()['active'],1)
        self.assertEqual(self.lab()['suspended'],1)
        self.assertEqual(self.lab()['suspension_message'],self.notice)
        app.init()
        self.assertEqual(self.lab()['suspension_message'],self.notice)
        data={**self.host.fixture.data,'date':'2026-11-02','hours':[8,10]}
        for cookie in (self.teacher,self.admin):
            rejected=self.host.request('/api/bookings',data,cookie)
            self.assertEqual(rejected['status'],400)
            self.assertIn(self.notice,json.loads(rejected['body'])['error'])
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM bookings').fetchone()[0],1)
        self.assertEqual(self.action(dict(id=1,action='resume'))['status'],200)
        self.assertEqual(self.lab()['suspended'],0)
        self.assertEqual(self.lab()['suspension_message'],'')
        self.assertEqual(self.host.request('/api/bookings',data,self.teacher)['status'],201)

    def test_invalid_and_unauthorized_suspensions(self):
        for message in ('','   ','x'*1001,None,True):
            with self.subTest(message=str(message)[:20]):
                self.assertEqual(self.action(dict(id=1,action='suspend',message=message))['status'],400)
        self.assertEqual(self.action(dict(id=1,action='suspend',message=self.notice),self.teacher)['status'],403)
        self.assertEqual(self.action(dict(id=999,action='suspend',message=self.notice))['status'],400)
        self.assertEqual(self.action(dict(id=999,action='resume'))['status'],400)
        self.assertEqual(self.lab()['suspended'],0)

    def test_notification_can_be_changed_and_edited_booking_is_blocked(self):
        ident=app.book(self.host.fixture.data,self.host.fixture.user)
        self.action(dict(id=1,action='suspend',message=self.notice))
        updated='Attività sospese fino alla conclusione dei lavori.\nContattare la segreteria.'
        self.assertEqual(self.action(dict(id=1,action='suspend',message=updated))['status'],200)
        self.assertEqual(self.lab()['suspension_message'],updated)
        data={**self.host.fixture.data,'id':ident,'user_id':1,'date':'2026-11-02','hours':[10]}
        self.assertEqual(self.host.request('/api/admin/bookings',data,self.admin)['status'],400)
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT start FROM bookings WHERE id=?',(ident,)).fetchone()[0],'2026-11-02T09:00')
