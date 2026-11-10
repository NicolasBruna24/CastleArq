# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 4. Diagramas de selección y ejecución

### Flujo de selección de runtime (from request to execution)

```
modelo request
       │
       ▼
resolver ModelArtifactResolver → resolved.model + resolved.artifact
       │
       ▼
detect_llama_capability() o detect_sycl_llama_capability() → capability
       │
       ▼
assess_model(hardware, runtimes, backends, model) → CompatibilityResult
       │   recommended_runtime │ recommended_backend
       ▼
preparar execute_preparation = prepare_execution(...)
       │
       ▼
selector = RuntimeBackendSelector.select(compatibility, capability, artifact)
       │
       ▼
ExecutionTarget: runtime=..., backend=..., requested_device_argument=...
       │
       ▼
create_runner(capability, target) → LlamaCppRunner / SyclLlamaRunner / ...
       │
       ▼
 runner.run(executable_artifact, target, request) → ExecutionResult
```

### Puntos de decisión clave

1. **Módulo que decide el runtime**: `prepare_execution()` en `execution_preparation.py` — llama a `selector.select()` después de evaluar compatibilidad

2. **Módulo que decide el dispositivo**: `RuntimeBackendSelector.select()` — usa `compatibility.recommended_backend` a menos que se proporcione `requested_backend`; el `requested_device_argument` viene de `capability.backend_argument(recommended_backend)`

3. **Información utilizada para decisiones:**
   - `compatibility.recommended_runtime` (de `assess_model()`)
   - `compatibility.recommended_backend` (de `assess_model()`)
   - `capability.supported_backends`
   - `capability.backend_argument(backend)` (retorna argumento de línea de comandos)
   - `executable_artifact.artifact.format` (debe estar en `capability.supported_formats`)
   - `model.supported_backends` (desde el catálogo del modelo)

4. **Selección real vs indicadores indirectos:**
   - La selección se basa en capacidades reales detectadas (`capability.available`, `capability.invocable`)
   - Pero `detect_llama_capability()` **no incluye SYCL** en `supported_backends` — SYCL solo se detecta cuando se provee `executable_path` explícitamente
   - `SUPPORTED_RUNTIME_VERSIONS` filtra versiones de runtime para evidencia de offload

5. **Qué ocurre cuando un runtime está instalado pero no puede usar el dispositivo:**
   - `SyclLlamaRunner.run()` falla con error de subprocess si `setvars.sh` no carga correctamente o los binaries SYCL no están resolubles
   - `OpenVINOInferenceService.generate()` falla si el dispositivo solicitado no está en `available_devices`
   - El selector falla con `BACKEND_UNSUPPORTED` si el backend recomendado no está en `capability.supported_backends`

6. **Qué ocurre cuando existen varios runtimes disponibles:**
   - `prepare_execution()` obtiene `runtimes` de `detect_runtimes()` o `detect_runtime_statuses()` — solo llama a la función una vez
   - `RuntimeBackendSelector.select()` trabaja con **una** capability a la vez
   - No hay lógica automática "probar SYCL si CPU falla" o "probar OpenVINO si llama.cpp falla"
   - El usuario debe configurar `CASTLEARQ_SYCL_RUNTIME` y `CASTLEARQ_SYCL_SETVARS` explícitamente