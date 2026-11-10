# Milestone 3.2 — Auditoría de integración de runtimes Intel

## 8. Recomendaciones priorizadas

### Prioridad 1: Arreglar `SUPPORTED_RUNTIME_VERSIONS` y evidencias de offload

**Qué hacer**: Asegurar que `assess_gpu_offload()` reciba y use correctamente el parámetro `backend` para validar versiones según el backend (CPU/Vulkan vs SYCL).

**Por qué**: Es el cambio más crítico para informes correctos. Sin esto, cualquier ejecución SYCL reportará `offload UNKNOWN` aunque el GPU se esté usando realmente (violando el principio de no considerar inferencia exitosa como aceleración GPU sin evidencia).

**Referencia**: `castlearq/offload_evidence.py:150-168`, `SUPPORTED_RUNTIME_VERSIONS_SYCL` ya existe en la línea 43.

### Prioridad 2: Hacer detectable SYCL desde `detect_llama_capability()`

**Qué hacer**: Modificar `detect_llama_capability()` para que, cuando el ejecutable detectado soporte SYCL (se verifique via `--list-devices` que contiene `SYCL0`), incluya `"SYCL"` en `supported_backends` y establezca `supported_formats=("GGUF",)`.

**Por qué**: Permitiría que los flujos de selección automática consideren SYCL como una opción viable, no solo cuando el usuario configura variables de entorno explícitas.

**Referencia**: `castlearq/runtimes.py` — `detect_llama_capability()` y `detect_sycl_llama_capability()`

### Prioridad 3: Hacer la selección de dispositivo SYCL dinámica

**Qué hacer**: Modificar `sycl_runner.py` para que acepte el dispositivo como parámetro en lugar de hardcodear `SYCL0`. Pasar el dispositivo desde `capability.backend_argument()` o desde una configuración.

**Por qué**: Los sistemas pueden tener múltiples dispositivos SYCL; la hardcodificación limita la flexibilidad.

**Referencia**: `castlearq/sycl_runner.py:106-116`, línea 109 fija `--device SYCL0`

### Prioridad 4: Agregar orquestación Intel-first

**Qué hacer**: Agregar lógica en `prepare_execution()` o en un nuevo módulo de orquestación que, al detectar hardware Intel (CPU + GPU Arc):
- Intente SYCL primero para modelos GGUF si está disponible
- Falls back a CPU/Vulkan si SYCL falla o no está configurado
- Considere OpenVINO para modelos ya optimizados

**Por qué**: Este es el objetivo central del milestone — permitir que CastleArq seleccione y orchestre runtimes Intel según modelo, hardware y capacidades reales.

**Referencia**: `castlearq/execution_preparation.py:178-240`, `castlearq/selection.py:54-137`

### Prioridad 5: Unificar descubrimiento de runtimes

**Qué hacer**: Crear una función que fusione los resultados de `detect_llama_capability()`, `detect_sycl_llama_capability()` y la detección OpenVINO en un solo informe de capacidades disponibles.

**Por qué**: Hoy no hay "fuente única de verdad" que liste todos los runtimes disponibles con sus capacidades. Los flujos están separados y el usuario debe navegarlos individualmente.

**Referencia**: `castlearq/runtimes.py` — `detect_runtimes()`, `detect_llama_capability()`, `detect_sycl_llama_capability()`

---

## Resumen ejecutivo

**Pregunta central**: ¿Puede CastleArq seleccionar y orquestar correctamente diferentes runtimes Intel según el modelo, el hardware y las capacidades reales del sistema?

**Respuesta**: Parcialmente. La arquitectura tiene los componentes necesarios (diferentes runners, compatibilidad de selección, sistema de admisión), pero están **fragmentados**:

1. **Detección**: `detect_llama_capability()` no ve SYCL; SYCL requiere configuración explícita
2. **Selección**: `RuntimeBackendSelector` funciona correctamente cuando la capability está bien provista, pero la capability rara vez incluye SYCL
3. **Ejecución**: Tanto SYCL como OpenVINO son ejecutables y verificados (reportes A2.6.6.14-15 validan SYCL en Arc B70; openvino_inference.py funciona)
4. **Orquestación**: Faltan — no hay lógica automática para probar múltiples runtimes Intel ni unificar la decisión

**Cambios mínimos obligatorios** para una experiencia Intel coherente:
1. ✅ `SUPPORTED_RUNTIME_VERSIONS_SYCL` ya existe en `offload_evidence.py` (línea 43)
2. ✅ Asegurar que `assess_gpu_offload(backend="SYCL")` valide la versión 0.7.0 correctamente
3. ⚠️ Extender `detect_llama_capability()` para incluir SYCL cuando el ejecutable lo soporte
4. ⚠️ Hacer selección de dispositivo SYCL dinámica
5. ⚠️ Agregar orquestación Intel-first en `prepare_execution()` o composición raíz

Sin los cambios 3 y 4, CastleArq seguirá teniendo integraciones parcialmente independientes de runtimes Intel, requiring configuración manual explícita para cualquier runtime distinto a CPU puro.