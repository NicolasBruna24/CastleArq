# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 1. Mapa de integración de llama.cpp

### Arquitectura de detección

- **`castlearq/runtimes.py`**: Detection module
  - `detect_llama_capability()`: Detects `llama`, `llama-cli`, `llama-server`, `llama.app` via `shutil.which()`
  - Ejecuta `--version` y `--help` (subcomando `cli`)
  - Detecta backends: `CPU` siempre; `Vulkan` solo si aparece en `--list-devices`
  - **No tiene conocimiento de SYCL**. Devuelve `supported_backends=("CPU",)` o `("CPU", "Vulkan")`
  - Punto de entrada usado por `run_service.prepare()` y `execute_model.execute_model()` para el camino CPU/Vulkan

- **`castlearq/runtimes.py`**: SYCL-specific detection
  - `detect_sycl_llama_capability(executable_path, setvars_path)`: Descubre runtime SYCL solo si se pasa `executable_path`
  - Flujo: verifica ejecutable, carga `setvars.sh`, ejecuta `--version`, `--help`, `--list-devices` (requiere `SYCL0`)

### Capability model

- **`LlamaRuntimeIdentity`**, **`ResolvedLlamaRuntime`**, **`RuntimeCapability`** dataclasses
- **`invocable`**: `available and supports_one_shot`

### Ejecución

- **`LlamaCppRunner`**: Ejecuta CLI de llama.cpp una sola vez
- **`SyclLlamaRunner`**: Versión SYCL; requiere `build_sycl_runner(capability)` con `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS`
- Argumentos SYCL: `--device SYCL0` (hardcoded)

### Estados de runtime

- **`RuntimeStatus`**: `name`, `installed`, `available`, `gpu_backend_detected`, `supported_backends`
- **`RuntimeAvailability`**: `NOT_FOUND`, `FOUND_UNUSABLE`, `AVAILABLE`, `PROBE_ERROR`, `UNKNOWN`