# SMAPT ModLab

Aplicación de escritorio para montar modpacks de Minecraft. Permite buscar mods en CurseForge, guardarlos en un proyecto y preparar un ZIP para importarlo en el lanzador. También tiene un modo de recomendaciones con un modelo de lenguaje que se ejecuta en el propio equipo.

## Funciones

- Navegar por el catálogo de CurseForge, con categorías, búsqueda y páginas de 50 resultados.
- Elegir la versión de Minecraft y el cargador (Forge, Fabric o NeoForge).
- Añadir o quitar mods sin perder la selección al cambiar de pantalla.
- Guardar y abrir proyectos JSON.
- Revisar dependencias obligatorias e incompatibilidades declaradas antes de exportar.
- Generar un ZIP con `manifest.json`, referencias oficiales `projectID` y `fileID`, y una lista de mods. CurseForge descarga los JAR al importar el pack.
- Consultar las instancias detectadas y crear perfiles gráficos con copia de seguridad.

El programa no comprueba que Minecraft vaya a arrancar con todas las combinaciones. Los conflictos no declarados y el rendimiento real hay que probarlos en el juego.

## Catálogo de CurseForge

**Todavía falta configurar una clave de desarrollo o una pasarela.** Sin esa conexión la aplicación abre, pero no puede buscar mods reales.

La clave para desarrollo se puede pasar mediante `CURSEFORGE_API_KEY` o desde **Conexión del catálogo**. No se guarda dentro de los proyectos. Para compartir la aplicación sin entregar la clave, está `catalog_server.py`: consulta CurseForge desde un servidor propio y devuelve los resultados a ModLab.

1. Solicita una [clave de la API de CurseForge](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key).
2. Configura `CURSEFORGE_API_KEY` en el servidor y publica la pasarela mediante HTTPS. Por defecto, la pasarela escucha en `127.0.0.1:8765`; `SMAPT_BIND` y `PORT` permiten cambiarlo.
3. Al crear el paquete, indica `SMAPT_CATALOG_URL=https://tu-servidor.example`. La URL se guarda en `app-config.json`; la clave no debe incluirse en el cliente.

La pasarela admite únicamente las rutas necesarias de CurseForge para Minecraft, limita parámetros y peticiones por IP y no almacena respuestas en caché. No permite usar otras API como sustituto. Antes de publicarla para terceros hay que comprobar las condiciones y autorizaciones de CurseForge para ese uso.

## Recomendaciones locales

El paquete completo utiliza `llama-cpp-python` y el modelo `Qwen3-4B-Instruct-2507` en formato GGUF Q4_K_M. No hace falta instalar Ollama ni contratar otro servicio de IA. El modelo ocupa unos 2,5 GB y necesita varios GB de memoria cuando está funcionando.

La IA interpreta lo que escribes y propone mods del catálogo que puedan encajar. Sus razones son orientativas: una recomendación no equivale a una prueba de compatibilidad.

## Uso

1. Abre ModLab y selecciona versión de Minecraft y cargador.
2. Busca mods en **Explorar mods** o introduce lo que quieres en **Crear con IA**.
3. Revisa y modifica la selección en **Mi modpack**.
4. Pulsa **Comprobar pack** y revisa las dependencias.
5. Exporta el ZIP e impórtalo en CurseForge desde Minecraft → Importar.

El cargador necesita una versión válida para exportar. ModLab puede consultar sus metadatos oficiales o aceptar una versión introducida manualmente. La RAM definitiva se configura en el lanzador.

## Ejecutar desde el código

En un entorno virtual de Python:

```bash
python -m pip install -r requirements.txt
python scripts/fetch_model.py
python app.py
```

`fetch_model.py` descarga una revisión concreta del modelo y comprueba su SHA-256. Para generar una versión portátil:

```bash
python -m pip install "pyinstaller>=6.16,<7"
python build_portable.py
```

El paquete se crea en `dist/`. Hay que distribuir la carpeta completa, incluido `_internal`. Linux y Windows se compilan por separado. La versión Linux construida en CachyOS utiliza glibc 2.44; en otras distribuciones puede hacer falta compilar desde una base compatible. Hay un workflow manual en `.github/workflows/portable.yml`.

## Pruebas

```bash
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python app.py --smoke
python scripts/evaluate_ai.py
```

Las pruebas del repositorio usan respuestas simuladas de CurseForge; no verifican una conexión real con el proveedor. `evaluate_ai.py` permite comprobar el modelo con ejemplos de evaluación definidos en el propio proyecto.

## Código y dependencias

- `app.py`: ventanas y navegación.
- `visual_widgets.py`: tarjetas e imágenes del catálogo.
- `curseforge.py` y `catalog_server.py`: consultas, archivos y pasarela.
- `local_ai.py` e `intelligence.py`: modelo local y recomendaciones.
- `modpack.py`: comprobación y exportación del modpack.
- `core.py`: detección del equipo e instancias.
- `build_portable.py` y `scripts/`: empaquetado y pruebas.

Las licencias de las bibliotecas y del modelo están recogidas en [THIRD_PARTY.md](THIRD_PARTY.md).
