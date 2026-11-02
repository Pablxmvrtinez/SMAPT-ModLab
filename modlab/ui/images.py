"""Carga asíncrona de imágenes con caché.

CurseForge: solo memoria durante la sesión (sus términos no permiten guardar datos de la API).
Modrinth: memoria y caché HTTP en disco, limitada a 150 MB.
"""
from collections import OrderedDict

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest

from modlab import USER_AGENT, paths

MEMORY_BYTES = 96 * 1024 * 1024  # presupuesto de píxeles decodificados en memoria


def allowed(url):
    parsed = QUrl(url)
    host = parsed.host()
    if parsed.scheme() != 'https':
        return None
    if host == 'forgecdn.net' or host.endswith('.forgecdn.net'):
        return 'curseforge'
    if host == 'cdn.modrinth.com':
        return 'modrinth'
    return None


class _Decoded(QObject):
    ready = Signal(str, object)


class _Decode(QRunnable):
    """Decodifica y escala fuera del hilo de la interfaz (QImage es seguro entre hilos; QPixmap no)."""

    def __init__(self, url, data, sizes, signal):
        super().__init__()
        self.url, self.data, self.sizes, self.signal = url, data, sizes, signal

    def run(self):
        image = QImage()
        image.loadFromData(self.data)
        results = [] if image.isNull() else [(size, ImageLoader.scaled_image(image, size)) for size in self.sizes]
        self.signal.ready.emit(self.url, results)


class ImageLoader(QObject):
    def __init__(self, parent=None, disk=True):
        super().__init__(parent)
        screen = QGuiApplication.primaryScreen()
        ImageLoader.RATIO = min(2.0, max(1.0, screen.devicePixelRatio() if screen else 1.0))
        self.decoder = QThreadPool(self)
        self.decoder.setMaxThreadCount(2)
        self.decoded = _Decoded(self)
        self.decoded.ready.connect(self._deliver)
        self.memory = OrderedDict()
        self.memory_bytes = 0
        self.pending = {}
        self.plain = QNetworkAccessManager(self)
        self.cached = QNetworkAccessManager(self)
        self.disk = None
        if disk:
            self.disk = QNetworkDiskCache(self)
            self.disk.setCacheDirectory(str(paths.cache_dir() / 'images'))
            self.disk.setMaximumCacheSize(150 * 1024 * 1024)
            self.cached.setCache(self.disk)

    def fetch(self, url, size, callback):
        """Entrega un QPixmap escalado a ``size`` (QSize lógico) mediante ``callback``."""
        kind = allowed(url or '')
        if not kind:
            return
        size = QSize(size)
        key = (url, size.width(), size.height())
        hit = self.memory.get(key)
        if hit is not None:
            self.memory.move_to_end(key)
            callback(hit)
            return
        if url in self.pending:
            self.pending[url].append((size, callback))
            return
        self.pending[url] = [(size, callback)]
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(15000)
        request.setRawHeader(b'User-Agent', USER_AGENT.encode())
        manager = self.plain
        if kind == 'modrinth' and self.disk is not None:
            manager = self.cached
            request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                                 QNetworkRequest.CacheLoadControl.PreferCache)
        reply = manager.get(request)
        reply.setReadBufferSize(12 * 1024 * 1024)
        reply.finished.connect(lambda: self._finished(url, reply))

    def _finished(self, url, reply):
        ok = reply.error() == reply.NetworkError.NoError
        data = bytes(reply.readAll()) if ok else b''
        reply.deleteLater()
        if not data:
            self.pending.pop(url, None)
            return
        sizes = list({(s.width(), s.height()): s for s, _ in self.pending.get(url, [])}.values())
        self.decoder.start(_Decode(url, data, sizes, self.decoded))

    def _deliver(self, url, results):
        waiting = self.pending.pop(url, [])
        pixmaps = {}
        for size, image in results:
            pixmap = QPixmap.fromImage(image)
            pixmaps[(size.width(), size.height())] = pixmap
            self._remember((url, size.width(), size.height()), pixmap)
        for size, callback in waiting:
            pixmap = pixmaps.get((size.width(), size.height()))
            if pixmap is None:
                continue
            try:
                callback(pixmap)
            except RuntimeError:
                pass  # El widget de destino ya no existe (cambio de página).

    def _remember(self, key, pixmap):
        old = self.memory.pop(key, None)
        if old is not None:
            self.memory_bytes -= _cost(old)
        self.memory[key] = pixmap
        self.memory_bytes += _cost(pixmap)
        while self.memory_bytes > MEMORY_BYTES and len(self.memory) > 1:
            _, evicted = self.memory.popitem(last=False)
            self.memory_bytes -= _cost(evicted)

    RATIO = None

    @classmethod
    def scaled_image(cls, image, size):
        # Escala a la densidad real de la pantalla para no guardar imágenes enormes en memoria.
        ratio = cls.RATIO or 1.0
        target = QSize(round(size.width() * ratio), round(size.height() * ratio))
        if image.width() > target.width() or image.height() > target.height():
            image = image.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
        return image

    def clear(self):
        self.memory.clear()
        self.memory_bytes = 0
        if self.disk is not None:
            self.disk.clear()

    def disk_size(self):
        return self.disk.cacheSize() if self.disk is not None else 0


def _cost(pixmap):
    return pixmap.width() * pixmap.height() * 4
