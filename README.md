# CastleArq

CastleArq es un gestor y orquestador local de artifacts de IA. Descubre y
diagnostica un runtime local, gestiona modelos GGUF, evalúa compatibilidad,
selecciona el backend disponible y ejecuta prompts con llama.cpp.

CastleArq no reemplaza a llama.cpp: el runtime, sus drivers y sus modelos son
dependencias externas que debe proporcionar el usuario.

## What is CastleArq?

CastleArq ofrece un flujo local para:

- descubrir y diagnosticar el runtime oficial `llama`;
- consultar el catálogo de modelos;
- descargar explícitamente artifacts GGUF;
- almacenarlos y volver a listarlos localmente;
- validar compatibilidad y seleccionar backend;
- ejecutar un primer prompt o una sesión chat.

La documentación técnica de arquitectura, contratos, evaluación y ejecución
está en [`docs/`](docs/). El usuario no necesita leerla para completar el
flujo básico.

## Requirements

- Linux como baseline actual.
- Python `>=3.10`.
- Un entorno virtual de Python.
- `llama.cpp` proporcionado externamente, con el ejecutable oficial `llama`
  disponible en `PATH`.

CastleArq no incluye llama.cpp, modelos, drivers, Vulkan, CUDA, ROCm ni otros
stacks de GPU. El flujo normal no requiere `sudo` y no modifica el sistema.

## Installation

Desde un checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
castlearq --version
castlearq --help
```

También puede instalarse desde un wheel o sdist construido previamente. Por
ejemplo, con un wheel local:

```bash
pip install dist/castlearq-0.1.0-py3-none-any.whl
```

La instalación no necesita `PYTHONPATH` ni el código fuente después de
instalarse. El paquete no contiene modelos.

## Runtime setup

CastleArq requiere el ejecutable `llama`; no instala ni compila llama.cpp.
Comprueba primero que el launcher esté en el `PATH`:

```bash
command -v llama
```

Después consulta el estado que CastleArq puede observar:

```bash
castlearq runtime
```

La salida muestra el runtime, launcher, executable resuelto, versión, build,
estado de disponibilidad y capabilities detectadas.

| Estado | Significado | Acción |
|---|---|---|
| `AVAILABLE` | Runtime utilizable | Continuar con modelos. |
| `NOT_FOUND` | `llama` no está disponible | Proporcionar llama.cpp externamente. |
| `FOUND_UNUSABLE` | Se encontró un path no utilizable | Revisar path, permisos y tipo de ejecutable. |
| `PROBE_ERROR` | La validación no pudo completarse | Revisar el `reason`, instalación o build de llama.cpp. |
| `UNKNOWN` | No hay evidencia suficiente | Revisar el `reason` y repetir el diagnóstico. |

`llama` es el launcher oficial. `llama-cli`, `llama-server` y `llama.app` no
sustituyen automáticamente a `llama` para la ejecución de CastleArq 0.1.x.

## First model

Consulta el catálogo y elige el `MODEL_ID` canónico:

```bash
castlearq models
```

Descarga explícitamente el artifact:

```bash
castlearq download qwen2.5-coder-7b-instruct
```

La descarga requiere conexión con la fuente remota. Si el catálogo ofrece
varias variantes, puedes seleccionar una con:

```bash
castlearq download MODEL_ID --quantization QUANTIZATION
```

o indicar un archivo concreto con `--filename` cuando corresponda. No se
asume que un modelo remoto permanezca disponible para siempre.

En este flujo:

- **model**: el modelo lógico que quieres usar;
- **`MODEL_ID`**: el identificador canónico que acepta la CLI;
- **artifact**: el archivo concreto que se descarga y almacena;
- **GGUF**: el formato del artifact usado por el runtime actual;
- **quantization**: la variante de precisión/tamaño elegida;
- **filename**: el nombre exacto del artifact.

## Verify local artifacts

```bash
castlearq list
```

`list` muestra los artifacts locales con su model ID, filename, quantización,
tamaño y estado. Los artifacts se reutilizan en ejecuciones posteriores.

El ModelStore oficial es independiente del checkout:

```text
$XDG_DATA_HOME/castlearq/models
```

y el fallback es:

```text
~/.local/share/castlearq/models
```

`~/.local/share/localai-hub/models` es únicamente compatibilidad legacy; no es
la ruta recomendada para nuevas instalaciones. No es necesario editar manifests
ni mover modelos manualmente para usar CastleArq.

## First execution

La interfaz recomendada para el primer uso es `execute`:

```bash
castlearq execute qwen2.5-coder-7b-instruct "Reply with exactly B9.34-OK"
```

Un prompt exitoso muestra la respuesta del modelo en stdout. El runtime
puede escribir mensajes de carga y generación, y CastleArq puede mostrar
warnings en stderr. Un warning no implica por sí solo que la ejecución haya
fallado.

- exit code `0`: ejecución exitosa;
- exit code `1`: fallo operativo;
- exit code `2`: argumentos o uso incorrecto.

La salida exacta puede variar con el modelo y el prompt. Un resultado exitoso
debe incluir salida generada y código `0`.

La interfaz `run` también existe y es compatible:

```bash
castlearq run qwen2.5-coder-7b-instruct --prompt "Reply with exactly B9.34-OK"
```

`run` y `execute` no son aliases sintácticos: `run` recibe `--prompt`, mientras
que `execute` recibe el prompt como argumento. Usa `execute` para el primer
flujo recomendado y conserva `run` como interfaz existente.

## Model management

El ciclo básico es:

```text
models → choose MODEL_ID → download → list → execute
```

`models` descubre el catálogo, `download` adquiere el artifact explícitamente,
`list` comprueba el almacenamiento local y `execute` ejecuta un prompt. Repetir
`execute` no vuelve a descargar el modelo.

## Troubleshooting

### `llama` no encontrado

Comprueba:

```bash
command -v llama
castlearq runtime
```

Si aparece `NOT_FOUND`, proporciona llama.cpp externamente y vuelve a ejecutar
`castlearq runtime`. CastleArq no lo instalará automáticamente.

### Runtime `FOUND_UNUSABLE`

CastleArq encontró un path, pero no puede usarlo como launcher. Revisa el path
devuelto, los permisos, el tipo de archivo y la instalación/build del runtime.

### Runtime `PROBE_ERROR`

CastleArq encontró el launcher pero no pudo validar la interfaz. Lee `Reason`,
revisa la instalación/build de llama.cpp y vuelve a ejecutar el diagnóstico.
Esto no demuestra por sí solo una incompatibilidad universal.

### Artifact inexistente

Consulta el catálogo y el ModelStore:

```bash
castlearq list
castlearq models
castlearq download MODEL_ID
```

### Artifact inválido o incompleto

Revisa `castlearq list`. No intentes ejecutar un artifact cuyo estado no sea
utilizable. Si el artifact no está descargado, vuelve a usar `download`; el
comando existente conserva la semántica de validación y no publica un
artifact que no cumpla sus verificaciones.

### Incompatibilidad

La ejecución puede bloquearse por modelo, artifact, memoria, quantization o
capabilities. Revisa `castlearq models`, `castlearq list` y `castlearq runtime`
antes de elegir otro artifact o prompt.

### Backend unavailable

Consulta las capabilities:

```bash
castlearq runtime
```

No asumas que un backend anunciado por el hardware está disponible en el
runtime. Usa un backend compatible con lo detectado.

### Admission denied

CastleArq bloqueó la ejecución según la evaluación actual. Lee el motivo
mostrado; no hay una instrucción para forzar la ejecución.

### Execution failure

Revisa el error y el stderr de la ejecución, y contrasta:

```bash
castlearq runtime
castlearq list
```

El fallo del proceso no significa automáticamente que falte el runtime o el
artifact.

### Download failure

Revisa conectividad, la disponibilidad de la fuente remota, el `MODEL_ID`, la
selección de quantization/filename y vuelve a ejecutar:

```bash
castlearq download MODEL_ID
```

### CLI usage error

Consulta:

```bash
castlearq --help
```

El exit code `2` indica uso incorrecto, como argumentos faltantes o flags no
válidos.

## Architecture

La documentación de arquitectura y los contratos técnicos están en
[`docs/`](docs/). Incluye decisiones de runtime discovery, capability,
compatibility, admission, ModelStore y execution. Es material opcional para el
flujo de usuario.

## Development

Desde un checkout, el mecanismo compatible es:

```bash
python3 -m app.main --help
python3 -m app.main --version
```

Los tests se ejecutan con pytest:

```bash
python3 -m pytest
```

El desarrollo desde checkout no es necesario para usar el paquete instalado.

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE) for
the full text.
