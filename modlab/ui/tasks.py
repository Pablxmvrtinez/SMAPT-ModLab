"""Tareas en segundo plano con QThreadPool: la red y la IA nunca bloquean la interfaz.

Cada tarea recibe ``progress(mensaje, fracción)`` y ``check()``; ambas lanzan ``Cancelled``
si se canceló. Una tarea con ``key`` sustituye a la anterior con la misma clave (por ejemplo,
una búsqueda nueva descarta los resultados de la búsqueda previa).
"""
import threading

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from modlab import logs
from modlab.errors import Cancelled

log = logs.get('tasks')


class _Signals(QObject):
    progress = Signal(str, float)
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Handle:
    def __init__(self, label):
        self.label = label
        self.cancel_event = threading.Event()
        self.running = True

    def cancel(self):
        self.cancel_event.set()

    @property
    def cancelled(self):
        return self.cancel_event.is_set()


class _Job(QRunnable):
    def __init__(self, fn, handle, signals):
        super().__init__()
        self.fn, self.handle, self.signals = fn, handle, signals
        self.setAutoDelete(True)

    def check(self):
        if self.handle.cancelled:
            raise Cancelled()

    def report(self, message, fraction=-1.0):
        self.check()
        self.signals.progress.emit(str(message), float(fraction))

    def run(self):
        try:
            result = self.fn(self.report, self.check)
            if not self.handle.cancelled:
                self.signals.done.emit(result)
        except Cancelled:
            pass
        except ValueError as exc:  # CatalogError y validaciones con mensaje para el usuario
            if not self.handle.cancelled:
                self.signals.failed.emit(str(exc))
        except Exception:  # noqa: BLE001 - se registra y se muestra un mensaje genérico
            log.exception('Fallo inesperado en la tarea «%s»', self.handle.label)
            if not self.handle.cancelled:
                self.signals.failed.emit('Error inesperado. Los detalles se guardaron en el registro de ModLab.')
        finally:
            self.signals.finished.emit()


class TaskRunner(QObject):
    """Lanza trabajos y entrega sus resultados en el hilo de la interfaz."""

    activity = Signal()

    def __init__(self, parent=None, threads=4):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(threads)
        self.jobs = {}
        self.keys = {}

    def run(self, fn, done=None, failed=None, progress=None, owner=None, key=None, label='', visible=True):
        if key and key in self.keys:
            self.keys[key].cancel()
        handle = Handle(label or key or 'tarea')
        handle.visible = visible
        signals = _Signals()

        def alive():
            return owner is None or shiboken6.isValid(owner)

        def on_done(result):
            if done and alive() and not handle.cancelled:
                try:
                    done(result)
                except Exception:  # noqa: BLE001
                    log.exception('Error al mostrar el resultado de «%s»', handle.label)
                    if failed and alive():
                        failed('No se pudo mostrar el resultado. Detalles en el registro.')

        def on_failed(message):
            if failed and alive() and not handle.cancelled:
                failed(message)

        def on_progress(message, fraction):
            if progress and alive() and not handle.cancelled:
                progress(message, fraction)

        def on_finished():
            handle.running = False
            self.jobs.pop(id(handle), None)
            if key and self.keys.get(key) is handle:
                del self.keys[key]
            self.activity.emit()

        signals.done.connect(on_done)
        signals.failed.connect(on_failed)
        signals.progress.connect(on_progress)
        signals.finished.connect(on_finished)
        self.jobs[id(handle)] = (handle, signals)
        if key:
            self.keys[key] = handle
        self.pool.start(_Job(fn, handle, signals))
        self.activity.emit()
        return handle

    def visible_jobs(self):
        return [h for h, _ in self.jobs.values() if getattr(h, 'visible', True) and not h.cancelled]

    def busy(self, key):
        handle = self.keys.get(key)
        return bool(handle and handle.running and not handle.cancelled)

    def cancel_all(self):
        for handle, _ in list(self.jobs.values()):
            handle.cancel()

    def shutdown(self, timeout_ms=4000):
        self.cancel_all()
        return self.pool.waitForDone(timeout_ms)
