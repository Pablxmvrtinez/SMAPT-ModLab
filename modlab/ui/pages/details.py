"""Ficha completa de un mod: descripción, versiones, dependencias y galería."""
import re

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QGridLayout, QHBoxLayout, QHeaderView,
                               QScrollArea, QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout, QWidget, QFrame)

from modlab.sources import LABELS as SOURCE_LABELS
from modlab.ui import icons
from modlab.ui.labels import category_label
from modlab.ui.theme import COLORS
from modlab.ui.widgets import (Badge, Cover, EmptyState, Logo, Spinner, button, card, clear_layout, downloads, label,
                               restyle, source_badge)

RELEASES = {'release': ('Estable', 'success'), 'beta': ('Beta', 'warning'), 'alpha': ('Alfa', 'danger')}
DEPENDENCY_TYPES = {'required': ('Obligatoria', 'danger'), 'optional': ('Opcional', 'neutral'),
                    'incompatible': ('Incompatible', 'warning'), 'embedded': ('Incluida', 'neutral'),
                    'include': ('Incluida', 'neutral'), 'tool': ('Herramienta', 'neutral')}


def safe_html(text):
    """Quita scripts, estilos, iframes, formularios, manejadores on*, comentarios e imágenes remotas."""
    text = re.sub(r'(?s)<!--.*?-->', '', text or '')
    text = re.sub(r'(?is)<(script|style|iframe|object|embed|form|svg)\b.*?</\1\s*>', '', text)
    text = re.sub(r'(?is)</?(script|style|iframe|object|embed|form|input|button|img|svg|link|meta)\b[^>]*>', '', text)
    text = re.sub(r'(?i)\s(on\w+|style)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', text)
    for _ in range(3):
        # Al quitar imágenes quedan contenedores vacíos que dejarían huecos en la ficha.
        text = re.sub(r'(?is)<(p|div|center|a|span|li|ul|ol|h\d|strong|b|em)\b[^>]*>\s*</\1\s*>', '', text)
    return text


def safe_markdown(text):
    text = re.sub(r'\[?!\[[^\]]*\]\([^)]*\)(\]\([^)]*\))?', '', text or '')
    text = safe_html(text)
    # Bloques HTML habituales en Modrinth → Markdown, para que el analizador no los pegue al párrafo anterior.
    text = re.sub(r'(?is)<h([1-6])\b[^>]*>(.*?)</h\1\s*>', lambda m: '\n\n' + '#' * int(m.group(1)) + ' ' + m.group(2).strip() + '\n\n', text)
    text = re.sub(r'(?i)<br\s*/?>', '  \n', text)
    text = re.sub(r'(?i)</?(p|center|div)\b[^>]*>', '\n\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


class SafeBrowser(QTextBrowser):
    """No carga recursos externos ni locales; solo abre enlaces http(s) en el navegador."""

    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open)
        self.document().setDefaultStyleSheet(f"a {{ color: {COLORS['accent_hover']}; }} h1, h2, h3 {{ color: #ffffff; }}")

    def loadResource(self, kind, url):
        return None

    @staticmethod
    def open(url):
        if url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)


def loading(text='Cargando…'):
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.addStretch()
    row.addWidget(Spinner(20))
    row.addWidget(label(text, 'muted'))
    row.addStretch()
    return holder


class DetailsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.mod = None
        self.pinned = None
        self.loaded = set()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.area)
        self.body = None

    # Construcción ------------------------------------------------------------------------------
    def show_mod(self, mod):
        self.mod = dict(mod)
        self.pinned = None
        self.loaded = set()
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(28, 18, 28, 28)
        v.setSpacing(16)
        top = QHBoxLayout()
        back = button('Volver', 'back', 'ghost')
        back.clicked.connect(self.win.back)
        top.addWidget(back)
        top.addStretch()
        v.addLayout(top)

        banner_url = next(iter(mod.get('screenshots') or []), '') or mod.get('logo', '')
        banner = Cover(mod['title'], banner_url, self.win.images, height=230, radius=16, top_only=False, width=1100)
        v.addWidget(banner)

        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(Logo(mod['title'], mod.get('logo', ''), self.win.images, 76), 0, Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(6)
        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(source_badge(mod['source']))
        for cat in mod.get('categories', [])[:4]:
            badges.addWidget(label(category_label(cat['name']), 'tag'))
        badges.addStretch()
        info.addLayout(badges)
        info.addWidget(label(mod['title'], 'h1', wrap=True))
        authors = ', '.join(mod.get('authors', [])[:3])
        meta = ' · '.join(x for x in ((f'por {authors}' if authors else ''), f"↓ {downloads(mod.get('downloads'))} descargas",
                                       (f"actualizado {mod['updated']}" if mod.get('updated') else '')) if x)
        info.addWidget(label(meta, 'muted', wrap=True))
        if mod.get('description'):
            info.addWidget(label(mod['description'], 'text2', wrap=True))
        head.addLayout(info, 1)
        actions = QVBoxLayout()
        actions.setSpacing(8)
        self.toggle = button('')
        self.toggle.setMinimumWidth(190)
        self.toggle.clicked.connect(lambda: self.win.toggle_mod(self.mod))
        actions.addWidget(self.toggle)
        web = button(f"Abrir en {SOURCE_LABELS[mod['source']]}", 'external')
        web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(mod.get('url') or self.win.catalogs.get(mod['source']).file_page(mod))))
        actions.addWidget(web)
        actions.addStretch()
        head.addLayout(actions)
        v.addLayout(head)
        if mod.get('allow_distribution') is False:
            v.addWidget(Badge('El autor no permite descargas desde aplicaciones de terceros: se exporta por referencia '
                              'y la descarga directa se hace desde CurseForge.', 'warning'))
        if mod.get('reason'):
            box, box_layout = card()
            box_layout.addWidget(label('POR QUÉ LO PROPONE LA IA', 'eyebrow'))
            box_layout.addWidget(label(mod['reason'], wrap=True))
            if mod.get('caveat'):
                box_layout.addWidget(label('Límite: ' + mod['caveat'], 'muted', wrap=True))
            v.addWidget(box)

        self.tabs = QTabWidget()
        self.description = SafeBrowser()
        self.description.setMinimumHeight(420)
        self.versions_tab = QWidget()
        self.deps_tab = QWidget()
        self.gallery_tab = QWidget()
        for widget in (self.versions_tab, self.deps_tab, self.gallery_tab):
            tab_layout = QVBoxLayout(widget)
            tab_layout.setContentsMargins(0, 12, 0, 0)
            tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tabs.addTab(self.description, 'Descripción')
        self.tabs.addTab(self.versions_tab, 'Versiones')
        self.tabs.addTab(self.deps_tab, 'Dependencias')
        shots = mod.get('screenshots') or []
        self.tabs.addTab(self.gallery_tab, f'Galería ({len(shots)})')
        self.tabs.currentChanged.connect(self.load_tab)
        v.addWidget(self.tabs, 1)
        self.area.setWidget(body)
        self.body = body
        self.refresh_state()
        self.load_tab(0)

    def refresh_state(self):
        if not self.mod or not self.body:
            return
        state = self.win.state_of(self.mod)
        texts = {'add': ('Añadir al pack', 'plus', 'primary'), 'busy': ('Añadiendo…', 'clock', None),
                 'in': ('Quitar del pack', 'x', 'inPack')}
        text, icon_name, kind = texts[state]
        self.toggle.setText(text)
        self.toggle.setIcon(icons.icon(icon_name, '#ffffff' if kind == 'primary' else '#ffb4c6', 16))
        self.toggle.setEnabled(state != 'busy')
        restyle(self.toggle, kind or '')

    # Pestañas ---------------------------------------------------------------------------------
    def load_tab(self, index):
        if index in self.loaded or not self.mod:
            return
        self.loaded.add(index)
        [self.load_description, self.load_versions, self.load_dependencies, self.load_gallery][index]()

    def load_description(self):
        mod = self.mod
        catalog = self.win.catalogs.get(mod['source'])
        self.description.setPlainText('Cargando descripción…')

        def done(result):
            if result['format'] == 'markdown':
                self.description.setMarkdown(safe_markdown(result['text']))
            else:
                self.description.setHtml(safe_html(result['text']))
        self.win.run(lambda p, c: catalog.description(mod['project_id']), done,
                     lambda message: self.description.setPlainText(message), key='details:description', owner=self.description,
                     visible=False, toast_errors=False)

    def load_versions(self):
        layout = self.versions_tab.layout()
        clear_layout(layout)
        mc, loader = self.win.target()
        bar = QHBoxLayout()
        self.only_compatible = QCheckBox(f'Solo compatibles con {mc} · {loader}')
        self.only_compatible.setChecked(True)
        self.only_compatible.toggled.connect(lambda _: self._fetch_versions())
        bar.addWidget(self.only_compatible)
        bar.addStretch()
        self.use_version = button('Usar esta versión en el pack', 'check', 'primary')
        self.use_version.setEnabled(False)
        self.use_version.clicked.connect(self._use_selected)
        bar.addWidget(self.use_version)
        layout.addLayout(bar)
        self.versions_stack = QStackedWidget()
        self.versions_table = QTableWidget(0, 5)
        self.versions_table.setHorizontalHeaderLabels(['Versión', 'Canal', 'Fecha', 'Minecraft', 'Cargadores'])
        header = self.versions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.versions_table.verticalHeader().hide()
        self.versions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.versions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.versions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.versions_table.setAlternatingRowColors(True)
        self.versions_table.setMinimumHeight(380)
        self.versions_table.itemSelectionChanged.connect(self._selection_changed)
        self.versions_stack.addWidget(self.versions_table)
        layout.addWidget(self.versions_stack, 1)
        self._fetch_versions()

    def _fetch_versions(self):
        mod = self.mod
        catalog = self.win.catalogs.get(mod['source'])
        mc, loader = self.win.target() if self.only_compatible.isChecked() else ('', '')
        while self.versions_stack.count() > 1:
            self.versions_stack.removeWidget(self.versions_stack.widget(1))
        spinner = loading('Consultando versiones…')
        self.versions_stack.addWidget(spinner)
        self.versions_stack.setCurrentWidget(spinner)
        self.use_version.setEnabled(False)

        def done(result):
            files = result['files']
            table = self.versions_table
            table.setRowCount(len(files))
            self.files = files
            for row, file in enumerate(files):
                channel, _ = RELEASES.get(file['release'], (file['release'], 'neutral'))
                values = [file['name'], channel, file['date'], ', '.join(file['game_versions'][:4]) +
                          ('…' if len(file['game_versions']) > 4 else ''), ', '.join(file['loaders'])]
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(value))
            if files:
                self.versions_stack.setCurrentWidget(table)
            else:
                empty = EmptyState('layers', 'Sin versiones', 'No hay archivos publicados para esta combinación.')
                self.versions_stack.addWidget(empty)
                self.versions_stack.setCurrentWidget(empty)

        def failed(message):
            error = EmptyState('alert', 'No se pudieron consultar las versiones', message, tone='danger')
            self.versions_stack.addWidget(error)
            self.versions_stack.setCurrentWidget(error)
        self.win.run(lambda p, c: catalog.versions(mod['project_id'], mc, loader, 0, 50), done, failed,
                     key='details:versions', owner=self.versions_table, visible=False, toast_errors=False)

    def _selection_changed(self):
        rows = self.versions_table.selectionModel().selectedRows()
        mc, loader = self.win.target()
        if not rows:
            self.use_version.setEnabled(False)
            return
        file = self.files[rows[0].row()]
        compatible = mc in file['game_versions'] and loader in file['loaders']
        self.use_version.setEnabled(compatible)
        self.use_version.setToolTip('' if compatible else f'Esta versión no es compatible con {mc} · {loader}.')

    def _use_selected(self):
        rows = self.versions_table.selectionModel().selectedRows()
        if rows:
            self.win.add_with_file(self.mod, self.files[rows[0].row()]['id'])

    def load_dependencies(self):
        layout = self.deps_tab.layout()
        clear_layout(layout)
        layout.addWidget(loading('Comprobando el archivo compatible y sus dependencias…'))
        mod = self.mod
        catalog = self.win.catalogs.get(mod['source'])
        mc, loader = self.win.target()
        allow = self.win.settings['allow_unstable']

        def work(progress, check):
            pinned, failures = catalog.pin_many([mod], mc, loader, allow_unstable=allow)
            if failures:
                raise ValueError(failures[0]['reason'])
            deps = [d for d in pinned[0]['file']['dependencies'] if d.get('project_id')]
            check()
            info = {m['project_id']: m for m in catalog.mods([d['project_id'] for d in deps])} if deps else {}
            return pinned[0], deps, info

        def done(result):
            pinned, deps, info = result
            clear_layout(layout)
            layout.addWidget(label(f"Archivo compatible: {pinned['version_number']} · "
                                   f"{RELEASES.get(pinned.get('release'), ('',))[0]}", 'text2'))
            if not deps:
                layout.addWidget(EmptyState('check', 'Sin dependencias declaradas',
                                            'El autor no declara dependencias para este archivo.'))
                return
            order = ['required', 'incompatible', 'optional', 'embedded', 'include', 'tool']
            for dep in sorted(deps, key=lambda d: order.index(d['type']) if d['type'] in order else 9):
                row_card, row = card(margins=(12, 10, 12, 10), horizontal=True)
                other = info.get(dep['project_id'])
                title = other['title'] if other else str(dep['project_id'])
                row.addWidget(Logo(title, other.get('logo', '') if other else '', self.win.images, 36))
                text = QVBoxLayout()
                text.setSpacing(0)
                text.addWidget(label(title, 'h3'))
                if other:
                    text.addWidget(label(other.get('description', '')[:140], 'muted'))
                row.addLayout(text, 1)
                kind, tone = DEPENDENCY_TYPES.get(dep['type'], (dep['type'], 'neutral'))
                row.addWidget(Badge(kind, tone))
                if other and dep['type'] in ('required', 'optional'):
                    state = self.win.state_of(other)
                    add = button('En el pack' if state == 'in' else 'Añadir', 'check' if state == 'in' else 'plus')
                    add.setEnabled(state == 'add')
                    add.clicked.connect(lambda _=False, m=other, b=add: (self.win.toggle_mod(m), b.setEnabled(False)))
                    row.addWidget(add)
                if other:
                    see = button('Ver', 'forward', 'ghost')
                    see.clicked.connect(lambda _=False, m=other: self.win.open_details(m))
                    row.addWidget(see)
                layout.addWidget(row_card)
            layout.addWidget(label('Las dependencias obligatorias se añaden automáticamente al exportar. '
                                   'Las incompatibilidades declaradas bloquean la exportación.', 'muted', wrap=True))
            layout.addStretch()

        def failed(message):
            clear_layout(layout)
            layout.addWidget(EmptyState('alert', 'No hay un archivo compatible', message, tone='warning'))
        self.win.run(work, done, failed, key='details:deps', owner=self.deps_tab, visible=False, toast_errors=False)

    def load_gallery(self):
        layout = self.gallery_tab.layout()
        clear_layout(layout)
        shots = [u for u in self.mod.get('screenshots') or [] if u]
        if not shots:
            layout.addWidget(EmptyState('image', 'Sin imágenes', 'El autor no ha publicado capturas.'))
            return
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, url in enumerate(shots[:24]):
            thumb = Cover(self.mod['title'], url, self.win.images, height=170, radius=12, top_only=False, width=360)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.mousePressEvent = lambda e, u=url: self.open_image(u)
            grid.addWidget(thumb, i // 3, i % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid)
        layout.addStretch()

    def open_image(self, url):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.mod['title'])
        dialog.resize(1100, 680)
        v = QVBoxLayout(dialog)
        v.setContentsMargins(12, 12, 12, 12)
        cover = Cover(self.mod['title'], '', None, height=620, radius=12, top_only=False)
        self.win.images.fetch(url, QSize(1100, 620), cover.loaded)
        v.addWidget(cover)
        dialog.exec()
