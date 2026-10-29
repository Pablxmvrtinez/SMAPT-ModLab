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

    def test_beta_only_project_fails_without_permission(self):
        mr, _ = client({('GET', '/v2/project/AANobbMI/version'): [version('b', kind='beta')]})
        with self.assertRaises(CatalogError):
            mr.pin(normalize(hit()), '1.20.1', 'Fabric')

    def test_dependencies_by_version_are_mapped_to_projects(self):
        dep = {'project_id': None, 'version_id': 'apiv', 'dependency_type': 'required'}
        routes = {('GET', '/v2/project/AANobbMI/version'): [version('v1', deps=[dep])],
                  ('GET', '/v2/versions'): [{'id': 'apiv', 'project_id': 'P7dR8mSH'}],
                  ('GET', '/v2/projects'): [dict(hit('P7dR8mSH', 'fabric-api'), project_type='mod', id='P7dR8mSH')],
                  ('GET', '/v2/project/P7dR8mSH/version'): [version('api1', pid='P7dR8mSH')]}
        mr, _ = client(routes)
        report = mr.resolve_report([normalize(hit())], '1.20.1', 'Fabric')
        self.assertEqual([m['project_id'] for m in report['mods']], ['AANobbMI', 'P7dR8mSH'])
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
