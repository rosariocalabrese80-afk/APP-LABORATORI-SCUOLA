import sys,tempfile,threading,shutil
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright
with tempfile.TemporaryDirectory() as temp:
 app.DB=Path(temp)/'calendar.db';app.today=lambda:date(2026,10,30);app.init()
 app.create_user('admin@example.com','Admin','abcdef',role='admin')
 app.create_user('teacher@example.com','Docente prova','abcdef')
 for lab,day,hour,cls in [(1,'2026-10-30',9,'2B'),(2,'2026-10-30',9,'3A'),(3,'2026-11-02',11,'1C'),(1,'2026-11-30',13,'4A'),(1,'2026-10-30',13,'Classe con descrizione estesa per verificare la leggibilità delle prenotazioni del venerdì')]:
  app.book(dict(lab=lab,school_class=cls,start=f'{day}T{hour:02d}:00',end=f'{day}T{hour+1:02d}:00'),{'id':2,'name':'Docente prova con nome e cognome estesi per verificare il testo senza tagli'})
 server=app.SchoolServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='America/Los_Angeles');errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:'+str(server.server_port))
   page.locator('#username').fill('teacher@example.com');page.locator('#password').fill('abcdef');page.get_by_role('button',name='Accedi',exact=True).click()
   page.locator('#workspace').wait_for(state='visible')
   page.locator('#calendarView').click();page.locator('#calendarPanel').wait_for(state='visible')
   assert page.locator('#workspace').is_hidden()
   cell=page.locator('#calendarGrid td[data-date="2026-10-30"][data-hour="9"]')
   assert cell.locator('.calendar-event').count()==2
   assert page.locator('#calendarSummary').inner_text().startswith('3 prenotazioni')
   # Friday must fit completely, including the last hourly slot and long text.
   assert page.locator('#calendarGrid thead th').count()==8
   for width in (1440,1280,1100,1024,800):
    page.set_viewport_size({'width':width,'height':1000})
    assert page.locator('#calendarGrid').evaluate('''el=>{const grid=el.getBoundingClientRect();return [...el.querySelectorAll('td[data-date="2026-10-30"]')].every(cell=>{const r=cell.getBoundingClientRect();return r.left>=grid.left&&r.right<=grid.right-1})}''')
    assert page.locator('#calendarGrid td[data-date="2026-10-30"] .calendar-event').evaluate_all('''events=>events.every(event=>[event,...event.children].every(el=>el.scrollWidth<=el.clientWidth+1&&el.scrollHeight<=el.clientHeight+1))''')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.set_viewport_size({'width':1440,'height':1000})
   cell.locator('.calendar-event').first.click();page.locator('#calendarDialog').wait_for(state='visible')
   assert 'Docente: Docente prova' in page.locator('#calendarDetails').inner_text()
   assert 'Classe: 2B' in page.locator('#calendarDetails').inner_text()
   page.locator('#calendarOpenAgenda').click();page.locator('#workspace').wait_for(state='visible')
   assert page.locator('#filterDate').input_value()=='2026-10-30'
   page.locator('#calendarView').click();page.locator('#calendarLab').select_option('2')
   assert page.locator('#calendarGrid .calendar-event').count()==1
   page.locator('#calendarLab').select_option('')
   page.locator('#calendarNext').click()
   assert page.locator('#calendarGrid .calendar-event').count()==1
   assert '1C' in page.locator('#calendarGrid').inner_text()
   page.locator('#monthView').click()
   assert 'novembre 2026' in page.locator('#calendarTitle').inner_text()
   assert page.locator('.calendar-day[data-date^="2026-11"] .calendar-event').count()==2
   assert page.locator('#calendarNext').is_disabled()
   assert page.locator('.calendar-day[data-date="2026-12-01"]').inner_text().endswith('Fuori periodo')
   page.locator('#calendarPrev').click();assert 'ottobre 2026' in page.locator('#calendarTitle').inner_text()
   page.locator('#calendarPrev').click();assert 'settembre 2026' in page.locator('#calendarTitle').inner_text()
   assert page.locator('#calendarPrev').is_disabled()
   page.locator('#calendarToday').click();assert 'ottobre 2026' in page.locator('#calendarTitle').inner_text()
   # Date helpers remain correct through month ends, year ends and DST.
   assert page.evaluate("moveDays('2026-10-25',1)")=='2026-10-26'
   assert page.evaluate("monday('2027-01-01')")=='2026-12-28'
   assert page.evaluate("monthMove('2026-12-31',1)")=='2027-01-01'
   page.set_viewport_size({'width':390,'height':844})
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
   assert page.locator('#calendarGrid').evaluate('(el)=>el.scrollWidth>el.clientWidth')
   page.locator('#weekView').click()
   friday=page.locator('#calendarGrid td[data-date="2026-10-30"][data-hour="13"] .calendar-event')
   friday.scroll_into_view_if_needed()
   assert friday.evaluate('''event=>{const grid=document.getElementById('calendarGrid').getBoundingClientRect();const r=event.getBoundingClientRect();return r.left>=grid.left&&r.right<=grid.right}''')
   page.locator('#calendarRefresh').click();page.get_by_text('Calendario aggiornato.',exact=True).wait_for()
   page.locator('#logout').click();page.locator('#loginPanel').wait_for(state='visible')
   assert page.locator('#calendarPanel').is_hidden()
   assert page.locator('#viewNav').is_hidden()
   assert not errors,errors
   print('Browser OK: settimana con prenotazioni simultanee, mese, dettagli, filtro laboratorio, navigazione, limiti storico, aggiornamento, date/DST, logout e layout mobile.')
   browser.close()
 finally:server.shutdown();server.server_close();thread.join()
