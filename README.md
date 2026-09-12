# LocalAI Hub

LocalAI Hub busca ocultar la complejidad de ejecutar modelos de IA localmente
mediante detección automática de hardware, runtimes y backends. El proyecto
prioriza simplicidad, fiabilidad y mantenibilidad, sin instalar drivers,
runtimes ni dependencias del sistema.

## Estado actual

La Fase 1.5 está implementada:

- detección de sistema operativo, arquitectura, CPU, RAM y GPU en Linux;
- GPU con nombre, fabricante, PCI ID, driver y fuente de cada dato cuando están disponibles;
- detección de VRAM mediante sysfs y, opcionalmente, `vulkaninfo` o `llama ... serve --list-devices`;
- VRAM total y disponible, conservando `Unknown` cuando ninguna fuente lo expone;
- detección de runtimes `llama.cpp / llama.app` y Ollama;
- detección por presencia de Vulkan, OpenCL, SYCL, CUDA y ROCm;
- recomendación basada exclusivamente en lo detectado;
- interfaz preparada para futuros modelos y runners, sin ejecutar inferencia.

Los comandos ausentes, salidas inválidas y datos no disponibles se muestran como
`Unknown`, `Not detected` o `not available`; no provocan tracebacks al usuario.

## Instalación y uso

Se requiere Python 3.10 o posterior. No hay dependencias externas en el MVP:

```bash
python3 -m unittest discover
python3 -m app.main detect
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
inyectables, lo que permite probarla sin GPU real. Las fuentes de GPU son
opcionales: si falta `lspci`, sysfs, Vulkan o llama.app, la aplicación continúa
mostrando únicamente la información disponible. No se instala software
automáticamente y no se modifican drivers, kernel ni configuración del sistema.

## Roadmap

1. Detección de hardware y runtimes.
2. Mejora de fuentes de GPU y VRAM (Fase 1.5).
3. Catálogo de modelos y compatibilidad.
4. Descarga de modelos.
5. Ejecución mediante runners.
6. API local compatible con OpenAI.
7. Integración con Aider, Cline, Continue, VS Code y Qwen Code.
8. Interfaz gráfica.
9. Soporte avanzado para NVIDIA/CUDA, AMD/ROCm, Intel/SYCL, Vulkan y otros backends.

No se implementarán marketplace, cuentas, nube, Kubernetes, Docker obligatorio,
telemetría ni gestión automática de drivers en esta fase.
