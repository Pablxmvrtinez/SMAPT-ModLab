"""Dobles de red para las pruebas: ninguna prueba contacta con servicios reales."""
import json
from urllib.parse import urlparse


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, url='https://example.test/', body=b''):
        self.status_code = status
        self.payload = payload
        self.headers = headers or {}
        self.url = url
        self.body = body

    def json(self):
        if self.payload is None:
            raise ValueError('sin JSON')
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    @property
    def content(self):
        return self.body

    def iter_content(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeHttp:
    """Sustituye a requests.Session. ``routes`` asocia (método, ruta) a una respuesta o función."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        path = urlparse(url).path
        self.calls.append({'method': method, 'url': url, 'path': path, 'params': params or {},
                           'json': json, 'headers': headers or {}})
        handler = self.routes.get((method, path))
        if handler is None:
            return FakeResponse(404, {'error': 'not found'})
        if callable(handler):
            handler = handler(params or {}, json)
        if isinstance(handler, FakeResponse):
            return handler
        return FakeResponse(200, handler)

    def get(self, url, stream=False, timeout=None):
        response = self.routes.get(('GET', url))
        self.calls.append({'method': 'GET', 'url': url})
        return response if isinstance(response, FakeResponse) else FakeResponse(404, url=url)


def raw_mod(pid=10, **extra):
    result = {'id': pid, 'gameId': 432, 'classId': 6, 'name': f'Mod {pid}', 'slug': f'mod-{pid}',
              'summary': 'Descripción del mod', 'downloadCount': 12345,
              'logo': {'thumbnailUrl': 'https://media.forgecdn.net/test.png'},
              'categories': [{'id': 101, 'name': 'Cosmetic', 'slug': 'cosmetic'}],
              'links': {'websiteUrl': f'https://www.curseforge.com/minecraft/mc-mods/mod-{pid}'},
              'authors': [{'name': 'Author'}], 'allowModDistribution': True,
              'latestFilesIndexes': [{'gameVersion': '1.20.1', 'fileId': pid * 100, 'releaseType': 1, 'modLoader': 1}]}
    result.update(extra)
    return result


def raw_file(pid=10, fid=None, deps=(), **extra):
    result = {'id': fid or pid * 100, 'modId': pid, 'isAvailable': True, 'fileName': f'mod-{pid}.jar',
              'releaseType': 1, 'gameVersions': ['1.20.1', 'Forge'], 'displayName': f'Mod {pid} 1.0',
              'dependencies': list(deps), 'fileDate': '2026-01-01T00:00:00Z', 'fileLength': 10,
              'downloadUrl': f'https://edge.forgecdn.net/files/{pid}/mod-{pid}.jar',
              'hashes': [{'value': 'a' * 40, 'algo': 1}]}
    result.update(extra)
    return result


def curseforge_routes(mods, files):
    """Rutas mínimas de CurseForge construidas a partir de diccionarios id → objeto crudo."""
    def get_mods(params, body):
        return {'data': [mods[i] for i in body['modIds'] if i in mods]}

    def get_files(params, body):
        return {'data': [files[i] for i in body['fileIds'] if i in files]}
    routes = {('POST', '/v1/mods'): get_mods, ('POST', '/v1/mods/files'): get_files}
    for pid, mod in mods.items():
        routes[('GET', f'/v1/mods/{pid}')] = {'data': mod}
        own = [f for f in files.values() if f['modId'] == pid]
        routes[('GET', f'/v1/mods/{pid}/files')] = {'data': own, 'pagination': {'totalCount': len(own)}}
    return routes


def dumps(value):
    return json.dumps(value)
