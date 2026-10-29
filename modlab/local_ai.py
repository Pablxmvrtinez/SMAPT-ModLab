"""Modelo de lenguaje local incluido en el paquete. No usa servicios ni agentes."""
from threading import RLock
from contextlib import contextmanager
import json
import os

from modlab import paths
from modlab.errors import CatalogError

MODEL_FILE='Qwen3-4B-Instruct-2507-Q4_K_M.gguf'


def model_path():
    return paths.resource_root()/'assets/models'/MODEL_FILE


class LocalAI:
    def __init__(self):
        self.lock=RLock()
        self._model=None
        self._keep=False

    def available(self):
        import importlib.util
        return model_path().is_file() and importlib.util.find_spec('llama_cpp') is not None

    @contextmanager
    def session(self):
        with self.lock:
            self._keep=True
            try:
                yield self
            finally:
                self._keep=False
                if self._model is not None:
                    self._model.close();self._model=None

    def complete(self,instruction,data,schema,progress=lambda _:None):
        if not self.available():
            raise CatalogError('Este paquete no contiene el motor y el modelo de IA. Usa la edición completa de ModLab; no necesitas instalar agentes.')
        from llama_cpp import Llama
        import psutil
        if self._model is None and psutil.virtual_memory().available < 5.5*1024**3:
            raise CatalogError('La IA integrada necesita aproximadamente 5,5 GB de RAM libre. Cierra Minecraft u otras aplicaciones; Explorar mods funciona sin cargar el modelo.')
        with self.lock:
            progress('La IA local está razonando sobre tu petición…')
            if self._model is None:
                self._model=Llama(model_path=str(model_path()),n_ctx=6144,
                    n_threads=min(6,max(1,(os.cpu_count() or 2)//2)),
                    n_batch=256,chat_format='chatml',verbose=False)
            try:
                stream=self._model.create_chat_completion(messages=[{'role':'system','content':instruction},
                    {'role':'user','content':json.dumps(data,ensure_ascii=False)}],
                    response_format={'type':'json_object','schema':schema},temperature=0.1,
                    max_tokens=2000,seed=42,stream=True)
                chunks=[];finish=None
                for i,chunk in enumerate(stream):
                    choice=chunk['choices'][0]
                    chunks.append(choice.get('delta',{}).get('content',''))
                    finish=choice.get('finish_reason') or finish
                    if i and i%64==0:progress('La IA está preparando la interpretación y sus motivos…')
                if finish=='length':
                    raise CatalogError('La IA no terminó la respuesta. Prueba una descripción más concreta o un pack menor.')
                return json.loads(''.join(chunks))
            except (ValueError,KeyError,TypeError):
                raise CatalogError('La IA local no devolvió una propuesta válida. Reformula la descripción e inténtalo de nuevo.') from None
            finally:
                if not self._keep and self._model is not None:
                    self._model.close();self._model=None
