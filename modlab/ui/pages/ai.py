"""Crear con IA: el modelo local interpreta la experiencia y propone mods del catálogo elegido."""
from PySide6.QtWidgets import QHBoxLayout, QSpinBox, QTextEdit, QVBoxLayout, QWidget

from modlab.intelligence import ExperienceDesigner, plan_text
from modlab.sources import LABELS as SOURCE_LABELS
from modlab.ui.pages import plain_page
from modlab.ui.widgets import Badge, CardGrid, EmptyState, Segmented, button, card, label

EXAMPLES = [
    ('Chill con amigos', 'Construir y decorar con amigos, cocinar, explorar a nuestro ritmo y algún jefe opcional. Prioriza rendimiento.'),
    ('Fábricas y máquinas', 'Quiero muchas fábricas, automatización, energía y máquinas. Sin magia y con buena optimización.'),
    ('Magia y aventura', 'Quiero progresión de magia, hechizos, exploración, mazmorras y jefes, sin tecnología industrial.'),
    ('Construcción creativa', 'Quiero mucha variedad de bloques, muebles y herramientas para construir. Sin jefes ni combates extra.'),
]


class AiPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.proposal = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        page, v = plain_page()
        outer.addWidget(page)

        box, layout = card(spacing=12)
        head = QHBoxLayout()
        head.addWidget(label('Describe cómo quieres jugar', 'h2'))
        head.addStretch()
        self.ai_badge = Badge('', 'neutral')
        head.addWidget(self.ai_badge)
        layout.addLayout(head)
        layout.addWidget(label('El modelo local interpreta ritmo, actividades y exclusiones, busca en el catálogo y explica '
                               'cada propuesta. No envía tu texto a ningún servicio externo.', 'muted', wrap=True))
        self.prompt = QTextEdit()
        self.prompt.setFixedHeight(96)
        self.prompt.setPlaceholderText('Quiero construir tranquilo, explorar con amigos, algún jefe opcional y buen rendimiento en un PC modesto…')
        self.prompt.setPlainText(EXAMPLES[0][1])
        layout.addWidget(self.prompt)
        chips = QHBoxLayout()
        for title, text in EXAMPLES:
            chip = button(title, kind='ghost')
            chip.clicked.connect(lambda _=False, t=text: self.prompt.setPlainText(t))
            chips.addWidget(chip)
        chips.addStretch()
        layout.addLayout(chips)
        controls = QHBoxLayout()
        controls.addWidget(label('Catálogo', 'muted'))
        self.source = Segmented([('curseforge', 'CurseForge'), ('modrinth', 'Modrinth')], win.default_source())
        controls.addWidget(self.source)
        controls.addSpacing(12)
        controls.addWidget(label('Hasta', 'muted'))
        self.limit = QSpinBox()
        self.limit.setRange(1, 400)
        self.limit.setValue(60)
        controls.addWidget(self.limit)
        controls.addWidget(label('mods', 'muted'))
        controls.addStretch()
        self.start = button('Proponer mods', 'sparkles', 'primary')
        self.start.clicked.connect(self.propose)
        controls.addWidget(self.start)
        layout.addLayout(controls)
        v.addWidget(box)

        self.summary = label('', 'text2', wrap=True)
        self.summary_card, summary_layout = card(spacing=6)
        summary_layout.addWidget(label('INTERPRETACIÓN', 'eyebrow'))
        summary_layout.addWidget(self.summary)
        self.summary_card.hide()
        v.addWidget(self.summary_card)

        self.grid = CardGrid(win.images)
        self.grid.toggled.connect(win.toggle_mod)
        self.grid.details.connect(win.open_details)
        self.grid.show_message(EmptyState('sparkles', 'Las propuestas aparecerán aquí',
                                          'Cada mod incluye el motivo por el que encaja y un límite o incertidumbre.'))
        v.addWidget(self.grid, 1)
        bottom = QHBoxLayout()
        self.count = label('', 'muted')
        bottom.addWidget(self.count, 1)
        self.add_all = button('Añadir toda la propuesta', 'plus')
        self.add_all.setEnabled(False)
        self.add_all.clicked.connect(self.add_proposal)
        bottom.addWidget(self.add_all)
        v.addLayout(bottom)
        win.target_changed.connect(self.reset)
        self.update_badge()

    def update_badge(self):
        available = self.win.ai.available()
        self.ai_badge.set('IA local lista' if available else 'IA no incluida en esta edición', 'success' if available else 'warning')
        self.start.setToolTip('' if available else 'Esta instalación no incluye el modelo local. Usa la edición completa.')

    def reset(self):
        self.proposal = []
        self.add_all.setEnabled(False)
        self.count.setText('')

    def propose(self):
        phrase = self.prompt.toPlainText().strip()
        if not phrase:
            self.win.toast('Describe primero cómo quieres jugar', tone='warning')
            return
        if not self.win.ai.available():
            self.win.toast('La IA local no está incluida', 'Instala la edición completa o ejecuta scripts/fetch_model.py '
                           'con llama-cpp-python instalado. Explorar mods funciona sin IA.', 'warning', 7000)
            return
        source = self.source.current
        catalog = self.win.catalogs.get(source)
        if not catalog.available():
            self.win.toast(f'{SOURCE_LABELS[source]} no está conectado', 'Configúralo en Ajustes o elige Modrinth.', 'warning')
            return
        mc, loader = self.win.target()
        limit = self.limit.value()
        designer = ExperienceDesigner(catalog, self.win.ai)
        self.reset()
        self.grid.show_loading(6)
        self.summary_card.hide()
        self.start.setEnabled(False)

        def progress(message, fraction):
            if message.startswith('EXPERIENCIA\n'):
                self.summary.setText(message.partition('\n')[2])
                self.summary_card.show()

        def done(result):
            self.start.setEnabled(True)
            self.proposal = result['mods']
            text = plan_text(result['plan'])
            if result['rejected']:
                text += '\n\nDescartados: ' + '; '.join(m['title'] + ': ' + m['reason'] for m in result['rejected'][:8])
            text += '\n\n' + ' '.join(result['warnings'])
            self.summary.setText(text)
            self.summary_card.show()
            self.grid.show_mods(self.proposal, self.win.state_of)
            self.count.setText(f"{len(self.proposal)} propuestas tras evaluar {result['candidate_count']} fichas de "
                               f'{SOURCE_LABELS[source]}. Revisa los motivos antes de añadirlas.')
            self.add_all.setEnabled(bool(self.proposal))

        def failed(message):
            self.start.setEnabled(True)
            self.grid.show_message(EmptyState('alert', 'La IA no pudo completar la propuesta', message, tone='danger'))

        def work(report, check):
            return designer.propose(phrase, mc, loader, limit, lambda m: report(m))
        self.win.run(work, done, failed, key='ai', label='La IA local está trabajando', owner=self,
                     progress=progress, toast_errors=False)

    def add_proposal(self):
        mc, loader = self.win.target()
        added = 0
        for mod in self.proposal:
            if mod.get('minecraft') == mc and mod.get('loader') == loader and mod['key'] not in self.win.pack:
                self.win.pack.add(mod)
                added += 1
        self.win.pack_changed.emit()
        self.win.toast(f'{added} mods añadidos al pack', 'Puedes seguir explorando y ampliar el pack.', 'success')

    def refresh_states(self):
        self.grid.refresh_states(self.win.state_of)
