"""Contrato común de catálogos y resolución de dependencias por lotes."""
import html
import re

from modlab.errors import CatalogError, NotFoundError

LOADER_NAMES = ('Forge', 'NeoForge', 'Fabric', 'Quilt')
SORTS = ('relevance', 'downloads', 'popularity', 'updated', 'name')
MAX_PACK = 1000


def mod_key(source, project_id):
    return f'{source}:{project_id}'


def key_of(mod):
    return mod.get('key') or mod_key(mod.get('source', ''), mod['project_id'])


def plain_text(value, limit=5000):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()[:limit]


class CatalogSource:
    """Interfaz que comparten CurseForge y Modrinth.

    Cada fuente implementa ``search``, ``categories``, ``mod``, ``mods``, ``description``,
    ``versions``, ``compatible_file`` y ``pin_many``. La resolución completa del pack y la
    detección de incompatibilidades declaradas son comunes.
    """

    source = ''
    label = ''

    def available(self):
        return True

    def pin(self, mod, minecraft, loader):
        pinned, failures = self.pin_many([mod], minecraft, loader)
        if failures:
            raise CatalogError(failures[0]['reason'])
        return pinned[0]

    def resolve_report(self, mods, minecraft, loader, progress=lambda _: None, check=lambda: None):
        """Fija archivos y añade dependencias obligatorias. Devuelve un informe sin lanzar por conflictos."""
        if not mods:
            raise CatalogError('Añade al menos un mod al pack.')
        foreign = [m['title'] for m in mods if m.get('source') != self.source]
        if foreign:
            raise CatalogError(f'Estos mods no son de {self.label}: ' + ', '.join(foreign[:5]))
        ids = [m['project_id'] for m in mods]
        if len(set(ids)) != len(ids):
            raise CatalogError('El pack contiene proyectos duplicados.')
        selected = set(ids)
        resolved, missing, required_by = {}, [], {}
        pending = list(mods)
        while pending:
            check()
            progress(f'Verificando archivos en {self.label} · {len(resolved) + len(pending)} mods')
            pinned, failures = self.pin_many(pending, minecraft, loader)
            for item in pinned:
                resolved[item['project_id']] = item
            for failure in failures:
                if failure['project_id'] in selected:
                    missing.append(failure)
                else:
                    parent = required_by.get(failure['project_id'], '')
                    missing.append(dict(failure, reason=failure['reason'] + (f' (requerido por {parent})' if parent else '')))
            wanted = []
            for item in pinned:
                for dep in item['file'].get('dependencies', []):
                    pid = dep.get('project_id')
                    if dep.get('type') != 'required' or pid is None:
                        continue
                    if pid not in resolved and pid not in wanted and not any(f['project_id'] == pid for f in missing):
                        wanted.append(pid)
                        required_by.setdefault(pid, item['title'])
            if len(resolved) + len(wanted) > MAX_PACK:
                raise CatalogError('Demasiadas dependencias; revisa el pack.')
            pending = []
            if wanted:
                check()
                progress(f'Consultando {len(wanted)} dependencias obligatorias…')
                found = {m['project_id']: m for m in self.mods(wanted)}
                for pid in wanted:
                    if pid in found:
                        pending.append(found[pid])
                    else:
                        missing.append({'project_id': pid, 'title': str(pid),
                                        'reason': f'Dependencia no disponible en {self.label} (requerida por {required_by[pid]}).'})
        conflicts = []
        for item in resolved.values():
            for dep in item['file'].get('dependencies', []):
                other = resolved.get(dep.get('project_id'))
                if dep.get('type') == 'incompatible' and other:
                    pair = tuple(sorted((item['title'], other['title'])))
                    if pair not in conflicts:
                        conflicts.append(pair)
        added = sorted((m for pid, m in resolved.items() if pid not in selected), key=lambda m: m['title'].casefold())
        ordered = [resolved[pid] for pid in ids if pid in resolved] + added
        return {'mods': ordered, 'dependencies': added, 'missing': missing, 'conflicts': conflicts}

    def resolve(self, mods, minecraft, loader, progress=lambda _: None, check=lambda: None):
        report = self.resolve_report(mods, minecraft, loader, progress, check)
        if report['conflicts']:
            a, b = report['conflicts'][0]
            raise CatalogError(f'Incompatibilidad declarada: {a} ↔ {b}')
        if report['missing']:
            lines = [f"• {m['title']}: {m['reason']}" for m in report['missing'][:8]]
            raise CatalogError('Hay mods sin archivo compatible:\n' + '\n'.join(lines))
        return report['mods']

    def safe_mod(self, pid):
        try:
            return self.mod(pid)
        except NotFoundError:
            return None
