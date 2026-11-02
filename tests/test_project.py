"""Modelo del pack y formato de proyecto."""
import json
import tempfile
import unittest
from pathlib import Path

from modlab.project import Pack
from modlab.sources.curseforge import normalize
from fakes import raw_mod


class PackTests(unittest.TestCase):
    def test_add_remove_and_keys_per_source(self):
        pack = Pack()
        pack.add(normalize(raw_mod(1)))
        pack.add({'source': 'modrinth', 'project_id': 'AANobbMI', 'title': 'Sodium'})
        self.assertEqual(pack.keys(), {'curseforge:1', 'modrinth:AANobbMI'})
        self.assertEqual(pack.sources(), {'curseforge', 'modrinth'})
        pack.remove('curseforge:1')
        self.assertEqual(len(pack), 1)

    def test_target_change_keeps_projects_but_drops_files(self):
        pack = Pack()
        pack.add(dict(normalize(raw_mod(1)), file_id=5, file={}, version_number='1'))
        self.assertTrue(pack.set_target('1.21.1', 'NeoForge'))
        self.assertIn('curseforge:1', pack)
        self.assertNotIn('file_id', pack.mods['curseforge:1'])
        self.assertFalse(pack.set_target('1.21.1', 'NeoForge'))

    def test_saved_project_contains_only_the_selection(self):
        pack = Pack('Acheron', '1.20.1', 'Forge')
        pack.add(dict(normalize(raw_mod(1)), file_id=100, reason='Encaja'))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'p.json'
            pack.save(path)
            stored = json.loads(path.read_text())
            self.assertEqual(stored['schema'], 2)
            mod = stored['mods'][0]
            self.assertEqual(mod['file_id'], 100)
            for field in ('description', 'logo', 'screenshots', 'downloads', 'latest_files'):
                self.assertNotIn(field, mod)
            again = Pack.load(path)
        self.assertEqual(again.name, 'Acheron')
        self.assertEqual(again.mods['curseforge:1']['file_id'], 100)

    def test_legacy_schema_one_is_accepted(self):
        value = {'schema': 1, 'source': 'curseforge', 'name': 'Viejo', 'minecraft': '1.20.1', 'loader': 'Forge',
                 'mods': [dict(normalize(raw_mod(3)), file_id=12345)]}
        pack = Pack.from_json(value)
        self.assertEqual(pack.mods['curseforge:3']['file_id'], 12345)

    def test_invalid_projects_are_rejected(self):
        base = {'schema': 2, 'name': 'X', 'minecraft': '1.20.1', 'loader': 'Forge', 'mods': []}
        for broken in (dict(base, schema=9), dict(base, loader='Rift'), dict(base, minecraft='../../x'),
                       dict(base, mods=[{'source': 'curseforge', 'project_id': '1', 'title': 'x'}]),
                       dict(base, mods=[{'source': 'other', 'project_id': 1, 'title': 'x'}]),
                       dict(base, mods=[{'source': 'modrinth', 'project_id': '../x', 'title': 'x'}])):
            with self.assertRaises(ValueError):
                Pack.from_json(broken)


if __name__ == '__main__':
    unittest.main()
