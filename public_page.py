"""Página pública de Modrinth: buscar, seleccionar, guardar y exportar sin API key."""
from pathlib import Path
import json
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox)
from visual_widgets import CardGrid
from modpack import resolve_loader_version
from public_catalog import PublicCatalog, export_mrpack


class PublicPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.catalog = PublicCatalog()
        self.pack = {}
        self.results = []
        self.offset = 0
        self.total = 0
        self.loaded = False

        layout = QVBoxLayout(self)
        title = QLabel("Catálogo público · Modrinth")
        title.setObjectName("h1")
        layout.addWidget(title)
        note = QLabel("Sin claves ni registros. Busca mods compatibles, elige los que quieras y exporta un paquete .mrpack.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Buscar: Create, Sodium, muebles, aventuras…")
        self.query.returnPressed.connect(self.search_mods)
        row.addWidget(self.query, 1)
        button = QPushButton("Buscar")
        button.setObjectName("primary")
        button.clicked.connect(self.search_mods)
        row.addWidget(button)
        layout.addLayout(row)

        self.info = QLabel("Catálogo público de Modrinth")
        self.info.setObjectName("muted")
        layout.addWidget(self.info)
        self.grid = CardGrid(host.images)
        self.grid.add.connect(self.add_mod)
        self.grid.details.connect(self.show_details)
        layout.addWidget(self.grid, 1)

        row = QHBoxLayout()
        self.prev = QPushButton("← Anteriores")
        self.prev.clicked.connect(lambda: self.search_mods(offset=max(self.offset-30, 0)))
        self.next = QPushButton("Siguientes →")
        self.next.clicked.connect(lambda: self.search_mods(offset=self.offset+30))
        self.prev.setEnabled(False)
        self.next.setEnabled(False)
        row.addWidget(self.prev)
        row.addWidget(self.next)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(QLabel("Mi selección para Modrinth"))
        self.selected = QListWidget()
        self.selected.setMaximumHeight(130)
        layout.addWidget(self.selected)
        row = QHBoxLayout()
        remove = QPushButton("Quitar seleccionado")
        remove.clicked.connect(self.remove_mod)
        save = QPushButton("Guardar selección")
        save.clicked.connect(self.save)
        load = QPushButton("Abrir selección")
        load.clicked.connect(self.open)
        row.addWidget(remove)
        row.addWidget(save)
        row.addWidget(load)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.pack_name = QLineEdit("Mi modpack")
        self.pack_name.setPlaceholderText("Nombre del modpack")
        self.loader_version = QLineEdit()
        self.loader_version.setPlaceholderText("Versión del cargador (automática)")
        row.addWidget(self.pack_name)
        row.addWidget(self.loader_version)
        layout.addLayout(row)
        self.export = QPushButton("Exportar paquete .mrpack para Modrinth / Prism")
        self.export.setObjectName("primary")
        self.export.clicked.connect(self.export_pack)
        layout.addWidget(self.export)
        self.refresh()

    def search_mods(self, *_, offset=0):
        if self.host.busy:
            return
        mc = self.host.version.currentText().strip()
        loader = self.host.loader.currentText()
        query = self.query.text().strip()
        self.loaded = True
        def ready(data):
            self.results = data["mods"]
            self.total = data["total"]
            self.offset = offset
            self.grid.show_mods(self.results, self.pack)
            self.info.setText(f"Modrinth · {self.total} resultados · Minecraft {mc}/{loader}")
            self.prev.setEnabled(offset > 0)
            self.next.setEnabled(offset+30 < self.total)
            if not self.results:
                self.info.setText("No se encontraron mods con estos filtros.")
        self.host.run_task(lambda progress: self.catalog.search(query, mc, loader, offset, 30), ready)

    def add_mod(self, mod):
        if mod["project_id"] not in self.pack:
            self.pack[mod["project_id"]] = mod
            self.refresh()

    def remove_mod(self):
        row = self.selected.currentItem()
        if row:
            self.pack.pop(row.data(Qt.ItemDataRole.UserRole), None)
            self.refresh()

    def refresh(self):
        self.selected.clear()
        for mod in self.pack.values():
            row = QListWidgetItem(mod["title"])
            row.setData(Qt.ItemDataRole.UserRole, mod["project_id"])
            self.selected.addItem(row)
        self.grid.update_pack(self.pack)
        self.export.setEnabled(bool(self.pack))

    def target_changed(self):
        self.loaded = False
        self.results = []
        self.grid.show_mods([])
        self.info.setText("Versión o cargador cambiado: busca mods para la nueva selección. Las versiones se verificarán al exportar.")
        self.offset = 0
        self.prev.setEnabled(False)
        self.next.setEnabled(False)

    def show_details(self, mod):
        answer = QMessageBox.question(
            self, mod["title"],
            mod.get("description", "")[:900] + "\n\n"
            "¿Abrir la ficha original en Modrinth?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            slug = mod.get("slug", "")
            if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", slug):
                QDesktopServices.openUrl(QUrl("https://modrinth.com/mod/" + slug))

    def save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar selección Modrinth", "modrinth-seleccion.json",
            "Proyecto Modrinth (*.json)")
        if not path:
            return
        data = {
            "schema": 1, "source": "modrinth", "name": self.pack_name.text(),
            "minecraft": self.host.version.currentText().strip(),
            "loader": self.host.loader.currentText(),
            "mods": [{"source": "modrinth", "project_id": x["project_id"],
                      "title": x["title"], "slug": x.get("slug", ""),
                      "description": x.get("description", ""), "logo": x.get("logo", ""),
                      "screenshots": [], "categories": x.get("categories", []),
                      "downloads": x.get("downloads", 0)}
                     for x in self.pack.values()]
        }
        try:
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.host.status.setText("Selección pública guardada en " + path)
        except OSError as exc:
            self.host.failure(str(exc))

    def open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir selección Modrinth", "", "Proyecto Modrinth (*.json)")
        if not path:
            return
        try:
            file = Path(path)
            if file.stat().st_size > 2_000_000:
                raise ValueError("El proyecto supera 2 MB.")
            data = json.loads(file.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("source") != "modrinth"
                    or data.get("schema") != 1 or not isinstance(data.get("mods"), list)
                    or len(data["mods"]) > 300):
                raise ValueError("Formato de proyecto incorrecto.")
            entries = {}
            for item in data["mods"]:
                if (not isinstance(item, dict) or item.get("source") != "modrinth"
                        or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(item.get("project_id", "")))
                        or not isinstance(item.get("title"), str)):
                    raise ValueError("La selección contiene mods inválidos.")
                entries[str(item["project_id"])] = {
                    "source": "modrinth", "project_id": str(item["project_id"]),
                    "title": item["title"][:200], "slug": str(item.get("slug", ""))[:100],
                    "description": str(item.get("description", ""))[:2000],
                    "logo": "", "screenshots": [], "downloads": 0,
                    "categories": []
                }
            self.pack = entries
            self.pack_name.setText(str(data.get("name", "Mi modpack"))[:120])
            self.refresh()
            self.host.status.setText("Selección abierta. Se comprobarán los mods al exportar.")
        except (ValueError, OSError, TypeError) as exc:
            self.host.failure("No se pudo abrir la selección: " + str(exc))

    def export_pack(self):
        if self.host.busy or not self.pack:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar pack para Modrinth", self.pack_name.text() + ".mrpack",
            "Modpack Modrinth (*.mrpack)")
        if not path:
            return
        if not path.lower().endswith(".mrpack"):
            path += ".mrpack"
        mc = self.host.version.currentText().strip()
        loader = self.host.loader.currentText()
        name = self.pack_name.text()
        manual = self.loader_version.text().strip()
        mods = list(self.pack.values())
        def task(progress):
            version = manual or resolve_loader_version(mc, loader)
            return export_mrpack(path, name, mc, loader, version, mods, self.catalog, progress)
        def ready(data):
            QMessageBox.information(self, "Paquete preparado",
                f"Exportados {data['mods']} mods, incluyendo dependencias.\n"
                f"{data['path']}\n\nImporta este archivo desde Modrinth App o Prism Launcher.")
        self.host.run_task(task, ready)
