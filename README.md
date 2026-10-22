# SMAPT ModLab

**Crea y organiza modpacks de Minecraft desde tu escritorio.**

[![Pruebas](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml/badge.svg)](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml) ![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![Estado](https://img.shields.io/badge/estado-en%20desarrollo-EAA33B)

ModLab combina un explorador de mods, un editor de packs, un comprobador de dependencias y un diseñador de experiencias con IA local. Puedes elegir mods manualmente o explicar cómo quieres jugar y revisar las recomendaciones antes de añadirlas.

> **Estado:** en desarrollo. La búsqueda real necesita una conexión autorizada con CurseForge. El constructor portátil y el motor de IA están implementados, pero todavía falta probar una distribución completa en Windows y Linux. No se incluyen claves privadas ni JAR de otros autores.

## Contenido

- [Funciones y estado](#funciones-y-estado)
- [Cómo utilizar la aplicación](#cómo-utilizar-la-aplicación)
- [Instalación desde el código](#instalación-desde-el-código)
- [Conexión con CurseForge](#conexión-con-curseforge)
- [Guardar y exportar packs](#guardar-y-exportar-packs)
- [Optimizar y restaurar gráficos](#optimizar-y-restaurar-gráficos)
- [Crear ejecutables](#crear-ejecutables)
- [Solución de problemas](#solución-de-problemas)

## Funciones y estado

| Función | Situación |
| --- | --- |
| Navegación, exploración visual y selección de mods | Implementada; la búsqueda requiere API |
| Proyectos JSON, revisión de dependencias y exportación ZIP | Cubiertos por pruebas con respuestas simuladas |
| IA local para interpretar peticiones y recomendar mods | Integrada; falta una prueba real de extremo a extremo con el modelo descargado |
| Detección de instancias y ajustes gráficos con copias de seguridad | Implementados y probados |
| Ejecutables portátiles | Constructor disponible; aún sin versión final validada |

**Importante:** un ZIP exportado por ModLab no contiene archivos JAR. Incluye identificadores oficiales para que CurseForge descargue los mods admitidos al importar el pack.

## Cómo utilizar la aplicación

1. Elige la **versión de Minecraft** y el **cargador** (Forge, Fabric o NeoForge) en la parte superior.
2. Abre **Explorar mods** para buscar por nombre o categoría, o **Crear con IA** para describir una experiencia de juego. Ambas funciones necesitan el catálogo; la segunda también necesita el modelo local.
3. Revisa los resultados y añade los mods a **Mi modpack**.
4. Guarda el proyecto en JSON cuando quieras retomarlo. Si cambias de versión o cargador, ModLab mantiene tus proyectos seleccionados y vuelve a comprobar los archivos compatibles.
5. Utiliza **Comprobar pack** para revisar dependencias y conflictos declarados.
6. Pulsa **Crear ZIP para CurseForge** e impórtalo desde el lanzador de CurseForge, en Minecraft > Importar.

Las advertencias se basan en metadatos oficiales. **No garantizan que Minecraft arranque** con cualquier combinación: siempre conviene probar el modpack antes de compartirlo.

## Instalación desde el código

Necesitas **Python 3.12** (recomendado), Internet para instalar dependencias y unos 2,5 GB de almacenamiento para el modelo GGUF, además de RAM libre para ejecutarlo.

Descarga el repositorio y abre una terminal en su carpeta principal.

**Linux:**

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/fetch_model.py
.venv/bin/python app.py
~~~

**Windows (PowerShell):**

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fetch_model.py
.\.venv\Scripts\python.exe app.py
~~~

`fetch_model.py` descarga una revisión fijada del modelo, comprueba el tamaño y verifica SHA-256. La IA utiliza `llama-cpp-python` con `Qwen3-4B-Instruct-2507`, sin requerir Ollama ni una suscripción externa.

Para probar solo el arranque de la interfaz, sin ejecutar el modelo:

~~~bash
python app.py --smoke
~~~

## Conexión con CurseForge

La aplicación se puede abrir sin una clave, pero **no podrá consultar mods reales ni verificar archivos para exportar** hasta conectar el catálogo. Para tus pruebas de desarrollo:

1. Solicita una clave conforme a las [instrucciones de CurseForge](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key).
2. Configura la variable de entorno `CURSEFORGE_API_KEY` o utiliza el cuadro **Conexión del catálogo** de la aplicación.
3. Comprueba que aparecen las categorías y que una búsqueda devuelve resultados.

Ejemplo para una sesión local de Linux:

~~~bash
export CURSEFORGE_API_KEY="TU_CLAVE_PERSONAL"
.venv/bin/python app.py
~~~

**Nunca publiques la clave en GitHub ni dentro del ejecutable.** Las [condiciones de CurseForge](https://support.curseforge.com/support/solutions/articles/9000207405-curseforge-3rd-party-api-terms-and-conditions) restringen compartir claves y utilizar proxies. La herramienta `catalog_server.py` es experimental, no una pasarela pública aprobada. Una distribución lista para todos necesita un método autorizado por CurseForge.

## Guardar y exportar packs

**Guardar proyecto** genera un archivo JSON con tu selección y sus datos esenciales. Puedes recuperarlo con **Abrir proyecto**. Los archivos JSON de procedencia desconocida se validan antes de cargarlos.

**Comprobar pack** consulta CurseForge para verificar archivos compatibles y dependencias obligatorias; si encuentra una incompatibilidad declarada, se detiene y explica el problema. **Crear ZIP** hace la comprobación de nuevo y exporta un manifiesto con `projectID` y `fileID`, más información del pack.

Después abre el lanzador CurseForge e importa ese ZIP. CurseForge se encarga de descargar los JAR permitidos. Algunos proyectos no ofrecen una versión estable para todas las combinaciones de Minecraft y cargador; ModLab no inventa versiones que no existen.

## Optimizar y restaurar gráficos

En **Mi equipo** podrás consultar tu hardware e instancias detectadas de CurseForge o Prism. En **Optimizar** selecciona una instancia y elige una prioridad: equilibrado, máximos FPS o calidad visual.

Al pulsar **Aplicar gráficos con copia de seguridad**, ModLab ajusta distancia de renderizado, simulación, FPS y opciones gráficas compatibles después de pedir confirmación. Antes de cambiar nada, guarda el estado anterior en la carpeta `.smapt-backups/` de la instancia.

**Restaurar última copia de gráficos** recupera los ajustes guardados. Antes de hacerlo genera otra copia del estado actual, por si quieres deshacer esa restauración. **Cierra Minecraft antes de aplicar o restaurar cambios.** La memoria RAM asignada a Java se cambia desde el lanzador, no desde ModLab.

## Crear ejecutables

Con las dependencias instaladas y el modelo ya descargado:

~~~bash
python -m pip install "pyinstaller>=6.16,<7"
python build_portable.py
~~~

El paquete se genera en `dist/`. **No copies solamente el EXE o el binario:** conserva toda la carpeta, incluida `_internal`. Windows y Linux se compilan por separado. En Linux puede ser necesario compilar desde una distribución con bibliotecas compatibles con los equipos de destino.

Hay un [workflow de empaquetado manual](.github/workflows/portable.yml), pero todavía no está confirmado un lanzamiento final probado en ambos sistemas.

## Solución de problemas

**«El catálogo no está conectado».** Verifica el acceso autorizado a CurseForge y tu conexión. No se utiliza un catálogo alternativo oculto.

**«Esta instalación no incluye la IA».** Descarga el modelo con `scripts/fetch_model.py` y revisa las dependencias y la memoria RAM disponible.

**«No hay archivo estable compatible».** Elige otra versión de Minecraft, otro cargador o sustituye ese mod.

**«Mi instancia no aparece».** Comprueba que tiene una carpeta reconocida por el lanzador. Las rutas de instalación personalizadas pueden requerir detección adicional.

**«El pack se importa, pero el juego falla».** La comprobación de metadatos no detecta todos los conflictos. Prueba los mods en una instancia separada y revisa los logs de Minecraft.

Para ejecutar las pruebas sin mostrar la ventana:

~~~bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
~~~

En Windows utiliza `python -m unittest discover -s tests -v` sin el prefijo de Linux. Estas pruebas emplean respuestas simuladas, no tu clave real. GitHub también ejecuta [pruebas automáticas](.github/workflows/tests.yml) al subir cambios.

## Licencias y agradecimientos

ModLab utiliza Python, PySide6, Requests, psutil, `llama-cpp-python` y el modelo Qwen3-4B-Instruct-2507 (GGUF). Las condiciones y enlaces de las dependencias se detallan en [THIRD_PARTY.md](THIRD_PARTY.md).
