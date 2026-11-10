# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 7. Problemas arquitectónicos reales, con referencias a código

### 1. Detección SYCL fragmentada

**Problema**: `detect_llama_capability()` nunca incluye SYCL en `supported_backends`. El descubrimiento SYCL es una función separada (`detect_sycl_llama_capability`) que requiere `executable_path` explícito.

**Código afectado**: `castlearq/runtimes.py: detect_llama_capability()` (líneas 318-416 aprox)

**Impacto**: Los flujos de `prepare_execution()` y `assess_model()` nunca seleccionan SYCL automáticamente. El usuario debe configurar `CASTLEARQ_SYCL_RUNTIME` explícitamente.

### 2. `SUPPORTED_RUNTIME_VERSIONS` no incluye la versión SYCL validada correctamente

**Problema**: `offload_evidence.py:34` tiene `SUPPORTED_RUNTIME_VERSIONS = frozenset({SUPPORTED_RUNTIME_VERSION})` donde `SUPPORTED_RUNTIME_VERSION = "0.4.0-dev (build 10909, commit a2878d30d)"`. Aunque existen `SUPPORTED_RUNTIME_VERSIONS_CPU_VULKAN` y `SUPPORTED_RUNTIME_VERSIONS_SYCL` (líneas 39-43), la función `assess_gpu_offload()` solo los usa cuando se pasa el parámetro `backend` (y solo si el llamado viene del camino correcto).

**Código afectado**: `castlearq/offload_evidence.py:150-168`

**Impacto**: Incluso cuando se ejecuta inferencia SYCL correctamente (como en A2.6.6.15), la evidencia de offload se clasifica como `unsupported_version` a menos que se passe explícitamente `backend="SYCL"`.

### 3. No hay orquestación "Intel-first"

**Problema**: No hay lógica que intente automáticamente múltiples runtimes Intel (CPU → SYCL → OpenVINO) basándose en el hardware disponible y el tipo de modelo.

**Código afectado**: No hay función única de orquestación; la selección ocurre en `RuntimeBackendSelector.select()` que trabaja con una capability a la vez.

**Impacto**: En un sistema con CPU Intel + GPU Arc, CastleArq no intentará automáticamente SYCL para modelos GGUF. El usuario debe configurar y seleccionar manualmente.

### 4. Hardcodificación de `SYCL0` en el runner

**Problema**: `sycl_runner.py:109` fija `--device SYCL0` en los argumentos de ejecución.

**Código afectado**: `castlearq/sycl_runner.py:106-116`

**Impacto**: No permite seleccionar dinámicamente entre múltiples dispositivos SYCL. Si un sistema tiene `SYCL0` y `SYCL1`, solo funcionará `SYCL0`.

### 5. OpenVINO y llama.cpp son caminos aislados

**Problema**: Cuando un modelo tiene `backend: "openvino"`, el sistema toma un camino completamente diferente sin considerar si también hay un runtime llama.cpp disponible.

**Código afectado**: `run_service.py:457-520` y `main.py:477-522`

**Impacto**: Un modelo GGUF también podría ejecutarse vía OpenVINO si hubiera conversión, pero no hay detección/unificación que lo permita. Cada formato va por su camino.

### 6. `discover_sycl_llama_runtime()` referenciado en tests pero no implementado

**Problema**: Tests y reportes anteriores referencian `discover_sycl_llama_runtime` pero la función nunca fue implementada en `runtimes.py`.

**Código afectado**: `castlearq/runtimes.py` — la función no existe; solo `detect_sycl_llama_capability()` existe.

**Impacto**: Tests `test_sycl_discovery.py` fallan con `AttributeError` al intentar importar la función inexistente.