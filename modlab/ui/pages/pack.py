"""Mi modpack: selección, comprobación, exportación (.zip / .mrpack) y descarga de archivos."""
from pathlib import Path
import html

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLineEdit, QMenu,
                               QMessageBox, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from modlab import downloads as downloader
from modlab.modpack import audit_pack, build_mrpack, build_pack, resolve_loader_version
from modlab.project import Pack
from modlab.sources import LABELS as SOURCE_LABELS
from modlab.ui.pages import plain_page
from modlab.ui.widgets import Badge, EmptyState, Segmented, button, card, clear_layout, label, tool

STATUS = {'release': 'Estable', 'beta': 'Beta', 'alpha': 'Alfa'}


class PackPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.filter = 'all'
        self.report = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.empty = EmptyState('package', 'Tu modpack está vacío',
                                'Añade mods desde Explorar, desde la ficha de un mod o con una propuesta de la IA. '
                                'También puedes abrir un proyecto guardado.',
                                [('Explorar mods', lambda: win.navigate('browse'), 'primary', 'compass'),
                                 ('Crear con IA', lambda: win.navigate('ai'), None, 'sparkles'),
                                 ('Abrir proyecto', self.open_project, None, 'folder')])
        self.stack.addWidget(self.empty)
        page, v = plain_page()
        self.stack.addWidget(page)

        info, info_layout = card(margins=(18, 16, 18, 16), spacing=12)
        fields = QHBoxLayout()
        fields.setSpacing(10)
        self.name = QLineEdit(win.pack.name)
        self.name.setPlaceholderText('Nombre del modpack')
        self.name.setStyleSheet('font-size: 17px; font-weight: 700;')
        self.name.textChanged.connect(lambda t: setattr(win.pack, 'name', t))
        fields.addWidget(self.name, 3)
        self.version = QLineEdit(win.pack.version)
        self.version.setPlaceholderText('Versión del pack')
        self.version.setToolTip('Versión del modpack (aparece en el manifest).')
        self.version.textChanged.connect(lambda t: setattr(win.pack, 'version', t))
        fields.addWidget(self.version, 1)
        self.author = QLineEdit(win.pack.author or win.settings['author'])
        self.author.setPlaceholderText('Autor')
        self.author.textChanged.connect(self._author)
        fields.addWidget(self.author, 1)
        self.loader_build = QLineEdit()
        self.loader_build.setPlaceholderText('Cargador: automático')
        self.loader_build.setToolTip('Versión exacta del cargador. Vacío = consultar la versión recomendada oficial.')
        fields.addWidget(self.loader_build, 1)
        info_layout.addLayout(fields)
        self.summary = label('', 'muted')
        info_layout.addWidget(self.summary)
        v.addWidget(info)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.check_button = button('Comprobar pack', 'shield')
        self.check_button.setToolTip('Fija archivos compatibles y revisa dependencias e incompatibilidades declaradas.')
        self.check_button.clicked.connect(self.check)
        bar.addWidget(self.check_button)
        self.export_button = button('Exportar', 'upload', 'primary')
        menu = QMenu(self.export_button)
        menu.addAction('Modpack de CurseForge (.zip)', lambda: self.export('curseforge'))
        menu.addAction('Modpack de Modrinth (.mrpack)', lambda: self.export('modrinth'))
        self.export_button.setMenu(menu)
        bar.addWidget(self.export_button)
        self.download_button = button('Descargar mods', 'download')
        self.download_button.setToolTip('Descarga los JAR permitidos en una carpeta (por ejemplo, la carpeta mods de una instancia).')
        self.download_button.clicked.connect(self.download)
        bar.addWidget(self.download_button)
        bar.addStretch()
        for text, icon_name, slot in (('Abrir', 'folder', self.open_project), ('Guardar', 'save', self.save_project)):
            item = button(text, icon_name, 'ghost')
            item.clicked.connect(slot)
            bar.addWidget(item)
        clear = button('Vaciar', 'trash', 'danger')
        clear.clicked.connect(self.clear)
        bar.addWidget(clear)
        v.addLayout(bar)

        filters = QHBoxLayout()
        self.filters = Segmented([('all', 'Todos'), ('curseforge', 'CurseForge'), ('modrinth', 'Modrinth')])
        self.filters.changed.connect(self._set_filter)
        filters.addWidget(self.filters)
        filters.addStretch()
        remove = tool('trash', 'Quitar los seleccionados (Supr)')
        remove.clicked.connect(self.remove_selected)
        filters.addWidget(remove)
        v.addLayout(filters)

        self.table = QTreeWidget()
        self.table.setColumnCount(4)
        self.table.setHeaderLabels(['Mod', 'Catálogo', 'Archivo fijado', 'Estado'])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setIconSize(QSize(28, 28))
        self.table.setUniformRowHeights(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.table.itemDoubleClicked.connect(lambda item, _: self.win.open_details(self.win.pack.mods[item.data(0, Qt.ItemDataRole.UserRole)]))
        header = self.table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        QShortcut(QKeySequence.StandardKey.Delete, self.table, self.remove_selected)
        v.addWidget(self.table, 3)

        self.report_card, self.report_layout = card(spacing=8)
        self.report_card.hide()
        v.addWidget(self.report_card, 2)

        win.pack_changed.connect(self.refresh)
        win.target_changed.connect(self.target_changed)
        self.refresh()

    # Datos ---------------------------------------------------------------------------------------
    def _author(self, text):
        self.win.pack.author = text
        self.win.settings['author'] = text

    def _set_filter(self, key):
        self.filter = key
        self.refresh()

    def target_changed(self):
        self.report = None
        self.report_card.hide()
        self.refresh()

    def refresh(self):
        pack = self.win.pack
        self.stack.setCurrentIndex(1 if len(pack) else 0)
        if self.name.text() != pack.name:
            self.name.setText(pack.name)
        if self.version.text() != pack.version:
            self.version.setText(pack.version)
        if pack.author and self.author.text() != pack.author:
            self.author.setText(pack.author)
        counts = {s: len(pack.by_source(s)) for s in ('curseforge', 'modrinth')}
        self.filters.set_text('all', f'Todos  {len(pack)}')
        self.filters.set_text('curseforge', f"CurseForge  {counts['curseforge']}")
        self.filters.set_text('modrinth', f"Modrinth  {counts['modrinth']}")
        pinned = sum(1 for m in pack.values() if m.get('file_id'))
        self.summary.setText(f'{len(pack)} mods · Minecraft {pack.minecraft} · {pack.loader} · {pinned} con archivo fijado. '
                             'Las dependencias obligatorias se añaden al exportar.')
        selected = {i.data(0, Qt.ItemDataRole.UserRole) for i in self.table.selectedItems()}
        self.table.clear()
        for mod in pack.values():
            if self.filter != 'all' and mod['source'] != self.filter:
                continue
            status = ('Pendiente de comprobar' if not mod.get('file_id') else
                      STATUS.get(mod.get('release'), 'Fijado'))
            if mod.get('allow_distribution') is False:
                status += ' · descarga manual'
            item = QTreeWidgetItem([mod['title'], SOURCE_LABELS.get(mod['source'], mod['source']),
                                    mod.get('version_number') or '—', status])
            item.setData(0, Qt.ItemDataRole.UserRole, mod['key'])
            item.setToolTip(0, mod.get('reason') or mod.get('description', ''))
            self.table.addTopLevelItem(item)
            item.setSelected(mod['key'] in selected)
            if mod.get('logo'):
                self.win.images.fetch(mod['logo'], QSize(28, 28), lambda pixmap, i=item: self._set_icon(i, pixmap))
        self.update_buttons()

    def update_buttons(self):
        busy = self.win.runner.busy('pack')
        for widget in (self.check_button, self.export_button, self.download_button):
            widget.setEnabled(bool(len(self.win.pack)) and not busy)

    def _set_icon(self, item, pixmap):
        try:
            item.setIcon(0, QIcon(pixmap))
        except RuntimeError:
            pass

    def selected_keys(self):
        return [i.data(0, Qt.ItemDataRole.UserRole) for i in self.table.selectedItems()]

    def remove_selected(self):
        keys = self.selected_keys()
        for key in keys:
            self.win.pack.remove(key)
        if keys:
            self.win.pack_changed.emit()
            self.win.toast(f'{len(keys)} mod(s) quitados del pack', tone='info', timeout=2500)

    def context_menu(self, point):
        item = self.table.itemAt(point)
        if not item:
            return
        mod = self.win.pack.mods.get(item.data(0, Qt.ItemDataRole.UserRole))
        if not mod:
            return
        menu = QMenu(self)
        menu.addAction('Ver ficha', lambda: self.win.open_details(mod))
        catalog = self.win.catalogs.get(mod['source'])
        menu.addAction('Abrir en la web', lambda: QDesktopServices.openUrl(QUrl(catalog.file_page(mod))))
        menu.addSeparator()
        menu.addAction('Quitar del pack', self.remove_selected)
        menu.exec(self.table.viewport().mapToGlobal(point))

    def clear(self):
        if not len(self.win.pack):
            return
        answer = QMessageBox.question(self, 'Vaciar el modpack', f'¿Quitar los {len(self.win.pack)} mods del pack?')
        if answer == QMessageBox.StandardButton.Yes:
            self.win.pack.clear()
            self.report_card.hide()
            self.win.pack_changed.emit()

    # Proyecto ------------------------------------------------------------------------------------
    def save_project(self):
        start = str(Path(self.win.settings['last_folder'] or Path.home()) / (self.win.pack.name or 'modpack'))
        path, _ = QFileDialog.getSaveFileName(self, 'Guardar proyecto', start + '.modlab.json', 'Proyecto ModLab (*.json)')
        if not path:
            return
        try:
            self.win.pack.save(path)
        except OSError as exc:
            self.win.toast('No se pudo guardar el proyecto', type(exc).__name__, 'error')
            return
        self.win.settings['last_folder'] = str(Path(path).parent)
        self.win.toast('Proyecto guardado', Path(path).name, 'success')

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir proyecto', self.win.settings['last_folder'],
                                              'Proyecto ModLab (*.json)')
        if not path:
            return
        try:
            pack = Pack.load(path)
        except ValueError as exc:
            self.win.toast('No se pudo abrir el proyecto', str(exc), 'error')
            return
        self.win.settings['last_folder'] = str(Path(path).parent)
        self.win.load_pack(pack)
        self.win.toast('Proyecto abierto', f'{len(pack)} mods · los archivos se verifican al comprobar o exportar.', 'success')

    # Comprobación -------------------------------------------------------------------------------
    def check(self):
        pack = self.win.pack
        mods = pack.values()
        mc, loader = pack.minecraft, pack.loader

        def done(report):
            self.report = report
            self.show_report(report)
            problems = len(report['missing']) + len(report['conflicts'])
            self.win.toast('Comprobación completada' if not problems else 'La comprobación encontró problemas',
                           f"{report['total']} mods en total · {len(report['dependencies'])} dependencias nuevas",
                           'success' if not problems else 'warning')
        self.win.run(lambda progress, check: audit_pack(mods, mc, loader, progress, catalogs=self.win.catalogs, check=check),
                     done, key='pack', label='Comprobando el pack', owner=self)
        self.update_buttons()

    def show_report(self, report):
        clear_layout(self.report_layout)
        self.report_card.show()
        head = QHBoxLayout()
        head.addWidget(label('Resultado de la comprobación', 'h3'))
        head.addStretch()
        head.addWidget(Badge(f"{report['total']} mods en total", 'neutral'))
        head.addWidget(Badge(f"{len(report['dependencies'])} dependencias", 'neutral'))
        head.addWidget(Badge(f"{len(report['missing'])} sin archivo", 'danger' if report['missing'] else 'success'))
        head.addWidget(Badge(f"{len(report['conflicts'])} incompatibilidades", 'danger' if report['conflicts'] else 'success'))
        close = tool('x', 'Ocultar')
        close.clicked.connect(self.report_card.hide)
        head.addWidget(close)
        self.report_layout.addLayout(head)
        lines = []
        for a, b in report['conflicts']:
            lines.append(f'<span style="color:#ff5c6c">✖ Incompatibilidad declarada: {_esc(a)} ↔ {_esc(b)}</span>')
        for m in report['missing']:
            lines.append(f"<span style=\"color:#ff5c6c\">✖ {_esc(m['title'])}: {_esc(m['reason'])}</span>")
        for d in report['dependencies'][:60]:
            lines.append(f"<span style=\"color:#b4bcd0\">+ {_esc(d['title'])}</span> "
                         f"<span style=\"color:#7f89a3\">({SOURCE_LABELS.get(d.get('source'), '')} · {_esc(d.get('version', ''))})</span>")
        if len(report['dependencies']) > 60:
            lines.append(f"… y {len(report['dependencies']) - 60} dependencias más.")
        if not lines:
            lines.append('<span style="color:#3ecf8e">✔ Todo correcto: cada mod tiene un archivo compatible y no hay incompatibilidades declaradas.</span>')
        body = label('<br>'.join(lines), wrap=True, rich=True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.report_layout.addWidget(body)
        self.report_layout.addWidget(label('Una comprobación correcta no garantiza que Minecraft arranque: los conflictos no '
                                           'declarados solo se detectan probando el juego.', 'muted', wrap=True))

    # Exportación --------------------------------------------------------------------------------
    def _subset(self, source):
        pack = self.win.pack
        mods = pack.by_source(source)
        other = [m['title'] for m in pack.values() if m['source'] != source]
        name = SOURCE_LABELS[source]
        if not mods:
            QMessageBox.information(self, 'Nada que exportar', f'El pack no contiene mods de {name}.')
            return None
        if other:
            answer = QMessageBox.question(
                self, 'Mods de otro catálogo',
                f'El formato de {name} solo puede referenciar mods de {name}. Estos {len(other)} mods no se incluirán:\n\n'
                + '\n'.join('• ' + t for t in other[:12]) + ('\n…' if len(other) > 12 else '') +
                f'\n\n¿Exportar solo los {len(mods)} mods de {name}?')
            if answer != QMessageBox.StandardButton.Yes:
                return None
        return mods

    def export(self, source):
        pack = self.win.pack
        mc, loader = pack.minecraft, pack.loader
        if source == 'curseforge' and loader == 'Quilt':
            QMessageBox.warning(self, 'Cargador no admitido', 'Los modpacks de CurseForge solo admiten Forge, NeoForge y Fabric.')
            return
        mods = self._subset(source)
        if mods is None:
            return
        extension = '.zip' if source == 'curseforge' else '.mrpack'
        kind = 'Modpack de CurseForge (*.zip)' if source == 'curseforge' else 'Modpack de Modrinth (*.mrpack)'
        start = str(Path(self.win.settings['last_folder'] or Path.home()) / ((pack.name or 'modpack') + extension))
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar modpack', start, kind)
        if not path:
            return
        if not path.lower().endswith(extension):
            path += extension
        self.win.settings['last_folder'] = str(Path(path).parent)
        name, version, author = pack.name, pack.version, pack.author
        build = self.loader_build.text().strip()
        catalog = self.win.catalogs.get(source)

        def work(progress, check):
            progress('Consultando la versión oficial del cargador…')
            loader_version = build or resolve_loader_version(mc, loader)
            check()
            if source == 'curseforge':
                return build_pack(path, name, mc, loader, loader_version, mods, progress, catalog, author, version, check)
            return build_mrpack(path, name, mc, loader, loader_version, mods, progress, catalog, version, pack.description, check)

        def done(result):
            how = ('CurseForge → Minecraft → Crear perfil personalizado → Importar.' if source == 'curseforge' else
                   'Modrinth App, Prism Launcher u otro lanzador compatible → Importar .mrpack.')
            box = QMessageBox(self)
            box.setWindowTitle('Modpack exportado')
            box.setText(f"{result['mods']} mods (con dependencias) exportados a:\n{result['path']}\n\nPara usarlo: {how}")
            folder = box.addButton('Abrir carpeta', QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is folder:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(result['path']).parent)))
        self.win.run(work, done, key='pack', label='Exportando modpack', owner=self)
        self.update_buttons()

    def download(self):
        pack = self.win.pack
        folder = QFileDialog.getExistingDirectory(self, 'Carpeta de destino de los mods',
                                                  self.win.settings['last_folder'] or str(Path.home()))
        if not folder:
            return
        self.win.settings['last_folder'] = folder
        mods = pack.values()
        mc, loader = pack.minecraft, pack.loader
        catalogs = self.win.catalogs

        def work(progress, check):
            resolved, missing = [], []
            for source in ('curseforge', 'modrinth'):
                group = [m for m in mods if m['source'] == source]
                if group:
                    report = catalogs.get(source).resolve_report(group, mc, loader, progress, check)
                    resolved += report['mods']
                    missing += report['missing']
            progress('Preparando descargas autorizadas…', 0.0)
            items, manual = downloader.plan(resolved, catalogs, check)
            result = downloader.download_all(items, folder, lambda f, m: progress(m, f), check)
            return dict(result, manual=manual, missing=missing, folder=folder)

        def done(result):
            lines = [f"Descargados: {len(result['downloaded'])}", f"Ya estaban: {len(result['existing'])}"]
            if result['manual']:
                lines.append(f"\nDescarga manual ({len(result['manual'])}) — el autor no permite descargas de terceros:")
                lines += [f"• {m['title']}: {m['page']}" for m in result['manual'][:15]]
            if result['failed']:
                lines.append(f"\nFallidos ({len(result['failed'])}):")
                lines += [f"• {m['title']}: {m['reason']}" for m in result['failed'][:15]]
            if result['missing']:
                lines.append(f"\nSin archivo compatible ({len(result['missing'])}):")
                lines += [f"• {m['title']}" for m in result['missing'][:15]]
            box = QMessageBox(self)
            box.setWindowTitle('Descarga terminada')
            box.setText('\n'.join(lines))
            folder_button = box.addButton('Abrir carpeta', QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() is folder_button:
                QDesktopServices.openUrl(QUrl.fromLocalFile(result['folder']))
        self.win.run(work, done, key='pack', label='Descargando mods', owner=self)
        self.update_buttons()


def _esc(text):
    return html.escape(str(text))
