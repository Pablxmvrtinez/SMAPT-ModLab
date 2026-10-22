"""Contratos con CurseForge usando respuestas simuladas, sin claves reales."""
import unittest
from unittest.mock import Mock,patch
import requests
from curseforge import CurseForgeClient,Connection,CatalogError,normalize


def raw_mod(pid=10):
    return {'id':pid,'gameId':432,'classId':6,'name':f'Mod {pid}','slug':f'mod-{pid}',
            'summary':'Descripción del mod','downloadCount':12345,'logo':{'thumbnailUrl':'https://media.forgecdn.net/test.png'},
            'categories':[{'id':101,'name':'Cosmetic','slug':'cosmetic'}],
            'links':{'websiteUrl':f'https://www.curseforge.com/minecraft/mc-mods/mod-{pid}'},'authors':[{'name':'Author'}]}


def file(pid=10,fid=None,deps=(),**extra):
    result={'id':fid or pid*100,'modId':pid,'isAvailable':True,'fileName':f'mod-{pid}.jar',
            'releaseType':1,'gameVersions':['1.20.1','Forge'],'displayName':'1.0',
            'dependencies':list(deps),'fileDate':'2026-01-01'}
    result.update(extra);return result


class ClientTests(unittest.TestCase):
    def setUp(self):self.client=CurseForgeClient(Connection(api_key='private'))
    def test_only_official_source_and_auth_header(self):
        response=Mock(status_code=200);response.json.return_value={'data':[raw_mod()], 'pagination':{'totalCount':1000}}
        with patch('curseforge.requests.get',return_value=response) as get:
            result=self.client.search('building',index=100,minecraft='1.20.1',loader='Forge')
        args=get.call_args
        self.assertEqual(args.args[0],'https://api.curseforge.com/v1/mods/search')
        self.assertEqual(args.kwargs['headers']['x-api-key'],'private')
        self.assertEqual(args.kwargs['params']['gameId'],432)
        self.assertEqual(args.kwargs['params']['classId'],6)
        self.assertEqual(args.kwargs['params']['index'],100)
        self.assertEqual(args.kwargs['params']['modLoaderType'],1)
        self.assertEqual(result['mods'][0]['source'],'curseforge')
        self.assertEqual(result['mods'][0]['logo'],'https://media.forgecdn.net/test.png')
    def test_gateway_never_receives_api_key(self):
        response=Mock(status_code=200);response.json.return_value={'data':[]}
        with patch('curseforge.requests.get',return_value=response) as get:
            CurseForgeClient(Connection('https://catalog.example','private')).categories()
        self.assertNotIn('x-api-key',get.call_args.kwargs['headers'])
    def test_missing_connection_is_explicit(self):
        with patch('curseforge.requests.get') as get:
            with self.assertRaisesRegex(CatalogError,'Falta conectar'):CurseForgeClient(Connection()).search()
        get.assert_not_called()
    def test_auth_error_does_not_leak_key(self):
        with patch('curseforge.requests.get',return_value=Mock(status_code=403)):
            with self.assertRaisesRegex(CatalogError,'rechazó') as exc:self.client.categories()
        self.assertNotIn('private',str(exc.exception))
    def test_no_insecure_remote_gateway(self):
        with self.assertRaises(CatalogError):Connection('http://remote.example').check()
        with self.assertRaises(CatalogError):Connection('https://user:key@example.com').check()
        Connection('http://localhost:8765').check()
    def test_queries_do_not_reuse_api_response_cache(self):
        first=Mock(status_code=200);first.json.return_value={'data':[{'id':1}]}
        second=Mock(status_code=200);second.json.return_value={'data':[{'id':2}]}
        with patch('curseforge.requests.get',side_effect=[first,second]) as get:
            self.assertEqual(self.client.categories(),[{'id':1}])
            self.assertEqual(self.client.categories(),[{'id':2}])
        self.assertEqual(get.call_count,2)
    def test_joint_minecraft_and_loader_validation(self):
        self.client.get=Mock(return_value={'data':[file(gameVersions=['1.20.1','Fabric']),
                                                   file(releaseType=2),file(fid=999)]})
        chosen=self.client.compatible_file(10,'1.20.1','Forge')
        self.assertEqual(chosen['id'],999)
    def test_pin_does_not_trust_wrong_project_file(self):
        self.client.get=Mock(return_value={'data':file(99)})
        with self.assertRaises(CatalogError):self.client.compatible_file(10,'1.20.1','Forge',123)
    def test_required_dependencies_and_cycles(self):
        self.client.mod=Mock(side_effect=lambda pid:normalize(raw_mod(pid)))
        def pin(mod,mc,loader):
            pid=mod['project_id'];deps=[{'modId':20,'relationType':3},{'modId':30,'relationType':2}] if pid==10 else [{'modId':10,'relationType':3}]
            return dict(mod,file_id=pid*100,file=file(pid,deps=deps))
        self.client.pin=Mock(side_effect=pin)
        mods=self.client.resolve([normalize(raw_mod())],'1.20.1','Forge')
        self.assertEqual({m['project_id'] for m in mods},{10,20})
    def test_explicit_incompatibility_blocks_pack(self):
        self.client.pin=Mock(side_effect=lambda m,mc,l:dict(m,file_id=m['project_id']*100,
            file=file(m['project_id'],deps=[{'modId':20,'relationType':5}] if m['project_id']==10 else [])))
        with self.assertRaisesRegex(CatalogError,'Incompatibilidad'):
            self.client.resolve([normalize(raw_mod(10)),normalize(raw_mod(20))],'1.20.1','Forge')
    def test_incompatibility_names_both_mods(self):
        self.client.pin=Mock(side_effect=lambda m,mc,l:dict(m,file_id=m['project_id']*100,
            file=file(m['project_id'],deps=[{'modId':20,'relationType':5}] if m['project_id']==10 else [])))
        with self.assertRaises(CatalogError) as error:
            self.client.resolve([normalize(raw_mod(10)),normalize(raw_mod(20))],'1.20.1','Forge')
        self.assertIn('Mod 10',str(error.exception))
        self.assertIn('Mod 20',str(error.exception))

    def test_no_other_catalog_can_be_pinned(self):
        with self.assertRaisesRegex(CatalogError,'Solo se admiten'):
            self.client.pin({'source':'modrinth','project_id':10},'1.20.1','Forge')
