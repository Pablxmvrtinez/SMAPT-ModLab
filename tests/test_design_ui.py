"""Flujos de la interfaz en Qt sin red: catálogos simulados y ajustes temporales."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from modlab.errors import CatalogError
from modlab.settings import Settings
from modlab.sources import Catalogs
from modlab.sources.base import CatalogSource
from modlab.sources.curseforge import Connection, normalize
from modlab.ui.labels import THEMES
from modlab.ui.widgets import EmptyState
from modlab.ui.window import NAV, ModLab
from fakes import raw_mod


class FakeCatalog(CatalogSource):
    def __init__(self, source='curseforge', available=True):
        self.source = source
        self.label = 'CurseForge' if source == 'curseforge' else 'Modrinth'
        self.connection = Connection(api_key='k' if available else '')
        self._available = available
        self.mods_list = [normalize(raw_mod(i)) for i in range(1, 121)]
        if source == 'modrinth':
            self.mods_list = [dict(m, source='modrinth', project_id=f'M{m["project_id"]}', key=f'modrinth:M{m["project_id"]}')
                              for m in self.mods_list]
        self.search = Mock(side_effect=self._search)
        self.failing = None

    def available(self):
        return self._available

    def categories(self):
        return [{'id': 101, 'name': 'Cosmetic'}, {'id': 102, 'name': 'Magic'}]

    def _search(self, query='', category=None, index=0, page_size=50, sort='downloads', minecraft='', loader=''):
        if self.failing:
            raise CatalogError(self.failing)
        return {'mods': self.mods_list[index:index + page_size], 'pagination': {'totalCount': len(self.mods_list)}}

    def pin_many(self, mods, minecraft, loader, allow_unstable=False):
        pinned = [dict(m, file_id=m.get('file_id') or 999, version_number='1.0', release='release', minecraft=minecraft,
                       loader=loader, file={'dependencies': []}) for m in mods]
        return pinned, []

    def mods(self, ids):
        return [m for m in self.mods_list if m['project_id'] in ids]

    def description(self, pid):
        return {'format': 'html', 'text': '<p>Hola</p><script>alert(1)</script>'}

    def versions(self, pid, minecraft='', loader='', index=0, page_size=50):
        return {'files': [{'id': 5, 'name': 'v5', 'release': 'beta', 'date': '2026-01-01', 'game_versions': ['1.20.1'],
                           'loaders': ['Forge'], 'dependencies': []}], 'total': 1}

    def download_url(self, mod):
        return ''

    def file_page(self, mod):
        return 'https://example.test'


class DesignUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings = Settings(folder=Path(self.folder.name))
        self.cf = FakeCatalog('curseforge')
        self.mr = FakeCatalog('modrinth')
        self.window = ModLab(settings=self.settings, catalogs=Catalogs(self.cf, self.mr), load_system=False)
        self.window.images.fetch = Mock()
        self.window.ai = Mock()
        self.window.ai.available.return_value = False
        self.window.show()

    def tearDown(self):
        self.wait()
        self.window.close()
        self.qt.processEvents()
        self.folder.cleanup()

    def wait(self, timeout=3):
        deadline = time.monotonic() + timeout
        while self.window.runner.jobs and time.monotonic() < deadline:
            self.qt.processEvents()
            time.sleep(0.005)
        self.qt.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(self.window.runner.jobs)

    def browse(self):
        self.window.navigate('browse')
        self.wait()
        return self.window.pages['browse']

    def test_navigation_covers_every_section(self):
        self.assertGreaterEqual(len(THEMES), 20)
        self.assertEqual(len(NAV), 7)
        for name, *_ in NAV:
            self.window.navigate(name)
            self.assertIs(self.window.stack.currentWidget(), self.window.pages[name])
            self.assertTrue(self.window.nav[name].isChecked())

    def test_fifty_cards_and_pagination(self):
        page = self.browse()
        self.assertEqual(len(page.grid.cards), 50)
        self.assertTrue(page.next.isEnabled())
        self.assertFalse(page.prev.isEnabled())
        page.next.click()
        self.wait()
        self.assertEqual(page.index, 50)
        self.assertEqual(self.cf.search.call_args.args[2], 50)
        self.assertTrue(page.prev.isEnabled())

    def test_search_filters_use_global_target(self):
        page = self.browse()
        self.window.loader.setCurrentText('NeoForge')
        self.wait()
        args = self.cf.search.call_args.args
        self.assertEqual(args[5:], ('1.20.1', 'NeoForge'))
        page.sort.setCurrentIndex(page.sort.findData('updated'))
        self.wait()
        self.assertEqual(self.cf.search.call_args.args[4], 'updated')

    def test_add_toggle_and_card_states(self):
        page = self.browse()
        mod = page.grid.cards[0].mod
        self.window.toggle_mod(mod)
        self.wait()
        self.assertIn(mod['key'], self.window.pack)
        self.assertEqual(self.window.pack.mods[mod['key']]['file_id'], 999)
        self.assertEqual(page.grid.cards[0].state, 'in')
        self.assertEqual(self.window.pack_button.text(), 'Mi pack · 1')
        self.window.toggle_mod(mod)
        self.assertNotIn(mod['key'], self.window.pack)
        self.assertEqual(page.grid.cards[0].state, 'add')

    def test_pack_survives_pages_sources_and_deduplicates(self):
        page = self.browse()
        self.window.toggle_mod(page.grid.cards[0].mod)
        self.wait()
        self.window.add_with_file(page.grid.cards[0].mod, None)
        self.wait()
        page.next.click()
        self.wait()
        page.set_source('modrinth')
        self.wait()
        self.window.toggle_mod(page.grid.cards[0].mod)
        self.wait()
        self.assertEqual(len(self.window.pack), 2)
        self.assertEqual(self.window.pack.sources(), {'curseforge', 'modrinth'})

    def test_version_change_keeps_projects_and_drops_files(self):
        page = self.browse()
        mod = page.grid.cards[0].mod
        self.window.toggle_mod(mod)
        self.wait()
        self.window.version.setCurrentText('1.21.1')
        self.window.change_target()
        self.wait()
        self.assertIn(mod['key'], self.window.pack)
        self.assertNotIn('file_id', self.window.pack.mods[mod['key']])
        self.assertEqual(self.window.target(), ('1.21.1', 'Forge'))

    def test_invalid_version_is_rejected(self):
        self.window.version.setCurrentText('../../etc')
        self.window.change_target()
        self.assertEqual(self.window.target()[0], '1.20.1')

    def test_curseforge_without_connection_offers_modrinth(self):
        self.wait()
        self.cf._available = False
        self.cf.connection = Connection()
        self.cf.search.reset_mock()
        self.assertEqual(self.window.default_source(), 'modrinth')
        page = self.browse()
        page.set_source('curseforge')
        self.wait()
        self.assertIsInstance(page.grid.items[0], EmptyState)
        self.cf.search.assert_not_called()

    def test_catalog_failure_preserves_pack(self):
        page = self.browse()
        self.window.toggle_mod(page.grid.cards[0].mod)
        self.wait()
        self.cf.failing = 'Sin conexión con CurseForge'
        page.run_search(0)
        self.wait()
        self.assertEqual(len(self.window.pack), 1)
        self.assertIsInstance(page.grid.items[0], EmptyState)

    def test_failed_pin_is_reported_and_not_added(self):
        self.cf.pin_many = Mock(return_value=([], [{'project_id': 1, 'title': 'Mod 1', 'reason': 'Sin archivo estable'}]))
        with patch.object(self.window, 'toast') as toast:
            self.window.toggle_mod(self.cf.mods_list[0])
            self.wait()
        self.assertFalse(len(self.window.pack))
        self.assertIn('Sin archivo estable', toast.call_args.args[1])

    def ai_result(self, mode='recommend'):
        brief = {'analysis': 'Quiere construir tranquilo.', 'summary': 'Construcción tranquila', 'setting': '',
                 'difficulty': 'baja', 'combat': 'Sin combates extra', 'performance': 'prioridad',
                 'requirements': [{'name': 'Construcción', 'detail': 'Casas', 'priority': 'obligatorio', 'queries': ['building'],
                                   'examples': [], 'categories': []}],
                 'exclusions': [{'concept': 'Combate', 'terms': ['boss'], 'categories': []}], 'assumptions': []}
        mods = [dict(self.cf.mods_list[i], file_id=900 + i, version_number='1.0', reason='Encaja con construir.',
                     role=f'rol {i}', requirement='Construcción') for i in (1, 2)]
        return {'mode': mode, 'brief': brief, 'mods': mods, 'dependencies': [dict(self.cf.mods_list[5], version_number='2.0')],
                'rejected': [{'title': 'Boss Mod', 'reason': 'Incluye «Combate», que pediste evitar.'}],
                'stats': {'found': 30, 'evaluated': 20, 'unevaluated': 0, 'seconds': 12.0, 'tokens_per_second': 9},
                'coverage': [{'requirement': 'Construcción', 'priority': 'obligatorio', 'mods': [m['title'] for m in mods]}],
                'warnings': ['Aviso']}

    def run_ai(self, mode):
        page = self.window.pages['ai']
        page.mode.set_current(mode, emit=True)
        page.prompt.setPlainText('Quiero construir casas tranquilamente sin combates.')
        result = self.ai_result(mode)

        def fake_run(designer, request, progress, check):
            from modlab.intelligence import BRIEF_EVENT
            progress('Interpretando descripción…', 0.05)
            progress(BRIEF_EVENT + json.dumps(result['brief']), 0.2)
            progress('Evaluando compatibilidad · lote 1 de 1', 0.5)
            self.seen_request = request
            return result
        with patch.object(page.setup, 'ready', return_value=True), \
                patch('modlab.ui.pages.ai.ModpackDesigner.run', fake_run):
            page._update_status()
            page.start()
            self.wait()
        return page

    def test_ai_without_engine_shows_setup_instead_of_guessing(self):
        self.wait()
        page = self.window.pages['ai']
        page.prompt.setPlainText('Quiero un apocalipsis zombi con armas.')
        with patch.object(page.setup, 'ready', return_value=False), patch.object(self.window, 'toast') as toast:
            page.start()
        self.assertIs(page.stack.currentWidget(), page.setup)
        self.assertIn('IA', toast.call_args.args[0])
        self.assertNotIn('ai', self.window.runner.keys)

    def test_ai_recommendations_show_brief_cards_and_discard(self):
        page = self.run_ai('recommend')
        self.assertEqual(self.seen_request.mode, 'recommend')
        self.assertEqual((self.seen_request.minecraft, self.seen_request.loader), self.window.target())
        self.assertFalse(page.brief_card.isHidden())
        texts = ' '.join(w.text() for w in page.brief_card.findChildren(type(page.summary)))
        self.assertIn('Sin combate', texts)
        self.assertEqual(len(page.grid.cards), 2)
        page.discard(page.grid.cards[0].mod)
        self.assertEqual(len(page.grid.cards), 1)
        self.assertIn('Descartados (2)', page.rejected_button.text())
        page.add_all_mods()
        self.assertEqual(len(self.window.pack), 1)

    def test_ai_modpack_preview_can_be_edited_and_used(self):
        self.window.toggle_mod(self.cf.mods_list[0])
        self.wait()
        page = self.run_ai('create')
        self.assertIs(page.results_stack.currentWidget(), page.preview)
        first = page.tree.topLevelItem(0).child(0)
        first.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(len(page.preview_selection()), 1)
        with patch('modlab.ui.pages.ai.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            page.use_preview(export=False)
        self.assertEqual(self.window.pack.keys(), {'curseforge:3'})
        self.assertIn('construir', self.window.pack.description)
        self.assertIs(self.window.stack.currentWidget(), self.window.pages['pack'])

    def test_stepper_follows_real_stages(self):
        from modlab.ui.pages.ai import step_of
        self.assertEqual([step_of(m) for m in ('Interpretando descripción · x', 'Buscando mods · 3/9',
                                               'Evaluando compatibilidad · lote 1', 'Preparando modpack · x', 'otro')],
                         [0, 1, 2, 3, None])

    def test_reopening_project_preserves_reviewed_file_id(self):
        mod = dict(self.cf.mods_list[0], file_id=12345)
        value = {'schema': 1, 'source': 'curseforge', 'name': 'Pack', 'minecraft': '1.20.1', 'loader': 'Forge', 'mods': [mod]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'project.json'
            path.write_text(json.dumps(value))
            with patch('modlab.ui.pages.pack.QFileDialog.getOpenFileName', return_value=(str(path), '')):
                self.window.pages['pack'].open_project()
        self.assertEqual(self.window.pack.mods['curseforge:1']['file_id'], 12345)
        self.window.version.setCurrentText('1.21.1')
        self.window.change_target()
        self.assertNotIn('file_id', self.window.pack.mods['curseforge:1'])

    def test_check_pack_reports_dependencies_and_conflicts(self):
        self.window.toggle_mod(self.cf.mods_list[0])
        self.wait()
        report = {'selected': 1, 'total': 2, 'dependencies': [{'project_id': 2, 'title': 'Biblioteca', 'source': 'curseforge',
                                                                'version': '1.0'}],
                  'missing': [], 'conflicts': [('A', 'B')]}
        with patch('modlab.ui.pages.pack.audit_pack', return_value=report) as audit:
            self.window.pages['pack'].check()
            self.wait()
        audit.assert_called_once()
        page = self.window.pages['pack']
        self.assertFalse(page.report_card.isHidden())
        text = ' '.join(w.text() for w in page.report_card.findChildren(type(page.summary)))
        self.assertIn('Biblioteca', text)
        self.assertIn('Incompatibilidad', text)
        self.assertEqual(len(self.window.pack), 1)
        self.assertTrue(page.check_button.isEnabled())

    def test_details_page_sanitizes_description_and_lists_versions(self):
        self.window.open_details(self.cf.mods_list[0])
        self.wait()
        details = self.window.pages['details']
        self.assertIn('Hola', details.description.toPlainText())
        self.assertNotIn('alert', details.description.toHtml())
        details.tabs.setCurrentIndex(1)
        self.wait()
        self.assertEqual(details.versions_table.rowCount(), 1)
        self.window.back()
        self.assertIsNot(self.window.stack.currentWidget(), details)

    def test_verify_saved_mrpack_reports_without_touching_pack(self):
        from test_mrpack_validator import archive, manifest
        self.window.toggle_mod(self.cf.mods_list[0])
        self.wait()
        with tempfile.TemporaryDirectory() as td:
            good, bad = Path(td) / 'ok.mrpack', Path(td) / 'bad.mrpack'
            archive(good, manifest())
            bad.write_bytes(b'not a zip')
            page = self.window.pages['pack']
            with patch('modlab.ui.pages.pack.QFileDialog.getOpenFileName', return_value=(str(good), '')), \
                    patch('modlab.ui.pages.pack.QMessageBox.information') as info:
                page.verify_mrpack()
                self.wait()
            self.assertIn('1 mods', info.call_args.args[2])
            with patch('modlab.ui.pages.pack.QFileDialog.getOpenFileName', return_value=(str(bad), '')), \
                    patch('modlab.ui.pages.pack.QMessageBox.warning') as warning:
                page.verify_mrpack()
                self.wait()
            self.assertIn('manifiesto', warning.call_args.args[2])
            with patch('modlab.ui.pages.pack.QFileDialog.getOpenFileName', return_value=('', '')):
                page.verify_mrpack()
            self.assertNotIn('verify', self.window.runner.keys)
        self.assertEqual(len(self.window.pack), 1)

    def test_changing_target_clears_manual_loader_build(self):
        self.window.toggle_mod(self.cf.mods_list[0])
        self.wait()
        page = self.window.pages['pack']
        page.loader_build.setText('47.4.10')
        self.assertEqual(self.window.pack.loader_version, '47.4.10')
        self.window.loader.setCurrentText('NeoForge')
        self.assertEqual(page.loader_build.text(), '')
        self.assertEqual(self.window.pack.loader_version, '')

    def test_session_key_is_never_saved(self):
        settings_page = self.window.pages['settings']
        settings_page.key.setText('secret-session-key')
        settings_page.use_key()
        self.wait()
        self.settings.save()
        self.assertNotIn('secret-session-key', (Path(self.folder.name) / 'settings.json').read_text())
        self.assertEqual(self.window.catalogs.curseforge.connection.mode, 'direct')


if __name__ == '__main__':
    unittest.main()
