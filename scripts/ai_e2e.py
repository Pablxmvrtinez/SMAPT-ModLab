"""Prueba de extremo a extremo con el modelo REAL y datos reales de Modrinth.

    python scripts/ai_e2e.py                       # modo B: crea y exporta un modpack
    python scripts/ai_e2e.py --recommend           # modo A: solo recomendaciones
    python scripts/ai_e2e.py --text "Quiero …" --target 12 --output pack.mrpack

Interpreta la descripción, busca en Modrinth (1.20.1 · Fabric por defecto), evalúa, monta el modpack,
exporta el .mrpack oficial y lo valida. No descarga JAR ni arranca Minecraft: que el pack funcione en
el juego hay que comprobarlo importándolo en un lanzador.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modlab.intelligence import DesignRequest, ModpackDesigner, brief_text  # noqa: E402
from modlab.local_ai import LocalAI  # noqa: E402
from modlab.modpack import build_mrpack, resolve_loader_version  # noqa: E402
from modlab.mrpack_validator import validate_exported_mrpack  # noqa: E402
from modlab.sources import ModrinthClient  # noqa: E402

DEFAULT = ('Quiero construir casas bonitas tranquilamente, sin combates adicionales, '
           'y tengo un ordenador poco potente.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text', default=DEFAULT)
    parser.add_argument('--target', type=int, default=12)
    parser.add_argument('--minecraft', default='1.20.1')
    parser.add_argument('--loader', default='Fabric')
    parser.add_argument('--recommend', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    ai = LocalAI()
    if not ai.available():
        print('La IA local no está disponible (motor o modelo).')
        return 2
    catalog = ModrinthClient()
    request = DesignRequest(args.text, args.minecraft, args.loader, args.target,
                            mode='recommend' if args.recommend else 'create')
    start = time.monotonic()
    last = ['']

    def progress(message, fraction=-1):
        head = message.split('\n')[0].split(' · La IA')[0]
        if head != last[0]:
            last[0] = head
            print(f'[{time.monotonic() - start:5.0f} s] {head}', flush=True)
    result = ModpackDesigner(catalog, ai).run(request, progress)
    print('\nINTERPRETACIÓN\n' + brief_text(result['brief']))
    print(f"\n{len(result['mods'])} mods · {result['stats']}")
    for mod in result['mods']:
        print(f"  · {mod['title']} [{mod['requirement']} · {mod['role']} · {mod['fit']}/10] {mod.get('version_number', '')}")
        print(f"      {mod['reason']}")
    for dep in result['dependencies']:
        print(f"  + dependencia: {dep['title']} {dep.get('version_number', '')}")
    print('Descartados:', len(result['rejected']), [r['title'] for r in result['rejected'][:8]])
    for note in result['warnings']:
        print('Aviso:', note)
    if result['mode'] == 'create':
        loader_version = resolve_loader_version(args.minecraft, args.loader)
        output = args.output or Path(tempfile.gettempdir()) / 'smapt-ai-e2e.mrpack'
        exported = build_mrpack(output, 'ModLab IA e2e', args.minecraft, args.loader, loader_version, result['mods'],
                                client=catalog, summary=args.text[:200])
        report = validate_exported_mrpack(output, expected_count=exported['mods'])
        print(f"\n.mrpack exportado y validado: {output} · {report['mods']} archivos · Minecraft {report['minecraft']} · "
              f"{report['loader']} {loader_version}")
    print(f'\nTiempo total: {time.monotonic() - start:.0f} s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
