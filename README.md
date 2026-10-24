# SMAPT ModLab

**Crea y comparte modpacks de Minecraft sin configurar una API ni tener conocimientos de programación.**

[![Pruebas automáticas](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml/badge.svg)](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Beta](https://img.shields.io/badge/estado-beta-orange)

SMAPT ModLab es un programa de escritorio para buscar mods, organizar selecciones y exportar packs compatibles con los lanzadores de Minecraft.

**No necesitas cuenta, API key ni IA** para usar el nuevo catálogo público de **Modrinth**. Puedes buscar mods y generar archivos `.mrpack` para importarlos en **Modrinth App** o **Prism Launcher**. La integración con CurseForge se conserva como modo opcional para desarrolladores con acceso autorizado.

> **Edición beta:** el programa y los archivos exportados todavía requieren pruebas en equipos reales. El catálogo de Modrinth usa Internet y respeta sus límites de consultas. Los mods y sus licencias siguen perteneciendo a sus autores.

## Descargar

Ve a **[Releases de SMAPT-ModLab](https://github.com/Pablxmvrtinez/SMAPT-ModLab/releases)** y elige tu sistema:

- **Windows:** descarga el archivo ZIP para Windows, descomprímelo y abre `SMAPT-ModLab.exe`.
- **Linux:** descarga el `.tar.gz`, extráelo y ejecuta `Abrir-ModLab.sh` dentro de la carpeta.
- No copies solo el ejecutable: la carpeta `_internal` contiene las bibliotecas necesarias.

Si todavía no aparece ninguna versión, consulta el [estado de las compilaciones](https://github.com/Pablxmvrtinez/SMAPT-ModLab/actions/workflows/portable.yml). Las descargas se publican tras superar las pruebas y el arranque básico en ambos sistemas.

**Importante:** la edición pública no incluye el modelo de IA de 2,5 GB. Por eso la descarga es más ligera. El catálogo y la exportación públicos funcionan sin ese modelo.

## Crear tu primer modpack

1. Abre el programa y pulsa **Empezar sin claves** o entra en **Mods públicos**.
2. Selecciona arriba la **versión de Minecraft** y el **cargador** (Fabric, Forge o NeoForge).
3. Busca mods por nombre. También puedes navegar por los resultados populares.
4. Pulsa **Añadir** en los mods que quieras. Aparecerán en **Mi selección para Modrinth**.
5. Pulsa **Comprobar selección y dependencias** para revisar las versiones, posibles conflictos declarados y bibliotecas obligatorias sin modificar tu selección.
6. Escribe un nombre para tu modpack y pulsa **Exportar paquete .mrpack**.
7. ModLab consulta los archivos compatibles y sus dependencias obligatorias; si algo no encaja, te muestra un error y conserva la selección.
8. Importa el archivo generado en **Modrinth App** o **Prism Launcher** y prueba el juego.

El `.mrpack` contiene nombres, hashes y URL de descarga de archivos oficiales, **no incluye los JAR**. Al importar el pack, el lanzador obtiene los archivos correspondientes.

Los archivos exportados también incluyen el entorno de instalación indicado por Modrinth (cliente, servidor dedicado u opcional cuando corresponde). Los mods destinados exclusivamente a servidores dedicados no se marcan como instalables en el cliente. Si el catálogo indica dependencias obligatorias circulares, se detiene la exportación para evitar generar un pack inconsistente.

Si lo quieres retomar más tarde, usa **Guardar selección**. El botón **Abrir selección** recupera ese proyecto en formato JSON, incluyendo la versión de Minecraft, el cargador y la versión manual del cargador si la habías indicado. Al cambiar de versión o cargador manualmente, se borra el número de build anterior para evitar exportar una combinación equivocada.

### ¿Y CurseForge?

La pestaña **Explorar mods** utiliza CurseForge y requiere una clave personal o acceso autorizado configurado en **Conexión del catálogo**. No es necesario para el modo público. **No se incluye tu clave en el programa**, y no se publica un proxy compartido sin permiso de CurseForge.

Las condiciones de la API están disponibles en [CurseForge Third-Party Terms](https://support.curseforge.com/support/solutions/articles/9000207405-curseforge-3rd-party-api-terms-and-conditions).

### ¿Y la IA?

La sección **Crear con IA** es opcional y necesita instalar el motor local y el modelo GGUF. No utiliza una API de pago, pero la edición pública básica no lo incluye.

Si quieres ejecutar la edición con IA **desde el código**, instala las dependencias adicionales indicadas más abajo y descarga el modelo verificado. La IA propone mods de CurseForge cuando el catálogo está autorizado. Por ahora **no genera directamente modpacks de Modrinth**.

## Instalar desde el código

Necesitas Python 3.12, acceso a Internet para instalar dependencias y los archivos de este repositorio.

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

Estos comandos instalan la **edición pública** sin IA. No hace falta pedir una clave de Modrinth.

**IA opcional**, desde una instalación de desarrollo:

~~~bash
python -m pip install -r requirements-ai.txt
python scripts/fetch_model.py
python app.py
~~~

El modelo utiliza `llama-cpp-python` y Qwen3-4B-Instruct-2507 GGUF. Su descarga está fijada por revisión y se valida con SHA-256. Requiere varios GB de memoria libre.

## Compilar versiones portátiles

Para crear el paquete del sistema en el que estás trabajando:

~~~bash
python -m pip install -r requirements.txt "pyinstaller>=6.16,<7"
python build_portable.py
~~~

El resultado aparece en `dist/`. Para incluir la IA en una compilación de desarrollo, instala `requirements-ai.txt`, descarga el modelo y configura `SMAPT_INCLUDE_AI=1` antes de ejecutar el constructor.

El [workflow de compilación](.github/workflows/portable.yml) genera una edición pública para Windows y Linux y puede publicar las descargas de la versión beta tras sus comprobaciones.

## Otras funciones

**Mi equipo y Optimizar:** identifica instancias de Prism y CurseForge cuando usan rutas conocidas. Permite proponer ajustes gráficos y aplicarlos tras tu confirmación; guarda antes una copia de los originales. También hay una opción **Restaurar última copia de gráficos**. Cierra Minecraft antes de aplicar o restaurar.

**Proyectos de CurseForge:** selecciona mods, guárdalos en JSON, consulta sus dependencias y exporta un ZIP de importación si tienes acceso autorizado al catálogo.

**Modo público Modrinth:** funciona de forma independiente: sus selecciones JSON y paquetes `.mrpack` no son intercambiables automáticamente con los proyectos ZIP de CurseForge.

## Problemas habituales

**«Modrinth limita las peticiones».** El servicio establece un límite de consultas por IP; espera y vuelve a intentarlo.

**«No hay versión compatible».** Cambia la versión de Minecraft, el cargador o elimina ese mod de tu selección.

**«El pack no funciona al importarlo».** Los metadatos de dependencias ayudan, pero no garantizan compatibilidad con todas las combinaciones. Prueba los mods en una instancia independiente y revisa los registros de Minecraft.

**«La IA no está disponible».** Es normal en la edición pública. El buscador y la exportación no la necesitan.

**«CurseForge no está conectado».** Usa el catálogo público de Modrinth o configura una clave de desarrollador autorizada.

## Pruebas y código

Las pruebas unitarias cubren búsqueda pública, selección de versiones, verificación de URL y hashes, dependencias, formato `.mrpack`, interfaz, exportación de CurseForge y restauración de gráficos.

~~~bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
~~~

En Windows elimina el prefijo de variable de entorno. El proceso de CI comprueba Linux y Windows; las pruebas simuladas no sustituyen un test funcional de los mods reales en Minecraft.

### Prueba con datos reales de Modrinth

La comprobación de integración obtiene versiones auténticas de Fabric API y Sodium para Minecraft 1.20.1, resuelve sus dependencias, consulta la versión del cargador Fabric y exporta un `.mrpack`. Después revisa el ZIP, las rutas, los hashes, las URLs y la correspondencia con el archivo original del catálogo, **sin descargar JAR ni arrancar Minecraft**.

~~~bash
python scripts/modrinth_live_smoke.py --output artifacts/modrinth-smoke.mrpack
~~~

El workflow [Modrinth - prueba real de exportación](.github/workflows/modrinth-live-smoke.yml) ejecuta este proceso y guarda un `.mrpack` como artefacto durante 7 días si la prueba termina correctamente. Necesita conexión a Internet; los problemas de red o de disponibilidad del catálogo hacen fallar la prueba. El archivo generado es **solo una muestra de validación**, no un modpack de producción. La importación en Prism Launcher o Modrinth App y la ejecución del juego siguen necesitando una prueba manual.


Los archivos principales son `app.py` (interfaz), `public_page.py` (modo público), `public_catalog.py` (API pública y MRPACK), `curseforge.py` (API con clave), `modpack.py` (ZIP para CurseForge) y `core.py` (detección y gráficos).

## Créditos y licencias

Este proyecto utiliza Python, PySide6, Requests y psutil. Consulta [THIRD_PARTY.md](THIRD_PARTY.md) para licencias y referencias de las bibliotecas y del modelo de IA. Las fichas, iconos y archivos de mods se obtienen desde sus respectivos servicios y siguen sujetos a los permisos de sus autores.
