"""Prueba real de Modrinth: genera y verifica un .mrpack sin descargar JAR.

Uso:
    python scripts/modrinth_live_smoke.py --output artifacts/modrinth-smoke.mrpack

Necesita conexión con Modrinth y Fabric Meta. No instala Minecraft.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modlab.modpack import build_mrpack, resolve_loader_version  # noqa: E402
from modlab.mrpack_validator import validate_exported_mrpack  # noqa: E402
from modlab.sources import ModrinthClient  # noqa: E402


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_archive(path, minecraft, loader_version, selected_versions, total):
    """Valida el ZIP y compara el mod principal con los metadatos originales."""
    with ZipFile(path) as archive:
        check(archive.namelist() == ["modrinth.index.json"],
              "El .mrpack contiene archivos inesperados o JAR incrustados.")
        check(archive.testzip() is None, "El ZIP generado está dañado.")
        manifest = json.loads(archive.read("modrinth.index.json"))
    check(manifest.get("formatVersion") == 1, "Versión de formato incorrecta.")
    check(manifest.get("game") == "minecraft", "Juego incorrecto.")
    check(manifest.get("dependencies") == {
        "minecraft": minecraft, "fabric-loader": loader_version
    }, "Minecraft o cargador incorrectos en el manifiesto.")
    files = manifest.get("files")
    check(isinstance(files, list) and len(files) == total and total > 0,
          "La cantidad de mods del manifiesto no coincide con el análisis.")
    paths = set()
    expected_files = {
        "mods/" + pinned["file"]["filename"]: pinned
        for pinned in selected_versions
    }
    check(len(expected_files) == len(selected_versions),
          "Los mods seleccionados usan el mismo nombre de archivo.")
    selected_found = set()
    for item in files:
        destination = item.get("path", "")
        check(isinstance(destination, str) and destination.startswith("mods/")
              and destination.endswith(".jar") and ".." not in destination
              and "\\" not in destination and destination.count("/") == 1,
              "Ruta insegura o inesperada en el manifiesto.")
        check(destination not in paths, "Archivo duplicado en el .mrpack.")
        paths.add(destination)
        hashes = item.get("hashes", {})
        check(isinstance(hashes, dict)
              and re.fullmatch(r"[a-f0-9]{40}", hashes.get("sha1", ""))
              and re.fullmatch(r"[a-f0-9]{128}", hashes.get("sha512", "")),
              "Hashes ausentes o mal formados.")
        check(type(item.get("fileSize")) is int and item["fileSize"] > 0,
              "Tamaño inválido.")
        urls = item.get("downloads")
        check(isinstance(urls, list) and len(urls) == 1
              and urlparse(urls[0]).scheme == "https"
              and urlparse(urls[0]).hostname == "cdn.modrinth.com",
              "Descarga externa no admitida.")
        environment = item.get("env", {})
        check(isinstance(environment, dict)
              and set(environment) == {"client", "server"}
              and all(side in ("required", "optional", "unsupported")
                      for side in environment.values()),
              "Entorno cliente/servidor incorrecto.")
        if destination in expected_files:
            expected_version = expected_files[destination]
            expected = expected_version["file"]
            selected_found.add(destination)
            check(hashes == {"sha1": expected["sha1"], "sha512": expected["sha512"]}
                  and item["fileSize"] == expected["size"]
                  and urls == [expected["download_url"]],
                  "Un mod seleccionado no coincide con Modrinth.")
            if expected_version["title"] == "Sodium":
                check(environment["server"] == "unsupported",
                      "Sodium debe estar marcado como mod solo de cliente.")
    check(selected_found == set(expected_files),
          "Faltan mods seleccionados en el .mrpack.")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/modrinth-smoke.mrpack"))
    args = parser.parse_args()
    minecraft, loader = "1.20.1", "Fabric"
    catalog = ModrinthClient(cache=False)

    print("Consultando Fabric API y Sodium en Modrinth...", flush=True)
    selected = [catalog.mod("fabric-api"), catalog.mod("sodium")]
    check(all(mod["project_id"] for mod in selected)
          and selected[0]["project_id"] != selected[1]["project_id"],
          "Modrinth no devolvió dos proyectos diferentes.")
    versions = [catalog.pin(mod, minecraft, loader) for mod in selected]
    for pinned in versions:
        print("Versión real de " + pinned["title"] + ":", pinned["version_number"], flush=True)

    report = catalog.resolve_report(selected, minecraft, loader)
    check(not report["missing"] and not report["conflicts"]
          and len(report["mods"]) >= len(selected),
          "Auditoría pública inconsistente.")
    print("Dependencias obligatorias adicionales:",
          len(report["dependencies"]), flush=True)
    build = resolve_loader_version(minecraft, loader)
    print("Fabric Loader verificado:", build, flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = build_mrpack(args.output, "SMAPT Modrinth Smoke Test",
                          minecraft, loader, build, selected, client=catalog)
    files = validate_archive(args.output, minecraft, build, versions,
                             len(report["mods"]))
    validation = validate_exported_mrpack(args.output, expected_count=len(files))
    check(result["mods"] == validation["mods"] == len(files),
          "El exportador y los validadores no coinciden.")
    print("PRUEBA REAL SUPERADA:", len(files), "mod(s).")
    print("Archivo:", args.output.resolve())
    print("No se han descargado archivos JAR ni iniciado Minecraft.")


if __name__ == "__main__":
    main()
