"""Cliente HTTP compartido: reintentos, errores comprensibles y caché opcional en disco."""
import hashlib
import json
import os
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from modlab import USER_AGENT, logs
from modlab.errors import AuthError, CatalogError, NetworkError, NotFoundError, RateLimitError

log = logs.get('http')
TIMEOUT = (8, 30)


def session(retries=2):
    s = requests.Session()
    retry = Retry(total=retries, connect=retries, read=1, status=retries, backoff_factor=0.6,
                  status_forcelist=(502, 503, 504), allowed_methods=frozenset({'GET', 'POST', 'HEAD'}),
                  respect_retry_after_header=True, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=10)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    s.headers['User-Agent'] = USER_AGENT
    return s


class JsonCache:
    """Caché TTL en memoria y disco. Solo para servicios cuyos términos lo permiten (Modrinth)."""

    def __init__(self, folder, memory_items=256, max_files=3000):
        self.folder = Path(folder)
        self.memory = OrderedDict()
        self.memory_items = memory_items
        self.max_files = max_files
        self.lock = threading.Lock()
        self.writes = 0

    def _path(self, key):
        return self.folder / (hashlib.sha256(key.encode()).hexdigest()[:40] + '.json')

    def get(self, key):
        now = time.time()
        with self.lock:
            hit = self.memory.get(key)
            if hit and hit[0] > now:
                self.memory.move_to_end(key)
                return hit[1]
        try:
            stored = json.loads(self._path(key).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if not isinstance(stored, dict) or stored.get('expires', 0) <= now:
            return None
        self._remember(key, stored['expires'], stored.get('data'))
        return stored.get('data')

    def _remember(self, key, expires, data):
        with self.lock:
            self.memory[key] = (expires, data)
            self.memory.move_to_end(key)
            while len(self.memory) > self.memory_items:
                self.memory.popitem(last=False)

    def put(self, key, data, ttl):
        expires = time.time() + ttl
        self._remember(key, expires, data)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(dir=self.folder, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump({'expires': expires, 'data': data}, handle)
            os.replace(temp, self._path(key))
        except OSError as exc:
            log.debug('No se pudo escribir la caché: %s', exc)
            return
        self.writes += 1
        if self.writes % 100 == 0:
            self.prune()

    def prune(self):
        try:
            files = sorted(self.folder.glob('*.json'), key=lambda p: p.stat().st_mtime)
        except OSError:
            return
        now = time.time()
        for index, path in enumerate(files):
            try:
                if index < len(files) - self.max_files or path.stat().st_mtime < now - 7 * 86400:
                    path.unlink()
            except OSError:
                pass

    def clear(self):
        with self.lock:
            self.memory.clear()
        for path in self.folder.glob('*.json'):
            try:
                path.unlink()
            except OSError:
                pass

    def size(self):
        try:
            return sum(p.stat().st_size for p in self.folder.glob('*.json'))
        except OSError:
            return 0


class ApiClient:
    """Petición JSON con reintentos y traducción de errores HTTP a mensajes claros."""

    def __init__(self, base, service, headers=None, cache=None, http=None):
        self.base = base.rstrip('/')
        self.service = service
        self.headers = {'Accept': 'application/json', **(headers or {})}
        self.cache = cache
        self.http = http or session()

    def request(self, method, route, params=None, body=None, ttl=0):
        url = self.base + route
        key = None
        if self.cache is not None and ttl and method == 'GET':
            key = url + '?' + json.dumps(params or {}, sort_keys=True)
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        data = self._send(method, url, params, body, retry_rate_limit=True)
        if key:
            self.cache.put(key, data, ttl)
        return data

    def _send(self, method, url, params, body, retry_rate_limit):
        try:
            response = self.http.request(method, url, params=params, json=body,
                                         headers=self.headers, timeout=TIMEOUT)
        except requests.Timeout:
            raise NetworkError(f'{self.service} tardó demasiado en responder. Inténtalo de nuevo.') from None
        except requests.RequestException as exc:
            log.warning('%s %s falló: %s', method, url.split('?')[0], type(exc).__name__)
            raise NetworkError(f'No se pudo conectar con {self.service}. Comprueba tu conexión a internet.') from None
        status = response.status_code
        if status == 429:
            wait = _retry_after(response)
            if retry_rate_limit and wait is not None and wait <= 5:
                time.sleep(wait)
                return self._send(method, url, params, body, retry_rate_limit=False)
            raise RateLimitError(f'{self.service} ha limitado temporalmente las consultas. Espera '
                                 f'{int(wait) if wait else "unos"} segundos y vuelve a intentarlo.', wait)
        if status in (401, 403):
            log.warning('%s respondió %s para %s', self.service, status, url.split('?')[0])
            raise AuthError(self.auth_message(status))
        if status == 404:
            raise NotFoundError(f'{self.service} no encuentra el recurso solicitado.')
        if status >= 500:
            log.warning('%s respondió %s', self.service, status)
            raise NetworkError(f'{self.service} no está disponible ahora mismo (error {status}). Inténtalo más tarde.')
        if status >= 400:
            log.warning('%s rechazó la petición %s (%s)', self.service, url.split('?')[0], status)
            raise CatalogError(f'{self.service} rechazó la consulta (error {status}).')
        try:
            return response.json()
        except ValueError:
            raise CatalogError(f'{self.service} devolvió una respuesta que no es JSON.') from None

    def auth_message(self, status):
        return f'{self.service} rechazó el acceso (error {status}).'


def _retry_after(response):
    for header in ('Retry-After', 'X-Ratelimit-Reset'):
        value = response.headers.get(header)
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                return None
    return None
