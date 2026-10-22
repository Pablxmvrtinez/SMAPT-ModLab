"""Regresiones de seguridad, portabilidad y recuperación de ModLab."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from core import apply_graphics, latest_graphics_backup, restore_graphics
from app import ModLab


class RecoveryTests(unittest.TestCase):
    def test_restore_works_and_can_be_undone(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "config").mkdir()
            options = folder / "options.txt"
            shaders = folder / "config/oculus.properties"
            options.write_text("renderDistance:20\nmaxFps:260\n")
            shaders.write_text("enableShaders=true\n")
            inst = {"name": "Prueba", "path": str(folder)}
            mode = {"render": 8, "simulation": 6, "fps": 90, "mode": "Máximos FPS", "shaders": False}
            with patch("core.is_running", return_value=False):
                apply_graphics(inst, mode)
                self.assertIn("renderDistance:8", options.read_text())
                self.assertEqual(latest_graphics_backup(inst).name, next((folder / ".smapt-backups").iterdir()).name)
                restored, undo = restore_graphics(inst)
            self.assertIn("renderDistance:20", options.read_text())
            self.assertIn("enableShaders=true", shaders.read_text())
            self.assertIn("renderDistance:8", (Path(undo) / "options.txt").read_text())
            self.assertNotEqual(restored, undo)

    def test_same_timestamp_does_not_overwrite_backup(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "options.txt").write_text("renderDistance:20\n")
            inst = {"name": "Prueba", "path": str(folder)}
            settings = {"render": 8, "simulation": 6, "fps": 90,
                        "mode": "Máximos FPS", "shaders": False}
            with patch("core.datetime") as clock, patch("core.is_running", return_value=False):
                clock.now.return_value.strftime.return_value = "20261022_120000_000000"
                first = apply_graphics(inst, settings)
                restored, second = restore_graphics(inst)
            self.assertEqual(first, restored)
            self.assertNotEqual(first, second)
            self.assertTrue(Path(second, "options.txt").is_file())
            self.assertIn("renderDistance:20", (folder / "options.txt").read_text())

    def test_restore_requires_backup(self):
        with tempfile.TemporaryDirectory() as td:
            inst = {"path": td}
            self.assertIsNone(latest_graphics_backup(inst))
            with self.assertRaisesRegex(ValueError, "copias"):
                restore_graphics(inst)

    def test_restore_refuses_running_game(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "options.txt").write_text("renderDistance:20\n")
            backup = p / ".smapt-backups" / "20261022_010000_000001"
            backup.mkdir(parents=True)
            (backup / "options.txt").write_text("renderDistance:10\n")
            with patch("core.is_running", return_value=True):
                with self.assertRaises(RuntimeError):
                    restore_graphics({"path": td})
            self.assertIn("20", (p / "options.txt").read_text())


class ProjectSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = ModLab()

    def tearDown(self):
        self.window.close()
        self.qt.processEvents()

    def test_rejects_duplicate_projects_without_losing_pack(self):
        self.window.pack = {25: {"source": "curseforge", "project_id": 25, "title": "Existente"}}
        bad = {"schema": 1, "source": "curseforge", "name": "Inseguro",
               "minecraft": "1.20.1", "loader": "Forge",
               "mods": [{"source":"curseforge","project_id":1,"title":"Uno"}] * 2}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text(json.dumps(bad))
            with patch("app.QFileDialog.getOpenFileName", return_value=(str(p), "")):
                self.window.open_project()
        self.assertIn("duplicados", self.window.status.text())
        self.assertIn(25, self.window.pack)

    def test_rejects_oversized_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "oversized.json"
            with p.open("wb") as handle:
                handle.truncate(5 * 1024 * 1024 + 1)
            with patch("app.QFileDialog.getOpenFileName", return_value=(str(p), "")):
                self.window.open_project()
        self.assertIn("5 MB", self.window.status.text())

    def test_save_excludes_raw_catalog_responses(self):
        self.window.pack = {1: {"source":"curseforge","project_id":1,"file_id":100,
                                "title":"Uno","file":{"secrets":"raw metadata"}}}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "project.json"
            with patch("app.QFileDialog.getSaveFileName", return_value=(str(p), "")):
                self.window.save_project()
            data = json.loads(p.read_text())
        self.assertEqual(data["mods"][0]["file_id"], 100)
        self.assertNotIn("file", data["mods"][0])


if __name__ == "__main__":
    unittest.main()
