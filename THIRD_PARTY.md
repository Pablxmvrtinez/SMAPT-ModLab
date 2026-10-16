# Dependencias distribuidas

El paquete portable contiene Python, PySide6/Qt, Requests y psutil, además de sus
bibliotecas transitivas. No contiene agentes externos ni archivos de mods. La edición completa sí incluye el modelo local descrito abajo.

- Python: licencia PSF. https://docs.python.org/3/license.html
- PySide6/Qt: LGPLv3/GPLv3 o licencias comerciales según componentes. Este paquete
  usa las bibliotecas compartidas, conservadas como archivos separados en `_internal`.
  https://doc.qt.io/qtforpython-6/licenses.html
  Código fuente y versiones: https://download.qt.io/official_releases/QtForPython/
- Requests: Apache-2.0. https://github.com/psf/requests
- psutil: BSD-3-Clause. https://github.com/giampaolo/psutil
- PyInstaller: GPL con excepción para aplicaciones empaquetadas.
  https://pyinstaller.org/en/stable/license.html

El código fuente de ModLab y `build_portable.py` permiten reconstruir el paquete
con otras versiones compatibles de las bibliotecas. Conserva `_internal` completo
al compartirlo. Las licencias de los mods se aplican por separado a los ZIP de
Minecraft que se descarguen y generen desde la aplicación.

La edición con IA incorpora llama-cpp-python/llama.cpp (MIT) y
Qwen3-4B-Instruct-2507, cuantización Q4_K_M de Unsloth (Apache-2.0).
El modelo se descarga de una revisión fija y se verifica con SHA-256; su licencia
se incluye junto al archivo GGUF. No se incluyen archivos de mods de CurseForge.

- Modelo original: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Cuantización: https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- Motor: https://github.com/abetlen/llama-cpp-python
