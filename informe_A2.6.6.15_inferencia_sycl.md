# Informe A2.6.6.15 — Primera inferencia GGUF mediante SYCL en Intel Arc Pro B70

**Ejecutable:** `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli`
**Modelo:** `/home/brunapc/.local/share/localai-hub/models/qwen2.5-coder-7b-instruct/5b37778a47291aa0347128efb51ef39376ed68fd0210cecdb663f0aa0d9a73b3/qwen2.5-coder-7b-instruct-q4_k_m.gguf`
**Dispositivo objetivo:** `SYCL0 — Intel(R) Arc(TM) Pro B70 Graphics`
**Variable de entorno (solo proceso de diagnóstico, no persistente):**
`LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib`
**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA sobre el modelo y el repositorio. Una sola inferencia ejecutada. Sin reconstrucción, sin descarga, sin modificación persistente.

---

## 1. Inspección previa — identidad del modelo

| Campo | Valor |
|---|---|
| ¿Existe el modelo? | **Sí** |
| Ruta absoluta | `/home/brunapc/.local/share/localai-hub/models/qwen2.5-coder-7b-instruct/5b37778a47291aa0347128efb51ef39376ed68fd0210cecdb663f0aa0d9a73b3/qwen2.5-coder-7b-instruct-q4_k_m.gguf` |
| Tamaño | 4,4 GB |
| SHA256 | `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` |
| Magic / formato | `GGUF` (versión GGUF V3, latest) |
| ¿Coincide con el esperado? | **Sí** — `qwen2.5-coder-7b-instruct-q4_k_m.gguf` |

Metadatos del modelo leídos durante la carga:
- Arquitectura: `qwen2`
- Nombre: `Qwen2.5 Coder 7B Instruct GGUF`
- Fine-tune: `Instruct-GGUF`
- Basename: `Qwen2.5-Coder`
- Tamaño: `7B`
- Block count: `28` capas
- Contexto máximo: `131072`
- Embedding length: `3584`
- Feed-forward length: `18944`
- Attention heads: `28` (KV heads: `4`)
- RoPE freq base: `1000000`

Nota: el modelo reside en un subdirectorio con hash (`5b37778a...`) dentro de `models/`, no directamente en la raíz de `models/`. Su identidad coincide con el modelo solicitado.

---

## 2. Identidad del runtime

| Campo | Valor |
|---|---|
| Ejecutable | `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` |
| Versión | `0.7.0-dev (build 11776, commit ead9f3205)` |
| Compilador | `IntelLLVM 2026.2.0 for Linux x86_64` |
| Backend SYCL | Validado en A2.6.6.14 (dispositivo SYCL0 detectado) |
| Parámetros de ejecución | `-c 512` (contexto), `-n 32` (máx. tokens generación), `-ngl 999` (offload máximo de capas), `-dev SYCL0` (dispositivo), `-v` (verbose) |
| Prompt | `Write a short Python function that returns the factorial of a non-negative integer.` |

---

## 3. Dispositivo utilizado

Durante la carga el runtime reportó:
```
device_info:
  - SYCL0   : Intel(R) Arc(TM) Pro B70 Graphics (32656 MiB, 31722 MiB free)
  - CPU     : Intel(R) Core(TM) i5-14600K (46828 MiB, 46828 MiB free)
```
El dispositivo seleccionado fue **SYCL0**, correspondiente a la **Intel Arc Pro B70** con 32656 MiB de VRAM (31722 MiB libres al inicio).

---

## 4. Resultado de la inferencia

| Campo | Valor |
|---|---|
| Código de salida | **0** (éxito) |
| Errores de ejecución | Ninguno |
| Advertencias de bibliotecas | Ninguna |
| Tokens de prompt evaluados | 44 |
| Tokens generados | 32 |
| Tiempo de evaluación del prompt | 1189,327 ms |
| Prompt performance | 36,99 tokens/seg (27,03 ms/token) |
| Tiempo de generación | 343,426 ms |
| Generación performance | **90,27 tokens/seg** (11,08 ms/token) |
| Tiempo total (elapsed) | ~4,44 s |
| Tipo de parada | `limit` (se alcanzó el límite de 32 tokens) |

Respuesta generada: **no pudo capturarse completa** (la salida del terminal fue middle-truncada en la zona del texto generado por el modelo). Se confirmó que la generación produjo 32 tokens y finalizó con `stop_type: limit`.

---

## 5. Evidencia de offload (GPU)

### Identificación del dispositivo y backend
- `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics` detectado y usado como dispositivo de offload.
- Backend: SYCL (oneAPI DPC++ sobre Level Zero, `libze_loader.so.1`).

### Memoria GPU utilizada (desglose final)
```
| memory breakdown [MiB]                        | total    free    self   model   context   compute    unaccounted |
|   - SYCL0 (Intel(R) Arc(TM) Pro B70 Graphics) | 32656 = 27115 + (4342 =  4168 +      28 +     146) +        1198 |
```
Interpretación del desglose SYCL0:
- **model**: 4168 MiB (pesos del modelo offloadados a GPU)
- **context**: 28 MiB
- **compute**: 146 MiB
- **self** (modelo + contexto + compute): 4342 MiB
- **total VRAM**: 32656 MiB, de los cuales 27115 MiB usados por el proceso y 1198 MiB no contabilizados

El hecho de que 4168 MiB de pesos del modelo residan en `SYCL0` (model memory) es **evidencia directa de offload de capas a GPU**.

### Capas offload
- Solicitado: `-ngl 999` (máximo número de capas a VRAM).
- Total de capas del modelo: **28** (según `qwen2.block_count`).
- **Conteo exacto de capas offloadadas:** no pudo capturarse (estaba en la parte middle-truncada de la salida del terminal, en los mensajes de inicialización del backend SYCL `ggml_backend_sycl_...`).

### Mensajes de inicialización del backend SYCL
Se observó detección del dispositivo SYCL0 y asignación de memoria en GPU (4168 MiB de modelo en VRAM). Los mensajes detallados de `ggml_backend_sycl` (registro de backend, offload por capa) quedaron en la sección truncada de la salida.

---

## 6. Rendimiento observado

| Métrica | Valor |
|---|---|
| Prompt eval speed | 36,99 t/s |
| Generation speed | 90,27 t/s |
| Pantalla final | `[ Prompt: 37,0 t/s | Generation: 90,3 t/s ]` |
| Tiempo total | 4,44 s |

---

## 7. Clasificación del resultado

**Inferencia completada con GPU confirmada.**

Justificación:
- Código de salida 0, sin errores ni advertencias.
- Dispositivo SYCL0 (Intel Arc Pro B70) detectado y utilizado.
- 4168 MiB de pesos del modelo asignados a memoria de `SYCL0` (`model` memory en el desglose), lo que demuestra offload real de capas a GPU, no solo CPU.
- Velocidad de generación de 90,27 t/s, consistente con aceleración por GPU para un modelo 7B Q4_K_M.

No se trata de "inferencia sin evidencia de GPU": la asignación de 4168 MiB en `SYCL0 model memory` es evidencia concreta de offload de capas al dispositivo Intel Arc Pro B70.

---

## 8. Dictamen sobre la primera inferencia SYCL en Arc Pro B70

**La primera inferencia GGUF mediante SYCL en la Intel Arc Pro B70 se completó con éxito.**

Evidencia resumida:
1. El runtime SYCL se inicializó sin errores y detectó la Intel Arc Pro B70 como `SYCL0`.
2. El modelo `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (4,4 GB, GGUF V3, 28 capas) se cargó y evaluó correctamente.
3. Se solicitó offload máximo (`-ngl 999`) y se observó 4168 MiB de pesos del modelo en memoria `SYCL0`, confirmando que las capas se descargaron a la GPU.
4. La generación produjo 32 tokens a 90,27 t/s sin errores de ejecución.
5. No se observó error de biblioteca, símbolo, ABI, driver Level Zero ni inicialización del backend SYCL.

**Limitación observada:** la salida del terminal fue middle-truncada, por lo que no se pudo capturar la respuesta generada exacta ni el conteo numérico preciso de capas offloadadas (aunque la memoria GPU asignada confirma que el offload ocurrió). Esta limitación es de visualización de salida, no de ejecución.

El entorno llama.cpp-sycl 0.7.0-dev con Intel oneAPI 2026.2 es capaz de ejecutar inferencia GGUF acelerada por SYCL sobre la Intel Arc Pro B70.

---

**Fin del informe. Una sola inferencia ejecutada. No se realizó inferencia adicional. No se modificó nada de forma persistente.**