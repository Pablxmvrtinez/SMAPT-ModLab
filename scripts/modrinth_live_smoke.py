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

from modpack import resolve_loader_version
from public_catalog import PublicCatalog, audit_public_pack, export_mrpack


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
        "mods/" + mod_version["file"]["filename"]: mod_version
        for mod_version in selected_versions
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
            check(hashes == expected["hashes"]
                  and item["fileSize"] == expected["size"]
                  and urls == [expected["url"]],
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
    catalog = PublicCatalog()

    print("Consultando Fabric API y Sodium en Modrinth...", flush=True)
    selected = [catalog.project("fabric-api"), catalog.project("sodium")]
    check(all(mod["project_id"] for mod in selected)
          and selected[0]["project_id"] != selected[1]["project_id"],
          "Modrinth no devolvió dos proyectos diferentes.")
    versions = [catalog.version(mod, minecraft, loader) for mod in selected]
    for mod, version in zip(selected, versions):
        version["title"] = mod["title"]
        print("Versión real de " + mod["title"] + ":",
              version["version_number"], flush=True)

    report = audit_public_pack(selected, minecraft, loader, catalog=catalog)
    check(report["selected"] == len(selected)
          and report["total"] >= len(selected),
          "Auditoría pública inconsistente.")
    print("Dependencias obligatorias adicionales:",
          len(report["dependencies"]), flush=True)
    build = resolve_loader_version(minecraft, loader)
    print("Fabric Loader verificado:", build, flush=True)

    result = export_mrpack(args.output, "SMAPT Modrinth Smoke Test",
                           minecraft, loader, build, selected, catalog=catalog)
    files = validate_archive(args.output, minecraft, build, versions,
                             report["total"])
    check(result["mods"] == len(files), "El exportador devolvió un total erróneo.")
    print("PRUEBA REAL SUPERADA:", len(files), "mod(s).")
    print("Archivo:", args.output.resolve())
    print("No se han descargado archivos JAR ni iniciado Minecraft.")


if __name__ == "__main__":
    main()
