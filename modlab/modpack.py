"""Comprobación del pack, versiones de cargador y exportación a CurseForge (.zip) y Modrinth (.mrpack)."""
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile
import html
import json
import re
import tempfile

import requests

from modlab import USER_AGENT
from modlab.errors import CatalogError
from modlab.mrpack_validator import MrpackValidationError, safe_mod_filename, validate_exported_mrpack
from modlab.sources.modrinth import environment_sides

CURSEFORGE_LOADERS = ('forge', 'fabric', 'neoforge')
MRPACK_LOADERS = {'Forge': 'forge', 'NeoForge': 'neoforge', 'Fabric': 'fabric-loader', 'Quilt': 'quilt-loader'}
MRPACK_HOSTS = ('cdn.modrinth.com', 'github.com', 'raw.githubusercontent.com', 'gitlab.com')
LOADER_VERSION = re.compile(r'\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.]+)?')


def _check_common(name, mods, loader_version):
    if not name.strip() or not mods:
        raise ValueError('Indica el nombre del pack y añade mods.')
    if len(name.strip()) > 120:
        raise ValueError('El nombre del pack puede tener como máximo 120 caracteres.')
    if not LOADER_VERSION.fullmatch(loader_version or ''):
        raise ValueError('La versión del cargador no es válida.')


def _write_atomic(destination, writer, validate=None):
    """Escribe en un temporal, lo valida y lo mueve al final: un error nunca deja un archivo a medias."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.smapt-', dir=destination.parent) as temp:
        archive = Path(temp) / 'pack.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
            writer(z)
        if validate:
            validate(archive)
        archive.replace(destination)
    return destination


def build_pack(destination, name, minecraft, loader, loader_version, mods, progress=lambda _: None, client=None,
               author='', version='1.0.0', check=lambda: None):
    """Modpack nativo de CurseForge: manifest con projectID/fileID; el lanzador descarga los JAR."""
    if loader.lower() not in CURSEFORGE_LOADERS:
        raise ValueError('CurseForge solo importa packs de Forge, Fabric o NeoForge.')
    _check_common(name, mods, loader_version)
    if client is None:
        from modlab.sources import CurseForgeClient
        client = CurseForgeClient()
    resolved = client.resolve(mods, minecraft, loader, progress, check)
    check()
    manifest = {'minecraft': {'version': minecraft, 'modLoaders': [
        {'id': loader.lower() + '-' + loader_version, 'primary': True}]},
        'manifestType': 'minecraftModpack', 'manifestVersion': 1, 'name': name.strip(),
        'version': version.strip() or '1.0.0', 'author': author.strip() or 'SMAPT ModLab', 'overrides': 'overrides',
        'files': [{'projectID': m['project_id'], 'fileID': m['file_id'], 'required': True} for m in resolved]}

    def write(z):
        z.writestr('manifest.json', json.dumps(manifest, indent=2, ensure_ascii=False))
        z.writestr('overrides/', '')
        z.writestr('modlist.html', '<meta charset="utf-8"><h1>' + html.escape(name) + '</h1><ul>' + ''.join(
            '<li><a href="https://www.curseforge.com/minecraft/mc-mods/' + html.escape(m.get('slug', ''), quote=True) + '">' +
            html.escape(m['title']) + '</a></li>' for m in resolved) + '</ul>')
        lock = [{k: m.get(k) for k in ('source', 'project_id', 'file_id', 'title', 'version_number', 'reason')} for m in resolved]
        z.writestr('smapt-lock.json', json.dumps(lock, indent=2, ensure_ascii=False))
        z.writestr('IMPORTAR.txt', 'CurseForge → Minecraft → Importar → selecciona este ZIP.\n'
                   'Los mods están referenciados con sus IDs oficiales; CurseForge descarga los archivos.\n'
                   'Prueba el juego para comprobar conflictos no declarados.\n')
    path = _write_atomic(destination, write)
    return {'path': str(path), 'mods': len(resolved)}


def safe_jar_name(filename):
    name = str(filename)
    if (not name or '/' in name or '\\' in name or not name.endswith('.jar') or name.startswith('.')
            or not safe_mod_filename(name)):
        raise CatalogError(f'Nombre de archivo no válido en Windows o Linux: {filename!r}')
    return name


def build_mrpack(destination, name, minecraft, loader, loader_version, mods, progress=lambda _: None, client=None,
                 version='1.0.0', summary='', check=lambda: None):
    """Modpack de Modrinth (formatVersion 1) con hashes SHA-1/SHA-512 y descargas de cdn.modrinth.com."""
    if loader not in MRPACK_LOADERS:
        raise ValueError('Cargador no admitido en .mrpack.')
    _check_common(name, mods, loader_version)
    if client is None:
        from modlab.sources import ModrinthClient
        client = ModrinthClient()
    resolved = client.resolve(mods, minecraft, loader, progress, check)
    check()
    files = []
    for mod in resolved:
        file = mod.get('file') or {}
        url = file.get('download_url', '')
        if not (file.get('sha1') and file.get('sha512') and url):
            raise CatalogError(f"{mod['title']}: Modrinth no publicó hashes o URL para el archivo.")
        host = urlparse(url).hostname or ''
        if urlparse(url).scheme != 'https' or host not in MRPACK_HOSTS:
            raise CatalogError(f"{mod['title']}: la descarga no procede de un dominio admitido por .mrpack.")
        entry = {'path': 'mods/' + safe_jar_name(file.get('filename')),
                 'hashes': {'sha1': file['sha1'], 'sha512': file['sha512']},
                 'downloads': [url], 'fileSize': int(file.get('size') or 0)}
        entry['env'] = environment_sides(file.get('environment'), mod.get('client_side'), mod.get('server_side'))
        files.append(entry)
    paths = [f['path'].casefold() for f in files]
    if len(set(paths)) != len(paths):
        raise CatalogError('Dos mods usan el mismo nombre de archivo; revisa el pack.')
    index = {'formatVersion': 1, 'game': 'minecraft', 'versionId': version.strip() or '1.0.0', 'name': name.strip(),
             'files': files, 'dependencies': {'minecraft': minecraft, MRPACK_LOADERS[loader]: loader_version}}
    if summary.strip():
        index['summary'] = summary.strip()[:500]

    def write(z):
        z.writestr('modrinth.index.json', json.dumps(index, indent=2, ensure_ascii=False))

    def validate(archive):
        try:
            validate_exported_mrpack(archive, expected_count=len(files))
        except MrpackValidationError as exc:
            raise CatalogError('El paquete generado no superó la validación: ' + str(exc)) from None
    path = _write_atomic(destination, write, validate)
    return {'path': str(path), 'mods': len(resolved)}


def audit_pack(mods, minecraft, loader, progress=lambda _: None, client=None, catalogs=None, check=lambda: None):
    """Verifica el pack completo sin exportar ni cambiar la selección. Agrupa por catálogo."""
    if not mods:
        raise ValueError('Añade mods antes de comprobar el pack.')
    groups = {}
    for mod in mods:
        groups.setdefault(mod.get('source', 'curseforge'), []).append(mod)
    report = {'selected': len(mods), 'total': 0, 'dependencies': [], 'missing': [], 'conflicts': []}
    for source, group in groups.items():
        source_client = catalogs.get(source) if catalogs else client
        if source_client is None:
            from modlab.sources import CurseForgeClient
            source_client = CurseForgeClient()
        result = source_client.resolve_report(group, minecraft, loader, progress, check)
        report['total'] += len(result['mods'])
        report['dependencies'] += [{'project_id': m['project_id'], 'title': m['title'], 'source': source,
                                    'version': m.get('version_number', '')} for m in result['dependencies']]
        report['missing'] += [dict(m, source=source) for m in result['missing']]
        report['conflicts'] += result['conflicts']
    report['dependencies'].sort(key=lambda m: m['title'].casefold())
    return report


def resolve_loader_version(minecraft, loader):
    """Consulta metadatos oficiales de cada cargador; nunca inventa versiones para el manifest."""
    import xml.etree.ElementTree as ET
    headers = {'User-Agent': USER_AGENT}

    def get(url):
        res = requests.get(url, headers=headers, timeout=(10, 40))
        res.raise_for_status()
        return res
    try:
        kind = loader.lower()
        if kind == 'forge':
            promos = get('https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json').json()['promos']
            version = promos.get(minecraft + '-recommended') or promos.get(minecraft + '-latest')
        elif kind == 'fabric':
            rows = get('https://meta.fabricmc.net/v2/versions/loader/' + minecraft).json()
            version = next((r['loader']['version'] for r in rows if r['loader'].get('stable')), None)
        elif kind == 'quilt':
            rows = get('https://meta.quiltmc.org/v3/versions/loader/' + minecraft).json()
            version = next((r['loader']['version'] for r in rows if '-' not in r['loader']['version']), None)
        elif kind == 'neoforge':
            version = _neoforge_version(minecraft, get, ET)
        else:
            raise ValueError('Cargador no admitido.')
        if not version:
            raise ValueError('No se encuentra un cargador estable para esta versión. Elige otra combinación o indica el build manualmente.')
        return version
    except (requests.RequestException, KeyError, TypeError, ET.ParseError):
        raise ValueError('No se pudo detectar el cargador. Comprueba la conexión o indica su versión manualmente.') from None


def _neoforge_version(minecraft, get, ET):
    parts = minecraft.split('.')
    if not all(p.isdigit() for p in parts) or len(parts) not in (2, 3):
        raise ValueError('Indica manualmente la versión de NeoForge para este Minecraft.')
    if parts[0] == '1':
        # 1.20.2 → 20.2.x, 1.21 → 21.0.x. NeoForge 1.20.1 usaba otro artefacto: versión manual.
        if int(parts[1]) < 20 or minecraft == '1.20.1':
            raise ValueError('Indica manualmente la versión de NeoForge para este Minecraft.')
        prefix = parts[1] + '.' + (parts[2] if len(parts) == 3 else '0') + '.'
    else:
        # Versiones anuales de Minecraft (por ejemplo 26.1): solo builds publicados con ese prefijo.
        prefix = minecraft + ('.0.' if len(parts) == 2 else '.')
    rows = ET.fromstring(get('https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml').text)
    versions = [v.text for v in rows.findall('./versioning/versions/version')
                if v.text and v.text.startswith(prefix) and re.fullmatch(r'\d+(?:\.\d+){2,3}', v.text)]
    return max(versions, key=lambda v: tuple(map(int, v.split('.'))), default=None)
