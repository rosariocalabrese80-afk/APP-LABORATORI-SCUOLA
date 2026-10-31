"""Personal profile and password changes for teachers and administrators."""
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright, expect

with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'profile.sqlite3'
    app.today=lambda:date(2026,10,30)
    app.init()
    app.create_user('admin@example.org','Responsabile','abcdef',role='admin')
    app.create_user('teacher@example.org','Docente <prova>','abcdef')
    app.create_user('pending@example.org','Da approvare','abcdef',status='pending')
    app.book(dict(lab=1,school_class='2B',start='2026-11-02T09:00',end='2026-11-02T10:00'),dict(id=2,name='Docente <prova>'))
    server=app.SchoolServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            contexts=[browser.new_context() for _ in range(3)]
            teacher,second,admin=[context.new_page() for context in contexts]
            base=f'http://127.0.0.1:{server.server_port}'
            errors=[]
            def login(page,email,password='abcdef'):
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base)
                expect(page.locator('#profilePanel')).to_be_hidden()
                page.locator('#username').fill(email)
                page.locator('#password').fill(password)
                page.get_by_role('button',name='Accedi',exact=True).click()
                expect(page.locator('#workspace')).to_be_visible()
            login(teacher,'teacher@example.org')
            login(second,'teacher@example.org')
            login(admin,'admin@example.org')
            expect(teacher.locator('#passwordPanel')).to_be_hidden()
            teacher.locator('#profileView').click()
            expect(teacher.locator('#profilePanel')).to_be_visible()
            expect(teacher.locator('#workspace')).to_be_hidden()
            expect(teacher.locator('#reportPanel')).to_be_hidden()
            expect(teacher.locator('#profileView')).to_have_attribute('aria-pressed','true')
            expect(teacher.locator('#profileInfo')).to_contain_text('Docente <prova>')
            expect(teacher.locator('#profileInfo')).to_contain_text('teacher@example.org')
            expect(teacher.locator('#profileInfo')).to_contain_text('Approvato e attivo')
            expect(teacher.locator('#profileInfo')).to_contain_text('ora italiana')
            expect(teacher.locator('#profileInfo')).not_to_contain_text('admin@example.org')
            expect(teacher.locator('#profileAdmin')).to_be_hidden()
            expect(teacher.locator('#profileBookings')).to_contain_text('conservate: 1')
            teacher.locator('#profileMyBookings').click()
            expect(teacher.locator('#workspace')).to_be_visible()
            expect(teacher.locator('#onlyMine')).to_be_checked()
            expect(teacher.locator('#agenda .booking')).to_have_count(1)
            teacher.locator('#profileView').click()
            teacher.set_viewport_size({'width':390,'height':844})
            assert teacher.evaluate('document.documentElement.scrollWidth <= innerWidth')
            teacher.locator('#currentPassword').fill('wrong-password')
            teacher.locator('#changedPassword').fill('new-password')
            teacher.locator('#confirmedPassword').fill('new-password')
            teacher.get_by_role('button',name='Salva e termina le sessioni',exact=True).click()
            expect(teacher.locator('#message')).to_contain_text('Password attuale non valida')
            expect(teacher.locator('#profilePanel')).to_be_visible()
            teacher.locator('#currentPassword').fill('abcdef')
            teacher.get_by_role('button',name='Salva e termina le sessioni',exact=True).click()
            expect(teacher.locator('#loginPanel')).to_be_visible()
            expect(teacher.locator('#profilePanel')).to_be_hidden()
            assert second.request.get(base+'/api/data').status==401
            teacher.locator('#username').fill('teacher@example.org')
            teacher.locator('#password').fill('new-password')
            teacher.get_by_role('button',name='Accedi',exact=True).click()
            expect(teacher.locator('#workspace')).to_be_visible()
            admin.locator('#profileView').click()
            expect(admin.locator('#profileAdmin')).to_be_visible()
            expect(admin.locator('#profileInfo')).to_contain_text('admin@example.org')
            expect(admin.locator('#profileInfo')).to_contain_text('Amministratore')
            expect(admin.locator('#profileAdminSummary')).to_contain_text('Iscritti in attesa: 1')
            expect(admin.locator('#profileAdminSummary')).to_contain_text('Amministratori attivi: 1')
            admin.locator('#profileOpenAdmin').click()
            expect(admin.locator('#adminPanel')).to_be_visible()
            expect(admin.locator('#profilePanel')).to_be_hidden()
            admin.locator('#profileView').click()
            admin.locator('#currentPassword').fill('abcdef')
            admin.locator('#changedPassword').fill('admin-new-password')
            admin.locator('#confirmedPassword').fill('admin-new-password')
            admin.get_by_role('button',name='Salva e termina le sessioni',exact=True).click()
            expect(admin.locator('#loginPanel')).to_be_visible()
            admin.locator('#username').fill('admin@example.org')
            admin.locator('#password').fill('admin-new-password')
            admin.get_by_role('button',name='Accedi',exact=True).click()
            expect(admin.locator('#adminView')).to_be_visible()
            assert not errors,errors
            browser.close()
            print('Browser OK: profilo personale docente/admin, dati corretti, permessi, riepiloghi, collegamenti, cambio password, revoca sessioni e mobile.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
