"""Carga asíncrona de imágenes con caché.

CurseForge: solo memoria durante la sesión (sus términos no permiten guardar datos de la API).
Modrinth: memoria y caché HTTP en disco, limitada a 150 MB.
"""
from collections import OrderedDict

from PySide6.QtCore import QObject, QSize, Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest

from modlab import USER_AGENT, paths

MEMORY_ITEMS = 400


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


class ImageLoader(QObject):
    def __init__(self, parent=None, disk=True):
        super().__init__(parent)
        self.memory = OrderedDict()
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
        image = QImage()
        if reply.error() == reply.NetworkError.NoError:
            image.loadFromData(bytes(reply.readAll()))
        reply.deleteLater()
        waiting = self.pending.pop(url, [])
        if image.isNull():
            return
        for size, callback in waiting:
            pixmap = self._scaled(image, size)
            self.memory[(url, size.width(), size.height())] = pixmap
            while len(self.memory) > MEMORY_ITEMS:
                self.memory.popitem(last=False)
            try:
                callback(pixmap)
            except RuntimeError:
                pass  # El widget de destino ya no existe (cambio de página).

    @staticmethod
    def _scaled(image, size):
        # Escala a la resolución real de pantalla (2×) para no guardar imágenes enormes en memoria.
        target = QSize(size.width() * 2, size.height() * 2)
        if image.width() > target.width() or image.height() > target.height():
            image = image.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
        pixmap = QPixmap.fromImage(image)
        return pixmap

    def clear(self):
        self.memory.clear()
        if self.disk is not None:
            self.disk.clear()

    def disk_size(self):
        return self.disk.cacheSize() if self.disk is not None else 0
