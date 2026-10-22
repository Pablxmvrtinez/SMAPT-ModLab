# S.M.A.P.T. ModLab · Acheron

Aplicación de escritorio con dos modos: **Crear con IA** y **Explorar mods**.
El catálogo y los manifiestos usan exclusivamente CurseForge.

## Qué incluye

- Inicio visual con paisaje isométrico original y 24 accesos temáticos.
- Biblioteca de tarjetas con imágenes/logos de CurseForge, etiquetas, descargas,
  descripción, ficha y botón para añadir al pack.
- Paginación de 50 mods, orden por descargas/popularidad/actualización y todas las
  categorías que devuelva la API oficial. No está limitada a una lista prefijada.
- IA local integrada que interpreta una descripción completa, obtiene alternativas
  del catálogo y explica aportación, función y límites de cada recomendación.
- Hasta 400 mods elegidos como techo configurable; no se rellena con contenido
  irrelevante para alcanzar un número. Se pueden combinar recomendaciones con
  todos los mods que se añadan manualmente desde la biblioteca.
- Pack que conserva su selección al navegar, evita duplicados y guarda/abre proyectos.
- Comprobación previa del modpack sin modificar la selección: revisa versiones,
  dependencias obligatorias e incompatibilidades declaradas por CurseForge.
- Exportación nativa: `manifest.json` con `projectID` y `fileID` oficiales. CurseForge
  descarga los archivos al importar el ZIP; no se redistribuyen JAR dentro de la app.
- Detección de hardware e instancias y optimizador gráfico con copia de seguridad.

## Conexión con CurseForge: requisito pendiente del desarrollador

**La API oficial exige una clave de desarrollador. Este repositorio no incluye una
clave y no muestra resultados ficticios cuando el catálogo no está conectado.**

[Solicita una clave para SMAPT ModLab](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key).

Para pruebas propias, establece `CURSEFORGE_API_KEY` en tu entorno o introduce la
clave en **Conexión del catálogo**. La clave de prueba permanece en memoria y no
se guarda en el proyecto ni se incluye en el paquete.

Para compartir la aplicación con amigos sin pedirles claves:

1. Ejecuta `catalog_server.py` en un servidor del desarrollador con
   `CURSEFORGE_API_KEY` configurada como secreto. La clave nunca va con el cliente.
2. Publica esa pasarela detrás de HTTPS. Por defecto escucha en localhost:8765;
   `SMAPT_BIND` y `PORT` permiten ajustar la escucha. El proceso de publicación no
   se ejecuta automáticamente desde este proyecto.
3. Construye la aplicación con `SMAPT_CATALOG_URL=https://tu-pasarela.example`.
   Solo esa URL pública queda en `app-config.json` dentro del paquete.

La pasarela solo admite rutas GET de catálogo, fija Minecraft (432) y Mods (6),
limita parámetros y consultas por IP, sin caché de respuestas. No expone la clave ni el
cuerpo privado de errores del proveedor. No es un servicio de inferencia de IA.
La configuración de CurseForge corresponde al desarrollador, no a cada amigo.

Antes de publicar la pasarela, solicita a CurseForge la aprobación de la arquitectura
y del uso de metadatos en proyectos y manifiestos. La solicitud de API está pendiente;
el código preparado no implica que CurseForge haya autorizado su funcionamiento.

Sin clave/pasarela es posible abrir y revisar la interfaz, pero las búsquedas y la
curación sobre datos reales siguen pendientes de esa conexión. No hay sustitución
por Modrinth ni scraping de la web para evitar la autenticación.

## Uso

1. Abre el ejecutable del paquete completo.
2. En **Crear con IA**, describe cómo quieres jugar, lo que quieres evitar y las
   limitaciones del equipo. No necesitas escoger categorías. Revisa la explicación
   y añade lo que encaje al pack.
3. En **Explorar mods**, navega por tarjetas, temas o búsquedas y añade más opciones.
4. En **Mi modpack**, pulsa **Comprobar pack** para consultar dependencias y
   conflictos declarados, y después **Crear ZIP para CurseForge**.
5. En CurseForge: Minecraft → Importar → selecciona el ZIP.

Minecraft y cargador son ajustes técnicos compartidos por ambos modos. Si cambian,
la selección se conserva y los archivos se verifican de nuevo. Al exportar se
resuelven las dependencias obligatorias y se rechazan incompatibilidades declaradas.

La asignación real de RAM la hace el lanzador. La compatibilidad completa, el
arranque en Minecraft y el rendimiento necesitan una prueba del juego.

## IA incluida, sin agentes externos

El paquete completo incorpora `llama-cpp-python` y Qwen3-4B-Instruct-2507 en GGUF
Q4_K_M (cuantización de Unsloth, modelo de Qwen, Apache-2.0). No necesita Ollama,
cuenta de OpenAI, claves de IA ni procesos de agentes instalados aparte.
El modelo ocupa aproximadamente 2,5 GB en disco. Durante la inferencia consume
varios GB de RAM y CPU; en equipos modestos puede tardar varios minutos. La memoria
se libera al terminar el diseño. Explorar mods no carga el modelo.

El diseño usa el texto completo y las negaciones. El modelo propone objetivos y
consultas funcionales; las consultas recuperan candidatos, no deciden por sí solas
su pertinencia. Otra evaluación del modelo considera el conjunto y genera motivos
por mod, descartando IDs incoherentes o puntuaciones no válidas. No se promete
comprensión infalible: revisa los supuestos, exclusiones y razones antes de añadir.

La selección trabaja con los datos de las fichas del catálogo; cuando son escuetos
puede faltar información para justificar una recomendación. Las razones son criterio
del modelo, no FPS medidos ni una garantía de compatibilidad.

## Desarrollar y construir paquetes

En un entorno virtual del desarrollador:

```bash
python -m pip install -r requirements.txt
python scripts/fetch_model.py
python app.py
```

El script descarga una revisión fija del modelo y verifica tamaño y SHA-256.
El usuario final recibe el modelo y el motor incluidos; no hace estos pasos.

```bash
python -m pip install "pyinstaller>=6.16,<7"
python build_portable.py
```

Se genera un paquete en `dist/` para el sistema actual. Extrae y comparte la carpeta
completa, incluido `_internal`. Linux y Windows necesitan sus propias compilaciones.
El flujo manual de GitHub Actions prepara ambos, incorpora el modelo y usa la variable
pública `SMAPT_CATALOG_URL`; no recibe ni empaqueta la clave privada de CurseForge.
El paquete local de Linux se construye en CachyOS/glibc 2.44; otras distribuciones
requieren comprobar compatibilidad o compilar desde una base más antigua.

## Validación

```bash
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python app.py --smoke
python scripts/evaluate_ai.py
```

Las pruebas unitarias usan respuestas de CurseForge y modelos simulados: validan
contratos, fuente, autenticación, dependencias, ZIP, paginación, selección y flujo Qt.
`evaluate_ai.py` ejecuta el modelo real con descripciones opuestas y un conjunto
explícito de fichas de evaluación; no finge resultados de una consulta en vivo.
La comprobación completa con la API real requiere la clave del desarrollador.

## Archivos

- `app.py`: navegación y flujos de la aplicación.
- `visual_widgets.py`: tarjetas, carga asíncrona de imágenes y arte de interfaz.
- `curseforge.py`: catálogo oficial, archivos y dependencias.
- `catalog_server.py`: pasarela del desarrollador para compartir la app sin claves.
- `local_ai.py` / `intelligence.py`: inferencia local y diseño contextual.
- `modpack.py`: manifiesto nativo y detección del cargador.
- `core.py`: hardware, instancias y optimizador.
- `build_portable.py` / `scripts/`: construcción y evaluación.
