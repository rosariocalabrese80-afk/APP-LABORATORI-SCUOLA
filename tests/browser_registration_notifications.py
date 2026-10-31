"""Pending registration badges, periodic refresh and administration actions."""
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright,expect

with tempfile.TemporaryDirectory() as folder:
    app.DB=Path(folder)/'notifications.sqlite3'
    app.today=lambda:date(2026,10,30)
    app.init()
    app.create_user('admin@example.org','Responsabile','abcdef',role='admin')
    app.create_user('teacher@example.org','Docente attivo','abcdef')
    app.create_user('pending@example.org','Prima richiesta','abcdef',status='pending')
    app.create_user('excluded@example.org','Docente escluso','abcdef',status='suspended')
    server=app.SchoolServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context()
            public=browser.new_context()
            page=context.new_page()
            page.clock.install()
            base=f'http://127.0.0.1:{server.server_port}'
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base)
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            page.locator('#username').fill('admin@example.org')
            page.locator('#password').fill('abcdef')
            page.get_by_role('button',name='Accedi',exact=True).click()
            expect(page.locator('#workspace')).to_be_visible()
            expect(page.locator('#adminPendingBadge')).to_be_visible()
            expect(page.locator('#adminPendingBadge')).to_have_text('1')
            expect(page.locator('#adminView')).to_have_attribute('aria-label','Amministrazione, 1 iscrizione in attesa')
            # Opening the administration leaves the request pending and its badge visible.
            page.locator('#adminView').click()
            expect(page.locator('#adminPanel')).to_be_visible()
            expect(page.locator('#usersPendingBadge')).to_be_visible()
            expect(page.locator('#usersPendingBadge')).to_have_text('1')
            assert not page.locator('#adminUsers').evaluate('el=>el.open')
            page.locator('#homeView').click()
            # A new registration in another session is picked up by the 30-second refresh.
            registered=public.request.post(base+'/api/register',data=dict(email='new@example.org',name='Seconda richiesta',password='abcdef',confirm_password='abcdef'))
            assert registered.status==201
            page.clock.fast_forward(30000)
            expect(page.locator('#adminPendingBadge')).to_have_text('2')
            page.locator('#adminView').click()
            expect(page.locator('#usersPendingBadge')).to_have_text('2')
            page.locator('#adminUsers > summary').click()
            page.locator('#usersList .booking').filter(has_text='pending@example.org').get_by_role('button',name='Approva',exact=True).click()
            expect(page.locator('#adminPendingBadge')).to_have_text('1')
            expect(page.locator('#usersPendingBadge')).to_have_text('1')
            # Deleting the final pending request clears both badges immediately.
            page.once('dialog',lambda dialog:dialog.accept())
            page.locator('#usersList .booking').filter(has_text='new@example.org').get_by_role('button',name='Elimina',exact=True).click()
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            expect(page.locator('#usersPendingBadge')).to_be_hidden()
            expect(page.locator('#adminView')).to_have_attribute('aria-label','Amministrazione')
            expect(page.locator('#adminPendingBadge')).to_have_text('')
            expect(page.locator('#usersPendingBadge')).to_have_text('')
            # A response started before a newer local update cannot restore a stale badge.
            page.route('**/api/admin/notifications',lambda route:route.fulfill(status=200,content_type='application/json',body='{"pending_registrations":99}'))
            page.evaluate('async()=>{const request=refreshAdminNotifications();updatePendingBadges(0);await request}')
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            page.unroute('**/api/admin/notifications')
            # Focus refresh also discovers a request without leaving the current page.
            registered=public.request.post(base+'/api/register',data=dict(email='third@example.org',name='Terza richiesta',password='abcdef',confirm_password='abcdef'))
            assert registered.status==201
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(page.locator('#adminPendingBadge')).to_have_text('1')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#logout').click()
            expect(page.locator('#loginPanel')).to_be_visible()
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            expect(page.locator('#usersPendingBadge')).to_be_hidden()
            page.locator('#username').fill('teacher@example.org')
            page.locator('#password').fill('abcdef')
            page.get_by_role('button',name='Accedi',exact=True).click()
            expect(page.locator('#workspace')).to_be_visible()
            expect(page.locator('#adminView')).to_be_hidden()
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            assert page.request.get(base+'/api/admin/notifications').status==403
            assert public.request.get(base+'/api/admin/notifications').status==401
            page.clock.fast_forward(30000)
            expect(page.locator('#adminPendingBadge')).to_be_hidden()
            assert not errors,errors
            browser.close()
            print('Browser OK: numerini coerenti, registrazioni da altra sessione, aggiornamento periodico e al ritorno, approvazione, eliminazione, zero, mobile e riservatezza.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
