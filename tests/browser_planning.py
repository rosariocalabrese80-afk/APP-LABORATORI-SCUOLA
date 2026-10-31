"""Optional Playwright regression: closures, own edits, reports and backup."""
import sys
import tempfile
import threading
import shutil
import sqlite3
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory() as folder:
    app.DB = Path(folder) / 'planning.sqlite3'
    app.today = lambda: date(2026, 10, 30)
    app.init()
    app.create_user('admin@example.org','Admin','abcdef',role='admin')
    app.create_user('teacher@example.org','Docente','abcdef')
    app.create_user('other@example.org','Altro docente','abcdef')
    app.book(dict(lab=1,school_class='ALTRA',start='2026-11-02T11:00',end='2026-11-02T12:00'),dict(id=3,name='Altro docente'))
    server = app.SchoolServer(('127.0.0.1',0), app.Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            admin=browser.new_page()
            teacher=browser.new_page()
            errors=[]
            for page,email in [(admin,'admin@example.org'),(teacher,'teacher@example.org')]:
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#username').fill(email)
                page.locator('#password').fill('abcdef')
                page.get_by_role('button',name='Accedi',exact=True).click()
                page.locator('#workspace').wait_for(state='visible')
            assert teacher.locator('#workspace > aside > #reportPanel').count()==1
            booking=teacher.locator('#bookingForm').evaluate('el=>{const r=el.closest(".card").getBoundingClientRect();return {x:r.x,bottom:r.bottom}}')
            report=teacher.locator('#reportPanel').bounding_box()
            assert abs(report['x']-booking['x'])<2
            assert report['y']>=booking['bottom']
            fields=[teacher.locator('#'+name).bounding_box() for name in ['reportDate','reportPeriod','reportScope']]
            assert fields[0]['y']+fields[0]['height']<=fields[1]['y']
            assert fields[1]['y']+fields[1]['height']<=fields[2]['y']
            admin.locator('#adminView').click()
            admin.get_by_text('Calendario delle chiusure',exact=True).click()
            admin.locator('#closureMonth').fill('2026-11')
            admin.locator('#closureMonth').dispatch_event('change')
            admin.locator('#closureDays input[value="2026-11-03"]').check()
            admin.locator('#closureMessage').fill('Chiusura straordinaria')
            admin.get_by_role('button',name='Salva giorni spuntati').click()
            admin.get_by_text('Chiusure salvate.',exact=True).wait_for()
            teacher.reload()
            teacher.locator("#reset").click()
            teacher.locator('#closureAgenda').get_by_text('Chiusura straordinaria',exact=False).wait_for()
            teacher.locator('#lab').select_option('1')
            teacher.locator('#date').fill('2026-11-03')
            teacher.locator('#date').dispatch_event('change')
            assert teacher.locator('#save').is_disabled()
            assert teacher.locator('#hoursField input:enabled').count()==0
            teacher.locator('#date').fill('2026-11-02')
            teacher.locator('#date').dispatch_event('change')
            teacher.locator('#school_class').fill('MIA')
            teacher.locator('#hoursField input[value="9"]').check()
            teacher.locator('#save').click()
            teacher.get_by_text('Prenotazione salvata.',exact=True).wait_for()
            teacher.locator('#onlyMine').check()
            assert teacher.locator('#agenda .booking').count()==1
            teacher.locator('#agenda').get_by_role('button',name='Modifica',exact=True).click()
            assert teacher.locator('#hoursField input[value="9"]').is_checked()
            teacher.locator('#hoursField input[value="10"]').check()
            teacher.locator('#school_class').fill('MODIFICATA')
            teacher.locator('#save').click()
            teacher.locator('#agenda').get_by_text('Docente · Classe MODIFICATA',exact=True).wait_for()
            assert '10:00 – 11:00' in teacher.locator('#agenda').inner_text()
            teacher.locator('#onlyMine').uncheck()
            assert teacher.locator('#agenda .booking').count()==2
            teacher.locator('#calendarView').click()
            teacher.locator('#calendarDate').fill('2026-11-02')
            teacher.locator('#calendarDate').dispatch_event('change')
            teacher.locator('#calendarMine').check()
            assert teacher.locator('#calendarGrid .calendar-event').count()==1
            assert 'Chiusura straordinaria' in teacher.locator('#calendarGrid').inner_text()
            assert teacher.locator('#calendarReportSlot > #reportPanel').count()==1
            assert teacher.locator('#reportPanel').is_visible()
            teacher.locator('#reportDate').fill('2026-11-02')
            teacher.locator('#reportScope').select_option('mine')
            teacher.locator('#reportPeriod').select_option('week')
            with teacher.expect_download() as download:
                teacher.get_by_role('button',name='Scarica PDF',exact=True).click()
            file=Path(folder)/'report.pdf'
            download.value.save_as(file)
            assert file.read_bytes().startswith(b'%PDF-1.4')
            assert b'ALTRA' not in file.read_bytes()
            with teacher.expect_popup() as popup:
                teacher.get_by_role('button',name='Apri stampa',exact=True).click()
            popup.value.wait_for_load_state()
            assert 'MODIFICATA' in popup.value.locator('body').inner_text()
            assert 'ALTRA' not in popup.value.locator('body').inner_text()
            assert popup.value.get_by_role('button',name='Stampa / Salva come PDF').count()==1
            popup.value.wait_for_function("document.querySelector('header .letterhead').naturalWidth>0")
            assert popup.value.locator('h1').inner_text()=='PRENOTAZIONI SETTIMANALI'
            assert popup.value.locator('.booking strong').count()>0
            assert popup.value.locator('em').count()>0
            popup.value.emulate_media(media='print')
            assert popup.value.locator('.print-actions').is_hidden()
            assert popup.value.locator('.report-sheet > thead').evaluate("el=>getComputedStyle(el).display")=='table-header-group'
            browser_pdf=popup.value.pdf(format='A4',print_background=True,prefer_css_page_size=True)
            assert browser_pdf.startswith(b'%PDF-')
            admin.get_by_text('Backup completo',exact=True).click()
            with admin.expect_download() as download:
                admin.get_by_role('link',name='Scarica backup SQLite').click()
            file=Path(folder)/'download.sqlite3'
            download.value.save_as(file)
            with sqlite3.connect(file) as db:
                assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
                assert db.execute('select count(*) from closures').fetchone()[0]==1
                assert db.execute('select count(*) from bookings').fetchone()[0]==2
            teacher.set_viewport_size(dict(width=390,height=844))
            teacher.locator('#homeView').click()
            assert teacher.locator('#reportDate').input_value()=='2026-11-02'
            assert teacher.locator('#reportPeriod').input_value()=='week'
            assert teacher.locator('#reportScope').input_value()=='mine'
            assert teacher.evaluate('document.documentElement.scrollWidth <= innerWidth')
            report=teacher.locator('#reportPanel').bounding_box()
            assert report['width']<=390
            assert teacher.locator('#reportPanel').is_visible()
            for view,panel in [('rulesView','rulesPanel'),('profileView','profilePanel')]:
                teacher.locator('#'+view).click()
                teacher.locator('#'+panel).wait_for(state='visible')
                assert teacher.locator('#reportPanel').is_hidden()
            assert not errors, errors
            print('Browser OK: chiusure spuntabili, blocco, avvisi, filtro personale, modifica, PDF, stampa, backup e mobile.')
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
