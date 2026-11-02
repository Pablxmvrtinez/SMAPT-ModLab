"""Regresiones de seguridad, portabilidad y recuperación de ModLab."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from modlab.core import apply_graphics, backups, restore_backup
from modlab.project import Pack

MODE = {"render": 8, "simulation": 6, "fps": 90, "mode": "Máximos FPS", "shaders": False}


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
            with patch("modlab.core.is_running", return_value=False):
                apply_graphics(inst, MODE)
                self.assertIn("renderDistance:8", options.read_text())
                latest = backups(inst)[0]
                undo = restore_backup(inst, latest)
            self.assertIn("renderDistance:20", options.read_text())
            self.assertIn("enableShaders=true", shaders.read_text())
            self.assertIn("renderDistance:8", (Path(undo) / "options.txt").read_text())
            self.assertNotEqual(str(latest), undo)

    def test_same_timestamp_does_not_overwrite_backup(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "options.txt").write_text("renderDistance:20\n")
            inst = {"name": "Prueba", "path": str(folder)}
            with patch("modlab.core.datetime") as clock, patch("modlab.core.is_running", return_value=False):
                clock.now.return_value.strftime.return_value = "20261022_120000_000000"
                first = apply_graphics(inst, MODE)
                second = apply_graphics(inst, MODE)
            self.assertNotEqual(first, second)
            self.assertTrue(Path(first, "options.txt").is_file())
            self.assertTrue(Path(second, "options.txt").is_file())
            self.assertEqual(len(backups(inst)), 2)

    def test_restore_requires_a_backup_of_this_instance(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            (Path(td) / "options.txt").write_text("renderDistance:20\n")
            self.assertEqual(backups({"path": td}), [])
            with self.assertRaises(ValueError):
                restore_backup({"path": td}, Path(other))

    def test_restore_refuses_running_game(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "options.txt").write_text("renderDistance:20\n")
            backup = p / ".smapt-backups" / "20261022_010000_000001"
            backup.mkdir(parents=True)
            (backup / "options.txt").write_text("renderDistance:10\n")
            with patch("modlab.core.is_running", return_value=True):
                with self.assertRaises(RuntimeError):
                    restore_backup({"path": td}, backup)
            self.assertIn("20", (p / "options.txt").read_text())


class ProjectSafetyTests(unittest.TestCase):
    def project(self, mods, **extra):
        return dict({"schema": 2, "name": "Pack", "minecraft": "1.20.1", "loader": "Forge", "mods": mods}, **extra)

    def test_rejects_duplicate_projects(self):
        mods = [{"source": "curseforge", "project_id": 1, "title": "Uno"}] * 2
        with self.assertRaisesRegex(ValueError, "duplicados"):
            Pack.from_json(self.project(mods))

    def test_rejects_oversized_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "oversized.json"
            with p.open("wb") as handle:
                handle.truncate(5 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, "5 MB"):
                Pack.load(p)

    def test_rejects_bad_file_ids(self):
        for mod in ({"source": "curseforge", "project_id": 1, "title": "x", "file_id": "1"},
                    {"source": "curseforge", "project_id": 1, "title": "x", "file_id": -5},
                    {"source": "modrinth", "project_id": "AAAA", "title": "x", "file_id": "../v"}):
            with self.assertRaises(ValueError):
                Pack.from_json(self.project([mod]))

    def test_save_excludes_raw_catalog_responses(self):
        pack = Pack()
        pack.add({"source": "curseforge", "project_id": 1, "file_id": 100, "title": "Uno",
                  "file": {"secrets": "raw metadata"}, "latest_files": [1]})
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "project.json"
            pack.save(p)
            data = json.loads(p.read_text())
        self.assertEqual(data["mods"][0]["file_id"], 100)
        self.assertNotIn("file", data["mods"][0])
        self.assertNotIn("latest_files", data["mods"][0])

    def test_manual_loader_build_is_kept_until_target_changes(self):
        pack = Pack.from_json(self.project([], loader_version="47.4.10"))
        self.assertEqual(pack.loader_version, "47.4.10")
        self.assertEqual(Pack.from_json(pack.to_json()).loader_version, "47.4.10")
        pack.set_target("1.21.1", "NeoForge")
        self.assertEqual(pack.loader_version, "")
        with self.assertRaises(ValueError):
            Pack.from_json(self.project([], loader_version="47; rm -rf"))


if __name__ == "__main__":
    unittest.main()
