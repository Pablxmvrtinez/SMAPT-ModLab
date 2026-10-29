"""Flujo visual y persistencia del pack en Qt, sin red ni inferencia real."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from app import ModLab,THEMES
from modlab.sources.curseforge import normalize
from fakes import raw_mod


class DesignUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.window=ModLab();self.window.catalog=Mock();self.window.images.fetch=Mock()
        self.mods=[normalize(raw_mod(i)) for i in range(1,51)]
        self.window.catalog.search.return_value={'mods':self.mods,'pagination':{'totalCount':5000}}
        self.window.catalog.pin.side_effect=lambda m,mc,l:dict(m,file_id=m['project_id']*100,version_number='1.0',minecraft=mc,loader=l)
    def tearDown(self):
        self.wait();self.window.close();self.qt.processEvents()
    def wait(self):
        deadline=time.monotonic()+3
        while self.window.tasks and time.monotonic()<deadline:
            self.qt.processEvents();time.sleep(.005)
        self.qt.processEvents();self.assertFalse(self.window.tasks)
    def test_two_modes_and_many_categories(self):
        self.assertGreaterEqual(len(THEMES),24)
        self.assertEqual(self.window.stack.count(),6)
        self.window.navigate(1);self.assertEqual(self.window.stack.currentIndex(),1)
    def test_fifty_visual_cards_and_pagination(self):
        self.window.search_browser();self.wait()
        self.assertEqual(len(self.window.browse_grid.cards),50)
        self.assertTrue(self.window.next.isEnabled())
        self.window.page_browser(50);self.wait()
        self.assertEqual(self.window.index,50)
        self.assertEqual(self.window.catalog.search.call_args.args[2],50)
    def test_pack_survives_pages_and_deduplicates(self):
        self.window.search_browser();self.wait()
        self.window.add_mod(self.mods[0]);self.wait()
        self.window.add_mod(self.mods[0]);self.wait()
        self.assertEqual(len(self.window.pack),1)
        self.window.page_browser(50);self.wait()
        self.assertEqual(len(self.window.pack),1)
        self.assertFalse(self.window.browse_grid.cards[0].button.isEnabled())
    def test_version_change_invalidates_files_not_selected_projects(self):
        self.window.add_mod(self.mods[0]);self.wait()
        self.window.version.setCurrentText('1.21.1')
        self.assertIn(1,self.window.pack)
        self.assertNotIn('file_id',self.window.pack[1])
    def test_manual_removal_updates_cards(self):
        self.window.search_browser();self.wait();self.window.add_mod(self.mods[0]);self.wait()
        self.window.pack_list.setCurrentRow(0);self.window.remove_selected()
        self.assertFalse(self.window.pack)
        self.assertTrue(self.window.browse_grid.cards[0].button.isEnabled())
    def test_catalog_failure_preserves_pack(self):
        self.window.add_mod(self.mods[0]);self.wait()
        self.window.catalog.search.side_effect=ValueError('Sin conexión con CurseForge')
        self.window.search_browser();self.wait()
        self.assertEqual(len(self.window.pack),1)
        self.assertIn('CurseForge',self.window.status.text())
    def test_ai_without_model_is_explicit(self):
        self.window.ai=Mock();self.window.ai.available.return_value=False
        self.window.start_ai();self.assertIn('no incluye la IA',self.window.status.text())
    def test_add_proposal_joins_existing_manual_pack(self):
        self.window.add_mod(self.mods[0]);self.wait()
        self.window.ai_mods=[dict(self.mods[1],file_id=200,minecraft='1.20.1',loader='Forge')]
        self.window.add_proposal();self.assertEqual(set(self.window.pack),{1,2})

    def test_reopening_project_preserves_reviewed_file_id(self):
        mod=dict(self.mods[0],file_id=12345,minecraft='1.20.1',loader='Forge')
        value={'schema':1,'source':'curseforge','name':'Pack','minecraft':'1.20.1','loader':'Forge','mods':[mod]}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'project.json';path.write_text(json.dumps(value))
            with patch('app.QFileDialog.getOpenFileName',return_value=(str(path),'')):
                self.window.open_project()
        self.assertEqual(self.window.pack[1]['file_id'],12345)
        self.window.version.setCurrentText('1.21.1')
        self.assertNotIn('file_id',self.window.pack[1])

    def test_check_pack_preserves_selection_and_reports_dependencies(self):
        self.window.add_mod(self.mods[0]);self.wait()
        with patch('app.audit_pack',return_value={
            'selected':1,'total':2,
            'dependencies':[{'project_id':2,'title':'Biblioteca','version':'1.0'}],'missing':[],'conflicts':[],
        }) as audit, patch('app.QMessageBox.information') as info:
            self.window.check_pack();self.wait()
        audit.assert_called_once()
        self.assertEqual(len(self.window.pack),1)
        self.assertIn('Biblioteca',info.call_args.args[2])
        self.assertTrue(self.window.audit_button.isEnabled())
