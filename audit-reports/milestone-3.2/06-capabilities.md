# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 6. Capacidades verificadas, experimentales y pendientes

### llama.cpp / GGUF

| Capacidad | Estado | Evidencia |
|---|---|---|
| Detección de ejecutable `llama-cli`/`llama` | ✅ Verificada | `detect_llama_capability()` funciona via `shutil.which()` |
| Formato GGUF admitido | ✅ Verificado | `supported_formats=("GGUF",)` en `RuntimeCapability` |
| Ejecución CPU | ✅ Verificada | `LlamaCppRunner` con `--device CPU` |
| Ejecución Vulkan | ✅ Verificada | `LlamaCppRunner` con `--device Vulkan` (cuando está disponible) |
| Ejecución SYCL | ✅ Verificada (con configuración) | Reportes A2.6.6.14 y A2.6.6.15: inferencia exitosa en Intel Arc Pro B70 |
| Detección automática SYCL | ❌ Pendiente | `detect_llama_capability()` no incluye SYCL; requiere `executable_path` explícito |
| Versión runtime para offload | ✅ Parcial | `SUPPORTED_RUNTIME_VERSIONS_SYCL` incluye `0.7.0-dev (build 11776)`, pero depende de pasar `backend="SYCL"` a `assess_gpu_offload()` |

### OpenVINO

| Capacidad | Estado | Evidencia |
|---|---|---|
| Cargar OpenVINO GenAI | ✅ Verificada | `OpenVINOInferenceService` en `openvino_inference.py` |
| Detectar CPU/GPU | ✅ Verificada | `_available_openvino_devices()` via `ov.Core().available_devices` |
| Ejecución CPU | ✅ Verificada | `device="CPU"` en `generate()` |
| Ejecución GPU | ✅ Verificada | `device="GPU"` en `generate()` (cuando hay GPU Intel compatible) |
| Carga de modelos OpenVINO | ✅ Verificada | Validación de `.bin` weights, content_id, sha256 |
| Integración con admisión | ✅ Verificada | `run_service.py` toma camino OpenVINO cuando `backend=="openvino"` |
| Versión/runtime para offload | ✅ No aplica | OpenVINO no usa el sistema de offload de llama.cpp |

### Intel GPU Arc

| Capacidad | Estado | Dispositivo |
|---|---|---|
| Detección SYCL (`sycl-ls` / `--list-devices`) | ✅ Verificada | A2.6.6.14: `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics` |
| Ejecución GGUF vía SYCL | ✅ Verificada | A2.6.6.15: 90.27 t/s, offload 4168 MiB a GPU |
| Soporte OpenVINO para Arc | ✅ Verificable | Depende de si el modelo tiene optimización OpenVINO |
| Selección dinámica de dispositivo | ❌ Pendiente | Hardcoded `SYCL0` en `sycl_runner.py` |

### Intel NPU

| Capacidad | Estado | Comentario |
|---|---|---|
| Detección NPU | ❌ No diseñado | No hay código de detección NPU en el códigobase |
| Integración NPU | ❌ No diseñado | Sin implementación ni diseño actual |
| Flujo de orquestación | ❌ No diseñado | Futuro soporte, no en el scope actual |