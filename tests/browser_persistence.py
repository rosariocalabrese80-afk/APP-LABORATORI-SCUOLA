"""Verify records through the browser across a complete WSGI process restart.

Optional development test: requires Playwright and Chromium, not used by the app.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright

SERVER = """
from datetime import date
from wsgiref.simple_server import make_server
import app
app.today = lambda: date(2026,10,30)
from wsgi import application
with make_server('127.0.0.1',0,application) as server:
    print(server.server_port, flush=True)
    server.serve_forever()
"""


def launch(database, log):
    process = subprocess.Popen(
        [sys.executable, '-c', SERVER], cwd=app.ROOT,
        env={**os.environ, 'LAB_DB': str(database), 'COOKIE_SECURE': '0'},
        stdout=subprocess.PIPE, stderr=log, text=True)
    port = process.stdout.readline().strip()
    if not port.isdigit():
        process.terminate()
        process.wait(timeout=10)
        raise RuntimeError('Server WSGI non avviato; controllare il log del test.')
    return process, 'http://127.0.0.1:' + port


def login(page, base, email):
    page.goto(base)
    page.locator('#username').fill(email)
    page.locator('#password').fill('abcdef')
    page.get_by_role('button', name='Accedi', exact=True).click()
    page.locator('#workspace').wait_for(state='visible')
    assert page.get_by_role('button', name='Prenotazioni e agenda', exact=True).is_visible()


with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    app.DB = directory / 'persistent-data' / 'laboratori.sqlite3'
    app.today = lambda: date(2026, 10, 30)
    app.init()
    app.create_user('admin@example.com', 'Amministratore', 'abcdef', role='admin')
    app.create_user('teacher@example.com', 'Docente persistente', 'abcdef')
    with (directory / 'server.log').open('w') as log, sync_playwright() as playwright:
        browser = None
        process, base = launch(app.DB, log)
        try:
            browser = playwright.chromium.launch(
                executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            login(page, base, 'teacher@example.com')
            page.locator('#lab').select_option('1')
            page.locator('#date').fill('2026-11-02')
            page.locator('#school_class').fill('2B')
            for hour in (8, 10):
                page.locator(f'input[name="hours"][value="{hour}"]').check()
            page.locator('#save').click()
            page.get_by_text('2 ore prenotate.', exact=True).wait_for()
            assert page.locator('#agenda article').count() == 2
            # Close the browser completely: no context or cookies are reused.
            browser.close()
            browser = None
            # Stop and restart the hosting process with the same external DB.
            process.terminate()
            process.wait(timeout=10)
            process, base = launch(app.DB, log)
            browser = playwright.chromium.launch(
                executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            login(page, base, 'teacher@example.com')
            page.locator('#filterDate').fill('2026-11-02')
            assert page.locator('#agenda article').count() == 2
            assert 'Docente persistente' in page.locator('#agenda').inner_text()
            assert 'Classe 2B' in page.locator('#agenda').inner_text()
            assert '08:00 – 09:00' in page.locator('#agenda').inner_text()
            assert '10:00 – 11:00' in page.locator('#agenda').inner_text()
            page.locator('#calendarView').click()
            page.locator('#calendarDate').fill('2026-11-02')
            assert page.locator('#calendarGrid .calendar-event').count() == 2
            with app.connect() as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert db.execute('SELECT count(*) FROM bookings').fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM users WHERE status='active'").fetchone()[0] == 2
            print('OK: account e due prenotazioni presenti dopo chiusura completa del browser e riavvio del processo WSGI; agenda, calendario e integrità SQLite verificati.')
        finally:
            if browser is not None:
                browser.close()
            process.terminate()
            process.wait(timeout=10)
