"""Rutas de usuario y de recursos, iguales en el código fuente y en el paquete portable.

Coinciden con las de Qt (QStandardPaths con organización SMAPT y aplicación SMAPT-ModLab)
para conservar la configuración guardada por versiones anteriores.
"""
import os
import sys
from pathlib import Path

from modlab import APP_NAME, ORGANIZATION


def resource_root():
    """Carpeta con `assets/` y `app-config.json` (``_internal`` en PyInstaller)."""
    if getattr(sys, 'frozen', False):
        return Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _windows_base(variable, fallback):
    return Path(os.environ.get(variable) or Path.home() / fallback)


def config_dir():
    if sys.platform == 'win32':
        base = _windows_base('LOCALAPPDATA', 'AppData/Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Preferences'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / ORGANIZATION / APP_NAME


def cache_dir():
    if sys.platform == 'win32':
        base = _windows_base('LOCALAPPDATA', 'AppData/Local')
        return base / ORGANIZATION / APP_NAME / 'cache'
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Caches'
    else:
        base = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
    return base / ORGANIZATION / APP_NAME


def data_dir():
    """Datos grandes que el usuario descarga (por ejemplo, el modelo de IA)."""
    if sys.platform == 'win32':
        return _windows_base('LOCALAPPDATA', 'AppData/Local') / ORGANIZATION / APP_NAME / 'data'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support' / APP_NAME
    base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return base / ORGANIZATION / APP_NAME


def log_dir():
    if sys.platform == 'win32':
        return _windows_base('LOCALAPPDATA', 'AppData/Local') / ORGANIZATION / APP_NAME / 'logs'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Logs' / APP_NAME
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    return base / ORGANIZATION / APP_NAME / 'logs'


def ensure(path):
    path.mkdir(parents=True, exist_ok=True)
    return path
