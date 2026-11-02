"""Contrato con la API v2 de Modrinth mediante respuestas simuladas."""
import json
import tempfile
import unittest

from modlab.errors import CatalogError
from modlab.http import JsonCache
from modlab.sources.modrinth import ModrinthClient, normalize
from fakes import FakeHttp, FakeResponse


def hit(pid='AANobbMI', slug='sodium', **extra):
    value = {'project_id': pid, 'slug': slug, 'title': slug.title(), 'description': 'Rápido',
             'categories': ['fabric', 'optimization'], 'display_categories': ['fabric', 'optimization'],
             'downloads': 5, 'icon_url': 'https://cdn.modrinth.com/icon.webp', 'gallery': ['https://cdn.modrinth.com/a.webp'],
             'author': 'jelly', 'date_modified': '2026-10-01T00:00:00Z', 'client_side': 'required', 'server_side': 'unsupported'}
    value.update(extra)
    return value


def version(vid='v1', pid='AANobbMI', deps=(), kind='release', date='2026-01-01T00:00:00Z', loaders=('fabric',)):
    return {'id': vid, 'project_id': pid, 'name': 'Sodium 1.0', 'version_number': '1.0', 'version_type': kind,
            'loaders': list(loaders), 'game_versions': ['1.20.1'], 'date_published': date, 'status': 'listed',
            'dependencies': list(deps),
            'files': [{'primary': True, 'filename': f'{pid}-{vid}.jar', 'size': 3,
                       'url': f'https://cdn.modrinth.com/data/{pid}/versions/{vid}/{pid}.jar',
                       'hashes': {'sha1': 'b' * 40, 'sha512': 'c' * 128}}]}


def client(routes, cache=False):
    http = FakeHttp(routes)
    return ModrinthClient(cache=cache, http=http), http


class ModrinthTests(unittest.TestCase):
    def test_search_builds_facets_and_normalizes(self):
        mr, http = client({('GET', '/v2/search'): {'hits': [hit()], 'offset': 50, 'total_hits': 120}})
        result = mr.search('sodium', category='optimization', index=50, minecraft='1.20.1', loader='Fabric')
        params = http.calls[0]['params']
        self.assertEqual(json.loads(params['facets']), [['project_type:mod'], ['categories:optimization'],
                                                        ['versions:1.20.1'], ['categories:fabric']])
        self.assertEqual(params['index'], 'relevance')
        self.assertEqual(params['offset'], 50)
        mod = result['mods'][0]
        self.assertEqual(mod['key'], 'modrinth:AANobbMI')
        self.assertEqual([c['name'] for c in mod['categories']], ['optimization'])
        self.assertEqual(mod['loaders'], ['Fabric'])
        self.assertEqual(result['pagination'], {'index': 50, 'totalCount': 120})

    def test_pin_prefers_latest_release(self):
        rows = [version('beta', kind='beta', date='2026-05-01'), version('old', date='2025-01-01'), version('new', date='2026-02-01')]
        mr, http = client({('GET', '/v2/project/AANobbMI/version'): rows})
        pinned = mr.pin(normalize(hit()), '1.20.1', 'Fabric')
        self.assertEqual(pinned['file_id'], 'new')
        self.assertEqual(json.loads(http.calls[0]['params']['loaders']), ['fabric'])

    def test_beta_is_used_only_when_no_release_exists(self):
        mr, _ = client({('GET', '/v2/project/AANobbMI/version'): [version('b', kind='beta')]})
        self.assertEqual(mr.pin(normalize(hit()), '1.20.1', 'Fabric')['release'], 'beta')
        mr, _ = client({('GET', '/v2/project/AANobbMI/version'): [version('a', kind='alpha')]})
        with self.assertRaises(CatalogError):
            mr.pin(normalize(hit()), '1.20.1', 'Fabric')
        self.assertEqual(mr.pin_many([normalize(hit())], '1.20.1', 'Fabric', allow_unstable=True)[0][0]['file_id'], 'a')

    def test_release_without_verifiable_jar_falls_back_to_beta(self):
        broken = version('rel', date='2026-09-01')
        broken['files'][0]['url'] = 'https://evil.example/sodium.jar'
        unlisted = version('hidden', date='2026-10-01')
        unlisted['status'] = 'unlisted'
        mr, _ = client({('GET', '/v2/project/AANobbMI/version'): [broken, unlisted, version('b', kind='beta')]})
        self.assertEqual(mr.pin(normalize(hit()), '1.20.1', 'Fabric')['file_id'], 'b')

    def test_unverifiable_files_are_ignored(self):
        from modlab.sources.modrinth import verifiable
        good = {'filename': 'a.jar', 'url': 'https://cdn.modrinth.com/data/a/a.jar', 'size': 5,
                'hashes': {'sha1': 'a' * 40, 'sha512': 'b' * 128}}
        self.assertTrue(verifiable(good))
        for change in ({'url': 'http://cdn.modrinth.com/a.jar'}, {'filename': '../a.jar'}, {'size': 0},
                       {'hashes': {'sha1': 'zz', 'sha512': 'b' * 128}}, {'filename': 'a.zip'}):
            self.assertFalse(verifiable(dict(good, **change)), change)

    def test_ids_are_validated_before_building_urls(self):
        mr, http = client({})
        for bad in ('../../etc', 'a b', 'x/y'):
            with self.assertRaises(CatalogError):
                mr.mod(bad)
        self.assertFalse(http.calls)

    def test_every_environment_maps_to_pack_sides(self):
        from modlab.sources.modrinth import ENVIRONMENT_SIDES, environment_sides
        for environment, (client_side, server_side) in ENVIRONMENT_SIDES.items():
            self.assertEqual(environment_sides(environment), {'client': client_side, 'server': server_side})
        self.assertEqual(environment_sides('server_only'), {'client': 'optional', 'server': 'required'})
        self.assertEqual(environment_sides('', 'required', 'unsupported'), {'client': 'required', 'server': 'unsupported'})
        self.assertEqual(environment_sides(None), {'client': 'required', 'server': 'required'})

    def test_dependency_pinned_to_a_specific_version(self):
        dep = {'project_id': 'P7dR8mSH', 'version_id': 'api-old', 'dependency_type': 'required'}
        old_api = version('api-old', pid='P7dR8mSH', date='2025-01-01')
        routes = {('GET', '/v2/project/AANobbMI/version'): [version('v1', deps=[dep])],
                  ('GET', '/v2/projects'): [dict(hit('P7dR8mSH', 'fabric-api'), project_type='mod', id='P7dR8mSH')],
                  ('GET', '/v2/version/api-old'): old_api,
                  ('GET', '/v2/project/P7dR8mSH/version'): [version('api-new', pid='P7dR8mSH', date='2026-05-01')]}
        mr, _ = client(routes)
        report = mr.resolve_report([normalize(hit())], '1.20.1', 'Fabric')
        self.assertEqual(report['dependencies'][0]['file_id'], 'api-old')

    def test_dependencies_by_version_are_mapped_to_projects(self):
        dep = {'project_id': None, 'version_id': 'apiv', 'dependency_type': 'required'}
        routes = {('GET', '/v2/project/AANobbMI/version'): [version('v1', deps=[dep])],
                  ('GET', '/v2/versions'): [{'id': 'apiv', 'project_id': 'P7dR8mSH'}],
                  ('GET', '/v2/projects'): [dict(hit('P7dR8mSH', 'fabric-api'), project_type='mod', id='P7dR8mSH')],
                  ('GET', '/v2/version/apiv'): version('apiv', pid='P7dR8mSH')}
        mr, _ = client(routes)
        report = mr.resolve_report([normalize(hit())], '1.20.1', 'Fabric')
        self.assertEqual([m['project_id'] for m in report['mods']], ['AANobbMI', 'P7dR8mSH'])
        self.assertEqual(report['dependencies'][0]['file_id'], 'apiv')
        self.assertEqual(report['dependencies'][0]['slug'], 'fabric-api')

    def test_declared_incompatibility(self):
        dep = {'project_id': 'OTHER', 'version_id': None, 'dependency_type': 'incompatible'}
        routes = {('GET', '/v2/project/AANobbMI/version'): [version('v1', deps=[dep])],
                  ('GET', '/v2/project/OTHER/version'): [version('v2', pid='OTHER')]}
        mr, _ = client(routes)
        with self.assertRaisesRegex(CatalogError, 'Incompatibilidad'):
            mr.resolve([normalize(hit()), normalize(hit('OTHER', 'other'))], '1.20.1', 'Fabric')

    def test_responses_are_cached_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            mr, http = client({('GET', '/v2/tag/category'): [{'name': 'magic', 'project_type': 'mod', 'header': 'categories'},
                                                             {'name': '16x', 'project_type': 'resourcepack', 'header': 'resolutions'}]},
                              cache=JsonCache(folder))
            self.assertEqual([c['id'] for c in mr.categories()], ['magic'])
            mr.categories()
            self.assertEqual(len(http.calls), 1)
            fresh, http2 = client({}, cache=JsonCache(folder))
            self.assertEqual(fresh.categories()[0]['id'], 'magic')
            self.assertFalse(http2.calls)

    def test_errors_are_explained(self):
        mr, _ = client({('GET', '/v2/search'): FakeResponse(503)})
        with self.assertRaisesRegex(CatalogError, 'Modrinth no está disponible'):
            mr.search()


if __name__ == '__main__':
    unittest.main()
