"""Pruebas con el modelo REAL (lentas: unos minutos en CPU). Se activan con SMAPT_REAL_AI=1.

    SMAPT_REAL_AI=1 python -m unittest tests/test_ai_real.py -v      (desde la carpeta tests: discover -p test_ai_real.py)

Comprueban que el motor carga, que devuelve JSON válido y que la interpretación respeta las negaciones
de descripciones libres. La evaluación completa de 10 descripciones está en scripts/evaluate_ai.py.
"""
import os
import re
import unittest

from modlab.intelligence import DesignRequest, ModpackDesigner, apply_preferences
from modlab.local_ai import LocalAI

ENABLED = os.environ.get('SMAPT_REAL_AI') == '1'


@unittest.skipUnless(ENABLED, 'Define SMAPT_REAL_AI=1 para usar el modelo real')
class RealModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = LocalAI()
        if not cls.ai.available():
            raise unittest.SkipTest('La IA local no está instalada')
        cls.session = cls.ai.session()
        cls.session.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.session.__exit__(None, None, None)

    def interpret(self, phrase):
        request = DesignRequest(phrase, '1.20.1', 'Fabric')
        return apply_preferences(ModpackDesigner(None, self.ai).understand(phrase, request), request)

    @staticmethod
    def queries(brief):
        return ' | '.join(q.casefold() for r in brief['requirements'] for q in r['queries'] + r['examples'])

    def test_horror_without_zombies(self):
        brief = self.interpret('Quiero un mundo de terror con exploración, pero sin zombis.')
        self.assertRegex(self.queries(brief), r'horror|scary|creep|fear|terror')
        self.assertNotRegex(self.queries(brief), r'zombi')
        self.assertTrue(any(re.search('zombi', ' '.join(e['terms'])) for e in brief['exclusions']), brief['exclusions'])

    def test_magic_and_dragons_without_machines(self):
        brief = self.interpret('Quiero magia y dragones, pero nada de máquinas.')
        self.assertRegex(self.queries(brief), r'magic|spell|wizard')
        self.assertRegex(self.queries(brief), r'dragon')
        self.assertNotRegex(self.queries(brief), r'machine|industr|factory|automation')
        self.assertTrue(brief['exclusions'])

    def test_no_negation_means_no_exclusions(self):
        brief = self.interpret('Quiero un Minecraft parecido a Pokémon.')
        self.assertRegex(self.queries(brief), r'pok[eé]mon|cobblemon|creature|captur|catch')
        self.assertEqual(brief['exclusions'], [])


if __name__ == '__main__':
    unittest.main()
