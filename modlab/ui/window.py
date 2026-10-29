"""Ventana principal: navegación, estado compartido y coordinación de tareas."""
import re

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from modlab import __version__, logs
from modlab.errors import CatalogError
from modlab.local_ai import LocalAI
from modlab.project import Pack, VERSION_PATTERN
from modlab.settings import Settings
from modlab.sources import Catalogs, CurseForgeClient, ModrinthClient, connection_from_environment, key_of
from modlab.sources.base import LOADER_NAMES
from modlab.ui import icons
from modlab.ui.images import ImageLoader
from modlab.ui.pages.ai import AiPage
from modlab.ui.pages.browse import BrowsePage
from modlab.ui.pages.details import DetailsPage
from modlab.ui.pages.home import HomePage
from modlab.ui.pages.pack import PackPage
from modlab.ui.pages.settings import SettingsPage
from modlab.ui.pages.system import OptimizePage, SystemPage
from modlab.ui.tasks import TaskRunner
from modlab.ui.theme import COLORS
from modlab.ui.widgets import FadeStack, Spinner, ToastHost, button, label, tool

log = logs.get('window')
FALLBACK_VERSIONS = ['1.21.1', '1.20.1', '1.21.4', '1.19.2', '1.18.2', '1.16.5', '1.12.2']
NAV = [('home', 'Inicio', 'home', 'Tu punto de partida'),
       ('ai', 'Crear con IA', 'sparkles', 'Describe tu partida y recibe una propuesta razonada'),
       ('browse', 'Explorar mods', 'compass', 'Busca en CurseForge y Modrinth'),
       ('pack', 'Mi modpack', 'package', 'Revisa, comprueba y exporta tu selección'),
       ('system', 'Mi equipo', 'cpu', 'Hardware e instalaciones de Minecraft'),
       ('optimize', 'Optimizar', 'gauge', 'Perfil gráfico con copia de seguridad'),
       ('settings', 'Ajustes', 'settings', 'Conexiones, datos locales e IA')]


class ModLab(QMainWindow):
    pack_changed = Signal()
    target_changed = Signal()
    catalogs_changed = Signal()
    system_changed = Signal()

    def __init__(self, settings=None, catalogs=None, load_system=True):
        super().__init__()
        self.setWindowTitle('S.M.A.P.T. ModLab')
        self.resize(1440, 920)
        self.setMinimumSize(980, 640)
        self.settings = settings if settings is not None else Settings()
        self.catalogs = catalogs or Catalogs(CurseForgeClient(connection_from_environment(self.settings['gateway'])),
                                             ModrinthClient())
        self.runner = TaskRunner(self)
        self.images = ImageLoader(self)
        self.ai = LocalAI()
        self.pack = Pack(minecraft=self.settings['minecraft'], loader=self.settings['loader'])
        self.pack.author = self.settings['author']
        self.adding = set()
        self.hw = None
        self.instances = []
        self.history = []
        self._build()
        self.pack_changed.connect(self._pack_changed)
        self.runner.activity.connect(self._activity)
        self.navigate('home')
        if load_system:
            QTimer.singleShot(50, self.load_system)
            QTimer.singleShot(80, self.load_versions)

    # Construcción --------------------------------------------------------------------------------
    def _build(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._sidebar())
        main = QWidget()
        column = QVBoxLayout(main)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._topbar())
        self.stack = FadeStack()
        self.pages = {'home': HomePage(self), 'ai': AiPage(self), 'browse': BrowsePage(self), 'pack': PackPage(self),
                      'system': SystemPage(self), 'optimize': OptimizePage(self), 'settings': SettingsPage(self),
                      'details': DetailsPage(self)}
        for page in self.pages.values():
            self.stack.addWidget(page)
        column.addWidget(self.stack, 1)
        column.addWidget(self._activity_bar())
        outer.addWidget(main, 1)
        self.toasts = ToastHost(root)
        for index, (name, *_rest) in enumerate(NAV, 1):
            QShortcut(QKeySequence(f'Ctrl+{index}'), self, lambda n=name: self.navigate(n))
        QShortcut(QKeySequence('Ctrl+F'), self, self.focus_search)
        QShortcut(QKeySequence('Ctrl+S'), self, lambda: self.pages['pack'].save_project())
        QShortcut(QKeySequence('Ctrl+O'), self, lambda: self.pages['pack'].open_project())
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.back)
        QShortcut(QKeySequence('Alt+Left'), self, self.back)

    def _sidebar(self):
        side = QFrame()
        side.setObjectName('sidebar')
        self.sidebar = side
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 16)
        v.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icons.brand_pixmap(34, self.devicePixelRatioF()))
        brand.addWidget(logo)
        self.brand_text = QWidget()
        text = QVBoxLayout(self.brand_text)
        text.setContentsMargins(4, 0, 0, 0)
        text.setSpacing(0)
        text.addWidget(label('S.M.A.P.T.', 'brand'))
        text.addWidget(label('MODLAB', 'brandSub'))
        brand.addWidget(self.brand_text)
        brand.addStretch()
        v.addLayout(brand)
        v.addSpacing(22)
        self.nav = {}
        for name, title, icon_name, _ in NAV:
            if name == 'system':
                self.nav_section = label('TU EQUIPO', 'navSection')
                v.addSpacing(6)
                v.addWidget(self.nav_section)
            item = QPushButton('  ' + title)
            item.setObjectName('nav')
            item.setCheckable(True)
            item.setIcon(icons.icon(icon_name, COLORS['text2'], 18, active='#ff8fab'))
            item.setIconSize(QSize(18, 18))
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setToolTip(title)
            item.clicked.connect(lambda _=False, n=name: self.navigate(n))
            item.title = title
            self.nav[name] = item
            v.addWidget(item)
        v.addStretch()
        self.status_card = QFrame()
        self.status_card.setObjectName('statusCard')
        status = QVBoxLayout(self.status_card)
        status.setContentsMargins(12, 10, 12, 10)
        status.setSpacing(4)
        self.cf_status = label('', wrap=True, rich=True)
        self.mr_status = label('', rich=True)
        status.addWidget(self.cf_status)
        status.addWidget(self.mr_status)
        v.addWidget(self.status_card)
        self.version_label = label(f'v{__version__} · Acheron', 'muted')
        self.version_label.setContentsMargins(4, 8, 0, 0)
        v.addWidget(self.version_label)
        self._update_status()
        return side

    def _topbar(self):
        bar = QFrame()
        bar.setObjectName('topbar')
        row = QHBoxLayout(bar)
        row.setContentsMargins(28, 14, 20, 14)
        row.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title = label('', 'pageTitle')
        self.subtitle = label('', 'pageSubtitle')
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        row.addLayout(titles, 1)
        row.addWidget(label('Minecraft', 'muted'))
        self.version = QComboBox()
        self.version.setEditable(True)
        self.version.setMinimumWidth(110)
        self.version.setToolTip('Versión de Minecraft del modpack (puedes escribirla)')
        self.version.addItems(self._with_current(FALLBACK_VERSIONS))
        self.version.setCurrentText(self.pack.minecraft)
        self.version.lineEdit().editingFinished.connect(self.change_target)
        self.version.activated.connect(lambda _: self.change_target())
        row.addWidget(self.version)
        self.loader = QComboBox()
        self.loader.addItems(['Forge', 'NeoForge', 'Fabric', 'Quilt'])
        self.loader.setCurrentText(self.pack.loader)
        self.loader.setToolTip('Cargador de mods')
        self.loader.currentTextChanged.connect(lambda _: self.change_target())
        row.addWidget(self.loader)
        self.pack_button = button('Mi pack · 0', 'package', 'packBadge', icon_color='#ffd3de')
        self.pack_button.clicked.connect(lambda: self.navigate('pack'))
        row.addWidget(self.pack_button)
        return bar

    def _activity_bar(self):
        bar = QFrame()
        bar.setObjectName('activity')
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 8, 16, 8)
        row.setSpacing(10)
        self.spinner = Spinner(16)
        row.addWidget(self.spinner)
        self.activity_text = label('Listo.', 'muted')
        row.addWidget(self.activity_text, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(240)
        row.addWidget(self.progress)
        self.cancel_button = tool('x', 'Cancelar la operación en curso', size=14)
        self.cancel_button.clicked.connect(self.cancel)
        row.addWidget(self.cancel_button)
        self.spinner.hide()
        self.progress.hide()
        self.cancel_button.hide()
        return bar

    # Navegación ---------------------------------------------------------------------------------
    def navigate(self, name, remember=True):
        if name not in self.pages:
            return
        current = self._current_name()
        if remember and current and current != name:
            self.history = (self.history + [current])[-20:]
        for key, item in self.nav.items():
            item.setChecked(key == name)
        entry = next((n for n in NAV if n[0] == name), None)
        if entry:
            self.title.setText(entry[1])
            self.subtitle.setText(entry[3])
        self.stack.fade_to(self.stack.indexOf(self.pages[name]))

    def _current_name(self):
        widget = self.stack.currentWidget()
        return next((k for k, v in self.pages.items() if v is widget), None)

    def back(self):
        current = self._current_name()
        while self.history:
            name = self.history.pop()
            if name != current:
                self.navigate(name, remember=False)
                return

    def open_details(self, mod):
        self.pages['details'].show_mod(mod)
        self.navigate('details')
        self.title.setText(mod['title'])
        self.subtitle.setText('Ficha del mod')

    def browse_theme(self, theme):
        page = self.pages['browse']
        self.navigate('browse')
        page.apply_theme(theme)

    def focus_search(self):
        self.navigate('browse')
        self.pages['browse'].focus_search()

    # Estado compartido ---------------------------------------------------------------------------
    def target(self):
        return self.pack.minecraft, self.pack.loader

    def default_source(self):
        preferred = self.settings['source']
        if preferred == 'curseforge' and not self.catalogs.curseforge.available():
            return 'modrinth'
        return preferred

    def change_target(self):
        version = self.version.currentText().strip()
        loader = self.loader.currentText()
        if not VERSION_PATTERN.match(version) or loader not in LOADER_NAMES:
            self.toast('Versión de Minecraft no válida', 'Usa un formato como 1.20.1.', 'warning')
            self.version.setCurrentText(self.pack.minecraft)
            return
        if self.pack.set_target(version, loader):
            self.settings['minecraft'], self.settings['loader'] = version, loader
            self.settings.save()
            self.adding.clear()
            self.target_changed.emit()
            self.pack_changed.emit()
            if len(self.pack):
                self.toast('Versión cambiada', f'El pack conserva sus {len(self.pack)} mods; los archivos se verificarán '
                           f'de nuevo para {version} · {loader}.', 'info')

    def state_of(self, mod):
        key = key_of(mod)
        if key in self.pack:
            return 'in'
        return 'busy' if key in self.adding else 'add'

    def toggle_mod(self, mod):
        key = key_of(mod)
        if key in self.pack:
            self.pack.remove(key)
            self.pack_changed.emit()
            self.toast('Quitado del pack', mod['title'], 'info', 2200)
            return
        self.add_with_file(mod, None)

    def add_with_file(self, mod, file_id):
        """Fija un archivo compatible (el indicado o el más reciente) y añade el mod al pack."""
        key = key_of(mod)
        if key in self.adding:
            return
        catalog = self.catalogs.get(mod['source'])
        mc, loader = self.target()
        allow = self.settings['allow_unstable']
        wanted = dict(mod, file_id=file_id) if file_id else {k: v for k, v in mod.items() if k not in ('file_id', 'file')}
        self.adding.add(key)
        self._refresh_cards()

        def work(progress, check):
            pinned, failures = catalog.pin_many([wanted], mc, loader, allow_unstable=allow)
            if failures:
                raise CatalogError(failures[0]['reason'])
            return pinned[0]

        def done(pinned):
            self.adding.discard(key)
            if self.target() != (mc, loader):
                self._refresh_cards()
                return
            self.pack.add(pinned)
            self.pack_changed.emit()
            self.toast('Añadido al pack', f"{pinned['title']} · {pinned['version_number']}", 'success', 2600)

        def failed(message):
            self.adding.discard(key)
            self._refresh_cards()
            hint = '' if allow else ' Puedes elegir una beta en la pestaña Versiones o activarlas en Ajustes.'
            self.toast(f"No se pudo añadir {mod['title']}", message + hint, 'error', 7000)
        self.run(work, done, failed, key='pin:' + key, label='Comprobando ' + mod['title'], toast_errors=False)

    def load_pack(self, pack):
        self.pack = pack
        self.version.setCurrentText(pack.minecraft)
        self.loader.blockSignals(True)
        self.loader.setCurrentText(pack.loader)
        self.loader.blockSignals(False)
        self.settings['minecraft'], self.settings['loader'] = pack.minecraft, pack.loader
        self.target_changed.emit()
        self.pack_changed.emit()

    def _pack_changed(self):
        self.pack_button.setText(f'Mi pack · {len(self.pack)}')
        self._refresh_cards()

    def _refresh_cards(self):
        for name in ('browse', 'ai', 'home'):
            self.pages[name].refresh_states()
        if self._current_name() == 'details':
            self.pages['details'].refresh_state()

    def set_curseforge(self, client):
        self.catalogs.curseforge = client
        self._update_status()
        self.catalogs_changed.emit()

    def _update_status(self):
        mode = self.catalogs.curseforge.connection.mode
        dot = lambda ok: f"<span style='color:{COLORS['success'] if ok else COLORS['danger']}'>●</span>"
        self.cf_status.setText(f"{dot(bool(mode))} <b>CurseForge</b><br><span style='color:{COLORS['muted']}'>"
                               f"{ {'direct': 'Clave de API', 'gateway': 'Pasarela'}.get(mode, 'Sin conexión') }</span>")
        self.mr_status.setText(f"{dot(True)} <b>Modrinth</b> <span style='color:{COLORS['muted']}'>· público</span>")

    # Tareas -------------------------------------------------------------------------------------
    def run(self, fn, done=None, failed=None, key=None, label='', owner=None, visible=True, progress=None, toast_errors=True):
        def on_failed(message):
            if failed:
                failed(message)
            elif toast_errors:
                self.toast(label or 'La operación falló', message, 'error', 7000)

        def on_progress(message, fraction):
            if visible:
                self.activity_text.setText(message)
                if fraction >= 0:
                    self.progress.setRange(0, 1000)
                    self.progress.setValue(int(fraction * 1000))
                else:
                    self.progress.setRange(0, 0)
            if progress:
                progress(message, fraction)
        handle = self.runner.run(fn, done, on_failed, on_progress, owner, key, label, visible)
        if visible and label:
            self.activity_text.setText(label + '…')
        return handle

    def _activity(self):
        jobs = self.runner.visible_jobs()
        busy = bool(jobs)
        self.spinner.setVisible(busy)
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if busy:
            if self.progress.maximum() == 1000 and self.progress.value() >= 1000:
                self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
            self.activity_text.setText('Listo.')
        self.pages['pack'].update_buttons()

    def cancel(self):
        for handle in self.runner.visible_jobs():
            handle.cancel()
        self.adding.clear()
        self._refresh_cards()
        self.activity_text.setText('Operación cancelada. Tu pack se conserva.')
        QTimer.singleShot(0, self._activity)

    def toast(self, title, message='', tone='info', timeout=4500):
        return self.toasts.show_toast(title, message, tone, timeout)

    def load_system(self):
        from modlab.core import hardware, instances

        def done(result):
            self.hw, self.instances = result
            self.system_changed.emit()
        self.run(lambda p, c: (hardware(), instances()), done, key='system', visible=False)

    def load_versions(self):
        def done(versions):
            current = self.version.currentText()
            self.version.blockSignals(True)
            self.version.clear()
            self.version.addItems(self._with_current([v for v in versions if re.fullmatch(r'[\d.]+', v)][:80]))
            self.version.setCurrentText(current)
            self.version.blockSignals(False)
        self.run(lambda p, c: self.catalogs.modrinth.game_versions(), done, key='versions', visible=False, toast_errors=False)

    def _with_current(self, versions):
        current = self.pack.minecraft
        return versions if current in versions else [current] + list(versions)

    # Ventana ------------------------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 1180
        self.sidebar.setFixedWidth(76 if compact else 236)
        self.brand_text.setVisible(not compact)
        self.status_card.setVisible(not compact)
        self.version_label.setVisible(not compact)
        self.nav_section.setVisible(not compact)
        for item in self.nav.values():
            item.setText('' if compact else '  ' + item.title)
        self.toasts.reposition()

    def closeEvent(self, event):
        busy = self.runner.visible_jobs()
        if busy and any(h.label.startswith(('Exportando', 'Descargando')) for h in busy):
            answer = QMessageBox.question(self, 'Operación en curso', 'Hay una exportación o descarga en curso. '
                                          '¿Cancelarla y cerrar ModLab?')
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.settings.save()
        if not self.runner.shutdown(5000):
            log.warning('Algunas tareas no terminaron a tiempo al cerrar')
        event.accept()
