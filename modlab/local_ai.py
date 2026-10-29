"""Modelo de lenguaje local (Qwen3-4B en llama.cpp). No usa servicios externos ni agentes.

Las respuestas se restringen con una gramática derivada de un esquema JSON, así que siempre son JSON
sintácticamente válido; el contenido se valida después en ``intelligence.py``.
"""
from contextlib import contextmanager
from threading import RLock
import json
import time

import psutil

from modlab import ai_setup, logs
from modlab.errors import Cancelled, CatalogError

log = logs.get('local_ai')
MODEL_FILE = ai_setup.MODEL_FILE


def model_path():
    """Ruta del modelo disponible o, si no hay ninguno, la ubicación del paquete (para mensajes)."""
    return ai_setup.model_path() or ai_setup.bundled_model()


class LocalAI:
    def __init__(self, context=8192):
        self.lock = RLock()
        self.context = context
        self._model = None
        self._keep = False
        self.last_stats = {}

    def available(self):
        return ai_setup.engine_installed() and ai_setup.model_path() is not None

    @contextmanager
    def session(self):
        """Mantiene el modelo cargado entre varias peticiones de una misma propuesta."""
        with self.lock:
            self._keep = True
            try:
                yield self
            finally:
                self._keep = False
                self._unload()

    def _unload(self):
        if self._model is not None:
            self._model.close()
            self._model = None

    def _load(self, progress):
        if self._model is not None:
            return self._model
        if psutil.virtual_memory().available < ai_setup.RAM_NEEDED:
            raise CatalogError('La IA local necesita unos 5,5 GB de RAM libre. Cierra Minecraft u otras aplicaciones; '
                               'Explorar mods funciona sin cargar el modelo.')
        from llama_cpp import Llama, llama_supports_gpu_offload
        progress('Cargando el modelo de IA…')
        physical = psutil.cpu_count(logical=False) or 2
        logical = psutil.cpu_count() or physical
        start = time.monotonic()
        self._model = Llama(model_path=str(ai_setup.model_path()), n_ctx=self.context, n_batch=512,
                            n_threads=max(1, physical), n_threads_batch=max(1, logical),
                            n_gpu_layers=-1 if llama_supports_gpu_offload() else 0,
                            chat_format='chatml', verbose=False)
        log.info('Modelo cargado en %.1f s (%s hilos, contexto %s)', time.monotonic() - start, physical, self.context)
        return self._model

    def complete(self, instruction, data, schema, progress=lambda _: None, max_tokens=1600, temperature=0.2):
        """Respuesta JSON que cumple ``schema``. ``progress`` puede lanzar Cancelled para detener la generación."""
        if not self.available():
            raise CatalogError('Falta la IA local (motor o modelo). Abre «Configurar IA» en Crear con IA para instalarla.')
        with self.lock:
            model = self._load(progress)
            payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
            stream = None
            try:
                start = time.monotonic()
                stream = model.create_chat_completion(
                    messages=[{'role': 'system', 'content': instruction}, {'role': 'user', 'content': payload}],
                    response_format={'type': 'json_object', 'schema': schema}, temperature=temperature,
                    top_p=0.9, max_tokens=max_tokens, seed=42, stream=True)
                chunks, finish, tokens = [], None, 0
                for chunk in stream:
                    choice = chunk['choices'][0]
                    piece = choice.get('delta', {}).get('content') or ''
                    if piece:
                        chunks.append(piece)
                        tokens += 1
                        if tokens % 24 == 0:
                            progress(f'La IA está escribiendo… ({tokens} fragmentos)')
                    finish = choice.get('finish_reason') or finish
                seconds = time.monotonic() - start
                self.last_stats = {'tokens': tokens, 'seconds': round(seconds, 1),
                                   'tokens_per_second': round(tokens / seconds, 1) if seconds else 0}
                log.info('Respuesta de la IA: %s fragmentos en %.1f s', tokens, seconds)
                if finish == 'length':
                    raise CatalogError('La IA no terminó la respuesta dentro del límite. Prueba una descripción más breve.')
                return json.loads(''.join(chunks))
            except Cancelled:
                raise
            except (ValueError, KeyError, TypeError):
                raise CatalogError('La IA local devolvió una respuesta que no se puede interpretar. Inténtalo de nuevo.') from None
            finally:
                if stream is not None and hasattr(stream, 'close'):
                    stream.close()
                if not self._keep:
                    self._unload()
