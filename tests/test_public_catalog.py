"""Pruebas del modo público, siempre sin cuentas ni descargas de archivos JAR."""
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile
import json
import tempfile
import unittest

from public_catalog import PublicCatalog, PublicCatalogError, export_mrpack, preferred_file, audit_public_pack


def entry(pid="abc", name="Sodium"):
    return {"source": "modrinth", "project_id": pid, "title": name,
            "slug": name.lower(), "description": "Rendimiento", "categories": []}


def version(pid="abc", deps=None, filename="sodium.jar"):
    return {"id": "vers_" + pid, "project_id": pid,
            "version_number": "1.0", "version_type": "release",
            "status": "listed", "game_versions": ["1.20.1"], "loaders": ["fabric"],
            "dependencies": deps or [],
            "files": [{"filename": filename, "url": "https://cdn.modrinth.com/data/x/" + filename,
                       "hashes": {"sha1": "a"*40, "sha512": "b"*128},
                       "size": 1200, "primary": True}]}


class PublicCatalogTests(unittest.TestCase):
    def test_public_search_requires_no_auth(self):
        session = Mock()
        session.get.return_value.json.return_value = {
            "hits": [{"project_id": "abc", "title": "Sodium",
                      "description": "Rendimiento", "slug": "sodium",
                      "icon_url": "", "display_categories": ["optimization"],
                      "downloads": 10000}],
            "total_hits": 1}
        session.get.return_value.status_code = 200
        result = PublicCatalog(session).search("sodium", "1.20.1", "Fabric")
        self.assertEqual(result["mods"][0]["source"], "modrinth")
        options = session.get.call_args.kwargs
        self.assertNotIn("Authorization", options["headers"])
        self.assertEqual(options["params"]["limit"], 30)
        self.assertIn("versions:1.20.1", options["params"]["facets"])

    def test_selects_suitable_versions(self):
        client = PublicCatalog()
        client.get = Mock(return_value=[version()])
        chosen = client.version(entry(), "1.20.1", "Fabric")
        self.assertEqual(chosen["file"]["filename"], "sodium.jar")
        self.assertEqual(chosen["version_id"], "vers_abc")

    def test_rejects_untrusted_file_urls(self):
        value = version()["files"][0]
        for url in ("http://cdn.modrinth.com/file.jar", "https://evil.example/file.jar"):
            with self.assertRaises(PublicCatalogError):
                preferred_file({"files": [dict(value, url=url)]})

    def test_resolves_required_dependencies(self):
        api = PublicCatalog()
        main = version("abc", [{"dependency_type": "required",
                                "project_id": "def", "version_id": None}])
        child = version("def")
        api.get = Mock(side_effect=lambda path, **kw:
                       [main] if path == "/project/abc/version" else
                       [child] if path == "/project/def/version" else
                       {"id": "def", "title": "Fabric API", "slug": "fabric-api", "categories": []})
        pinned = api.resolve([entry()], "1.20.1", "Fabric")
        self.assertEqual({m["project_id"] for m in pinned}, {"abc", "def"})

    def test_preflight_lists_only_automatically_added_dependencies(self):
        api = Mock()
        selected = entry("abc", "Sodium")
        api.resolve.return_value = [
            {"project_id": "abc", "title": "Sodium"},
            {"project_id": "xyz", "title": "Z Library", "version_number": "2"},
            {"project_id": "def", "title": "Fabric API", "version_number": "1"},
        ]
        report = audit_public_pack([selected], "1.20.1", "Fabric", catalog=api)
        self.assertEqual(report["selected"], 1)
        self.assertEqual(report["total"], 3)
        self.assertEqual([d["title"] for d in report["dependencies"]],
                         ["Fabric API", "Z Library"])
        self.assertEqual(selected["title"], "Sodium")
        api.resolve.assert_called_once()

    def test_preflight_rejects_empty_selection(self):
        with self.assertRaises(PublicCatalogError):
            audit_public_pack([], "1.20.1", "Fabric", catalog=Mock())

    def test_exports_importable_mrpack_without_jar_downloads(self):
        api = Mock()
        api.resolve.return_value = [{
            "project_id": "abc", "title": "Sodium", "environment": "client_only",
            "file": version()["files"][0]}]
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "my_pack.mrpack"
            result = export_mrpack(dest, "Mi modpack", "1.20.1",
                                   "Fabric", "0.16.10", [entry()], api)
            with ZipFile(dest) as zipfile:
                data = json.loads(zipfile.read("modrinth.index.json"))
                self.assertFalse(any(n.endswith(".jar") for n in zipfile.namelist()))
            self.assertEqual(result["mods"], 1)
            self.assertEqual(data["dependencies"]["fabric-loader"], "0.16.10")
            self.assertEqual(data["files"][0]["env"]["server"], "unsupported")
            self.assertEqual(data["files"][0]["hashes"]["sha512"], "b"*128)


if __name__ == "__main__":
    unittest.main()
