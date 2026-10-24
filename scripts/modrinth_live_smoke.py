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


def validate_archive(path, minecraft, loader_version, selected_version, total):
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
    expected = selected_version["file"]
    expected_path = "mods/" + expected["filename"]
    selected_found = False
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
        if destination == expected_path:
            selected_found = True
            check(hashes == expected["hashes"]
                  and item["fileSize"] == expected["size"]
                  and urls == [expected["url"]],
                  "El mod principal no coincide con los metadatos reales de Modrinth.")
    check(selected_found, "El mod seleccionado no está en el .mrpack.")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/modrinth-smoke.mrpack"))
    args = parser.parse_args()
    minecraft, loader = "1.20.1", "Fabric"
    catalog = PublicCatalog()

    print("Consultando la ficha real de Fabric API en Modrinth...", flush=True)
    mod = catalog.project("fabric-api")
    check(mod["project_id"], "Modrinth no devolvió un ID de proyecto.")
    version = catalog.version(mod, minecraft, loader)
    print("Versión real:", version["version_number"], flush=True)

    report = audit_public_pack([mod], minecraft, loader, catalog=catalog)
    check(report["selected"] == 1 and report["total"] >= 1,
          "Auditoría pública inconsistente.")
    print("Dependencias obligatorias adicionales:",
          len(report["dependencies"]), flush=True)
    build = resolve_loader_version(minecraft, loader)
    print("Fabric Loader verificado:", build, flush=True)

    result = export_mrpack(args.output, "SMAPT Modrinth Smoke Test",
                           minecraft, loader, build, [mod], catalog=catalog)
    files = validate_archive(args.output, minecraft, build, version,
                             report["total"])
    check(result["mods"] == len(files), "El exportador devolvió un total erróneo.")
    print("PRUEBA REAL SUPERADA:", len(files), "mod(s).")
    print("Archivo:", args.output.resolve())
    print("No se han descargado archivos JAR ni iniciado Minecraft.")


if __name__ == "__main__":
    main()
