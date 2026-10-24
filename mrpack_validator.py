"""Validación independiente de los .mrpack generados por SMAPT ModLab.

Esta validación comprueba los metadatos y la integridad del ZIP, pero no descarga
JAR ni garantiza que los mods se ejecuten correctamente en Minecraft.
"""
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile


class MrpackValidationError(ValueError):
    """El archivo no cumple las restricciones del exportador público."""


VALID_SIDES = {"required", "optional", "unsupported"}
LOADERS = {"fabric-loader", "forge", "neoforge"}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
SAFE_PATH = re.compile(r"mods/[^/\\\x00-\x1f]+\.jar\Z", re.IGNORECASE)
MAX_MANIFEST_BYTES = 10_000_000
RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
FORBIDDEN_WINDOWS_CHARS = set('<>:"|?*')


def safe_mod_filename(filename):
    """No genera rutas que Windows o Linux interpreten de forma distinta."""
    if not isinstance(filename, str) or len(filename) > 255:
        return False
    if filename.strip() != filename or any(c in filename for c in FORBIDDEN_WINDOWS_CHARS):
        return False
    stem = filename.split(".", 1)[0].upper()
    return stem not in RESERVED_WINDOWS_NAMES


def _ensure(ok, message):
    if not ok:
        raise MrpackValidationError(message)


def validate_exported_mrpack(path, expected_count=None):
    """Revisa estructura, rutas, URL, hashes, entornos y metadatos.

    Solo admite el subconjunto de Modrinth producido por este exportador:
    un manifiesto JSON y cero archivos JAR dentro del ZIP.
    """
    path = Path(path)
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            _ensure(len(members) == 1
                    and members[0].filename == "modrinth.index.json"
                    and not members[0].is_dir(),
                    "El paquete debe contener únicamente modrinth.index.json.")
            _ensure(members[0].file_size <= MAX_MANIFEST_BYTES,
                    "El manifiesto supera el límite permitido.")
            _ensure(archive.testzip() is None,
                    "El paquete ZIP no supera la comprobación de integridad.")
            manifest = json.loads(archive.read(members[0]).decode("utf-8"))
    except (BadZipFile, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MrpackValidationError("No se puede leer el manifiesto del .mrpack.") from exc

    _ensure(isinstance(manifest, dict), "El manifiesto debe ser un objeto JSON.")
    _ensure(type(manifest.get("formatVersion")) is int
            and manifest["formatVersion"] == 1,
            "La versión del formato .mrpack no es válida.")
    _ensure(manifest.get("game") == "minecraft",
            "El paquete no corresponde a Minecraft.")
    _ensure(isinstance(manifest.get("name"), str)
            and 0 < len(manifest["name"].strip()) <= 120,
            "El nombre del modpack no es válido.")
    _ensure(isinstance(manifest.get("versionId"), str)
            and bool(manifest["versionId"]), "Falta la versión del modpack.")

    deps = manifest.get("dependencies")
    _ensure(isinstance(deps, dict)
            and "minecraft" in deps
            and len(set(deps) & LOADERS) == 1
            and len(deps) == 2
            and all(isinstance(value, str) and bool(value.strip())
                    for value in deps.values()),
            "Faltan la versión de Minecraft o un cargador válido.")

    files = manifest.get("files")
    _ensure(isinstance(files, list) and len(files) > 0,
            "El modpack no contiene mods.")
    if expected_count is not None:
        _ensure(type(expected_count) is int and len(files) == expected_count,
                "El número de archivos exportados no coincide con lo previsto.")

    seen = set()
    for index, item in enumerate(files, start=1):
        _ensure(isinstance(item, dict),
                f"La entrada de mod {index} no es válida.")
        name = item.get("path")
        _ensure(isinstance(name, str) and SAFE_PATH.fullmatch(name)
                and name.rsplit("/", 1)[1] not in (".jar", "..jar")
                and safe_mod_filename(name.rsplit("/", 1)[1]),
                f"Ruta de mod no válida en la entrada {index}.")
        key = name.casefold()
        _ensure(key not in seen,
                f"Hay archivos con nombres duplicados: {name}.")
        seen.add(key)

        hashes = item.get("hashes")
        _ensure(isinstance(hashes, dict)
                and isinstance(hashes.get("sha1"), str)
                and isinstance(hashes.get("sha512"), str)
                and HEX40.fullmatch(hashes["sha1"])
                and HEX128.fullmatch(hashes["sha512"]),
                f"Los hashes del mod {index} no son válidos.")
        _ensure(type(item.get("fileSize")) is int and item["fileSize"] > 0,
                f"El tamaño del mod {index} no es válido.")

        sides = item.get("env")
        _ensure(isinstance(sides, dict)
                and set(sides) == {"client", "server"}
                and all(value in VALID_SIDES for value in sides.values()),
                f"El entorno del mod {index} no es válido.")
        links = item.get("downloads")
        _ensure(isinstance(links, list) and len(links) == 1
                and isinstance(links[0], str),
                f"Las URL de descarga del mod {index} no son válidas.")
        try:
            url = urlparse(links[0])
            trusted = (url.scheme == "https"
                       and url.hostname == "cdn.modrinth.com"
                       and url.port in (None, 443)
                       and url.username is None and url.password is None
                       and url.path.startswith("/data/"))
        except ValueError:
            trusted = False
        _ensure(trusted,
                f"La descarga del mod {index} no procede de Modrinth.")

    return {
        "mods": len(files),
        "minecraft": deps["minecraft"],
        "loader": next(loader for loader in LOADERS if loader in deps),
    }
