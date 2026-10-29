# Progreso de S.M.A.P.T. ModLab 2.0

Registro de trabajo para poder retomar la tarea si la sesión se interrumpe.
Rama: `main` (solo commits locales; nada publicado en remoto).

## Fase 1 · Inspección (completada)

Estado inicial: 47 pruebas en verde, catálogo exclusivo de CurseForge, una única
tarea en segundo plano a la vez y la interfaz entera en `app.py`.

### Hallazgos

| # | Área | Problema |
|---|------|----------|
| 1 | Modrinth | **No existía integración con Modrinth** ni exportación `.mrpack`; el código rechazaba explícitamente `source: modrinth`. Se añade como catálogo independiente, no como sustituto de CurseForge. |
| 2 | CurseForge | Resolución de dependencias N+1: una o varias peticiones por mod y por dependencia; `compatible_file` podía paginar hasta 200 veces. |
| 3 | CurseForge | Solo se admitían archivos `release`; un mod con solo betas no se podía añadir ni elegir versión manualmente. |
| 4 | CurseForge | Sin descargas de archivos, sin consulta de versiones ni de dependencias opcionales desde la interfaz. |
| 5 | CurseForge | Los errores 404/5xx/red se mostraban con el mismo mensaje genérico y sin reintentos. |
| 6 | Términos CF | Los proyectos guardaban fichas completas de la API (descripciones, imágenes). Los términos de la API de terceros (§3.1) prohíben guardar o cachear datos de la API. |
| 7 | UI | Una sola tarea a la vez: mientras cargaba una descripción se bloqueaba toda la aplicación y los clics se ignoraban en silencio. |
| 8 | UI | `show_details`: si se cerraba el diálogo antes de recibir la descripción, el callback escribía en un widget destruido. |
| 9 | UI | `choose_theme` sin categorías cargadas mezclaba clases y categorías y dejaba una función sin usar. |
| 10 | Rendimiento | `hardware()` (con `nvidia-smi`, hasta 5 s) e `instances()` se ejecutaban en el hilo principal antes de mostrar la ventana. |
| 11 | Rendimiento | Imágenes sin caché entre páginas y escaladas a 640×360 para cada tarjeta. |
| 12 | Portabilidad | `hardware()` solo leía `/proc/cpuinfo` y `nvidia-smi`; la interfaz mostraba «CachyOS / KDE Plasma» fijo. |
| 13 | Portabilidad | Instancias: solo CurseForge (ruta Linux) y Prism Flatpak. Faltaban Windows, Prism nativo, MultiMC, Modrinth App, ATLauncher y el lanzador oficial. |
| 14 | Calidad | Sin registro de errores; excepciones arbitrarias mostradas como texto crudo (por ejemplo `'data'`). |
| 15 | Calidad | Código muerto: `save_plan`/`planes/`, imports sin uso (`QSplitter`, `connection_from_environment`, `save_plan`), parámetro `variant` sin uso. |
| 16 | Exportación | Autor (`SMAPT ModLab`) y versión (`1.0.0`) fijos en el manifest. |
| 17 | Datos | Versiones de Minecraft codificadas a mano; Quilt definido pero no seleccionable. |
| 18 | CI | Solo un workflow manual que exige compilar llama.cpp y descargar 2,5 GB; sin pruebas automáticas en push/PR. |
| 19 | Entorno | `CURSEFORGE_API_KEY` no está definida en este equipo (ni shell, fish, systemd ni `.env`). |

## Fases

- [x] Fase 1 · Inspección
- [x] Fase 2 · CurseForge completo (+ Modrinth, descargas, `.mrpack`)
  - Paquete `modlab/` (fuentes, HTTP, proyecto, exportación, descargas, registro).
  - CurseForge: lotes `POST /v1/mods` y `/v1/mods/files`, índice `latestFilesIndexes`, versiones,
    dependencias tipadas, betas con permiso explícito, `download-url`, respeto de `allowModDistribution`,
    errores 401/403/404/429/5xx diferenciados, reintentos, sin caché (§3.1).
  - Modrinth: búsqueda con facetas, categorías, versiones, dependencias (también por versión), caché en disco.
  - Exportación `.mrpack` (hashes SHA-1/SHA-512, `env`, dominios admitidos) y ZIP de CurseForge con autor/versión.
  - Descargas con verificación de hash, escritura atómica y dominios permitidos.
  - Pasarela: rutas nuevas de solo lectura, POST por lotes validados, `no-store`, `/health`, límite configurable.
  - `scripts/check_live.py`: Modrinth verificado en vivo (búsqueda, filtros, deps Iris→Sodium, `.mrpack`, descarga).
- [ ] Fase 3 · Interfaz nueva
- [ ] Fase 4 · Refactorización y rendimiento
- [ ] Fase 5 · Funciones restantes y errores
- [ ] Fase 6 · Pruebas, compilación y documentación

## Bloqueos

- **Prueba real de CurseForge:** requiere `CURSEFORGE_API_KEY` en el entorno.
  Cuando esté definida: `python scripts/check_live.py curseforge`.
