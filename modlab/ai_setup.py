"""Estado e instalación del motor de IA local: llama-cpp-python + modelo Qwen3-4B (GGUF).

El modelo se busca primero dentro del paquete (edición con IA) y después en la carpeta de datos del
usuario, donde lo deja la descarga desde la aplicación. La descarga usa una revisión fija de Hugging Face
y se verifica con tamaño y SHA-256 antes de darla por buena.
"""
import hashlib
import importlib.util
import os
import sys

import psutil
import requests

from modlab import USER_AGENT, logs, paths
from modlab.errors import CatalogError

log = logs.get('ai_setup')
REPOSITORY = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
REVISION = 'a06e946bb6b655725eafa393f4a9745d460374c9'
MODEL_FILE = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
SHA256 = '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
SIZE = 2497281120
ENGINE_PACKAGE = 'llama-cpp-python==0.3.36'
RAM_NEEDED = 5.5 * 1024 ** 3
CHUNK = 4 * 1024 * 1024


def model_url(filename=MODEL_FILE):
    return f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{filename}'


def bundled_model():
    return paths.resource_root() / 'assets/models' / MODEL_FILE


def user_model():
    return paths.data_dir() / 'models' / MODEL_FILE


def model_path():
    """Primer modelo completo encontrado (paquete o carpeta del usuario); None si no hay ninguno."""
    for candidate in (bundled_model(), user_model()):
        try:
            if candidate.is_file() and candidate.stat().st_size == SIZE:
                return candidate
        except OSError:
            continue
    return None


def engine_installed():
    return importlib.util.find_spec('llama_cpp') is not None


def engine_details():
    if not engine_installed():
        return {'installed': False, 'version': '', 'gpu': False}
    try:
        import llama_cpp
        return {'installed': True, 'version': getattr(llama_cpp, '__version__', ''),
                'gpu': bool(llama_cpp.llama_supports_gpu_offload())}
    except Exception as exc:  # noqa: BLE001 - una biblioteca nativa rota no debe cerrar la app
        log.warning('llama_cpp no se puede cargar: %s', type(exc).__name__)
        return {'installed': False, 'version': '', 'gpu': False, 'error': 'El motor está instalado pero no se puede cargar.'}


def can_install_engine():
    """pip solo es viable desde el código fuente dentro de un entorno virtual (no en el paquete ni en el Python del sistema)."""
    return not getattr(sys, 'frozen', False) and sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def install_engine_command():
    return [sys.executable, '-m', 'pip', 'install', ENGINE_PACKAGE]


def install_engine_environment():
    # Compilación portable sin GPU; con otras opciones de CMake el usuario puede activar CUDA o Vulkan.
    return dict(os.environ, CMAKE_ARGS=os.environ.get('CMAKE_ARGS', '-DGGML_NATIVE=OFF'))


def status():
    memory = psutil.virtual_memory()
    model = model_path()
    engine = engine_details()
    partial = user_model().with_name(MODEL_FILE + '.part')
    return {'engine': engine, 'model': str(model) if model else '', 'model_bundled': bool(model and model == bundled_model()),
            'download_target': str(user_model()), 'partial_bytes': partial.stat().st_size if partial.is_file() else 0,
            'ram_total': memory.total, 'ram_available': memory.available, 'ram_needed': RAM_NEEDED,
            'ready': bool(engine['installed'] and model), 'can_install_engine': can_install_engine()}


def verify_model(path, progress=lambda done, total: None, check=lambda: None):
    digest = hashlib.sha256()
    done = 0
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(CHUNK), b''):
            check()
            digest.update(block)
            done += len(block)
            progress(done, SIZE)
    return digest.hexdigest() == SHA256


def download_model(progress=lambda message, fraction: None, check=lambda: None, http=None):
    """Descarga (reanudable) a la carpeta de datos del usuario y verifica tamaño y SHA-256."""
    target = user_model()
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(MODEL_FILE + '.part')
    have = part.stat().st_size if part.is_file() else 0
    if have > SIZE:
        part.unlink()
        have = 0
    headers = {'User-Agent': USER_AGENT}
    if have:
        headers['Range'] = f'bytes={have}-'
    http = http or requests
    try:
        with http.get(model_url(), headers=headers, stream=True, timeout=(20, 120)) as response:
            if have and response.status_code == 200:
                have = 0  # el servidor no admite reanudar: se empieza de nuevo
            elif response.status_code not in (200, 206):
                raise CatalogError(f'Hugging Face respondió {response.status_code} al descargar el modelo.')
            with open(part, 'ab' if have else 'wb') as handle:
                received = have
                for block in response.iter_content(CHUNK):
                    check()
                    if block:
                        handle.write(block)
                        received += len(block)
                        progress(f'Descargando el modelo · {received / 1024 ** 3:.2f} de {SIZE / 1024 ** 3:.2f} GB',
                                 0.9 * received / SIZE)
    except requests.RequestException:
        raise CatalogError('Se interrumpió la descarga del modelo. Vuelve a pulsar «Descargar» para continuar donde se quedó.') from None
    if part.stat().st_size != SIZE:
        raise CatalogError('La descarga del modelo está incompleta. Vuelve a pulsar «Descargar» para continuar.')
    progress('Verificando el modelo (SHA-256)…', 0.9)
    if not verify_model(part, lambda done, total: progress('Verificando el modelo (SHA-256)…', 0.9 + 0.1 * done / total), check):
        part.unlink(missing_ok=True)
        raise CatalogError('El archivo descargado no coincide con el modelo oficial y se ha eliminado.')
    os.replace(part, target)
    for filename in ('LICENSE',):
        try:
            extra = http.get(model_url(filename), headers={'User-Agent': USER_AGENT}, timeout=30)
            if extra.status_code == 200:
                (target.parent / filename).write_bytes(extra.content)
        except requests.RequestException:
            pass
    progress('Modelo descargado y verificado.', 1.0)
    return str(target)


def describe(info):
    """Texto breve del estado para la interfaz."""
    if info['ready']:
        where = 'incluido en el paquete' if info['model_bundled'] else 'descargado'
        gpu = 'con GPU' if info['engine'].get('gpu') else 'en CPU'
        return f"IA local lista ({where}, {gpu})."
    if not info['engine']['installed']:
        return info['engine'].get('error') or 'Falta el motor llama-cpp-python.'
    return 'Falta el modelo Qwen3-4B (2,5 GB).'


def bytes_text(value):
    return f'{value / 1024 ** 3:.1f} GB'
