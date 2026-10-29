"""Pruebas del motor local; no afectan a partidas ni configuraciones reales."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from modlab.core import hardware, instances, recommend, apply_graphics, read_json, save_plan

class CoreTests(unittest.TestCase):
    def test_hardware(self):
        h = hardware()
        self.assertGreater(h["ram_gb"], 1)
        self.assertTrue(h["cpu"])

    def test_instance_detection(self):
        found = instances()
        self.assertTrue(all("path" in pack and "mods" in pack for pack in found))

    def test_recommendations(self):
        h = {"ram_gb": 32, "vram_gb": 8}
        balanced = recommend(283, h)
        self.assertLessEqual(balanced["heap"], 15)
        self.assertGreaterEqual(balanced["render"], 6)
        self.assertFalse(balanced["shaders"])
        fast = recommend(283, h, "Máximos FPS")
        self.assertLess(fast["render"], balanced["render"])

    def test_json_fallback(self):
        self.assertEqual(read_json(Path("/nonexistent/xxx/modpack.json")), {})

    def test_graphics_are_backed_up(self):
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td)
            (pack / "config").mkdir()
            (pack / "options.txt").write_text("renderDistance:16\nmaxFps:260\n")
            (pack / "config/oculus.properties").write_text("enableShaders=true\nshaderPack=pack.zip\n")
            inst = {"path": str(pack), "name": "Test"}
            settings = recommend(283, {"ram_gb":32, "vram_gb":8})
            with patch("modlab.core.is_running", return_value=False):
                path = Path(apply_graphics(inst, settings))
            self.assertTrue((path/"options.txt").exists())
            self.assertIn("renderDistance:16", (path/"options.txt").read_text())
            self.assertIn("renderDistance:8", (pack/"options.txt").read_text())
            self.assertIn("enableShaders=false", (pack/"config/oculus.properties").read_text())
            self.assertIn("shaderPack=pack.zip", (pack/"config/oculus.properties").read_text())

    def test_plan_uses_chosen_destination(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'friend-plan.json'
            result=save_plan('Chill','1.20.1','Forge',[],{}, {},destination=dest)
            self.assertEqual(result,dest)
            self.assertEqual(read_json(dest)['description'],'Chill')

    def test_guard_running_game(self):
        with tempfile.TemporaryDirectory() as td:
            pack = Path(td)
            (pack/"options.txt").write_text("renderDistance:12\n")
            with patch("modlab.core.is_running", return_value=True):
                with self.assertRaises(RuntimeError):
                    apply_graphics({"path":str(pack)}, recommend(80,{"ram_gb":32,"vram_gb":8}))
            self.assertEqual((pack/"options.txt").read_text(), "renderDistance:12\n")

if __name__ == "__main__":
    unittest.main()
