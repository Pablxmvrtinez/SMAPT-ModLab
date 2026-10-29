"""S.M.A.P.T. ModLab: diseñador de modpacks de Minecraft para CurseForge y Modrinth.

    python app.py              abre la aplicación
    python app.py --smoke      abre y cierra la ventana (comprobación de arranque)
    python app.py --verify-ai  comprueba la IA local integrada
"""
import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from modlab import APP_NAME, ORGANIZATION, __version__, logs, paths


def splash_pixmap():
    from modlab.ui import icons
    pixmap = QPixmap(560, 300)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, 560, 300)
    gradient.setColorAt(0, QColor('#121a30'))
    gradient.setColorAt(1, QColor('#3a1426'))
    p.setBrush(gradient)
    p.setPen(QColor('#2b3346'))
    p.drawRoundedRect(QRectF(0.5, 0.5, 559, 299), 18, 18)
    p.drawPixmap(40, 52, icons.pixmap('cube', '#e3466e', 56, 1.0, 2.0))
    p.setPen(QColor('#ffffff'))
    p.setFont(QFont('Sans Serif', 30, QFont.Weight.Black))
    p.drawText(116, 92, 'S.M.A.P.T.')
    p.setPen(QColor('#e3466e'))
    p.setFont(QFont('Sans Serif', 11, QFont.Weight.Bold))
    p.drawText(118, 116, 'M O D L A B   ·   A C H E R O N')
    p.setPen(QColor('#b4bcd0'))
    p.setFont(QFont('Sans Serif', 11))
    p.drawText(40, 200, 'Modpacks de Minecraft con CurseForge, Modrinth e IA local')
    p.setPen(QColor('#7f89a3'))
    p.drawText(40, 262, f'v{__version__}')
    p.end()
    return pixmap


def verify_ai():
    from modlab.local_ai import LocalAI
    result = LocalAI().complete('Devuelve un objeto JSON con ready igual a true.', {},
                                {'type': 'object', 'properties': {'ready': {'type': 'boolean'}},
                                 'required': ['ready'], 'additionalProperties': False})
    if result.get('ready') is not True:
        raise SystemExit('La IA integrada no superó la comprobación.')
    print('IA integrada verificada.')
    return 0


def main():
    log_file = logs.setup()
    if '--verify-ai' in sys.argv:
        return verify_ai()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationVersion(__version__)
    from modlab.ui import theme
    theme.apply(app)
    icon = paths.resource_root() / 'assets/icon.svg'
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    splash = QSplashScreen(splash_pixmap())
    splash.show()
    splash.showMessage('Preparando la interfaz…', Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, QColor('#b4bcd0'))
    app.processEvents()
    from modlab.ui.window import ModLab
    logs.get('app').info('ModLab %s iniciado (registro en %s)', __version__, log_file)
    win = ModLab()
    win.show()
    splash.finish(win)
    if '--smoke' in sys.argv:
        QTimer.singleShot(1500, win.close)
        QTimer.singleShot(1600, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
