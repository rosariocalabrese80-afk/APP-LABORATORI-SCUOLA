"""Agenda dates toggle combined with laboratory and ownership filters."""
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
    app.DB = Path(folder) / 'agenda.sqlite3'
    app.today = lambda: date(2026,10,30)
    app.init()
    app.create_user('first@example.org','Primo docente','abcdef')
    app.create_user('second@example.org','Secondo docente','abcdef')
    app.create_user('admin@example.org','Responsabile','abcdef',role='admin')
    for day,lab,hour,user in [('2026-11-02',1,9,1),('2026-11-03',1,9,1),
                              ('2026-11-02',1,10,2),('2026-11-03',2,11,1),('2026-11-02',2,12,2)]:
        app.book(dict(lab=lab,school_class='2B',start=f'{day}T{hour:02d}:00',end=f'{day}T{hour+1:02d}:00'),
                 dict(id=user,name='Primo docente' if user==1 else 'Secondo docente'))
    server=app.SchoolServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#username').fill('first@example.org')
            page.locator('#password').fill('abcdef')
            page.get_by_role('button',name='Accedi',exact=True).click()
            expect(page.locator('#workspace')).to_be_visible()
            assert page.get_by_role('heading',name='Laboratori della scuola',exact=True).count()==0
            page.locator('#filterDate').fill('2026-11-02')
            page.locator('#filterDate').dispatch_event('change')
            expect(page.locator('#agenda .booking')).to_have_count(3)
            page.locator('#filterLab').select_option('1')
            expect(page.locator('#agenda .booking')).to_have_count(2)
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('')
            expect(page.locator('#filterLab')).to_have_value('1')
            expect(page.locator('#reset')).to_have_attribute('aria-pressed','true')
            expect(page.locator('#reset')).to_have_text('Torna al 2 novembre 2026')
            expect(page.locator('#agenda .booking')).to_have_count(3)
            page.locator('#onlyMine').check()
            expect(page.locator('#agenda .booking')).to_have_count(2)
            expect(page.locator('#agendaFilterStatus')).to_contain_text('Solo le mie prenotazioni')
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            expect(page.locator('#onlyMine')).to_be_checked()
            expect(page.locator('#filterLab')).to_have_value('1')
            expect(page.locator('#agenda .booking')).to_have_count(1)
            expect(page.locator('#reset')).to_have_text('Mostra tutte le date')
            page.locator('#reset').click()
            page.locator('#filterLab').select_option('2')
            expect(page.locator('#agenda .booking')).to_have_count(1)
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            expect(page.locator('#filterLab')).to_have_value('2')
            expect(page.locator('#agenda .booking')).to_have_count(0)
            page.locator('#reset').click()
            page.locator('#filterLab').select_option('')
            expect(page.locator('#agenda .booking')).to_have_count(3)
            page.locator('#onlyMine').uncheck()
            expect(page.locator('#agenda .booking')).to_have_count(5)
            # Reloading data within the app preserves all-date mode and its return date.
            page.evaluate('async()=>await load()')
            expect(page.locator('#filterDate')).to_have_value('')
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            expect(page.locator('#agenda .booking')).to_have_count(3)
            page.locator('#reset').click()
            # Choosing a date manually ends all-date mode and records the new return date.
            page.locator('#filterDate').fill('2026-11-03')
            page.locator('#filterDate').dispatch_event('change')
            expect(page.locator('#reset')).to_have_attribute('aria-pressed','false')
            expect(page.locator('#agenda .booking')).to_have_count(2)
            page.locator('#reset').click()
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-03')
            # Opening a day from the calendar also restores the correct toggle state.
            page.locator('#calendarView').click()
            page.locator('#calendarDate').fill('2026-11-02')
            page.locator('#calendarDate').dispatch_event('change')
            page.locator('#calendarGrid .calendar-event').first.click()
            page.locator('#calendarOpenAgenda').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            expect(page.locator('#reset')).to_have_attribute('aria-pressed','false')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#reset').click()
            expect(page.locator('#reset')).to_have_text('Torna al 2 novembre 2026')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#reset').click()
            expect(page.locator('#filterDate')).to_have_value('2026-11-02')
            assert not errors,errors
            browser.close()
            print('Browser OK: tutte le date reversibili, filtri laboratorio/personali combinati, selezione manuale, aggiornamento, calendario e mobile.')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
