"""Descarga de los JAR del pack desde las URL oficiales, con verificación de hash.

CurseForge: solo se descargan archivos cuyo autor permite la distribución por terceros
(``allowModDistribution``); el resto se enlaza para descargarlo manualmente desde la web.
"""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import requests

from modlab import logs
from modlab.errors import Cancelled, CatalogError
from modlab.http import session
from modlab.modpack import safe_jar_name

log = logs.get('downloads')
ALLOWED_HOSTS = ('cdn.modrinth.com', 'edge.forgecdn.net', 'mediafilez.forgecdn.net')
CHUNK = 256 * 1024


def allowed_url(url):
    parsed = urlparse(url or '')
    host = parsed.hostname or ''
    return parsed.scheme == 'https' and (host in ALLOWED_HOSTS or host.endswith('.forgecdn.net'))


def plan(resolved, catalogs, check=lambda: None):
    """Clasifica cada mod en descargable o manual (con enlace a su página oficial)."""
    items, manual = [], []
    for mod in resolved:
        check()
        client = catalogs.get(mod['source'])
        url = client.download_url(mod)
        file = mod.get('file') or {}
        if url and allowed_url(url):
            items.append({'mod': mod, 'url': url, 'filename': safe_jar_name(file.get('filename', '')),
                          'size': int(file.get('size') or 0), 'sha1': file.get('sha1', ''), 'sha512': file.get('sha512', '')})
        else:
            manual.append({'title': mod['title'], 'page': client.file_page(mod),
                           'reason': 'El autor no permite descargas desde aplicaciones de terceros.'
                           if mod.get('allow_distribution') is False else 'No hay URL de descarga autorizada.'})
    return items, manual


def _digest(path, algorithm):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def _matches(path, item):
    if not path.is_file() or (item['size'] and path.stat().st_size != item['size']):
        return False
    if item.get('sha512'):
        return _digest(path, 'sha512') == item['sha512']
    if item.get('sha1'):
        return _digest(path, 'sha1') == item['sha1']
    return False


def download_all(items, folder, progress=lambda fraction, message: None, check=lambda: None, http=None):
    """Descarga en ``folder``. Devuelve listas de descargados, existentes y fallidos."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    http = http or session()
    total = sum(i['size'] for i in items) or len(items) or 1
    done_bytes = 0
    report = {'downloaded': [], 'existing': [], 'failed': []}
    for number, item in enumerate(items, 1):
        check()
        target = folder / item['filename']
        label = f"{number}/{len(items)} · {item['mod']['title']}"
        if _matches(target, item):
            report['existing'].append(item['filename'])
            done_bytes += item['size'] or 1
            progress(done_bytes / total, 'Ya descargado · ' + label)
            continue
        part = target.with_name(target.name + '.part')
        try:
            with http.get(item['url'], stream=True, timeout=(10, 60)) as response:
                if not allowed_url(response.url):
                    raise CatalogError('La descarga redirigió a un dominio no autorizado.')
                response.raise_for_status()
                sha1, sha512 = hashlib.sha1(), hashlib.sha512()
                received = 0
                with open(part, 'wb') as handle:
                    for block in response.iter_content(CHUNK):
                        check()
                        handle.write(block)
                        sha1.update(block)
                        sha512.update(block)
                        received += len(block)
                        progress((done_bytes + received) / total, 'Descargando ' + label)
            if item['sha512'] and sha512.hexdigest() != item['sha512'] or item['sha1'] and sha1.hexdigest() != item['sha1']:
                raise CatalogError('El archivo descargado no coincide con el hash publicado.')
            if not item['sha512'] and not item['sha1']:
                raise CatalogError('El catálogo no publicó un hash para verificar el archivo.')
            os.replace(part, target)
            report['downloaded'].append(item['filename'])
            done_bytes += item['size'] or received
        except Cancelled:
            part.unlink(missing_ok=True)
            raise
        except (requests.RequestException, OSError, CatalogError) as exc:
            part.unlink(missing_ok=True)
            reason = str(exc) if isinstance(exc, CatalogError) else 'Error de red o de disco (' + type(exc).__name__ + ')'
            log.warning('Descarga fallida de %s: %s', item['filename'], reason)
            report['failed'].append({'title': item['mod']['title'], 'reason': reason})
            done_bytes += item['size'] or 1
    progress(1.0, 'Descargas terminadas')
    return report
