# SMAPT ModLab

**Crea y comparte modpacks de Minecraft sin configurar una API ni tener conocimientos de programación.**

[![Pruebas automáticas](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml/badge.svg)](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Beta](https://img.shields.io/badge/estado-beta-orange)

SMAPT ModLab es un programa de escritorio para buscar mods, organizar tu selección y exportar packs para los
lanzadores de Minecraft.

**No necesitas cuenta, API key ni IA** para usar el catálogo público de **Modrinth**: buscas, eliges y exportas un
`.mrpack` para **Modrinth App** o **Prism Launcher**. **CurseForge** también está integrado para quien tenga acceso
autorizado a su API, y la **IA local** es un complemento opcional.

> **Edición beta:** el programa y los archivos exportados todavía requieren pruebas en equipos reales. Los mods y sus
> licencias siguen perteneciendo a sus autores.

## Descargar

Ve a **[Releases de SMAPT-ModLab](https://github.com/Pablxmvrtinez/SMAPT-ModLab/releases)** y elige tu sistema:

- **Windows:** descarga el ZIP, descomprímelo y abre `SMAPT-ModLab.exe`.
- **Linux:** descarga el `.tar.gz`, extráelo y ejecuta `Abrir-ModLab.sh` dentro de la carpeta.
- No copies solo el ejecutable: la carpeta `_internal` contiene las bibliotecas necesarias.

Si todavía no aparece ninguna versión, consulta el
[estado de las compilaciones](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/portable.yml).
La edición pública no incluye el modelo de IA de 2,5 GB; el catálogo y la exportación funcionan sin él.

## Crear tu primer modpack

1. Abre ModLab. Arriba a la derecha elige la **versión de Minecraft** y el **cargador** (Fabric, Forge, NeoForge o Quilt).
2. Entra en **Explorar mods** y elige **Modrinth** (o **CurseForge** si lo tienes conectado). Escribe lo que buscas:
   los resultados aparecen mientras escribes. Filtra por categoría u orden, o pulsa una **temática** en Inicio.
3. Pulsa **Añadir** en las tarjetas. Pulsa la tarjeta para ver su **ficha**: descripción, imágenes, todas las versiones
   (puedes fijar una concreta) y sus dependencias.
4. En **Mi modpack** pulsa **Comprobar pack**: verás el archivo elegido para cada mod, las dependencias obligatorias que
   se añadirán y las incompatibilidades declaradas. Tu selección no se modifica.
5. Escribe nombre, versión y autor, y pulsa **Exportar → Modpack de Modrinth (.mrpack)** (o **ZIP de CurseForge**).
6. Importa el archivo en **Modrinth App**, **Prism Launcher** o **CurseForge** y prueba el juego.

ModLab prioriza las versiones **estables**; en Modrinth usa una beta solo si no hay estable compatible (en Ajustes puedes
permitir también alfas o betas de CurseForge). El `.mrpack` contiene nombres, hashes y URL oficiales, **no incluye los
JAR**: el lanzador los descarga al importar.

**Validación antes de guardar:** ModLab revisa la estructura del ZIP, las rutas (con nombres válidos en Windows y Linux),
los hashes, que las descargas procedan de `cdn.modrinth.com` y los entornos cliente/servidor **antes** de reemplazar un
archivo. Si algo falla, el archivo anterior se conserva. Desde **Exportar → Verificar un .mrpack guardado** puedes
revisar una exportación anterior; también desde la terminal:

~~~bash
python scripts/validate_mrpack.py /ruta/al/archivo.mrpack
~~~

El validador comprueba el formato que genera ModLab; no descarga mods ni garantiza que arranquen en el juego.

Los mods de servidor dedicado no se marcan como instalables en el cliente: el `.mrpack` usa el entorno que indica
Modrinth para cada versión. Si dos mods exigen versiones distintas de la misma dependencia, la comprobación lo avisa.

**Descargar mods** (en Mi modpack) guarda los JAR en una carpeta, por ejemplo la carpeta `mods` de una instancia, con
progreso real y verificación de hash. Los mods de CurseForge cuyo autor no permite descargas de terceros no se
descargan: ModLab muestra el enlace a su página oficial.

**Guardar** y **Abrir** conservan la selección en un proyecto `.json` (versión de Minecraft, cargador, build manual del
cargador y archivos fijados). Al cambiar la versión o el cargador se borra el build manual para no exportar una
combinación equivocada.

### ¿Y CurseForge?

ModLab usa la [API oficial](https://docs.curseforge.com/rest-api/) con la cabecera `x-api-key`. Según los
[términos de la API de terceros](https://support.curseforge.com/support/solutions/articles/9000207405-curseforge-3rd-party-api-terms-and-conditions)
**la clave no se comparte** (§2.2) y **los datos de la API no se guardan ni se cachean** (§3.1). ModLab cumple ambas:

- La clave se lee de la variable de entorno `CURSEFORGE_API_KEY` (o se escribe en Ajustes solo para la sesión). Solo se
  envía a `api.curseforge.com`; nunca va a disco, registros, proyectos ni paquetes.
- No hay caché de CurseForge: los proyectos guardan solo tu selección (IDs, título y archivo fijado).

~~~bash
export CURSEFORGE_API_KEY='tu-clave'      # Windows (PowerShell): $env:CURSEFORGE_API_KEY='tu-clave'
python app.py
python scripts/check_live.py curseforge   # comprueba la conexión real sin mostrar la clave
~~~

**Compartir ModLab con acceso a CurseForge:** la clave no puede ir dentro del programa. La alternativa es
`catalog_server.py`, una pasarela que guarda la clave en tu servidor, solo admite rutas de lectura de mods de Minecraft,
valida parámetros, limita peticiones por IP y responde con `Cache-Control: no-store`. Publícala con HTTPS y construye el
paquete con `SMAPT_CATALOG_URL=https://tu-servidor`. **Publícala solo si tu autorización de CurseForge cubre ese uso.**

### ¿Y la IA?

**Crear con IA** entiende descripciones libres en español («quiero sobrevivir en un apocalipsis zombi explorando
ciudades, con armas de fuego y bases, sin que sea muy difícil») y trabaja con mods **reales** del catálogo que elijas,
Modrinth (sin clave) o CurseForge:

1. **Interpreta** la descripción con un modelo local (Qwen3-4B en llama.cpp): requisitos obligatorios y opcionales,
   búsquedas que el propio modelo escribe para cada idea (sin lista fija de palabras), mods conocidos solo como pistas
   de búsqueda, lo que rechazas («sin zombis», «nada de máquinas»), dificultad y rendimiento.
2. **Busca** cada idea en el catálogo con tu versión y cargador, descarta las fichas con temas rechazados y las
   bibliotecas, y prioriza las que cubren más requisitos.
3. **Evalúa** las mejores fichas con el modelo: encaje, requisito que cubren, función y un motivo concreto.
4. **Recomendar mods** muestra tarjetas con imagen y motivo para añadir o descartar una a una.
   **Crear modpack** elige una combinación equilibrada sin funciones repetidas, comprueba archivos compatibles,
   resuelve dependencias, sustituye los mods incompatibles por alternativas y muestra una vista previa editable que
   puedes llevar a Mi modpack o exportar (`.mrpack` o ZIP de CurseForge).

La IA no inventa mods ni IDs: todo sale del catálogo y se verifica antes de exportar. Una propuesta no garantiza que
Minecraft arranque; pruébala en una instancia aparte. En CPU, una propuesta tarda de 2 a 6 minutos según el número de
mods (la barra muestra cada fase). **Configurar IA** (en Crear con IA o Ajustes) muestra los requisitos, descarga el
modelo de 2,5 GB con verificación SHA-256 y reanudación, instala el motor desde el código y prueba que responde.

## Instalar desde el código

Necesitas Python 3.12 (3.11 también funciona).

**Linux:**

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
~~~

**Windows (PowerShell):**

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
~~~

**IA opcional:**

~~~bash
python -m pip install -r requirements-ai.txt
python scripts/fetch_model.py
python app.py --verify-ai
~~~

El modelo se descarga de una revisión fija y se verifica con SHA-256.

Atajos: `Ctrl+1…7` secciones, `Ctrl+F` buscar, `Ctrl+S` guardar proyecto, `Ctrl+O` abrir, `Esc` volver.

## Compilar versiones portátiles

~~~bash
python -m pip install -r requirements.txt "pyinstaller>=6.16,<7"
python build_portable.py              # edición pública (sin claves, sin IA)
python build_portable.py --with-ai    # edición con IA (requirements-ai.txt + modelo); también SMAPT_INCLUDE_AI=1
~~~

El resultado aparece en `dist/`. El [workflow de compilación](.github/workflows/portable.yml) genera la edición pública
para Windows y Linux, comprueba que arranca y publica las descargas beta con la versión de `modlab/__init__.py`.

## Otras funciones

- **Mi equipo:** CPU, GPU (NVIDIA, AMD e Intel), RAM y sistema; instancias de CurseForge, Prism (nativo y Flatpak),
  MultiMC, Modrinth App, ATLauncher y el lanzador oficial, en Windows y Linux.
- **Optimizar:** propone ajustes gráficos por instancia y los aplica tras tu confirmación, guardando antes una copia.
  **Restaurar una copia** recupera cualquier copia anterior (y guarda el estado actual por si quieres deshacer).
  Cierra Minecraft antes de aplicar o restaurar.
- **Ajustes:** conexión de CurseForge, prueba de conexión, caché, carpeta de registros y estado de la IA.

## Problemas habituales

- **«Modrinth ha limitado temporalmente las consultas».** Hay un límite por IP; espera unos segundos.
- **«Sin archivo estable para Minecraft…».** Cambia la versión o el cargador, elige una versión concreta en la ficha
  del mod o quita ese mod.
- **«El pack no funciona al importarlo».** Las dependencias declaradas ayudan, pero no garantizan compatibilidad con
  cualquier combinación. Prueba en una instancia aparte y revisa los registros de Minecraft.
- **«La IA no está disponible».** Es normal en la edición pública; explorar y exportar no la necesitan.
- **«CurseForge no está conectado».** Usa Modrinth o configura tu clave autorizada (ver arriba).

Los registros de ModLab (sin claves ni cabeceras) están en Ajustes → **Abrir carpeta de registros**.

## Pruebas y código

~~~bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python app.py --smoke
python scripts/check_live.py                                     # catálogos reales
python scripts/modrinth_live_smoke.py --output artifacts/modrinth-smoke.mrpack
python scripts/evaluate_ai.py                                    # comprensión semántica con el modelo real
python scripts/ai_e2e.py                                         # IA real + Modrinth → .mrpack validado
~~~

Las pruebas unitarias simulan la red y cubren catálogos, dependencias, validación `.mrpack`, descargas, proyectos,
interfaz y restauración de gráficos; la CI las ejecuta en Linux y Windows. La
[prueba real de Modrinth](.github/workflows/modrinth-live-smoke.yml) resuelve Fabric API y Sodium, exporta y valida un
`.mrpack` sin descargar JAR ni arrancar Minecraft.

Estructura: `app.py` (arranque), `modlab/sources/` (CurseForge y Modrinth), `modlab/modpack.py` y
`modlab/mrpack_validator.py` (exportación y validación), `modlab/downloads.py`, `modlab/project.py`, `modlab/core.py`
(equipo, instancias y gráficos), `modlab/intelligence.py` y `local_ai.py` (IA), `modlab/ui/` (interfaz) y
`catalog_server.py` (pasarela).

## Créditos y licencias

Usa Python, PySide6, Requests y psutil; consulta [THIRD_PARTY.md](THIRD_PARTY.md) para licencias de bibliotecas y del
modelo de IA. Las fichas, imágenes y archivos de mods proceden de sus servicios y siguen sujetos a los permisos de sus
autores.
