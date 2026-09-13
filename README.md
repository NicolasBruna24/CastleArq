# LocalAI Hub

LocalAI Hub busca ocultar la complejidad de ejecutar modelos de IA localmente
mediante detección automática de hardware, runtimes y backends. El proyecto
prioriza simplicidad, fiabilidad y mantenibilidad, sin instalar drivers,
runtimes ni dependencias del sistema.

## Estado actual

La Fase 2 está implementada:

- detección de sistema operativo, arquitectura, CPU, RAM y GPU en Linux;
- GPU con nombre, fabricante, PCI ID, driver y fuente de cada dato cuando están disponibles;
- detección de VRAM mediante sysfs y, opcionalmente, `vulkaninfo` o `llama ... serve --list-devices`;
- VRAM total y disponible, conservando `Unknown` cuando ninguna fuente lo expone;
- detección de runtimes `llama.cpp / llama.app` y Ollama;
- detección por presencia de Vulkan, OpenCL, SYCL, CUDA y ROCm;
- recomendación basada exclusivamente en lo detectado;
- catálogo pequeño y estático de modelos de coding, general-purpose y reasoning;
- cuantizaciones GGUF aproximadas y estimación explícita de memoria;
- motor de compatibilidad con estados compatible, marginal, incompatible y unknown;
- recomendación ordenada por memoria, calidad, margen, runtime y backend;
- interfaz preparada para futuros runners, sin descargar ni ejecutar modelos.

Los comandos ausentes, salidas inválidas y datos no disponibles se muestran como
`Unknown`, `Not detected` o `not available`; no provocan tracebacks al usuario.

## Instalación y uso

Se requiere Python 3.10 o posterior. No hay dependencias externas en el MVP:

```bash
python3 -m unittest discover
python3 -m app.main detect
python3 -m app.main models
```

La aplicación no usa `sudo`, no modifica el sistema y no instala drivers,
CUDA, ROCm, SYCL, oneAPI ni otros runtimes.

## Arquitectura

- `app/hardware.py`: estructuras y detección de hardware.
- `app/runtimes.py`: detección de runtimes y backends.
- `app/models.py`: metadatos de modelos para una fase futura.
- `app/model_catalog.py`: catálogo curado local, sin red ni scraping.
- `app/compatibility.py`: estimación, compatibilidad y recomendación.
- `app/runner.py`: interfaz abstracta para runners futuros.
- `app/main.py`: CLI.

La detección está separada de la presentación y acepta funciones de ejecución
inyectables, lo que permite probarla sin GPU real. Las fuentes de GPU son
opcionales: si falta `lspci`, sysfs, Vulkan o llama.app, la aplicación continúa
mostrando únicamente la información disponible. No se instala software
automáticamente y no se modifican drivers, kernel ni configuración del sistema.

## Roadmap

1. Detección de hardware y runtimes.
2. Mejora de fuentes de GPU y VRAM (Fase 1.5).
3. Catálogo de modelos y compatibilidad.
4. Descarga de modelos.
5. Ejecución mediante runners.
6. API local compatible con OpenAI.
7. Integración con Aider, Cline, Continue, VS Code y Qwen Code.
8. Interfaz gráfica.
9. Soporte avanzado para NVIDIA/CUDA, AMD/ROCm, Intel/SYCL, Vulkan y otros backends.

No se implementarán marketplace, cuentas, nube, Kubernetes, Docker obligatorio,
telemetría ni gestión automática de drivers en esta fase.

## Fase 2: catálogo y compatibilidad

`models` analiza el catálogo local usando el hardware, runtimes y backends
detectados. La memoria se estima a partir de parámetros, bits por parámetro y
overhead; el resultado se marca siempre como estimado. La VRAM se prioriza y la
RAM puede actuar como respaldo penalizado, pero no se considera equivalente.
Los márgenes se centralizan en `config/config.toml`.

Esta fase no descarga modelos, no consulta Hugging Face, no inicia servidores,
no ejecuta inferencia y no instala software.

La compatibilidad no combina la VRAM de varias GPUs: cada dispositivo se
evalúa individualmente y el análisis multi-GPU avanzado queda para una fase
posterior. La RAM solo se usa como fallback cuando el runtime declara soporte
CPU explícito; en ese caso el resultado se marca como `marginal`.

## Fase 3.0-A: almacenamiento local

La subfase inicial de Fase 3 separa un modelo lógico de un `ArtifactSpec`
descargable y añade manifests JSON al almacenamiento local. Por defecto se usa
`~/.local/share/localai-hub/models`, configurable en `[models]` de
`config/config.toml`. El comando `list` solo inspecciona artifacts locales:

```bash
python3 -m app.main list
```

Los estados distinguen `not_downloaded`, `downloading`, `downloaded`,
`verified` y `failed`. Un checksum disponible se verifica al inspeccionar el
artifact; sin checksum, un archivo nunca se marca como criptográficamente
verificado. El estado operativo se deriva del filesystem y de metadata
verificable; el estado persistido en el manifest es informativo/cache. La ruta
local se deriva siempre del model ID sanitizado, artifact ID y filename, y no
se utiliza ningún `local_path` externo. Esta subfase todavía no accede a
Internet ni descarga archivos.

## Fase 3.0-B.1: Hugging Face metadata discovery

Hugging Face es la primera fuente externa de metadata. La consulta remota es
explícita:

```bash
python3 -m app.main source huggingface owner/repository
```

La operación valida el repository, consulta únicamente la API pública de
metadata y descubre artifacts GGUF convirtiéndolos a `ArtifactSpec`. Conserva
el tamaño y SHA-256 solo cuando Hugging Face los proporciona y detecta
cuantizaciones de forma conservadora. No solicita el contenido de los
artifacts, no descarga modelos y no modifica `ModelStore`. El Download Manager
queda reservado para Fase 3.0-B.2.

## Fase 3.0-B.2.1: planificación de descargas

La planificación valida localmente un `ArtifactSpec` y determina si está
preparado para una futura descarga. Comprueba la fuente, URL de Hugging Face,
filename, formato GGUF, tamaño, SHA-256, destino dentro del `ModelStore`,
estado local y espacio disponible.

El comando `plan` es estrictamente offline:

```bash
python3 -m app.main plan owner/repository model.Q4_K_M.gguf
```

No busca modelos, no consulta Hugging Face, no descarga contenido y no crea
directorios, manifests, archivos `.part` ni artifacts. Con tamaño desconocido
el resultado es `UNKNOWN`, nunca `READY`. La ejecución de descargas queda
reservada para una fase posterior.

## Fase 3.0-B.2.2: descarga básica

La API `Downloader` recibe un `DownloadPlan` `READY`, descarga el contenido
por streaming a un archivo `.part` y publica el artifact mediante una
publicación atómica exclusiva sin reemplazo (`os.link` seguido de la
eliminación del `.part`). La reanudación segura de archivos `.part`
preexistentes mediante HTTP Range se describe en la fase B.2.4 siguiente.

Esta fase no implementa SHA-256, retries, concurrencia ni gestión de manifests
o estados persistidos.

## Fase 3.0-B.2.4: reanudación mediante HTTP Range

Un archivo `.part` existente puede reutilizarse mediante una petición
`Range: bytes=<offset>-`. Solo se anexan datos cuando el servidor responde
`206 Partial Content` con un `Content-Range` coherente con el offset local y
el tamaño esperado. Una respuesta `200` ante una petición Range no se anexa y
un `416 Range Not Satisfiable` preserva el `.part` intacto.

Los errores de red, escritura, `fsync` o validación de rango conservan el
progreso parcial para una ejecución posterior. La publicación final continúa
siendo exclusiva mediante `os.link(.part, final)` seguida de la eliminación
del `.part`. Esta fase todavía no implementa SHA-256, retries ni recovery.

## Fase 3.0-B.2.5: verificación SHA-256

Cuando `ArtifactSpec.sha256` está disponible, `Downloader` calcula el
SHA-256 del `.part` completo en streaming, desde el byte cero, después de
comprobar el tamaño y antes de publicar. Solo un checksum coincidente permite
la publicación exclusiva mediante `os.link(.part, final)` seguida de
`os.unlink(.part)`.

Un checksum incorrecto devuelve `CHECKSUM_MISMATCH`, no publica el artifact y
conserva el `.part` intacto. Si no hay checksum esperado, no se inventa uno y
se mantiene la publicación basada en tamaño. Esta fase no implementa retries,
recovery, reparación automática ni persistencia adicional de manifests.

## Fase 3.0-B.2.6.1: inspección de estado

`ArtifactFilesystemInspector` permite inspeccionar de forma read-only si un
artifact está `CLEAN`, `PARTIAL`, `FINAL_EXISTS` o `INCONSISTENT`. La
inspección no crea directorios, no accede a la red, no modifica manifests ni
elimina archivos `.part`. Los symlinks y paths inseguros se rechazan mediante
las garantías existentes de `ModelStore`.

## Fase 3.0-B.2.6.2: decisiones de recuperación

`RecoveryDecider` transforma el estado inspeccionado en una decisión
read-only: `NO_ACTION`, `RESUME_ELIGIBLE`, `USE_EXISTING` o
`REVIEW_REQUIRED`. No accede al filesystem, no modifica archivos o manifests,
no elimina `.part` y no ejecuta descargas ni recuperación automática.

## Fase 3.0-B.2.6.3: cleanup explícito

`ArtifactCleanup` ejecuta únicamente operaciones destructivas solicitadas de
forma explícita: eliminar el `.part` o eliminar el artifact final. Cada
operación está acotada a su objetivo, nunca elimina manifests ni directorios,
rechaza symlinks y es idempotente cuando el objetivo no existe. No decide
automáticamente qué archivo conservar en estados inconsistentes.

## Fase 4: ejecución de un artifact local

`run` resuelve un modelo lógico contra el catálogo, verifica el artifact local
mediante preflight y lo ejecuta una sola vez con el runtime detectado. No
descarga, no modifica manifests, no altera el estado del artifact ni el
`ModelStore`.

El comando `chat` abre una conversación interactiva multi-turno sobre un único
proceso de runtime:

```text
python3 -m app.main chat <model-id>
```

Sigue el mismo pipeline de seguridad (resolver → preflight → selección) y usa
la misma capa de ejecución que `run`. Escribe `/exit` o pulsa Ctrl+D para
salir; Ctrl+C cancela la generación en curso. El contexto conversacional lo
mantiene el runtime, no la aplicación.

Supuesto: el `ModelStore` local se considera confiable y no compartido con
actores no confiables durante la ejecución. Existe una ventana TOCTOU residual
entre el preflight y el lanzamiento del subprocess: un actor con escritura
sobre el `ModelStore` podría reemplazar o modificar el archivo en ese
intervalo. Eliminarla por completo requeriría mecanismos adicionales (file
descriptors, locks o publicación por inodo), fuera del alcance actual de
Fase 4.
