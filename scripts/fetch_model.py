"""Descarga reproducible del modelo para incluirlo en el paquete (edición con IA).

Usa la misma revisión fija y verificación SHA-256 que la descarga desde la aplicación, pero guarda el
archivo en assets/models/ para que build_portable.py --with-ai lo empaquete.
"""
import hashlib
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modlab.ai_setup import MODEL_FILE, SHA256, SIZE, model_url  # noqa: E402


def main():
    folder = ROOT / 'assets/models'
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / MODEL_FILE
    if dest.is_file() and dest.stat().st_size == SIZE:
        with dest.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() == SHA256:
                print('Modelo ya verificado.')
                return
    tmp = dest.with_suffix('.part')
    digest = hashlib.sha256()
    size = 0
    try:
        with requests.get(model_url(), stream=True, timeout=(20, 180)) as r:
            r.raise_for_status()
            with tmp.open('wb') as f:
                for chunk in r.iter_content(4 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
        if size != SIZE or digest.hexdigest() != SHA256:
            raise ValueError('La descarga no coincide con el modelo oficial.')
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    for filename in ('LICENSE', 'NOTICE'):
        r = requests.get(model_url(filename), timeout=30)
        if r.ok:
            (folder / filename).write_bytes(r.content)
    print('Modelo integrado y verificado:', dest)


if __name__ == '__main__':
    main()
