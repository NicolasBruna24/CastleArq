# Informe A2.6.6.16 — Evaluación de integración del runtime SYCL validado en CastleArq Core

**Runtime SYCL validado (referencia):**
- Ejecutable: `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli`
- Versión: `0.7.0-dev (build 11776, commit ead9f3205)`
- Compilador: IntelLLVM 2026.2.0 for Linux x86_64
- Backend: SYCL / Level Zero
- Dispositivo: Intel Arc Pro B70 (SYCL0, 32656 MiB VRAM)
- Inferencia GGUF validada: A2.6.6.15 (código de salida 0, 90,27 t/s, 4168 MiB offload a GPU)

**Runtime del sistema (referencia):**
- Ejecutable: `/usr/bin/llama-cli`
- Versión: `8681 (Debian)`, compilador GNU 15.2.0
- Backend: solo CPU (carga `libggml-cpu-alderlake.so`)
- Sin soporte SYCL

**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA. No se modificó ningún archivo, no se ejecutó inferencia, no se realizaron operaciones Git.

---

## 1. Arquitectura actual — mecanismo de admisión

### 1.1 `SUPPORTED_RUNTIME_VERSIONS` y `normalize_runtime_version()`

Están definidos en `castlearq/offload_evidence.py` (no en `identity_admission.py`, que maneja la admisión de identidades de modelo, no de versiones de runtime):

```python
SUPPORTED_RUNTIME_VERSION = "0.4.0-dev (build 10909, commit a2878d30d)"
SUPPORTED_RUNTIME_VERSIONS = frozenset({SUPPORTED_RUNTIME_VERSION})
```

`normalize_runtime_version(version)` simplemente elimina un prefijo opcional `version:` y devuelve el texto limpio o `None`.

**Consecuencia crítica:** `assess_gpu_offload()` rechaza cualquier versión que no esté en `SUPPORTED_RUNTIME_VERSIONS` devolviendo `OffloadStatus.UNKNOWN` con categoría `UNSUPPORTED_VERSION`. El runtime SYCL validado (`0.7.0-dev (build 11776, commit ead9f3205)`) **no está** en este conjunto, por lo que cualquier ejecución SYCL mediante `SyclLlamaRunner` produciría evidencia de offload siempre clasificada como `unsupported_version`, independientemente de que el offload haya ocurrido realmente.

### 1.2 `detect_llama_capability()`

Definido en `castlearq/runtimes.py`. Sonda el ejecutable `llama` encontrado vía `shutil.which("llama")`:
- Ejecuta `--version` y `--help` (subcomando `cli`).
- Detecta backends: `CPU` siempre; `Vulkan` solo si aparece en `--list-devices`.
- No tiene conocimiento de SYCL. Devuelve `supported_backends=("CPU",)` o `("CPU", "Vulkan")`.
- Es el punto de entrada usado por `run_service.prepare()` y `execute_model.execute_model()` para el camino CPU/Vulkan.

### 1.3 `RuntimeCapability`

Dataclass en `castlearq/runtimes.py` con campos: `name`, `executable_path`, `version`, `supported_formats`, `supported_backends`, `prompt_input_modes`, `supports_one_shot`, `available`, `reason`, `compatibility_names`, `backend_arguments`. Propiedad `invocable = available and supports_one_shot`. Método `supports_runtime_name()` y `backend_argument(backend)`.

### 1.4 `detect_sycl_llama_capability()` / `discover_sycl_llama_runtime()`

En `castlearq/runtimes.py`. Descubre el runtime SYCL **solo si se pasa `executable_path`** (o vía variables de entorno en `build_sycl_runner`). El flujo de descubrimiento:
1. Verifica que el ejecutable exista y sea ejecutable.
2. Carga `setvars.sh` vía `SyclEnvironmentProvider` para obtener el entorno oneAPI (`PATH`, `LD_LIBRARY_PATH`, `ONEAPI_ROOT`).
3. Ejecuta `--version` (requiere returncode 0).
4. Ejecuta `--help` y verifica opciones requeridas: `--device`, `--gpu-layers`, `--ctx-size`, `--n-predict`, `--prompt`, `--single-turn`.
5. Ejecuta `--list-devices` y requiere `SYCL0` en la salida.
6. Si todo pasa, construye un `RuntimeCapability` con `supported_backends=("SYCL",)`, `supported_formats=("GGUF",)`, `backend_arguments=(("SYCL", "SYCL0"),)`.

Es **opcional y solo a petición**: nunca se inyecta en el descubrimiento CPU/Vulkan por defecto.

---

## 2. Integración SYCL existente

| Componente | Archivo | Responsabilidad | ¿Depende de versión del runtime? |
|---|---|---|---|
| Entorno oneAPI | `sycl_environment.py` | `SyclEnvironmentProvider.load()` ejecuta `setvars.sh` y devuelve el entorno con `LD_LIBRARY_PATH` | No (solo requiere `setvars.sh` presente) |
| Runner SYCL | `sycl_runner.py` | `SyclLlamaRunner` construye argv con `--device SYCL0 -ngl N -c N -n N -p prompt --single-turn -v`; ejecuta con `subprocess.run(env=environment)` | Parcial: `runtime_version` se almacena pero solo se pasa a `assess_gpu_offload` |
| Evidencia offload | `offload_evidence.py` | `assess_gpu_offload()` parsea `load_tensors: offloaded X/Y layers to GPU` | **Sí**: rechaza versiones no en `SUPPORTED_RUNTIME_VERSIONS` |
| Selector | `selection.py` | `RuntimeBackendSelector.select()` valida capacidad invocable, nombre de runtime, formato y backend | Parcial: usa `supported_backends` y `compatibility_names` |
| Orquestación | `run_service.py` / `execute_model.py` | Para `target.backend == "SYCL"` inyecta `SyclLlamaRunner` (vía `build_sycl_runner(capability)`) | Parcial: pasa `capability` con `version` |
| Runner base | `runner.py` | `LlamaCppRunner` para CPU/Vulkan; usa `--simple-io --model ...` | Sí: usa `capability.executable_path` y `backend_argument` |
| Métricas | `runtime_metrics.py` | `parse_llama_human_output()` extrae `[ Prompt: X t/s | Generation: Y t/s ]` | No |

### 2.1 Flujo de ejecución SYCL en `execute_model.py`

Líneas 394-410: cuando `target.backend == "SYCL"`, se requiere que `deps.runner` sea una `SyclLlamaRunner` (si se inyecta) o se construye con `build_sycl_runner(capability)`. Luego `runner.run(executable_artifact, target, request)`.

### 2.2 Wiring de capacidades

- `detect_llama_capability()` → CPU/Vulkan (vía `which("llama")`).
- `detect_sycl_llama_capability()` → SYCL (solo si se configura `executable_path`).
- `RuntimeBackendSelector.select()` une compatibilidad + capacidad para producir el `ExecutionTarget`.
- No hay un registro unificado de runtimes múltiples: cada camino (CPU/Vulkan vs SYCL) se construye por separado.

---

## 3. Comparación entre runtimes

| Aspecto | A. Runtime sistema `/usr/bin/llama-cli` | B. Runtime SYCL `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` |
|---|---|---|
| Versión | `8681 (Debian)` | `0.7.0-dev (build 11776, commit ead9f3205)` |
| Compilador | GNU 15.2.0 | IntelLLVM 2026.2.0 |
| Backends detectados | CPU únicamente (`libggml-cpu-alderlake.so`) | SYCL (SYCL0: Intel Arc Pro B70) |
| Soporta `--device` | Sí | Sí |
| Soporta `-ngl/--gpu-layers` | Sí | Sí |
| Soporta `--list-devices` | Sí | Sí (reporta SYCL0) |
| Soporta `--single-turn` | Sí | Sí |
| Formato de offload evidence | `load_tensors: offloaded X/Y layers to GPU` (build 10909) | Output A2.6.6.15 mostró `common_memory_breakdown_print` con SYCL0 model 4168 MiB; el formato exacto `load_tensors` no se pudo verificar por truncamiento |
| `SUPPORTED_RUNTIME_VERSIONS` | **No coincide** (es 8681, no 10909) | **No coincide** (es 11776, no 10909) |
| Requiere `LD_LIBRARY_PATH` | No (dependencias del sistema) | Sí (oneAPI compiler/dnnl/tbb vía setvars.sh) |

**Hallazgo clave:** ni el runtime del sistema ni el runtime SYCL están en `SUPPORTED_RUNTIME_VERSIONS` (que solo contiene `0.4.0-dev (build 10909, commit a2878d30d)`). Esto significa que el parser de offload evidence rechazaría a ambos runtimes con `UNSUPPORTED_VERSION` en el estado actual del código.

Otra diferencia importante: el runtime SYCL necesita `LD_LIBRARY_PATH` apuntando a oneAPI (compiler/dnnl/tbb) para resolver dependencias en tiempo de ejecución, mientras que el runtime del sistema usa dependencias del sistema estándar.

---

## 4. Configuración del entorno sin modificación global

El diseño actual de `SyclLlamaRunner` ya soporta aislamiento del entorno:

- **Ruta explícita al ejecutable:** vía `capability.executable_path` o variable `CASTLEARQ_SYCL_RUNTIME`.
- **`LD_LIBRARY_PATH` limitado al proceso:** `SyclEnvironmentProvider.load()` ejecuta `setvars.sh` y captura su entorno completo (`PATH`, `LD_LIBRARY_PATH`, `ONEAPI_ROOT`, etc.), que se pasa exclusivamente al `subprocess.run(env=environment)` del runner. `os.environ` del proceso CastleArq no se modifica (verificado en `test_env_not_modified`).
- **Variables de entorno necesarias:** `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` (o pasarlas vía `capability`/`env_provider`).
- **Identificación del dispositivo:** hardcodeado como `--device SYCL0` en `sycl_runner.py` (línea 94). El descubrimiento previa valida que `SYCL0` aparezca en `--list-devices`.
- **Validación previa de dependencias:** `discover_sycl_llama_runtime()` valida `--version`, `--help`, `--list-devices` antes de considerar el runtime disponible.
- **Separación CPU/Vulkan vs SYCL:** el código ya las separa en caminos distintos (`LlamaCppRunner` vs `SyclLlamaRunner`), seleccionados por `target.backend` en `execute_model.py`.

**Conclusión sección 4:** la arquitectura actual **admite** esta separación sin cambios estructurales mayores. Lo que falta es principalmente la configuración de las variables de entorno (`CASTLEARQ_SYCL_RUNTIME`, `CASTLEARQ_SYCL_SETVARS`) y la actualización de `SUPPORTED_RUNTIME_VERSIONS`.

---

## 5. Propuesta arquitectónica

### 5.1 ¿Puede CastleArq admitir ambos runtimes simultáneamente?

**Sí.** La arquitectura ya lo soporta:
- `LlamaCppRunner` para CPU/Vulkan (runtime del sistema).
- `SyclLlamaRunner` para SYCL (runtime independiente validado).
- La selección se hace por `target.backend` en `execute_model.py`, que inyecta el runner apropiado.

No hay conflicto porque cada runner tiene su propio `executable_path` y su propio entorno de subprocess.

### 5.2 ¿Debe cada runtime tener su propia identidad y política de admisión?

**Sí (obligatorio para el offload evidence).** Actualmente `offload_evidence.SUPPORTED_RUNTIME_VERSIONS` es un conjunto global de una sola versión (`0.4.0-dev build 10909`). Debe ampliarse para incluir cada versión de runtime que se quiera validar para offload:

- Añadir `"0.7.0-dev (build 11776, commit ead9f3205)"` al conjunto (o mejor, versionar la política por runtime).

Cada `RuntimeCapability` ya lleva su propio campo `version`, que se pasa a `assess_gpu_offload()`. El problema es que el conjunto de versiones soportadas es estático y no incluye ni al runtime del sistema ni al SYCL.

### 5.3 ¿Cómo se seleccionaría el ejecutable SYCL sin reemplazar el runtime del sistema?

Mediante variables de entorno o capacidad inyectada, **sin tocar** `/usr/bin/llama-cli`:
- `CASTLEARQ_SYCL_RUNTIME=/home/brunapc/llama.cpp-sycl/build/bin/llama-cli`
- `CASTLEARQ_SYCL_SETVARS=/opt/intel/oneapi/setvars.sh` (o la ruta adecuada de `setvars.sh`)
- O inyectar `capability.executable_path` directamente al construir `SyclLlamaRunner`.

El descubrimiento `discover_sycl_llama_runtime()` valida el ejecutable de forma independiente. El runtime del sistema (`which("llama")`) sigue siendo usado por `detect_llama_capability()` para CPU/Vulkan.

### 5.4 ¿Cómo se evitaría que una ejecución SYCL utilice silenciosamente CPU o Vulkan?

Varias capas de defensa ya existen o se pueden reforzar:

1. **`SyclLlamaRunner.run()` hardcodea `--device SYCL0`** (línea 94) y `-ngl` configurable. No acepta dispositivo alternativo desde la request.
2. **`RuntimeCapability.supported_backends=("SYCL",)`** para el runtime SYCL, por lo que el selector nunca elegiría CPU o Vulkan para un target SYCL.
3. **`execute_model.py` líneas 394-402** exige que, para backend SYCL, el runner inyectado sea `SyclLlamaRunner` (no `LlamaCppRunner`).

**Riesgo residual:** si alguien construye manualmente un `SyclLlamaRunner` con el ejecutable del sistema (`/usr/bin/llama-cli`), ese ejecutable no tiene backend SYCL y fallaría. Pero eso es un error de configuración, no de silencioso fallback. Se podría añadir una validación en `build_sycl_runner()` que verifique que el ejecutable tenga SYCL en `--help`/`--list-devices` antes de aceptarlo (el descubrimiento ya lo hace, pero `build_sycl_runner` acepta `executable_path` directo sin re-validar).

### 5.5 ¿Cómo se validaría el offload real?

Dos cosas son necesarias:

1. **`SUPPORTED_RUNTIME_VERSIONS` debe incluir `"0.7.0-dev (build 11776, commit ead9f3205)"`.** Sin esto, `assess_gpu_offload()` devuelve siempre `UNKNOWN`/`unsupported_version`.
2. **Verificar que el parser `_FINAL_COUNT` matchee el output real del runtime SYCL.** En A2.6.6.15 la salida mostró `common_memory_breakdown_print` con `SYCL0 ... model 4168 ...`, pero el formato `load_tensors: offloaded X/Y layers to GPU` no se pudo verificar por truncamiento de terminal. Si el runtime 0.7.0-dev no emite ese formato exacto, el parser devolvería `NO_FINAL_COUNT` y el offload no se confirmaría por evidencia de texto, aunque la memoria GPU demuestre que ocurrió.

Alternativa de robustez: complementar `assess_gpu_offload` con el desglose de memoria `common_memory_breakdown_print` (model > 0 en SYCL0) como evidencia secundaria.

### 5.6 ¿Qué cambios serían necesarios en Core?

**Cambios obligatorios (para que SYCL funcione correctamente con offload validado):**

1. **`castlearq/offload_evidence.py`:** añadir `"0.7.0-dev (build 11776, commit ead9f3205)"` a `SUPPORTED_RUNTIME_VERSIONS`. Opcional pero recomendado: hacer el conjunto configurable por runtime (ej. mapeo `runtime_name -> supported_versions`).

2. **Configuración de entorno:** definir `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` en el despliegue/composición de CastleArq, apuntando al ejecutable validado y al `setvars.sh` de oneAPI.

**Cambios opcionales (mejores prácticas, no estrictamente necesarios para funcionar):**

3. **`castlearq/sycl_runner.py`:** en `build_sycl_runner()`, validar que el `executable_path` tenga SYCL disponible (reutilizar `discover_sycl_llama_runtime` o al menos comprobar `--list-devices` contiene `SYCL0`) antes de construir el runner, para fallar rápido en configuración errónea.

4. **`castlearq/offload_evidence.py`:** ampliar el parser para reconocer también el formato de desglose de memoria `common_memory_breakdown_print` como evidencia secundaria de offload, por si el formato `load_tensors` cambia entre versiones.

5. **Tests:** añadir tests de integración para `SyclLlamaRunner` con el ejecutable SYCL real (mocked) y tests de `assess_gpu_offload` con output de la versión 0.7.0-dev.

### 5.7 Estrategia de pruebas

- **Unitarios (existentes, no modificar):** `test_sycl_runner.py` (args, env, timeout, OS error, env not modified), `test_sycl_discovery.py` (disponible/no configurado/SYCL0 ausente/CPU-Vulkan preservado).
- **Unitarios nuevos recomendados:** `assess_gpu_offload` con versión `0.7.0-dev (build 11776)` y output conteniendo `load_tensors: offloaded 28/28 layers to GPU`; `build_sycl_runner` con `executable_path` inválido.
- **De integración (sin inferencia):** `detect_sycl_llama_capability()` con el ejecutable real y `setvars.sh`, verificando que devuelve `available=True`, `version="0.7.0-dev (build 11776, commit ead9f3205)"`, `supported_backends=("SYCL",)`.
- **De inferencia validada (A2.6.6.15, ya ejecutado):** código 0, 90,27 t/s, 4168 MiB offload a SYCL0.

---

## 6. Limitaciones encontradas

1. **`SUPPORTED_RUNTIME_VERSIONS` estático y desactualizado:** solo contiene `0.4.0-dev (build 10909)`. Ni el runtime del sistema (8681) ni el SYCL validado (11776) están soportados para offload evidence.
2. **Parser de offload acoplado a un formato específico:** `_FINAL_COUNT` busca `load_tensors: offloaded X/Y layers to GPU`. Si el runtime 0.7.0-dev no emite ese formato exacto, la evidencia de offload sería `UNKNOWN`/`NO_FINAL_COUNT` a pesar de que la memoria GPU demuestre offload real.
3. **`--device SYCL0` hardcodeado en `sycl_runner.py`:** funciona para este dispositivo, pero no permite selección dinámica de dispositivo entre múltiples GPUs SYCL.
4. **No hay registro unificado de runtimes múltiples:** CPU/Vulkan y SYCL se descubren por caminos separados; no hay una sola fuente de verdad que liste ambos runtimes con sus capacidades.

---

## 7. Dictamen

**Integración viable con cambios mínimos obligatorios.**

La arquitectura de CastleArq Core ya está diseñada para admitir runtimes múltiples de forma aislada (`LlamaCppRunner` vs `SyclLlamaRunner`, entorno de subprocess aislado vía `setvars.sh`, selección por backend). El runtime SYCL validado (`0.7.0-dev build 11776`) es descubrible, ejecutable y ha superado una inferencia real en A2.6.6.15 con offload confirmado a la Intel Arc Pro B70.

Los únicos cambios **obligatorios** son:
1. Añadir `"0.7.0-dev (build 11776, commit ead9f3205)"` a `SUPPORTED_RUNTIME_VERSIONS` en `offload_evidence.py`, para que la evidencia de offload no se clasifique como `unsupported_version`.
2. Configurar `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` en el despliegue.

Sin el cambio 1, cualquier ejecución SYCL reportaría offload `UNKNOWN` aunque el GPU se esté usando realmente, lo que violaría el principio de A2.6.6.15 §4 de no considerar inferencia exitosa como aceleración GPU sin evidencia.

No se requiere modificar `/usr/bin/llama-cli`, el runtime del sistema, los archivos OpenVINO, los tests existentes, ni el staging de CastleArq.

---

**Fin del informe. No se implementó ninguna propuesta. No se modificó ningún archivo.**