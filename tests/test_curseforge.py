"""Contratos con CurseForge usando respuestas simuladas, sin claves reales."""
import unittest

from modlab.errors import AuthError, CatalogError, NetworkError, RateLimitError
from modlab.sources.curseforge import Connection, CurseForgeClient, normalize, normalize_file
from fakes import FakeHttp, FakeResponse, curseforge_routes, raw_file, raw_mod


def client(routes=None, connection=None):
    http = FakeHttp(routes)
    return CurseForgeClient(connection or Connection(api_key='private'), http=http), http


class ClientTests(unittest.TestCase):
    def test_only_official_source_and_auth_header(self):
        cf, http = client({('GET', '/v1/mods/search'): {'data': [raw_mod()], 'pagination': {'totalCount': 1000}}})
        result = cf.search('building', index=100, minecraft='1.20.1', loader='Forge')
        call = http.calls[0]
        self.assertEqual(call['url'], 'https://api.curseforge.com/v1/mods/search')
        self.assertEqual(call['headers']['x-api-key'], 'private')
        self.assertEqual(call['params']['gameId'], 432)
        self.assertEqual(call['params']['classId'], 6)
        self.assertEqual(call['params']['index'], 100)
        self.assertEqual(call['params']['modLoaderType'], 1)
        self.assertEqual(call['params']['gameVersion'], '1.20.1')
        self.assertEqual(result['mods'][0]['source'], 'curseforge')
        self.assertEqual(result['mods'][0]['key'], 'curseforge:10')
        self.assertEqual(result['mods'][0]['logo'], 'https://media.forgecdn.net/test.png')
        self.assertEqual(result['pagination']['totalCount'], 1000)

    def test_all_loaders_map_to_official_ids(self):
        cf, http = client({('GET', '/v1/mods/search'): {'data': []}})
        for loader, expected in (('Forge', 1), ('Fabric', 4), ('Quilt', 5), ('NeoForge', 6)):
            cf.search(loader=loader)
            self.assertEqual(http.calls[-1]['params']['modLoaderType'], expected)
        with self.assertRaises(CatalogError):
            cf.search(loader='Rift')

    def test_sort_keys_and_name_order(self):
        cf, http = client({('GET', '/v1/mods/search'): {'data': []}})
        cf.search(sort='updated')
        self.assertEqual(http.calls[-1]['params']['sortField'], 3)
        cf.search(sort='name')
        self.assertEqual(http.calls[-1]['params']['sortOrder'], 'asc')

    def test_key_is_never_sent_to_gateway(self):
        cf, http = client({('GET', '/v1/categories'): {'data': []}}, Connection('https://catalog.example'))
        cf.categories()
        self.assertEqual(http.calls[0]['url'], 'https://catalog.example/v1/categories')
        self.assertNotIn('x-api-key', http.calls[0]['headers'])

    def test_direct_key_goes_only_to_curseforge(self):
        cf, http = client({('GET', '/v1/categories'): {'data': []}}, Connection('https://catalog.example', 'private'))
        cf.categories()
        self.assertTrue(http.calls[0]['url'].startswith('https://api.curseforge.com/'))

    def test_missing_connection_is_explicit(self):
        cf, http = client(connection=Connection())
        with self.assertRaisesRegex(CatalogError, 'Falta conectar'):
            cf.search()
        self.assertFalse(http.calls)
        self.assertFalse(cf.available())

    def test_auth_error_does_not_leak_key(self):
        cf, _ = client({('GET', '/v1/categories'): FakeResponse(403)})
        with self.assertRaises(AuthError) as exc:
            cf.categories()
        self.assertIn('CURSEFORGE_API_KEY', str(exc.exception))
        self.assertNotIn('private', str(exc.exception))

    def test_rate_limit_and_server_errors_are_explained(self):
        cf, _ = client({('GET', '/v1/categories'): FakeResponse(429, headers={'Retry-After': '30'})})
        with self.assertRaisesRegex(RateLimitError, '30 segundos'):
            cf.categories()
        cf, _ = client({('GET', '/v1/categories'): FakeResponse(503)})
        with self.assertRaises(NetworkError):
            cf.categories()

    def test_short_rate_limit_is_retried_once(self):
        answers = [FakeResponse(429, headers={'Retry-After': '0'}), FakeResponse(200, {'data': [{'id': 1}]})]
        cf, http = client({('GET', '/v1/categories'): lambda p, b: answers.pop(0)})
        self.assertEqual(cf.categories()[0]['id'], 1)
        self.assertEqual(len(http.calls), 2)

    def test_unexpected_payload_is_rejected(self):
        cf, _ = client({('GET', '/v1/categories'): {'nope': 1}})
        with self.assertRaisesRegex(CatalogError, 'inesperada'):
            cf.categories()

    def test_no_insecure_remote_gateway(self):
        with self.assertRaises(CatalogError):
            Connection('http://remote.example').check()
        with self.assertRaises(CatalogError):
            Connection('https://user:key@example.com').check()
        Connection('http://localhost:8765').check()

    def test_api_responses_are_not_cached(self):
        # Términos de la API de terceros §3.1: no guardar ni cachear datos de la API.
        answers = [{'data': [{'id': 1}]}, {'data': [{'id': 2}]}]
        cf, http = client({('GET', '/v1/categories'): lambda p, b: answers.pop(0)})
        self.assertEqual(cf.categories()[0]['id'], 1)
        self.assertEqual(cf.categories()[0]['id'], 2)
        self.assertEqual(len(http.calls), 2)

    def test_categories_exclude_classes(self):
        cf, _ = client({('GET', '/v1/categories'): {'data': [{'id': 6, 'name': 'Mods', 'isClass': True},
                                                            {'id': 101, 'name': 'Magic'}]}})
        self.assertEqual([c['id'] for c in cf.categories()], [101])

    def test_description_is_html(self):
        cf, _ = client({('GET', '/v1/mods/10/description'): {'data': '<p>Hola</p>'}})
        self.assertEqual(cf.description(10), {'format': 'html', 'text': '<p>Hola</p>'})

    def test_versions_and_dependency_types(self):
        deps = [{'modId': 20, 'relationType': 3}, {'modId': 30, 'relationType': 2}, {'modId': 40, 'relationType': 5}]
        cf, http = client({('GET', '/v1/mods/10/files'): {'data': [raw_file(10, deps=deps), raw_file(10, fid=7, isServerPack=True)],
                                                          'pagination': {'totalCount': 2}}})
        result = cf.versions(10, '1.20.1', 'Forge')
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(result['files'][0]['dependencies'], [{'project_id': 20, 'type': 'required'},
                                                              {'project_id': 30, 'type': 'optional'},
                                                              {'project_id': 40, 'type': 'incompatible'}])
        self.assertEqual(result['files'][0]['loaders'], ['Forge'])
        self.assertEqual(http.calls[0]['params']['modLoaderType'], 1)


class FileSelectionTests(unittest.TestCase):
    def test_joint_minecraft_and_loader_validation(self):
        files = {1: raw_file(10, fid=1, gameVersions=['1.20.1', 'Fabric']), 2: raw_file(10, fid=2, releaseType=2),
                 999: raw_file(10, fid=999)}
        cf, _ = client(curseforge_routes({10: raw_mod(10)}, files))
        self.assertEqual(cf.compatible_file(10, '1.20.1', 'Forge')['id'], 999)

    def test_beta_only_mod_needs_explicit_permission(self):
        files = {2: raw_file(10, fid=2, releaseType=2)}
        cf, _ = client(curseforge_routes({10: raw_mod(10)}, files))
        with self.assertRaises(CatalogError):
            cf.compatible_file(10, '1.20.1', 'Forge')
        self.assertEqual(cf.compatible_file(10, '1.20.1', 'Forge', allow_unstable=True)['id'], 2)

    def test_explicit_file_must_belong_to_project(self):
        cf, _ = client({('GET', '/v1/mods/10/files/123'): {'data': raw_file(99, fid=123)}})
        with self.assertRaises(CatalogError):
            cf.compatible_file(10, '1.20.1', 'Forge', 123)

    def test_pin_uses_latest_file_index_in_one_batch(self):
        mods = {10: raw_mod(10), 20: raw_mod(20)}
        files = {1000: raw_file(10), 2000: raw_file(20)}
        cf, http = client(curseforge_routes(mods, files))
        pinned, failures = cf.pin_many([normalize(mods[10]), normalize(mods[20])], '1.20.1', 'Forge')
        self.assertEqual([p['file_id'] for p in pinned], [1000, 2000])
        self.assertFalse(failures)
        self.assertEqual([c['path'] for c in http.calls], ['/v1/mods/files'])

    def test_pin_falls_back_to_file_list(self):
        mod = raw_mod(10, latestFilesIndexes=[])
        cf, http = client(curseforge_routes({10: mod}, {555: raw_file(10, fid=555)}))
        pinned, _ = cf.pin_many([normalize(mod)], '1.20.1', 'Forge')
        self.assertEqual(pinned[0]['file_id'], 555)
        self.assertIn('/v1/mods/10/files', [c['path'] for c in http.calls])

    def test_saved_project_mods_are_refreshed_in_batch(self):
        mods = {10: raw_mod(10)}
        cf, http = client(curseforge_routes(mods, {1000: raw_file(10)}))
        pinned, _ = cf.pin_many([{'source': 'curseforge', 'project_id': 10, 'title': 'Mod 10'}], '1.20.1', 'Forge')
        self.assertEqual(pinned[0]['file_id'], 1000)
        self.assertEqual(http.calls[0]['path'], '/v1/mods')

    def test_no_other_catalog_can_be_pinned(self):
        cf, _ = client()
        with self.assertRaisesRegex(CatalogError, 'Solo se admiten'):
            cf.pin({'source': 'modrinth', 'project_id': 'abc', 'title': 'x'}, '1.20.1', 'Forge')


class ResolutionTests(unittest.TestCase):
    def test_required_dependencies_cycles_and_optional(self):
        mods = {10: raw_mod(10), 20: raw_mod(20), 30: raw_mod(30)}
        files = {1000: raw_file(10, deps=[{'modId': 20, 'relationType': 3}, {'modId': 30, 'relationType': 2}]),
                 2000: raw_file(20, deps=[{'modId': 10, 'relationType': 3}]), 3000: raw_file(30)}
        cf, http = client(curseforge_routes(mods, files))
        report = cf.resolve_report([normalize(mods[10])], '1.20.1', 'Forge')
        self.assertEqual([m['project_id'] for m in report['mods']], [10, 20])
        self.assertEqual([m['title'] for m in report['dependencies']], ['Mod 20'])
        self.assertLessEqual(len(http.calls), 4)

    def test_explicit_incompatibility_names_both_mods(self):
        mods = {10: raw_mod(10), 20: raw_mod(20)}
        files = {1000: raw_file(10, deps=[{'modId': 20, 'relationType': 5}]), 2000: raw_file(20)}
        cf, _ = client(curseforge_routes(mods, files))
        with self.assertRaises(CatalogError) as error:
            cf.resolve([normalize(mods[10]), normalize(mods[20])], '1.20.1', 'Forge')
        self.assertIn('Incompatibilidad', str(error.exception))
        self.assertIn('Mod 10', str(error.exception))
        self.assertIn('Mod 20', str(error.exception))

    def test_missing_files_are_reported_together(self):
        mods = {10: raw_mod(10, latestFilesIndexes=[]), 20: raw_mod(20, latestFilesIndexes=[])}
        cf, _ = client(curseforge_routes(mods, {}))
        report = cf.resolve_report([normalize(mods[10]), normalize(mods[20])], '1.20.1', 'Forge')
        self.assertEqual(len(report['missing']), 2)
        with self.assertRaisesRegex(CatalogError, 'sin archivo compatible'):
            cf.resolve([normalize(mods[10]), normalize(mods[20])], '1.20.1', 'Forge')

    def test_duplicates_and_foreign_sources_rejected(self):
        cf, _ = client()
        mod = normalize(raw_mod(10))
        with self.assertRaisesRegex(CatalogError, 'duplicados'):
            cf.resolve_report([mod, mod], '1.20.1', 'Forge')
        with self.assertRaisesRegex(CatalogError, 'no son de CurseForge'):
            cf.resolve_report([{'source': 'modrinth', 'project_id': 'a', 'title': 'A'}], '1.20.1', 'Forge')


class DownloadPermissionTests(unittest.TestCase):
    def test_author_opt_out_is_respected(self):
        cf, http = client()
        mod = dict(normalize(raw_mod(10, allowModDistribution=False)), file_id=1000,
                   file=normalize_file(raw_file(10, downloadUrl=None)))
        self.assertEqual(cf.download_url(mod), '')
        self.assertFalse(http.calls)
        self.assertIn('/files/1000', cf.file_page(mod))

    def test_download_url_endpoint_when_missing(self):
        cf, http = client({('GET', '/v1/mods/10/files/1000/download-url'): {'data': 'https://edge.forgecdn.net/x.jar'}})
        mod = dict(normalize(raw_mod(10)), file_id=1000, file=normalize_file(raw_file(10, downloadUrl=None)))
        self.assertEqual(cf.download_url(mod), 'https://edge.forgecdn.net/x.jar')
        cf, _ = client({('GET', '/v1/mods/10/files/1000/download-url'): FakeResponse(403)})
        self.assertEqual(cf.download_url(mod), '')


if __name__ == '__main__':
    unittest.main()
