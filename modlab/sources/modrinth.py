"""Catálogo público de Modrinth (API v2). No requiere clave; sí un User-Agent identificable."""
import json

from modlab import logs, paths
from modlab.errors import CatalogError, NotFoundError
from modlab.http import ApiClient, JsonCache
from modlab.sources.base import CatalogSource, mod_key

log = logs.get('modrinth')

API = 'https://api.modrinth.com/v2'
LOADERS = {'Forge': 'forge', 'NeoForge': 'neoforge', 'Fabric': 'fabric', 'Quilt': 'quilt'}
LOADER_BY_SLUG = {value: name for name, value in LOADERS.items()}
SORTS = {'relevance': 'relevance', 'downloads': 'downloads', 'popularity': 'follows', 'updated': 'updated', 'name': 'relevance'}
# Etiquetas de plataforma o de servidor que no son temáticas.
NOT_THEMES = set(LOADERS.values()) | {'bukkit', 'spigot', 'paper', 'purpur', 'folia', 'sponge', 'velocity',
                                      'bungeecord', 'waterfall', 'datapack', 'liteloader', 'modloader', 'rift'}
TTL_TAGS = 24 * 3600
TTL_SEARCH = 10 * 60
TTL_PROJECT = 30 * 60
BATCH = 100


def normalize(hit):
    """Acepta resultados de búsqueda y proyectos completos (sus campos difieren)."""
    pid = hit.get('project_id') or hit['id']
    gallery = hit.get('gallery') or []
    urls = [g if isinstance(g, str) else g.get('url') for g in gallery]
    urls = [u for u in urls if u]
    featured = hit.get('featured_gallery')
    if featured and featured not in urls:
        urls.insert(0, featured)
    themes = hit.get('display_categories') or hit.get('categories') or []
    loaders = [LOADER_BY_SLUG[c] for c in (hit.get('loaders') or hit.get('categories') or []) if c in LOADER_BY_SLUG]
    author = hit.get('author')
    return {'source': 'modrinth', 'key': mod_key('modrinth', pid), 'project_id': pid, 'title': hit['title'],
            'slug': hit.get('slug', ''), 'description': hit.get('description', ''),
            'url': 'https://modrinth.com/mod/' + (hit.get('slug') or pid), 'logo': hit.get('icon_url') or '',
            'screenshots': urls, 'thumbnails': urls, 'downloads': hit.get('downloads', 0) or 0,
            'categories': [{'id': c, 'name': c, 'slug': c} for c in themes if c not in NOT_THEMES],
            'authors': [author] if author else [], 'updated': (hit.get('date_modified') or hit.get('updated') or '')[:10],
            'allow_distribution': True, 'loaders': loaders,
            'client_side': hit.get('client_side', 'unknown'), 'server_side': hit.get('server_side', 'unknown')}


def normalize_version(raw):
    files = raw.get('files') or []
    primary = next((f for f in files if f.get('primary')), files[0] if files else {})
    hashes = primary.get('hashes') or {}
    return {'id': raw['id'], 'project_id': raw.get('project_id'), 'name': raw.get('name') or raw.get('version_number', ''),
            'version_number': raw.get('version_number', ''), 'filename': primary.get('filename', ''),
            'date': (raw.get('date_published') or '')[:10], 'release': raw.get('version_type', 'release'),
            'game_versions': raw.get('game_versions') or [],
            'loaders': [LOADER_BY_SLUG.get(l, l) for l in raw.get('loaders') or []],
            'size': primary.get('size') or 0, 'download_url': primary.get('url', ''),
            'sha1': hashes.get('sha1', ''), 'sha512': hashes.get('sha512', ''),
            'available': raw.get('status', 'listed') in ('listed', 'archived', 'unlisted'),
            'dependencies': [{'project_id': d.get('project_id'), 'version_id': d.get('version_id'),
                              'type': d.get('dependency_type', 'optional')} for d in raw.get('dependencies') or []]}


class ModrinthClient(CatalogSource):
    source = 'modrinth'
    label = 'Modrinth'

    def __init__(self, cache=None, http=None):
        if cache is None:
            cache = JsonCache(paths.cache_dir() / 'modrinth')
        self.api = ApiClient(API, 'Modrinth', cache=cache or None, http=http)

    def get(self, route, ttl=0, **params):
        return self.api.request('GET', route, params=params or None, ttl=ttl)

    def categories(self):
        rows = self.get('/tag/category', ttl=TTL_TAGS)
        return [{'id': c['name'], 'name': c['name'], 'label': c['name'], 'icon': c.get('icon', '')}
                for c in rows if c.get('project_type') == 'mod' and c.get('header') == 'categories']

    def game_versions(self):
        rows = self.get('/tag/game_version', ttl=TTL_TAGS)
        return [r['version'] for r in rows if r.get('version_type') == 'release']

    def search(self, query='', category=None, index=0, page_size=50, sort='downloads', minecraft='', loader=''):
        if not 1 <= page_size <= 100:
            raise CatalogError('El tamaño de página debe estar entre 1 y 100.')
        facets = [['project_type:mod']]
        if category:
            facets.append([f'categories:{category}'])
        if minecraft:
            facets.append([f'versions:{minecraft}'])
        if loader:
            if loader not in LOADERS:
                raise CatalogError('Cargador no admitido.')
            facets.append([f'categories:{LOADERS[loader]}'])
        index_name = SORTS.get(sort, 'downloads') if isinstance(sort, str) else 'downloads'
        if query and sort == 'downloads':
            index_name = 'relevance'
        params = {'facets': json.dumps(facets), 'index': index_name, 'offset': max(0, int(index)), 'limit': page_size}
        if query:
            params['query'] = query[:150]
        data = self.get('/search', ttl=TTL_SEARCH, **params)
        return {'mods': [normalize(h) for h in data.get('hits', [])],
                'pagination': {'index': data.get('offset', index), 'totalCount': data.get('total_hits', 0)}}

    def mod(self, pid):
        raw = self.get(f'/project/{pid}', ttl=TTL_PROJECT)
        if raw.get('project_type') != 'mod':
            raise CatalogError('El proyecto de Modrinth no es un mod.')
        return normalize(raw)

    def mods(self, ids):
        ids = list(dict.fromkeys(i for i in ids if i))
        result = []
        for start in range(0, len(ids), BATCH):
            rows = self.get('/projects', ttl=TTL_PROJECT, ids=json.dumps(ids[start:start + BATCH]))
            result += [normalize(r) for r in rows if r.get('project_type') == 'mod']
        return result

    def description(self, pid):
        return {'format': 'markdown', 'text': self.get(f'/project/{pid}', ttl=TTL_PROJECT).get('body', '')}

    def versions(self, pid, minecraft='', loader='', index=0, page_size=50):
        params = {}
        if loader in LOADERS:
            params['loaders'] = json.dumps([LOADERS[loader]])
        if minecraft:
            params['game_versions'] = json.dumps([minecraft])
        rows = self.get(f'/project/{pid}/version', ttl=TTL_SEARCH, **params)
        files = [normalize_version(r) for r in rows if r.get('files')]
        return {'files': files[index:index + page_size], 'total': len(files)}

    def compatible_file(self, pid, minecraft, loader, file_id=None, allow_unstable=False):
        if loader not in LOADERS:
            raise CatalogError('Cargador no admitido.')
        if file_id:
            version = normalize_version(self.get(f'/version/{file_id}', ttl=TTL_PROJECT))
            if version['project_id'] != pid or minecraft not in version['game_versions'] or loader not in version['loaders']:
                raise CatalogError(f'La versión elegida no es compatible con {minecraft} / {loader}.')
            return version
        files = [f for f in self.versions(pid, minecraft, loader, page_size=1000)['files']
                 if f['available'] and f['filename'].endswith('.jar')]
        stable = [f for f in files if f['release'] == 'release']
        chosen = stable or (files if allow_unstable else [])
        if not chosen:
            raise CatalogError(f'No hay archivo estable compatible para {pid} en Minecraft {minecraft} / {loader}.')
        return max(chosen, key=lambda f: f['date'])

    def pin_many(self, mods, minecraft, loader, allow_unstable=False):
        pinned, failures = [], []
        for mod in mods:
            if mod.get('source') != 'modrinth':
                raise CatalogError('Solo se admiten mods de Modrinth en este catálogo.')
            try:
                version = self.compatible_file(mod['project_id'], minecraft, loader, mod.get('file_id'), allow_unstable)
            except NotFoundError:
                failures.append({'project_id': mod['project_id'], 'title': mod['title'], 'reason': 'El mod ya no está disponible en Modrinth.'})
                continue
            except CatalogError as exc:
                if 'compatible' not in str(exc):
                    raise
                failures.append({'project_id': mod['project_id'], 'title': mod['title'],
                                 'reason': f'Sin archivo estable para Minecraft {minecraft} / {loader}.'})
                continue
            pinned.append(dict(mod, file_id=version['id'], version_number=version['version_number'] or version['name'],
                               file=version, release=version['release'], minecraft=minecraft, loader=loader))
        self._fill_dependency_projects(pinned)
        return pinned, failures

    def _fill_dependency_projects(self, pinned):
        # Algunas dependencias solo indican la versión; se traduce a proyecto con una consulta por lote.
        missing = [d['version_id'] for p in pinned for d in p['file']['dependencies'] if not d['project_id'] and d.get('version_id')]
        if not missing:
            return
        rows = self.get('/versions', ttl=TTL_PROJECT, ids=json.dumps(list(dict.fromkeys(missing))[:BATCH]))
        owners = {r['id']: r.get('project_id') for r in rows}
        for p in pinned:
            for d in p['file']['dependencies']:
                if not d['project_id'] and d.get('version_id'):
                    d['project_id'] = owners.get(d['version_id'])

    def download_url(self, mod):
        return (mod.get('file') or {}).get('download_url', '')

    def file_page(self, mod):
        suffix = f"/version/{mod['file_id']}" if mod.get('file_id') else ''
        return f"https://modrinth.com/mod/{mod.get('slug') or mod['project_id']}{suffix}"

    def clear_cache(self):
        if self.api.cache:
            self.api.cache.clear()
