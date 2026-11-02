"""Modelo del modpack y formato de proyecto (.json) independiente de la interfaz."""
import json
import re
from pathlib import Path

from modlab.errors import CatalogError
from modlab.sources.base import LOADER_NAMES, MAX_PACK, key_of

SCHEMA = 2
# Solo se guarda la selección: los términos de CurseForge (§3.1) no permiten almacenar datos de su API.
STORED = ('source', 'project_id', 'title', 'slug', 'file_id', 'version_number', 'release', 'role', 'reason', 'caveat')
PINNED = ('file_id', 'file', 'version_number', 'release', 'minecraft', 'loader')
VERSION_PATTERN = re.compile(r'^[0-9A-Za-z][0-9A-Za-z.\-_+ ]{0,31}$')
MODRINTH_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
MAX_FILE_BYTES = 5 * 1024 * 1024
LOADER_BUILD = re.compile(r'^[A-Za-z0-9.+_-]{1,60}$')


class Pack:
    def __init__(self, name='Mi modpack', minecraft='1.20.1', loader='Forge'):
        self.name = name
        self.version = '1.0.0'
        self.author = ''
        self.minecraft = minecraft
        self.loader = loader
        self.loader_version = ''  # versión manual del cargador; vacía = la recomendada oficial
        self.description = ''
        self.mods = {}

    def __len__(self):
        return len(self.mods)

    def __contains__(self, key):
        return key in self.mods

    def keys(self):
        return set(self.mods)

    def values(self):
        return list(self.mods.values())

    def add(self, mod):
        if len(self.mods) >= MAX_PACK and key_of(mod) not in self.mods:
            raise CatalogError(f'El pack ya tiene {MAX_PACK} mods.')
        mod = dict(mod, key=key_of(mod))
        self.mods[mod['key']] = mod
        return mod

    def remove(self, key):
        return self.mods.pop(key, None)

    def clear(self):
        self.mods.clear()

    def sources(self):
        return {m['source'] for m in self.mods.values()}

    def by_source(self, source):
        return [m for m in self.mods.values() if m['source'] == source]

    def set_target(self, minecraft, loader):
        """Cambiar versión o cargador invalida los archivos fijados pero conserva los proyectos."""
        if (minecraft, loader) == (self.minecraft, self.loader):
            return False
        self.minecraft, self.loader = minecraft, loader
        self.loader_version = ''  # un build manual de otra versión exportaría una combinación equivocada
        for mod in self.mods.values():
            for field in PINNED:
                mod.pop(field, None)
        return True

    def to_json(self):
        return {'schema': SCHEMA, 'app': 'smapt-modlab', 'name': self.name, 'version': self.version,
                'author': self.author, 'minecraft': self.minecraft, 'loader': self.loader,
                'loader_version': self.loader_version, 'description': self.description,
                'mods': [{k: m[k] for k in STORED if m.get(k) not in (None, '')} for m in self.mods.values()]}

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=2), encoding='utf-8')

    @classmethod
    def from_json(cls, value):
        if not isinstance(value, dict) or value.get('schema') not in (1, SCHEMA):
            raise ValueError('Formato de proyecto no admitido.')
        if value.get('schema') == 1 and value.get('source') != 'curseforge':
            raise ValueError('Formato de proyecto no admitido.')
        loader, minecraft = value.get('loader'), value.get('minecraft')
        if loader not in LOADER_NAMES or not isinstance(minecraft, str) or not VERSION_PATTERN.match(minecraft):
            raise ValueError('Versión o cargador no válido.')
        mods = value.get('mods')
        if not isinstance(mods, list) or len(mods) > MAX_PACK:
            raise ValueError('La lista de mods no es válida.')
        pack = cls(str(value.get('name') or 'Mi modpack')[:100], minecraft, loader)
        pack.version = str(value.get('version') or '1.0.0')[:32]
        pack.author = str(value.get('author') or '')[:100]
        pack.description = str(value.get('description') or '')[:4000]
        build = value.get('loader_version') or ''
        if build and (not isinstance(build, str) or not LOADER_BUILD.match(build)):
            raise ValueError('La versión manual del cargador no es válida.')
        pack.loader_version = build
        for raw in mods:
            if not isinstance(raw, dict):
                raise ValueError('El proyecto contiene mods no válidos.')
            source = raw.get('source')
            pid = raw.get('project_id')
            valid_id = ((source == 'curseforge' and type(pid) is int and pid > 0) or
                        (source == 'modrinth' and isinstance(pid, str) and MODRINTH_ID.match(pid)))
            if not valid_id or not isinstance(raw.get('title'), str) or len(raw['title']) > 200:
                raise ValueError('El proyecto contiene mods no válidos.')
            file_id = raw.get('file_id')
            if file_id is not None and not ((source == 'curseforge' and type(file_id) is int and file_id > 0) or
                                            (source == 'modrinth' and isinstance(file_id, str) and MODRINTH_ID.match(file_id))):
                raise ValueError('El proyecto contiene IDs de archivo incorrectos.')
            if f'{source}:{pid}' in pack:
                raise ValueError('El proyecto contiene mods duplicados.')
            mod = {k: raw[k] for k in STORED if k in raw}
            mod['title'] = mod['title'][:200]
            pack.add(mod)
        return pack

    @classmethod
    def load(cls, path):
        try:
            too_big = Path(path).stat().st_size > MAX_FILE_BYTES
        except OSError as exc:
            raise ValueError('No se pudo leer el archivo: ' + type(exc).__name__) from None
        if too_big:
            raise ValueError('El archivo supera el tamaño máximo de 5 MB.')
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('No se pudo leer el archivo: ' + type(exc).__name__) from None
        return cls.from_json(value)
