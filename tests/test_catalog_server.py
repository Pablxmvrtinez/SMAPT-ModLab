import unittest
from unittest.mock import Mock,patch
from catalog_server import Handler,rate


class GatewayTests(unittest.TestCase):
    def handler(self,path):
        handler=object.__new__(Handler);handler.path=path;handler.client_address=('127.0.0.1',1234);handler.reply=Mock()
        return handler
    def setUp(self):rate.clear()
    def test_gateway_does_not_cache_api_responses(self):
        first=Mock(status_code=200);first.json.return_value={'data':[{'id':1}]}
        second=Mock(status_code=200);second.json.return_value={'data':[{'id':2}]}
        h=self.handler('/v1/categories')
        with patch.dict('os.environ',{'CURSEFORGE_API_KEY':'secret'}),patch('catalog_server.requests.get',side_effect=[first,second]) as get:
            h.do_GET();self.assertEqual(h.reply.call_args.args[1],{'data':[{'id':1}]})
            h.do_GET();self.assertEqual(h.reply.call_args.args[1],{'data':[{'id':2}]})
        self.assertEqual(get.call_count,2)
    def test_arbitrary_urls_are_not_proxied(self):
        h=self.handler('/https://other.example/secret')
        with patch('catalog_server.requests.get') as get:h.do_GET()
        get.assert_not_called();self.assertEqual(h.reply.call_args.args[0],404)
    def test_key_stays_server_side_and_game_is_fixed(self):
        h=self.handler('/v1/mods/search?gameId=999&pageSize=50')
        response=Mock(status_code=200);response.json.return_value={'data':[]}
        with patch.dict('os.environ',{'CURSEFORGE_API_KEY':'server-secret'}),patch('catalog_server.requests.get',return_value=response) as get:
            h.do_GET()
        self.assertEqual(get.call_args.kwargs['params']['gameId'],'432')
        self.assertEqual(get.call_args.kwargs['headers']['x-api-key'],'server-secret')
        self.assertNotIn('server-secret',str(h.reply.call_args))
    def test_auth_errors_do_not_forward_private_response_body(self):
        h=self.handler('/v1/categories')
        with patch.dict('os.environ',{'CURSEFORGE_API_KEY':'secret'}),patch('catalog_server.requests.get',return_value=Mock(status_code=403)):
            h.do_GET()
        self.assertEqual(h.reply.call_args.args[0],403)
        self.assertNotIn('secret',str(h.reply.call_args))
