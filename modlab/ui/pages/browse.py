"""Explorar: búsqueda instantánea con filtros en CurseForge o Modrinth."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QVBoxLayout, QWidget

from modlab.sources import LABELS as SOURCE_LABELS
from modlab.ui.labels import category_label
from modlab.ui.pages import plain_page
from modlab.ui.widgets import Badge, CardGrid, EmptyState, SearchBox, Segmented, button, label, tool

PAGE = 50
SORTS = [('downloads', 'Más descargados'), ('popularity', 'Populares'), ('updated', 'Actualizados'),
         ('relevance', 'Relevancia'), ('name', 'Nombre')]


class BrowsePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.source = win.default_source()
        self.categories = {}
        self.index = 0
        self.total = 0
        self.pending = None
        self.dirty = True
        page, v = plain_page()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        top = QHBoxLayout()
        self.sources = Segmented([('curseforge', 'CurseForge'), ('modrinth', 'Modrinth')], self.source)
        self.sources.changed.connect(self.set_source)
        top.addWidget(self.sources)
        self.status = Badge('', 'neutral')
        top.addWidget(self.status)
        top.addStretch()
        self.target = Badge('', 'neutral')
        top.addWidget(self.target)
        v.addLayout(top)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search = SearchBox('Buscar mods: Create, minimapa, muebles, optimización…')
        self.search.search.connect(lambda _: self.run_search(0))
        filters.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.setMinimumWidth(200)
        self.category.addItem('Todas las categorías', None)
        self.category.currentIndexChanged.connect(lambda _: self.run_search(0))
        filters.addWidget(self.category)
        self.sort = QComboBox()
        for key, text in SORTS:
            self.sort.addItem(text, key)
        self.sort.currentIndexChanged.connect(lambda _: self.run_search(0))
        filters.addWidget(self.sort)
        reload = tool('refresh', 'Repetir la búsqueda')
        reload.clicked.connect(lambda: self.run_search(self.index))
        filters.addWidget(reload)
        v.addLayout(filters)

        self.info = label('', 'muted')
        v.addWidget(self.info)
        self.grid = CardGrid(win.images)
        self.grid.toggled.connect(win.toggle_mod)
        self.grid.details.connect(win.open_details)
        v.addWidget(self.grid, 1)

        pages = QHBoxLayout()
        self.prev = button('Anterior', 'chevron_left')
        self.prev.clicked.connect(lambda: self.run_search(max(0, self.index - PAGE)))
        self.next = button('Siguiente', 'chevron_right')
        self.next.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.next.clicked.connect(lambda: self.run_search(self.index + PAGE))
        self.page_label = label('', 'muted')
        pages.addWidget(self.prev)
        pages.addStretch()
        pages.addWidget(self.page_label)
        pages.addStretch()
        pages.addWidget(self.next)
        v.addLayout(pages)

        win.target_changed.connect(self.mark_dirty)
        win.catalogs_changed.connect(self.catalogs_changed)
        self.update_header()

    # Estado ---------------------------------------------------------------------------------
    def catalog(self):
        return self.win.catalogs.get(self.source)

    def update_header(self):
        mc, loader = self.win.target()
        self.target.set(f'Minecraft {mc} · {loader}', 'neutral')
        available = self.catalog().available()
        if self.source == 'curseforge':
            mode = self.win.catalogs.curseforge.connection.mode
            self.status.set({'direct': 'Clave de API', 'gateway': 'Pasarela'}.get(mode, 'Sin conexión'),
                            'success' if available else 'danger')
        else:
            self.status.set('Público', 'success')

    def mark_dirty(self):
        self.dirty = True
        self.update_header()
        if self.isVisible():
            self.run_search(0)

    def catalogs_changed(self):
        self.categories.pop('curseforge', None)
        self.mark_dirty()

    def showEvent(self, event):
        super().showEvent(event)
        if self.dirty:
            self.run_search(0)

    def set_source(self, source, search=True):
        self.source = source
        self.sources.set_current(source)
        self.win.settings['source'] = source
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem('Todas las categorías', None)
        self.category.blockSignals(False)
        self.update_header()
        if search:
            self.run_search(0)

    def apply_theme(self, theme):
        """Temática de Inicio: categoría equivalente o, si no existe en el catálogo, búsqueda."""
        _, _, cf_name, mr_slug, query = theme
        wanted = cf_name if self.source == 'curseforge' else mr_slug
        self.search.setText('' if wanted or cf_name is None else query)
        self.pending = wanted
        self.category.blockSignals(True)
        self.category.setCurrentIndex(0)
        self.category.blockSignals(False)
        self._select_pending()
        self.run_search(0)

    def _select_pending(self):
        if not self.pending:
            return
        for i in range(self.category.count()):
            data = self.category.itemData(i)
            cat = next((c for c in self.categories.get(self.source, []) if c['id'] == data), None)
            if cat and cat['name'].casefold() == str(self.pending).casefold():
                self.category.blockSignals(True)
                self.category.setCurrentIndex(i)
                self.category.blockSignals(False)
                self.pending = None
                return

    def load_categories(self):
        source = self.source
        if source in self.categories or not self.catalog().available():
            return

        def done(rows):
            self.categories[source] = rows
            if source != self.source:
                return
            current = self.category.currentData()
            self.category.blockSignals(True)
            self.category.clear()
            self.category.addItem('Todas las categorías', None)
            for cat in sorted(rows, key=lambda c: category_label(c['name']).casefold()):
                self.category.addItem(category_label(cat['name']), cat['id'])
            index = self.category.findData(current)
            self.category.setCurrentIndex(max(0, index))
            self.category.blockSignals(False)
            if self.pending:
                self._select_pending()
                self.run_search(0)
        self.win.run(lambda p, c: self.catalog().categories(), done, key='categories:' + source, owner=self,
                     visible=False, toast_errors=False)

    # Búsqueda ---------------------------------------------------------------------------------
    def run_search(self, index=0):
        self.dirty = False
        catalog = self.catalog()
        self.update_header()
        if not catalog.available():
            self.grid.show_message(EmptyState(
                'plug', 'CurseForge todavía no está conectado',
                'Define la variable de entorno CURSEFORGE_API_KEY con tu clave autorizada o configura la pasarela '
                'de ModLab en Ajustes. Mientras tanto puedes usar Modrinth.',
                [('Abrir Ajustes', lambda: self.win.navigate('settings'), 'primary', 'settings'),
                 ('Usar Modrinth', lambda: self.set_source('modrinth'), None, 'layers')]))
            self.info.setText('')
            self.page_label.setText('')
            self.prev.setEnabled(False)
            self.next.setEnabled(False)
            return
        self.load_categories()
        if self.pending and self.source in self.categories:
            self._select_pending()
        query = self.search.text().strip()
        category = self.category.currentData()
        sort = self.sort.currentData()
        mc, loader = self.win.target()
        self.grid.show_loading(8)
        self.info.setText(f'Buscando en {SOURCE_LABELS[self.source]}…')
        self.prev.setEnabled(False)
        self.next.setEnabled(False)

        def done(result):
            mods = result['mods']
            self.index = index
            self.total = result['pagination'].get('totalCount', len(mods))
            if not mods:
                self.grid.show_message(EmptyState('search', 'No hay mods para esta búsqueda',
                                                  f'Nada coincide en Minecraft {mc} · {loader}. Cambia los filtros, '
                                                  'la versión o prueba el otro catálogo.'))
            else:
                self.grid.show_mods(mods, self.win.state_of)
            shown = f'{self.total:,}'.replace(',', '.')
            self.info.setText(f'{shown} resultados en {SOURCE_LABELS[self.source]}' + (f' para «{query}»' if query else ''))
            pages = max(1, -(-self.total // PAGE))
            self.page_label.setText(f'Página {index // PAGE + 1} de {pages:,}'.replace(',', '.'))
            self.prev.setEnabled(index > 0)
            limit = 10000 if self.source == 'curseforge' else self.total
            self.next.setEnabled(index + PAGE < min(limit, self.total))

        def failed(message):
            self.grid.show_message(EmptyState('alert', 'No se pudo completar la búsqueda', message,
                                              [('Reintentar', lambda: self.run_search(index), 'primary', 'refresh')],
                                              tone='danger'))
            self.info.setText('')
        self.win.run(lambda p, c: catalog.search(query, category, index, PAGE, sort, mc, loader), done, failed,
                     key='browse', owner=self, label='Buscando mods', toast_errors=False)

    def refresh_states(self):
        self.grid.refresh_states(self.win.state_of)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()
