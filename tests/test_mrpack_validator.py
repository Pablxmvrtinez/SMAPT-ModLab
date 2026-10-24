"""Pruebas del validador .mrpack, sin conexión ni descargas JAR."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from mrpack_validator import MrpackValidationError, validate_exported_mrpack
from public_catalog import PublicCatalogError, export_mrpack
from unittest.mock import Mock


def manifest():
    return {
        "formatVersion": 1, "game": "minecraft", "versionId": "1.0.0",
        "name": "Pack de prueba",
        "dependencies": {"minecraft": "1.20.1", "fabric-loader": "0.16.10"},
        "files": [{
            "path": "mods/fabric-api.jar",
            "hashes": {"sha1": "a" * 40, "sha512": "b" * 128},
            "downloads": ["https://cdn.modrinth.com/data/abc/versions/x/fabric-api.jar"],
            "env": {"client": "required", "server": "required"},
            "fileSize": 1024,
        }]
    }


def archive(path, payload, extra=False):
    with ZipFile(path, "w") as destination:
        destination.writestr("modrinth.index.json", json.dumps(payload))
        if extra:
            destination.writestr("mods/should-not-be-here.jar", b"example")


class ValidateMrpackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "pack.mrpack"

    def assert_invalid(self, payload):
        archive(self.target, payload)
        with self.assertRaises(MrpackValidationError):
            validate_exported_mrpack(self.target)

    def test_generated_structure_is_valid(self):
        archive(self.target, manifest())
        report = validate_exported_mrpack(self.target, expected_count=1)
        self.assertEqual(report["mods"], 1)
        self.assertEqual(report["minecraft"], "1.20.1")
        self.assertEqual(report["loader"], "fabric-loader")

    def test_rejects_unexpected_zip_contents(self):
        archive(self.target, manifest(), extra=True)
        with self.assertRaisesRegex(MrpackValidationError, "únicamente"):
            validate_exported_mrpack(self.target)

    def test_rejects_corrupted_archive(self):
        self.target.write_bytes(b"not a zip")
        with self.assertRaises(MrpackValidationError):
            validate_exported_mrpack(self.target)

    def test_rejects_wrong_expected_file_count(self):
        archive(self.target, manifest())
        with self.assertRaisesRegex(MrpackValidationError, "número"):
            validate_exported_mrpack(self.target, expected_count=2)

    def test_rejects_unsafe_paths(self):
        for path in ("mods/../escape.jar", "../escape.jar", "mods/a/b.jar",
                     "mods/evil\\file.jar", "mods/.jar"):
            with self.subTest(path=path):
                invalid = manifest()
                invalid["files"][0]["path"] = path
                self.assert_invalid(invalid)

    def test_rejects_case_insensitive_duplicate_filenames(self):
        invalid = manifest()
        another = copy.deepcopy(invalid["files"][0])
        another["path"] = "mods/FABRIC-API.jar"
        invalid["files"].append(another)
        self.assert_invalid(invalid)

    def test_rejects_fake_cdn_origin(self):
        for url in (
            "https://cdn.modrinth.com.evil.example/data/x/f.jar",
            "http://cdn.modrinth.com/data/x/f.jar",
            "https://cdn.modrinth.com:8443/data/x/f.jar",
            "https://user:pass@cdn.modrinth.com/data/x/f.jar",
            "https://example.com/data/x/f.jar",
        ):
            with self.subTest(url=url):
                invalid = manifest()
                invalid["files"][0]["downloads"] = [url]
                self.assert_invalid(invalid)

    def test_rejects_invalid_hash_sizes_and_environment(self):
        for key, value in (
            ("hashes", {"sha1": "a", "sha512": "b" * 128}),
            ("fileSize", True),
            ("fileSize", 0),
            ("env", {"client": "required", "server": "enabled"}),
        ):
            with self.subTest(key=key, value=value):
                invalid = manifest()
                invalid["files"][0][key] = value
                self.assert_invalid(invalid)

    def test_failed_export_preserves_previous_file(self):
        previous = b"existing project"
        self.target.write_bytes(previous)
        fake_catalog = Mock()
        fake_catalog.resolve.return_value = [{
            "project_id": "abc", "title": "Unsafe", "environment": "client_and_server",
            "file": {
                "filename": "../escape.jar",
                "hashes": {"sha1": "a" * 40, "sha512": "b" * 128},
                "url": "https://cdn.modrinth.com/data/x/escape.jar",
                "size": 1200,
            },
        }]
        with self.assertRaises(PublicCatalogError):
            export_mrpack(self.target, "Example", "1.20.1", "Fabric", "0.16.10",
                          [{"project_id": "abc", "title": "Unsafe"}],
                          catalog=fake_catalog)
        self.assertEqual(self.target.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
