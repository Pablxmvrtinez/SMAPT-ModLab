"""Instalación del motor de IA: descarga reanudable y verificada del modelo (con un servidor simulado)."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modlab import ai_setup
from modlab.errors import CatalogError
from fakes import FakeResponse

DATA = b'modelo-de-prueba-' * 64


class FakeHub:
    def __init__(self, data=DATA, resumable=True):
        self.data = data
        self.resumable = resumable
        self.ranges = []

    def get(self, url, headers=None, stream=False, timeout=None):
        if url.endswith('LICENSE'):
            return FakeResponse(200, body=b'Apache-2.0')
        start = 0
        header = (headers or {}).get('Range')
        self.ranges.append(header)
        if header and self.resumable:
            start = int(header.split('=')[1].rstrip('-'))
            return FakeResponse(206, body=self.data[start:])
        return FakeResponse(200, body=self.data)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        patches = [patch.object(ai_setup, 'SIZE', len(DATA)), patch.object(ai_setup, 'SHA256', hashlib.sha256(DATA).hexdigest()),
                   patch('modlab.paths.data_dir', return_value=folder / 'data'),
                   patch.object(ai_setup, 'bundled_model', return_value=folder / 'bundle' / ai_setup.MODEL_FILE)]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_download_verifies_and_installs_model(self):
        events = []
        path = ai_setup.download_model(lambda m, f: events.append((m, f)), http=FakeHub())
        self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertEqual(ai_setup.model_path(), Path(path))
        self.assertTrue((Path(path).parent / 'LICENSE').is_file())
        self.assertEqual(events[-1][1], 1.0)

    def test_interrupted_download_resumes(self):
        part = ai_setup.user_model().with_name(ai_setup.MODEL_FILE + '.part')
        part.parent.mkdir(parents=True)
        part.write_bytes(DATA[:100])
        hub = FakeHub()
        ai_setup.download_model(http=hub)
        self.assertEqual(hub.ranges[0], 'bytes=100-')
        self.assertEqual(ai_setup.user_model().read_bytes(), DATA)

    def test_server_without_resume_restarts_cleanly(self):
        part = ai_setup.user_model().with_name(ai_setup.MODEL_FILE + '.part')
        part.parent.mkdir(parents=True)
        part.write_bytes(b'x' * 50)
        ai_setup.download_model(http=FakeHub(resumable=False))
        self.assertEqual(ai_setup.user_model().read_bytes(), DATA)

    def test_corrupted_download_is_deleted(self):
        bad = DATA[:-1] + b'!'
        with self.assertRaisesRegex(CatalogError, 'no coincide'):
            ai_setup.download_model(http=FakeHub(bad))
        self.assertIsNone(ai_setup.model_path())
        self.assertFalse(ai_setup.user_model().with_name(ai_setup.MODEL_FILE + '.part').exists())

    def test_bundled_model_has_priority_and_status_reports_it(self):
        bundled = ai_setup.bundled_model()
        bundled.parent.mkdir(parents=True)
        bundled.write_bytes(DATA)
        self.assertEqual(ai_setup.model_path(), bundled)
        info = ai_setup.status()
        self.assertTrue(info['model_bundled'])
        self.assertEqual(info['ready'], ai_setup.engine_installed())
        self.assertIn('IA' if info['ready'] else 'motor', ai_setup.describe(info))

    def test_partial_or_wrong_size_model_is_not_used(self):
        target = ai_setup.user_model()
        target.parent.mkdir(parents=True)
        target.write_bytes(DATA[:10])
        self.assertIsNone(ai_setup.model_path())

    def test_engine_install_only_from_a_virtual_environment(self):
        with patch('sys.prefix', '/venv'), patch('sys.base_prefix', '/usr'):
            self.assertTrue(ai_setup.can_install_engine())
            self.assertIn(ai_setup.ENGINE_PACKAGE, ai_setup.install_engine_command())
        with patch('sys.prefix', '/usr'), patch('sys.base_prefix', '/usr'):
            self.assertFalse(ai_setup.can_install_engine())


if __name__ == '__main__':
    unittest.main()
