"""Ajustes: conexión de catálogos, preferencias, datos locales, IA y acerca de."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from modlab import __version__, ai_setup, logs, paths
from modlab.sources import Connection, CurseForgeClient
from modlab.ui.pages import scroll_page
from modlab.ui.widgets import Badge, button, card, label


class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = scroll_page()
        outer.addWidget(area)

        cf, cf_layout = card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label('CurseForge', 'h2'))
        head.addStretch()
        self.cf_badge = Badge('', 'neutral')
        head.addWidget(self.cf_badge)
        cf_layout.addLayout(head)
        self.cf_mode = label('', 'text2', wrap=True)
        cf_layout.addWidget(self.cf_mode)
        cf_layout.addWidget(label('Desarrollo: define la variable de entorno CURSEFORGE_API_KEY antes de abrir ModLab; la clave '
                                  'solo se envía a api.curseforge.com y nunca se guarda en disco. Distribución: los términos de '
                                  'CurseForge no permiten compartir la clave, así que las copias para otras personas usan la '
                                  'pasarela (catalog_server.py) publicada con HTTPS.', 'muted', wrap=True))
        row = QHBoxLayout()
        self.gateway = QLineEdit(win.settings['gateway'])
        self.gateway.setPlaceholderText('https://catalogo.tu-servidor.com')
        row.addWidget(label('Pasarela', 'muted'))
        row.addWidget(self.gateway, 1)
        save = button('Guardar pasarela', 'save')
        save.clicked.connect(self.save_gateway)
        row.addWidget(save)
        cf_layout.addLayout(row)
        row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('Clave de desarrollo solo para esta sesión (no se guarda)')
        row.addWidget(label('Clave', 'muted'))
        row.addWidget(self.key, 1)
        use = button('Usar en esta sesión', 'plug')
        use.clicked.connect(self.use_key)
        row.addWidget(use)
        cf_layout.addLayout(row)
        row = QHBoxLayout()
        test = button('Probar conexión', 'refresh', 'primary')
        test.clicked.connect(lambda: self.test('curseforge', self.cf_result))
        row.addWidget(test)
        self.cf_result = label('', 'muted', wrap=True)
        row.addWidget(self.cf_result, 1)
        cf_layout.addLayout(row)
        v.addWidget(cf)

        mr, mr_layout = card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label('Modrinth', 'h2'))
        head.addStretch()
        head.addWidget(Badge('Catálogo público', 'success'))
        mr_layout.addLayout(head)
        mr_layout.addWidget(label('No necesita clave. ModLab se identifica con su User-Agent y guarda en caché las consultas '
                                  'durante unos minutos para respetar el límite de 300 peticiones por minuto.', 'muted', wrap=True))
        row = QHBoxLayout()
        test = button('Probar conexión', 'refresh')
        test.clicked.connect(lambda: self.test('modrinth', self.mr_result))
        row.addWidget(test)
        self.mr_result = label('', 'muted', wrap=True)
        row.addWidget(self.mr_result, 1)
        mr_layout.addLayout(row)
        v.addWidget(mr)

        prefs, prefs_layout = card(spacing=10)
        prefs_layout.addWidget(label('Preferencias', 'h2'))
        self.unstable = QCheckBox('Usar versiones beta o alfa cuando un mod no tenga versión estable compatible')
        self.unstable.setChecked(win.settings['allow_unstable'])
        self.unstable.toggled.connect(lambda value: win.settings.__setitem__('allow_unstable', value))
        prefs_layout.addWidget(self.unstable)
        v.addWidget(prefs)

        data, data_layout = card(spacing=10)
        data_layout.addWidget(label('Datos locales', 'h2'))
        self.cache_label = label('', 'muted', wrap=True)
        data_layout.addWidget(self.cache_label)
        row = QHBoxLayout()
        clear = button('Vaciar caché', 'trash')
        clear.clicked.connect(self.clear_cache)
        row.addWidget(clear)
        open_logs = button('Abrir carpeta de registros', 'folder')
        open_logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.ensure(paths.log_dir())))))
        row.addWidget(open_logs)
        open_config = button('Abrir carpeta de ajustes', 'folder', 'ghost')
        open_config.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.ensure(paths.config_dir())))))
        row.addWidget(open_config)
        row.addStretch()
        data_layout.addLayout(row)
        data_layout.addWidget(label('Los registros no contienen claves ni cabeceras; las rutas personales se acortan a «~».',
                                    'muted', wrap=True))
        v.addWidget(data)

        ai, ai_layout = card(spacing=8)
        head = QHBoxLayout()
        head.addWidget(label('IA local (opcional)', 'h2'))
        head.addStretch()
        self.ai_badge = Badge('', 'neutral')
        head.addWidget(self.ai_badge)
        ai_layout.addLayout(head)
        self.ai_text = label('', 'muted', wrap=True)
        ai_layout.addWidget(self.ai_text)
        configure = button('Configurar IA', 'settings')
        configure.clicked.connect(self.configure_ai)
        ai_layout.addWidget(configure, 0, Qt.AlignmentFlag.AlignLeft)
        v.addWidget(ai)

        about, about_layout = card(spacing=6)
        about_layout.addWidget(label(f'S.M.A.P.T. ModLab {__version__} · Acheron Edition', 'h3'))
        about_layout.addWidget(label('Los mods pertenecen a sus autores y se rigen por sus licencias. ModLab respeta los permisos '
                                     'de distribución de CurseForge y los términos de las API de CurseForge y Modrinth.',
                                     'muted', wrap=True))
        links = QHBoxLayout()
        for text, url in (('Repositorio', 'https://github.com/Pablxmvrtinez/SMAPT-ModLab'),
                          ('Licencias de terceros', 'https://github.com/Pablxmvrtinez/SMAPT-ModLab/blob/main/THIRD_PARTY.md')):
            item = button(text, 'external', 'ghost')
            item.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            links.addWidget(item)
        links.addStretch()
        about_layout.addLayout(links)
        v.addWidget(about)
        v.addStretch()
        win.catalogs_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        connection = self.win.catalogs.curseforge.connection
        mode = connection.mode
        self.cf_badge.set({'direct': 'Clave de API', 'gateway': 'Pasarela'}.get(mode, 'Sin conexión'),
                          'success' if mode else 'danger')
        self.cf_mode.setText({'direct': 'Conectado directamente con la clave de la variable de entorno o de esta sesión.',
                              'gateway': f'Conectado mediante la pasarela {connection.gateway}.'}.get(
            mode, 'CurseForge no está configurado. Explorar y exportar con Modrinth funciona igualmente.'))
        size = self.win.images.disk_size() + self.win.catalogs.modrinth.cache_size()
        self.cache_label.setText(f'Caché de Modrinth e imágenes: {size / 1024 / 1024:.1f} MB en {paths.cache_dir()}. '
                                 'Las respuestas de CurseForge no se guardan (términos de su API).')
        info = ai_setup.status()
        self.ai_badge.set('Disponible' if info['ready'] else 'No instalada', 'success' if info['ready'] else 'warning')
        self.ai_text.setText(ai_setup.describe(info) + ' Qwen3-4B-Instruct-2507 (Q4_K_M) en llama.cpp, dentro de tu equipo; '
                             'necesita unos 5,5 GB de RAM libre mientras trabaja. En «Configurar IA» puedes descargar el '
                             'modelo con verificación SHA-256 y probarlo.')

    def configure_ai(self):
        self.win.navigate('ai')
        self.win.pages['ai'].show_setup()

    def save_gateway(self):
        url = self.gateway.text().strip().rstrip('/')
        if url:
            try:
                Connection(url).check()
            except ValueError as exc:
                self.cf_result.setText(str(exc))
                return
        self.win.settings['gateway'] = url
        self.win.settings.save()
        self.win.set_curseforge(CurseForgeClient(Connection(url, self.win.catalogs.curseforge.connection.api_key)))
        self.cf_result.setText('Pasarela guardada.' if url else 'Pasarela eliminada.')

    def use_key(self):
        key = self.key.text().strip()
        if not key:
            return
        self.key.clear()
        self.win.set_curseforge(CurseForgeClient(Connection(self.win.settings['gateway'], key)))
        self.test('curseforge', self.cf_result)

    def test(self, source, target):
        catalog = self.win.catalogs.get(source)
        target.setText('Probando…')

        def work(progress, check):
            rows = catalog.categories()
            check()
            found = catalog.search('', page_size=1, minecraft='1.20.1', loader='Fabric')
            return len(rows), found['pagination'].get('totalCount', 0)

        def done(result):
            target.setText(f'✔ Conexión correcta: {result[0]} categorías y {result[1]:,} mods para 1.20.1 · Fabric.'.replace(',', '.'))
            target.setObjectName('success')
            target.style().polish(target)

        def failed(message):
            target.setText('✖ ' + message)
            target.setObjectName('error')
            target.style().polish(target)
            logs.get('settings').info('Prueba de conexión de %s fallida', source)
        self.win.run(work, done, failed, key='test:' + source, owner=target, visible=False, toast_errors=False)

    def clear_cache(self):
        self.win.images.clear()
        self.win.catalogs.modrinth.clear_cache()
        self.refresh()
        self.win.toast('Caché vaciada', tone='success', timeout=2500)
