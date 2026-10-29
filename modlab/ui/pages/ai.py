"""Crear con IA: describe una partida y la IA local recomienda mods o monta un modpack exportable."""
import json
import time

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QHeaderView, QMessageBox, QPlainTextEdit, QProgressBar,
                               QSpinBox, QStackedWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from modlab.intelligence import BRIEF_EVENT, DesignRequest, ModpackDesigner
from modlab.sources import LABELS as SOURCE_LABELS
from modlab.ui import icons
from modlab.ui.pages import plain_page
from modlab.ui.pages.ai_setup import AiSetupPanel
from modlab.ui.theme import COLORS
from modlab.ui.widgets import (Badge, CardGrid, EmptyState, Segmented, Spinner, button, card, clear_layout, label,
                               restyle)

EXAMPLES = [
    ('Apocalipsis zombi', 'Quiero un Minecraft ambientado en un apocalipsis zombi. Me gustaría explorar ciudades abandonadas, '
                          'utilizar armas de fuego y construir bases para sobrevivir. No quiero que sea excesivamente difícil.'),
    ('RPG de fantasía', 'Quiero algo parecido a un RPG de fantasía con progresión de personaje, jefes y mazmorras, '
                        'pero sin tecnología industrial.'),
    ('Construir tranquilo', 'Quiero construir casas bonitas tranquilamente, sin combates adicionales, y tengo un ordenador poco potente.'),
    ('Parecido a Pokémon', 'Quiero un Minecraft parecido a Pokémon.'),
    ('Magia y dragones', 'Quiero magia y dragones, pero nada de máquinas.'),
    ('Granja con mascotas', 'Quiero algo tranquilo con mascotas, muebles y agricultura.'),
]
STEPS = [('Interpretando descripción', 'sparkles'), ('Buscando mods', 'search'),
         ('Evaluando compatibilidad', 'shield'), ('Preparando resultado', 'package')]
PERFORMANCE = [('equilibrado', 'Equilibrado'), ('rendimiento', 'Priorizar rendimiento'), ('contenido', 'Priorizar contenido')]


def step_of(message):
    for index, prefix in enumerate(('Interpretando', 'Buscando', 'Evaluando', 'Preparando')):
        if message.startswith(prefix):
            return index
    return 3 if message.startswith('Comprobando') else None


class Stepper(QWidget):
    """Cuatro fases con su estado (pendiente, en curso, hecha), progreso real y tiempo transcurrido."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.items = []
        for title, icon_name in STEPS:
            holder = QHBoxLayout()
            holder.setSpacing(8)
            mark = label()
            mark.setFixedSize(22, 22)
            spin = Spinner(18)
            spin.hide()
            text = label(title, 'muted')
            holder.addWidget(mark)
            holder.addWidget(spin)
            holder.addWidget(text)
            row.addLayout(holder)
            self.items.append((mark, spin, text, icon_name))
        row.addStretch()
        self.elapsed = label('', 'muted')
        row.addWidget(self.elapsed)
        layout.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        self.detail = label('', 'text2', wrap=True)
        layout.addWidget(self.detail)
        self.started = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.set_step(-1)

    def start(self):
        self.started = time.monotonic()
        self.bar.setValue(0)
        self.set_step(0)
        self.timer.start(1000)
        self._tick()

    def stop(self, done=True):
        self.timer.stop()
        self.set_step(len(STEPS) if done else -1)
        if done:
            self.bar.setValue(1000)

    def _tick(self):
        seconds = int(time.monotonic() - self.started)
        self.elapsed.setText(f'{seconds // 60}:{seconds % 60:02d}')

    def set_step(self, current):
        self.current = current
        for index, (mark, spin, text, icon_name) in enumerate(self.items):
            active = index == current
            done = index < current
            spin.setVisible(active)
            mark.setVisible(not active)
            color = COLORS['success'] if done else COLORS['muted']
            mark.setPixmap(icons.pixmap('check' if done else icon_name, color, 18, 2.0))
            text.setObjectName('h3' if active else 'text2' if done else 'muted')
            restyle(text)

    def advance(self, message, fraction):
        step = step_of(message)
        if step is not None and step != self.current:
            self.set_step(step)
        if fraction >= 0:
            self.bar.setValue(max(self.bar.value(), int(fraction * 1000)))
        self.detail.setText(message)


class AiPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.result = None
        self.handle = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        page, v = plain_page(spacing=12)
        outer.addWidget(page)

        self.composer, layout = card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label('Describe la partida que quieres', 'h2'))
        head.addStretch()
        self.status = button('', 'settings', 'ghost')
        self.status.clicked.connect(self.show_setup)
        head.addWidget(self.status)
        layout.addLayout(head)
        self.collapsed = QWidget()
        collapsed = QHBoxLayout(self.collapsed)
        collapsed.setContentsMargins(0, 0, 0, 0)
        self.collapsed_text = label('', 'text2')
        collapsed.addWidget(self.collapsed_text, 1)
        edit = button('Editar descripción', 'chevron_down', 'ghost')
        edit.clicked.connect(lambda: self.set_compact(False))
        collapsed.addWidget(edit)
        self.collapsed.hide()
        layout.addWidget(self.collapsed)
        self.editor = QWidget()
        editor = QVBoxLayout(self.editor)
        editor.setContentsMargins(0, 0, 0, 0)
        editor.setSpacing(10)
        self.prompt = QTextEdit()
        self.prompt.setAcceptRichText(False)
        self.prompt.setMinimumHeight(96)
        self.prompt.setMaximumHeight(150)
        self.prompt.setPlaceholderText('Escribe con libertad: ambientación, actividades, ritmo, dificultad, lo que NO quieres y '
                                       'tu equipo. Por ejemplo: «Quiero sobrevivir en un apocalipsis zombi explorando ciudades, '
                                       'con armas de fuego y bases, sin que sea muy difícil».')
        editor.addWidget(self.prompt)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for title, phrase in EXAMPLES:
            chip = button(title, kind='ghost')
            chip.setToolTip(phrase)
            chip.clicked.connect(lambda _=False, t=phrase: self.prompt.setPlainText(t))
            chips.addWidget(chip)
        chips.addStretch()
        editor.addLayout(chips)
        modes = QHBoxLayout()
        modes.setSpacing(10)
        modes.addWidget(label('Modo', 'muted'))
        self.mode = Segmented([('recommend', 'Recomendar mods'), ('create', 'Crear modpack')])
        self.mode.changed.connect(self._mode_changed)
        modes.addWidget(self.mode)
        modes.addSpacing(10)
        modes.addWidget(label('Catálogo', 'muted'))
        self.source = Segmented([('modrinth', 'Modrinth'), ('curseforge', 'CurseForge')], win.default_source())
        self.source.changed.connect(self._source_changed)
        modes.addWidget(self.source)
        modes.addStretch()
        editor.addLayout(modes)
        layout.addWidget(self.editor)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(label('Minecraft', 'muted'))
        self.version = QComboBox()
        self.version.setEditable(True)
        self.version.setMinimumWidth(96)
        row.addWidget(self.version)
        self.loader = QComboBox()
        self.loader.addItems(['Fabric', 'Forge', 'NeoForge', 'Quilt'])
        row.addWidget(self.loader)
        row.addWidget(label('≈ mods', 'muted'))
        self.target = QSpinBox()
        self.target.setRange(3, 150)
        self.target.setValue(20)
        self.target.setToolTip('Cantidad aproximada. Más mods = más fichas que evaluar y más tiempo.')
        row.addWidget(self.target)
        self.performance = QComboBox()
        for key, text_ in PERFORMANCE:
            self.performance.addItem(text_, key)
        row.addWidget(self.performance)
        row.addStretch()
        self.go = button('Analizar mi idea', 'sparkles', 'primary')
        self.go.clicked.connect(self.start)
        row.addWidget(self.go)
        layout.addLayout(row)
        v.addWidget(self.composer)

        self.activity, activity_layout = card(spacing=8)
        top = QHBoxLayout()
        top.addWidget(label('La IA está trabajando en tu idea', 'h3'))
        top.addStretch()
        self.cancel_button = button('Cancelar', 'x', 'ghost')
        self.cancel_button.clicked.connect(self.cancel)
        top.addWidget(self.cancel_button)
        activity_layout.addLayout(top)
        self.stepper = Stepper()
        activity_layout.addWidget(self.stepper)
        self.activity.hide()
        v.addWidget(self.activity)

        self.brief_card, self.brief_layout = card(spacing=8)
        self.brief_card.hide()
        v.addWidget(self.brief_card)

        self.stack = QStackedWidget()
        self.intro = EmptyState('sparkles', 'Escribe tu idea con tus propias palabras',
                                'La IA local entiende la descripción completa (también lo que no quieres), busca mods reales '
                                'en el catálogo y explica por qué encaja cada uno. «Crear modpack» además resuelve '
                                'dependencias y deja el pack listo para exportar.')
        self.setup = AiSetupPanel(win)
        self.setup.changed.connect(self._update_status)
        self.grid = CardGrid(win.images)
        self.grid.toggled.connect(win.toggle_mod)
        self.grid.details.connect(win.open_details)
        self.grid.discarded.connect(self.discard)
        self.preview = QWidget()
        QVBoxLayout(self.preview).setContentsMargins(0, 0, 0, 0)
        results = QWidget()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(8)
        bar = QHBoxLayout()
        self.summary = label('', 'muted', wrap=True)
        bar.addWidget(self.summary, 1)
        self.rejected_button = button('', 'filter', 'ghost')
        self.rejected_button.clicked.connect(self.show_rejected)
        bar.addWidget(self.rejected_button)
        self.add_all = button('Añadir todas', 'plus')
        self.add_all.clicked.connect(self.add_all_mods)
        bar.addWidget(self.add_all)
        results_layout.addLayout(bar)
        self.results_stack = QStackedWidget()
        self.results_stack.addWidget(self.grid)
        self.results_stack.addWidget(self.preview)
        results_layout.addWidget(self.results_stack, 1)
        for widget in (self.intro, self.setup, results):
            self.stack.addWidget(widget)
        self.results = results
        v.addWidget(self.stack, 1)

        win.target_changed.connect(self._sync_target)
        win.pack_changed.connect(self.refresh_states)
        win.catalogs_changed.connect(self._update_status)
        self._sync_target()
        self._update_status()
        self.stack.setCurrentWidget(self.intro if self.setup.ready() else self.setup)

    # Estado --------------------------------------------------------------------------------------
    def _sync_target(self):
        mc, loader = self.win.target()
        self.version.blockSignals(True)
        self.version.clear()
        self.version.addItems([self.win.version.itemText(i) for i in range(self.win.version.count())])
        self.version.setCurrentText(mc)
        self.version.blockSignals(False)
        self.loader.blockSignals(True)
        self.loader.setCurrentText(loader)
        self.loader.blockSignals(False)

    def _update_status(self):
        ready = self.setup.ready()
        self.status.setText('IA local lista' if ready else 'Configurar IA')
        self.status.setIcon(icons.icon('check' if ready else 'alert', COLORS['success'] if ready else COLORS['warning'], 16))
        self.go.setEnabled(ready and self.handle is None)
        self.go.setToolTip('' if ready else 'Primero instala el motor y el modelo de IA en «Configurar IA».')

    def _mode_changed(self, mode):
        self.go.setText('Crear mi modpack' if mode == 'create' else 'Analizar mi idea')

    def _source_changed(self, source):
        if source == 'curseforge' and not self.win.catalogs.curseforge.available():
            self.win.toast('CurseForge no está conectado', 'Define CURSEFORGE_API_KEY o configura la pasarela en Ajustes. '
                           'Modrinth funciona sin clave.', 'warning', 6000)
            self.source.set_current('modrinth')

    def set_compact(self, compact):
        """Durante el análisis y con resultados, la descripción se resume en una línea para dejar sitio."""
        text = ' '.join(self.prompt.toPlainText().split())
        self.collapsed_text.setText(text if len(text) < 150 else text[:147] + '…')
        self.collapsed_text.setToolTip(self.prompt.toPlainText())
        self.collapsed.setVisible(compact)
        self.editor.setVisible(not compact)

    def show_setup(self):
        self.setup.refresh()
        self.stack.setCurrentWidget(self.setup)

    # Ejecución -------------------------------------------------------------------------------------
    def start(self):
        phrase = self.prompt.toPlainText().strip()
        if len(phrase) < 8:
            self.win.toast('Describe tu idea', 'Escribe al menos una frase sobre la partida que quieres.', 'warning')
            return
        if not self.setup.ready():
            self.show_setup()
            self.win.toast('Falta configurar la IA', 'Instala el motor y el modelo para continuar.', 'warning')
            return
        version, loader = self.version.currentText().strip(), self.loader.currentText()
        if (version, loader) != self.win.target():
            self.win.set_target(version, loader)
            if self.win.target() != (version, loader):
                return
        catalog = self.win.catalogs.get(self.source.current)
        request = DesignRequest(phrase, version, loader, self.target.value(), self.performance.currentData(), self.mode.current)
        designer = ModpackDesigner(catalog, self.win.ai)
        self.result = None
        self.brief_card.hide()
        self.set_compact(True)
        self.activity.show()
        self.stepper.start()
        self.stack.setCurrentWidget(self.results)
        self.results_stack.setCurrentWidget(self.grid)
        self.grid.show_loading(min(8, request.target))
        self.summary.setText('Los resultados aparecerán al terminar la evaluación.')
        self.rejected_button.hide()
        self.add_all.hide()

        def progress(message, fraction):
            if message.startswith(BRIEF_EVENT):
                self.show_brief(json.loads(message[len(BRIEF_EVENT):]))
                self.stepper.advance('Buscando mods…', fraction)
            else:
                self.stepper.advance(message, fraction)

        def done(result):
            self.handle = None
            self.stepper.stop()
            self.activity.hide()
            self._update_status()
            self.show_result(result, request)

        def failed(message):
            self.handle = None
            self.stepper.stop(done=False)
            self.activity.hide()
            self._update_status()
            self.grid.show_message(EmptyState('alert', 'La IA no pudo completar la propuesta', message, tone='danger'))
            self.summary.setText('')
        self.handle = self.win.run(lambda report, check: designer.run(request, report, check), done, failed, key='ai',
                                   label='La IA está analizando tu idea', owner=self, progress=progress, toast_errors=False)
        self._update_status()

    def cancel(self):
        if self.handle is not None:
            self.handle.cancel()
            self.handle = None
        self.stepper.stop(done=False)
        self.activity.hide()
        self.grid.show_message(EmptyState('x', 'Análisis cancelado', 'Puedes ajustar la descripción y volver a intentarlo.'))
        self.summary.setText('')
        self._update_status()

    # Resultados --------------------------------------------------------------------------------------
    def show_brief(self, brief):
        clear_layout(self.brief_layout)
        self.brief_card.show()
        head = QHBoxLayout()
        head.addWidget(label('LO QUE HA ENTENDIDO LA IA', 'eyebrow'))
        head.addStretch()
        head.addWidget(Badge('Dificultad: ' + brief['difficulty'], 'neutral'))
        head.addWidget(Badge('Rendimiento: ' + brief['performance'], 'neutral'))
        self.brief_layout.addLayout(head)
        self.brief_layout.addWidget(label(brief['summary'], 'h3', wrap=True))
        if brief.get('analysis'):
            self.brief_layout.addWidget(label(brief['analysis'], 'muted', wrap=True))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for requirement in brief['requirements']:
            chip = Badge(requirement['name'], 'warning' if requirement['priority'] == 'obligatorio' else 'neutral')
            chip.setToolTip(f"{requirement['priority'].capitalize()} · {requirement['detail']}\n"
                            f"Búsquedas: {', '.join(requirement['queries'] + requirement['examples'])}")
            chips.addWidget(chip)
        for exclusion in brief['exclusions']:
            chip = Badge('Sin ' + exclusion['concept'].lower(), 'danger')
            chip.setToolTip('Se descartan fichas con: ' + ', '.join(exclusion['terms']))
            chips.addWidget(chip)
        chips.addStretch()
        self.brief_layout.addLayout(chips)
        if brief.get('assumptions'):
            self.brief_layout.addWidget(label('Supuestos: ' + '; '.join(brief['assumptions']), 'muted', wrap=True))

    def show_result(self, result, request):
        self.result = result
        self.request = request
        self.show_brief(result['brief'])
        stats = result['stats']
        speed = f" · {stats['tokens_per_second']} frag/s" if stats.get('tokens_per_second') else ''
        covered = sum(1 for row in result['coverage'] if row['mods'])
        self.summary.setText(f"{len(result['mods'])} mods de {SOURCE_LABELS[self.source.current]} · cubren {covered} de "
                             f"{len(result['coverage'])} requisitos · {stats['found']} fichas encontradas, "
                             f"{stats['evaluated']} evaluadas por la IA en {stats['seconds']:.0f} s{speed}. "
                             + ' '.join(result['warnings'][1:]))
        self.rejected_button.setText(f"Descartados ({len(result['rejected'])})")
        self.rejected_button.setVisible(bool(result['rejected']))
        if result['mode'] == 'create':
            self.add_all.hide()
            self.show_preview(result)
            self.results_stack.setCurrentWidget(self.preview)
        else:
            self.add_all.show()
            self.grid.show_mods(result['mods'], self.win.state_of, discardable=True)
            self.results_stack.setCurrentWidget(self.grid)
        self.win.toast('Propuesta lista' if result['mode'] == 'recommend' else 'Modpack preparado',
                       f"{len(result['mods'])} mods · revisa los motivos antes de usarlos.", 'success')

    def discard(self, mod):
        if not self.result:
            return
        self.result['mods'] = [m for m in self.result['mods'] if m['key'] != mod['key']]
        self.result['rejected'].append({'title': mod['title'], 'reason': 'Descartado por ti.'})
        self.grid.show_mods(self.result['mods'], self.win.state_of, discardable=True)
        self.rejected_button.setText(f"Descartados ({len(self.result['rejected'])})")
        self.rejected_button.show()

    def add_all_mods(self):
        if not self.result:
            return
        added = 0
        for mod in self.result['mods']:
            if mod['key'] not in self.win.pack:
                self.win.pack.add(mod)
                added += 1
        if not self.win.pack.description:
            self.win.pack.description = self.prompt.toPlainText().strip()[:500]
        self.win.pack_changed.emit()
        self.win.toast(f'{added} mods añadidos a Mi modpack', 'Las dependencias se añaden al comprobar o exportar.', 'success')

    def show_rejected(self):
        if not self.result:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Mods descartados')
        dialog.resize(640, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('Fichas que la IA o los filtros descartaron, con el motivo.', 'muted', wrap=True))
        text = QPlainTextEdit('\n'.join(f"• {r['title']}: {r['reason']}" for r in self.result['rejected']))
        text.setReadOnly(True)
        layout.addWidget(text)
        close = button('Cerrar')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    # Vista previa del modpack (modo B) -------------------------------------------------------------------
    def show_preview(self, result):
        layout = self.preview.layout()
        clear_layout(layout)
        box, inner = card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label('Vista previa del modpack', 'h2'))
        head.addStretch()
        head.addWidget(Badge(f"{len(result['mods'])} mods elegidos", 'success'))
        head.addWidget(Badge(f"+ {len(result['dependencies'])} dependencias", 'neutral'))
        inner.addLayout(head)
        inner.addWidget(label('Desmarca lo que no quieras. Las dependencias obligatorias se recalculan al exportar.', 'muted', wrap=True))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Mod', 'Versión', 'Motivo'])
        self.tree.setIconSize(QSize(28, 28))
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self._open_item)
        groups = {}
        for row in result['coverage']:
            group = QTreeWidgetItem([f"{row['requirement']}  ·  {row['priority']}", '', '' if row['mods'] else
                                     'Sin mods compatibles para este requisito'])
            group.setFirstColumnSpanned(not row['mods'])
            self.tree.addTopLevelItem(group)
            groups[row['requirement']] = group
        other = None
        for mod in result['mods']:
            parent = groups.get(mod.get('requirement'))
            if parent is None:
                other = other or QTreeWidgetItem(['Otros'])
                parent = other
            item = QTreeWidgetItem([mod['title'], mod.get('version_number', ''), mod.get('reason', '')])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, mod['key'])
            item.setToolTip(2, mod.get('reason', ''))
            parent.addChild(item)
            self._icon(item, mod)
        if other:
            self.tree.addTopLevelItem(other)
        if result['dependencies']:
            deps = QTreeWidgetItem(['Dependencias que se añadirán', '', 'Necesarias para que funcionen los mods elegidos'])
            for mod in result['dependencies']:
                child = QTreeWidgetItem([mod['title'], mod.get('version_number', ''), 'Dependencia obligatoria'])
                deps.addChild(child)
                self._icon(child, mod)
            self.tree.addTopLevelItem(deps)
        self.tree.expandAll()
        inner.addWidget(self.tree, 1)
        actions = QHBoxLayout()
        use = button('Editar en Mi modpack', 'package')
        use.clicked.connect(lambda: self.use_preview(export=False))
        actions.addWidget(use)
        export = button('Exportar ' + ('.mrpack' if self.source.current == 'modrinth' else 'ZIP de CurseForge'), 'upload', 'primary')
        export.clicked.connect(lambda: self.use_preview(export=True))
        actions.addWidget(export)
        actions.addStretch()
        again = button('Volver a generar', 'refresh', 'ghost')
        again.clicked.connect(self.start)
        actions.addWidget(again)
        inner.addLayout(actions)
        layout.addWidget(box)

    def _icon(self, item, mod):
        if mod.get('logo'):
            self.win.images.fetch(mod['logo'], QSize(28, 28), lambda pixmap, i=item: self._set_icon(i, pixmap))

    @staticmethod
    def _set_icon(item, pixmap):
        try:
            item.setIcon(0, QIcon(pixmap))
        except RuntimeError:
            pass

    def _open_item(self, item, _column):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        mod = next((m for m in (self.result or {}).get('mods', []) if m['key'] == key), None)
        if mod:
            self.win.open_details(mod)

    def preview_selection(self):
        keys = set()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                child = group.child(j)
                if child.checkState(0) == Qt.CheckState.Checked and child.data(0, Qt.ItemDataRole.UserRole):
                    keys.add(child.data(0, Qt.ItemDataRole.UserRole))
        return [m for m in self.result['mods'] if m['key'] in keys]

    def use_preview(self, export):
        mods = self.preview_selection()
        if not mods:
            self.win.toast('No hay mods seleccionados', tone='warning')
            return
        pack = self.win.pack
        if len(pack):
            answer = QMessageBox.question(self, 'Mi modpack ya tiene mods',
                                          f'Mi modpack contiene {len(pack)} mods. ¿Reemplazarlos por esta propuesta? '
                                          '(«No» añade la propuesta a los mods actuales.)',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                                          QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Yes:
                pack.clear()
        for mod in mods:
            pack.add(mod)
        pack.description = self.prompt.toPlainText().strip()[:500]
        if pack.name in ('', 'Mi modpack'):
            pack.name = (self.result['brief']['summary'][:60].rstrip('. ') or 'Modpack con IA')
        self.win.pack_changed.emit()
        self.win.navigate('pack')
        if export:
            self.win.pages['pack'].export(self.source.current)

    def refresh_states(self):
        if self.results_stack.currentWidget() is self.grid:
            self.grid.refresh_states(self.win.state_of)
