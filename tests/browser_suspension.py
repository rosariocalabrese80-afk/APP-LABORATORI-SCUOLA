"""Optional browser test: administrator suspends a lab while a teacher is online."""
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright


def login(page,base,email):
    page.goto(base)
    page.locator('#username').fill(email)
    page.locator('#password').fill('abcdef')
    page.get_by_role('button',name='Accedi',exact=True).click()
    page.locator('#workspace').wait_for(state='visible')


with tempfile.TemporaryDirectory() as temporary:
 app.DB=Path(temporary)/'suspension.sqlite3';app.today=lambda:date(2026,10,30);app.init()
 app.create_user('admin@example.com','Responsabile','abcdef',role='admin')
 app.create_user('teacher@example.com','Docente prova','abcdef')
 app.book(dict(lab=1,school_class='2B',start='2026-11-02T09:00',end='2026-11-02T10:00'),{'id':2,'name':'Docente prova'})
 server=app.SchoolServer(('127.0.0.1',0),app.Handler)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
   admin_context=browser.new_context();teacher_context=browser.new_context(viewport={'width':390,'height':844})
   admin=admin_context.new_page();teacher=teacher_context.new_page();errors=[]
   for page in (admin,teacher):page.on('pageerror',lambda e:errors.append(str(e)))
   base='http://127.0.0.1:'+str(server.server_port)
   login(admin,base,'admin@example.com');login(teacher,base,'teacher@example.com')
   teacher.locator('#lab').select_option('1');teacher.locator('#date').fill('2026-11-02');teacher.locator('#filterDate').fill('2026-11-02');teacher.locator('#school_class').fill('2B')
   teacher.wait_for_function("!document.querySelector('#hoursField input[value=\"8\"]').disabled")
   admin.locator('#adminView').click()
   admin.get_by_text('Gestisci laboratori',exact=True).click()
   row=admin.locator('#adminLabs [data-lab-id="1"]')
   row.get_by_role('button',name='Sospendi temporaneamente',exact=True).click()
   admin.locator('#labSuspensionDialog').wait_for(state='visible')
   notice='Manutenzione delle postazioni.\nIl laboratorio tornerà disponibile dopo i lavori.'
   admin.get_by_label('Comunicazione agli utenti',exact=True).fill(notice)
   admin.get_by_role('button',name='Conferma sospensione',exact=True).click()
   admin.get_by_text('Sospensione temporanea salvata. La comunicazione sarà mostrata agli utenti.',exact=True).wait_for()
   teacher.locator('#lab').select_option('2');teacher.locator('#lab').select_option('1')
   teacher.locator('#labSuspensionNotice').wait_for(state='visible')
   assert teacher.locator('#labSuspensionNoticeMessage').inner_text()==notice
   assert teacher.locator('#hoursField input:not([disabled])').count()==0
   assert teacher.locator('#save').is_disabled()
   teacher.get_by_role('button',name='Ho capito',exact=True).click()
   assert teacher.locator('#agenda article').count()==1
   assert teacher.locator('#labSuspensionStatus').inner_text()==notice
   assert teacher.evaluate('document.documentElement.scrollWidth<=innerWidth')
   admin.once('dialog',lambda d:d.accept())
   row.get_by_role('button',name='Termina sospensione',exact=True).click()
   admin.get_by_text('Operazione completata.',exact=True).wait_for()
   teacher.locator('#lab').select_option('2');teacher.locator('#lab').select_option('1')
   teacher.wait_for_function("!document.querySelector('#hoursField input[value=\"8\"]').disabled")
   assert teacher.locator('#labSuspensionNotice').is_hidden()
   teacher.locator('#hoursField input[value="8"]').check();teacher.locator('#save').click()
   teacher.get_by_text('Prenotazione salvata.',exact=True).wait_for()
   assert teacher.locator('#agenda article').count()==2
   # Suspension after the teacher already selected a free hour must still block saving.
   teacher.locator('#hoursField input[value="10"]').check()
   row.get_by_role('button',name='Sospendi temporaneamente',exact=True).click()
   admin.locator('#labSuspensionMessage').fill('Seconda sospensione: verifica tecnica in corso.')
   admin.locator('#confirmLabSuspension').click()
   admin.get_by_text('Sospensione temporanea salvata. La comunicazione sarà mostrata agli utenti.',exact=True).wait_for()
   teacher.locator('#save').click()
   teacher.locator('#labSuspensionNotice').wait_for(state='visible')
   assert teacher.locator('#labSuspensionNoticeMessage').inner_text()=='Seconda sospensione: verifica tecnica in corso.'
   with app.connect() as db:assert db.execute('SELECT count(*) FROM bookings').fetchone()[0]==2
   assert not errors,errors
   print('Browser OK: comunicazione admin, avviso al docente con sessione già aperta, blocco ore, conservazione prenotazioni, riattivazione, sospensione prima del salvataggio e mobile.')
   browser.close()
 finally:server.shutdown();server.server_close();thread.join()
