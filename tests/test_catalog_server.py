import io
import json
import unittest
from unittest.mock import Mock, patch

from catalog_server import Handler, rate


class GatewayTests(unittest.TestCase):
    def handler(self, path, body=None, headers=None):
        handler = object.__new__(Handler)
        handler.path = path
        handler.client_address = ('127.0.0.1', 1234)
        handler.reply = Mock()
        raw = json.dumps(body).encode() if body is not None else b''
        handler.headers = dict({'Content-Length': str(len(raw))}, **(headers or {}))
        handler.rfile = io.BytesIO(raw)
        return handler

    def setUp(self):
        rate.clear()

    def upstream(self, *responses):
        return patch('catalog_server.upstream.request', side_effect=list(responses))

    def ok(self, payload):
        response = Mock(status_code=200)
        response.json.return_value = payload
        return response

    def test_gateway_does_not_cache_api_responses(self):
        h = self.handler('/v1/categories')
        with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'secret'}), \
                self.upstream(self.ok({'data': [{'id': 1}]}), self.ok({'data': [{'id': 2}]})) as get:
            h.do_GET()
            self.assertEqual(h.reply.call_args.args[1], {'data': [{'id': 1}]})
            h.do_GET()
            self.assertEqual(h.reply.call_args.args[1], {'data': [{'id': 2}]})
        self.assertEqual(get.call_count, 2)

    def test_arbitrary_urls_are_not_proxied(self):
        for path in ('/https://other.example/secret', '/v1/games', '/v1/mods/1/files/2/other'):
            h = self.handler(path)
            with self.upstream() as get:
                h.do_GET()
            get.assert_not_called()
            self.assertEqual(h.reply.call_args.args[0], 404)

    def test_new_read_only_routes_are_allowed(self):
        for path in ('/v1/mods/10/files/20/download-url', '/v1/mods/10/files/20/changelog', '/v1/mods/10/files/20'):
            h = self.handler(path)
            with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'k'}), self.upstream(self.ok({'data': 'x'})):
                h.do_GET()
            self.assertEqual(h.reply.call_args.args[0], 200)

    def test_key_stays_server_side_and_game_is_fixed(self):
        h = self.handler('/v1/mods/search?gameId=999&pageSize=50')
        with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'server-secret'}), self.upstream(self.ok({'data': []})) as get:
            h.do_GET()
        self.assertEqual(get.call_args.kwargs['params']['gameId'], '432')
        self.assertEqual(get.call_args.kwargs['headers']['x-api-key'], 'server-secret')
        self.assertNotIn('server-secret', str(h.reply.call_args))

    def test_auth_errors_do_not_forward_private_response_body(self):
        h = self.handler('/v1/categories')
        with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'secret'}), self.upstream(Mock(status_code=403)):
            h.do_GET()
        self.assertEqual(h.reply.call_args.args[0], 403)
        self.assertNotIn('secret', str(h.reply.call_args))

    def test_batch_posts_are_validated(self):
        good = self.handler('/v1/mods', {'modIds': [1, 2], 'filterPcOnly': True})
        with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'k'}), self.upstream(self.ok({'data': []})) as post:
            good.do_POST()
        self.assertEqual(post.call_args.kwargs['json'], {'modIds': [1, 2], 'filterPcOnly': True})
        for path, body in (('/v1/mods', {'modIds': ['1']}), ('/v1/mods', {'modIds': list(range(1, 200))}),
                           ('/v1/mods/files', {'fileIds': [1], 'extra': 1}), ('/v1/fingerprints', {'fingerprints': [1]})):
            h = self.handler(path, body)
            with self.upstream() as post:
                h.do_POST()
            post.assert_not_called()
            self.assertIn(h.reply.call_args.args[0], (400, 404))

    def test_rate_limit_per_client(self):
        with patch('catalog_server.LIMIT_PER_MINUTE', 2), patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'k'}), \
                self.upstream(self.ok({'data': []}), self.ok({'data': []})):
            for _ in range(3):
                h = self.handler('/v1/categories')
                h.do_GET()
        self.assertEqual(h.reply.call_args.args[0], 429)

    def test_health_does_not_reveal_key(self):
        h = self.handler('/health')
        with patch.dict('os.environ', {'CURSEFORGE_API_KEY': 'secret'}):
            h.do_GET()
        self.assertEqual(h.reply.call_args.args[1], {'ok': True, 'curseforge': True})


if __name__ == '__main__':
    unittest.main()
