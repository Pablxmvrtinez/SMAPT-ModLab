"""Catálogo exclusivo de CurseForge y resolución de archivos para Minecraft."""
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import html
import json
import os
import re

import requests

GAME_ID=432
CLASS_ID=6
LOADERS={'Forge':1,'Fabric':4,'Quilt':5,'NeoForge':6}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Connection:
    gateway: str = ''
    api_key: str = field(default='',repr=False)

    def check(self):
        if not self.gateway and not self.api_key:
            raise CatalogError('Falta conectar el catálogo oficial de CurseForge. El desarrollador debe configurar su pasarela o clave de API; los usuarios no necesitan cuentas de IA.')
        if self.gateway:
            parsed=urlparse(self.gateway)
            if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost')):
                raise CatalogError('La pasarela debe usar HTTPS; HTTP solo se admite en localhost.')
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise CatalogError('La URL de la pasarela no debe contener claves ni credenciales.')


def connection_from_environment():
    config={}
    try:
        config=json.loads((Path(__file__).resolve().parent/'app-config.json').read_text())
    except (OSError,ValueError):pass
    if not isinstance(config,dict):config={}
    url=config.get('catalog_url','')
    if not isinstance(url,str):url=''
    return Connection(os.getenv('SMAPT_CATALOG_URL',url),
                      os.getenv('CURSEFORGE_API_KEY',''))


def plain_text(value,limit=5000):
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()[:limit]


def normalize(mod):
    logo=mod.get('logo') or {}
    return {'source':'curseforge','project_id':int(mod['id']),'title':mod['name'],
            'slug':mod.get('slug',''),'description':mod.get('summary',''),
            'url':(mod.get('links') or {}).get('websiteUrl',''),
            'logo':logo.get('thumbnailUrl') or logo.get('url',''),
            'screenshots':[s.get('url') or s.get('thumbnailUrl') for s in mod.get('screenshots',[])],
            'downloads':mod.get('downloadCount',0),
            'categories':[{'id':c['id'],'name':c['name'],'slug':c.get('slug','')} for c in mod.get('categories',[])],
            'authors':[a['name'] for a in mod.get('authors',[])],
            'updated':mod.get('dateModified','')[:10]}


class CurseForgeClient:
    def __init__(self,connection=None):
        self.connection=connection or connection_from_environment()

    def get(self,route,**params):
        self.connection.check()
        base=self.connection.gateway.rstrip('/') if self.connection.gateway else 'https://api.curseforge.com'
        headers={'Accept':'application/json','User-Agent':'SMAPT-ModLab/1.0'}
        if not self.connection.gateway:headers['x-api-key']=self.connection.api_key
        try:
            response=requests.get(base+route,params=params,headers=headers,timeout=(10,40))
            if response.status_code in (401,403):
                raise CatalogError('CurseForge rechazó el acceso al catálogo. Revisa la conexión del desarrollador.')
            if response.status_code==429:
                raise CatalogError('CurseForge ha limitado las consultas. Espera un momento y vuelve a intentarlo.')
            response.raise_for_status();data=response.json()
        except (requests.RequestException,ValueError) as exc:
            if isinstance(exc,CatalogError):raise
            raise CatalogError('No se pudo consultar CurseForge. Comprueba la conexión; no se usará otro catálogo como sustituto.') from None
        if not isinstance(data,dict) or 'data' not in data:
            raise CatalogError('CurseForge devolvió una respuesta inesperada.')
        return data

    def categories(self):
        return self.get('/v1/categories',gameId=GAME_ID,classId=CLASS_ID)['data']

    def search(self,query='',category=None,index=0,page_size=50,sort=6,minecraft='',loader=''):
        if not 1<=page_size<=50:raise CatalogError('El tamaño de página debe estar entre 1 y 50.')
        if not 0<=index<10000:raise CatalogError('Se alcanzó el límite de paginación de CurseForge.')
        params={'gameId':GAME_ID,'classId':CLASS_ID,'index':index,'pageSize':min(50,10000-index,page_size),
                'sortField':sort,'sortOrder':'desc'}
        if query:params['searchFilter']=query
        if category:params['categoryId']=int(category)
        if minecraft:params['gameVersion']=minecraft
        if loader:
            if loader not in LOADERS:raise CatalogError('Cargador no admitido.')
            params['modLoaderType']=LOADERS[loader]
        response=self.get('/v1/mods/search',**params)
        return {'mods':[normalize(m) for m in response['data']], 'pagination':response.get('pagination',{})}

    def mod(self,pid):
        raw=self.get(f'/v1/mods/{int(pid)}')['data']
        if raw.get('gameId')!=GAME_ID or raw.get('classId')!=CLASS_ID:
            raise CatalogError('El proyecto no es un mod de Minecraft.')
        return normalize(raw)

    def description(self,pid):
        return plain_text(self.get(f'/v1/mods/{int(pid)}/description')['data'])

    def compatible_file(self,pid,minecraft,loader,file_id=None):
        if loader not in LOADERS:raise CatalogError('Cargador no admitido.')
        def compatible(f):
            versions=f.get('gameVersions',[])
            return (f.get('modId')==int(pid) and f.get('isAvailable',False)
                    and not f.get('isServerPack') and f.get('releaseType')==1
                    and minecraft in versions and loader.lower() in [v.lower() for v in versions]
                    and f.get('fileName','').endswith('.jar'))
        if file_id:
            row=self.get(f'/v1/mods/{int(pid)}/files/{int(file_id)}')['data']
            if not compatible(row):raise CatalogError(f'El archivo elegido de {pid} no es una versión estable compatible con {minecraft} / {loader}.')
            return row
        for index in range(0,10000,50):
            response=self.get(f'/v1/mods/{int(pid)}/files',gameVersion=minecraft,
                              modLoaderType=LOADERS[loader],index=index,pageSize=50)
            rows=response['data']
            matching=[f for f in rows if compatible(f)]
            if matching:return max(matching,key=lambda f:f.get('fileDate',''))
            total=response.get('pagination',{}).get('totalCount',len(rows))
            if not rows or index+len(rows)>=total:break
        raise CatalogError(f'No hay archivo estable compatible para {pid} en Minecraft {minecraft} / {loader}.')

    def pin(self,mod,minecraft,loader):
        if mod.get('source')!='curseforge':raise CatalogError('Solo se admiten mods de CurseForge.')
        file=self.compatible_file(mod['project_id'],minecraft,loader,mod.get('file_id'))
        return dict(mod,file_id=file['id'],version_number=file.get('displayName') or file['fileName'],
                    file=file, minecraft=minecraft,loader=loader)

    def resolve(self,mods,minecraft,loader,progress=lambda _:None):
        if not mods:raise CatalogError('Añade al menos un mod al pack.')
        pins={int(m['project_id']):m for m in mods}
        if len(pins)!=len(mods):raise CatalogError('El pack contiene proyectos duplicados.')
        resolved={}
        def visit(mod):
            pid=int(mod['project_id'])
            if pid in resolved:return
            progress('Verificando '+mod['title'])
            item=self.pin(pins.get(pid,mod),minecraft,loader)
            resolved[pid]=item
            if len(resolved)>1000:raise CatalogError('Demasiadas dependencias; revisa el pack.')
            for dep in item['file'].get('dependencies',[]):
                if dep['relationType']==3:
                    child=int(dep['modId'])
                    if child not in resolved:visit(pins.get(child) or self.mod(child))
        for mod in mods:visit(mod)
        for item in resolved.values():
            for dep in item['file'].get('dependencies',[]):
                if dep['relationType']==5 and int(dep['modId']) in resolved:
                    raise CatalogError('Incompatibilidad declarada: '+item['title']+' ↔ '+resolved[int(dep['modId'])]['title'])
        return list(resolved.values())
