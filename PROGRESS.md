# Progreso de S.M.A.P.T. ModLab 2.0

Registro de trabajo para poder retomar la tarea si la sesión se interrumpe.
Rama: `modlab-2.0` (remota `origin/modlab-2.0`). Incluye la fusión de `origin/main` (17 commits del 22–24 oct):
su validador `.mrpack`, nombres válidos en Windows, entornos de Modrinth, copias sin colisiones, seguridad de
proyectos, prueba real de Modrinth y publicación de betas se integraron en la estructura `modlab/`.
`public_catalog.py` y `public_page.py` se retiraron porque `modlab/sources/modrinth.py` y la interfaz nueva los sustituyen.
Diferencia deliberada: un ciclo de dependencias obligatorias (A↔B) se resuelve incluyendo ambos mods en lugar de
bloquear la exportación; sí se avisa si dos mods exigen versiones distintas de la misma dependencia.

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
- [x] Fase 3 · Interfaz nueva (`modlab/ui/`)
  - Sistema de diseño: tokens de color, hoja de estilos, iconos SVG propios, tipografía y espaciado coherentes.
  - Navegación lateral (se compacta por debajo de 1180 px), barra superior con versión/cargador globales.
  - Tarjetas con portada y logo reales, insignia de catálogo, estado Añadir/Añadiendo/En el pack.
  - Esqueletos animados de carga, estados vacíos y de error con acciones, avisos (toasts), fundido entre páginas.
  - Explorar: CurseForge/Modrinth, búsqueda instantánea (450 ms), categorías, orden, paginación.
  - Ficha de mod: portada, descripción saneada, versiones (elegir una concreta), dependencias, galería.
  - Mi modpack: tabla, filtros por catálogo, comprobación con informe, exportar .zip/.mrpack, descargar mods.
  - Mi equipo, Optimizar (con restaurar copia) y Ajustes (conexión, caché, registros, IA).
  - Pantalla de carga (splash) y barra de actividad con progreso real y cancelación.
  - Tareas con QThreadPool: varias a la vez, la búsqueda nueva sustituye a la anterior.
- [x] Fase 4 · Refactorización y rendimiento
  - Caché de imágenes por presupuesto de bytes (96 MB) y escalado a la densidad real de pantalla.
  - Decodificación de imágenes en hilos de trabajo (QImage), sin bloquear la interfaz.
  - Sesión HTTP compartida por cliente (antes CurseForge abría una conexión nueva por consulta).
  - Gancho global de excepciones: se registra y se avisa sin cerrar la app.
  - Ajustes guardados al cambiar versión/cargador; logotipo real (assets/icon.svg) en barra lateral, splash y ejecutable.
  - requirements-lite.txt (sin IA) + requirements.txt (completa); build_portable.py con `--lite` e iconos generados.
  - CI: `tests.yml` (Linux y Windows, Python 3.11/3.12) en cada push/PR; `portable.yml` con edición ligera/completa.
  - Medido (datos reales de Modrinth): ventana visible 0,30 s; 50 tarjetas 0,35 s; 273 MB tras 6 páginas; CPU en reposo 0,7 %.
- [x] Fase 5 · Funciones restantes y errores
  - IA local verificada con el modelo real (`--verify-ai`) desde el código y desde el paquete con IA.
  - Prueba real de propuesta con IA sobre Modrinth: falló en el primer lote por un descarte repetido del modelo;
    corregido (IDs 1..20 por lote, descartes tolerantes, fichas sin valorar descartadas con aviso).
    Repetida tras la corrección: 8 mods coherentes con la petición (Sodium, Lithium, ModernFix, FerriteCore,
    Macaw's Furniture, Another Furniture, Handwerk, Adaptive Performance Tweaks), sin magia, en 185 s de CPU.
  - Navegación «Volver» simplificada; autor, descripción y build manual del cargador coherentes en el pack.
  - Pasarela probada como proceso real contra la API de CurseForge (clave inválida → 403 claro, sin filtrar la clave).
  - Fusión de `origin/main` (validador .mrpack, nombres Windows, entornos, copias sin colisión, seguridad de proyectos).
- [x] Fase 6 · Pruebas, compilación y documentación
  - Compilación anterior (16-oct) conservada en `dist/anterior-1.0-2026-10-16/`.
  - Edición pública Linux: `dist/SMAPT-ModLab-linux-x86_64.tar.gz` (115 MB, 276 MB descomprimida), arranque `--smoke` OK,
    plugins WebP/SVG incluidos, sin claves ni modelo.
  - Edición con IA Linux: `dist/SMAPT-ModLab-IA-linux-x86_64.tar.gz` (2,7 GB), `--smoke` y `--verify-ai` OK.
  - Windows: se compila y prueba en GitHub Actions (`portable.yml`, `tests.yml`); no se ha probado en un equipo real.

## Misión «Crear con IA» (30-oct)

Diagnóstico con el modelo real: consultas limitadas a 60 conceptos fijos («parecido a Pokémon» → «machines»),
exclusiones inventadas, sesgo hacia mods de rendimiento y lotes lentos (≈150 s por 20 fichas).

- [x] Arquitectura nueva (`modlab/intelligence.py`): rechazos en una pregunta propia con citas verificadas,
      plan con búsquedas libres, categorías asignadas después del plan, recuperación paralela con búsqueda
      relajada, filtro de exclusiones y bibliotecas, evaluación por lotes de 10, montaje equilibrado.
- [x] Motor (`local_ai.py`, `ai_setup.py`): modelo en el paquete o descargado (reanudable, SHA-256), instalación
      del motor con pip en entornos virtuales, 6 núcleos físicos, contexto 8192, cancelación.
- [x] Interfaz: modos Recomendar / Crear modpack, catálogo, versión, cargador, nº de mods, rendimiento, fases
      con progreso real, interpretación visible, tarjetas con descartar, vista previa editable, exportar,
      panel «Configurar IA».
- [x] Evaluación semántica real (`scripts/evaluate_ai.py`, 10 descripciones): 5/10 → 6/10 → 6/10 → 9/10 → 9/10
      → **10/10** con la versión final (rechazos con sinónimos; singular/plural; sin palabras genéricas).
      `tests/test_ai_real.py` (SMAPT_REAL_AI=1): 3/3 con el modelo real.
- [x] Interfaz real + IA real (ventana fuera de pantalla): modpack zombi en 181 s, la interfaz nunca se bloqueó
      más de 69 ms (3616 mediciones), vista previa → Mi modpack → .mrpack exportado desde la interfaz y validado.
- [x] Extremo a extremo real (`scripts/ai_e2e.py`, Modrinth 1.20.1 Fabric):
      casas (crear) 117-140 mods encontrados → pack equilibrado + Fabric API → .mrpack validado (≈210 s);
      «parecido a Pokémon» → Cobblemon 10/10 sin conocer el nombre; apocalipsis zombi → Zombie Apocalypse Core,
      Guns++, MC: Zombified, ruinas y mapas.
- Limitaciones conocidas: en CPU una propuesta tarda 3-4 min; el modelo 4B a veces inventa detalles en los
      motivos (p. ej. «biomas urbanos» de Biomes O' Plenty) aunque el mod sea real y compatible; la GPU
      (RTX 4060) no se usa: requiere recompilar llama-cpp-python con CUDA o Vulkan (vulkan-headers, sudo).

## Estado de las pruebas

- 168 pruebas unitarias en verde (sin red) + 3 con el modelo real, arranque `--smoke` correcto, pyflakes limpio.
- Modrinth verificado en vivo con `scripts/check_live.py modrinth` y `scripts/modrinth_live_smoke.py`.
- Windows: no probado en una máquina real; el workflow `tests.yml` lo cubrirá en GitHub Actions.

## Bloqueos

- **Prueba real de CurseForge:** requiere `CURSEFORGE_API_KEY` en el entorno.
  Cuando esté definida: `python scripts/check_live.py curseforge`.
