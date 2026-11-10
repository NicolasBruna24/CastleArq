# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 2. Mapa de integración de OpenVINO

### Arquitectura

- **`castlearq/openvino_inference.py`**: Servicio de inferencia OpenVINO GenAI
- **`OpenVINOInferenceService`**: Clase principal que gestiona el ciclo de vida de la inferencia
- **`PipelineFactory`**: Protocolo para fábricas de pipelines (patrón de diseño)

### Carga y detección

- **`_available_openvino_devices()`**: Detecta dispositivos disponibles usando `openvino as ov`:
  ```python
  core = ov.Core()
  devices = tuple(str(device) for device in core.available_devices)
  ```
- Soporta dispositivos: `CPU`, `GPU`, y otros dispositivos OpenVINO compatibles
- El dispositivo se selecciona pasando el parámetro `device` a `generate()` (default: `"CPU"`)

### Preparación de modelo

- **Validación de archivos**: Verifica que existan archivos `.bin` (pesos) correspondientes
- **Validación de tokenizador integrado**: Verifica el tokenizer integrado del modelo
- **`_validate_artifact_files()`**: Verifica checksums y content_id de paquetes OpenVINO
- **`_validate_integrated_tokenizer()`**: Valida el tokenizer integrado

### Ejecución de inferencia

- **`generate(manifest_path, prompt, device="CPU", max_new_tokens=8)`**: Ejecuta la inferencia
- **Factory pattern**: `_build_pipeline_factory()` crea el pipeline para el modelo
- **Pipelines cached** por `(str(model_dir), device)` key
- **Extracción de resultados**: `_extract_generated_text()` y `_extract_finish_reason()` manejan dos formas de resultado observadas en tiempo de ejecución

### Resultados

- **`OpenVINOGenerationResult`**: `text`, `device`, `requested_backend`, `initialization_status`, `effective_device`, `requested_device`, `available_devices`, `physical_telemetry`, `finish_reason`

### Integración con CastleArq

- **`run_service.py`**: Cuando `backend == "openvino"`, crea `OpenVINOInferenceService` y `OpenVINOChatSession`
- **`main.py`**: El comando `run` detecta `backend == "openvino"` en el artifact resolvido y toma el camino OpenVINO
- Los modelos OpenVINO llevan `backend: "openvino"` en su artifact spec