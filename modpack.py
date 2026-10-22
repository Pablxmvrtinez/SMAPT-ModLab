"""Exporta manifiestos nativos de CurseForge y resuelve el cargador oficial."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import html
import json
import re
import tempfile
import requests
from curseforge import CurseForgeClient


def build_pack(destination,name,minecraft,loader,loader_version,mods,progress=lambda _:None,client=None):
    if loader.lower() not in ('forge','fabric','neoforge'):
        raise ValueError('Cargador no admitido para exportar a CurseForge.')
    if not name.strip() or not mods:
        raise ValueError('Indica el nombre del pack y añade mods.')
    if not re.fullmatch(r'\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.]+)?',loader_version):
        raise ValueError('La versión del cargador no es válida.')
    client=client or CurseForgeClient()
    resolved=client.resolve(mods,minecraft,loader,progress)
    manifest={'minecraft':{'version':minecraft,'modLoaders':[
        {'id':loader.lower()+'-'+loader_version,'primary':True}]},
        'manifestType':'minecraftModpack','manifestVersion':1,'name':name.strip(),
        'version':'1.0.0','author':'SMAPT ModLab','overrides':'overrides',
        'files':[{'projectID':m['project_id'],'fileID':m['file_id'],'required':True} for m in resolved]}
    destination=Path(destination)
    with tempfile.TemporaryDirectory(prefix='.smapt-',dir=destination.parent) as temp:
        archive=Path(temp)/'pack.zip'
        with ZipFile(archive,'w',ZIP_DEFLATED) as z:
            z.writestr('manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False))
            z.writestr('overrides/','')
            z.writestr('modlist.html','<meta charset="utf-8"><h1>'+html.escape(name)+'</h1><ul>'+''.join(
                '<li><a href="https://www.curseforge.com/minecraft/mc-mods/'+html.escape(m.get('slug',''),quote=True)+'">'+
                html.escape(m['title'])+'</a></li>' for m in resolved)+'</ul>')
            lock=[{k:m.get(k) for k in ('source','project_id','file_id','title','version_number','reason')} for m in resolved]
            z.writestr('smapt-lock.json',json.dumps(lock,indent=2,ensure_ascii=False))
            z.writestr('IMPORTAR.txt','CurseForge → Minecraft → Importar → selecciona este ZIP.\n'
                       'Los mods están referenciados con sus IDs oficiales; CurseForge descarga los archivos.\n'
                       'Prueba el juego para comprobar conflictos no declarados.\n')
        archive.replace(destination)
    return {'path':str(destination),'mods':len(resolved)}


def audit_pack(mods, minecraft, loader, progress=lambda _: None, client=None):
    """Verifica el pack completo con CurseForge, sin exportar ni cambiar la selección."""
    if not mods:
        raise ValueError('Añade mods antes de comprobar el pack.')
    client = client or CurseForgeClient()
    resolved = client.resolve(mods, minecraft, loader, progress)
    selected_ids = {int(m['project_id']) for m in mods}
    added = sorted(
        (m for m in resolved if int(m['project_id']) not in selected_ids),
        key=lambda m: m['title'].casefold(),
    )
    return {
        'selected': len(selected_ids),
        'total': len(resolved),
        'dependencies': [
            {'project_id': m['project_id'], 'title': m['title'],
             'version': m.get('version_number', '')}
            for m in added
        ],
    }


def resolve_loader_version(minecraft, loader):
    """Consulta metadatos oficiales; no inventa versiones para el manifest."""
    import xml.etree.ElementTree as ET
    headers = {'User-Agent': 'SMAPT-ModLab/1.0'}
    def get(url):
        res = requests.get(url, headers=headers, timeout=(10, 40))
        res.raise_for_status()
        return res
    try:
        if loader.lower() == 'forge':
            promos = get('https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json').json()['promos']
            version = promos.get(minecraft + '-recommended') or promos.get(minecraft + '-latest')
        elif loader.lower() == 'fabric':
            rows = get('https://meta.fabricmc.net/v2/versions/loader/' + minecraft).json()
            version = next((r['loader']['version'] for r in rows if r['loader'].get('stable')), None)
        elif loader.lower() == 'neoforge':
            parts = minecraft.split('.')
            if len(parts) not in (2,3) or not all(p.isdigit() for p in parts) or int(parts[1]) < 20:
                raise ValueError('Indica manualmente la versión de NeoForge para este Minecraft.')
            branch = str(int(parts[1])) + '.' + (parts[2] if len(parts) == 3 else '0') + '.'
            rows = ET.fromstring(get('https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml').text)
            versions = [v.text for v in rows.findall('./versioning/versions/version')
                        if v.text and v.text.startswith(branch) and re.fullmatch(r'\d+\.\d+\.\d+', v.text)]
            version = max(versions, key=lambda v: tuple(map(int,v.split('.'))), default=None)
        else:
            raise ValueError('Cargador no admitido para exportar a CurseForge.')
        if not version:
            raise ValueError('No se encuentra un cargador estable para esta versión. Elige otra combinación o indica el build manualmente.')
        return version
    except (requests.RequestException, KeyError, TypeError, ET.ParseError):
        raise ValueError('No se pudo detectar el cargador. Comprueba la conexión o indica su versión manualmente.') from None
