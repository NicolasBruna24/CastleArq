# CastleArq

CastleArq is a command-line tool for running local GGUF models with
[llama.cpp](https://github.com/ggml-org/llama.cpp) that checks whether a model
can run on your machine — and shows its work — before running it.

CastleArq does not replace llama.cpp and does not perform inference itself.
llama.cpp is the runtime that loads the model and generates text. CastleArq
manages model files, evaluates compatibility, applies admission and orchestrates
execution against that runtime.

> **Version note.** The published PyPI release is `0.1.0`. This README describes
> the current `main` branch, which is ahead of that release.

## What problem does it solve?

You have GGUF model files and a local llama.cpp runtime. Pointing `llama-cli` at
a model gives you either output or a failure, and nothing in between: no answer
to *why* it failed, and no way to know in advance whether it could have worked at
all on this machine, with this artifact, on this runtime.

CastleArq answers that question first, with evidence, and refuses to run what it
cannot justify running.

## How it works

```text
runtime       -> inspect the llama.cpp runtime that is actually installed
models        -> catalog of candidate models for this machine
download      -> fetch a GGUF artifact (the model file) and store it locally
compatibility -> evaluate five conditions and print the evidence
execute       -> refuse or run, according to that evaluation
```

## Why compatibility evidence matters

The compatibility evaluation checks exactly five named conditions between one
specific artifact and the detected runtime:

| Condition | Question |
|---|---|
| artifact–model identity | is this file the model that was asked for? |
| artifact format support | does the runtime accept this file format? |
| model architecture support | does the runtime know this architecture? |
| runtime artifact support | does the runtime report supporting this artifact? |
| runtime backend support | does the selected backend support this model? |

Each condition is reported with what was **Expected**, what was **Observed**, and
the **Evidence** recorded for that observation. A condition is `PASSED`,
`FAILED`, or `UNKNOWN` — and `UNKNOWN` is reported as `UNKNOWN`. It is never
silently converted into a failure.

When the evaluation does not admit the model, **admission** — the decision that
allows or refuses execution — refuses it, and the run does not happen. There is
no flag to force execution past a refusal.

The same admission policy applies to every surface that runs a model: the
`execute` command, `POST /v1/run` over HTTP, and opening a chat session.

Throughout this document:

- **model** — the logical model you want to use;
- **`MODEL_ID`** — the canonical identifier the CLI accepts;
- **artifact** — the concrete model file (GGUF) stored locally;
- **quantization** — the chosen size/precision variant of that file;
- **runtime** — the llama.cpp installation that loads and runs the model.

## Installation

```bash
pip install castlearq
```

From a checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
castlearq --version
```

A previously built wheel or sdist can also be installed, for example
`pip install dist/castlearq-0.1.0-py3-none-any.whl`. Installation needs neither
`PYTHONPATH` nor the source tree afterwards, and the package contains no models.

## Requirements

CastleArq is for **developers already working with local AI models on Linux who
have, or can obtain, llama.cpp, and who use GGUF files.** It is not a consumer
application.

You need:

- **Linux** as the exercised baseline.
- **Python 3.10 or newer.**
- **llama.cpp provided externally.** CastleArq does not install, build or vendor
  it, and does not ship models, drivers, Vulkan, CUDA or ROCm. The official
  `llama` launcher must be on your `PATH`.
- **Disk space** for model files. A single 7B Q4_K_M artifact is roughly 4.4 GiB.

The normal flow does not require `sudo` and does not modify your system.

## Runtime setup

CastleArq requires the `llama` executable; it does not install or build
llama.cpp. First check that the launcher is on your `PATH`:

```bash
command -v llama
```

Then inspect the state CastleArq can observe:

```bash
castlearq runtime
```

The output shows the runtime, launcher, resolved executable, version, build,
availability and detected capabilities.

| State | Meaning | Action |
|---|---|---|
| `AVAILABLE` | runtime usable | continue with models |
| `NOT_FOUND` | `llama` is not available | provide llama.cpp externally |
| `FOUND_UNUSABLE` | a path was found but is not usable | check path, permissions and file type |
| `PROBE_ERROR` | validation could not complete | read `reason`, check the llama.cpp install/build |
| `UNKNOWN` | not enough evidence | read `reason` and re-run the diagnostic |

`llama` is the official launcher. `llama-cli`, `llama-server` and `llama.app` do
not automatically stand in for `llama` in CastleArq 0.1.x.

## Quick start

```bash
# 1. Check the runtime CastleArq will drive
castlearq runtime

# 2. See which models are candidates for this machine
castlearq models

# 3. Fetch one explicitly (multi-GB download)
castlearq download qwen2.5-coder-7b-instruct

# 4. Check it can run here, and see the evidence
castlearq compatibility qwen2.5-coder-7b-instruct

# 5. Run a prompt
castlearq execute qwen2.5-coder-7b-instruct "Reply with exactly: OK"
```

`compatibility` is a normal step in this flow, not optional troubleshooting: it
is the same evaluation `execute` uses to decide whether to run.

## Check compatibility before running anything

```bash
castlearq compatibility qwen2.5-coder-7b-instruct
```

This command is **read-only**: it runs no inference, starts no runtime,
downloads nothing, does not modify the model store and creates no persistent
state. It prints the verdict and, for each condition, its status, what was
expected, what was observed, and the evidence already recorded.

Abridged output (the real command prints all five conditions):

```text
Compatibility evaluation
  Model: qwen2.5-coder-7b-instruct
  Artifact: qwen2.5-coder-7b-instruct-q4_k_m.gguf (Q4_K_M)
  Runtime: llama.cpp CLI
  Verdict: INSUFFICIENT_EVIDENCE

Checks:
  artifact format support: PASSED
    Expected: 'gguf'
    Observed: 'gguf'
    Evidence (observed): artifact.format = 'gguf'
  runtime artifact support: UNKNOWN
    Evidence (observed): runtime.supports_artifact = None
```

Exit codes: `0` when the evaluation admits execution, `1` when it does not,
`2` on incorrect usage.

The criterion is the same one `execute` uses: this command reports, it does not
change policy.

### `INSUFFICIENT_EVIDENCE` does not mean incompatible

`INSUFFICIENT_EVIDENCE` is the overall verdict when not every condition has
sufficient evidence. It does not assert that the model is incompatible; it
asserts that CastleArq does not know enough to assert either way.

The actual behaviour, which `compatibility` does not alter:

- if any condition is `FAILED`, a failure is demonstrated and execution is
  refused;
- if the only conditions without evidence are the ones that do not depend on a
  prior evaluation, CastleArq treats them as non-blocking and admits execution.
  That is why you can see `Verdict: INSUFFICIENT_EVIDENCE` together with exit
  code `0`: the verdict is honest about what it does not know, and the admission
  is equally honest about what it does.

`UNKNOWN` never becomes `FAILED`, and `INSUFFICIENT_EVIDENCE` never
automatically becomes "not compatible". To know whether a given model is
blocked, the admission result decides — not the name of the verdict.

## First execution

```bash
castlearq execute qwen2.5-coder-7b-instruct "Reply with exactly: OK"
```

A successful prompt prints the model's response on stdout. The runtime may print
loading and generation messages, and CastleArq may print warnings on stderr. A
warning does not by itself mean the execution failed.

- exit code `0`: success;
- exit code `1`: operational failure;
- exit code `2`: incorrect arguments or usage.

Exact output varies with the model and prompt. A successful result includes
generated output and code `0`.

### `execute` versus `run`

The legacy `run` interface also exists and reaches the same llama.cpp runtime:

```bash
castlearq run qwen2.5-coder-7b-instruct --prompt "Reply with exactly: OK"
```

They are not equivalent in policy:

| | `execute` | `run` |
|---|---|---|
| Prompt | positional | `--prompt` |
| Strict evaluation before running | yes | no |
| Admission | yes | no |
| Runtime | llama.cpp | llama.cpp |

`execute` evaluates compatibility strictly and refuses to run when admission
denies it, showing the conditions, reasons and evidence. `run` is the legacy
interface: it reaches the same runtime through the legacy preparation path and
does **not** apply strict evaluation admission.

Use `execute`. `run` is kept for compatibility.


### A real run

The transcript below was captured from a real execution on Linux with
llama.cpp 0.4.0-dev and a real 4.4 GiB Q4_K_M artifact, using the commands
above. Nothing in it is hand-written.

`castlearq compatibility qwen2.5-coder-7b-instruct`:

```text
Compatibility evaluation
  Model: qwen2.5-coder-7b-instruct
  Artifact: qwen2.5-coder-7b-instruct-q4_k_m.gguf (Q4_K_M)
  Runtime: llama.cpp CLI
  Verdict: INSUFFICIENT_EVIDENCE

Checks:
  artifact-model identity: PASSED
    Expected: 'qwen2.5-coder-7b-instruct'
    Observed: 'qwen2.5-coder-7b-instruct'
    Evidence (observed): model.identity.model_id = 'qwen2.5-coder-7b-instruct'
    Evidence (observed): artifact.identifier = 'qwen2.5-coder-7b-instruct'
  artifact format support: PASSED
    Expected: 'gguf'
    Observed: 'gguf'
    Evidence (observed): artifact.format = 'gguf'
    Evidence (observed): runtime.supported_formats = 'gguf'
    Evidence (observed): runtime.unsupported_formats = None
  model architecture support: PASSED
    Expected: 'qwen2'
    Observed: 'qwen2'
    Evidence (observed): model.architecture = 'qwen2'
    Evidence (observed): runtime.architecture_knowledge = 'explicit lists'
  runtime artifact support: UNKNOWN
    Evidence (observed): runtime.name = 'llama.cpp'
    Evidence (observed): runtime.supports_artifact = None
  runtime backend support: UNKNOWN
    Evidence (observed): context.backend = None
    Evidence (observed): runtime.supported_backends = 'cpu, cuda, hip'
    Evidence (observed): runtime.unsupported_backends = None
```

Read it honestly: three conditions passed with evidence; two are `UNKNOWN`
because the runtime reports nothing for them. CastleArq reports
`INSUFFICIENT_EVIDENCE` rather than inventing a pass, and admission still allows
the run because those two conditions are not blocking.

`castlearq execute qwen2.5-coder-7b-instruct "Reply with exactly: CASTLEARQ_OK"`
(llama.cpp's own loading banner elided, indicated below):

```text
Warning: Model memory is an estimate.

[... llama.cpp loading banner and runtime command help elided ...]

> Reply with exactly: CASTLEARQ_OK
CASTLEARQ_OK

[ Prompt: 258.1 t/s | Generation: 38.0 t/s ]
```

The command exited `0` and the model produced exactly the requested token
sequence. The `Warning:` line comes from CastleArq's own memory estimation,
which is separate from the five-condition verdict — see
[What the verdict does not cover](#what-the-verdict-does-not-cover).


## Model management

The basic cycle is:

```text
models -> choose MODEL_ID -> download -> list -> execute
```

`models` shows the catalog, `download` acquires the artifact explicitly, `list`
inspects local storage and `execute` runs a prompt. Repeating `execute` does not
download the model again.

`models` prints, per candidate, the recommended quantization, an estimated
memory figure, the selected runtime and backend, the reason, and any warning.
Those recommendations come from CastleArq's memory estimation and hardware
assessment, which are **not** the five-condition compatibility verdict.

To pick a specific variant:

```bash
castlearq download MODEL_ID --quantization QUANTIZATION
castlearq download MODEL_ID --filename MODEL_FILE.gguf
```

A download requires network access to the remote source, and CastleArq does not
assume a remote model stays available forever.

### Verify local artifacts

```bash
castlearq list
```

`list` shows locally stored artifacts with their model id, filename,
quantization, size and verification state. Artifacts are reused by later runs.

The model store is independent of the checkout:

```text
$XDG_DATA_HOME/castlearq/models
```

with the fallback:

```text
~/.local/share/castlearq/models
```

`~/.local/share/localai-hub/models` is legacy path compatibility only; it is not
the recommended path for new installations. You do not need to edit manifests or
move models by hand.

## How this differs from using llama.cpp directly

CastleArq **drives** llama.cpp; it does not replace it and does not perform
inference itself. llama.cpp is the runtime that loads the model and generates
text. CastleArq manages artifacts, evaluates compatibility, applies admission
and orchestrates execution against that runtime.

The difference is what happens *before* the runtime is invoked. Pointing
`llama-cli` at a model starts generation immediately. CastleArq first reports
which of five conditions it could verify, what it expected, what it observed, and
what evidence it has — and then refuses to start generation when the evaluation
does not admit the model.

CastleArq makes no claim to be better, faster, safer or more reliable than any
other tool, and makes no comparison with other local-AI runtimes. What it claims
is narrower and checkable: it evaluates those five conditions, shows the
evidence, and does not run what it cannot justify running.


## What the verdict does not cover

The compatibility verdict is evidence about **five named conditions** between one
artifact and one detected runtime. Reading it as anything broader would be a
misreading, so this is stated explicitly.

The verdict does **not** establish:

- **memory sufficiency.** It is not a RAM/VRAM capacity check. CastleArq's memory
  estimation is a separate, approximate heuristic reported separately (as a
  `Warning:` line), and it is labelled as an estimate.
- **output quality, model quality or semantic correctness** of anything generated.
- **model behaviour** — the verdict says nothing about what a model will say.
- **security or safety.** CastleArq is not a sandbox and provides no isolation
  or hardening. A model that passes admission is not thereby safe to run.
- **performance.** No speed, throughput or latency claim is made or measured.
- **absence of crashes or runtime failures.** Admission is a decision made
  before generation; the runtime may still fail afterwards, and `execute`
  reports that as an operational failure.

Admission is also not a permission system. CastleArq has no identities, roles or
accounts; the HTTP `403` status it returns for a refusal means "the evaluation
did not admit this", not "you are not authorised".

A pass therefore means: *these five conditions were checked and none of them
demonstrably failed.* It does not mean *this model will run well*.

## HTTP API

```bash
castlearq serve
```

`serve` is **not** a status-only endpoint. It starts an HTTP API and performs
**real inference**:

```text
GET    /health                       -> liveness and version (this one is read-only)
GET    /v1/models                    -> catalog
GET    /v1/artifacts                 -> local artifacts
POST   /v1/run                       -> RUNS a prompt (real inference)
POST   /v1/chat/sessions             -> opens a live chat session
POST   /v1/chat/sessions/{id}/turns  -> sends a prompt to that session
GET    /v1/chat/sessions/{id}        -> session status
DELETE /v1/chat/sessions/{id}        -> closes the session
```

The server binds loopback (`127.0.0.1`) by default and rejects non-loopback
hosts. That is a property of **network exposure**.

**Execution policy** is a separate matter, and the two should not be confused:
HTTP execution applies the **same strict evaluation admission** as `execute`.
Admission is a property of execution, not of the command or the transport. A
model that strict evaluation does not admit is **not** executed over HTTP.

| Status | Meaning |
| --- | --- |
| `200` | success (`model_id`, `output`, `exit_code`, `warnings`) |
| `400` | malformed request |
| `404` | model not in the local catalog |
| `409` | an execution is already running (global lock, no queue) |
| `403` | **admission denied** by the compatibility evaluation |
| `422` | preparation failure (invalid artifact, no executable target) |
| `500` | **evaluation error** — the evaluation failed; this is not a denial |
| `503` | runtime unavailable, or the runner failed |

A refusal returns only the admission summary:

```json
{
  "error": "execution refused by compatibility admission",
  "admission": { "status": "evaluated", "verdict": "incompatible" }
}
```

Checks, diagnostics, evidence, local paths and exception details are never
returned. For the full evaluation use `castlearq compatibility MODEL_ID`.

A `500` means the evaluation **raised** (for example an unreadable GGUF), not
that it denied: that is why no verdict is shown. Execution is refused in both
cases.

`POST /v1/chat/sessions` opens a live session, so it is subject to the same
admission and the same global lock.


## Limitations

Current, factual limitations of this release:

- **Linux is the exercised baseline.** The code inspects other platforms, but
  only Linux has been run end to end.
- **llama.cpp is an external dependency.** CastleArq does not install, build or
  vendor it. Without a working `llama` launcher, nothing can run.
- **Models are large.** A 7B Q4_K_M artifact is roughly 4.4 GiB; downloads need
  network access, time and disk.
- **The catalog currently contains 3 models.** `castlearq models` recommends from
  that small catalog, so treat it as a starting point rather than a broad index.
- **CastleArq does not perform inference itself.** It orchestrates llama.cpp.
- **Memory figures are estimates.** They are derived from parameter count and
  quantization, not measured, and are reported with a warning.
- **No quantization, scheduling, clustering or multi-GPU features.** The backend
  is selected for the detected hardware; there is no workload scheduler.
- **One execution at a time.** The HTTP surface serialises execution behind a
  single lock and answers `409` rather than queueing.
- **No auth, TLS or persistence.** `serve` is loopback-only by design; chat
  sessions live in memory only.

## Troubleshooting

### `llama` not found

```bash
command -v llama
castlearq runtime
```

If you see `NOT_FOUND`, provide llama.cpp externally and re-run
`castlearq runtime`. CastleArq will not install it for you.

### Runtime `FOUND_UNUSABLE`

CastleArq found a path it cannot use as a launcher. Check the reported path,
permissions, file type, and the runtime install/build.

### Runtime `PROBE_ERROR`

CastleArq found the launcher but could not validate its interface. Read `Reason`,
check the llama.cpp install/build and re-run the diagnostic. This does not by
itself demonstrate a universal incompatibility.

### Artifact missing

```bash
castlearq list
castlearq models
castlearq download MODEL_ID
```

### Artifact invalid or incomplete

Check `castlearq list`. Do not try to run an artifact whose state is not usable.
If it is not downloaded, use `download` again; the existing command keeps its
validation semantics and will not publish an artifact that fails its checks.

### Incompatibility

Execution can be blocked by model, artifact, memory, quantization or
capabilities. Check `castlearq models`, `castlearq list` and `castlearq runtime`
before choosing a different artifact or prompt.

### Backend unavailable

```bash
castlearq runtime
```

Do not assume a backend advertised by the hardware is available in the runtime.
Use a backend compatible with what was detected.

### Admission denied

CastleArq blocked execution according to the current evaluation. The output
includes the full evaluation that produced the block: the verdict, each condition
with its status, what was expected, what was observed, and the evidence. There
is no instruction to force execution.

```bash
castlearq compatibility MODEL_ID
```

shows that same evaluation without running anything, and is the recommended way
to understand the reason before trying again.

A `UNKNOWN` condition is not a failure: it means there is not enough evidence,
and it is not treated as an incompatibility.

### Compatibility evaluation error

If the evaluation could not complete, CastleArq says so explicitly:

```text
Compatibility evaluation error: GGUFReadError: ...
```

This is **not** a policy denial: it means the evaluation **failed**. The
reported cause (for example a corrupt or unreadable GGUF) is the real problem,
and execution remains blocked. Check the artifact with `castlearq list` and
re-download it if its state is not usable.

### Execution failure

Check the error and the execution's stderr, and compare:

```bash
castlearq runtime
castlearq list
```

A process failure does not automatically mean the runtime or the artifact is
missing.

### Download failure

Check connectivity, remote source availability, the `MODEL_ID`, the
quantization/filename selection, and re-run:

```bash
castlearq download MODEL_ID
```

### CLI usage error

```bash
castlearq --help
```

Exit code `2` indicates incorrect usage, such as missing arguments or invalid
flags.


## Command reference

| Command | What it does |
|---|---|
| `models` | Catalog with recommendations scored against the detected hardware |
| `download MODEL_ID` | Explicitly fetch a GGUF artifact |
| `list` | Locally stored artifacts and their state |
| `compatibility MODEL_ID` | Compatibility evaluation **without running anything** |
| `execute MODEL_ID "PROMPT"` | Run a prompt (recommended; strict evaluation applies) |
| `run MODEL_ID --prompt "T"` | Legacy interface; no strict evaluation |
| `chat MODEL_ID` | Interactive chat session with the model |
| `serve` | HTTP API on `127.0.0.1` that **executes models** (see above) |
| `runtime` | Resolved llama.cpp runtime state |
| `detect` | System, CPU, memory and GPU |
| `diagnose` | GPU software diagnosis (Vulkan/CUDA/ROCm) |
| `verify` | Re-checks the **GPU diagnosis**, not artifact integrity |
| `source huggingface REPO` | Inspects a remote source |
| `plan REPO FILENAME` | Inspects one specific remote artifact |

`detect`, `runtime`, `models`, `list`, `compatibility`, `source` and `plan` are
read-only: they change nothing.

`verify` checks **environment remediation** after a `diagnose`. It is not an
artifact integrity check; for that, use `list`, which shows the verification
state of each stored artifact.

## Chat

```bash
castlearq chat qwen2.5-coder-7b-instruct
```

Opens an interactive session with the model already loaded. During the session
it responds to `/regen` (regenerate), `/clear` (clear history), `/read <file>`
and `/glob <pattern>`; `/exit` or `Ctrl+C` closes it.

`chat` uses the same runtime and the same local artifact as `execute`, so a
model downloaded with `download` is reused without downloading it again. To
check compatibility before starting a conversation, run
`castlearq compatibility MODEL_ID`.

Opening a chat session starts a model, so it is subject to the same admission as
`execute`.

## Architecture

Technical architecture, contracts and decision records are in
[`docs/`](docs/), covering runtime discovery, capability, compatibility,
admission, the model store and execution. It is optional material for the user
flow above.

## Development

From a checkout, the supported mechanism is:

```bash
python3 -m app.main --help
python3 -m app.main --version
```

Tests run with pytest:

```bash
python3 -m pytest
```

Working from a checkout is not required to use the installed package.

## License

Licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE) for
the full text.

