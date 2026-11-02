"""Construye el paquete portable en el sistema de destino (Linux o Windows).

    python build_portable.py              edición pública: sin claves y sin IA (la que se publica)
    python build_portable.py --with-ai    edición con IA local (modelo + llama-cpp-python, unos 2,5 GB más)

SMAPT_INCLUDE_AI=1 equivale a --with-ai.

SMAPT_CATALOG_URL (opcional) se guarda en app-config.json para que el paquete use la pasarela del
desarrollador. La clave de CurseForge nunca se incluye: el script se niega a construir si la ve en la URL.
"""
from pathlib import Path
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / 'assets/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
MODEL_SIZE = 2497281120
QT_UNUSED = ['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore', 'PySide6.QtQuick',
             'PySide6.QtQml', 'PySide6.QtMultimedia', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
             'PySide6.QtPdf', 'PySide6.QtBluetooth', 'PySide6.QtPositioning', 'PySide6.QtSql', 'PySide6.QtTest']
LICENSE_PACKAGES = ('requests', 'psutil', 'PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6',
                    'llama-cpp-python', 'numpy', 'diskcache', 'jinja2', 'urllib3', 'certifi',
                    'charset-normalizer', 'idna')


def render_icons(folder):
    """Genera icon.png e icon.ico a partir de assets/icon.svg con Qt (sin dependencias extra)."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ROOT / 'assets/icon.svg'))
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    png, ico = folder / 'icon.png', folder / 'icon.ico'
    image.save(str(png))
    if not image.save(str(ico)):
        ico = None
    return png, ico


def check_config(url):
    if url and ('key' in url.lower() or '@' in url):
        raise SystemExit('SMAPT_CATALOG_URL no debe contener claves ni credenciales.')
    return url


def collect_licenses(folder):
    from importlib.metadata import PackageNotFoundError, distribution
    licenses = folder / 'LICENSES'
    licenses.mkdir(exist_ok=True)
    for name in LICENSE_PACKAGES:
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            continue
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = licenses / name / file.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    # Paquetes Qt de distribuciones Linux instalan licencias fuera de los metadatos de Python.
    for name in ('qt6-base', 'qt6-svg', 'qt6-wayland', 'qt6-imageformats', 'pyside6', 'shiboken6'):
        source = Path('/usr/share/licenses') / name
        if source.is_dir():
            shutil.copytree(source, licenses / name, dirs_exist_ok=True)


def main():
    with_ai = '--with-ai' in sys.argv or os.getenv('SMAPT_INCLUDE_AI') == '1'
    lite = not with_ai
    if with_ai:
        if not MODEL.is_file() or MODEL.stat().st_size != MODEL_SIZE:
            raise SystemExit('Falta el modelo integrado. Ejecuta python scripts/fetch_model.py.')
        if importlib.util.find_spec('llama_cpp') is None:
            raise SystemExit('Instala requirements-ai.txt (llama-cpp-python) para la edición con IA.')
    name = 'SMAPT-ModLab-IA' if with_ai else 'SMAPT-ModLab'
    separator = os.pathsep
    with tempfile.TemporaryDirectory(prefix='smapt-build-') as temp:
        temp = Path(temp)
        config = temp / 'app-config.json'
        config.write_text(json.dumps({'catalog_url': check_config(os.getenv('SMAPT_CATALOG_URL', ''))}))
        png, ico = render_icons(temp)
        args = [sys.executable, '-m', 'PyInstaller', '--onedir', '--windowed', '--name', name, '--noupx', '--noconfirm',
                '--add-data', f'{ROOT / "assets/icon.svg"}{separator}assets',
                '--add-data', f'{config}{separator}.',
                '--distpath', str(ROOT / 'dist'), '--workpath', str(temp / 'work'), '--specpath', str(temp),
                '--log-level', 'WARN', '--exclude-module', 'tkinter']
        for module in QT_UNUSED:
            args += ['--exclude-module', module]
        if ico and sys.platform == 'win32':
            args += ['--icon', str(ico)]
        if lite:
            args += ['--exclude-module', 'llama_cpp']
        else:
            args += ['--collect-all', 'llama_cpp', '--exclude-module', 'llama_cpp.server',
                     '--exclude-module', 'torch', '--exclude-module', 'transformers',
                     '--add-data', f'{MODEL}{separator}assets/models',
                     '--add-data', f'{ROOT / "assets/models/LICENSE"}{separator}assets/models']
        env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(temp / 'cache'))
        env.pop('CURSEFORGE_API_KEY', None)  # la clave nunca debe llegar al proceso de empaquetado
        subprocess.run(args + [str(ROOT / 'app.py')], cwd=ROOT, env=env, check=True)
        folder = ROOT / 'dist' / name
        shutil.copy2(png, folder / 'icon.png')
    for doc in ('README.md', 'THIRD_PARTY.md'):
        shutil.copy2(ROOT / doc, folder / doc)
    collect_licenses(folder)
    if sys.platform.startswith('linux'):
        start = folder / 'Abrir-ModLab.sh'
        start.write_text(f'#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nexec ./{name} "$@"\n')
        start.chmod(0o755)
    label = 'windows' if sys.platform == 'win32' else 'linux' if sys.platform.startswith('linux') else sys.platform
    archive_path = ROOT / 'dist' / f'{name}-{label}-{platform.machine().lower()}'
    if sys.platform == 'win32':
        archive = shutil.make_archive(str(archive_path), 'zip', root_dir=ROOT / 'dist', base_dir=name)
    else:
        archive = str(archive_path) + '.tar.gz'
        with tarfile.open(archive, 'w:gz', compresslevel=1 if not lite else 6) as packed:
            packed.add(folder, arcname=name)
    print('Paquete listo:', archive)


if __name__ == '__main__':
    main()
