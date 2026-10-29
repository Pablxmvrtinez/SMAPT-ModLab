"""Lógica del diseñador con IA usando un modelo y un catálogo simulados (sin red ni inferencia real).

La comprensión semántica real se comprueba con el modelo en scripts/evaluate_ai.py y tests/test_ai_real.py.
"""
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from zipfile import ZipFile

from modlab.errors import Cancelled, CatalogError
from modlab.intelligence import (BRIEF_EVENT, EVALUATE_SCHEMA, INTERPRET_SCHEMA, NEGATION_SCHEMA, DesignRequest,
                                 ModpackDesigner, excluded_by, grounded, validate_brief)
from modlab.modpack import build_mrpack
from modlab.sources.base import CatalogSource


def mod(pid, title, description='', categories=(), downloads=1000):
    return {'source': 'modrinth', 'key': f'modrinth:{pid}', 'project_id': pid, 'title': title, 'slug': title.lower().replace(' ', '-'),
            'description': description, 'categories': [{'id': c, 'name': c} for c in categories], 'downloads': downloads,
            'logo': '', 'screenshots': []}


class FakeCatalog(CatalogSource):
    source = 'modrinth'
    label = 'Modrinth'

    def __init__(self, results, deps=None, no_file=(), incompatible=()):
        self.results = results
        self.deps = deps or {}
        self.no_file = set(no_file)
        self.incompatible = dict(incompatible)
        self.queries = []
        self.all = {m['project_id']: m for mods in results.values() for m in mods}

    def categories(self):
        return [{'id': 'adventure', 'name': 'adventure'}, {'id': 'decoration', 'name': 'decoration'},
                {'id': 'technology', 'name': 'technology'}]

    def search(self, query='', category=None, index=0, page_size=50, sort='downloads', minecraft='', loader=''):
        key = query or ('category:' + str(category))
        self.queries.append(key)
        return {'mods': self.results.get(key, [])[:page_size], 'pagination': {'totalCount': 0}}

    def mods(self, ids):
        return [self.all[i] for i in ids if i in self.all]

    def pin_many(self, mods, minecraft, loader, allow_unstable=False):
        pinned, failures = [], []
        for m in mods:
            if m['project_id'] in self.no_file:
                failures.append({'project_id': m['project_id'], 'title': m['title'], 'reason': 'Sin archivo estable.'})
                continue
            deps = [{'project_id': d, 'type': 'required'} for d in self.deps.get(m['project_id'], [])]
            if m['project_id'] in self.incompatible:
                deps.append({'project_id': self.incompatible[m['project_id']], 'type': 'incompatible'})
            name = m['project_id'].lower() + '.jar'
            pinned.append(dict(m, file_id='v' + m['project_id'], version_number='1.0', release='release',
                               file={'filename': name, 'sha1': 'a' * 40, 'sha512': 'b' * 128, 'size': 10,
                                     'download_url': f"https://cdn.modrinth.com/data/{m['project_id']}/{name}",
                                     'environment': 'client_and_server', 'dependencies': deps}))
        return pinned, failures


class FakeAI:
    """Devuelve el plan indicado y puntúa las fichas con una tabla título → (fit, requisito, rol, conflicto)."""

    def __init__(self, brief, scores):
        self.brief = brief
        self.scores = scores
        self.calls = []
        self.last_stats = {'tokens_per_second': 9.0}

    def session(self):
        return nullcontext()

    def complete(self, instruction, data, schema, progress=lambda _: None, max_tokens=0):
        self.calls.append((schema, data))
        progress('escribiendo')
        if schema is NEGATION_SCHEMA:
            return {'rejections': json.loads(json.dumps(self.brief.get('exclusions', [])))}
        if schema is INTERPRET_SCHEMA:
            assert 'rejected' in data
            return {k: v for k, v in json.loads(json.dumps(self.brief)).items() if k != 'exclusions'}
        assert schema is EVALUATE_SCHEMA
        result = []
        for card in data['cards']:
            fit, requirement, role, conflict = self.scores.get(card['title'], (0, 0, '', False))
            result.append({'id': card['id'], 'fit': fit, 'requirement': requirement, 'role': role, 'conflict': conflict,
                           'reason': f'{card["title"]} encaja con la idea.' if fit >= 6 else ''})
        return {'evaluations': result}


def brief(**extra):
    value = {'analysis': 'Quiere supervivencia zombi urbana con armas, sin magia.', 'summary': 'Apocalipsis zombi.',
             'setting': 'Ciudades en ruinas', 'difficulty': 'moderada', 'combat': 'Moderado', 'performance_priority': False,
             'requirements': [
                 {'name': 'Armas de fuego', 'detail': 'Disparar', 'priority': 'obligatorio',
                  'queries': ['guns', 'firearms', 'magic guns'], 'examples': ['Gun Mod X'], 'categories': ['adventure', 'Inventada']},
                 {'name': 'Ciudades abandonadas', 'detail': 'Explorar', 'priority': 'obligatorio',
                  'queries': ['abandoned cities'], 'examples': [], 'categories': []},
                 {'name': 'Bases', 'detail': 'Construir refugios', 'priority': 'opcional',
                  'queries': ['base building'], 'examples': [], 'categories': []}],
             'exclusions': [{'quote': 'sin magia', 'concept': 'Magia', 'strength': 'total', 'terms': ['magic', 'spell', 'magia']}],
             'assumptions': ['Multijugador opcional']}
    value.update(extra)
    return value


GUNS = mod('G1', 'Gun Mod X', 'Realistic guns and ammo', ['adventure'])
GUNS2 = mod('G2', 'Firearms Plus', 'More firearms', ['adventure'])
CITY = mod('C1', 'Ruined Cities', 'Abandoned cities and loot', ['adventure'])
CITY2 = mod('C2', 'Urban Ruins', 'Post apocalyptic towns', ['adventure'])
BASE = mod('B1', 'Fortify', 'Walls and base defenses', ['decoration'])
WAND = mod('W1', 'Wand Guns', 'Shoot spells with magic wands', ['adventure'])
LIB = mod('L1', 'Core Lib', 'Library', ['library'])
SCORES = {'Gun Mod X': (10, 1, 'armas de fuego', False), 'Firearms Plus': (8, 1, 'armas de fuego', False),
          'Ruined Cities': (9, 2, 'ciudades', False), 'Urban Ruins': (8, 2, 'ciudades en ruinas', False),
          'Fortify': (7, 3, 'defensas', False), 'Wand Guns': (9, 1, 'armas mágicas', False)}
RESULTS = {'guns': [GUNS, WAND, LIB], 'firearms': [GUNS2, GUNS], 'Gun Mod X': [mod('X9', 'Something Else'), GUNS],
           'abandoned cities': [CITY, CITY2], 'base building': [BASE], 'category:adventure': [CITY2]}


def request(**extra):
    value = dict(description='Quiero un apocalipsis zombi con armas de fuego, ciudades abandonadas y bases, sin magia.',
                 minecraft='1.20.1', loader='Fabric', target=4)
    value.update(extra)
    return DesignRequest(**value)


class InterpretationTests(unittest.TestCase):
    def test_queries_are_free_text_and_excluded_topics_removed(self):
        value = validate_brief(brief(), request().description)
        self.assertEqual(value['requirements'][0]['queries'], ['guns', 'firearms'])  # «magic guns» pide un tema excluido
        self.assertEqual(value['exclusions'][0]['concept'], 'Magia')
        self.assertNotIn('enum', json.dumps(INTERPRET_SCHEMA['properties']['requirements']['items']['properties']['queries']))
        self.assertNotIn('categories', json.dumps(INTERPRET_SCHEMA))  # sin lista de categorías que condicione al modelo

    def test_invented_exclusions_are_dropped(self):
        invented = dict(brief(), exclusions=[{'quote': 'sin fantasía', 'concept': 'Fantasía', 'strength': 'total', 'terms': ['fantasy']},
                                             {'quote': 'ciudades abandonadas', 'concept': 'Ciudades', 'strength': 'total', 'terms': ['city']}])
        value = validate_brief(invented, 'Quiero un mundo medieval con reinos, aldeas y ciudades abandonadas.')
        self.assertEqual(value['exclusions'], [])  # la primera cita no está en el texto; la segunda no es un rechazo
        self.assertTrue(grounded('nada de máquinas', 'Quiero magia y dragones, pero nada de maquinas.'))

    def test_moderation_is_a_limit_not_a_filter(self):
        moderate = dict(brief(), exclusions=[{'quote': 'sin añadir demasiados enemigos', 'concept': 'Enemigos', 'strength': 'total',
                                              'terms': ['mob', 'enemy']}])
        value = validate_brief(moderate, 'Quiero un modpack de aventuras, pero sin añadir demasiados enemigos.')
        self.assertEqual(value['exclusions'], [])
        self.assertEqual(value['limits'][0]['concept'], 'Enemigos')

    def test_negated_queries_and_duplicates_are_removed(self):
        raw = dict(brief(), requirements=[{'name': 'Paz', 'detail': '', 'priority': 'obligatorio', 'queries': ['no mobs', 'peaceful', 'without combat'], 'examples': []},
                                          {'name': 'Paz', 'detail': '', 'priority': 'opcional', 'queries': ['calm'], 'examples': []},
                                          {'name': 'Muebles', 'detail': '', 'priority': 'opcional', 'queries': ['peaceful', 'furniture'], 'examples': []}])
        value = validate_brief(raw, request().description)
        self.assertEqual([r['queries'] for r in value['requirements']], [['peaceful'], ['furniture']])

    def test_plan_without_searchable_requirements_is_rejected(self):
        with self.assertRaises(CatalogError):
            validate_brief(dict(brief(), requirements=[{'name': 'x', 'queries': [], 'examples': []}]), 'texto')

    def test_low_end_pc_sets_performance(self):
        value, _ = ModpackDesigner(FakeCatalog(RESULTS), FakeAI(dict(brief(), performance_priority=True), SCORES)).interpret(request())
        self.assertEqual(value['performance'], 'prioridad')
        self.assertEqual(value['requirements'][-1]['name'], 'Rendimiento')

    def test_performance_preference_adds_requirement(self):
        ai = FakeAI(brief(), SCORES)
        value, _ = ModpackDesigner(FakeCatalog(RESULTS), ai).interpret(request(performance='rendimiento'))
        self.assertEqual(value['performance'], 'prioridad')
        self.assertEqual(value['requirements'][-1]['name'], 'Rendimiento')
        self.assertIs(ai.calls[0][0], NEGATION_SCHEMA)  # primero se pregunta qué rechaza el jugador
        self.assertEqual(ai.calls[1][1]['rejected'], ['Magia'])
        self.assertEqual(ai.calls[1][1]['performance_preference'], 'rendimiento')

    def test_exclusion_matches_whole_words(self):
        self.assertEqual(excluded_by(WAND, [{'concept': 'Magia', 'terms': ['magic'], 'categories': []}]), 'Magia')
        self.assertIsNone(excluded_by(mod('M', 'Magical Mystery', 'Tour bus'), [{'concept': 'Magia', 'terms': ['magic'], 'categories': []}]))


class RecommendTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FakeCatalog(RESULTS)
        self.ai = FakeAI(brief(), SCORES)
        self.designer = ModpackDesigner(self.catalog, self.ai, workers=1)

    def test_generated_queries_reach_the_real_catalog(self):
        self.designer.recommend(request())
        for query in ('guns', 'firearms', 'abandoned cities', 'base building', 'Gun Mod X'):
            self.assertIn(query, self.catalog.queries)
        self.assertEqual(len(self.catalog.queries), len(set(self.catalog.queries)))  # sin búsquedas repetidas

    def test_recommendations_respect_exclusions_coverage_and_reasons(self):
        events = []
        result = self.designer.recommend(request(target=4), lambda m, f=-1: events.append(m))
        titles = [m['title'] for m in result['mods']]
        self.assertNotIn('Wand Guns', titles)  # excluido por «magic» antes de llegar al modelo
        self.assertNotIn('Core Lib', titles)  # bibliotecas: se añaden solas como dependencias
        self.assertNotIn('Something Else', titles)  # el ejemplo no coincidía con el título
        self.assertIn('Gun Mod X', titles)
        self.assertIn('Ruined Cities', titles)
        self.assertLessEqual(len(titles), 4)
        self.assertTrue(all(m['reason'] and m['requirement'] for m in result['mods']))
        self.assertTrue(any('Wand Guns' == r['title'] and 'Magia' in r['reason'] for r in result['rejected']))
        evaluated = [c['title'] for schema, data in self.ai.calls if schema is EVALUATE_SCHEMA for c in data['cards']]
        self.assertNotIn('Wand Guns', evaluated)
        self.assertTrue(any(e.startswith(BRIEF_EVENT) for e in events))
        self.assertEqual({r['requirement'] for r in result['coverage'] if r['mods']},
                         {'Armas de fuego', 'Ciudades abandonadas', 'Bases'})

    def test_low_fit_and_conflicts_are_not_recommended(self):
        scores = dict(SCORES, **{'Fortify': (4, 3, 'defensas', False), 'Urban Ruins': (9, 2, 'hordas', True)})
        result = ModpackDesigner(self.catalog, FakeAI(brief(), scores), workers=1).recommend(request(target=10))
        titles = [m['title'] for m in result['mods']]
        self.assertNotIn('Fortify', titles)
        self.assertNotIn('Urban Ruins', titles)
        self.assertTrue(any(r['title'] == 'Urban Ruins' for r in result['rejected']))

    def test_mod_without_file_is_replaced(self):
        catalog = FakeCatalog(RESULTS, no_file=['G1'])
        result = ModpackDesigner(catalog, FakeAI(brief(), SCORES), workers=1).recommend(request(target=3))
        titles = [m['title'] for m in result['mods']]
        self.assertNotIn('Gun Mod X', titles)
        self.assertEqual(len(titles), 3)
        self.assertTrue(all(m['file_id'] for m in result['mods']))

    def test_noisy_model_output_is_tolerated(self):
        class Noisy(FakeAI):
            def complete(self, instruction, data, schema, progress=lambda _: None, max_tokens=0):
                value = super().complete(instruction, data, schema, progress, max_tokens)
                if schema is EVALUATE_SCHEMA:
                    value['evaluations'] += [{'id': 99, 'fit': 10, 'requirement': 1, 'role': 'x', 'conflict': False, 'reason': 'x'},
                                             dict(value['evaluations'][0], fit=0)]
                return value
        result = ModpackDesigner(self.catalog, Noisy(brief(), SCORES), workers=1).recommend(request())
        self.assertTrue(result['mods'])

    def test_cancellation_stops_the_pipeline(self):
        calls = {'n': 0}

        def check():
            calls['n'] += 1
            if calls['n'] > 2:
                raise Cancelled()
        with self.assertRaises(Cancelled):
            self.designer.recommend(request(), check=check)


class CreateTests(unittest.TestCase):
    def test_modpack_is_balanced_resolves_dependencies_and_exports(self):
        lib = mod('L1', 'Core Lib', 'Library', ['library'])
        results = dict(RESULTS, **{'guns': [GUNS, WAND, lib]})
        catalog = FakeCatalog(results, deps={'G1': ['L1']})
        result = ModpackDesigner(catalog, FakeAI(brief(), SCORES), workers=1).create(request(target=4, mode='create'))
        titles = [m['title'] for m in result['mods']]
        roles = [m['role'] for m in result['mods']]
        self.assertEqual(len(roles), len(set(roles)))  # sin funciones repetidas en el modo B
        self.assertIn('Gun Mod X', titles)
        self.assertEqual([d['title'] for d in result['dependencies']], ['Core Lib'])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'zombi.mrpack'
            exported = build_mrpack(path, 'Zombi', '1.20.1', 'Fabric', '0.16.10', result['mods'], client=catalog)
            with ZipFile(path) as z:
                files = json.loads(z.read('modrinth.index.json'))['files']
        self.assertEqual(exported['mods'], len(titles) + 1)
        self.assertIn('mods/l1.jar', [f['path'] for f in files])

    def test_incompatible_pair_keeps_best_and_finds_alternative(self):
        catalog = FakeCatalog(RESULTS, incompatible={'G1': 'C1'})
        result = ModpackDesigner(catalog, FakeAI(brief(), SCORES), workers=1).create(request(target=3, mode='create'))
        titles = [m['title'] for m in result['mods']]
        self.assertIn('Gun Mod X', titles)
        self.assertNotIn('Ruined Cities', titles)
        self.assertIn('Urban Ruins', titles)  # alternativa del mismo requisito
        self.assertTrue(any(r['title'] == 'Ruined Cities' and 'Incompatible' in r['reason'] for r in result['rejected']))

    def test_nothing_compatible_is_reported_honestly(self):
        catalog = FakeCatalog(RESULTS, no_file=['G1', 'G2', 'C1', 'C2', 'B1'])
        with self.assertRaises(CatalogError):
            ModpackDesigner(catalog, FakeAI(brief(), SCORES), workers=1).create(request(mode='create'))


if __name__ == '__main__':
    unittest.main()
