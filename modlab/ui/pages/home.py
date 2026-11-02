"""Inicio: portada, estado general, temáticas y mods populares para la versión elegida."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from modlab.ui import icons
from modlab.ui.labels import THEMES
from modlab.ui.pages import scroll_page
from modlab.ui.theme import COLORS
from modlab.ui.widgets import (Artwork, EmptyState, ModCard, SkeletonCard, StatTile, button, card, clear_layout,
                               label)
from modlab.sources import LABELS as SOURCE_LABELS


class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.loaded_for = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = scroll_page()
        outer.addWidget(area)

        hero, row = card('hero', (32, 28, 20, 20), 20, horizontal=True)
        text = QVBoxLayout()
        text.setSpacing(10)
        text.addWidget(label('MODPACKS DE MINECRAFT', 'eyebrow'))
        text.addWidget(label('Crea un modpack\na tu manera.', 'heroTitle'))
        text.addWidget(label('Busca en CurseForge y Modrinth, comprueba dependencias y exporta packs listos para '
                             'importar. O describe cómo quieres jugar y deja que la IA local proponga una selección.',
                             'text2', wrap=True))
        text.addSpacing(6)
        actions = QHBoxLayout()
        create = button('Crear con IA', 'sparkles', 'primary')
        create.clicked.connect(lambda: win.navigate('ai'))
        explore = button('Explorar mods', 'compass')
        explore.clicked.connect(lambda: win.navigate('browse'))
        actions.addWidget(create)
        actions.addWidget(explore)
        actions.addStretch()
        text.addLayout(actions)
        text.addStretch()
        row.addLayout(text, 5)
        art = Artwork()
        art.setMinimumSize(300, 230)
        row.addWidget(art, 4)
        v.addWidget(hero)

        stats = QGridLayout()
        stats.setSpacing(14)
        self.pack_tile = StatTile('package', 'Tu modpack', '0 mods')
        self.cf_tile = StatTile('plug', 'CurseForge', '…', accent=COLORS['curseforge'])
        self.mr_tile = StatTile('layers', 'Modrinth', 'Disponible', 'Catálogo público', accent=COLORS['modrinth'])
        self.pc_tile = StatTile('cpu', 'Tu equipo', '…', accent=COLORS['violet'])
        for i, tile in enumerate((self.pack_tile, self.cf_tile, self.mr_tile, self.pc_tile)):
            stats.addWidget(tile, 0, i)
        self.pack_tile.mousePressEvent = lambda e: win.navigate('pack')
        self.cf_tile.mousePressEvent = lambda e: win.navigate('settings')
        self.pc_tile.mousePressEvent = lambda e: win.navigate('system')
        for tile in (self.pack_tile, self.cf_tile, self.pc_tile):
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
        v.addLayout(stats)

        v.addWidget(label('Explorar por temática', 'h2'))
        themes = QGridLayout()
        themes.setSpacing(10)
        for i, theme in enumerate(THEMES):
            chip = button('  ' + theme[1], kind='chip')
            chip.setIcon(icons.icon(theme[0], COLORS['accent'], 20))
            chip.setMinimumHeight(52)
            chip.clicked.connect(lambda _=False, t=theme: win.browse_theme(t))
            themes.addWidget(chip, i // 4, i % 4)
        v.addLayout(themes)

        heading = QHBoxLayout()
        self.popular_title = label('Populares', 'h2')
        heading.addWidget(self.popular_title)
        heading.addStretch()
        more = button('Ver todo', 'forward', 'ghost')
        more.clicked.connect(lambda: win.navigate('browse'))
        heading.addWidget(more)
        v.addLayout(heading)
        self.popular = QGridLayout()
        self.popular.setSpacing(16)
        v.addLayout(self.popular)
        v.addStretch()

        win.pack_changed.connect(self.refresh_stats)
        win.catalogs_changed.connect(self.refresh_stats)
        win.system_changed.connect(self.refresh_stats)
        win.target_changed.connect(self.load_popular)
        win.catalogs_changed.connect(self.load_popular)
        self.refresh_stats()

    def showEvent(self, event):
        super().showEvent(event)
        key = (self.win.target(), self.win.default_source())
        if self.loaded_for != key:
            self.load_popular()

    def refresh_stats(self):
        win = self.win
        mc, loader = win.target()
        self.pack_tile.set(f'{len(win.pack)} mods', f'{mc} · {loader}')
        cf = win.catalogs.curseforge.connection
        self.cf_tile.set('Conectado' if cf.mode else 'Sin conexión',
                         {'direct': 'Clave de API autorizada', 'gateway': 'Pasarela de ModLab'}.get(cf.mode, 'Configúralo en Ajustes'))
        if win.hw:
            self.pc_tile.set(f"{win.hw['ram_gb']:.0f} GB RAM", f"{len(win.instances)} instalaciones · {win.hw['gpu'][:28]}")

    def load_popular(self):
        if not self.isVisible():
            self.loaded_for = None
            return
        mc, loader = self.win.target()
        source = self.win.default_source()
        self.loaded_for = ((mc, loader), source)
        self.popular_title.setText(f'Populares en {SOURCE_LABELS[source]} para {mc} · {loader}')
        self._fill([SkeletonCard() for _ in range(4)])
        catalog = self.win.catalogs.get(source)

        def done(result):
            mods = result['mods'][:4]
            if not mods:
                self._fill([EmptyState('search', 'Sin resultados para esta versión', 'Prueba otra versión de Minecraft o cargador.')])
                return
            cards = []
            for mod in mods:
                item = ModCard(mod, self.win.images, self.win.state_of(mod))
                item.toggled.connect(self.win.toggle_mod)
                item.details.connect(self.win.open_details)
                cards.append(item)
            self._fill(cards)

        def failed(message):
            self._fill([EmptyState('alert', 'No se pudieron cargar los populares', message, tone='warning')])
        self.win.run(lambda progress, check: catalog.search(sort='downloads', page_size=4, minecraft=mc, loader=loader),
                     done, failed, key='home:popular', owner=self, visible=False)

    def _fill(self, widgets):
        clear_layout(self.popular)
        for i in range(4):
            self.popular.setColumnStretch(i, 1)
        if len(widgets) == 1 and isinstance(widgets[0], EmptyState):
            self.popular.addWidget(widgets[0], 0, 0, 1, 4)
            return
        self.cards = [w for w in widgets if isinstance(w, ModCard)]
        for i, widget in enumerate(widgets):
            self.popular.addWidget(widget, 0, i)

    def refresh_states(self):
        for item in getattr(self, 'cards', []):
            try:
                item.set_state(self.win.state_of(item.mod))
            except RuntimeError:
                pass
