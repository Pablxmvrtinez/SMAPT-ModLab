"""Pasarela de catálogo para el desarrollador. La clave nunca viaja con la app."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import re
from collections import defaultdict,deque
from threading import Lock
from time import monotonic
from urllib.parse import urlparse,parse_qs
import requests

ROUTES=re.compile(r'^/v1/(?:categories|mods/search|mods/\d+(?:/description|/files(?:/\d+)?)?)$')
PARAMS={'gameId','classId','index','pageSize','sortField','sortOrder','searchFilter','categoryId','gameVersion','modLoaderType'}
rate=defaultdict(deque);lock=Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,payload):
        data=json.dumps(payload).encode()
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        uri=urlparse(self.path);params=parse_qs(uri.query)
        if not ROUTES.fullmatch(uri.path) or set(params)-PARAMS:
            self.reply(404,{'error':'Ruta no admitida.'});return
        if any(len(v)!=1 or len(v[0])>300 for v in params.values()):
            self.reply(400,{'error':'Parámetros no válidos.'});return
        params={k:v[0] for k,v in params.items()}
        if uri.path.endswith(('categories','search')):
            params.update(gameId='432',classId='6')
        if 'pageSize' in params and (not params['pageSize'].isdigit() or not 1<=int(params['pageSize'])<=50):
            self.reply(400,{'error':'Tamaño de página no válido.'});return
        now=monotonic();client=self.client_address[0]
        with lock:
            window=rate[client]
            while window and now-window[0]>60:window.popleft()
            if len(window)>=180:
                self.reply(429,{'error':'Demasiadas consultas.'});return
            window.append(now)
            if len(rate)>10000:rate.clear()
        api_key=os.getenv('CURSEFORGE_API_KEY','')
        if not api_key:
            self.reply(503,{'error':'El desarrollador aún no ha conectado CurseForge.'});return
        try:
            response=requests.get('https://api.curseforge.com'+uri.path,params=params,
                                  headers={'x-api-key':api_key,'Accept':'application/json'},timeout=(10,40))
            if response.status_code!=200:
                self.reply(response.status_code,{'error':'CurseForge no pudo atender la consulta.'});return
            data=response.json()
            self.reply(200,data)
        except (requests.RequestException,ValueError):
            self.reply(502,{'error':'No se pudo contactar con CurseForge.'})


if __name__=='__main__':
    ThreadingHTTPServer((os.getenv('SMAPT_BIND','127.0.0.1'),int(os.getenv('PORT','8765'))),Handler).serve_forever()
