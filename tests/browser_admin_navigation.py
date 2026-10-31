"""Admin navigation, collapsed membership management and teacher visibility."""
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright, expect

with tempfile.TemporaryDirectory() as folder:
    app.DB = Path(folder) / 'navigation.sqlite3'
    app.today = lambda: date(2026, 10, 30)
    app.init()
    app.create_user('admin@example.org', 'Responsabile', 'abcdef', role='admin')
    app.create_user('teacher@example.org', 'Docente ammesso', 'abcdef')
    app.create_user('pending@example.org', 'Docente da ammettere', 'abcdef', status='pending')
    server = app.SchoolServer(('127.0.0.1', 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1280,'height':900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            expect(page.locator('#adminView')).to_be_hidden()
            page.locator('#username').fill('admin@example.org')
            page.locator('#password').fill('abcdef')
            page.get_by_role('button', name='Accedi', exact=True).click()
            expect(page.locator('#workspace')).to_be_visible()
            expect(page.locator('#adminPanel')).to_be_hidden()
            expect(page.locator('#adminView')).to_be_visible()
            assert page.locator('#rulesView').evaluate("el=>el.nextElementSibling.id") == 'adminView'
            page.locator('#adminView').click()
            expect(page.locator('#adminPanel')).to_be_visible()
            expect(page.locator('#workspace')).to_be_hidden()
            expect(page.locator('#rulesPanel')).to_be_hidden()
            expect(page.locator('#reportPanel')).to_be_hidden()
            expect(page.locator('#adminView')).to_have_attribute('aria-pressed','true')
            assert not page.locator('#adminUsers').evaluate('el=>el.open')
            expect(page.locator('#userSearch')).to_be_hidden()
            page.locator('#adminUsers > summary').click()
            expect(page.locator('#userSearch')).to_be_visible()
            expect(page.locator('#usersList')).to_contain_text('Docente ammesso')
            expect(page.locator('#usersList')).to_contain_text('Docente da ammettere')
            page.locator('#userSearch').fill('pending@example.org')
            expect(page.locator('#usersList .booking')).to_have_count(1)
            expect(page.locator('#usersList')).to_contain_text('In attesa')
            page.locator('#usersList').get_by_role('button',name='Approva',exact=True).click()
            expect(page.locator('#usersList')).to_contain_text('Attivo')
            expect(page.locator('#adminPanel')).to_be_visible()
            expect(page.locator('#workspace')).to_be_hidden()
            page.locator('#adminUsers > summary').click()
            expect(page.locator('#usersList')).to_be_hidden()
            page.locator('#rulesView').click()
            expect(page.locator('#rulesPanel')).to_be_visible()
            expect(page.locator('#adminPanel')).to_be_hidden()
            page.locator('#homeView').click()
            expect(page.locator('#workspace')).to_be_visible()
            expect(page.locator('#adminPanel')).to_be_hidden()
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#adminView').click()
            expect(page.locator('#adminPanel')).to_be_visible()
            page.locator('#adminUsers > summary').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#logout').click()
            expect(page.locator('#loginPanel')).to_be_visible()
            expect(page.locator('#adminView')).to_be_hidden()
            assert not page.locator('#adminUsers').evaluate('el=>el.open')
            page.locator('#username').fill('teacher@example.org')
            page.locator('#password').fill('abcdef')
            page.get_by_role('button',name='Accedi',exact=True).click()
            expect(page.locator('#workspace')).to_be_visible()
            expect(page.locator('#adminView')).to_be_hidden()
            expect(page.locator('#adminPanel')).to_be_hidden()
            page.evaluate("showView('admin')")
            expect(page.locator('#adminPanel')).to_be_hidden()
            expect(page.locator('#workspace')).to_be_visible()
            response = page.request.get(f'http://127.0.0.1:{server.server_port}/api/admin')
            assert response.status == 403
            assert not errors, errors
            browser.close()
            print('Browser OK: menu amministrazione separato, elenco iscritti chiuso, ricerca, approvazione, navigazione, mobile e permessi docente.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
