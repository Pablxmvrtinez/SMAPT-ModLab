"""Panel «Configurar IA»: requisitos, descarga verificada del modelo, instalación del motor y prueba."""
import time

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from modlab import ai_setup
from modlab.local_ai import LocalAI
from modlab.ui.widgets import Badge, button, card, label

READY_SCHEMA = {'type': 'object', 'properties': {'ready': {'type': 'boolean'}, 'language': {'type': 'string', 'maxLength': 20}},
                'required': ['ready', 'language'], 'additionalProperties': False}


class AiSetupPanel(QWidget):
    changed = Signal()

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.process = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box, layout = card(spacing=12)
        outer.addWidget(box)
        head = QHBoxLayout()
        head.addWidget(label('Motor de IA local', 'h2'))
        head.addStretch()
        self.badge = Badge('', 'neutral')
        head.addWidget(self.badge)
        layout.addLayout(head)
        layout.addWidget(label('ModLab usa Qwen3-4B-Instruct (GGUF Q4_K_M) en llama.cpp, dentro de tu equipo: tu descripción '
                               'no se envía a ningún servicio. Necesita el motor llama-cpp-python y el modelo (2,5 GB).',
                               'muted', wrap=True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        self.rows = {}
        for row, (key, title) in enumerate((('engine', 'Motor'), ('model', 'Modelo'), ('memory', 'Memoria'), ('accel', 'Aceleración'))):
            grid.addWidget(label(title, 'metricLabel'), row, 0)
            state = Badge('', 'neutral')
            detail = label('', 'text2', wrap=True)
            grid.addWidget(state, row, 1)
            grid.addWidget(detail, row, 2)
            self.rows[key] = (state, detail)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.message = label('', 'muted', wrap=True)
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.download = button('Descargar modelo (2,5 GB)', 'download', 'primary')
        self.download.clicked.connect(self.start_download)
        actions.addWidget(self.download)
        self.install = button('Instalar motor', 'plug')
        self.install.setToolTip('pip install ' + ai_setup.ENGINE_PACKAGE + ' (compila llama.cpp; tarda varios minutos)')
        self.install.clicked.connect(self.install_engine)
        actions.addWidget(self.install)
        self.test = button('Probar la IA', 'sparkles')
        self.test.clicked.connect(self.test_ai)
        actions.addWidget(self.test)
        self.stop = button('Cancelar', 'x', 'ghost')
        self.stop.clicked.connect(self.cancel)
        self.stop.hide()
        actions.addWidget(self.stop)
        actions.addStretch()
        refresh = button('Actualizar', 'refresh', 'ghost')
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.hide()
        layout.addWidget(self.log)
        outer.addStretch()
        self.handle = None
        self.refresh()

    def refresh(self):
        info = ai_setup.status()
        self.info = info
        engine = info['engine']
        self.badge.set('Lista' if info['ready'] else 'Pendiente', 'success' if info['ready'] else 'warning')
        self._row('engine', ('Correcto', 'success') if engine['installed'] else ('Falta', 'danger'),
                  f"llama-cpp-python {engine['version']}" if engine['installed'] else
                  (engine.get('error') or 'No instalado. ' + ('Pulsa «Instalar motor».' if info['can_install_engine'] else
                   'Usa la edición con IA de ModLab o, desde el código: pip install -r requirements-ai.txt')))
        partial = f" · descarga parcial: {ai_setup.bytes_text(info['partial_bytes'])} (se reanudará)" if info['partial_bytes'] else ''
        self._row('model', ('Correcto', 'success') if info['model'] else ('Falta', 'danger'),
                  (('Incluido en el paquete: ' if info['model_bundled'] else 'Descargado: ') + info['model']) if info['model'] else
                  f"Falta {ai_setup.MODEL_FILE} (2,5 GB). Se guardará en {info['download_target']}{partial}")
        enough = info['ram_total'] >= info['ram_needed']
        self._row('memory', ('Correcto', 'success') if enough else ('Atención', 'warning'),
                  f"{ai_setup.bytes_text(info['ram_total'])} en total, {ai_setup.bytes_text(info['ram_available'])} libres "
                  f"· necesita unos {ai_setup.bytes_text(info['ram_needed'])} libres mientras trabaja")
        self._row('accel', ('GPU', 'success') if engine.get('gpu') else ('CPU', 'neutral'),
                  'El modelo se carga en la tarjeta gráfica.' if engine.get('gpu') else
                  'Sin aceleración por GPU en este motor: una propuesta completa tarda varios minutos.')
        busy = self.handle is not None or self.process is not None
        self.download.setVisible(not info['model'])
        self.download.setEnabled(not busy)
        self.install.setVisible(not engine['installed'] and info['can_install_engine'])
        self.install.setEnabled(not busy)
        self.test.setEnabled(info['ready'] and not busy)
        self.changed.emit()

    def _row(self, key, state_and_tone, text):
        state, detail = self.rows[key]
        state.set(*state_and_tone)
        detail.setText(text)

    def _busy(self, value):
        self.stop.setVisible(value)
        self.progress.setVisible(value)
        if value:
            self.progress.setRange(0, 0)

    def start_download(self):
        def progress(message, fraction):
            self.message.setText(message)
            if fraction >= 0:
                self.progress.setRange(0, 1000)
                self.progress.setValue(int(fraction * 1000))

        def done(path):
            self.handle = None
            self._busy(False)
            self.message.setText('Modelo descargado y verificado con SHA-256.')
            self.win.toast('Modelo de IA instalado', path, 'success', 6000)
            self.refresh()

        def failed(message):
            self.handle = None
            self._busy(False)
            self.message.setText('✖ ' + message)
            self.refresh()
        self._busy(True)
        self.message.setText('Conectando con Hugging Face…')
        self.handle = self.win.run(lambda report, check: ai_setup.download_model(report, check), done, failed,
                                   key='ai:download', label='Descargando el modelo de IA', owner=self, progress=progress,
                                   toast_errors=False)
        self.refresh()

    def install_engine(self):
        if self.process is not None:
            return
        self.log.clear()
        self.log.show()
        self._busy(True)
        self.message.setText('Instalando llama-cpp-python: se compila llama.cpp y puede tardar varios minutos…')
        process = QProcess(self)
        environment = process.processEnvironment()
        for key, value in ai_setup.install_engine_environment().items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(
            lambda: self.log.appendPlainText(bytes(process.readAllStandardOutput()).decode(errors='replace').rstrip()))
        process.finished.connect(self._installed)
        command = ai_setup.install_engine_command()
        process.start(command[0], command[1:])
        self.process = process
        self.refresh()

    def _installed(self, code, _status):
        self.process = None
        self._busy(False)
        if code == 0:
            self.message.setText('Motor instalado. Reinicia ModLab si «Probar la IA» no lo detecta.')
        else:
            self.message.setText(f'✖ La instalación terminó con el código {code}. Revisa el registro de arriba '
                                 '(hacen falta un compilador de C++ y CMake).')
        self.refresh()

    def test_ai(self):
        def work(report, check):
            ai = LocalAI(context=2048)
            start = time.monotonic()
            answer = ai.complete('Responde en JSON. ready=true y language con el idioma de la petición.',
                                 'Comprueba que funcionas. Responde en español.', READY_SCHEMA, lambda m: report(m), max_tokens=40)
            if answer.get('ready') is not True:
                raise ValueError('La IA respondió, pero no superó la comprobación.')
            return time.monotonic() - start

        def done(seconds):
            self.handle = None
            self._busy(False)
            self.message.setText(f'✔ La IA cargó el modelo y respondió JSON válido en {seconds:.1f} s.')
            self.refresh()

        def failed(message):
            self.handle = None
            self._busy(False)
            self.message.setText('✖ ' + message)
            self.refresh()
        self._busy(True)
        self.message.setText('Cargando el modelo y pidiendo una respuesta de prueba…')
        self.handle = self.win.run(work, done, failed, key='ai:test', label='Probando la IA', owner=self, toast_errors=False)
        self.refresh()

    def cancel(self):
        if self.handle is not None:
            self.handle.cancel()
            self.handle = None
        if self.process is not None:
            self.process.kill()
        self._busy(False)
        self.message.setText('Operación cancelada. La descarga parcial se conserva y se reanudará.')
        self.refresh()

    def ready(self):
        return bool(self.info['ready'])

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.process is not None:
            self.message.setText('La instalación del motor sigue en segundo plano.')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and (self.handle or self.process):
            self.cancel()
        else:
            super().keyPressEvent(event)
