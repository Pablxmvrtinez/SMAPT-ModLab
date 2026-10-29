"""Pasarela de catálogo para el desarrollador. La clave nunca viaja con la app.

Uso: CURSEFORGE_API_KEY=... python catalog_server.py  (escucha en 127.0.0.1:8765)
Publícala detrás de un proxy HTTPS. Condiciones respetadas de la API de terceros de CurseForge:
la clave permanece en el servidor (§2.2) y las respuestas no se guardan ni se cachean (§3.1).
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import re
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from urllib.parse import urlparse, parse_qs

import requests

GET_ROUTES = re.compile(r'^/v1/(?:categories|mods/search|mods/\d+(?:/description|/files(?:/\d+(?:/changelog|/download-url)?)?)?)$')
POST_ROUTES = {'/v1/mods': ('modIds', {'modIds', 'filterPcOnly'}), '/v1/mods/files': ('fileIds', {'fileIds'})}
PARAMS = {'gameId', 'classId', 'index', 'pageSize', 'sortField', 'sortOrder', 'searchFilter', 'categoryId',
          'gameVersion', 'modLoaderType'}
MAX_BODY = 8192
MAX_IDS = 100
LIMIT_PER_MINUTE = int(os.getenv('SMAPT_RATE_LIMIT', '180'))
rate = defaultdict(deque)
lock = Lock()
log = logging.getLogger('smapt.gateway')
upstream = requests.Session()


class Handler(BaseHTTPRequestHandler):
    server_version = 'SMAPT-Gateway/2'

    def log_message(self, *args):
        pass

    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def client_ip(self):
        if os.getenv('SMAPT_TRUST_PROXY') == '1':
            forwarded = self.headers.get('X-Forwarded-For', '') if getattr(self, 'headers', None) else ''
            if forwarded:
                return forwarded.split(',')[0].strip()
        return self.client_address[0]

    def allowed(self):
        now = monotonic()
        with lock:
            window = rate[self.client_ip()]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= LIMIT_PER_MINUTE:
                return False
            window.append(now)
            if len(rate) > 10000:
                rate.clear()
        return True

    def forward(self, method, path, params=None, body=None):
        api_key = os.getenv('CURSEFORGE_API_KEY', '')
        if not api_key:
            self.reply(503, {'error': 'El desarrollador aún no ha conectado CurseForge.'})
            return
        try:
            response = upstream.request(method, 'https://api.curseforge.com' + path, params=params, json=body,
                                        headers={'x-api-key': api_key, 'Accept': 'application/json'}, timeout=(10, 40))
            if response.status_code != 200:
                log.warning('CurseForge respondió %s a %s', response.status_code, path)
                self.reply(response.status_code, {'error': 'CurseForge no pudo atender la consulta.'})
                return
            self.reply(200, response.json())
        except (requests.RequestException, ValueError):
            self.reply(502, {'error': 'No se pudo contactar con CurseForge.'})

    def do_GET(self):
        uri = urlparse(self.path)
        if uri.path == '/health':
            self.reply(200, {'ok': True, 'curseforge': bool(os.getenv('CURSEFORGE_API_KEY'))})
            return
        params = parse_qs(uri.query)
        if not GET_ROUTES.fullmatch(uri.path) or set(params) - PARAMS:
            self.reply(404, {'error': 'Ruta no admitida.'})
            return
        if any(len(v) != 1 or len(v[0]) > 300 for v in params.values()):
            self.reply(400, {'error': 'Parámetros no válidos.'})
            return
        params = {k: v[0] for k, v in params.items()}
        if uri.path.endswith(('categories', 'search')):
            params.update(gameId='432', classId='6')
        if 'pageSize' in params and (not params['pageSize'].isdigit() or not 1 <= int(params['pageSize']) <= 50):
            self.reply(400, {'error': 'Tamaño de página no válido.'})
            return
        if not self.allowed():
            self.reply(429, {'error': 'Demasiadas consultas.'})
            return
        self.forward('GET', uri.path, params=params)

    def do_POST(self):
        uri = urlparse(self.path)
        if uri.path not in POST_ROUTES or uri.query:
            self.reply(404, {'error': 'Ruta no admitida.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.reply(413 if length > MAX_BODY else 400, {'error': 'Cuerpo no válido.'})
            return
        try:
            body = json.loads(self.rfile.read(length))
        except ValueError:
            self.reply(400, {'error': 'JSON no válido.'})
            return
        field, allowed_fields = POST_ROUTES[uri.path]
        ids = body.get(field) if isinstance(body, dict) else None
        if (not isinstance(body, dict) or set(body) - allowed_fields or not isinstance(ids, list)
                or not 0 < len(ids) <= MAX_IDS or not all(type(i) is int and i > 0 for i in ids)
                or not isinstance(body.get('filterPcOnly', True), bool)):
            self.reply(400, {'error': 'Parámetros no válidos.'})
            return
        if not self.allowed():
            self.reply(429, {'error': 'Demasiadas consultas.'})
            return
        self.forward('POST', uri.path, body=body)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    address = (os.getenv('SMAPT_BIND', '127.0.0.1'), int(os.getenv('PORT', '8765')))
    if not os.getenv('CURSEFORGE_API_KEY'):
        log.warning('CURSEFORGE_API_KEY no está definida: la pasarela responderá 503.')
    log.info('Pasarela de ModLab en http://%s:%s', *address)
    ThreadingHTTPServer(address, Handler).serve_forever()


if __name__ == '__main__':
    main()
