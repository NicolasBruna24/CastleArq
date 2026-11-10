# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 5. Dependencias y acoplamientos

### Dependencias dentro de CastleArq

```
main.py
  ├── run_service.py ←── execution_preparation.py
  │                       │
  │                       ├── compatibility.py ←── hardware.py
  │                       │
  │                       ├── runtimes.py ←── sycl_environment.py
  │                       │
  │                       ├── selection.py
  │                       │
  │                       ├── runner_factory.py ←── sycl_runner.py
  │                       │
  │                       └── runner.py ←── execution.py
  │
  ├── openvino_inference.py (ruta separada, activada cuando backend=="openvino")
  │
  └── api.py (adapta run_service sobre HTTP)
```

### Acoplamientos críticos

1. **`SUPPORTED_RUNTIME_VERSIONS` estático en `offload_evidence.py`** (línea 34):
   - Solo contiene `0.4.0-dev (build 10909)`
   - Aunque existen `SUPPORTED_RUNTIME_VERSIONS_CPU_VULKAN` y `SUPPORTED_RUNTIME_VERSIONS_SYCL` (líneas 39-43), `assess_gpu_offload()` solo los usa cuando se pasa el parámetro `backend`
   - Impacto: ejecuciones SYCL reportan `unsupported_version` aunque el GPU se use realmente

2. **`detect_llama_capability()` sin conciencia SYCL**:
   - Retorna `supported_backends=("CPU",)` o `("CPU", "Vulkan")` nunca `("SYCL",)`
   - El descubrimiento SYCL es una función separada que requiere `executable_path` explícito
   - No hay fusión automática de ambos resultados

3. **`build_sycl_runner()` requiere configuración explícita**:
   - `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` variables de entorno
   - No hay detección automática; el runner falla con `ValueError` si no están configurados

4. **Hardcodificación de `--device SYCL0` en `sycl_runner.py`** (línea 109):
   - Funciona para un dispositivo SYCL pero no permite selección dinámica entre múltiples GPUs SYCL
   - El `backend_argument()` retorna `(("SYCL", "SYCL0"),)` — fijo

5. **OpenVINO y llama.cpp son caminos totalmente separados**:
   - Cuando `backend == "openvino"`, el sistema toma un camino diferente sin considerar llama.cpp disponible
   - No hay orquestación que diga "si hay modelo GGUF y GPU Intel, probar SYCL primero"

6. **`discover_sycl_llama_runtime()` referenciado en tests pero no implementado**:
   - Tests y reportes anteriores lo referencian pero nunca fue implementado en `runtimes.py`
   - Solo `detect_sycl_llama_capability()` existe
   - Tests `test_sycl_discovery.py` fallan con `AttributeError`