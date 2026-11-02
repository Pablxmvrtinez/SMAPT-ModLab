import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from modlab.errors import CatalogError
from modlab.modpack import audit_pack, build_mrpack, build_pack, resolve_loader_version
from modlab.sources.curseforge import normalize
from fakes import raw_mod


def modrinth_mod(pid, filename='a.jar', url=None, **file):
    return {'source': 'modrinth', 'project_id': pid, 'title': pid, 'client_side': 'required', 'server_side': 'optional',
            'file_id': 'v' + pid, 'file': dict({'filename': filename, 'sha1': '1' * 40, 'sha512': '2' * 128, 'size': 9,
                                                'download_url': url or f'https://cdn.modrinth.com/data/{pid}/{filename}'}, **file)}


class CurseForgePackTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.mods = [dict(normalize(raw_mod(10)), file_id=1000), dict(normalize(raw_mod(20)), file_id=2000)]
        self.client.resolve.return_value = self.mods

    def test_native_manifest_includes_dependencies_author_and_version(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'pack.zip'
            result = build_pack(path, 'Acheron', '1.20.1', 'Forge', '47.4.10', self.mods[:1], client=self.client,
                                author='Pablo', version='2.1.0')
            with ZipFile(path) as z:
                m = json.loads(z.read('manifest.json'))
                self.assertEqual(m['files'], [{'projectID': 10, 'fileID': 1000, 'required': True},
                                              {'projectID': 20, 'fileID': 2000, 'required': True}])
                self.assertEqual((m['author'], m['version']), ('Pablo', '2.1.0'))
                self.assertEqual(m['minecraft']['modLoaders'][0]['id'], 'forge-47.4.10')
                self.assertIn('overrides/', z.namelist())
                self.assertFalse(any(n.endswith('.jar') for n in z.namelist()))
                self.assertIsNone(z.testzip())
            self.assertEqual(result['mods'], 2)

    def test_failed_resolution_preserves_previous_zip(self):
        self.client.resolve.side_effect = ValueError('No compatible')
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'pack.zip'
            path.write_bytes(b'previous')
            with self.assertRaises(ValueError):
                build_pack(path, 'Pack', '1.20.1', 'Forge', '47.4.10', self.mods, client=self.client)
            self.assertEqual(path.read_bytes(), b'previous')
            self.assertEqual(list(Path(td).iterdir()), [path])

    def test_required_metadata_is_checked(self):
        with self.assertRaises(ValueError):
            build_pack('unused.zip', 'Pack', '1.20.1', 'Forge', '', self.mods, client=self.client)
        with self.assertRaisesRegex(ValueError, 'CurseForge solo'):
            build_pack('unused.zip', 'Pack', '1.20.1', 'Quilt', '0.26.0', self.mods, client=self.client)
        self.client.resolve.assert_not_called()


class ModrinthPackTests(unittest.TestCase):
    def test_mrpack_index_follows_format(self):
        client = Mock()
        client.resolve.return_value = [modrinth_mod('AAA', 'a.jar'), modrinth_mod('BBB', 'b.jar')]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'pack.mrpack'
            build_mrpack(path, 'Acheron', '1.20.1', 'Fabric', '0.16.10', [modrinth_mod('AAA')], client=client,
                         version='1.2.0', summary='Chill')
            with ZipFile(path) as z:
                index = json.loads(z.read('modrinth.index.json'))
                self.assertEqual(z.namelist(), ['modrinth.index.json'])
        self.assertEqual(index['formatVersion'], 1)
        self.assertEqual(index['game'], 'minecraft')
        self.assertEqual(index['versionId'], '1.2.0')
        self.assertEqual(index['dependencies'], {'minecraft': '1.20.1', 'fabric-loader': '0.16.10'})
        first = index['files'][0]
        self.assertEqual(first['path'], 'mods/a.jar')
        self.assertEqual(set(first['hashes']), {'sha1', 'sha512'})
        self.assertEqual(first['env'], {'client': 'required', 'server': 'optional'})
        self.assertTrue(first['downloads'][0].startswith('https://cdn.modrinth.com/'))

    def test_mrpack_rejects_unsafe_entries(self):
        client = Mock()
        for bad in ([modrinth_mod('A', url='https://evil.example/a.jar')], [modrinth_mod('A', sha512='')],
                    [modrinth_mod('A', 'x.jar'), modrinth_mod('B', 'x.jar')]):
            client.resolve.return_value = bad
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(CatalogError):
                    build_mrpack(Path(td) / 'p.mrpack', 'P', '1.20.1', 'Fabric', '0.16.10', bad[:1], client=client)
                self.assertEqual(list(Path(td).iterdir()), [])

    def test_loader_keys(self):
        client = Mock()
        client.resolve.return_value = [modrinth_mod('A')]
        for loader, key in (('Forge', 'forge'), ('NeoForge', 'neoforge'), ('Quilt', 'quilt-loader')):
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / 'p.mrpack'
                build_mrpack(path, 'P', '1.20.1', loader, '1.0.0', [modrinth_mod('A')], client=client)
                with ZipFile(path) as z:
                    self.assertIn(key, json.loads(z.read('modrinth.index.json'))['dependencies'])


class LoaderVersionTests(unittest.TestCase):
    def test_loader_comes_from_official_metadata(self):
        response = Mock()
        response.json.return_value = {'promos': {'1.20.1-recommended': '47.4.10'}}
        with patch('modlab.modpack.requests.get', return_value=response):
            self.assertEqual(resolve_loader_version('1.20.1', 'Forge'), '47.4.10')
        response.json.return_value = [{'loader': {'stable': False, 'version': '0.17.0-beta'}}, {'loader': {'stable': True, 'version': '0.16.10'}}]
        with patch('modlab.modpack.requests.get', return_value=response):
            self.assertEqual(resolve_loader_version('1.20.1', 'Fabric'), '0.16.10')
        response.json.return_value = [{'loader': {'version': '0.27.0-beta.1'}}, {'loader': {'version': '0.26.4'}}]
        with patch('modlab.modpack.requests.get', return_value=response):
            self.assertEqual(resolve_loader_version('1.20.1', 'Quilt'), '0.26.4')

    def test_neoforge_picks_highest_matching_build(self):
        xml = ('<metadata><versioning><versions><version>21.1.9</version><version>21.1.77</version>'
               '<version>21.1.80-beta</version><version>21.4.1</version></versions></versioning></metadata>')
        with patch('modlab.modpack.requests.get', return_value=Mock(text=xml)):
            self.assertEqual(resolve_loader_version('1.21.1', 'NeoForge'), '21.1.77')
        with self.assertRaises(ValueError):
            resolve_loader_version('1.20.1', 'NeoForge')

    def test_unknown_loader_version_not_invented(self):
        response = Mock()
        response.json.return_value = {'promos': {}}
        with patch('modlab.modpack.requests.get', return_value=response):
            with self.assertRaises(ValueError):
                resolve_loader_version('1.99', 'Forge')


class AuditTests(unittest.TestCase):
    def test_report_groups_sources(self):
        cf, mr = Mock(), Mock()
        cf.resolve_report.return_value = {'mods': [1, 2], 'dependencies': [{'project_id': 20, 'title': 'B lib'}],
                                          'missing': [], 'conflicts': [('A', 'C')]}
        mr.resolve_report.return_value = {'mods': [3], 'dependencies': [{'project_id': 'x', 'title': 'A lib'}],
                                          'missing': [{'project_id': 'y', 'title': 'Y', 'reason': 'sin archivo'}], 'conflicts': []}
        catalogs = Mock()
        catalogs.get.side_effect = lambda s: cf if s == 'curseforge' else mr
        mods = [{'source': 'curseforge', 'project_id': 10, 'title': 'A'}, {'source': 'modrinth', 'project_id': 'z', 'title': 'Z'}]
        report = audit_pack(mods, '1.20.1', 'Fabric', catalogs=catalogs)
        self.assertEqual(report['selected'], 2)
        self.assertEqual(report['total'], 3)
        self.assertEqual([d['title'] for d in report['dependencies']], ['A lib', 'B lib'])
        self.assertEqual(report['missing'][0]['source'], 'modrinth')
        self.assertEqual(report['conflicts'], [('A', 'C')])

    def test_empty_pack_is_not_checked(self):
        with self.assertRaisesRegex(ValueError, 'Añade mods'):
            audit_pack([], '1.20.1', 'Fabric', client=None)


if __name__ == '__main__':
    unittest.main()
