"""Catálogo oficial de CurseForge (API REST v1) para mods de Minecraft.

Términos de la API de terceros: la clave no se comparte ni se incluye en el cliente (§2.2) y
los datos de la API no se guardan ni se cachean (§3.1). Por eso este cliente no usa caché:
cada consulta va a CurseForge o a la pasarela del desarrollador, que tampoco cachea.
"""
from dataclasses import dataclass, field
from urllib.parse import urlparse
import json
import os

from modlab import logs, paths
from modlab.errors import AuthError, CatalogError, NotFoundError
from modlab.http import ApiClient
from modlab.sources.base import CatalogSource, mod_key, plain_text

log = logs.get('curseforge')

API = 'https://api.curseforge.com'
GAME_ID = 432
CLASS_ID = 6
LOADERS = {'Forge': 1, 'Fabric': 4, 'Quilt': 5, 'NeoForge': 6}
LOADER_BY_ID = {value: name for name, value in LOADERS.items()}
SORT_FIELDS = {'relevance': 2, 'popularity': 2, 'updated': 3, 'name': 4, 'downloads': 6}
RELEASE = {1: 'release', 2: 'beta', 3: 'alpha'}
RELATIONS = {1: 'embedded', 2: 'optional', 3: 'required', 4: 'tool', 5: 'incompatible', 6: 'include'}
BATCH = 50
__all__ = ['CurseForgeClient', 'Connection', 'CatalogError', 'connection_from_environment', 'normalize', 'plain_text']


@dataclass(frozen=True)
class Connection:
    gateway: str = ''
    api_key: str = field(default='', repr=False)

    @property
    def mode(self):
        # La clave solo viaja a api.curseforge.com; la pasarela nunca la recibe.
        if self.api_key:
            return 'direct'
        return 'gateway' if self.gateway else ''

    def check(self):
        if not self.gateway and not self.api_key:
            raise CatalogError('Falta conectar el catálogo oficial de CurseForge. Define CURSEFORGE_API_KEY o '
                               'configura la pasarela de ModLab en Ajustes.')
        if self.gateway:
            parsed = urlparse(self.gateway)
            if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')):
                raise CatalogError('La pasarela debe usar HTTPS; HTTP solo se admite en localhost.')
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise CatalogError('La URL de la pasarela no debe contener claves ni credenciales.')


def bundled_gateway():
    try:
        config = json.loads((paths.resource_root() / 'app-config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ''
    url = config.get('catalog_url', '') if isinstance(config, dict) else ''
    return url if isinstance(url, str) else ''


def connection_from_environment(saved_gateway=''):
    """Clave de desarrollo desde el entorno; pasarela desde entorno, ajustes o paquete."""
    gateway = os.getenv('SMAPT_CATALOG_URL') or saved_gateway or bundled_gateway()
    return Connection(gateway.strip().rstrip('/'), os.getenv('CURSEFORGE_API_KEY', '').strip())


def normalize(mod):
    logo = mod.get('logo') or {}
    shots = mod.get('screenshots') or []
    return {'source': 'curseforge', 'key': mod_key('curseforge', int(mod['id'])), 'project_id': int(mod['id']),
            'title': mod['name'], 'slug': mod.get('slug', ''), 'description': mod.get('summary', ''),
            'url': (mod.get('links') or {}).get('websiteUrl', '') or
                   ('https://www.curseforge.com/minecraft/mc-mods/' + mod.get('slug', '')),
            'logo': logo.get('thumbnailUrl') or logo.get('url', ''),
            'screenshots': [s.get('url') or s.get('thumbnailUrl') for s in shots if s.get('url') or s.get('thumbnailUrl')],
            'thumbnails': [s.get('thumbnailUrl') or s.get('url') for s in shots if s.get('url') or s.get('thumbnailUrl')],
            'downloads': mod.get('downloadCount', 0) or 0,
            'categories': [{'id': c['id'], 'name': c['name'], 'slug': c.get('slug', '')} for c in mod.get('categories', [])],
            'authors': [a['name'] for a in mod.get('authors', [])],
            'updated': (mod.get('dateModified') or '')[:10],
            'allow_distribution': mod.get('allowModDistribution'),
            'latest_files': [{'game_version': i.get('gameVersion'), 'file_id': i.get('fileId'),
                              'release': i.get('releaseType'), 'loader': i.get('modLoader')}
                             for i in mod.get('latestFilesIndexes') or []]}


def loaders_of(game_versions):
    lowered = {v.lower() for v in game_versions}
    return [name for name in LOADERS if name.lower() in lowered]


def normalize_file(raw):
    versions = raw.get('gameVersions') or []
    sha1 = next((h.get('value') for h in raw.get('hashes') or [] if h.get('algo') == 1), '')
    return {'id': raw['id'], 'project_id': raw.get('modId'), 'name': raw.get('displayName') or raw.get('fileName', ''),
            'filename': raw.get('fileName', ''), 'date': (raw.get('fileDate') or '')[:10],
            'release': RELEASE.get(raw.get('releaseType'), 'release'),
            'game_versions': [v for v in versions if v[:1].isdigit()], 'loaders': loaders_of(versions),
            'size': raw.get('fileLength') or 0, 'download_url': raw.get('downloadUrl') or '', 'sha1': sha1,
            'available': bool(raw.get('isAvailable', True)), 'server_pack': bool(raw.get('isServerPack')),
            'dependencies': [{'project_id': int(d['modId']), 'type': RELATIONS.get(d.get('relationType'), 'other')}
                             for d in raw.get('dependencies') or [] if d.get('modId')]}


class CurseForgeClient(CatalogSource):
    source = 'curseforge'
    label = 'CurseForge'

    def __init__(self, connection=None, http=None):
        self.connection = connection or connection_from_environment()
        self.http = http

    def available(self):
        return bool(self.connection.mode)

    def _api(self):
        self.connection.check()
        if self.connection.mode == 'direct':
            api = ApiClient(API, 'CurseForge', {'x-api-key': self.connection.api_key}, http=self.http)
            api.auth_message = lambda status: (f'CurseForge rechazó la clave de API (error {status}). Revisa '
                                               'CURSEFORGE_API_KEY o los permisos de tu aplicación.')
        else:
            api = ApiClient(self.connection.gateway, 'La pasarela de CurseForge', http=self.http)
            api.auth_message = lambda status: (f'La pasarela de CurseForge rechazó el acceso (error {status}). '
                                               'Avisa al desarrollador de ModLab.')
        return api

    def _data(self, response):
        if not isinstance(response, dict) or 'data' not in response:
            raise CatalogError('CurseForge devolvió una respuesta inesperada.')
        return response

    def get(self, route, **params):
        return self._data(self._api().request('GET', route, params=params))

    def post(self, route, body):
        return self._data(self._api().request('POST', route, body=body))

    # Catálogo -----------------------------------------------------------------
    def categories(self):
        rows = self.get('/v1/categories', gameId=GAME_ID, classId=CLASS_ID)['data']
        return [dict(c, label=c.get('name', '')) for c in rows if not c.get('isClass')]

    def search(self, query='', category=None, index=0, page_size=50, sort='downloads', minecraft='', loader=''):
        if not 1 <= page_size <= 50:
            raise CatalogError('El tamaño de página debe estar entre 1 y 50.')
        if not 0 <= index < 10000:
            raise CatalogError('Se alcanzó el límite de paginación de CurseForge (10 000 resultados).')
        sort_field = sort if isinstance(sort, int) else SORT_FIELDS.get(sort, 6)
        params = {'gameId': GAME_ID, 'classId': CLASS_ID, 'index': index,
                  'pageSize': min(page_size, 10000 - index), 'sortField': sort_field,
                  'sortOrder': 'asc' if sort_field == 4 else 'desc'}
        if query:
            params['searchFilter'] = query[:150]
        if category:
            params['categoryId'] = int(category)
        if minecraft:
            params['gameVersion'] = minecraft
        if loader:
            if loader not in LOADERS:
                raise CatalogError('Cargador no admitido.')
            params['modLoaderType'] = LOADERS[loader]
        response = self.get('/v1/mods/search', **params)
        pagination = response.get('pagination') or {}
        return {'mods': [normalize(m) for m in response['data']],
                'pagination': {'index': index, 'totalCount': min(10000, pagination.get('totalCount', len(response['data'])))}}

    def _check_mod(self, raw):
        return raw.get('gameId') == GAME_ID and raw.get('classId') == CLASS_ID

    def mod(self, pid):
        raw = self.get(f'/v1/mods/{int(pid)}')['data']
        if not self._check_mod(raw):
            raise CatalogError('El proyecto no es un mod de Minecraft.')
        return normalize(raw)

    def mods(self, ids):
        ids = [int(i) for i in dict.fromkeys(ids)]
        result = []
        for start in range(0, len(ids), BATCH):
            rows = self.post('/v1/mods', {'modIds': ids[start:start + BATCH], 'filterPcOnly': True})['data']
            result += [normalize(r) for r in rows if self._check_mod(r)]
        return result

    def description(self, pid):
        return {'format': 'html', 'text': self.get(f'/v1/mods/{int(pid)}/description')['data'] or ''}

    def changelog(self, pid, file_id):
        return self.get(f'/v1/mods/{int(pid)}/files/{int(file_id)}/changelog')['data'] or ''

    # Archivos ------------------------------------------------------------------
    def versions(self, pid, minecraft='', loader='', index=0, page_size=50):
        params = {'index': index, 'pageSize': page_size}
        if minecraft:
            params['gameVersion'] = minecraft
        if loader in LOADERS:
            params['modLoaderType'] = LOADERS[loader]
        response = self.get(f'/v1/mods/{int(pid)}/files', **params)
        files = [normalize_file(f) for f in response['data'] if not f.get('isServerPack')]
        return {'files': files, 'total': (response.get('pagination') or {}).get('totalCount', len(files))}

    @staticmethod
    def compatible(raw, pid, minecraft, loader, allow_unstable=False):
        versions = [v.lower() for v in raw.get('gameVersions') or []]
        tags = {name.lower() for name in LOADERS} & set(versions)
        # Los archivos de Forge anteriores a 2019 no declaran cargador: eran todos de Forge.
        loader_ok = loader.lower() in tags or (loader == 'Forge' and not tags)
        return (raw.get('modId') == int(pid) and raw.get('isAvailable', False) and not raw.get('isServerPack')
                and (allow_unstable or raw.get('releaseType') == 1) and minecraft.lower() in versions
                and loader_ok and raw.get('fileName', '').endswith('.jar'))

    def compatible_file(self, pid, minecraft, loader, file_id=None, allow_unstable=False):
        if loader not in LOADERS:
            raise CatalogError('Cargador no admitido.')
        if file_id:
            raw = self.get(f'/v1/mods/{int(pid)}/files/{int(file_id)}')['data']
            if not self.compatible(raw, pid, minecraft, loader, allow_unstable=True):
                raise CatalogError(f'El archivo elegido de {pid} no es compatible con {minecraft} / {loader}.')
            return raw
        fallback = None
        for index in range(0, 10000, 50):
            response = self.get(f'/v1/mods/{int(pid)}/files', gameVersion=minecraft,
                                modLoaderType=LOADERS[loader], index=index, pageSize=50)
            rows = response['data']
            stable = [f for f in rows if self.compatible(f, pid, minecraft, loader)]
            if stable:
                return max(stable, key=lambda f: f.get('fileDate', ''))
            if allow_unstable and fallback is None:
                unstable = [f for f in rows if self.compatible(f, pid, minecraft, loader, True)]
                fallback = max(unstable, key=lambda f: f.get('fileDate', '')) if unstable else None
            total = (response.get('pagination') or {}).get('totalCount', len(rows))
            if not rows or index + len(rows) >= total:
                break
        if fallback:
            return fallback
        raise CatalogError(f'No hay archivo estable compatible para {pid} en Minecraft {minecraft} / {loader}.')

    def _pinned(self, mod, raw, minecraft, loader):
        file = normalize_file(raw)
        return dict(mod, file_id=raw['id'], version_number=file['name'], file=file, release=file['release'],
                    minecraft=minecraft, loader=loader)

    def pin_many(self, mods, minecraft, loader, allow_unstable=False):
        """Fija archivos con dos peticiones por lote usando el índice de últimos archivos de cada mod."""
        if loader not in LOADERS:
            raise CatalogError('Cargador no admitido.')
        for mod in mods:
            if mod.get('source') != 'curseforge':
                raise CatalogError('Solo se admiten mods de CurseForge.')
        incomplete = [m['project_id'] for m in mods if not m.get('file_id') and 'latest_files' not in m]
        fresh = {m['project_id']: m for m in self.mods(incomplete)} if incomplete else {}
        wanted = {}
        for mod in mods:
            mod = dict(fresh.get(mod['project_id'], {}), **mod) if mod['project_id'] in fresh else mod
            file_id = mod.get('file_id')
            if not file_id:
                options = [i for i in mod.get('latest_files', [])
                           if i['game_version'] == minecraft and i['loader'] == LOADERS[loader] and i['release'] == 1]
                file_id = max((i['file_id'] for i in options), default=None)
            wanted[mod['project_id']] = (mod, file_id)
        raws = {}
        ids = [fid for _, fid in wanted.values() if fid]
        for start in range(0, len(ids), BATCH):
            for raw in self.post('/v1/mods/files', {'fileIds': ids[start:start + BATCH]})['data']:
                raws[raw['id']] = raw
        pinned, failures = [], []
        for pid, (mod, file_id) in wanted.items():
            raw = raws.get(file_id)
            explicit = bool(mod.get('file_id'))
            if raw and self.compatible(raw, pid, minecraft, loader, allow_unstable=explicit or allow_unstable):
                pinned.append(self._pinned(mod, raw, minecraft, loader))
                continue
            if explicit:
                failures.append({'project_id': pid, 'title': mod['title'],
                                 'reason': f'El archivo elegido no es compatible con {minecraft} / {loader}.'})
                continue
            try:
                # El índice no siempre lista la combinación: se consulta la lista completa de archivos.
                raw = self.compatible_file(pid, minecraft, loader, allow_unstable=allow_unstable)
                pinned.append(self._pinned(mod, raw, minecraft, loader))
            except NotFoundError:
                failures.append({'project_id': pid, 'title': mod['title'], 'reason': 'El mod ya no está disponible en CurseForge.'})
            except CatalogError as exc:
                if isinstance(exc, AuthError) or 'archivo' not in str(exc):
                    raise
                failures.append({'project_id': pid, 'title': mod['title'],
                                 'reason': f'Sin archivo estable para Minecraft {minecraft} / {loader}.'})
        return pinned, failures

    # Descargas -------------------------------------------------------------------
    def download_url(self, mod):
        """URL oficial del archivo o cadena vacía si el autor no permite descargas de terceros."""
        file = mod.get('file') or {}
        if mod.get('allow_distribution') is False:
            return ''
        if file.get('download_url'):
            return file['download_url']
        try:
            return self.get(f"/v1/mods/{int(mod['project_id'])}/files/{int(mod['file_id'])}/download-url")['data'] or ''
        except (NotFoundError, AuthError):
            return ''

    def file_page(self, mod):
        slug = mod.get('slug', '')
        suffix = f"/files/{mod['file_id']}" if mod.get('file_id') else ''
        return f'https://www.curseforge.com/minecraft/mc-mods/{slug}{suffix}'
