"""Logout/re-login defaults, cross-account cleanup and persistent data."""
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
    clock={'day':date(2026,10,30)}
    app.DB=Path(folder)/'defaults.sqlite3'
    app.today=lambda:clock['day']
    app.init()
    app.create_user('admin@example.org','Responsabile','abcdef',role='admin')
    app.create_user('teacher@example.org','Docente','abcdef')
    app.book(dict(lab=1,school_class='2B',start='2026-11-02T09:00',end='2026-11-02T10:00',notes='Nota conservata'),dict(id=1,name='Responsabile'))
    app.manage_closure(dict(day='2026-11-03',message='Chiusura conservata',blocked=True,visible=True))
    server=app.SchoolServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            def login(email):
                page.locator('#username').fill(email)
                page.locator('#password').fill('abcdef')
                page.get_by_role('button',name='Accedi',exact=True).click()
                expect(page.locator('#workspace')).to_be_visible()
            def assert_defaults(day,admin):
                expect(page.locator('#homeView')).to_have_attribute('aria-pressed','true')
                expect(page.locator('#filterDate')).to_have_value(day)
                expect(page.locator('#filterLab')).to_have_value('')
                expect(page.locator('#onlyMine')).not_to_be_checked()
                expect(page.locator('#calendarMine')).not_to_be_checked()
                expect(page.locator('#date')).to_have_value(day)
                assert not page.locator('#date').evaluate('el=>el.validity.customError')
                for ident in ['lab','school_class','notes','editBookingId','userSearch','newName','newEmail','newPassword','closureMessage','newLab','resetPassword','labSuspensionMessage','currentPassword','changedPassword','confirmedPassword']:
                    expect(page.locator('#'+ident)).to_have_value('')
                expect(page.locator('#cancelEdit')).to_be_hidden()
                expect(page.locator('#save')).to_have_text('Prenota laboratorio')
                expect(page.locator('#reportDate')).to_have_value(day)
                expect(page.locator('#reportPeriod')).to_have_value('day')
                expect(page.locator('#reportScope')).to_have_value('all')
                assert page.locator('details[open]').count()==0
                assert page.locator('dialog[open]').count()==0
                assert page.locator('#closureDays input:checked').count()==0
                expect(page.locator('#closureBlocked')).to_be_checked()
                expect(page.locator('#closureVisible')).to_be_checked()
                if admin:expect(page.locator('#bookingUser')).to_have_value('1')
                else:expect(page.locator('#adminView')).to_be_hidden()
                page.locator('#calendarView').click()
                expect(page.locator('#calendarDate')).to_have_value(day)
                expect(page.locator('#calendarLab')).to_have_value('')
                expect(page.locator('#weekView')).to_have_attribute('aria-pressed','true')
                page.locator('#homeView').click()
            page.locator('#username').fill('admin@example.org')
            page.locator('#password').fill('errata')
            page.get_by_role('button',name='Accedi',exact=True).click()
            expect(page.locator('#message')).to_contain_text('Credenziali non valide')
            expect(page.locator('#username')).to_have_value('admin@example.org')
            login('admin@example.org')
            assert_defaults('2026-10-30',True)
            # Defaults must not be reapplied during navigation within one session.
            page.locator('#filterDate').fill('2026-11-02')
            page.locator('#filterDate').dispatch_event('change')
            page.locator('#filterLab').select_option('1')
            page.locator('#onlyMine').check()
            page.locator('#agenda').get_by_role('button',name='Modifica',exact=True).click()
            expect(page.locator('#editBookingId')).not_to_have_value('')
            page.locator('#reportDate').fill('2026-11-04')
            page.locator('#reportPeriod').select_option('month')
            page.locator('#reportScope').select_option('mine')
            page.locator('#calendarView').click()
            page.locator('#monthView').click()
            page.locator('#calendarDate').fill('2026-11-12')
            page.locator('#calendarDate').dispatch_event('change')
            page.locator('#calendarLab').select_option('1')
            page.locator('#calendarMine').check()
            page.locator('#homeView').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            expect(page.locator('#filterLab')).to_have_value('1')
            expect(page.locator('#onlyMine')).to_be_checked()
            expect(page.locator('#editBookingId')).not_to_have_value('')
            expect(page.locator('#reportPeriod')).to_have_value('month')
            page.locator('#adminView').click()
            page.locator('#adminUsers > summary').click()
            page.locator('#userSearch').fill('teacher')
            page.get_by_text('Crea un amministratore o docente',exact=True).click()
            page.locator('#newName').fill('Bozza non salvata')
            page.locator('#newEmail').fill('draft@example.org')
            page.locator('#newPassword').fill('password-da-cancellare')
            page.get_by_text('Calendario delle chiusure',exact=True).click()
            page.locator('#closureMonth').fill('2026-11')
            page.locator('#closureMonth').dispatch_event('change')
            page.locator('#closureDays input[value="2026-11-05"]').check()
            page.locator('#closureMessage').fill('Comunicazione non salvata')
            page.locator('#closureBlocked').uncheck()
            page.locator('#closureVisible').uncheck()
            page.get_by_text('Identità della scuola e regolamento',exact=True).click()
            page.locator('#brandingFile').set_input_files({'name':'draft.png','mimeType':'image/png','buffer':b'not-uploaded'})
            page.evaluate("document.getElementById('date').setCustomValidity('Errore precedente da cancellare')")
            page.locator('#profileView').click()
            page.locator('#currentPassword').fill('da-cancellare')
            page.locator('#logout').click()
            expect(page.locator('#loginPanel')).to_be_visible()
            assert page.locator('details[open]').count()==0
            assert page.locator('#brandingFile').evaluate('el=>el.files.length')==0
            assert page.evaluate('state.bookings.length===0&&adminState.users.length===0&&rulesState===null')
            # A new login uses today's server date even if the tab was open overnight.
            clock['day']=date(2026,11,2)
            login('admin@example.org')
            assert_defaults('2026-11-02',True)
            expect(page.locator('#agenda')).to_contain_text('Nota conservata')
            page.locator('#profileView').click()
            page.locator('#logout').click()
            expect(page.locator('#loginPanel')).to_be_visible()
            login('teacher@example.org')
            assert_defaults('2026-11-02',False)
            expect(page.locator('#agenda')).to_contain_text('Nota conservata')
            # Expiration returns to a clean login too, without deleting saved data.
            page.locator('#reportPeriod').select_option('month')
            with app.connect() as db:
                db.execute('DELETE FROM sessions WHERE user_id=2')
            page.locator('#calendarView').click()
            expect(page.locator('#loginPanel')).to_be_visible()
            assert page.evaluate('state.bookings.length===0&&adminState.users.length===0')
            login('teacher@example.org')
            assert_defaults('2026-11-02',False)
            with app.connect() as db:
                assert db.execute('SELECT count(*) FROM users').fetchone()[0]==2
                assert db.execute('SELECT notes FROM bookings').fetchone()[0]=='Nota conservata'
                assert db.execute('SELECT message FROM closures').fetchone()[0]=='Chiusura conservata'
            assert not errors,errors
            browser.close()
            print('Browser OK: reset dopo logout e nuovo accesso, data corrente, filtri/moduli/menu/file azzerati, sessione corrente conservata e dati persistenti intatti.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
