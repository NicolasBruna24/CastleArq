# LocalAI Hub

LocalAI Hub busca ocultar la complejidad de ejecutar modelos de IA localmente
mediante detección automática de hardware, runtimes y backends. El proyecto
prioriza simplicidad, fiabilidad y mantenibilidad, sin instalar drivers,
runtimes ni dependencias del sistema.

## Estado actual

La Fase 1 está implementada:

- detección de sistema operativo, arquitectura, CPU, RAM y GPU en Linux;
- detección tolerante de VRAM cuando el hardware la expone (más soporte en fases posteriores);
- detección de runtimes `llama.cpp / llama.app` y Ollama;
- detección por presencia de Vulkan, OpenCL, SYCL, CUDA y ROCm;
- recomendación basada exclusivamente en lo detectado;
- interfaz preparada para futuros modelos y runners, sin ejecutar inferencia.

Los comandos ausentes, salidas inválidas y datos no disponibles se muestran como
`Unknown`, `Not detected` o `not available`; no provocan tracebacks al usuario.

## Instalación y uso

Se requiere Python 3.10 o posterior. No hay dependencias externas en el MVP:

```bash
python -m unittest discover -s tests
python -m app.main detect
```

La aplicación no usa `sudo`, no modifica el sistema y no instala drivers,
CUDA, ROCm, SYCL, oneAPI ni otros runtimes.

## Arquitectura

- `app/hardware.py`: estructuras y detección de hardware.
- `app/runtimes.py`: detección de runtimes y backends.
- `app/models.py`: metadatos de modelos para una fase futura.
- `app/runner.py`: interfaz abstracta para runners futuros.
- `app/main.py`: CLI.

La detección está separada de la presentación y acepta funciones de ejecución
inyectables, lo que permite probarla sin GPU real.

## Roadmap

1. Detección de hardware y runtimes.
2. Catálogo de modelos y compatibilidad.
3. Descarga de modelos.
4. Ejecución mediante runners.
5. API local compatible con OpenAI.
6. Integración con Aider, Cline, Continue, VS Code y Qwen Code.
7. Interfaz gráfica.
8. Soporte avanzado para NVIDIA/CUDA, AMD/ROCm, Intel/SYCL, Vulkan y otros backends.

No se implementarán marketplace, cuentas, nube, Kubernetes, Docker obligatorio,
telemetría ni gestión automática de drivers en esta fase.
