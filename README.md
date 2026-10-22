# SMAPT ModLab

**Crea y organiza modpacks de Minecraft desde una aplicación de escritorio.**

ModLab permite elegir versiones y cargadores, buscar mods compatibles desde un catálogo configurado, revisar tu selección y exportar un paquete para importarlo en CurseForge. También incluye un sistema de recomendaciones con IA local.

> **Estado del proyecto:** en desarrollo. La aplicación puede abrirse sin conexión al catálogo, pero la búsqueda de mods reales requiere configurar un acceso autorizado a CurseForge. Las sugerencias de IA y las comprobaciones no garantizan que una combinación de mods funcione al arrancar Minecraft.

## Qué puedes hacer

- Elegir versión de Minecraft y cargador: Forge, Fabric o NeoForge.
- Explorar un catálogo de mods por categorías y búsqueda, cuando la conexión está configurada.
- Añadir y quitar mods de la selección y guardar o reabrir proyectos JSON.
- Revisar dependencias obligatorias e incompatibilidades declaradas.
- Exportar un ZIP con un `manifest.json` y referencias oficiales de CurseForge para su importación.
- Detectar instancias y gestionar perfiles gráficos con copia de seguridad.
- Solicitar recomendaciones mediante un modelo de IA que se ejecuta en el equipo.

## Cómo utilizar ModLab

1. Abre la aplicación y selecciona tu **versión de Minecraft** y el **cargador**.
2. En **Explorar mods**, busca los que quieres añadir. Si el catálogo no está configurado, esa búsqueda no estará disponible.
3. Como alternativa, entra en **Crear con IA**, describe tu modpack y revisa las recomendaciones propuestas.
4. Consulta **Mi modpack** para añadir o retirar elementos.
5. Pulsa **Comprobar pack** para revisar la información de dependencias disponible.
6. Usa **Exportar** para generar el ZIP e impórtalo desde CurseForge, en la opción de importar un modpack.

El archivo exportado contiene referencias como `projectID` y `fileID`. CurseForge se encarga de descargar los JAR permitidos al importar el paquete; ModLab no incluye automáticamente todos los archivos de mods.

## Instalar y ejecutar desde el código

El proyecto está desarrollado en Python y utiliza PySide6 para la interfaz. Para ejecutarlo desde su código fuente:

1. Instala una versión de Python compatible con las dependencias del proyecto.
2. Descarga o clona este repositorio y abre una terminal en su carpeta raíz.
3. Crea y activa un entorno virtual (recomendado).
4. Instala las dependencias y arranca:

```bash
python -m pip install -r requirements.txt
python scripts/fetch_model.py
python app.py
```

`fetch_model.py` descarga la revisión prevista del modelo de IA y verifica su SHA-256. Necesitarás espacio de almacenamiento suficiente: el modelo `Qwen3-4B-Instruct-2507` en GGUF Q4_K_M ocupa aproximadamente 2,5 GB, además de memoria durante su uso. La integración local utiliza `llama-cpp-python`, sin necesidad de Ollama.

## Cómo funciona la conexión con CurseForge

El catálogo utiliza la API de CurseForge y **no incluye una clave privada en el repositorio ni en una descarga pública**.

Para desarrollo personal, puede configurarse una clave autorizada mediante `CURSEFORGE_API_KEY` o desde **Conexión del catálogo**. Sin esta configuración, la aplicación abre, pero no podrá obtener resultados reales del catálogo.

Una clave personal **no debe distribuirse con el programa** para que todo el mundo la reutilice. Las [condiciones de la API para terceros](https://support.curseforge.com/support/solutions/articles/9000207405-curseforge-3rd-party-api-terms-and-conditions) también restringen el acceso mediante proxies. Para ofrecer una descarga con búsqueda lista para cualquier usuario, primero hace falta una integración autorizada por CurseForge.

El archivo `catalog_server.py` es una herramienta experimental de integración, **no un servicio público desplegado ni autorizado**.

## Generar una versión portátil

Si quieres crear un paquete para ejecutar ModLab sin abrir directamente el código:

```bash
python -m pip install "pyinstaller>=6.16,<7"
python build_portable.py
```

El resultado aparece en `dist/`. Distribuye **toda la carpeta generada**, incluido `_internal`. Linux y Windows requieren compilaciones independientes. La compilación hecha en CachyOS utiliza glibc 2.44 y puede no funcionar en distribuciones más antiguas; en ese caso habrá que recompilar en un entorno compatible.

El repositorio también incluye el flujo manual de GitHub Actions `.github/workflows/portable.yml`.

## Cómo comprobar que funciona

Puedes ejecutar las pruebas automatizadas:

```bash
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python app.py --smoke
python scripts/evaluate_ai.py
```

Las pruebas emplean respuestas simuladas de CurseForge. **Superarlas no confirma que la conexión real con la API funcione**, ni que todos los modpacks exportados sean compatibles.

## Archivos principales

- `app.py` y `visual_widgets.py`: interfaz y componentes visuales.
- `curseforge.py`: integración con el catálogo.
- `catalog_server.py`: herramienta experimental de conexión.
- `local_ai.py` e `intelligence.py`: recomendaciones locales.
- `modpack.py`: selección, validaciones y exportación.
- `core.py`: detección de equipo e instancias.
- `build_portable.py` y `scripts/`: empaquetado y pruebas.

Las licencias de las dependencias y del modelo se encuentran en [THIRD_PARTY.md](THIRD_PARTY.md).
