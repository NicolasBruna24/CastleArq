# SYCL Experimental Support

CastleArq can execute GGUF models through a llama.cpp build compiled with SYCL,
targeting Intel GPUs via oneAPI. This support is **experimental**: it requires a
SYCL-enabled llama.cpp build, an installed oneAPI toolkit, explicit environment
configuration, and a model that has been validated on the target hardware.

## A. State and scope

- SYCL is an **experimental** backend of CastleArq Core. It is not a default
  and is never selected automatically.
- The backend drives a separate llama.cpp build compiled with SYCL
  (`llama-cli` with `--device SYCL0`).
- Real end-to-end validation was performed on **Intel Arc Pro B70** (SYCL0,
  32 GiB VRAM) with a TinyLlama 1.1B Q4_K_M GGUF artifact: all 23/23 layers
  offloaded to the GPU, exit code 0, both `run` and `execute` paths.
- Universal compatibility with every Intel GPU is **not** claimed. Each model
  and device combination must be validated individually.

## B. Architecture

The SYCL path reuses the existing CastleArq execution contracts and adds four
SYCL-specific pieces:

1. **`SyclEnvironmentProvider`** (`castlearq/sycl_environment.py`) — loads the
   oneAPI environment by sourcing `setvars.sh` in an isolated subprocess and
   capturing the resulting environment. It never mutates `os.environ` of the
   CastleArq process.
2. **`discover_sycl_llama_runtime`** (`castlearq/runtimes.py`) — probes the SYCL
   executable: file existence and executability, oneAPI environment load, `--version`,
   `--help` (required options), and `--list-devices` (must report `SYCL0`).
   Returns a `ResolvedLlamaRuntime` with a `RuntimeCapability` named
   `llama.cpp SYCL` whose `supported_backends=("SYCL",)` and
   `backend_arguments=(("SYCL", "SYCL0"),)`.
3. **Compatibility and selection** (`castlearq/compatibility.py`,
   `castlearq/selection.py`) — an explicit `requested_backend="SYCL"` is honoured
   by `assess_model` and produces `recommended_backend="SYCL"`. The selector
   maps it to `ExecutionTarget.backend="SYCL"` with
   `requested_device_argument="SYCL0"`. There is no silent fallback to CPU or
   Vulkan.
4. **`SyclLlamaRunner`** (`castlearq/sycl_runner.py`) — runs the SYCL
   `llama-cli` with `--device SYCL0`, the isolated oneAPI environment, and
   timeout handling. It reuses `assess_gpu_offload` for runtime-reported
   layer placement evidence.
5. **`build_sycl_runner`** (`castlearq/sycl_runner.py`) — single construction
   point: executable path resolves from `capability.executable_path` first, then
   `CASTLEARQ_SYCL_RUNTIME`; `setvars.sh` always from `CASTLEARQ_SYCL_SETVARS`.

The runner is selected in `run_service._select_runner` and `execute_model`
based on `ExecutionTarget.backend == "SYCL"`. CPU and Vulkan continue to use
`LlamaCppRunner`.

## C. Artifacts and formats

- Only **GGUF** artifacts are supported on the SYCL path (the SYCL capability
  reports `supported_formats=("GGUF",)`).
- OpenVINO artifacts are handled by a separate path and are not affected.

## D. Devices and environment

- **GPU**: Intel Arc Pro B70 (validated). Other Intel GPUs may work but are not
  guaranteed.
- **CPU**: any CPU supported by the SYCL build (used as fallback device
  internally by llama.cpp, but CastleArq never substitutes SYCL with CPU).
- **Device argument**: `SYCL0` (the first SYCL device reported by
  `--list-devices`).
- **oneAPI**: required for the SYCL runtime. CastleArq sources `setvars.sh` in
  an isolated subprocess and never modifies the parent process environment.

## E. Differences versus GGUF/CPU-Vulkan

- SYCL requires a **separate llama.cpp build** compiled with SYCL support.
- The SYCL runner uses a **separate executable path** (`CASTLEARQ_SYCL_RUNTIME`)
  and a oneAPI environment (`CASTLEARQ_SYCL_SETVARS`).
- No automatic fallback: if SYCL is requested and unavailable, execution fails
  with an explicit error.
- The `--device` argument is hardcoded to `SYCL0` in the current runner
  (limitation, see section H).

## F. Admission and internal safety

- SYCL is only selected when explicitly requested (`--backend SYCL`).
- `RuntimeBackendSelector` remains pure and deterministic; it does not detect
  hardware.
- The strict admission gate (`evaluate_model_compatibility`) is unchanged;
  SYCL backend support may be reported as `UNKNOWN` by the knowledge layer,
  which is a non-blocking unknown for execution admission.
- No fallback to CPU or Vulkan is introduced.

## G. Sessions and history

- SYCL execution is supported via `run` and `execute` commands only.
- Chat sessions (`chat` command) and the HTTP API do **not** support SYCL in
  this version.

## H. Limitations and known risks

- **Experimental**: SYCL support is not a stable backend. It requires manual
  configuration and a SYCL-enabled llama.cpp build.
- **No Chat or API support**: only `run` and `execute` CLI commands accept
  `--backend SYCL`.
- **No automatic fallback**: a SYCL request that cannot be satisfied fails
  explicitly; it is never silently replaced by CPU or Vulkan.
- **Hardcoded device**: `SyclLlamaRunner` uses `SYCL0` directly; multi-device
  or device selection is not supported.
- **Hardcoded runtime version**: the offload evidence parser uses a fixed
  runtime version string (`0.7.0-dev (build 11776, commit ead9f3205)`).
- **No user documentation of env vars in help text**: `--backend` help mentions
  only CPU and Vulkan.
- **Other Intel GPUs**: only Intel Arc Pro B70 has been validated. Other
  devices may work but are not guaranteed.

## I. Evidence of validation

Validated on Intel Arc Pro B70 (SYCL0, 32 GiB VRAM) with TinyLlama 1.1B
Q4_K_M:

- `run` path: exit code 0, 23/23 layers offloaded to GPU, 27.4 t/s prompt,
  375.0 t/s generation.
- `execute` path: exit code 0, GPU placement confirmed 23/23 layers,
  29.2 t/s prompt, 288.3 t/s generation.
- No fallback to CPU or Vulkan observed.
- Full diagnostic trail: `A2.6.5.7.5`.