# Informe A2.6.6.17 — Diseño de la política de admisión multi-runtime

**Objetivo:** Definir una política explícita y verificable para que CastleArq Core admita simultáneamente el runtime convencional llama.cpp (CPU/Vulkan) y el runtime SYCL validado para Intel Arc Pro B70.

**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA. Análisis y diseño exclusivamente. No se implementó ninguna política. No se modificó ningún archivo ni repositorio.

---

## 1. Inventario de ejecutables e identidades

### 1.1 Ejecutables encontrados

| # | Ruta absoluta | Tipo | ¿Symlink? | Detectado por Core |
|---|---|---|---|---|
| 1 | `/usr/bin/llama-cli` | Archivo real | No | Sí, vía `shutil.which("llama-cli")` en `detect_runtimes()` |
| 2 | `/home/brunapc/.local/bin/llama` | Archivo real | No | No (no está en PATH típico; depende del entorno) |
| 3 | `/home/brunapc/.llama-app/llama` | Archivo real | No | No |
| 4 | `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` | Archivo real | No | No (requiere `CASTLEARQ_SYCL_RUNTIME` o `capability.executable_path`) |
| 5 | `/home/brunapc/llama.cpp-sycl/build/bin/llama` | Archivo real | No | No |

Nota: `/usr/share/bash-completion/completions/llama-cli` es un archivo de completado de shell, no un ejecutable.

### 1.2 Identidades por ejecutable

| Ruta | Salida de `--version` | `--list-devices` | Backend / capacidades | Procedencia |
|---|---|---|---|---|
| `/usr/bin/llama-cli` | `version: 8681 (Debian)` / `built with GNU 15.2.0 for Linux x86_64` | Soporta `--list-devices`; salida: `Available devices:` (vacío) | CPU backend (`libggml-cpu-alderlake.so`). Sin SYCL, sin Vulkan. | Distribución Debian (paquete del sistema) |
| `/home/brunapc/.local/bin/llama` | `version: 0.4.0-dev (build 10909, commit a2878d30d)` / `built with Clang 22.1.8 for Linux x86_64` | **No soporta** `--list-devices` (`error: unknown command '--list-devices'`) | Capacidades desconocidas (no se puede sondear dispositivos). Coincide con `SUPPORTED_RUNTIME_VERSIONS`. | Build local (52.2 MB) |
| `/home/brunapc/.llama-app/llama` | `version: 0.4.0-dev (build 10909, commit a2878d30d)` / `built with Clang 22.1.8 for Linux x86_64` | **No soporta** `--list-devices` (`error: unknown command '--list-devices'`) | Capacidades desconocidas (no se puede sondear dispositivos). Coincide con `SUPPORTED_RUNTIME_VERSIONS`. | Build local (52.2 MB, inode distinto de `.local/bin/llama`) |
| `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` | `version: 0.7.0-dev (build 11776, commit ead9f3205)` / `built with IntelLLVM 2026.2.0 for Linux x86_64` | Soporta `--list-devices`; salida: `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics (32656 MiB, ...)` | Backend SYCL / Level Zero. Dispositivo SYCL0 confirmado. Inferencia GGUF validada en A2.6.6.15. | Build SYCL independiente (`llama.cpp-sycl`) |
| `/home/brunapc/llama.cpp-sycl/build/bin/llama` | No verificado | No verificado | No verificado | Build SYCL independiente (934.880 bytes) |

**Conclusión del inventario:**
- Build 10909 es la **única identidad actualmente en `SUPPORTED_RUNTIME_VERSIONS`**, pero ninguno de sus ejecutables soporta `--list-devices`.
- Build 8681 soporta `--list-devices` pero no reporta dispositivos GPU y no está en `SUPPORTED_RUNTIME_VERSIONS`.
- Build 11776 (SYCL) está completamente fuera de `SUPPORTED_RUNTIME_VERSIONS` y requiere configuración explícita.

---

## 2. Trazabilidad de los puntos de admisión en Core

### 2.1 Dónde se valida la versión

La validación de versión del runtime ocurre exclusivamente en **`castlearq/offload_evidence.py`**:

```python
SUPPORTED_RUNTIME_VERSION = "0.4.0-dev (build 10909, commit a2878d30d)"
SUPPORTED_RUNTIME_VERSIONS = frozenset({SUPPORTED_RUNTIME_VERSION})
```

`normalize_runtime_version(version)` elimina un prefijo opcional `version:` y devuelve el texto limpio o `None`.

En `assess_gpu_offload()` (líneas 139-142):
```python
if normalize_runtime_version(runtime_version) not in (
        SUPPORTED_RUNTIME_VERSIONS):
    return _unknown(OffloadEvidenceCategory.UNSUPPORTED_VERSION,
                    runtime_version)
```

**Consecuencia:** cualquier runtime cuya versión no esté exactamente en ese conjunto (incluidos build 8681 y build 11776) recibe evidencia de offload `UNKNOWN` con categoría `unsupported_version`, independientemente de que el offload GPU haya ocurrido realmente.

### 2.2 Componentes que dependen de la identidad del runtime

| Componente | Archivo | Depende de versión | Depende de backend | Notas |
|---|---|---|---|---|
| `assess_gpu_offload()` | `offload_evidence.py` | **Sí** (estricto, `SUPPORTED_RUNTIME_VERSIONS`) | No | Rechaza versiones no listadas |
| `normalize_runtime_version()` | `offload_evidence.py` | Sí (utilidad) | No | Solo formatea |
| `detect_llama_capability()` | `runtimes.py` | No (lee versión, no la valida) | Sí (CPU/Vulkan) | Sonda `which("llama")` |
| `detect_sycl_llama_capability()` | `runtimes.py` | No (lee versión, no la valida) | Sí (SYCL) | Sonda `executable_path` explícito |
| `discover_sycl_llama_runtime()` | `runtimes.py` | No (lee versión) | Sí (SYCL) | Valida `--version`, `--help`, `--list-devices` |
| `RuntimeCapability` | `runtimes.py` | No (almacena versión) | Sí (`supported_backends`) | Dataclass de capacidades |
| `RuntimeBackendSelector.select()` | `selection.py` | No | Sí (`supported_backends`) | Valida invocable, nombre, formato, backend |
| `SyclLlamaRunner` | `sycl_runner.py` | Parcial (pasa `runtime_version` a offload) | Sí (hardcodea `--device SYCL0`) | Ejecuta con env oneAPI |
| `LlamaCppRunner` | `runner.py` | No | Sí (`backend_argument`) | Ejecuta CPU/Vulkan |
| `execute_model.execute_model()` | `execute_model.py` | No | Sí (inyecta runner por backend) | Orquesta selección y ejecución |
| `run_service.prepare()` / `run_once()` | `run_service.py` | No | Sí | Prepara para ejecución o chat |

### 2.3 Componentes neutrales respecto del backend

- `compatibility.py` / `compatibility_evaluator.py`: evalúan compatibilidad modelo-capacidad sin conocer el backend específico del runtime.
- `identity_admission.py`: gestiona identidades de modelo (source → model_id), no versiones de runtime.
- `runtime_metrics.py`: parsea métricas de salida humana (`[ Prompt: X t/s | Generation: Y t/s ]`), backend-agnóstico.
- `execution.py`: tipos de dominio (`ExecutionTarget`, `ExecutionRequest`, `ExecutableArtifact`), sin lógica de backend.

### 2.4 Allowlist global y ejecuciones CPU

No existe una "allowlist global de versiones de runtime" aplicable a ejecuciones CPU. La restricción de versión (`SUPPORTED_RUNTIME_VERSIONS`) solo se aplica dentro de `assess_gpu_offload()`, que se invoca para **cualquier backend** (CPU, Vulkan, SYCL) a través de `SyclLlamaRunner` y `LlamaCppRunner` (ambos pasan `runtime_version` a `assess_gpu_offload()`).

Sin embargo, `detect_runtimes()` en `runtimes.py` solo verifica presencia de binarios en PATH (`which`), sin validar versión ni capacidades GPU. Por tanto:
- Ejecuciones CPU con `/usr/bin/llama-cli` (build 8681): **no se valida versión** en el camino de detección; solo se valida en offload evidence si se invoca `assess_gpu_offload()`.
- Ejecuciones CPU con build 10909: versión coincide con `SUPPORTED_RUNTIME_VERSIONS`, pero el ejecutable no soporta `--list-devices`.

### 2.5 Validaciones redundantes o contradictorias

- **Redundante:** `detect_llama_capability()` y `detect_sycl_llama_capability()` ambas leen `--version` pero ninguna valida contra `SUPPORTED_RUNTIME_VERSIONS`. La validación de versión solo ocurre en `assess_gpu_offload()`, desconectada del descubrimiento.
- **Contradictoria:** `SUPPORTED_RUNTIME_VERSIONS` contiene build 10909, pero los ejecutables build 10909 encontrados (`~/.local/bin/llama`, `~/.llama-app/llama`) no soportan `--list-devices`, por lo que `detect_llama_capability()` no puede confirmar dispositivos GPU para ellos. Sin embargo, `detect_backends()` en `runtimes.py` reporta Vulkan como disponible si `vulkaninfo` está en PATH, independientemente del runtime.

### 2.6 Comportamiento de las rutas `run` y `execute`

- **`run_service.run_once()` / `prepare()`:** resuelve artefacto → compatibilidad → preflight → selección → runner. Para backend SYCL inyecta `SyclLlamaRunner`; para CPU/Vulkan usa `LlamaCppRunner`.
- **`execute_model.execute_model()`:** mismo pipeline, con admisión estricta (B9.78) previa. Para `target.backend == "SYCL"` requiere `SyclLlamaRunner` inyectado o construido vía `build_sycl_runner(capability)`.

---

## 3. Comparación de las alternativas A, B y C

### 3.1 Alternativa A — Allowlist global de identidades

Mantener una lista única (`SUPPORTED_RUNTIME_VERSIONS`) con todas las identidades admitidas, sin distinguir backend.

| Ventajas | Desventajas |
|---|---|
| Simple, un único punto de verdad | No distingue capacidades por backend: build 10909 (sin `--list-devices`) y build 11776 (SYCL) comparten la misma allowlist |
| Fácil de entender | No impide que una identidad SYCL se use como CPU/Vulkan sin validación de dispositivo |
| Compatible con código actual | No expresa que build 11776 es válido *solo* para SYCL |

### 3.2 Alternativa B — Admisión por backend

Mantener políticas separadas: una para CPU/Vulkan, otra para SYCL, cada una con su propia lista de versiones admitidas y requisitos de dispositivo.

| Ventajas | Desventajas |
|---|---|
| Expresa que SYCL requiere dispositivo SYCL0 y oneAPI | Más complejo: dos allowlists que mantener |
| Evita que identidad SYCL se confunda con CPU/Vulkan | Requiere cambios en `offload_evidence.py` y posiblemente en `RuntimeCapability` |
| Build 10909 puede seguir admitido para CPU/Vulkan sin requerir `--list-devices` | Debe coordinarse con `detect_llama_capability()` y `detect_sycl_llama_capability()` |

### 3.3 Alternativa C — Registro de runtimes y capacidades

Asociar cada identidad exacta (versión + build + commit) con sus capacidades y restricciones autorizadas (backend, formato, dispositivo requerido, variables de entorno).

| Ventajas | Desventajas |
|---|---|
| Más expresivo y extensible | Complejidad mayor: nuevo registro, lógica de consulta, validación cruzada |
| Permite futuro sin romper versiones existentes | Requiere cambios más profundos en la arquitectura de admisión |
| Cada identidad tiene su propio contrato de offload evidence | Over-engineering para el alcance actual (solo dos runtimes concretos) |

### 3.4 Recomendación: Alternativa B (admisión por backend)

Se recomienda la **Alternativa B** porque:
1. **Seguridad:** separa explícitamente las políticas de CPU/Vulkan y SYCL, evitando que una identidad SYCL se use como CPU sin validación de dispositivo.
2. **Compatibilidad:** build 10909 (actualmente en `SUPPORTED_RUNTIME_VERSIONS`) puede seguir admitido para CPU/Vulkan sin exigirle `--list-devices` (que no soporta).
3. **Complejidad contenida:** solo dos listas de versiones (una por grupo de backend), sin nuevo registro de capacidades.
4. **Justificación de cada identidad con evidencia:** cada identidad se justifica con evidencia real de inferencia o de formato de offload validado.

---

## 4. Política recomendada

### 4.1 Principios rectores

1. **Identidad estricta:** cada runtime se identifica por versión completa (`version: build N, commit H`), no solo por número de versión.
2. **Admisión por backend:** una identidad admitida para SYCL no se transfiere automáticamente a CPU/Vulkan, y viceversa.
3. **No admisión automática:** una versión desconocida nunca se acepta por compartir número de versión con una conocida.
4. **Aislamiento de entorno:** la configuración SYCL (`LD_LIBRARY_PATH`, oneAPI) permanece limitada al proceso que ejecuta el runtime SYCL.

### 4.2 Tabla de identidades admitidas y capacidades autorizadas

| Identidad (versión completa) | Ruta del ejecutable | Backend autorizado | Dispositivo requerido | Formatos | Offload evidence requerido | ¿Admitir? | Justificación |
|---|---|---|---|---|---|---|---|
| `0.4.0-dev (build 10909, commit a2878d30d)` | `~/.local/bin/llama`, `~/.llama-app/llama` | CPU, Vulkan | Ninguno (CPU por defecto) | GGUF | `load_tensors: offloaded X/Y layers to GPU` (formato validado en tests existentes) | **Sí** | Coincide con `SUPPORTED_RUNTIME_VERSIONS` actual; tests existentes validan el formato de offload |
| `8681 (Debian)` | `/usr/bin/llama-cli` | Ninguno | N/A | GGUF | N/A | **No** | No está en `SUPPORTED_RUNTIME_VERSIONS`; paquete de distribución sin evidencia de offload validada para CastleArq |
| `0.7.0-dev (build 11776, commit ead9f3205)` | `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` | SYCL | `SYCL0` | GGUF | `load_tensors: offloaded X/Y layers to GPU` (pendiente de verificación en output real del build 11776) + memoria GPU (`common_memory_breakdown_print`) | **Sí, solo SYCL** | Evidencia real de inferencia en A2.6.6.15; dispositivo SYCL0 confirmado; 4168 MiB offload a GPU |

### 4.3 Reglas de admisión

1. **Build 8681:** NO se admite. No está en `SUPPORTED_RUNTIME_VERSIONS`, no tiene evidencia de offload validada, y es un paquete de distribución ajeno a CastleArq.
2. **Build 10909:** se admite para CPU/Vulkan. Ya está en `SUPPORTED_RUNTIME_VERSIONS`. No requiere cambios para su grupo de backend.
3. **Build 11776:** se admite **exclusivamente para SYCL**. Requiere agregarse a la lista de versiones admitidas para SYCL y validarse el dispositivo SYCL0.
4. **Prevención de identidad SYCL como CPU/Vulkan:** `SyclLlamaRunner.supported_backends = ("SYCL",)` y `execute_model.py` exige `SyclLlamaRunner` para backend SYCL. La política debe exigir que `detect_sycl_llama_capability()` nunca reporte `supported_backends` que incluya CPU o Vulkan.
5. **Prevención de versión desconocida:** `assess_gpu_offload()` rechaza con `UNSUPPORTED_VERSION` cualquier versión no en la lista correspondiente al backend. No hay fallback implícito.
6. **Futuras versiones:** se agregan a la lista correspondiente solo tras evidencia explícita (inferencia validada o tests de offload), nunca automáticamente por compartir número de versión mayor.

---

## 5. Reglas de aislamiento SYCL

La configuración SYCL debe permanecer limitada al proceso que ejecuta el runtime SYCL y no contaminar el entorno global de Core ni las ejecuciones CPU/Vulkan.

| Variable / elemento | Política | Razón |
|---|---|---|
| `CASTLEARQ_SYCL_RUNTIME` | Configurada solo para el proceso de ejecución SYCL (vía `env=` en `subprocess.run`) | Apunta al ejecutable SYCL válido; no afecta a otros runners |
| `CASTLEARQ_SYCL_SETVARS` | Configurada solo para el proceso de ejecución SYCL | Apunta a `setvars.sh` de oneAPI; se carga vía `SyclEnvironmentProvider` |
| `LD_LIBRARY_PATH` | Establecido exclusivamente en el entorno del subprocess SYCL (vía `setvars.sh`), nunca en `os.environ` del proceso Core | Evita contaminar ejecuciones CPU/Vulkan que usan dependencias del sistema |
| Dispositivo `SYCL0` | Hardcodeado en `SyclLlamaRunner.run()` (`--device SYCL0`); validado previamente por `discover_sycl_llama_runtime()` | Garantiza que solo se use el dispositivo SYCL esperado; no hay selección dinámica entre GPUs |
| Rutas oneAPI (`/opt/intel/oneapi/...`) | Accedidas solo vía `setvars.sh` dentro del subprocess SYCL | No se agregan al PATH global de Core |
| Ejecuciones CPU/Vulkan | Usan `LlamaCppRunner` con entorno del sistema (sin `LD_LIBRARY_PATH` oneAPI) | Aislamiento completo entre backends |

**Confirmación:** el código actual de `sycl_runner.py` (líneas 105-113) ya pasa `env=environment` (resultado de `setvars.sh`) exclusivamente a `subprocess.run`, y `test_env_not_modified` verifica que `os.environ` no se modifica. El aislamiento está implementado; solo requiere configurar las variables de entorno en el despliegue.

---

## 6. Reglas de verificación de offload por backend

| Backend | Evidencia requerida | Interpretación de ausencia de evidencia |
|---|---|---|
| **CPU** | No declarar offload GPU. El backend CPU no ejecuta en GPU. | N/A (offload no aplica) |
| **Vulkan** | Evidencia específica de Vulkan (formato a definir; no se asume compatibilidad con formato SYCL/CPU). | `UNKNOWN`/`NO_FINAL_COUNT` — no se confirma aceleración GPU |
| **SYCL** | (1) Identidad en lista admitida para SYCL; (2) dispositivo `SYCL0` detectado en `--list-devices`; (3) ejecución exitosa (código 0); (4) evidencia suficiente: `load_tensors: offloaded X/Y layers to GPU` con `X > 0`, **o** desglose de memoria `common_memory_breakdown_print` con `model > 0` en SYCL0 | `UNKNOWN` — no se considera aceleración GPU confirmada (principio de A2.6.6.15 §4) |

**Nota crítica sobre build 11776:** en A2.6.6.15 la salida del terminal fue middle-truncada, por lo que no se verificó si el build 11776 emite el formato `load_tensors: offloaded X/Y layers to GPU`. Sí se confirmó `common_memory_breakdown_print` con `SYCL0 ... model 4168 MiB`, que es evidencia secundaria de offload. La política debe exigir verificación del formato de output del build 11776 antes de confiar en `assess_gpu_offload()` para SYCL.

**No asumir compatibilidad de formato:** una misma expresión de salida de llama.cpp no funciona en todas las versiones y backends. Cada identidad admitida debe tener su formato de offload evidence validado contra output real.

---

## 7. Cambios mínimos para futura implementación

### 7.1 Obligatorios

1. **`castlearq/offload_evidence.py`:**
   - Dividir `SUPPORTED_RUNTIME_VERSIONS` en dos conjuntos: uno para CPU/Vulkan (mantener build 10909) y uno para SYCL (añadir build 11776).
   - `assess_gpu_offload()` debe recibir el backend objetivo y validar la versión contra el conjunto correspondiente.
   - Opcional: ampliar el parser para reconocer `common_memory_breakdown_print` como evidencia secundaria de offload SYCL.

2. **Configuración de despliegue:** definir `CASTLEARQ_SYCL_RUNTIME=/home/brunapc/llama.cpp-sycl/build/bin/llama-cli` y `CASTLEARQ_SYCL_SETVARS=<ruta setvars.sh de oneAPI>` solo para ejecuciones SYCL.

### 7.2 Opcionales (mejores prácticas)

3. **`castlearq/sycl_runner.py`:** en `build_sycl_runner()`, validar que el `executable_path` tenga SYCL disponible (reutilizar `discover_sycl_llama_runtime` o verificar `--list-devices` contiene `SYCL0`) antes de construir el runner.
4. **`castlearq/runtimes.py`:** `detect_sycl_llama_capability()` debe garantizar que `supported_backends` solo contenga `"SYCL"`, nunca CPU o Vulkan.

---

## 8. Tests necesarios para validar la política

| Test | Objetivo | ¿Existente? |
|---|---|---|
| `assess_gpu_offload` con versión build 11776 y output `load_tensors: offloaded 28/28 layers to GPU` | Verificar que el parser acepta la versión SYCL y confirma offload | No (solo tests con build 10909) |
| `assess_gpu_offload` con versión build 8681 | Verificar que se rechaza como `UNSUPPORTED_VERSION` para SYCL | No |
| `detect_sycl_llama_capability()` con ejecutable SYCL real y `setvars.sh` | Verificar `available=True`, `version="0.7.0-dev (build 11776, commit ead9f3205)"`, `supported_backends=("SYCL",)` | No (solo tests con mock) |
| `build_sycl_runner` con `executable_path` inválido | Verificar fallo rápido en configuración errónea | No |
| `test_env_not_modified` (ya existente) | Verificar que `os.environ` no se contamina | Sí (`test_sycl_runner.py`) |
| `test_sycl_discovery` (ya existente) | Verificar estados de disponibilidad SYCL | Sí |

---

## 9. Riesgos, incompatibilidades y cuestiones pendientes

| Riesgo | Descripción | Mitigación |
|---|---|---|
| Formato de offload del build 11776 no verificado | A2.6.6.15 fue truncado; no se confirmó si emite `load_tensors: offloaded X/Y layers to GPU` | Ejecutar inferencia corta capturando salida completa; verificar formato |
| `~/.local/bin/llama` y `~/.llama-app/llama` no soportan `--list-devices` | Build 10909 no puede confirmar dispositivos GPU mediante ese comando | Para CPU/Vulkan, no se requiere `--list-devices` (CPU es por defecto) |
| Build 8681 en PATH del sistema | `detect_runtimes()` lo detecta como instalado/disponible sin validar versión | La política de admisión debe filtrar por versión, no solo por presencia |
| `SUPPORTED_RUNTIME_VERSIONS` es estático | Nuevas versiones requieren cambio de código | Documentar proceso de adición de versiones con evidencia |

**Cuestiones pendientes:**
1. ¿Se debe admitir build 8681 para CPU aunque no esté en `SUPPORTED_RUNTIME_VERSIONS`? La recomendación es NO, por falta de evidencia de offload validada y por ser paquete de distribución ajeno a CastleArq.
2. ¿Se requiere verificar que `~/.local/bin/llama` y `~/.llama-app/llama` son el mismo build (mismo commit)? Sí, ambos reportan `0.4.0-dev (build 10909, commit a2878d30d)`.

---

## 10. Dictamen

**Política definida con incertidumbres.**

La política de admisión multi-runtime puede definirse sobre la base de la evidencia recopilada (A2.6.6.13 a A2.6.6.16). La arquitectura de CastleArq Core ya soporta runtimes múltiples de forma aislada, y los cambios necesarios son mínimos y bien delimitados.

**Incertidumbres restantes:**
1. El formato exacto de output de offload del build 11776 no se pudo verificar completamente por truncamiento de terminal en A2.6.6.15. Se confirmó evidencia de memoria GPU (4168 MiB en SYCL0) pero no el formato de texto `load_tensors: offloaded X/Y layers to GPU`.
2. No se verificó si `~/.local/bin/llama` y `~/.llama-app/llama` son hardlinks o copias independientes (inodes distintos, mismo tamaño y versión).

Estas incertidumbres no impiden definir la política, pero deben resolverse antes de una implementación que dependa del parser de offload evidence para SYCL.

**No se implementó ninguna política en esta fase.** El informe es exclusivamente de análisis y diseño.

---

**Fin del informe A2.6.6.17.**