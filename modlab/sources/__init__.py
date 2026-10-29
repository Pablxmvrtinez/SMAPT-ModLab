"""Catálogos de mods disponibles."""
from modlab.sources.base import CatalogSource, key_of, mod_key, plain_text
from modlab.sources.curseforge import Connection, CurseForgeClient, connection_from_environment
from modlab.sources.modrinth import ModrinthClient

SOURCES = ('curseforge', 'modrinth')
LABELS = {'curseforge': 'CurseForge', 'modrinth': 'Modrinth'}


class Catalogs:
    """Agrupa las fuentes para que la interfaz y los servicios elijan por nombre."""

    def __init__(self, curseforge=None, modrinth=None):
        self.curseforge = curseforge or CurseForgeClient()
        self.modrinth = modrinth or ModrinthClient()

    def get(self, source):
        if source == 'curseforge':
            return self.curseforge
        if source == 'modrinth':
            return self.modrinth
        raise ValueError(f'Catálogo desconocido: {source}')

    def __iter__(self):
        return iter((self.curseforge, self.modrinth))


__all__ = ['CatalogSource', 'Catalogs', 'Connection', 'CurseForgeClient', 'ModrinthClient',
           'connection_from_environment', 'key_of', 'mod_key', 'plain_text', 'SOURCES', 'LABELS']
