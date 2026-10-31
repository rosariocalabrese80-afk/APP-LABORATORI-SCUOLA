"""WSGI entry point for PythonAnywhere and other WSGI hosts."""
import io
import logging
from email.message import Message
from http import HTTPStatus

import app

# LAB_DB and COOKIE_SECURE must be configured before importing this module.
app.init()


class Request(app.Handler):
    """Reuse application routes without opening a socket or starting a server."""

    def __init__(self, environ, body):
        self.path = environ.get('PATH_INFO', '/')
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                self.headers[key[5:].replace('_', '-')] = value
        for key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            if environ.get(key):
                self.headers[key.replace('_', '-')] = environ[key]
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.response_status = 200
        self.response_headers = []

    def send_response(self, code, message=None):
        self.response_status = code
        self.response_headers = []

    def send_header(self, name, value):
        self.response_headers.append((name, str(value)))

    def end_headers(self):
        pass


def application(environ, start_response):
    try:
        length = int(environ.get('CONTENT_LENGTH') or '0')
        if not 0 <= length <= app.school.request_limit(environ.get('PATH_INFO','/')):
            raise ValueError()
    except ValueError:
        start_response('413 Content Too Large', [('Content-Type', 'application/json')])
        return [b'{"error":"Richiesta troppo grande o non valida."}']
    request = Request(environ, environ['wsgi.input'].read(length))
    method = environ.get('REQUEST_METHOD', 'GET')
    try:
        if method not in ('GET', 'POST', 'DELETE'):
            request.reply(405, {'error': 'Metodo non consentito.'})
            request.send_header('Allow', 'GET, POST, DELETE')
        else:
            getattr(request, 'do_' + method)()
    except Exception:
        logging.exception('Errore nella richiesta WSGI')
        request.wfile = io.BytesIO()
        request.reply(500, {'error': 'Errore interno. Contatta l’amministratore.'})
    status = f'{request.response_status} {HTTPStatus(request.response_status).phrase}'
    start_response(status, request.response_headers)
    return [request.wfile.getvalue()]
