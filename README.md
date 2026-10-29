![SMAPT ModLab, cabecera oscura de inspiración shinobi](assets/kakashi-inspired-banner.svg)

<p align="center">
  <strong>Un modpack a tu medida, desde el escritorio.</strong>
</p>
<p align="center">
  <code>Python</code> · <code>PySide6</code> · <code>CurseForge</code> · <code>Modrinth</code> · <code>IA local</code>
</p>

<p align="center">
  <a href="#funciones">Funciones</a> ·
  <a href="#curseforge">CurseForge</a> ·
  <a href="#ejecutar-desde-el-código">Instalación</a> ·
  <a href="#paquetes-portables">Paquetes</a> ·
  <a href="#pruebas">Pruebas</a>
</p>

---

Aplicación de escritorio para montar modpacks de Minecraft. Busca mods en **CurseForge** y **Modrinth**,
comprueba dependencias e incompatibilidades declaradas y exporta packs listos para importar en el lanzador.
Opcionalmente, un modelo de lenguaje que se ejecuta en tu propio equipo propone mods a partir de cómo quieres jugar.

## Funciones

- **Explorar mods** en CurseForge o Modrinth: búsqueda instantánea, categorías, orden y paginación,
  filtrada por versión de Minecraft y cargador (Forge, NeoForge, Fabric y Quilt).
- **Ficha de cada mod**: portada e imágenes reales, descripción, todas las versiones publicadas
  (puedes fijar una concreta, incluidas betas), dependencias obligatorias y opcionales, incompatibilidades y galería.
- **Mi modpack**: selección persistente entre páginas y catálogos, filtros por catálogo y comprobación completa:
  archivo compatible de cada mod, dependencias obligatorias que se añadirán e incompatibilidades declaradas.
- **Exportar**:
  - ZIP de CurseForge (`manifest.json` con `projectID`/`fileID`); el lanzador descarga los JAR al importar.
  - `.mrpack` de Modrinth (`modrinth.index.json` con hashes SHA-1/SHA-512, `env` y descargas de `cdn.modrinth.com`).
- **Descargar mods** a una carpeta (por ejemplo, la carpeta `mods` de una instancia) con progreso real y verificación
  de hash. Los mods de CurseForge cuyo autor no permite descargas de terceros se enlazan para descargarlos desde la web.
- **Proyectos** `.json` para guardar y retomar la selección.
- **Crear con IA** (opcional): el modelo local interpreta ritmo, actividades y exclusiones, busca en el catálogo elegido
  y explica cada propuesta.
- **Mi equipo**: CPU, GPU (NVIDIA, AMD e Intel), RAM y sistema; instancias de CurseForge, Prism (nativo y Flatpak),
  MultiMC, Modrinth App, ATLauncher y el lanzador oficial, en Windows y Linux.
- **Optimizar**: perfil gráfico por instancia con copia de seguridad previa y restauración.

ModLab no garantiza que Minecraft arranque con cualquier combinación: los conflictos no declarados y el rendimiento
real hay que comprobarlos jugando.

## CurseForge

ModLab usa la [API REST oficial](https://docs.curseforge.com/rest-api/) (`https://api.curseforge.com`) con la
cabecera `x-api-key`. Según los términos de la API de terceros, **la clave no se comparte** y **los datos de la API no
se guardan ni se cachean**; ModLab cumple ambas cosas:

- La clave se lee de la variable de entorno `CURSEFORGE_API_KEY` (o se introduce en Ajustes solo para la sesión).
  Únicamente se envía a `api.curseforge.com`; nunca se escribe en disco, registros, proyectos ni paquetes.
- Las respuestas de CurseForge no se cachean. Los proyectos guardan solo tu selección (IDs, título y archivo fijado).
- Las descargas respetan `allowModDistribution`: si el autor no las permite, ModLab no descarga el archivo y muestra
  el enlace oficial.

### Uso con tu clave (desarrollo)

```bash
export CURSEFORGE_API_KEY='tu-clave'
python app.py
python scripts/check_live.py curseforge
```

En Windows (PowerShell): `$env:CURSEFORGE_API_KEY='tu-clave'`. `check_live.py` recorre búsqueda, filtros, ficha,
descripción, versiones, dependencias, URL de descarga y resolución completa, sin mostrar la clave.

### Distribuir ModLab sin entregar la clave (pasarela)

Para que otras personas usen el catálogo de CurseForge, publica `catalog_server.py` en un servidor propio:

1. Configura `CURSEFORGE_API_KEY` en el servidor y arranca `python catalog_server.py`
   (escucha en `127.0.0.1:8765`; `SMAPT_BIND` y `PORT` lo cambian; `SMAPT_RATE_LIMIT` fija consultas por minuto e IP).
2. Publícala detrás de un proxy HTTPS. Si el proxy añade `X-Forwarded-For`, define `SMAPT_TRUST_PROXY=1`.
3. Construye el paquete con `SMAPT_CATALOG_URL=https://tu-servidor.example`; la URL se guarda en `app-config.json`.

La pasarela solo admite rutas de lectura de mods de Minecraft, valida parámetros y cuerpos, limita peticiones por IP,
responde con `Cache-Control: no-store` y no guarda respuestas. `GET /health` indica si tiene clave configurada.
Antes de publicarla para terceros, confirma con CurseForge que tu autorización cubre ese uso.

## Modrinth

Catálogo público de la [API v2](https://docs.modrinth.com/api/): no necesita clave. ModLab se identifica con su
User-Agent y guarda en caché (disco, unos minutos) las consultas para respetar el límite de 300 peticiones por minuto.

## Ejecutar desde el código

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
. .venv/bin/activate                     # Windows: .venv\Scripts\activate
python -m pip install -r requirements-lite.txt   # sin IA
python app.py
```

Para la IA local (unos 2,5 GB de modelo y 5,5 GB de RAM libre mientras trabaja):

```bash
python -m pip install -r requirements.txt
python scripts/fetch_model.py
python app.py --verify-ai
```

`fetch_model.py` descarga una revisión fija de `Qwen3-4B-Instruct-2507` (GGUF Q4_K_M) y comprueba su SHA-256.

Atajos: `Ctrl+1…7` secciones, `Ctrl+F` buscar, `Ctrl+S` guardar proyecto, `Ctrl+O` abrir, `Esc` volver.

## Paquetes portables

```bash
python -m pip install "pyinstaller>=6.16,<7"
python build_portable.py --lite   # edición ligera (sin IA)
python build_portable.py          # edición completa (con IA)
```

El paquete se crea en `dist/` (carpeta + `.tar.gz` en Linux o `.zip` en Windows). Hay que distribuir la carpeta
completa, incluido `_internal`. Linux y Windows se compilan por separado; el workflow manual
`.github/workflows/portable.yml` construye ambos. Un paquete Linux construido en una distribución reciente puede
necesitar una base más antigua (glibc) para funcionar en otras.

## Pruebas

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python app.py --smoke
python scripts/check_live.py            # catálogos reales (Modrinth siempre; CurseForge con clave o pasarela)
python scripts/evaluate_ai.py           # calidad del modelo local con casos del proyecto
```

Las pruebas unitarias no usan la red: simulan CurseForge y Modrinth. `.github/workflows/tests.yml` las ejecuta en
Linux y Windows en cada push y pull request.

## Datos locales

| Qué | Linux | Windows |
| --- | --- | --- |
| Ajustes | `~/.config/SMAPT/SMAPT-ModLab/` | `%LOCALAPPDATA%\SMAPT\SMAPT-ModLab\` |
| Caché (Modrinth e imágenes) | `~/.cache/SMAPT/SMAPT-ModLab/` | `%LOCALAPPDATA%\SMAPT\SMAPT-ModLab\cache\` |
| Registros | `~/.local/state/SMAPT/SMAPT-ModLab/logs/` | `%LOCALAPPDATA%\SMAPT\SMAPT-ModLab\logs\` |

Los registros no contienen claves ni cabeceras y acortan las rutas personales a `~`.

## Código

- `app.py`: arranque, pantalla de carga y comprobaciones (`--smoke`, `--verify-ai`).
- `modlab/sources/`: catálogos (`curseforge.py`, `modrinth.py`) y resolución común de dependencias (`base.py`).
- `modlab/http.py`, `errors.py`, `logs.py`, `paths.py`, `settings.py`: red, errores, registro, rutas y ajustes.
- `modlab/project.py`, `modpack.py`, `downloads.py`: modelo del pack, exportación y descargas.
- `modlab/core.py`: equipo, instancias y perfiles gráficos.
- `modlab/intelligence.py`, `local_ai.py`: diseñador con IA y modelo local.
- `modlab/ui/`: ventana, páginas, componentes, tema, iconos, imágenes y tareas en segundo plano.
- `catalog_server.py`: pasarela de CurseForge. `build_portable.py` y `scripts/`: empaquetado y comprobaciones.

Las licencias de las bibliotecas y del modelo están en [THIRD_PARTY.md](THIRD_PARTY.md). Los mods pertenecen a sus
autores y se rigen por sus propias licencias.
