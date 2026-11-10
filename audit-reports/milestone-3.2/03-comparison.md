# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 3. Comparación de ambos runtimes

| Aspecto | llama.cpp | OpenVINO |
|---|---|---|
| **Detección** | `detect_llama_capability()` en `runtimes.py`; `detect_syll_llama_capability()` cuando se provee `executable_path` | `_available_openvino_devices()` en `openvino_inference.py` via `openvino as ov.Core()` |
| **Disponibilidad** | `detect_runtimes()` returns `RuntimeStatus`; `SUPPORTED_RUNTIME_VERSIONS` estático | Detecta via import `openvino`; no hay versión estática comparable |
| **Formatos** | GGUF (principalmente); `supported_formats=("GGUF",)` para SYCL | Modelos OpenVINO optimizados (.xml + .bin); valida archivos .bin auxiliary |
| **Selección de dispositivo** | CPU o Vulkan (desde `--list-devices`); SYCL fijo en `SYCL0` (hardcodeado) | `device` parámetro en `generate()` (default "CPU"); también "GPU" si disponible |
| **Preparación** | Validación de artifact preflight; selección de backend vía `RuntimeBackendSelector` | Validación de archivos .bin, content_id, sha256, tokenizer integrado |
| **Ejecución** | Subprocess de `llama-cli` con argumentos variables | Pipeline OpenVINO GenAI `pipeline.generate(prompt, max_new_tokens=...)` |
| **Manejo de errores** | Errores de subprocess, timeouts, códigos de retorno; `ExecutionErrorCode` | `OpenVINOInferenceError` jerarquía ( `MissingDependencyError`, `InvalidArtifactError`, `PipelineInitError`, `GenerationError` ) |
| **Ciclo de vida** | Ejecución única (one-shot) por invocación; no hay persistencia de pipeline | Pipelines cached por `(model_dir, device)` key; `close()` cierra referencias |
| **Pruebas** | `test_runner.py` (19/19), `test_gpu_offload_evidence.py` (19/20) | `test_openvino_inference.py`, `test_openvino_integration_contracts.py` |

### Responsabilidades compartidas vs específicas

**Compartidas:**
- Evaluación de compatibilidad de modelos (`assess_model()` en `compatibility.py`)
- Selección de backend (`RuntimeBackendSelector.select()` en `selection.py`)
- Admisión estricta (`EvaluationAdmission`, denegación por defecto B9.78)
- Preflight de artifact (`ArtifactExecutionPreflight`, verificación de checksums)
- Detección de hardware (`detect_hardware()` en `hardware.py`)

**Específicas de runtime:**
- Ejecutable y argumentos (`LlamaCppRunner`, `SyclLlamaRunner`, `OpenVINOInferenceService`)
- Formatos de modelo y validación (GGUF vs OpenVINO .xml/.bin)
- Extracción de resultados y telemetría
- Manejo de errores específico del framework