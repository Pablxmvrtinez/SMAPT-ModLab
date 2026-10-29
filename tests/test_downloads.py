"""Descargas: permisos del autor, dominios autorizados y verificación de hash."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from modlab import downloads
from modlab.errors import CatalogError
from fakes import FakeHttp, FakeResponse

BODY = b'contenido del jar'
URL = 'https://cdn.modrinth.com/data/x/mod.jar'


def item(sha1=None, url=URL, filename='mod.jar'):
    return {'mod': {'title': 'Mod'}, 'url': url, 'filename': filename, 'size': len(BODY),
            'sha1': sha1 if sha1 is not None else hashlib.sha1(BODY).hexdigest(), 'sha512': ''}


class DownloadTests(unittest.TestCase):
    def test_only_official_cdns(self):
        self.assertTrue(downloads.allowed_url('https://edge.forgecdn.net/files/1/2/a.jar'))
        self.assertTrue(downloads.allowed_url(URL))
        self.assertFalse(downloads.allowed_url('http://cdn.modrinth.com/a.jar'))
        self.assertFalse(downloads.allowed_url('https://evil.example/a.jar'))

    def test_plan_separates_manual_downloads(self):
        catalog = Mock()
        catalog.download_url.side_effect = lambda m: '' if m['allow_distribution'] is False else URL
        catalog.file_page.return_value = 'https://www.curseforge.com/minecraft/mc-mods/x/files/1'
        catalogs = Mock()
        catalogs.get.return_value = catalog
        mods = [{'source': 'curseforge', 'title': 'Libre', 'allow_distribution': True, 'file': {'filename': 'a.jar', 'size': 1}},
                {'source': 'curseforge', 'title': 'Cerrado', 'allow_distribution': False, 'file': {'filename': 'b.jar'}}]
        items, manual = downloads.plan(mods, catalogs)
        self.assertEqual([i['filename'] for i in items], ['a.jar'])
        self.assertEqual(manual[0]['title'], 'Cerrado')
        self.assertIn('autor', manual[0]['reason'])

    def test_download_verifies_hash_and_skips_existing(self):
        http = FakeHttp({('GET', URL): FakeResponse(200, url=URL, body=BODY)})
        with tempfile.TemporaryDirectory() as td:
            report = downloads.download_all([item()], td, http=http)
            self.assertEqual(report['downloaded'], ['mod.jar'])
            self.assertEqual((Path(td) / 'mod.jar').read_bytes(), BODY)
            again = downloads.download_all([item()], td, http=http)
            self.assertEqual(again['existing'], ['mod.jar'])

    def test_hash_mismatch_leaves_no_file(self):
        http = FakeHttp({('GET', URL): FakeResponse(200, url=URL, body=BODY)})
        with tempfile.TemporaryDirectory() as td:
            report = downloads.download_all([item(sha1='0' * 40)], td, http=http)
            self.assertEqual(report['failed'][0]['title'], 'Mod')
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_redirect_to_unknown_host_is_refused(self):
        http = FakeHttp({('GET', URL): FakeResponse(200, url='https://evil.example/mod.jar', body=BODY)})
        with tempfile.TemporaryDirectory() as td:
            report = downloads.download_all([item()], td, http=http)
            self.assertIn('dominio', report['failed'][0]['reason'])

    def test_unsafe_file_names_are_rejected(self):
        from modlab.modpack import safe_jar_name
        self.assertEqual(safe_jar_name('sodium-fabric-0.5.13+mc1.20.1.jar'), 'sodium-fabric-0.5.13+mc1.20.1.jar')
        for bad in ('', '..', '.hidden.jar', 'virus.exe', '../../etc/x.jar', 'a\\b.jar', 'NUL.jar', 'x?.jar'):
            with self.assertRaises(CatalogError):
                safe_jar_name(bad)


if __name__ == '__main__':
    unittest.main()
