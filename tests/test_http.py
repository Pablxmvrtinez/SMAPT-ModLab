"""Capa HTTP compartida, caché de Modrinth y registro sin secretos."""
import logging
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from modlab import http, logs


class HttpTests(unittest.TestCase):
    def test_session_identifies_the_app(self):
        self.assertIn('SMAPT-ModLab', http.session().headers['User-Agent'])

    def test_cache_expires(self):
        with tempfile.TemporaryDirectory() as td:
            cache = http.JsonCache(td)
            cache.put('a', {'x': 1}, ttl=60)
            self.assertEqual(cache.get('a'), {'x': 1})
            cache.put('b', {'x': 2}, ttl=-1)
            self.assertIsNone(http.JsonCache(td).get('b'))
            self.assertGreater(cache.size(), 0)
            cache.clear()
            self.assertIsNone(http.JsonCache(td).get('a'))

    def test_cache_prunes_old_files(self):
        with tempfile.TemporaryDirectory() as td:
            cache = http.JsonCache(td, max_files=3)
            for i in range(6):
                cache.put(str(i), i, ttl=60)
                time.sleep(0.01)
            cache.prune()
            self.assertLessEqual(len(list(cache.folder.glob('*.json'))), 3)


class LogTests(unittest.TestCase):
    def test_secrets_and_home_are_redacted(self):
        key = '$2a$10$' + 'A' * 53
        with patch.dict(os.environ, {'CURSEFORGE_API_KEY': 'super-secret-key'}):
            text = logs.redact(f'x-api-key: super-secret-key {key} {os.path.expanduser("~")}/mods')
        self.assertNotIn('super-secret-key', text)
        self.assertNotIn(key, text)
        self.assertIn('~/mods', text)

    def test_formatter_redacts_records(self):
        formatter = logs.RedactingFormatter('%(message)s')
        record = logging.LogRecord('modlab', logging.INFO, __file__, 1, 'api_key=abc123', None, None)
        self.assertEqual(formatter.format(record), 'api_key=***')


if __name__ == '__main__':
    unittest.main()
