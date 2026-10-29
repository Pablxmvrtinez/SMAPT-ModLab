"""Contrato de comprensión/curación: usa un modelo simulado, no evalúa su calidad."""
import unittest
from unittest.mock import Mock
from contextlib import nullcontext
from modlab.intelligence import ExperienceDesigner
from modlab.errors import CatalogError
from modlab.sources.curseforge import normalize
from fakes import raw_mod


def plan():
    return {'summary':'Construir tranquilo y algún jefe elegible.','pace':'Tranquilo','combat':'Opcional',
            'performance':'Prioritario','exclusions':['Magia','Invasiones'],
            'goals':[{'name':'Construcción','purpose':'Crear casas','queries':['building'], 'category_names':['Cosmetic']}],
            'assumptions':['Contenido moderado']}

class DesignerTests(unittest.TestCase):
    def setUp(self):
        self.catalog=Mock();self.catalog.label='CurseForge';self.ai=Mock();self.ai.session.return_value=nullcontext()
        self.catalog.categories.return_value=[{'id':101,'name':'Cosmetic'}]
        self.catalog.search.return_value={'mods':[normalize(raw_mod(10)),normalize(raw_mod(20))]}
        self.catalog.pin.side_effect=lambda m,mc,loader:dict(m,file_id=m['project_id']*100,minecraft=mc,loader=loader)
        self.designer=ExperienceDesigner(self.catalog,self.ai)
        self.evals={'selected':[{'id':pid,'score':80,'role':'construcción','reason':'Permite construir a tu ritmo sin combates forzados.','caveat':'Consumo sin medir.'} for pid in (1,2)],'skipped':[]}
        self.ai.complete.side_effect=[plan(),self.evals]
    def test_complete_sentence_is_sent_and_reasons_are_preserved(self):
        phrase='Quiero construir tranquilo y algún jefe, pero sin magia ni invasiones.'
        result=self.designer.propose(phrase,'1.20.1','Forge',80)
        self.assertEqual(self.ai.complete.call_args_list[0].args[1]['description'],phrase)
        self.assertEqual(len(result['mods']),2)
        self.assertIn('a tu ritmo',result['mods'][0]['reason'])
        self.assertEqual(result['plan']['exclusions'],['Magia','Invasiones'])
    def test_invented_id_is_rejected(self):
        self.evals['selected'][0]['id']=999
        with self.assertRaisesRegex(CatalogError,'inexistente'):self.designer.propose('Construir','1.20.1','Forge',80)
    def test_incomplete_evaluation_is_rejected(self):
        self.evals['selected'].pop()
        with self.assertRaisesRegex(CatalogError,'sin evaluar'):self.designer.propose('Construir','1.20.1','Forge',80)
    def test_selection_limit_is_a_ceiling(self):
        result=self.designer.propose('Construir','1.20.1','Forge',1)
        self.assertEqual(len(result['mods']),1)
    def test_rejected_cards_are_not_added(self):
        self.evals['selected'].pop();self.evals['skipped']=[2]
        result=self.designer.propose('Construir','1.20.1','Forge',80)
        self.assertEqual([m['project_id'] for m in result['mods']],[10])
    def test_curator_evaluates_full_brief_not_only_a_query(self):
        self.designer.propose('Sin magia','1.20.1','Forge',80)
        data=self.ai.complete.call_args_list[1].args[1]
        self.assertEqual(data['experience']['exclusions'],['Magia','Invasiones'])
        self.assertEqual(len(data['cards']),2)
    def test_empty_catalog_is_not_replaced_by_demo_data(self):
        self.catalog.search.return_value={'mods':[]}
        with self.assertRaisesRegex(CatalogError,'no devolvió'):self.designer.propose('Construir','1.20.1','Forge',80)


class AliasTests(unittest.TestCase):
    def test_modrinth_string_ids_use_local_aliases(self):
        catalog=Mock();ai=Mock();ai.session.return_value=nullcontext();catalog.label='Modrinth'
        catalog.categories.return_value=[{'id':'decoration','name':'decoration'}]
        mods=[{'source':'modrinth','project_id':'AAAA','title':'A','description':'a','categories':[]},
              {'source':'modrinth','project_id':'BBBB','title':'B','description':'b','categories':[]}]
        catalog.search.return_value={'mods':mods}
        catalog.pin.side_effect=lambda m,mc,loader:dict(m,file_id='v')
        ai.complete.side_effect=[plan(),{'selected':[{'id':2,'score':90,'role':'deco','reason':'Encaja.','caveat':'-'}],'skipped':[1]}]
        result=ExperienceDesigner(catalog,ai).propose('Decorar','1.20.1','Fabric',10)
        self.assertEqual([m['project_id'] for m in result['mods']],['BBBB'])
        cards=ai.complete.call_args_list[1].args[1]['cards']
        self.assertEqual([c['id'] for c in cards],[1,2])
