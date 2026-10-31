"""Authenticated print and PDF reports; Python 3.12 standard library only."""
import calendar
from datetime import date, timedelta
from html import escape
import textwrap

import app


def pdf_document(lines):
    """Build paginated A4 PDF with embedded text and a standard WinAnsi font."""
    wrapped = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=95) or [''])
    pages = [wrapped[i:i+48] for i in range(0, len(wrapped), 48)] or [[]]
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    kids = []
    for number, page in enumerate(pages, 1):
        page_id = len(objects) + 1
        kids.append(f'{page_id} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id+1} 0 R >>'.encode())
        stream = b'BT /F1 10 Tf 40 800 Td 15 TL\n'
        for line in page + ['', f'Pagina {number} di {len(pages)}']:
            raw = line.encode('cp1252', 'replace').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
            stream += b'(' + raw + b') Tj T*\n'
        stream += b'ET'
        objects.append(b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream')
    objects[1] = f'<< /Type /Pages /Count {len(kids)} /Kids [{" ".join(kids)}] >>'.encode()
    result = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(result)
    result += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    result += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return result + f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def render(query, user):
    def value(key, default):
        return query.get(key, [default])[0]
    selected = date.fromisoformat(value('date', app.today().isoformat()))
    period, scope, output = value('period', 'day'), value('scope', 'all'), value('format', 'html')
    if period not in ('day', 'week', 'month') or scope not in ('all', 'mine') or output not in ('html', 'pdf'):
        raise ValueError()
    start = end = selected
    if period == 'week':
        start = selected - timedelta(days=selected.weekday())
        end = start + timedelta(days=6)
    elif period == 'month':
        start = selected.replace(day=1)
        end = selected.replace(day=calendar.monthrange(selected.year, selected.month)[1])
    app.purge_old()
    with app.connect() as db:
        rows = db.execute('SELECT b.*,l.name AS lab_name FROM bookings b JOIN labs l ON b.lab=l.id '
                          'WHERE substr(start,1,10) BETWEEN ? AND ? AND (?=\'all\' OR user_id=?) '
                          'ORDER BY start,l.name,b.id', (start.isoformat(), end.isoformat(), scope, user['id'])).fetchall()
        closures = db.execute('SELECT * FROM closures WHERE day BETWEEN ? AND ? AND (visible=1 OR ?=1) ORDER BY day',
                              (start.isoformat(), end.isoformat(), int(user['role']=='admin'))).fetchall()
    title = 'Prenotazioni ' + {'day':'giorno', 'week':'settimana', 'month':'mese'}[period]
    subtitle = ('Personali: ' + user['name']) if scope == 'mine' else 'Generali · Tutti i docenti'
    lines = ['Laboratori IC2 Giovanni Paolo II di Policoro', title, subtitle,
             f'Dal {start:%d/%m/%Y} al {end:%d/%m/%Y}',
             f'Dati conservati dal {app.month_shift(app.today(),-1):%d/%m/%Y}; orari Europe/Rome.', '']
    for closure in closures:
        lines.append(f"{closure['day']} · {closure['message'] or 'Chiusura'} · " + ('Prenotazioni bloccate' if closure['blocked'] else 'Avviso senza blocco'))
    if not rows:
        lines.append('Nessuna prenotazione nel periodo selezionato.')
    for row in rows:
        lines.extend([f"{row['start'][:10]} {row['start'][11:]}–{row['end'][11:]} · {row['lab_name']}",
                      f"Docente: {row['teacher']} · Classe: {row['school_class']}", row['notes'], ''])
    if output == 'pdf':
        return pdf_document(lines), 'application/pdf', f'prenotazioni-{period}-{scope}-{selected}.pdf'
    html = ('<!doctype html><html lang="it"><meta charset="utf-8"><title>' + escape(title) + '</title>'
            '<style>body{font:14px system-ui;margin:28px;color:#222}p{white-space:pre-wrap;overflow-wrap:anywhere}'
            '@media print{button{display:none}p{break-inside:avoid}}@page{size:A4;margin:16mm}</style>'
            '<button onclick="window.print()">Stampa / Salva come PDF</button>'
            + ''.join('<p>' + escape(line) + '</p>' for line in lines) + '</html>')
    return html.encode(), 'text/html; charset=utf-8', None
