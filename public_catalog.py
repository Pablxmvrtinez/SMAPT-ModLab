"""Catálogo público de mods; API oficial de Modrinth sin claves."""
import requests
import json

API = 'https://api.modrinth.com/v2'
USER_AGENT = 'Pablxmvrtinez/SMAPT-ModLab/1.1'

class PublicCatalogError(ValueError):
    pass

from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from zipfile import ZipFile, ZIP_DEFLATED
from tempfile import TemporaryDirectory
import re

LOADERS = {"Forge": "forge", "Fabric": "fabric", "NeoForge": "neoforge"}
PACK_LOADERS = {"Forge": "forge", "Fabric": "fabric-loader", "NeoForge": "neoforge"}

# Side flags follow the .mrpack physical client/dedicated-server specification.
# "server_only" can also work in singleplayer, so the client is optional.
ENVIRONMENT_SIDES = {
    "client_and_server": ("required", "required"),
    "client_only": ("required", "unsupported"),
    "client_only_server_optional": ("required", "optional"),
    "singleplayer_only": ("required", "unsupported"),
    "server_only": ("optional", "required"),
    "server_only_client_optional": ("optional", "required"),
    "dedicated_server_only": ("unsupported", "required"),
    "client_or_server": ("required", "optional"),
    "client_or_server_prefers_both": ("required", "required"),
    "unknown": ("required", "required"),
}


def modpack_sides(environment):
    """Traduce el entorno de Modrinth a flags de instalacion de un .mrpack."""
    client, server = ENVIRONMENT_SIDES.get(environment, ("required", "required"))
    return {"client": client, "server": server}


def normalize(hit):
    return {
        "source": "modrinth", "project_id": str(hit["project_id"]),
        "title": str(hit.get("title", "")), "slug": str(hit.get("slug", "")),
        "description": str(hit.get("description", "")),
        "logo": str(hit.get("icon_url") or ""), "screenshots": [],
        "downloads": int(hit.get("downloads", 0)),
        "categories": [{"name": str(x)} for x in hit.get("display_categories", [])]
    }


def preferred_file(version):
    for f in sorted(version.get("files", []), key=lambda x: not x.get("primary", False)):
        hashes = f.get("hashes") or {}
        url = urlparse(f.get("url", ""))
        name = f.get("filename", "")
        if (name.endswith(".jar") and "/" not in name and "\\" not in name
                and url.scheme == "https" and url.hostname == "cdn.modrinth.com"
                and re.fullmatch("[a-f0-9]{40}", hashes.get("sha1", ""))
                and re.fullmatch("[a-f0-9]{128}", hashes.get("sha512", ""))
                and type(f.get("size")) is int and f["size"] > 0):
            return f
    raise PublicCatalogError("La versión no contiene un archivo JAR verificable.")


class PublicCatalog:
    def __init__(self, client=None):
        self.client = client or requests

    def get(self, route, **params):
        try:
            response = self.client.get(API + route, params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=(10, 30))
            if response.status_code == 429:
                raise PublicCatalogError("Modrinth limita las peticiones. Inténtalo más tarde.")
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            raise PublicCatalogError("No se ha podido conectar con Modrinth.") from None

    def search(self, query="", minecraft="1.20.1", loader="Fabric", offset=0, limit=30):
        if loader not in LOADERS or not 0 <= offset < 10000 or not 1 <= limit <= 100:
            raise PublicCatalogError("Búsqueda no válida.")
        facets = [["project_type:mod"], ["versions:" + minecraft],
                  ["categories:" + LOADERS[loader]]]
        data = self.get("/search", query=query, facets=json.dumps(facets),
                        index="downloads", offset=offset, limit=limit)
        return {"mods": [normalize(row) for row in data["hits"]],
                "total": int(data.get("total_hits", 0))}

    def project(self, pid):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(pid)):
            raise PublicCatalogError("ID de proyecto no válido.")
        d = self.get("/project/" + str(pid))
        return normalize({"project_id": d["id"], "title": d["title"],
                          "slug": d.get("slug", ""), "description": d.get("description", ""),
                          "icon_url": d.get("icon_url"), "downloads": d.get("downloads", 0),
                          "display_categories": d.get("categories", [])})

    def version(self, mod, minecraft, loader, selected_version=None):
        pid = str(mod["project_id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", pid) or loader not in LOADERS:
            raise PublicCatalogError("Proyecto o cargador no válido.")
        if selected_version is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", selected_version):
                raise PublicCatalogError("ID de versión no válido.")
            rows = [self.get("/version/" + selected_version)]
        else:
            rows = self.get("/project/" + pid + "/version",
                            loaders=json.dumps([LOADERS[loader]]),
                            game_versions=json.dumps([minecraft]),
                            include_changelog="false")
        for row in rows:
            if (str(row.get("project_id")) != pid
                    or minecraft not in row.get("game_versions", [])
                    or LOADERS[loader] not in row.get("loaders", [])
                    or row.get("version_type") not in ("release", "beta")
                    or row.get("status") not in (None, "listed")):
                continue
            try:
                file = preferred_file(row)
            except PublicCatalogError:
                continue
            return {"project_id": pid, "title": mod["title"],
                    "version_id": row["id"], "version_number": row["version_number"],
                    "file": file, "dependencies": row.get("dependencies") or [],
                    "environment": row.get("environment", "client_and_server")}
        raise PublicCatalogError("No existe una versión compatible de " + mod["title"]
                                 + f" para {minecraft}/{loader}.")

    def resolve(self, mods, minecraft, loader, progress=lambda message: None):
        if not mods:
            raise PublicCatalogError("Añade al menos un mod antes de exportar.")
        selected = {str(mod["project_id"]): mod for mod in mods}
        finished, visiting, incompatible = {}, set(), set()

        def visit(mod, version_id=None):
            pid = str(mod["project_id"])
            if pid in finished:
                if version_id and version_id != finished[pid]["version_id"]:
                    raise PublicCatalogError("Versiones incompatibles de una dependencia.")
                return
            if pid in visiting:
                raise PublicCatalogError(
                    "Se han detectado dependencias obligatorias circulares en el pack."
                )
            if len(finished) + len(visiting) >= 300:
                raise PublicCatalogError("Demasiadas dependencias para un solo pack.")
            visiting.add(pid)
            try:
                progress("Comprobando " + mod["title"])
                version = self.version(mod, minecraft, loader, version_id)
                for dep in version["dependencies"]:
                    project = dep.get("project_id")
                    requested = dep.get("version_id")
                    dependency_type = dep.get("dependency_type")
                    if dependency_type not in ("required", "incompatible"):
                        continue
                    if not project and requested:
                        project = self.get("/version/" + requested).get("project_id")
                    if dependency_type == "incompatible":
                        if project:
                            incompatible.add((pid, str(project)))
                        continue
                    if not project:
                        raise PublicCatalogError("Dependencia obligatoria sin proyecto conocido.")
                    project = str(project)
                    visit(selected.get(project) or self.project(project), requested)
                finished[pid] = version
            finally:
                visiting.remove(pid)

        for mod in mods:
            visit(mod)
        for left, right in incompatible:
            if right in finished:
                raise PublicCatalogError("Mods incompatibles: " +
                                         finished[left]["title"] + " y " + finished[right]["title"])
        return list(finished.values())


def audit_public_pack(mods, minecraft, loader, progress=lambda message: None, catalog=None):
    """Comprueba versiones, conflictos y dependencias sin modificar la selección."""
    if not mods:
        raise PublicCatalogError("Añade al menos un mod antes de comprobar el pack.")
    resolved = (catalog or PublicCatalog()).resolve(mods, minecraft, loader, progress)
    selected_ids = {str(mod["project_id"]) for mod in mods}
    additional = sorted(
        (mod for mod in resolved if str(mod["project_id"]) not in selected_ids),
        key=lambda mod: mod["title"].casefold(),
    )
    return {
        "selected": len(selected_ids),
        "total": len(resolved),
        "dependencies": [
            {"project_id": mod["project_id"], "title": mod["title"],
             "version": mod.get("version_number", "")}
            for mod in additional
        ],
    }


def export_mrpack(destination, name, minecraft, loader, loader_version, mods,
                  catalog=None, progress=lambda message: None):
    if loader not in PACK_LOADERS or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,60}", loader_version):
        raise PublicCatalogError("Indica una versión válida del cargador.")
    if not name.strip() or len(name) > 120:
        raise PublicCatalogError("El pack debe tener un nombre de hasta 120 caracteres.")
    pinned = (catalog or PublicCatalog()).resolve(mods, minecraft, loader, progress)
    files, seen = [], set()
    for mod in pinned:
        file = mod["file"]
        dest = str(PurePosixPath("mods") / file["filename"])
        if dest in seen:
            raise PublicCatalogError("Dos mods usan el mismo nombre de archivo: " + dest)
        seen.add(dest)
        env = modpack_sides(mod.get("environment"))
        files.append({
            "path": dest,
            "hashes": {"sha1": file["hashes"]["sha1"], "sha512": file["hashes"]["sha512"]},
            "env": env,
            "downloads": [file["url"]], "fileSize": file["size"],
        })
    manifest = {
        "formatVersion": 1, "game": "minecraft", "versionId": "1.0.0",
        "name": name.strip(), "summary": "Creado con SMAPT ModLab",
        "files": files,
        "dependencies": {"minecraft": minecraft, PACK_LOADERS[loader]: loader_version},
    }
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".smapt-public-", dir=output.parent) as temp:
        archive = Path(temp) / "export.mrpack"
        with ZipFile(archive, "w", ZIP_DEFLATED) as zipfile:
            zipfile.writestr("modrinth.index.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.replace(output)
    return {"path": str(output), "mods": len(pinned)}
