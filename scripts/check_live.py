"""Comprobación real de los catálogos. No muestra ni guarda claves.

    python scripts/check_live.py               # Modrinth y CurseForge
    python scripts/check_live.py curseforge    # requiere CURSEFORGE_API_KEY o SMAPT_CATALOG_URL
    python scripts/check_live.py modrinth

Recorre búsqueda, filtros, ficha, descripción, versiones, dependencias y URL de descarga
(sin descargar el archivo). Sale con código 1 si alguna comprobación falla.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modlab.errors import CatalogError  # noqa: E402
from modlab.sources import CurseForgeClient, ModrinthClient  # noqa: E402

CASES = {'curseforge': ('jei', '1.20.1', 'Forge'), 'modrinth': ('sodium', '1.20.1', 'Fabric')}
failures = []


def step(name, action):
    start = time.monotonic()
    try:
        detail = action()
    except CatalogError as exc:
        failures.append(name)
        print(f'  ✗ {name}: {exc}')
        return None
    print(f'  ✓ {name} ({time.monotonic() - start:.1f} s){": " + detail[0] if detail and detail[0] else ""}')
    return detail[1] if detail else None


def check(client, query, minecraft, loader):
    print(f'\n{client.label} · búsqueda «{query}» en {minecraft} / {loader}')
    if not client.available():
        failures.append(client.label)
        print('  ✗ Sin conexión configurada: define CURSEFORGE_API_KEY o SMAPT_CATALOG_URL.')
        return
    categories = step('Categorías', lambda: (lambda c: (f'{len(c)} categorías', c))(client.categories()))
    found = step('Búsqueda filtrada', lambda: (lambda r: (f"{r['pagination']['totalCount']} resultados", r['mods']))(
        client.search(query, minecraft=minecraft, loader=loader, page_size=10)))
    if not found:
        failures.append('Sin resultados')
        return
    mod = next((m for m in found if m['slug'] in (query, 'jei', 'sodium')), found[0])
    print(f"    Primer resultado: {mod['title']} · {mod['downloads']:,} descargas · logo={'sí' if mod['logo'] else 'no'}")
    if categories:
        step('Filtro por categoría', lambda: (lambda r: (f"{r['pagination']['totalCount']} resultados", r))(
            client.search(category=categories[0]['id'], minecraft=minecraft, loader=loader, page_size=5)))
    step('Ficha del mod', lambda: (client.mod(mod['project_id'])['title'], None))
    step('Descripción', lambda: (lambda d: (f"{len(d['text'])} caracteres ({d['format']})", None))(client.description(mod['project_id'])))
    step('Versiones compatibles', lambda: (lambda v: (f"{v['total']} archivos", None))(client.versions(mod['project_id'], minecraft, loader)))
    pinned = step('Archivo fijado', lambda: (lambda p: (p['version_number'], p))(client.pin(mod, minecraft, loader)))
    if pinned:
        deps = pinned['file']['dependencies']
        print(f"    Dependencias declaradas: {len(deps)} ({', '.join(sorted({d['type'] for d in deps})) or 'ninguna'})")
        step('URL de descarga autorizada', lambda: (lambda u: (u.split('/')[2] if u else 'no permitida por el autor', None))(
            client.download_url(pinned)))
    step('Resolución con dependencias', lambda: (lambda r: (f"{len(r['mods'])} mods, {len(r['missing'])} sin archivo", None))(
        client.resolve_report([mod], minecraft, loader)))


def main():
    wanted = sys.argv[1:] or ['modrinth', 'curseforge']
    for name in wanted:
        query, minecraft, loader = CASES[name]
        client = CurseForgeClient() if name == 'curseforge' else ModrinthClient(cache=False)
        if name == 'curseforge' and client.connection.mode:
            print(f'\nCurseForge · modo {"clave directa" if client.connection.mode == "direct" else "pasarela"}')
        check(client, query, minecraft, loader)
    print('\nResultado:', 'TODO CORRECTO' if not failures else 'FALLOS en ' + ', '.join(failures))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
