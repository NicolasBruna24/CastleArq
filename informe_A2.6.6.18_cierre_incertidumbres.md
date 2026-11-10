# Informe A2.6.6.18 — Cierre de incertidumbres y especificación de implementación multi-runtime

**Objetivo:** Cerrar las dos incertidumbres pendientes de A2.6.6.17 y producir una especificación técnica para la admisión multi-runtime en CastleArq Core (arquitectura: admisión por backend, alternativa B).

**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA. Investigación y diseño exclusivamente. No se implementó ninguna política. No se modificó ningún archivo ni repositorio.

---

## 1. Incertidumbre 1 — Evidencia de offload SYCL

### 1.1 Formato exacto del mensaje de offload

Se inspeccionó el código fuente de la versión llama.cpp utilizada en el build SYCL (`/home/brunapc/llama.cpp-sycl/src/llama-model.cpp`). En la línea 2006 se encuentra:

```c
LLAMA_LOG_INFO("%s: offloaded %d/%d layers to GPU\n", __func__, std::min(n_gpu_layers, max_offloadable_layers), max_backend_supported_layers);
```

Donde `__func__` = `llama_model_base::load_tensors` (línea 1581).

**Mensaje exacto producido por el build 11776:**
```
llama_model_base::load_tensors: offloaded 28/28 layers to GPU
```

(28 capas totales, según `qwen2.block_count` confirmado en A2.6.6.15; `n_gpu_layers` depende del valor `-ngl` usado, que en A2.6.6.15 fue 999, por lo que se esperaría 28/28).

También se producen mensajes intermedios previos (líneas 2000-2001):
```
llama_model_base::load_tensors: offloading output layer to GPU
llama_model_base::load_tensors: offloading 27 repeating layers to GPU
```

Y mensajes de tamaño de buffer por backend (líneas 2013-2016):
```
llama_model_base::load_tensors:      SYCL model buffer size =   4168.00 MiB
```

### 1.2 Origen stdout/stderr

Todos los mensajes `LLAMA_LOG_INFO` van a **stderr** (configuración estándar de llama.cpp). No hay mensajes de offload en stdout.

### 1.3 Tabla de evidencia disponible

| Campo | Evidencia disponible |
|---|---|
| Mensaje exacto | `llama_model_base::load_tensors: offloaded 28/28 layers to GPU` (confirmado por inspección de source, línea 2006 de llama-model.cpp) |
| Origen stdout/stderr | stderr (vía `LLAMA_LOG_INFO`) |
| Capas descargadas | 28 (inferido de `-ngl 999` y `qwen2.block_count = 28`; no capturado directamente por truncamiento de terminal en A2.6.6.15) |
| Capas totales | 28 (según `qwen2.block_count` en metadatos del modelo) |
| Dispositivo | El mensaje no menciona explícitamente "SYCL0"; el dispositivo se identifica por el contexto de ejecución (`-dev SYCL0`) y por el desglose de memoria `common_memory_breakdown_print` que muestra `SYCL0 ... model 4168 MiB` |
| Compatibilidad con parser actual | **Sí, compatible**. El parser `_FINAL_COUNT` busca `load_tensors:[ \t]*offloaded...` que coincide con `llama_model_base::load_tensors: offloaded...` (substring match) |
| Evidencia insuficiente o pendiente | No se capturó el mensaje real en stdout/stderr de la ejecución A2.6.6.15 por truncamiento de terminal. La compatibilidad del parser se infiere del source, no se verificó contra output real del build 11776 |

### 1.4 Compatibilidad del parser actual

El parser `_FINAL_COUNT` en `offload_evidence.py`:
```python
_FINAL_COUNT = re.compile(
    r"load_tensors:[ \t]*offloaded[ \t]+([0-9]+)[ \t]*/[ \t]*([0-9]+)"
    r"[ \t]+layers[ \t]+to[ \t]+GPU"
)
```

Coincide con el formato real `llama_model_base::load_tensors: offloaded 28/28 layers to GPU` porque:
- `load_tensors:` coincide con el sufijo de `llama_model_base::load_tensors:`
- El resto del patrón coincide exactamente con `offloaded 28/28 layers to GPU`

**Conclusión:** El parser actual **sí puede reconocer** el mensaje de offload del build 11776, siempre que la versión esté en `SUPPORTED_RUNTIME_VERSIONS` para el backend SYCL.

---

## 2. Incertidumbre 2 — Relación física de ejecutables 10909

### 2.1 Tabla comparativa

| Campo | `/home/brunapc/.local/bin/llama` | `/home/brunapc/.llama-app/llama` |
|---|---|---|
| Ruta absoluta | `/home/brunapc/.local/bin/llama` | `/home/brunapc/.llama-app/llama` |
| ¿Symlink? | No (regular file) | No (regular file) |
| Destino del symlink | N/A | N/A |
| Device | 259,3 | 259,3 |
| Inode | 52960898 | 52958964 |
| Enlaces | 1 | 1 |
| Tamaño | 52208488 bytes | 52208488 bytes |
| Fecha modificación | 2026-09-11 20:18:18.942 | 2026-09-11 20:18:18.897 |
| SHA256 | `6e6131eac16214ca7a0fe6a810cc2543de775e1ce58dcfa0be4d4009abef8112` | `6e6131eac16214ca7a0fe6a810cc2543de775e1ce58dcfa0be4d4009abef8112` |
| Salida `--version` | `version: 0.4.0-dev (build 10909, commit a2878d30d)` / `built with Clang 22.1.8 for Linux x86_64` | `version: 0.4.0-dev (build 10909, commit a2878d30d)` / `built with Clang 22.1.8 for Linux x86_64` |

### 2.2 Dictamen sobre relación física

**Los dos ejecutables son copias independientes con hash idéntico (opción 3).**

Justificación:
- **No son hardlinks:** tienen inodes distintos (52960898 vs 52958964) y `Enlaces: 1` en ambos.
- **No son enlaces simbólicos:** ambos son archivos regulares (`regular file`).
- **Son copias independientes con hash idéntico:** mismo SHA256, mismo tamaño, misma versión, misma fecha de modificación (diferencias de milisegundos en el campo "Modificar" son atribuibles a operaciones de copia del filesystem).

---

## 3. Especificación final de admisión por backend

### 3.1 Matriz de admisión

| Identidad exacta | CPU | Vulkan | SYCL | Observaciones |
|---|---:|---:|---:|---|
| `0.4.0-dev (build 10909, commit a2878d30d)` | Sí | Sí, sujeto a validación existente | No | Build 10909 ya en `SUPPORTED_RUNTIME_VERSIONS`; no soporta `--list-devices`; Vulkan sujeto a detección existente |
| `8681 (Debian)` | No | No | No | No en `SUPPORTED_RUNTIME_VERSIONS`; sin evidencia de offload validada |
| `0.7.0-dev (build 11776, commit ead9f3205)` | No | No | Sí | Evidencia real de inferencia en A2.6.6.15; dispositivo SYCL0 confirmado |
| Cualquier otra/desconocida | No | No | No | Rechazada por defecto |

### 3.2 Reglas de admisión por backend

**CPU (build 10909):**
- Identidad debe coincidir exactamente con `0.4.0-dev (build 10909, commit a2878d30d)`.
- No requiere dispositivo GPU (CPU es el backend por defecto).
- No requiere `--list-devices` (build 10909 no lo soporta).

**Vulkan (build 10909):**
- Identidad debe coincidir exactamente con `0.4.0-dev (build 10909, commit a2878d30d)`.
- Requiere que `detect_llama_capability()` reporte `Vulkan` en `supported_backends` (basado en salida de `--list-devices` o `vulkaninfo` en PATH).
- No se autoriza Vulkan por suposición; solo si la capacidad está comprobada.

**SYCL (build 11776):**
- Identidad debe coincidir exactamente con `0.7.0-dev (build 11776, commit ead9f3205)`.
- Backend debe ser `SYCL` exclusivamente (never CPU/Vulkan).
- Requiere dispositivo `SYCL0` detectado en `--list-devices`.
- Requiere entorno oneAPI aislado al subprocess (`CASTLEARQ_SYCL_RUNTIME`, `CASTLEARQ_SYCL_SETVARS`, `LD_LIBRARY_PATH` vía `setvars.sh`).
- Una ejecución exitosa por sí sola **no** es prueba de offload GPU; se requiere evidencia de offload válida.

**Identidad desconocida:**
- Rechazada para todos los backends. No hay fallback implícito.

---

## 4. Lista exacta de archivos y funciones que requerirían cambios

### 4.1 `castlearq/offload_evidence.py` — Cambio OBLIGATORIO

| Elemento | Estado actual | Cambio necesario | Motivo | Riesgo de regresión |
|---|---|---|---|---|
| `SUPPORTED_RUNTIME_VERSION` / `SUPPORTED_RUNTIME_VERSIONS` | `frozenset({ "0.4.0-dev (build 10909, commit a2878d30d)" })` | Dividir en dos conjuntos: `SUPPORTED_RUNTIME_VERSIONS_CPU_VULKAN` (mantener 10909) y `SUPPORTED_RUNTIME_VERSIONS_SYCL` (añadir 11776) | `assess_gpu_offload()` rechaza versiones no listadas con `UNSUPPORTED_VERSION` | Bajo: solo se añade una versión; los tests existentes con 10909 siguen pasando |
| `assess_gpu_offload()` | Valida versión contra un único conjunto global | Recibir `backend` objetivo y validar contra el conjunto correspondiente | La misma versión no es válida para todos los backends | Medio: se añade un parámetro; llamadas existentes deben pasarse `backend="CPU"` (default) para no romper |
| `_FINAL_COUNT` regex | Coincide con `load_tensors: offloaded X/Y layers to GPU` | Sin cambios (ya compatible con formato de build 11776) | N/A | Ninguno |

### 4.2 `castlearq/sycl_runner.py` — Cambio OPCIONAL (recomendado)

| Elemento | Estado actual | Cambio necesario | Motivo | Riesgo de regresión |
|---|---|---|---|---|
| `build_sycl_runner()` | Acepta `executable_path` directo sin validar SYCL | Validar que el ejecutable tenga SYCL disponible (reutilizar `discover_sycl_llama_runtime` o verificar `--list-devices` contiene `SYCL0`) | Evitar construir un runner SYCL con un ejecutable no-SYCL | Bajo: solo añade validación; no cambia comportamiento cuando la configuración es correcta |
| `SyclLlamaRunner.__init__` | `runtime_version` se almacena pero solo se pasa a `assess_gpu_offload` | Asegurar que se pasa el `backend="SYCL"` al llamar `assess_gpu_offload()` | La versión debe validarse contra el conjunto SYCL | Bajo |

### 4.3 `castlearq/execute_model.py` — Sin cambios estructurales

| Elemento | Estado actual | Cambio necesario | Motivo | Riesgo de regresión |
|---|---|---|---|---|
| Líneas 394-410 (inyección de runner SYCL) | Exige `SyclLlamaRunner` para backend SYCL | Sin cambios | Ya correcto | Ninguno |

### 4.4 `castlearq/runtimes.py` — Cambio OPCIONAL (recomendado)

| Elemento | Estado actual | Cambio necesario | Motivo | Riesgo de regresión |
|---|---|---|---|---|
| `detect_sycl_llama_capability()` | Retorna `supported_backends=("SYCL",)` | Sin cambios (ya correcto) | N/A | Ninguno |
| `RuntimeCapability` | `supported_backends` es un tuple | Sin cambios | N/A | Ninguno |

---

## 5. Plan de pruebas

### 5.1 Pruebas unitarias (sin hardware requerido)

| Test | Objetivo | Backend |
|---|---|---|
| `assess_gpu_offload` con versión 10909 y output válido | Verificar que build 10909 sigue siendo aceptado para CPU/Vulkan | CPU/Vulkan |
| `assess_gpu_offload` con versión 11776 y output `load_tensors: offloaded 28/28 layers to GPU` | Verificar que build 11776 es aceptado para SYCL | SYCL |
| `assess_gpu_offload` con versión 8681 | Verificar que build 8681 es rechazado como `UNSUPPORTED_VERSION` | Todos |
| `assess_gpu_offload` con versión desconocida | Verificar que se rechaza como `UNSUPPORTED_VERSION` | Todos |
| `assess_gpu_offload` con salida vacía y versión válida | Verificar que se clasifica como `NO_FINAL_COUNT` | Todos |
| `build_sycl_runner` con `executable_path` inválido | Verificar fallo rápido (ValueError) | SYCL |
| `test_env_not_modified` (existente) | Verificar que `os.environ` no se contamina | SYCL |

### 5.2 Pruebas de integración (requieren hardware SYCL)

| Test | Objetivo | Backend | Requiere Arc Pro B70 |
|---|---|---|---|
| `detect_sycl_llama_capability()` con ejecutable real y `setvars.sh` | Verificar `available=True`, `version="0.7.0-dev (build 11776, commit ead9f3205)"`, `supported_backends=("SYCL",)` | SYCL | Sí |
| Inferencia corta con build 11776 y `-ngl 999` | Verificar código 0, offload > 0 en SYCL0 | SYCL | Sí |
| Regresión de tests existentes de CPU/Vulkan | Verificar que no se rompen | CPU/Vulkan | No (solo para Vulkan si hay GPU Vulkan) |

---

## 6. Riesgos y cuestiones todavía abiertas

| Riesgo | Descripción | Mitigación |
|---|---|---|
| Formato de offload del build 11776 no verificado contra output real | A2.6.6.15 fue truncado; no se capturó el mensaje `load_tensors: offloaded X/Y layers to GPU` del build 11776 en ejecución real. La compatibilidad del parser se infiere del source, no se verificó contra output real. | Ejecutar una inferencia corta capturando salida completa a archivo y verificar que el mensaje aparece y matchea el parser. |
| `~/.local/bin/llama` y `~/.llama-app/llama` (copias independientes) | Ambos reportan build 10909 pero son inodes distintos. Deben tratarse como dos rutas distintas que apuntan al mismo build. | No afecta a la política de admisión (mismo build = misma identidad). |
| Build 8681 en PATH del sistema | `detect_runtimes()` lo detecta como instalado/disponible sin validar versión. | La política de admisión debe filtrar por versión, no solo por presencia en PATH. |
| `SUPPORTED_RUNTIME_VERSIONS` estático | Nuevas versiones requieren cambio de código. | Documentar proceso de adición de versiones con evidencia explícita. |
| Intermedio "offloading" vs final "offloaded" | El build 11776 emite mensajes intermedios (`offloading output layer`, `offloading X repeating layers`) que el parser actual clasifica como `NO_FINAL_COUNT`. Esto es correcto: solo el mensaje final confirma el offload. | Ninguna; comportamiento correcto. |

### Cuestiones pendientes para implementación

1. **Verificación del formato de output real del build 11776:** Antes de implementar, se debe ejecutar una inferencia corta capturando salida completa (no truncada) y confirmar que aparece `llama_model_base::load_tensors: offloaded 28/28 layers to GPU` (o similar) en stderr.

2. **Validación de la versión 10909 para Vulkan:** Build 10909 no soporta `--list-devices`, por lo que no se puede confirmar dispositivos GPU mediante ese comando. La admisión para Vulkan debe basarse en la detección existente de `vulkaninfo` en PATH, no en la salida del propio ejecutable.

---

## 7. Dictamen

**Listo para implementar con una prueba pendiente.**

La especificación de implementación está completamente definida. Los cambios requeridos son mínimos y localizados:
1. `castlearq/offload_evidence.py`: dividir `SUPPORTED_RUNTIME_VERSIONS` en dos conjuntos (CPU/Vulkan y SYCL) y pasar el backend a `assess_gpu_offload()`.
2. Configuración de despliegue: definir `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` para ejecuciones SYCL.

La única prueba pendiente es verificar el formato exacto del mensaje `load_tensors` en output real del build 11776 (incertidumbre 1). Esta prueba no requiere cambios de código, solo capturar salida completa de una inferencia corta.

**No se implementó nada en esta fase.** El informe es exclusivamente de especificación y diseño.

---

**Fin del informe A2.6.6.18.**