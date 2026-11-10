# Informe A2.6.6.19 — Verificación de evidencia real de offload SYCL

**Objetivo:** Capturar la salida real de una inferencia con el runtime SYCL build 11776 y verificar que el mensaje de offload GPU coincide con el formato reconocido por el parser actual de CastleArq Core.

**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** UNA SOLA inferencia ejecutada (autorizada por el usuario). No se modificó ningún archivo del repositorio. No se ejecutaron pruebas adicionales de rendimiento.

---

## 1. Comprobaciones previas

Todas las comprobaciones previas superadas:

| Comprobación | Resultado |
|---|---|
| Ejecutable existe | `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` — archivo real, ejecutable |
| Identidad del runtime | `version: 0.7.0-dev (build 11776, commit ead9f3205)` / `built with IntelLLVM 2026.2.0 for Linux x86_64` |
| Modelo existe | `/home/brunapc/.local/share/localai-hub/models/qwen2.5-coder-7b-instruct/5b37778a47291aa0347128efb51ef39376ed68fd0210cecdb663f0aa0d9a73b3/qwen2.5-coder-7b-instruct-q4_k_m.gguf` |
| SHA256 del modelo | `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` — coincide con el valor documentado |
| Modelo legible | Sí (4,4 GB, permisos de lectura) |
| Dispositivo SYCL0 disponible | Sí: `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics (32656 MiB, 31738 MiB free)` |

---

## 2. Parámetros de ejecución

| Parámetro | Valor |
|---|---|
| Ejecutable | `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` |
| Modelo | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (ruta completa en almacén existente) |
| Contexto (`-c`) | 512 |
| Tokens máximos (`-n`) | 32 |
| Offload (`-ngl`) | 999 |
| Dispositivo (`-dev`) | SYCL0 |
| Verbosidad | `-v` |
| Prompt | `Write a short Python function that returns the factorial of a non-negative integer.` |
| `LD_LIBRARY_PATH` | `/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib` (solo proceso de diagnóstico) |

---

## 3. Resultado de la inferencia

| Campo | Valor |
|---|---|
| Código de salida | **0** (éxito) |
| Tokens de prompt evaluados | 44 |
| Tokens generados | 32 |
| Prompt performance | 35,14 tokens/seg |
| Generación performance | 81,97 tokens/seg |
| Tipo de parada | `limit` (límite de 32 tokens alcanzado) |
| Errores de ejecución | Ninguno |
| Advertencias de bibliotecas | Ninguna |

La inferencia se completó correctamente. Se generó una función Python de factorial válida.

---

## 4. Mensaje real de offload (stderr)

### 4.1 Texto exacto del mensaje final de offload

El mensaje aparece dos veces en stderr (una por cada fase de carga del modelo):

```
load_tensors: offloaded 29/29 layers to GPU
```

- Línea 940: `0.00.513.065 I load_tensors: offloaded 29/29 layers to GPU`
- Línea 2966: `0.00.691.949 I load_tensors: offloaded 29/29 layers to GPU`

### 4.2 Origen stdout/stderr

**stderr.** Todos los mensajes `LLAMA_LOG_INFO` (incluyendo `load_tensors`) se emiten a stderr, que es la configuración estándar de llama.cpp. No hay mensajes de offload en stdout.

### 4.3 Capas descargadas y totales

| Campo | Valor |
|---|---|
| Capas descargadas (offloaded) | 29 |
| Capas totales | 29 |
| Ratio | 29/29 (100% de las capas en GPU) |

Nota: El modelo tiene 29 capas (`n_layer_all = 29`), no 28 como se esperaba inicialmente a partir de `qwen2.block_count = 28` observado en A2.6.6.15. Los valores reales son 29/29, confirmados por la ejecución.

### 4.4 Dispositivo indicado

El mensaje de offload en sí **no menciona explícitamente "SYCL0"** en su texto. Sin embargo, el dispositivo se identifica por:
- Todas las 29 capas asignadas a `device SYCL0` (líneas 149-177 de stderr: `layer X assigned to device SYCL0, is_swa = 0`)
- El `device_info` inicial: `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics`
- El desglose de memoria final: `SYCL0 (Intel(R) Arc(TM) Pro B70 Graphics) | 32656 = ... model 4168 MiB`

### 4.5 Mensajes intermedios previos

También aparecen en stderr (líneas 938-939 y 2964-2965):
```
load_tensors: offloading output layer to GPU
load_tensors: offloading 27 repeating layers to GPU
```

Estos son mensajes intermedios de progreso; solo el mensaje final `offloaded 29/29 layers to GPU` confirma el offload completo.

### 4.6 Desglose de memoria GPU (línea 4936 de stderr)

```
|   - SYCL0 (Intel(R) Arc(TM) Pro B70 Graphics) | 32656 = 27134 + (4342 =  4168 +      28 +     146) +        1179 |
```

Interpretación:
- **model**: 4168 MiB (pesos del modelo offloadados a GPU)
- **context**: 28 MiB
- **compute**: 146 MiB
- **self** (modelo + contexto + compute): 4342 MiB
- **total VRAM**: 32656 MiB

Este desglose confirma offload real de 4168 MiB de pesos del modelo a la GPU SYCL0.

### 4.7 Ausencia de mensajes contradictorios

No hay mensajes contradictorios. Todas las 29 capas se asignan a SYCL0. No hay mensajes de fallback a CPU o Vulkan. No hay mensajes de error de inicialización SYCL ni de driver Level Zero.

---

## 5. Resultado de reconocimiento del parser actual

### 5.1 Reconocimiento sintáctico

El parser actual en `castlearq/offload_evidence.py` (líneas 38-41):

```python
_FINAL_COUNT = re.compile(
    r"load_tensors:[ \t]*offloaded[ \t]+([0-9]+)[ \t]*/[ \t]*([0-9]+)"
    r"[ \t]+layers[ \t]+to[ \t]+GPU"
)
```

El mensaje real capturado:
```
load_tensors: offloaded 29/29 layers to GPU
```

**Resultado: SÍ, el parser reconoce sintácticamente el mensaje.** El patrón coincide exactamente:
- `load_tensors:` coincide
- `offloaded 29/29 layers to GPU` coincide con el patrón completo
- Grupo 1 (capas descargadas): `29`
- Grupo 2 (capas totales): `29`
- Flujo: stderr

### 5.2 Validación de identidad del runtime (SEPARADA del reconocimiento sintáctico)

`castlearq/offload_evidence.py` (líneas 139-142):

```python
if normalize_runtime_version(runtime_version) not in (
        SUPPORTED_RUNTIME_VERSIONS):
    return _unknown(OffloadEvidenceCategory.UNSUPPORTED_VERSION,
                    runtime_version)
```

Donde `SUPPORTED_RUNTIME_VERSIONS = frozenset({"0.4.0-dev (build 10909, commit a2878d30d)"})`.

La versión del runtime ejecutado es `0.7.0-dev (build 11776, commit ead9f3205)`, que **NO está** en `SUPPORTED_RUNTIME_VERSIONS`.

**Resultado: La identidad del runtime 11776 NO está admitida.** Si `assess_gpu_offload()` se invocara con `runtime_version="0.7.0-dev (build 11776, commit ead9f3205)"`, devolvería `UNKNOWN` con categoría `unsupported_version`, **independientemente de que el mensaje sintáctico sea válido y el offload haya ocurrido realmente.**

### 5.3 Clasificación final de la evidencia de offload

| Dimensión | Resultado |
|---|---|
| Reconocimiento sintáctico del mensaje | **Reconocido** (pattern match exitoso) |
| Validación de identidad (build 11776) | **Rechazado** (no en `SUPPORTED_RUNTIME_VERSIONS`) |
| Clasificación final de `assess_gpu_offload()` | `UNKNOWN` / `unsupported_version` |
| Evidencia de offload real (memoria GPU) | **Confirmada** (4168 MiB en SYCL0 model memory) |

---

## 6. Evidencia de ausencia o presencia de fallback

**Ausencia de fallback a CPU/Vulkan confirmada:**

- Todas las 29 capas se asignan explícitamente a `device SYCL0` (líneas 149-177 de stderr)
- No hay mensajes de asignación de capas a CPU o Vulkan
- El `device_info` inicial muestra SYCL0 como el dispositivo GPU y CPU como dispositivo separado
- El desglose de memoria muestra model 4168 MiB en SYCL0, no en CPU
- El código de salida es 0 (ejecución exitosa sin fallback)

---

## 7. Dictamen

**Evidencia SYCL verificada (con salvedad de identidad no admitida).**

| Criterio de aceptación | Estado |
|---|---|
| Runtime corresponde a build 11776 | ✅ Confirmado (`ead9f3205`, IntelLLVM 2026.2.0) |
| Modelo coincide con SHA256 documentado | ✅ Confirmado (`509287f7...`) |
| Inferencia termina con código de salida 0 | ✅ Confirmado |
| Salida real contiene mensaje de offload GPU | ✅ Confirmado (`offloaded 29/29 layers to GPU`) |
| Parser actual reconoce sintácticamente el mensaje | ✅ Confirmado (pattern match exitoso) |
| No hay evidencia de fallback silencioso a CPU/Vulkan | ✅ Confirmado (todas las capas en SYCL0) |

**Limitación importante:** Aunque el parser actual **reconoce sintácticamente** el mensaje de offload del build 11776, la identidad del runtime `0.7.0-dev (build 11776, commit ead9f3205)` **no está** en `SUPPORTED_RUNTIME_VERSIONS` (que solo contiene build 10909). Por tanto, `assess_gpu_offload()` clasificaría la evidencia como `UNKNOWN`/`unsupported_version` si se invocara con esta versión, a pesar de que el offload GPU ocurrió realmente (4168 MiB de pesos en SYCL0, 29/29 capas asignadas).

**Conclusión:** La evidencia de offload SYCL está verificada técnicamente (mensaje válido, 29/29 capas en GPU, 4168 MiB en memoria SYCL0, sin fallback), pero la política de admisión actual de CastleArq Core no reconocería esta evidencia debido a que la identidad del runtime no está en la allowlist de versiones. Esto confirma el hallazgo de A2.6.6.16/A2.6.6.17: es necesario añadir build 11776 a `SUPPORTED_RUNTIME_VERSIONS` para el backend SYCL antes de que la evidencia de offload pueda clasificarse como `CONFIRMED`.

---

**Fin del informe A2.6.6.19. Una sola inferencia ejecutada. No se modificó ningún archivo.**