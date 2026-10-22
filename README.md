<p align="center">
  <strong>Un modpack a tu medida, desde el escritorio.</strong>
</p>
<p align="center">
  <code>Python</code> · <code>PySide6</code> · <code>CurseForge</code> · <code>IA local</code>
</p>

<p align="center">
  <a href="#funciones">Funciones</a> ·
  <a href="#uso">Uso</a> ·
  <a href="#ejecutar-desde-el-código">Instalación</a> ·
  <a href="#pruebas">Pruebas</a>
</p>

---

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

ModLab está diseñado para explorar mods de Minecraft desde la propia aplicación: buscar por nombre, filtrar resultados y seleccionar los archivos adecuados para la versión y el cargador elegidos.

**Estado actual:** la búsqueda real necesita acceso a la API oficial de CurseForge. La aplicación puede iniciarse sin ese acceso, pero el catálogo no estará disponible hasta configurarlo. No se incluye ninguna clave privada en las descargas.

La clave de API identifica al desarrollador autorizado; no es una contraseña que deba copiarse en una descarga pública. Para pruebas personales puede configurarse mediante la variable `CURSEFORGE_API_KEY` o la pantalla **Conexión del catálogo**.

Para distribuir ModLab con un catálogo que funcione sin pedir credenciales a cada usuario, antes es necesario acordar con CurseForge un mecanismo autorizado. Sus [condiciones para desarrolladores externos](https://support.curseforge.com/support/solutions/articles/9000207405-curseforge-3rd-party-api-terms-and-conditions) prohíben compartir la clave y restringen el uso de proxies. El proyecto incluye `catalog_server.py` como herramienta técnica experimental, **no como una pasarela pública ya aprobada ni desplegada**.

Los modpacks exportados incluyen referencias oficiales a los archivos, para que CurseForge gestione la importación y las descargas. La disponibilidad de cada mod también depende de los permisos definidos por su autor.

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
