"""Preferencias del usuario en JSON. Nunca guarda claves de API."""
import json
import os
import tempfile

from modlab import logs, paths
from modlab.sources.base import LOADER_NAMES

log = logs.get('settings')
DEFAULTS = {'gateway': '', 'minecraft': '1.20.1', 'loader': 'Forge', 'source': 'curseforge',
            'allow_unstable': False, 'author': '', 'last_folder': ''}
SECRET_FIELDS = ('api_key', 'curseforge_api_key', 'key')


class Settings(dict):
    def __init__(self, folder=None):
        super().__init__(DEFAULTS)
        self.folder = folder or paths.config_dir()
        self.file = self.folder / 'settings.json'
        self.load()

    def load(self):
        for name in ('catalog.json', 'settings.json'):
            # catalog.json es el formato de la versión 1 (solo guardaba la URL de la pasarela).
            try:
                value = json.loads((self.folder / name).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if not isinstance(value, dict):
                continue
            if name == 'catalog.json' and isinstance(value.get('catalog_url'), str):
                self['gateway'] = value['catalog_url']
            for key, default in DEFAULTS.items():
                if key in value and isinstance(value[key], type(default)):
                    self[key] = value[key]
        if self['loader'] not in LOADER_NAMES:
            self['loader'] = DEFAULTS['loader']
        if self['source'] not in ('curseforge', 'modrinth'):
            self['source'] = DEFAULTS['source']

    def save(self):
        data = {k: v for k, v in self.items() if k in DEFAULTS and k not in SECRET_FIELDS}
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(dir=self.folder, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(temp, self.file)
            return True
        except OSError as exc:
            log.warning('No se pudieron guardar los ajustes: %s', exc)
            return False
