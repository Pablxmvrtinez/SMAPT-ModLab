"""Interfaz pública verificable sin acceso a Internet."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app import ModLab


class PublicUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = ModLab()
        self.window.images.fetch = Mock()
        self.example = {
            "source": "modrinth", "project_id": "abc123", "title": "Sodium",
            "slug": "sodium", "description": "Rendimiento", "logo": "",
            "screenshots": [], "downloads": 12, "categories": []
        }
        self.window.public_page.catalog = Mock()
        self.window.public_page.catalog.search.return_value = {
            "mods": [self.example], "total": 1}

    def tearDown(self):
        self.wait()
        self.window.close()
        self.qt.processEvents()

    def wait(self):
        end = time.monotonic() + 4
        while self.window.tasks and time.monotonic() < end:
            self.qt.processEvents()
            time.sleep(.005)
        self.qt.processEvents()
        self.assertFalse(self.window.tasks)

    def test_public_catalog_loads_without_credential(self):
        self.window.navigate(6)
        self.wait()
        self.assertEqual(self.window.stack.currentIndex(), 6)
        self.assertEqual(len(self.window.public_page.grid.cards), 1)
        self.assertEqual(self.window.public_page.results[0]["title"], "Sodium")
        self.window.public_page.catalog.search.assert_called_once()

    def test_public_selection_survives_version_change(self):
        page = self.window.public_page
        page.add_mod(self.example)
        self.assertEqual(len(page.pack), 1)
        self.window.version.setCurrentText("1.21.1")
        self.assertEqual(len(page.pack), 1)
        self.assertFalse(page.loaded)

    def test_public_preflight_reports_dependencies_without_changing_selection(self):
        page = self.window.public_page
        page.add_mod(self.example)
        with patch("public_page.audit_public_pack", return_value={
            "selected": 1, "total": 2,
            "dependencies": [{"project_id": "fabric-api", "title": "Fabric API", "version": "0.1"}],
        }) as audit, patch("public_page.QMessageBox.information") as dialog:
            page.check_pack()
            self.wait()
        audit.assert_called_once()
        self.assertEqual(len(page.pack), 1)
        self.assertIn("Fabric API", dialog.call_args.args[2])
        self.assertTrue(page.audit.isEnabled())

    def test_reopen_restores_saved_minecraft_loader_and_manual_version(self):
        page = self.window.public_page
        self.window.version.setCurrentText("1.21.1")
        self.window.loader.setCurrentText("Fabric")
        page.loader_version.setText("0.16.10")
        page.add_mod(self.example)
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "project.json"
            with patch("public_page.QFileDialog.getSaveFileName",
                       return_value=(str(file), "")):
                page.save()
            data = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(data["minecraft"], "1.21.1")
            self.assertEqual(data["loader"], "Fabric")
            self.assertEqual(data["loader_version"], "0.16.10")
            self.window.version.setCurrentText("1.20.1")
            self.window.loader.setCurrentText("Forge")
            page.pack = {}
            with patch("public_page.QFileDialog.getOpenFileName",
                       return_value=(str(file), "")):
                page.open()
        self.assertEqual(self.window.version.currentText(), "1.21.1")
        self.assertEqual(self.window.loader.currentText(), "Fabric")
        self.assertEqual(page.loader_version.text(), "0.16.10")
        self.assertIn("abc123", page.pack)

    def test_reopen_invalid_config_preserves_active_selection(self):
        page = self.window.public_page
        page.add_mod(self.example)
        initial_version = self.window.version.currentText()
        initial_loader = self.window.loader.currentText()
        invalid = {
            "schema": 1, "source": "modrinth", "name": "Invalido",
            "minecraft": "../bad", "loader": "Fabric", "mods": [],
        }
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "bad.json"
            file.write_text(json.dumps(invalid), encoding="utf-8")
            with patch("public_page.QFileDialog.getOpenFileName",
                       return_value=(str(file), "")), patch.object(self.window, "failure") as failure:
                page.open()
        failure.assert_called_once()
        self.assertEqual(self.window.version.currentText(), initial_version)
        self.assertEqual(self.window.loader.currentText(), initial_loader)
        self.assertIn("abc123", page.pack)

    def test_changing_minecraft_clears_old_manual_loader_build(self):
        page = self.window.public_page
        page.loader_version.setText("0.16.10")
        self.window.version.setCurrentText("1.21.1")
        self.assertEqual(page.loader_version.text(), "")

    def test_save_and_reload_public_selection(self):
        page = self.window.public_page
        page.add_mod(self.example)
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "selection.json"
            with patch("public_page.QFileDialog.getSaveFileName",
                       return_value=(str(file), "")):
                page.save()
            saved = json.loads(file.read_text())
            self.assertEqual(saved["mods"][0]["project_id"], "abc123")
            page.pack = {}
            with patch("public_page.QFileDialog.getOpenFileName",
                       return_value=(str(file), "")):
                page.open()
        self.assertEqual(page.pack["abc123"]["title"], "Sodium")


if __name__ == "__main__":
    unittest.main()
