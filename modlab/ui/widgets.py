"""Componentes visuales reutilizables de ModLab."""
from PySide6.QtCore import (QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout,
                               QWidget)

from modlab.ui import icons
from modlab.ui.labels import category_label
from modlab.ui.theme import COLORS

SOURCE_LABELS = {'curseforge': 'CURSEFORGE', 'modrinth': 'MODRINTH'}


# Utilidades ---------------------------------------------------------------------------
def label(text='', name=None, wrap=False, rich=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text='', icon_name=None, kind=None, tooltip='', icon_color=None):
    widget = QPushButton(text)
    if kind:
        widget.setObjectName(kind)
    if icon_name:
        color = icon_color or ('#ffffff' if kind == 'primary' else COLORS['text2'])
        widget.setIcon(icons.icon(icon_name, color, 16))
        widget.setIconSize(QSize(16, 16))
    if tooltip:
        widget.setToolTip(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def tool(icon_name, tooltip, kind='ghost', size=18):
    widget = QToolButton()
    widget.setObjectName(kind)
    widget.setIcon(icons.icon(icon_name, COLORS['text2'], size))
    widget.setIconSize(QSize(size, size))
    widget.setToolTip(tooltip)
    widget.setAccessibleName(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def restyle(widget, name=None, **props):
    if name is not None:
        widget.setObjectName(name)
    for key, value in props.items():
        widget.setProperty(key, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def downloads(value):
    value = int(value or 0)
    if value >= 1_000_000:
        return f'{value / 1_000_000:.1f} M'.replace('.', ',')
    if value >= 1000:
        return f'{value / 1000:.0f} mil'
    return str(value)


def card(name='card', margins=(18, 16, 18, 16), spacing=10, horizontal=False):
    frame = QFrame()
    frame.setObjectName(name)
    layout = (QHBoxLayout if horizontal else QVBoxLayout)(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return frame, layout


class Badge(QLabel):
    def __init__(self, text, kind='neutral'):
        super().__init__(text)
        self.setProperty('badge', kind)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set(self, text, kind):
        self.setText(text)
        restyle(self, badge=kind)


def source_badge(source):
    return Badge(SOURCE_LABELS.get(source, source.upper()), source)


class Separator(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName('separator')


# Controles ------------------------------------------------------------------------------
class Segmented(QFrame):
    changed = Signal(str)

    def __init__(self, options, current=None):
        super().__init__()
        self.setObjectName('segmented')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.buttons = {}
        for key, text in options:
            item = QPushButton(text)
            item.setObjectName('segment')
            item.setCheckable(True)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.clicked.connect(lambda _=False, k=key: self.set_current(k, emit=True))
            layout.addWidget(item)
            self.buttons[key] = item
        self.current = None
        self.set_current(current or options[0][0])

    def set_current(self, key, emit=False):
        if key not in self.buttons:
            return
        changed = key != self.current
        self.current = key
        for name, item in self.buttons.items():
            item.setChecked(name == key)
        if emit and changed:
            self.changed.emit(key)

    def set_text(self, key, text):
        self.buttons[key].setText(text)


class SearchBox(QLineEdit):
    """Buscador con espera de 450 ms tras escribir; Intro busca al instante."""
    search = Signal(str)

    def __init__(self, placeholder):
        super().__init__()
        self.setObjectName('search')
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(icons.icon('search', COLORS['muted'], 18), QLineEdit.ActionPosition.LeadingPosition)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(450)
        self.timer.timeout.connect(lambda: self.search.emit(self.text().strip()))
        self.textEdited.connect(lambda _: self.timer.start())
        self.returnPressed.connect(self._now)
        self.last = None

    def _now(self):
        self.timer.stop()
        self.search.emit(self.text().strip())


class Spinner(QWidget):
    def __init__(self, size=18, color=None):
        super().__init__()
        self.setFixedSize(size, size)
        self.color = QColor(color or COLORS['accent'])
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def showEvent(self, event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.drawArc(r, -self.angle * 16, 270 * 16)
        p.end()


class Shimmer(QVariantAnimation):
    """Una única animación compartida por los esqueletos de carga; se detiene si no queda ninguno."""
    instance = None
    users = 0

    @classmethod
    def attach(cls, widget):
        if cls.instance is None:
            cls.instance = cls()
            cls.instance.setStartValue(0.0)
            cls.instance.setEndValue(1.0)
            cls.instance.setDuration(1400)
            cls.instance.setLoopCount(-1)
        cls.users += 1
        widget.destroyed.connect(cls.detach)
        if cls.instance.state() != QVariantAnimation.State.Running:
            cls.instance.start()
        return cls.instance

    @classmethod
    def detach(cls, *_):
        cls.users = max(0, cls.users - 1)
        if not cls.users and cls.instance is not None:
            cls.instance.stop()


class SkeletonCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName('skeleton')
        self.setFixedHeight(356)
        self.setMinimumWidth(240)
        self.phase = 0.0
        self.animation = Shimmer.attach(self)
        self.animation.valueChanged.connect(self._phase)

    def _phase(self, value):
        self.phase = value
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        gradient = QLinearGradient(-w + self.phase * 3 * w, 0, self.phase * 3 * w, 0)
        gradient.setColorAt(0, QColor('#171c29'))
        gradient.setColorAt(0.5, QColor('#20273a'))
        gradient.setColorAt(1, QColor('#171c29'))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)
        p.drawRoundedRect(QRectF(1, 1, w - 2, 140), 13, 13)
        for y, width in ((164, 0.7), (190, 0.45), (226, 0.9), (246, 0.8), (266, 0.6)):
            p.drawRoundedRect(QRectF(16, y, (w - 32) * width, 12), 6, 6)
        p.drawRoundedRect(QRectF(w - 126, 312, 110, 30), 9, 9)
        p.end()


class EmptyState(QWidget):
    def __init__(self, icon_name, title, text='', actions=(), tone='muted'):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 40, 24, 40)
        layout.setSpacing(10)
        layout.addStretch(1)
        color = {'danger': COLORS['danger'], 'warning': COLORS['warning']}.get(tone, COLORS['muted'])
        art = QLabel()
        art.setPixmap(icons.pixmap(icon_name, color, 44, self.devicePixelRatioF(), 1.6))
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(art)
        heading = label(title, 'h2', wrap=True)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        if text:
            body = label(text, 'muted', wrap=True)
            body.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body.setMinimumWidth(320)
            body.setMaximumWidth(580)
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(body, 10)
            row.addStretch()
            layout.addLayout(row)
        if actions:
            row = QHBoxLayout()
            row.addStretch()
            for text_, callback, kind, icon_name_ in actions:
                item = button(text_, icon_name_, kind)
                item.clicked.connect(callback)
                row.addWidget(item)
            row.addStretch()
            layout.addSpacing(6)
            layout.addLayout(row)
        layout.addStretch(1)


class StatTile(QFrame):
    def __init__(self, icon_name, title, value='—', hint='', accent=None):
        super().__init__()
        self.setObjectName('card')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        badge = QLabel()
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tint = accent or COLORS['accent']
        badge.setStyleSheet(f'background: {QColor(tint).darker(330).name()}; border-radius: 10px;')
        badge.setPixmap(icons.pixmap(icon_name, tint, 20, 2.0))
        layout.addWidget(badge)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = label(title.upper(), 'metricLabel')
        self.value = label(value, 'metric')
        self.hint = label(hint, 'muted', wrap=True)
        text.addWidget(self.title)
        text.addWidget(self.value)
        text.addWidget(self.hint)
        self.hint.setVisible(bool(hint))
        layout.addLayout(text, 1)

    def set(self, value, hint=None):
        self.value.setText(value)
        if hint is not None:
            self.hint.setText(hint)
            self.hint.setVisible(bool(hint))


# Notificaciones y transiciones ------------------------------------------------------------
class Toast(QFrame):
    closed = Signal(object)
    TONES = {'info': ('info', COLORS['blue']), 'success': ('check', COLORS['success']),
             'error': ('alert', COLORS['danger']), 'warning': ('alert', COLORS['warning'])}

    def __init__(self, title, message='', tone='info', timeout=4500):
        super().__init__()
        self.setObjectName('toast')
        self.setFixedWidth(360)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 10, 12)
        layout.setSpacing(12)
        icon_name, color = self.TONES.get(tone, self.TONES['info'])
        mark = QLabel()
        mark.setPixmap(icons.pixmap(icon_name, color, 20, 2.0))
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(mark)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(title, 'h3', wrap=True))
        if message:
            text.addWidget(label(message, 'text2', wrap=True))
        layout.addLayout(text, 1)
        close = tool('x', 'Cerrar aviso', size=14)
        close.clicked.connect(self.dismiss)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)
        self.fade = QPropertyAnimation(self.effect, b'opacity', self)
        self.fade.setDuration(180)
        self.fade.setEndValue(1.0)
        self.fade.start()
        if timeout:
            QTimer.singleShot(timeout, self.dismiss)
        self.dismissing = False

    def dismiss(self):
        if self.dismissing:
            return
        self.dismissing = True
        self.fade.stop()
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(lambda: self.closed.emit(self))
        self.fade.start()


class ToastHost(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(8)
        self.layout_.addStretch()
        self.toasts = []
        self.hide()

    def show_toast(self, title, message='', tone='info', timeout=4500):
        toast = Toast(title, message, tone, timeout)
        toast.closed.connect(self._remove)
        self.toasts.append(toast)
        self.layout_.addWidget(toast)
        while len(self.toasts) > 4:
            self._remove(self.toasts[0])
        self.show()
        self.reposition()
        self.raise_()
        return toast

    def _remove(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
            toast.deleteLater()
        if not self.toasts:
            self.hide()
        QTimer.singleShot(0, self.reposition)

    def reposition(self):
        parent = self.parentWidget()
        if not parent:
            return
        self.adjustSize()
        height = min(self.sizeHint().height(), parent.height() - 40)
        self.setGeometry(parent.width() - 360 - 24, parent.height() - height - 64, 360, height)


class FadeStack(QStackedWidget):
    """Cambio de página con un fundido breve (160 ms)."""

    def fade_to(self, index):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        widget = self.currentWidget()
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b'opacity', widget)
        animation.setDuration(160)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start()


# Imágenes y tarjetas -----------------------------------------------------------------------
class Artwork(QWidget):
    """Paisaje isométrico original dibujado por código para la portada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        p.setClipPath(path)
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor('#141c35'))
        gradient.setColorAt(1, QColor('#3a1426'))
        p.fillRect(self.rect(), gradient)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(34):
            x = (i * 97 + 47) % max(1, w)
            y = (i * 29 + 13) % max(1, int(h * .7))
            p.setBrush(QColor('#6774a5') if i % 3 else QColor('#e3466e'))
            p.drawEllipse(QRectF(x, y, 2, 2))
        p.setBrush(QColor('#2e4f8f'))
        p.drawEllipse(QRectF(w * .7, h * .08, 80, 80))
        tile = max(12, min(26, w / 22))
        cx, cy = w * .62, h * .58

        def poly(coords, paint):
            p.setBrush(QColor(paint))
            p.drawPolygon(QPolygonF([QPointF(*a) for a in coords]))

        def cube(x, y, z, color):
            sx = cx + (x - y) * tile
            sy = cy + (x + y) * tile * .43 - z * tile * .8
            pts = [(sx, sy), (sx + tile, sy + tile * .43), (sx, sy + tile * .86), (sx - tile, sy + tile * .43)]
            poly(pts, color)
            poly([pts[1], pts[2], (pts[2][0], pts[2][1] + tile * .8), (pts[1][0], pts[1][1] + tile * .8)], '#162544')
            poly([pts[2], pts[3], (pts[3][0], pts[3][1] + tile * .8), (pts[2][0], pts[2][1] + tile * .8)], '#292337')
        for x in range(-3, 4):
            for y in range(-3, 4):
                if abs(x) + abs(y) < 6:
                    cube(x, y, 0, '#385d69' if (x + y) % 3 else '#4c637a')
        for x, y in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            for z in range(1, 4):
                cube(x, y, z, '#69718d' if z < 3 else '#d23e65')
        for x, y in [(0, -2), (1, -2), (-1, -2), (-2, -1), (-2, 0), (-2, 1)]:
            cube(x, y, 1, '#69718d')
        for z in range(1, 3):
            cube(0, 0, z, '#3d69ad')
        p.end()


class Cover(QWidget):
    """Imagen recortada para llenar el área, con esquinas redondeadas y marcador mientras carga."""

    def __init__(self, title, url, images, height=140, radius=13, top_only=True, width=420, parent=None):
        super().__init__(parent)
        self.title = title
        self.pixmap = None
        self.radius = radius
        self.top_only = top_only
        self.setFixedHeight(height)
        if url and images:
            images.fetch(url, QSize(width, height), self.loaded)

    def loaded(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        path = QPainterPath()
        r = self.radius
        if self.top_only:
            path.moveTo(0, h)
            path.lineTo(0, r)
            path.quadTo(0, 0, r, 0)
            path.lineTo(w - r, 0)
            path.quadTo(w, 0, w, r)
            path.lineTo(w, h)
            path.closeSubpath()
        else:
            path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setClipPath(path)
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor('#1c2a48'))
        gradient.setColorAt(1, QColor('#3d1f33'))
        p.fillRect(self.rect(), gradient)
        if self.pixmap is not None and not self.pixmap.isNull():
            source = self.pixmap
            scale = max(w / source.width(), h / source.height())
            sw, sh = w / scale, h / scale
            p.drawPixmap(QRectF(0, 0, w, h), source, QRectF((source.width() - sw) / 2, (source.height() - sh) / 2, sw, sh))
            shade = QLinearGradient(0, h * .45, 0, h)
            shade.setColorAt(0, QColor(0, 0, 0, 0))
            shade.setColorAt(1, QColor(10, 12, 18, 150))
            p.fillRect(self.rect(), shade)
        else:
            p.setPen(QColor('#6f84b3'))
            p.setFont(QFont(self.font().family(), 30, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, ''.join(w_[:1] for w_ in self.title.split()[:2]).upper())
        p.end()


class Logo(QWidget):
    def __init__(self, title, url, images, size=48, parent=None):
        super().__init__(parent)
        self.title = title
        self.pixmap = None
        self.setFixedSize(size, size)
        if url and images:
            images.fetch(url, QSize(size, size), self.loaded)

    def loaded(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        p.fillPath(path, QColor('#1d2333'))
        p.setClipPath(path)
        if self.pixmap is not None and not self.pixmap.isNull():
            p.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            p.setPen(QColor('#8a9bc4'))
            p.setFont(QFont(self.font().family(), max(9, self.width() // 3), QFont.Weight.Bold))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.title[:1].upper())
        p.setClipping(False)
        p.setPen(QPen(QColor('#0a0c12'), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()


class ModCard(QFrame):
    toggled = Signal(object)
    details = Signal(object)
    HEIGHT = 356

    def __init__(self, mod, images, state='add', parent=None):
        super().__init__(parent)
        self.mod = mod
        self.setObjectName('modCard')
        self.setFixedHeight(self.HEIGHT)
        self.setMinimumWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(mod['title'])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 14)
        layout.setSpacing(0)
        cover_url = next((u for u in mod.get('thumbnails') or mod.get('screenshots') or [] if u), None) or mod.get('logo', '')
        self.cover = Cover(mod['title'], cover_url, images)
        layout.addWidget(self.cover)
        self.logo = Logo(mod['title'], mod.get('logo', ''), images, 48, self)
        badge = source_badge(mod.get('source', 'curseforge'))
        badge.setParent(self)
        badge.adjustSize()
        badge.move(12, 12)
        badge.raise_()
        body = QVBoxLayout()
        body.setContentsMargins(14, 8, 14, 0)
        body.setSpacing(6)
        meta = QHBoxLayout()
        meta.addSpacing(54)
        stats = label('↓ ' + downloads(mod.get('downloads')) + ('  ·  ' + mod['updated'] if mod.get('updated') else ''), 'muted')
        meta.addWidget(stats, 1, Qt.AlignmentFlag.AlignRight)
        body.addLayout(meta)
        title = label(mod['title'], 'cardTitle', wrap=True)
        title.setFixedHeight(40)
        title.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.addWidget(title)
        authors = ', '.join(mod.get('authors', [])[:2])
        tags = QHBoxLayout()
        tags.setSpacing(5)
        if mod.get('role'):
            tags.addWidget(Badge('IA · ' + mod['role'][:24], 'warning'))
        for cat in mod.get('categories', [])[:2 if not mod.get('role') else 1]:
            tag = label(category_label(cat['name']), 'tag')
            tag.setMaximumWidth(150)
            tags.addWidget(tag)
        tags.addStretch()
        body.addLayout(tags)
        text = mod.get('reason') or mod.get('description', '')
        desc = label(text, 'muted', wrap=True)
        desc.setFixedHeight(54)
        desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        desc.setToolTip(text if len(text) > 90 else '')
        body.addWidget(desc)
        body.addStretch()
        footer = QHBoxLayout()
        footer.addWidget(label(('por ' + authors) if authors else '', 'muted'), 1)
        self.button = button('')
        self.button.clicked.connect(lambda: self.toggled.emit(self.mod))
        footer.addWidget(self.button)
        body.addLayout(footer)
        layout.addLayout(body, 1)
        self.set_state(state)

    def set_state(self, state):
        texts = {'add': ('Añadir', 'plus', 'primary', True), 'busy': ('Añadiendo…', None, None, False),
                 'in': ('En el pack', 'check', 'inPack', True)}
        text, icon_name, kind, enabled = texts[state]
        self.state = state
        self.button.setText(text)
        self.button.setIcon(icons.icon(icon_name, '#ffffff' if kind == 'primary' else '#ffb4c6', 16) if icon_name else icons.icon('clock', COLORS['muted'], 16))
        self.button.setEnabled(enabled)
        self.button.setToolTip('Quitar del pack' if state == 'in' else '')
        restyle(self.button, kind or '')
        restyle(self, inPack='true' if state == 'in' else 'false')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.logo.move(14, self.cover.height() - 22)
        self.logo.raise_()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.details.emit(self.mod)
        super().mouseReleaseEvent(event)


class CardGrid(QScrollArea):
    """Rejilla adaptable: el número de columnas depende del ancho disponible."""
    toggled = Signal(object)
    details = Signal(object)
    MIN_WIDTH = 250

    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.images = images
        self.cards = []
        self.items = []
        self.columns = 0
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 2, 6, 8)
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self.container)

    def _replace(self, widgets):
        for widget in self.items:
            self.grid.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self.items = widgets
        self.cards = [w for w in widgets if isinstance(w, ModCard)]
        self.columns = 0
        self.reflow()
        self.verticalScrollBar().setValue(0)

    def show_mods(self, mods, state_of=lambda mod: 'add'):
        cards = []
        for mod in mods:
            item = ModCard(mod, self.images, state_of(mod))
            item.toggled.connect(self.toggled.emit)
            item.details.connect(self.details.emit)
            cards.append(item)
        self._replace(cards)

    def show_loading(self, count=8):
        self._replace([SkeletonCard() for _ in range(count)])

    def show_message(self, widget):
        self._replace([widget])

    def refresh_states(self, state_of):
        for item in self.cards:
            state = state_of(item.mod)
            if state != item.state:
                item.set_state(state)

    def reflow(self):
        if len(self.items) == 1 and not self.cards and not isinstance(self.items[0], SkeletonCard):
            if self.columns != -1:
                self.columns = -1
                for i in range(self.grid.columnCount()):
                    self.grid.setColumnStretch(i, 1 if i == 0 else 0)
                self.grid.addWidget(self.items[0], 0, 0, 1, 1)
            return
        width = self.viewport().width() - 6
        columns = max(1, (width + 16) // (self.MIN_WIDTH + 16))
        if columns == self.columns:
            return
        self.columns = columns
        for i in range(self.grid.columnCount()):
            self.grid.setColumnStretch(i, 0)
        for i in range(columns):
            self.grid.setColumnStretch(i, 1)
        for i, widget in enumerate(self.items):
            self.grid.addWidget(widget, i // columns, i % columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()
