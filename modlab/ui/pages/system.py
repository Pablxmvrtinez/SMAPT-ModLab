"""Mi equipo (hardware e instalaciones) y Optimizar (perfil gráfico con copia de seguridad)."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QMessageBox,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from modlab.core import apply_graphics, backups, recommend, restore_backup
from modlab.ui.pages import scroll_page
from modlab.ui.theme import COLORS
from modlab.ui.widgets import EmptyState, Segmented, StatTile, button, card, label


class SystemPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = scroll_page()
        outer.addWidget(area)
        tiles = QGridLayout()
        tiles.setSpacing(14)
        self.cpu = StatTile('cpu', 'Procesador', '…')
        self.gpu = StatTile('monitor', 'Gráfica', '…', accent=COLORS['violet'])
        self.ram = StatTile('layers', 'Memoria', '…', accent=COLORS['blue'])
        self.os = StatTile('server', 'Sistema', '…', accent=COLORS['success'])
        for i, tile in enumerate((self.cpu, self.gpu, self.ram, self.os)):
            tiles.addWidget(tile, i // 2, i % 2)
        v.addLayout(tiles)

        box, layout = card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label('Instalaciones de Minecraft encontradas', 'h2'))
        head.addStretch()
        refresh = button('Actualizar', 'refresh', 'ghost')
        refresh.clicked.connect(win.load_system)
        head.addWidget(refresh)
        layout.addLayout(head)
        layout.addWidget(label('CurseForge, Prism (nativo y Flatpak), MultiMC, Modrinth App, ATLauncher y el lanzador oficial, '
                               'en Windows y Linux. Doble clic para abrir la carpeta.', 'muted', wrap=True))
        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Instancia', 'Lanzador', 'Minecraft', 'Cargador', 'Mods'])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(300)
        header = self.table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemDoubleClicked.connect(lambda item, _: QDesktopServices.openUrl(
            QUrl.fromLocalFile(item.data(0, Qt.ItemDataRole.UserRole))))
        layout.addWidget(self.table)
        self.empty = label('No se encontraron instalaciones en las carpetas habituales.', 'muted')
        layout.addWidget(self.empty)
        v.addWidget(box)
        v.addWidget(label('El análisis no mide FPS: las recomendaciones de Optimizar se basan en la RAM, la VRAM y el '
                          'número de mods.', 'muted', wrap=True))
        v.addStretch()
        win.system_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        hw = self.win.hw
        if hw:
            self.cpu.set(hw['cpu'][:40], f"{hw['threads']} hilos")
            extra = (' · también ' + ', '.join(hw['gpus'][1:])) if len(hw.get('gpus', [])) > 1 else ''
            self.gpu.set(hw['gpu'][:40], (f"{hw['vram_gb']} GB de VRAM" if hw['vram_gb'] else 'VRAM no detectada') + extra)
            self.ram.set(f"{hw['ram_gb']} GB", f"{hw['ram_available_gb']} GB libres ahora")
            self.os.set(hw.get('system', '')[:40], '')
        self.table.clear()
        for inst in self.win.instances:
            item = QTreeWidgetItem([inst['name'], inst['launcher'], inst['version'] or '—', inst.get('loader') or '—',
                                    str(inst['mods'])])
            item.setData(0, Qt.ItemDataRole.UserRole, inst.get('folder') or inst['path'])
            item.setToolTip(0, inst['path'])
            self.table.addTopLevelItem(item)
        self.empty.setVisible(not self.win.instances and hw is not None)


class OptimizePage(QWidget):
    MODES = [('Equilibrado', 'Equilibrado'), ('Máximos FPS', 'Máximos FPS'), ('Calidad visual', 'Calidad visual')]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.profile = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = scroll_page()
        outer.addWidget(area)
        box, layout = card(spacing=12)
        layout.addWidget(label('Perfil gráfico para una instancia', 'h2'))
        layout.addWidget(label('Antes de aplicar cambios se guarda una copia de options.txt y de la configuración de shaders '
                               '(Oculus/Iris). Puedes restaurarla cuando quieras.', 'muted', wrap=True))
        row = QHBoxLayout()
        row.addWidget(label('Instancia', 'muted'))
        self.instance = QComboBox()
        self.instance.currentIndexChanged.connect(self.update_profile)
        row.addWidget(self.instance, 1)
        self.mode = Segmented(self.MODES)
        self.mode.changed.connect(lambda _: self.update_profile())
        row.addWidget(self.mode)
        layout.addLayout(row)
        v.addWidget(box)

        self.tiles = QGridLayout()
        self.tiles.setSpacing(14)
        self.render = StatTile('mountain', 'Distancia de renderizado', '—')
        self.simulation = StatTile('cube', 'Simulación', '—', accent=COLORS['violet'])
        self.fps = StatTile('gauge', 'FPS máximos', '—', accent=COLORS['blue'])
        self.shaders = StatTile('sparkles', 'Shaders', '—', accent=COLORS['warning'])
        self.heap = StatTile('layers', 'RAM de Java recomendada', '—', 'Se configura en el lanzador', accent=COLORS['success'])
        for i, tile in enumerate((self.render, self.simulation, self.fps, self.shaders, self.heap)):
            self.tiles.addWidget(tile, i // 3, i % 3)
        v.addLayout(self.tiles)
        actions = QHBoxLayout()
        self.apply_button = button('Aplicar con copia de seguridad', 'check', 'primary')
        self.apply_button.clicked.connect(self.apply)
        actions.addWidget(self.apply_button)
        self.restore_button = button('Restaurar una copia…', 'restore')
        self.restore_button.clicked.connect(self.restore)
        actions.addWidget(self.restore_button)
        actions.addStretch()
        v.addLayout(actions)
        self.empty = EmptyState('cpu', 'No hay instancias detectadas', 'Instala un modpack con CurseForge, Prism u otro '
                                'lanzador compatible y pulsa Actualizar en Mi equipo.')
        v.addWidget(self.empty)
        v.addWidget(label('Se ajustan distancia de renderizado y simulación, FPS máximos, VSync, partículas y el interruptor '
                          'de shaders. No se tocan mundos, mods ni servidores. La RAM de Java solo se recomienda.',
                          'muted', wrap=True))
        v.addStretch()
        win.system_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        current = self.instance.currentData()
        self.instance.blockSignals(True)
        self.instance.clear()
        for inst in self.win.instances:
            self.instance.addItem(f"{inst['name']}  ·  {inst['launcher']}  ·  {inst['mods']} mods", inst)
            if current and inst['path'] == current['path']:
                self.instance.setCurrentIndex(self.instance.count() - 1)
        self.instance.blockSignals(False)
        has = bool(self.win.instances)
        self.empty.setVisible(not has and self.win.hw is not None)
        self.update_profile()

    def update_profile(self, *_):
        inst = self.instance.currentData()
        enabled = bool(inst and self.win.hw)
        self.apply_button.setEnabled(enabled)
        self.restore_button.setEnabled(enabled)
        if not enabled:
            return
        self.profile = recommend(inst['mods'], self.win.hw, self.mode.current)
        p = self.profile
        self.render.set(f"{p['render']} chunks")
        self.simulation.set(f"{p['simulation']} chunks")
        self.fps.set(str(p['fps']), 'VSync desactivado')
        self.shaders.set('Activados' if p['shaders'] else 'Desactivados', 'Si hay Oculus o Iris instalado')
        self.heap.set(f"{p['heap']} GB máximo")

    def apply(self):
        inst = self.instance.currentData()
        if not inst:
            return
        answer = QMessageBox.question(self, 'Aplicar perfil gráfico',
                                      f"Se modificará la configuración gráfica de «{inst['name']}» y se guardará una copia.\n"
                                      'Cierra Minecraft antes de continuar. ¿Aplicar?')
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            backup = apply_graphics(inst, self.profile)
        except (OSError, ValueError, RuntimeError) as exc:
            self.win.toast('No se pudo aplicar el perfil', str(exc), 'error', 7000)
            return
        self.win.toast('Perfil aplicado', f'Copia guardada en {Path(backup).name}. Reinicia Minecraft.', 'success', 6000)

    def restore(self):
        inst = self.instance.currentData()
        if not inst:
            return
        copies = backups(inst)
        if not copies:
            self.win.toast('Sin copias de seguridad', 'Esta instancia todavía no tiene copias de ModLab.', 'info')
            return
        names = [c.name for c in copies]
        name, ok = QInputDialog.getItem(self, 'Restaurar copia', 'Elige la copia de seguridad (la más reciente primero):',
                                        names, 0, False)
        if not ok:
            return
        try:
            restore_backup(inst, copies[names.index(name)])
        except (OSError, ValueError, RuntimeError) as exc:
            self.win.toast('No se pudo restaurar', str(exc), 'error', 7000)
            return
        self.win.toast('Copia restaurada', 'Se guardó también el estado anterior por si quieres volver.', 'success')
