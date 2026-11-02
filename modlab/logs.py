"""Registro de errores en disco sin claves, cabeceras ni rutas personales completas."""
import logging
import logging.handlers
import os
import re
from pathlib import Path

from modlab import paths

_SECRET_PATTERNS = [
    re.compile(r'(x-api-key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', re.IGNORECASE),
    re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', re.IGNORECASE),
    # Las claves de CurseForge son cadenas bcrypt-like de 60 caracteres que empiezan por $2a$.
    re.compile(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}'),
]


def redact(text):
    text = str(text)
    key = os.environ.get('CURSEFORGE_API_KEY', '')
    if len(key) >= 8:
        text = text.replace(key, '***')
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else '') + '***', text)
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, '~')
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def setup(level=logging.INFO):
    """Configura un archivo rotativo de 1 MB × 3. Devuelve su ruta o None si no se puede escribir."""
    root = logging.getLogger('modlab')
    if root.handlers:
        return getattr(root, 'log_file', None)
    root.setLevel(level)
    formatter = RedactingFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    root.addHandler(console)
    try:
        file = paths.ensure(paths.log_dir()) / 'modlab.log'
        handler = logging.handlers.RotatingFileHandler(file, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    except OSError:
        return None
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.log_file = file
    return file


def get(name):
    return logging.getLogger('modlab.' + name)
