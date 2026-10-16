import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from zipfile import ZipFile
from modpack import build_pack,resolve_loader_version
from test_curseforge import raw_mod
from curseforge import normalize


class PackTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock()
        self.mods=[dict(normalize(raw_mod(10)),file_id=1000),dict(normalize(raw_mod(20)),file_id=2000)]
        self.client.resolve.return_value=self.mods
    def test_native_curseforge_manifest_includes_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'pack.zip'
            result=build_pack(path,'Acheron','1.20.1','Forge','47.4.10',self.mods[:1],client=self.client)
            with ZipFile(path) as z:
                m=json.loads(z.read('manifest.json'))
                self.assertEqual(m['files'],[{'projectID':10,'fileID':1000,'required':True},
                                              {'projectID':20,'fileID':2000,'required':True}])
                self.assertIn('overrides/',z.namelist())
                self.assertFalse(any(n.endswith('.jar') for n in z.namelist()))
                self.assertIsNone(z.testzip())
            self.assertEqual(result['mods'],2)
    def test_failed_resolution_preserves_previous_zip(self):
        self.client.resolve.side_effect=ValueError('No compatible')
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'pack.zip';path.write_bytes(b'previous')
            with self.assertRaises(ValueError):build_pack(path,'Pack','1.20.1','Forge','47.4.10',self.mods,client=self.client)
            self.assertEqual(path.read_bytes(),b'previous')
    def test_required_metadata_is_checked(self):
        with self.assertRaises(ValueError):build_pack('unused.zip','Pack','1.20.1','Forge','',self.mods,client=self.client)
        self.client.resolve.assert_not_called()
    def test_loader_comes_from_official_metadata(self):
        response=Mock();response.json.return_value={'promos':{'1.20.1-recommended':'47.4.10'}}
        with patch('modpack.requests.get',return_value=response):
            self.assertEqual(resolve_loader_version('1.20.1','Forge'),'47.4.10')
        response.json.return_value=[{'loader':{'stable':True,'version':'0.16.10'}}]
        with patch('modpack.requests.get',return_value=response):
            self.assertEqual(resolve_loader_version('1.20.1','Fabric'),'0.16.10')
    def test_unknown_loader_version_not_invented(self):
        response=Mock();response.json.return_value={'promos':{}}
        with patch('modpack.requests.get',return_value=response):
            with self.assertRaises(ValueError):resolve_loader_version('1.99','Forge')
