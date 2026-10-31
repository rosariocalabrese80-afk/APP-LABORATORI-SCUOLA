"""Authenticated, formatted print/PDF reports with the current school letterhead."""
import base64
import calendar
from datetime import date, timedelta
from html import escape
from io import BytesIO
from pathlib import Path
from threading import Lock
import warnings

import app

_FONT_LOCK = Lock()
_WEEKDAYS = ('lunedì','martedì','mercoledì','giovedì','venerdì','sabato','domenica')
_MONTHS = ('gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto','settembre','ottobre','novembre','dicembre')


def day_label(value):
    day = date.fromisoformat(value) if isinstance(value,str) else value
    return f'{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month-1]} {day.year}'


def letterhead(db):
    """Normalize the persisted JPEG/PNG/WebP, retaining aspect ratio and transparency."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    stored = db.execute("SELECT content FROM school_assets WHERE kind='header'").fetchone()
    original = (app.ROOT/'web/assets/school-header.jpg').read_bytes()
    candidates = [stored['content'], original] if stored else [original]
    for content in candidates:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    image.load()
                    image = ImageOps.exif_transpose(image).convert('RGBA')
                    image.thumbnail((2000,600),Image.Resampling.LANCZOS)
                    background = Image.new('RGB',image.size,'white')
                    background.paste(image,mask=image.getchannel('A'))
                    output = BytesIO()
                    background.save(output,format='PNG')
                    return {'content':output.getvalue(),'width':background.width,'height':background.height}
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            continue
    raise ValueError('Intestazione scolastica non disponibile.')


def pdf_styles():
    from reportlab import __file__ as reportlab_file
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    with _FONT_LOCK:
        if 'LabVera' not in pdfmetrics.getRegisteredFontNames():
            fonts = Path(reportlab_file).parent/'fonts'
            for name,file in [('LabVera','Vera.ttf'),('LabVera-Bold','VeraBd.ttf'),('LabVera-Italic','VeraIt.ttf'),('LabVera-BoldItalic','VeraBI.ttf')]:
                pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
            pdfmetrics.registerFontFamily('LabVera',normal='LabVera',bold='LabVera-Bold',italic='LabVera-Italic',boldItalic='LabVera-BoldItalic')
    body = ParagraphStyle('body',fontName='LabVera',fontSize=10,leading=15,spaceAfter=0,splitLongWords=True)
    return {
        'body':body,
        'title':ParagraphStyle('title',parent=body,fontName='LabVera-Bold',fontSize=17,leading=22,spaceAfter=9),
        'subtitle':ParagraphStyle('subtitle',parent=body,fontName='LabVera-Bold',fontSize=10,leading=15,spaceAfter=5),
        'day':ParagraphStyle('day',parent=body,fontName='LabVera-Bold',fontSize=12,leading=17,spaceBefore=15,spaceAfter=8,keepWithNext=True,textColor='#813c05'),
        'small':ParagraphStyle('small',parent=body,fontName='LabVera-Italic',fontSize=8,leading=12,textColor='#555555'),
        'note':ParagraphStyle('note',parent=body,fontName='LabVera-Italic',fontSize=9,leading=14),
    }


def build_pdf(flowables, header=None, title='Prenotazioni laboratori', footer_label='Orari italiani · Europe/Rome'):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate
    pdf_styles()
    width,height = A4
    margin = 42
    image_width = image_height = 0
    image = None
    if header:
        image = ImageReader(BytesIO(header['content']))
        ratio = header['width']/header['height']
        image_width = min(width-2*margin,82*ratio)
        image_height = image_width/ratio

    class NumberedCanvas(Canvas):
        def __init__(self,*args,**kwargs):
            kwargs.update(pdfVersion=(1,4),pageCompression=0)
            super().__init__(*args,**kwargs)
            self.pages = []
            self.setTitle(title)
            self.setAuthor('Laboratori IC2 Giovanni Paolo II di Policoro')
        def showPage(self):
            self.pages.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            count = len(self.pages)
            for state in self.pages:
                self.__dict__.update(state)
                self.saveState()
                self.setStrokeColorRGB(.8,.8,.8)
                self.line(margin,36,width-margin,36)
                self.setFont('LabVera',8)
                self.setFillColorRGB(.3,.3,.3)
                self.drawString(margin,24,footer_label)
                self.drawRightString(width-margin,24,f'Pagina {self._pageNumber} di {count}')
                self.restoreState()
                Canvas.showPage(self)
            Canvas.save(self)

    def draw_header(canvas,doc):
        if image:
            canvas.saveState()
            canvas.drawImage(image,(width-image_width)/2,height-margin-image_height,
                             width=image_width,height=image_height,mask='auto')
            canvas.restoreState()

    output = BytesIO()
    doc = SimpleDocTemplate(output,pagesize=A4,leftMargin=margin,rightMargin=margin,
                           topMargin=margin+image_height+(18 if image else 0),bottomMargin=51,
                           allowSplitting=True,title=title,author='Laboratori IC2 Giovanni Paolo II di Policoro')
    doc.build(flowables,onFirstPage=draw_header,onLaterPages=draw_header,canvasmaker=NumberedCanvas)
    return output.getvalue()


def pdf_document(lines):
    """Plain paragraph helper retained for pagination and PDF integrity checks."""
    from reportlab.platypus import Paragraph
    style = pdf_styles()['body']
    return build_pdf([Paragraph(escape(line) or '&#160;',style) for line in lines])


def report_pdf(report):
    from reportlab.platypus import Paragraph,Spacer,Table,TableStyle,KeepTogether
    styles = pdf_styles()
    paragraph = lambda text,style='body': Paragraph(text,styles[style])
    story = [paragraph(escape(report['title']),'title'),paragraph(escape(report['subtitle']),'subtitle'),
             paragraph(escape(report['period_label'])),
             paragraph(escape(report['availability']),'small'),Spacer(1,10),
             paragraph(f"<b>TOTALE: {len(report['rows'])} prenotazioni</b>"),Spacer(1,4)]
    for day in report['days']:
        story.append(paragraph(escape(day_label(day).upper()),'day'))
        for closure in report['closures']:
            if closure['day'] == day:
                text = ('PRENOTAZIONI BLOCCATE' if closure['blocked'] else 'AVVISO SENZA BLOCCO')
                story.extend([paragraph('<b>'+text+'</b>'),paragraph(escape(closure['message'] or 'Chiusura'),'note'),Spacer(1,8)])
        for row in report['rows']:
            if row['start'][:10] != day:
                continue
            content = [[paragraph('<b>DATA E ORA</b>'),paragraph('<b>'+escape(date.fromisoformat(row['start'][:10]).strftime('%d/%m/%Y')+' · '+row['start'][11:]+' – '+row['end'][11:])+'</b>')],
                       [paragraph('<b>Laboratorio</b>'),paragraph('<b>'+escape(row['lab_name'])+'</b>')],
                       [paragraph('<b>Docente</b>'),paragraph(escape(row['teacher']))],
                       [paragraph('<b>Classe</b>'),paragraph(escape(row['school_class']))]]
            table = Table(content,colWidths=[86,413],hAlign='LEFT')
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
                                       ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),
                                       ('BOTTOMPADDING',(0,0),(-1,-1),5),('BACKGROUND',(0,0),(-1,0),'#faf2e2'),
                                       ('LINEBELOW',(0,-1),(-1,-1),.5,'#d6c7b2')]))
            booking=[table]
            if row['notes']:
                booking.extend([Spacer(1,5),paragraph('<b>Note:</b> '+escape(row['notes']).replace('\n','<br/>'),'note')])
            booking.append(Spacer(1,12))
            story.append(KeepTogether(booking))
    if not report['rows']:
        story.extend([Spacer(1,10),paragraph('Nessuna prenotazione nel periodo selezionato.','note')])
    return build_pdf(story,report['header'],report['title'],report['period_label']+' · Europe/Rome')


def report_html(report):
    e = escape
    image = base64.b64encode(report['header']['content']).decode('ascii')
    parts = ['<!doctype html><html lang="it"><head><meta charset="utf-8"><title>'+e(report['title'])+'</title>',
             '''<style>
*{box-sizing:border-box}body{font:14px/1.5 system-ui,sans-serif;color:#252525;margin:24px auto;padding:0 20px;max-width:850px}.report-sheet{width:100%;border-collapse:collapse;table-layout:fixed}.report-sheet>thead>tr>td,.report-sheet>tbody>tr>td{padding:0;vertical-align:top}header img{display:block;width:100%;max-height:120px;object-fit:contain;margin:0 auto 20px}h1{font-size:24px;line-height:1.25;margin:0 0 10px}h2{font-size:17px;color:#813c05;border-bottom:1px solid #d6c7b2;padding-bottom:6px;margin-top:26px}p{margin:6px 0;overflow-wrap:anywhere}.scope{font-weight:700}.meta{font-size:12px;color:#555}.booking{border:1px solid #d6c7b2;border-radius:6px;padding:12px;margin:12px 0;break-inside:avoid}.booking h3{font-size:15px;margin:0 0 8px;background:#faf2e2;padding:7px}.booking dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:6px 12px;margin:0}.booking dt{font-weight:700}.booking dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.notice{border-left:3px solid #a54f09;padding:8px 12px;margin:10px 0;break-inside:avoid}.print-actions{margin:14px 0}.print-actions button{font:inherit;padding:10px 16px;cursor:pointer}footer{font-size:11px;color:#555;border-top:1px solid #ddd;margin-top:24px;padding-top:8px}@page{size:A4;margin:15mm}@media print{body{max-width:none;margin:0;padding:0;font-size:10pt;color:#000}.print-actions{display:none}h1{font-size:17pt}h2{font-size:12pt;break-after:avoid}thead{display:table-header-group;break-inside:avoid}header img{max-height:25mm;margin:0 auto 6mm}.booking{border-radius:0}.notice{break-inside:avoid}}@media(max-width:500px){body{padding:0 12px}.booking dl{grid-template-columns:1fr;gap:2px}.booking dd{margin-bottom:6px}}
</style></head><body>''',
             '<div class="print-actions"><button onclick="window.print()">Stampa / Salva come PDF</button></div>',
             '<table class="report-sheet"><thead><tr><td><header><img class="letterhead" src="data:image/png;base64,'+image+'" alt="Intestazione scolastica IC2 Giovanni Paolo II di Policoro"></header></td></tr></thead><tbody><tr><td>',
             '<main><h1>'+e(report['title'])+'</h1><p class="scope">'+e(report['subtitle'])+'</p>',
             '<p>'+e(report['period_label'])+'</p><p class="meta"><em>'+e(report['availability'])+'</em></p>',
             '<p><strong>TOTALE: '+str(len(report['rows']))+' prenotazioni</strong></p>']
    for day in report['days']:
        parts.append('<section class="report-day"><h2>'+e(day_label(day).upper())+'</h2>')
        for closure in report['closures']:
            if closure['day'] == day:
                status = 'PRENOTAZIONI BLOCCATE' if closure['blocked'] else 'AVVISO SENZA BLOCCO'
                parts.append('<aside class="notice"><strong>'+status+'</strong><p><em>'+e(closure['message'] or 'Chiusura')+'</em></p></aside>')
        for row in report['rows']:
            if row['start'][:10] != day:
                continue
            parts.append('<article class="booking"><h3><strong>'+e(date.fromisoformat(row['start'][:10]).strftime('%d/%m/%Y')+' · '+row['start'][11:]+' – '+row['end'][11:])+'</strong></h3><dl>')
            for label,text in [('Laboratorio',row['lab_name']),('Docente',row['teacher']),('Classe',row['school_class'])]:
                value = '<strong>'+e(text)+'</strong>' if label == 'Laboratorio' else e(text)
                parts.append('<dt>'+label+'</dt><dd>'+value+'</dd>')
            if row['notes']:
                parts.append('<dt>Note</dt><dd><em>'+e(row['notes'])+'</em></dd>')
            parts.append('</dl></article>')
        parts.append('</section>')
    if not report['rows']:
        parts.append('<p><em>Nessuna prenotazione nel periodo selezionato.</em></p>')
    parts.append('</main><footer>Laboratori IC2 Giovanni Paolo II di Policoro · Orari italiani · Europe/Rome</footer></td></tr></tbody></table></body></html>')
    return ''.join(parts).encode()


def render(query, user):
    def value(key, default):
        return query.get(key,[default])[0]
    selected = date.fromisoformat(value('date',app.today().isoformat()))
    period,scope,output = value('period','day'),value('scope','all'),value('format','html')
    if period not in ('day','week','month') or scope not in ('all','mine') or output not in ('html','pdf'):
        raise ValueError()
    start = end = selected
    if period == 'week':
        start = selected-timedelta(days=selected.weekday())
        end = start+timedelta(days=6)
    elif period == 'month':
        start = selected.replace(day=1)
        end = selected.replace(day=calendar.monthrange(selected.year,selected.month)[1])
    app.purge_old()
    with app.connect() as db:
        rows = [dict(row) for row in db.execute('SELECT b.*,l.name AS lab_name FROM bookings b JOIN labs l ON b.lab=l.id '
                          'WHERE substr(start,1,10) BETWEEN ? AND ? AND (?=\'all\' OR user_id=?) '
                          'ORDER BY start,l.name,b.id',(start.isoformat(),end.isoformat(),scope,user['id']))]
        closures = [dict(row) for row in db.execute('SELECT * FROM closures WHERE day BETWEEN ? AND ? AND (visible=1 OR ?=1) ORDER BY day',
                                                  (start.isoformat(),end.isoformat(),int(user['role']=='admin')))]
        header = letterhead(db)
    report = {
        'title':{'day':'PRENOTAZIONI GIORNALIERE','week':'PRENOTAZIONI SETTIMANALI','month':'PRENOTAZIONI MENSILI'}[period],
        'subtitle':('PERSONALI · '+user['name']) if scope == 'mine' else 'GENERALI · Tutti i docenti',
        'period_label':f'Dal {start:%d/%m/%Y} al {end:%d/%m/%Y}',
        'availability':f'Dati conservati dal {app.month_shift(app.today(),-1):%d/%m/%Y}. Orari italiani (Europe/Rome).',
        'rows':rows,'closures':closures,'header':header,
        'days':sorted({row['start'][:10] for row in rows}|{row['day'] for row in closures}),
    }
    if output == 'pdf':
        return report_pdf(report),'application/pdf',f'prenotazioni-{period}-{scope}-{selected}.pdf'
    return report_html(report),'text/html; charset=utf-8',None
