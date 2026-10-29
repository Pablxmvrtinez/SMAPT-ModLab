"""Páginas de la ventana principal. Cada página recibe la ventana (``win``) como contexto común."""
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


def scroll_page(margins=(28, 22, 28, 28), spacing=18):
    """Devuelve (área desplazable, layout interior)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget()
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    area.setWidget(inner)
    return area, layout


def plain_page(margins=(28, 22, 28, 18), spacing=14):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return page, layout
