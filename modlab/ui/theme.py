"""Tokens de diseño y hoja de estilos de la edición Acheron (tema oscuro)."""
from PySide6.QtGui import QColor, QPalette

COLORS = {
    'bg': '#0a0c12',
    'sidebar': '#0d1018',
    'surface': '#121621',
    'surface2': '#171c29',
    'elevated': '#1d2333',
    'hover': '#232a3d',
    'border': '#242b3c',
    'border_strong': '#323b52',
    'text': '#e9ecf5',
    'text2': '#b4bcd0',
    'muted': '#7f89a3',
    'accent': '#e3466e',
    'accent_hover': '#f0597f',
    'accent_soft': '#3a1a28',
    'violet': '#8b7cf6',
    'blue': '#5aa9ff',
    'success': '#3ecf8e',
    'warning': '#f5b84a',
    'danger': '#ff5c6c',
    'curseforge': '#f16436',
    'modrinth': '#1bd96a',
}

FONT = "'Inter', 'Segoe UI Variable Text', 'Segoe UI', 'Noto Sans', 'Cantarell', sans-serif"
RADIUS = 10


def stylesheet(c=COLORS):
    return f"""
* {{ outline: none; }}
QWidget {{ background: transparent; color: {c['text']}; font-family: {FONT}; font-size: 13px; }}
QMainWindow, QWidget#root, QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['elevated']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: 6px 8px; border-radius: 6px; }}

/* Navegación lateral */
QFrame#sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
QLabel#brand {{ font-size: 17px; font-weight: 800; letter-spacing: 0.5px; }}
QLabel#brandSub {{ color: {c['accent']}; font-size: 10px; font-weight: 800; letter-spacing: 3px; }}
QPushButton#nav {{ background: transparent; border: none; border-radius: 9px; text-align: left; padding: 10px 12px;
    color: {c['text2']}; font-weight: 600; }}
QPushButton#nav:hover {{ background: {c['surface2']}; color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['accent_soft']}; color: #ffd3de; }}
QLabel#navSection {{ color: {c['muted']}; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; padding: 8px 12px 2px 12px; }}
QFrame#statusCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}

/* Barra superior */
QFrame#topbar {{ background: {c['bg']}; border-bottom: 1px solid {c['border']}; }}
QLabel#pageTitle {{ font-size: 21px; font-weight: 800; }}
QLabel#pageSubtitle {{ color: {c['muted']}; }}

/* Tipografía */
QLabel#h1 {{ font-size: 26px; font-weight: 800; }}
QLabel#h2 {{ font-size: 17px; font-weight: 750; }}
QLabel#h3 {{ font-size: 14px; font-weight: 700; }}
QLabel#heroTitle {{ font-size: 32px; font-weight: 850; color: #ffffff; }}
QLabel#eyebrow {{ color: {c['accent']}; font-size: 11px; font-weight: 800; letter-spacing: 2px; }}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#text2 {{ color: {c['text2']}; }}
QLabel#metric {{ font-size: 22px; font-weight: 800; }}
QLabel#metricLabel {{ color: {c['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 750; }}
QLabel#error {{ color: {c['danger']}; }}
QLabel#success {{ color: {c['success']}; }}

/* Tarjetas */
QFrame#card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#hero {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 18px; }}
QFrame#modCard {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#modCard:hover {{ background: {c['surface2']}; border: 1px solid {c['border_strong']}; }}
QFrame#modCard[inPack="true"] {{ border: 1px solid #6b2a3d; }}
QFrame#skeleton {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#toast {{ background: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 12px; }}
QFrame#separator {{ background: {c['border']}; max-height: 1px; min-height: 1px; }}

/* Etiquetas */
QLabel#tag {{ background: {c['surface2']}; color: {c['text2']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 2px 7px; font-size: 11px; }}
QLabel[badge="curseforge"] {{ color: {c['curseforge']}; background: #2a1810; border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 800; letter-spacing: 0.6px; }}
QLabel[badge="modrinth"] {{ color: {c['modrinth']}; background: #0f2619; border-radius: 6px; padding: 2px 7px; font-size: 10px; font-weight: 800; letter-spacing: 0.6px; }}
QLabel[badge="success"] {{ color: {c['success']}; background: #10261d; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700; }}
QLabel[badge="warning"] {{ color: {c['warning']}; background: #2b2110; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700; }}
QLabel[badge="danger"] {{ color: {c['danger']}; background: #2c1418; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700; }}
QLabel[badge="neutral"] {{ color: {c['text2']}; background: {c['surface2']}; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 700; }}

/* Botones */
QPushButton, QToolButton {{ background: {c['surface2']}; border: 1px solid {c['border_strong']}; border-radius: 9px;
    padding: 8px 14px; font-weight: 650; color: {c['text']}; }}
QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; border-color: #46516d; }}
QPushButton:pressed, QToolButton:pressed {{ background: {c['elevated']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: #5b6479; background: {c['surface']}; border-color: {c['border']}; }}
QPushButton#primary {{ background: {c['accent']}; border: 1px solid {c['accent']}; color: #ffffff; }}
QPushButton#primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#primary:disabled {{ background: #3b2430; border-color: #3b2430; color: #8c7480; }}
QPushButton#ghost, QToolButton#ghost {{ background: transparent; border: 1px solid transparent; color: {c['text2']}; }}
QPushButton#ghost:hover, QToolButton#ghost:hover {{ background: {c['surface2']}; color: {c['text']}; }}
QPushButton#danger {{ background: transparent; border: 1px solid #5a2630; color: {c['danger']}; }}
QPushButton#danger:hover {{ background: #2c1418; }}
QPushButton#inPack {{ background: {c['accent_soft']}; border: 1px solid #6b2a3d; color: #ffb4c6; }}
QPushButton#inPack:hover {{ background: #4a1f31; }}
QPushButton#chip {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 14px; text-align: left; }}
QPushButton#chip:hover {{ background: {c['surface2']}; border-color: {c['border_strong']}; }}
QPushButton#segment {{ background: transparent; border: none; border-radius: 7px; padding: 6px 12px; color: {c['text2']}; }}
QPushButton#segment:hover {{ color: {c['text']}; }}
QPushButton#segment:checked {{ background: {c['elevated']}; color: {c['text']}; }}
QFrame#segmented {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 9px; }}
QPushButton#packBadge {{ background: {c['accent_soft']}; border: 1px solid #6b2a3d; color: #ffd3de; border-radius: 9px; }}
QPushButton#packBadge:hover {{ background: #4a1f31; }}

/* Entradas */
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QComboBox {{ background: {c['surface']}; border: 1px solid {c['border_strong']};
    border-radius: 9px; padding: 7px 10px; selection-background-color: {c['accent']}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: #46516d; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c['accent']}; }}
QLineEdit#search {{ padding-left: 8px; font-size: 14px; min-height: 22px; }}
QTextBrowser {{ padding: 14px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c['elevated']}; border: 1px solid {c['border_strong']}; selection-background-color: {c['hover']}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {c['border_strong']}; background: {c['surface']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}

/* Listas y tablas */
QTreeWidget, QTableWidget, QListWidget {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px;
    alternate-background-color: #141927; gridline-color: {c['border']}; }}
QTreeWidget::item, QTableWidget::item, QListWidget::item {{ padding: 6px 4px; border: none; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{ background: {c['hover']}; color: {c['text']}; }}
QTreeWidget::item:hover, QTableWidget::item:hover {{ background: #1b2131; }}
QHeaderView::section {{ background: {c['surface']}; color: {c['muted']}; padding: 8px; border: none;
    border-bottom: 1px solid {c['border']}; font-weight: 700; font-size: 11px; }}

/* Pestañas */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 9px 16px; border: none; border-bottom: 2px solid transparent; font-weight: 650; }}
QTabBar::tab:hover {{ color: {c['text']}; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}

/* Progreso y desplazamiento */
QProgressBar {{ background: {c['surface2']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['accent']}, stop:1 {c['violet']}); }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2b3346; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4560; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2b3346; border-radius: 4px; min-width: 36px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}
QMenu {{ background: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px 8px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['hover']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QMessageBox {{ background: {c['bg']}; }}
QFrame#activity {{ background: {c['sidebar']}; border-top: 1px solid {c['border']}; }}
"""


def apply(app):
    """Estilo Fusion, hoja de estilos y paleta (los enlaces de texto enriquecido usan la paleta global)."""
    app.setStyle('Fusion')
    palette = app.palette()
    for role, color in ((QPalette.ColorRole.Window, COLORS['bg']), (QPalette.ColorRole.Base, COLORS['surface']),
                        (QPalette.ColorRole.Text, COLORS['text']), (QPalette.ColorRole.WindowText, COLORS['text']),
                        (QPalette.ColorRole.ButtonText, COLORS['text']), (QPalette.ColorRole.Highlight, COLORS['accent']),
                        (QPalette.ColorRole.Link, COLORS['accent_hover']), (QPalette.ColorRole.LinkVisited, COLORS['violet'])):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(stylesheet())
