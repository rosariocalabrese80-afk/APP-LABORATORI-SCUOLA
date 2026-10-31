"""Optional browser test for school identity, regulations and admin uploads."""
import base64
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6GQAAAAASUVORK5CYII=')
with tempfile.TemporaryDirectory() as temporary:
 app.DB=Path(temporary)/'school.sqlite3';app.today=lambda:date(2026,10,30);app.init()
 app.create_user('admin@example.com','Admin','abcdef',role='admin')
 app.create_user('teacher@example.com','Docente','abcdef')
 server=app.SchoolServer(('127.0.0.1',0),app.Handler)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   base='http://127.0.0.1:'+str(server.server_port)
   page.goto(base);assert page.locator('#schoolHeading h1').inner_text()=='Laboratori IC2 Giovanni Paolo II di Policoro'
   assert page.locator('#schoolHeading p').inner_text()=='Pianifica le attività e prenota il laboratorio.'
   page.locator('#username').fill('admin@example.com');page.locator('#password').fill('abcdef');page.get_by_role('button',name='Accedi',exact=True).click()
   page.locator('#workspace').wait_for(state='visible')
   with page.expect_download() as download:
    page.locator('#homeRegulationDownload').click()
   target=Path(temporary)/'download.docx';download.value.save_as(target)
   assert target.read_bytes()==(app.ROOT/'documents'/'regolamento-laboratori.docx').read_bytes()
   page.locator('.school-admin > summary').click()
   for kind in ('header','logo'):
    page.locator('#brandingKind').select_option(kind)
    page.locator('#brandingFile').set_input_files({'name':'test.png','mimeType':'image/png','buffer':PNG})
    with page.expect_response(lambda r:r.url.endswith('/api/admin/branding') and r.request.method=='POST') as saved:
     page.get_by_role('button',name='Salva immagine',exact=True).click()
    assert saved.value.status==200
   page.locator('#schoolLetterhead').wait_for(state='visible')
   page.locator('#rulesView').click();page.locator('#rulesPanel').wait_for(state='visible')
   assert page.locator('#rulesIndex li').count()==10
   assert page.locator('#rulesArticle .rules-card').count()==10
   assert page.locator('#schoolLetterhead').is_hidden()
   assert page.locator('#schoolHeading').is_hidden()
   assert page.locator('#schoolLogo').is_visible()
   page.locator('#rulesIndex a[href="#regolamenti/accesso-chiavi"]').click()
   page.locator('#rulesArticle h2').filter(has_text='Prenotazioni, accesso e chiavi').wait_for()
   assert '131, 132 e 133' in page.locator('#rulesArticle').inner_text()
   page.locator('#rulesIndex a[href="#regolamenti/carrelli-mobili"]').click()
   page.locator('#rulesArticle').get_by_text('Il collaboratore verifica il collegamento alla rete elettrica',exact=False).wait_for()
   page.go_back();page.wait_for_url('**/#regolamenti/accesso-chiavi')
   page.locator('#homeView').click();assert '#regolamenti' not in page.url
   page.locator('#schoolLetterhead').wait_for(state='visible')
   page.locator('#regulationFile').set_input_files({'name':'nuovo-regolamento.txt','mimeType':'text/plain','buffer':b'Nuovo regolamento completo per la scuola.'})
   page.get_by_role('button',name='Pubblica il documento completo',exact=True).click()
   page.get_by_text('Documento pubblicato. Controlla e conferma la sintesi per questa nuova versione.',exact=True).wait_for()
   assert 'nuovo-regolamento.txt' in page.locator('#homeRegulationName').inner_text()
   page.locator('#homeRulesLink').click();page.locator('#rulesWarning').wait_for(state='visible')
   page.locator('#homeView').click()
   page.get_by_text('Modifica e conferma i capitoli della sintesi',exact=True).click()
   page.locator('#summaryBody0').fill('Testo essenziale aggiornato per il nuovo regolamento.')
   page.get_by_role('button',name='Salva la sintesi per il documento attuale',exact=True).click()
   page.get_by_text('Sintesi aggiornata e confermata per il documento attuale.',exact=True).wait_for()
   page.locator('#rulesView').click();assert page.locator('#rulesWarning').is_hidden()
   page.locator('#rulesIndex a').first.click();page.locator('#rulesArticle').get_by_text('Testo essenziale aggiornato',exact=False).wait_for()
   page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   page.locator('#logout').click();page.locator('#loginPanel').wait_for(state='visible')
   page.locator('#username').fill('teacher@example.com');page.locator('#password').fill('abcdef');page.get_by_role('button',name='Accedi',exact=True).click()
   page.locator('#homeRegulation').wait_for(state='visible');assert page.locator('#adminPanel').is_hidden()
   with page.expect_download() as downloaded:
    page.locator('#homeRegulationDownload').click()
   path=Path(temporary)/'new.txt';downloaded.value.save_as(path)
   assert path.read_bytes()==b'Nuovo regolamento completo per la scuola.'
   page.locator('#calendarView').click();page.locator('#calendarPanel').wait_for(state='visible')
   assert page.locator('#schoolHeading').is_hidden()
   assert page.locator('#schoolLogo').is_visible()
   assert not errors,errors
   print('Browser OK: nuovi titoli, intestazione solo home, logo nelle sezioni, dieci capitoli con navigazione, originale integro scaricabile, caricamenti admin, sintesi aggiornata, download docente e mobile.')
   browser.close()
 finally:server.shutdown();server.server_close();thread.join()
