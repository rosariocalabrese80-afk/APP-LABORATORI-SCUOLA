import base64
import json
import unittest
import app
import test_hosting


class SchoolTests(unittest.TestCase):
    def setUp(self):
        self.host=test_hosting.HostingTests()
        self.host.setUp()
        app.create_user('admin@example.com','Responsabile','abcdef',role='admin')
        self.admin=self.login('admin@example.com','abcdef')
        self.teacher=self.login('docente','password-test-123')

    def tearDown(self):
        self.host.tearDown()

    def login(self,email,password):
        response=self.host.request('/api/login',dict(username=email,password=password))
        self.assertEqual(response['status'],200)
        return response['headers']['Set-Cookie'].split(';')[0]

    def request(self,path,data=None,cookie=None):
        return self.host.request(path,data,cookie if cookie is not None else self.admin)

    def upload(self,filename,content,cookie=None):
        return self.request('/api/admin/regulation-file',dict(filename=filename,content=base64.b64encode(content).decode()),cookie)

    def test_original_branding_is_available_without_admin_upload(self):
        for kind,filename in [('header','school-header.jpg'),('logo','school-logo.png')]:
            result=self.request('/api/branding/'+kind,cookie='')
            self.assertEqual(result['status'],200)
            self.assertEqual(result['body'],(app.ROOT/'web'/'assets'/filename).read_bytes())

    def test_upgrade_seeds_missing_image_without_overwriting_custom_image(self):
        custom=b'custom image already uploaded by administrator'
        with app.connect() as db:
            db.execute("UPDATE school_assets SET content=? WHERE kind='logo'",(custom,))
            db.execute("DELETE FROM school_assets WHERE kind='header'")
        app.init()
        self.assertEqual(self.request('/api/branding/logo',cookie='')['body'],custom)
        self.assertEqual(self.request('/api/branding/header',cookie='')['body'],(app.ROOT/'web'/'assets'/'school-header.jpg').read_bytes())

    def test_original_download_and_chapter_index(self):
        self.assertEqual(self.request('/api/regulations',cookie='')['status'],401)
        self.assertEqual(self.request('/api/regulations/download',cookie='')['status'],401)
        response=self.request('/api/regulations',cookie=self.teacher)
        metadata=json.loads(response['body'])
        self.assertEqual(len(metadata['chapters']),10)
        self.assertTrue(metadata['summary_current'])
        self.assertIn('ribaltine',[c['id'] for c in metadata['chapters']])
        original=self.request('/api/regulations/download',cookie=self.teacher)
        self.assertEqual(original['status'],200)
        self.assertIn('attachment;',original['headers']['Content-Disposition'])
        self.assertEqual(original['body'],(app.ROOT/'documents'/'regolamento-laboratori.docx').read_bytes())

    def test_admin_upload_and_summary_versioning(self):
        content='Nuovo regolamento completo: attività e sicurezza.'.encode()
        self.assertEqual(self.upload('nuovo.txt',content)['status'],200)
        metadata=json.loads(self.request('/api/regulations')['body'])
        self.assertEqual(metadata['revision'],2)
        self.assertFalse(metadata['summary_current'])
        chapters=metadata['chapters']
        chapters[0]['paragraphs']=['Sintesi controllata per il nuovo testo.']
        result=self.request('/api/admin/regulation-summary',dict(chapters=chapters,document_revision=metadata['revision']))
        self.assertEqual(result['status'],200)
        app.init()
        after=json.loads(self.request('/api/regulations')['body'])
        self.assertTrue(after['summary_current'])
        self.assertEqual(after['revision'],2)
        self.assertEqual(after['chapters'][0]['paragraphs'],chapters[0]['paragraphs'])
        self.assertEqual(self.request('/api/regulations/download',cookie=self.teacher)['body'],content)

    def test_upload_original_docx_above_normal_request_limit(self):
        content=(app.ROOT/'documents'/'regolamento-laboratori.docx').read_bytes()
        self.assertGreater(len(content),16384)
        self.assertEqual(self.upload('regolamento.docx',content)['status'],200)
        self.assertEqual(self.request('/api/regulations/download')['body'],content)

    def test_teachers_cannot_upload_or_change_summary(self):
        self.assertEqual(self.upload('nuovo.txt',b'Nuovo',self.teacher)['status'],403)
        self.assertEqual(self.request('/api/admin/regulation-summary',dict(chapters=[]),self.teacher)['status'],403)
        self.assertEqual(self.request('/api/admin/branding',dict(kind='logo',content=''),self.teacher)['status'],403)
        self.assertEqual(json.loads(self.request('/api/regulations')['body'])['revision'],1)

    def test_invalid_documents_and_summaries_do_not_overwrite(self):
        for filename,content in [('bad.html',b'<script>test</script>'),('bad.docx',b'not a docx'),('bad.pdf',b'not a pdf'),('bad.txt',b'\x00bad'),('bad.txt',b'\xff')]:
            with self.subTest(filename=filename):
                self.assertEqual(self.upload(filename,content)['status'],400)
        self.assertEqual(self.request('/api/admin/regulation-file',dict(filename='bad.txt',content='not-base64'))['status'],400)
        self.assertEqual(self.upload('large.txt',b'x'*(5*1024*1024+1))['status'],400)
        self.assertEqual(self.request('/api/admin/regulation-summary',dict(chapters=[]))['status'],400)
        metadata=json.loads(self.request('/api/regulations')['body'])
        self.assertEqual(metadata['revision'],1)
        self.assertTrue(metadata['summary_current'])

    def test_branding_assets_persist_and_are_public(self):
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6GQAAAAASUVORK5CYII=')
        for kind in ('header','logo'):
            self.assertEqual(self.request('/api/admin/branding',dict(kind=kind,content=base64.b64encode(png).decode()))['status'],200)
        app.init()
        for kind in ('header','logo'):
            result=self.request('/api/branding/'+kind,cookie='')
            self.assertEqual(result['status'],200)
            self.assertEqual(result['body'],png)
            self.assertEqual(result['headers']['Content-Type'],'image/png')
        status=json.loads(self.request('/api/branding',cookie='')['body'])
        self.assertEqual(status,dict(header=True,logo=True))
        self.assertEqual(self.request('/api/admin/branding',dict(kind='logo',content=base64.b64encode(b'<svg/>').decode()))['status'],400)

    def test_stale_summary_cannot_be_confirmed_for_new_document(self):
        old=json.loads(self.request('/api/regulations')['body'])
        self.assertEqual(self.upload('nuovo.txt',b'Nuova versione')['status'],200)
        response=self.request('/api/admin/regulation-summary',dict(chapters=old['chapters'],document_revision=old['revision']))
        self.assertEqual(response['status'],400)
        self.assertFalse(json.loads(self.request('/api/regulations')['body'])['summary_current'])
