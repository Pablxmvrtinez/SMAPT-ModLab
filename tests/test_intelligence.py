"""Contrato de comprensión/curación: usa un modelo simulado, no evalúa su calidad."""
import unittest
from unittest.mock import Mock
from contextlib import nullcontext
from intelligence import ExperienceDesigner
from curseforge import normalize,CatalogError
from test_curseforge import raw_mod


def plan():
    return {'summary':'Construir tranquilo y algún jefe elegible.','pace':'Tranquilo','combat':'Opcional',
            'performance':'Prioritario','exclusions':['Magia','Invasiones'],
            'goals':[{'name':'Construcción','purpose':'Crear casas','queries':['building'], 'category_names':['Cosmetic']}],
            'assumptions':['Contenido moderado']}

class DesignerTests(unittest.TestCase):
    def setUp(self):
        self.catalog=Mock();self.ai=Mock();self.ai.session.return_value=nullcontext()
        self.catalog.categories.return_value=[{'id':101,'name':'Cosmetic'}]
        self.catalog.search.return_value={'mods':[normalize(raw_mod(10)),normalize(raw_mod(20))]}
        self.catalog.pin.side_effect=lambda m,mc,loader:dict(m,file_id=m['project_id']*100,minecraft=mc,loader=loader)
        self.designer=ExperienceDesigner(self.catalog,self.ai)
        self.evals={'selected':[{'id':pid,'score':80,'role':'construcción','reason':'Permite construir a tu ritmo sin combates forzados.','caveat':'Consumo sin medir.'} for pid in (10,20)],'skipped':[]}
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
        self.evals['selected'].pop();self.evals['skipped']=[20]
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
