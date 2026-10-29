"""Evaluación semántica con el modelo REAL: interpreta descripciones libres y comprueba su significado.

    python scripts/evaluate_ai.py                 # todas las descripciones
    python scripts/evaluate_ai.py pokemon terror  # solo algunas
    python scripts/evaluate_ai.py --json salida.json

Cada caso comprueba que la interpretación recoge los conceptos centrales (en las consultas que el modelo
genera libremente o en los mods de ejemplo), que respeta las negaciones (exclusiones y consultas sin el tema
rechazado) y que no inventa restricciones. Las comprobaciones miran el significado con expresiones amplias
de sinónimos; no se usan para generar la respuesta, solo para validarla. No consulta catálogos.
"""
from pathlib import Path
import json
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modlab.intelligence import DesignRequest, ModpackDesigner, apply_preferences  # noqa: E402
from modlab.local_ai import LocalAI  # noqa: E402

# (nombre, descripción, conceptos que deben aparecer, temas que deben excluirse, temas que no deben buscarse, extra)
CASES = [
    ('zombi', 'Quiero un Minecraft ambientado en un apocalipsis zombi. Me gustaría explorar ciudades abandonadas, utilizar '
              'armas de fuego y construir bases para sobrevivir. No quiero que sea excesivamente difícil.',
     [r'zombi|apocalyp|undead|outbreak', r'gun|firearm|weapon|rifle|pistol', r'city|cities|urban|ruin|abandon|town',
      r'base|build|shelter|bunker|fort|defen'], [], [], {'no_exclusions': True, 'limits': r'dific|hard|extrem|desafi'}),
    ('rpg', 'Quiero algo parecido a un RPG de fantasía con progresión de personaje, jefes y mazmorras, pero sin tecnología '
            'industrial.',
     [r'rpg|level|skill|class|progress|attribute|stat', r'boss', r'dungeon'], [r'tecnolog|industri|machine|tech|máquin'],
     [r'industr|machine|factory|automation|tech'], {}),
    ('casas', 'Quiero construir casas bonitas tranquilamente, sin combates adicionales, y tengo un ordenador poco potente.',
     [r'build|furniture|decor|house|block', r'perform|fps|optimi|memory|lag'], [r'combat|combate|mob|boss|monster|enem|jefe'],
     [r'boss|mob|monster|dungeon|weapon|combat|horde'], {'performance': ('prioridad',)}),
    ('terror', 'Quiero un mundo de terror con exploración, pero sin zombis.',
     [r'horror|scary|creep|fear|terror|dread|spooky', r'explor|structure|cave|dungeon|biome|ruin'], [r'zombi'], [r'zombi'], {}),
    ('magia', 'Quiero magia y dragones, pero nada de máquinas.',
     [r'magic|spell|wizard|sorcer|mana|arcane', r'dragon'], [r'machine|máquin|tech|industr|mecan|automat'],
     [r'machine|tech|industr|automation|factory'], {'performance': ('equilibrado',)}),
    ('pokemon', 'Quiero un Minecraft parecido a Pokémon',
     [r'pok[eé]mon|cobblemon|pixelmon|creature|monster|catch|captur|tam'], [], [], {'no_exclusions': True}),
    ('fps', 'Quiero mejorar FPS sin cambiar la experiencia original.',
     [r'perform|fps|optimi|memory|render|lag'], [], [r'boss|dungeon|magic|furniture|weapon|biome|dragon|mob'],
     {'performance': ('prioridad',)}),
    ('medieval', 'Quiero un mundo medieval con reinos, aldeas y guerras.',
     [r'medieval|castle|kingdom|knight', r'village|town|settlement', r'war|battle|army|siege|faction|soldier|conquest'], [], [],
     {'no_exclusions': True, 'performance': ('equilibrado',)}),
    ('tranquilo', 'Quiero algo tranquilo con mascotas, muebles y agricultura.',
     [r'pet|companion|animal|tame', r'furniture|decor', r'farm|crop|agricult|harvest|garden'], [],
     [r'boss|dungeon|horde|invasion|monster|zombie'], {}),
    ('aventura', 'Quiero un modpack de aventuras, pero sin añadir demasiados enemigos.',
     [r'adventure|explor|dungeon|structure|quest|travel'], [], [r'horde|invasion|more mobs|monster'],
     {'no_exclusions': True, 'limits': r'enem|mob|monst|hostil|combat'}),
]


def queries_of(brief):
    return [q.casefold() for r in brief['requirements'] for q in r['queries'] + r['examples']]


def judge(case, brief):
    name, _, concepts, excluded, forbidden, extra = case
    failures = []
    queries = queries_of(brief)
    exclusions = ' '.join([e['concept'] + ' ' + ' '.join(e['terms']) for e in brief['exclusions']]).casefold()
    for pattern in concepts:
        if not any(re.search(pattern, q) for q in queries):
            failures.append(f'falta el concepto /{pattern}/')
    for pattern in excluded:
        if not re.search(pattern, exclusions):
            failures.append(f'no excluye /{pattern}/')
    for pattern in forbidden:
        bad = [q for q in queries if re.search(pattern, q)]
        if bad:
            failures.append(f'busca un tema rechazado /{pattern}/: {bad}')
    if 'limits' in extra and not any(re.search(extra['limits'], (e['concept'] + ' ' + ' '.join(e['terms'])).casefold())
                                     for e in brief['limits']):
        failures.append('no recoge la moderación pedida como límite')
    if extra.get('no_exclusions') and brief['exclusions']:
        failures.append('inventa exclusiones: ' + ', '.join(e['concept'] for e in brief['exclusions']))
    if 'difficulty' in extra and brief['difficulty'] not in extra['difficulty']:
        failures.append(f"dificultad {brief['difficulty']}")
    if 'performance' in extra and brief['performance'] not in extra['performance']:
        failures.append(f"rendimiento {brief['performance']}")
    if 'only' in extra:
        other = [q for q in queries if not re.search(extra['only'], q)]
        if other:
            failures.append(f'añade contenido no pedido: {other}')
    return failures


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = Path(sys.argv[sys.argv.index('--json') + 1]) if '--json' in sys.argv else None
    if out:
        args = [a for a in args if a != str(out)]
    selected = [c for c in CASES if not args or c[0] in args]
    ai = LocalAI()
    if not ai.available():
        print('La IA local no está disponible (motor o modelo).')
        return 2
    report, failed = [], 0
    with ai.session():
        for case in selected:
            name, phrase = case[0], case[1]
            start = time.monotonic()
            request = DesignRequest(phrase, '1.20.1', 'Fabric')
            brief = apply_preferences(ModpackDesigner(None, ai).understand(phrase, request), request)
            failures = judge(case, brief)
            failed += bool(failures)
            seconds = time.monotonic() - start
            print(f"\n[{'OK ' if not failures else 'MAL'}] {name} · {seconds:.0f} s · {ai.last_stats.get('tokens_per_second')} frag/s")
            print('  ', brief['analysis'])
            for r in brief['requirements']:
                print(f"   - {r['name']} ({r['priority']}): {r['queries']} {r['examples'] or ''}")
            print('   Excluye:', [(e['concept'], e['terms']) for e in brief['exclusions']] or 'nada',
                  '· con moderación:', [e['concept'] for e in brief['limits']] or 'nada',
                  '· dificultad', brief['difficulty'], '· rendimiento', brief['performance'])
            for failure in failures:
                print('   ✗', failure)
            report.append({'case': name, 'seconds': round(seconds, 1), 'failures': failures, 'brief': brief})
    print(f'\nResultado: {len(selected) - failed}/{len(selected)} interpretaciones correctas.')
    if out:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
