# CastleArq Core — Inference Execution Observability Decision (v1 RATIFIED)

> **Nature: RATIFIED DECISION v1 (user-ratified).**
>
> **Decision content.** This document records the ratified v1 decision:
> how execution information is exposed through the API while preserving the
> separation between runtime internals and the public contract. The decision
> itself modified no code, tests, dependencies, configuration, or roadmap;
> allocated no roadmap identifier (no B9.x claimed); and authorized no
> implementation. The ratified contract is unchanged by the later
> reconciliation in section 15.
>
> The JSON contract in section 4 is the **ratified v1 contract** for
> successful `/v1/run` responses. It may be cited as the ratified v1
> decision.
>
> Baseline inspected:
>
> ```text
> Branch: main
> HEAD:   bcb15ef9abe4adc1983a54d48055b48980798f02
> ```

---

## 1. Status

```text
STATUS:          RATIFIED v1 (user decision)
NUMBER:          NONE — NOT ALLOCATED (no B9.x claimed)
IMPLEMENTATION:  NOT AUTHORIZED BY THIS DOCUMENT (see section 15 for the
                 recorded implementation status of the ratified contract)
```

Sections 4–9 record ratified decisions (marked `RATIFIED`). Verified
facts are marked `FACT`. Only explicitly flagged items remain pending.

---

## 2. Confirmed evidence (FACT)

- `FACT — castlearq/execution.py: ExecutionDiagnostics` is a frozen
  dataclass with measured subprocess facts: `started_at`, `finished_at`,
  `elapsed_seconds`, `stdout_bytes`, `stderr_bytes`, `exit_code`,
  `timed_out`, `terminated_normally`.
- `FACT — castlearq/execution.py: RuntimeMetrics` is a frozen dataclass
  with optional fields (`prompt_tokens`, `generated_tokens`,
  `prompt_tokens_per_second`, `generation_tokens_per_second`,
  `load_time_seconds`, `total_time_seconds`, all defaulting to `None`)
  plus `source: RuntimeMetricSource` (`llama_human_output` |
  `unavailable`). Validators reject negative/non-finite/wrongly-typed
  values; `None` means absent.
- `FACT — castlearq/runtime_metrics.py: parse_llama_human_output(text)`
  extracts only explicitly reported prompt/generation throughput from the
  last valid `[ Prompt: ... | Generation: ... ]` block; returns `None`
  when no valid block exists. It does not infer token counts or timings.
- `FACT — castlearq/execution.py: ExecutionResult` carries `success`,
  `exit_code`, `stdout`, `stderr`, `error`, `warnings`,
  `diagnostics: ExecutionDiagnostics | None`, and
  `runtime_metrics: RuntimeMetrics | None`.
- `FACT — castlearq/execute_model.py` preserves both `diagnostics` and
  `runtime_metrics` when merging selection/compatibility warnings into the
  returned `ExecutionResult`.
- `FACT — castlearq/api.py: RunResponseDTO` exposes `model_id`,
  `output`, `exit_code`, `warnings` plus the allow-list projections
  `execution` and `runtime_metrics` (each an object or `null`).
  `run_response_from_execution(model_id, result)` projects
  `result.diagnostics` via `_execution_projection` (fields:
  `elapsed_seconds`, `stdout_bytes`, `stderr_bytes`, `timed_out`,
  `terminated_normally`) and `result.runtime_metrics` via
  `_runtime_metrics_projection` (fields: `prompt_tokens`,
  `generated_tokens`, `prompt_tokens_per_second`,
  `generation_tokens_per_second`, `load_time_seconds`,
  `total_time_seconds`, `source`); each projection is `object | None`
  and never invents zeros. Internal fields (`started_at`,
  `finished_at`, duplicated `exit_code`, `requested_backend`,
  `requested_device_argument`) are excluded from the public projection.
- `FACT — B9.51` admission/rejection bodies expose only
  `admission.status`/`admission.verdict`; checks, evidence, paths, and
  exception details are deliberately withheld. The 500 handler states
  "never leak details to the client".
- `FACT — B9.46.28 (Runtime Execution Evidence Production Contract)`:
  `exit_code == 0` proves process completion with code zero, not by itself
  artifact load or inference; no structured signal currently proves
  llama.cpp loaded the GGUF or ran a specific inference with it.

---

## 3. Decision scope (v1)

Document how to expose useful execution information via the API while
preserving the runtime/public-contract separation.

Out of scope: changing runner parsing, adding new runtime signals,
changing admission policy, `run_lock` semantics, chat turns,
catalog/artifact DTOs, and any implementation.

## 4. Ratified public fields and JSON contract v1 (RATIFIED)

### 4.1 Design principles (RATIFIED)

1. Additive-only: existing `model_id`, `output`, `exit_code`, `warnings`
   keep names, types, and positions.
2. Projection, not passthrough: the API maps a fixed allow-list from
   `ExecutionDiagnostics`/`RuntimeMetrics`; it never serializes the
   dataclasses blindly and never forwards runtime internals.
3. Absence is explicit (`null` + source), never zero-filled (see section 5).
4. No local paths, argv, environment, or process handles cross the
   boundary (see section 7).

### 4.2 Ratified wire shape v1 (RATIFIED — successful `/v1/run` only)

```json
{
  "model_id": "string",
  "output": "string",
  "exit_code": 0,
  "warnings": ["string"],
  "execution": {
    "elapsed_seconds": 12.34,
    "stdout_bytes": 1234,
    "stderr_bytes": 56,
    "timed_out": false,
    "terminated_normally": true
  },
  "runtime_metrics": {
    "prompt_tokens": null,
    "generated_tokens": null,
    "prompt_tokens_per_second": 40.5,
    "generation_tokens_per_second": 18.2,
    "load_time_seconds": null,
    "total_time_seconds": null,
    "source": "llama_human_output"
  }
}
```

Notes:

- RATIFIED: `execution.*` derives from `ExecutionDiagnostics`, excluding
  `started_at`/`finished_at` wall-clock timestamps, the duplicated
  `exit_code`, and `requested_backend` / `requested_device_argument`
  (never exposed publicly). Rationale: elapsed time, byte sizes, and
  termination flags answer "how did it behave?" without pinning absolute
  host clocks in the public contract. `started_at`/`finished_at` are
  omitted from v1 (see ratified decision R3 in section 13).
- RATIFIED: `runtime_metrics.*` mirrors `RuntimeMetrics` 1:1, including
  `source`. Unknown/unparsed values are `null` (see section 5).
- RATIFIED: key names are `execution` and `runtime_metrics`. Both keys are
  always present on successful `/v1/run` responses; each holds either an
  object or `null` per section 5. Field order is illustrative; JSON object
  order is not part of the contract.
- Alternative shape considered and rejected: flattening
  `elapsed_seconds` at top level — rejected because it risks collisions
  with future top-level keys and weakens the runtime-vs-contract
  separation.

---

## 5. Absent metrics and provenance (RATIFIED)

1. RATIFIED: `runtime_metrics` is `null` when
   `ExecutionResult.runtime_metrics` is `None`. Absence is always
   distinguishable from zero: never emit invented zeros.
2. RATIFIED: when a `RuntimeMetrics` object exists, every field it leaves
   as `None` serializes as JSON `null`. Clients must treat `null` as "not
   reported by the runtime", never as `0` or `0.0`.
3. RATIFIED: `source` is preserved as the explicit provenance indicator
   whenever the `runtime_metrics` object is present (values
   `"llama_human_output"` | `"unavailable"`). It is the only provenance
   claim. `"llama_human_output"` asserts only that throughput numbers were
   parsed from the runtime human-readable output block — not that token
   counts, timings, backend, or offload are known.
4. RATIFIED: `execution` is `null` when `ExecutionResult.diagnostics` is
   `None` (e.g. preparation failures where nothing launched). No
   elapsed/byte/termination values are synthesized.
5. RATIFIED: no fallback inference — a missing metric is never computed
   from `elapsed_seconds`, `stdout_bytes`, output length, or any
   heuristic.

---

## 6. Backward compatibility (RATIFIED)

- RATIFIED: the new fields are emitted additively on successful `/v1/run`
  responses. Existing clients parsing `model_id`, `output`, `exit_code`,
  `warnings` are unaffected: those keys are unchanged, and
  unknown-field-tolerant JSON parsers ignore the two new keys.
- RATIFIED: request shape (`RunRequestDTO`) is unchanged; no new required
  input.
- RATIFIED: error/status mapping (400/403/404/409/422/500/503 per
  B9.51/B9.52) is unchanged. This decision covers only the 200 success
  body.
- RATIFIED: strict clients that reject unknown JSON keys may need
  adjustments to tolerate `execution` and `runtime_metrics`. No
  query-param/header/version gate is introduced in v1.

## 7. Security: what must never cross the boundary (RATIFIED)

Allow-list only. The following are excluded by construction:

- Local filesystem paths (artifact path, executable path, store root,
  manifest paths), including inside error or inspection strings.
- Process argv, environment variables, working directory, PIDs/handles.
- Raw exception messages, tracebacks, or compatibility-check internals
  (checks, expected/observed, evidence blobs) — consistent with
  `_admission_body()` and the 500 handler.
- Prompt echo beyond the existing `output` field; no new field carries
  the input prompt.

Serialization must use an explicit allow-list projection (named fields), never
`dataclasses.asdict(result)` or equivalent, so future internal fields do
not leak by default. Omitting wall-clock fields (4.2) further reduces
host-clock fingerprinting surface.

---

## 8. Acceptance tests (RATIFIED — implemented and passing; provisional file
`tests/test_run_observability_contract.py`)

All tests construct `ExecutionResult` directly (fake runner); no real
inference, no subprocess, no network:

1. Metrics present: populated `diagnostics` plus
   `RuntimeMetrics(source=LLAMA_HUMAN_OUTPUT, ...)` projects so that
   `execution` equals diagnostics values, reported metrics pass through,
   unreported metrics are `null`, `source` is `"llama_human_output"`,
   and the four existing keys are unchanged.
2. Metrics absent: `runtime_metrics=None` (parser returned `None`) —
   wire form is `runtime_metrics: null` (never zeros); no `0`/`0.0`
   appears for any metric; `execution` still reflects diagnostics when
   present.
3. Execution failure: `success=False` with `ExecutionErrorInfo` (e.g.
   `TIMEOUT` or `PROCESS_FAILED`) and diagnostics showing
   `timed_out=True` or non-zero `exit_code` — failure keeps its existing
   non-200 status/body (unchanged); termination flags are preserved
   truthfully rather than normalized.

4. Leak regression: fixed-string assertions that the serialized 200
   body contains no store-root, absolute-path, `argv`, `env`, or
   `traceback` patterns from crafted fixtures; plus a structural
   assertion that serialization uses the allow-list projector (a
   sentinel attribute on the fixture must not appear on the wire).
5. Compatibility: golden test showing the old four keys byte-identical
   with only the two new keys added.

RATIFIED: tests live in a dedicated contract file with the
provisional name `tests/test_run_observability_contract.py`. The tests pin
the section 5 `null` rules. All tests construct `ExecutionResult`
explicitly with a fake runner: no real inference, no real subprocesses,
no network, no new dependencies.

---

## 9. Limitations: what performance metrics cannot prove (RATIFIED)

RATIFIED: the exposed metrics do not prove which backend was used, how
many layers were offloaded to the GPU, or that hardware was effectively
used. No backend/offload fields are added without explicit evidence.

- Which backend was used (CPU vs. CUDA vs. other) — `RuntimeMetrics`
  has no backend field, and throughput is not a backend identifier.
- How many layers were offloaded to GPU — layer-offload counts are not
  captured in `ExecutionDiagnostics` or `RuntimeMetrics`.
- That the artifact was loaded or that a specific inference consumed it
  (per B9.46.28: only invocation/process facts exist; load/execution
  signals are absent).
- Comparability across runs or hosts: reported throughputs are
  runtime-self-reported, workload- and host-dependent, with no error
  bounds.

Consumer documentation must state these limits alongside the new fields
so dashboards are not misread as backend or offload evidence.

---

## 10. Alternatives considered

| Alternative | Description | Verdict (v1) |
|---|---|---|
| A. Additive objects | Section 4.2 | Ratified (v1). |
| B. Expose raw dataclasses | Serialize internals directly | Rejected — couples contract to internals. |
| C. Opt-in / versioned | Param, header, or v2 | Not adopted in v1 — additive emit ratified. |
| D. Full envelope | Backend, offload, loaded signals | Rejected — signals do not exist (B9.46.28). |
| E. Do nothing | Keep 4-key body | Rejected — safe facts stay unusable. |

---

## 11. Risks

- Misreading metrics as backend/GPU proof — mitigated by section 9
  warnings; no backend/offload fields without signals.
- Zero/absent conflation — mitigated by `null` + `source` rules and
  acceptance test case 2.
- Strict-client breakage — mitigated by additive-only change; strict
  clients are documented as possibly needing adjustments (section 6).
- Leak by future field — mitigated by allow-list projection (section 7).
- Contract drift — section 4 is now the ratified v1 contract; any change
  requires a new explicit decision.
- Timestamp/clock exposure — mitigated by the ratified omission of
  wall-clock fields in v1.

---

## 12. Status of candidate files (implemented in HEAD bcb15ef9)

- `castlearq/api.py` — `RunResponseDTO` (+ `to_dict()`) and
  `run_response_from_execution()` extended with the allow-list
  projection `execution` + `runtime_metrics` (implemented, not future).
- Dedicated contract test file
  `tests/test_run_observability_contract.py` — tests from section 8
  implemented and passing (7/7 contract tests).
- Docs: this document now records the two new keys, `null`
  semantics, and section 9 limits (this reconciliation).
- Explicitly not in scope for this reconciliation: `castlearq/execution.py`,
  `castlearq/runtime_metrics.py`, `castlearq/runner.py`,
  `castlearq/execute_model.py` — no parsing or domain changes decided
  here.

---

## 13. Ratification record and remaining scope

RATIFIED v1 (user decision) — recorded decisions:

- R1. Contract JSON: `execution` + `runtime_metrics` added to successful
  `/v1/run` responses; `model_id`, `output`, `exit_code`, `warnings`
  unchanged (section 4).
- R2. Absent data: `execution: null` without diagnostics;
  `runtime_metrics: null` without a metrics report; `null` (never zeros)
  for unreported metrics inside a present object; `source` preserved as
  provenance (section 5).
- R3. Temporal fields: `started_at`/`finished_at` omitted from v1;
  `elapsed_seconds` kept inside `execution` (section 4.2).
- R4. Compatibility: additive emit on successful `/v1/run`; requests,
  status codes, and error contracts unchanged; strict clients may need
  adjustments (section 6).
- R5. Tests: dedicated file, provisional
  `tests/test_run_observability_contract.py`, with explicit
  `ExecutionResult` fixtures and a fake runner — no real inference,
  subprocesses, network, or new dependencies (section 8). Implemented and
  passing (7/7 contract tests); no separate implementation authorization
  needed for this ratification record.
- R6. Scope: chat turns excluded from v1.
- R7. Security: explicit allow-list projection; no `asdict`; no paths,
  argv, env, PIDs, internal exceptions, or sensitive operational details
  (section 7).
- R8. Interpretation limits: no backend/offload proof; no backend/offload
  fields without explicit evidence (section 9).

No B9.x identifier is assigned and no roadmap incorporation is claimed.
Implementation is not authorized by this document.

Genuinely still pending (not covered by this ratification): whether a
future revision adds `started_at`/`finished_at`, introduces
opt-in/versioned delivery, extends any envelope to chat turns, or changes
the provisional test filename at implementation time.

---

## 14. Checks performed for this ratification record

- Read `castlearq/execution.py`, `castlearq/runtime_metrics.py`,
  `castlearq/execute_model.py`, and `castlearq/api.py` as cited in
  section 2; reviewed `docs/B9.51-*`, `docs/B9.46-*`, and
  `docs/run-boundary-architectural-decision.md` conventions.
- Placed this file as an unnumbered decision; no roadmap ID claimed.
---

## 15. Reconciliation record — implementation status of the ratified v1 contract

> **Scope of this section.** This section records an observed fact about the
> repository. It **does not** change the ratified v1 contract (sections 4–9),
> does not create or imply any authorization that was not given, and does not
> claim a roadmap identifier.

```text
RECONCILIATION DATE:   2026-10-20
STATUS:                FACT — implementation observed in the repository
CONTRACT CHANGE:       NONE (sections 4–9 unchanged)
AUTHORIZATION INVENTED: NONE
ROADMAP NUMBER:        NONE — still not allocated
```

### 15.1 Observed implementation

Commit `e8526c3` ("feat: expose inference execution observability", local,
not published) implements the ratified v1 contract:

- `castlearq/api.py` — `RunResponseDTO` gains the two additive keys
  `execution` and `runtime_metrics`; `to_dict()` emits them. Both are
  populated by explicit allow-list projections
  (`_execution_projection`, `_runtime_metrics_projection`) and never by
  serializing the dataclasses. The four ratified keys (`model_id`,
  `output`, `exit_code`, `warnings`) keep their names, types and order.
- `tests/test_run_observability_contract.py` — the acceptance tests of
  section 8, implemented as ratified (fake runner, no real inference, no
  subprocess, no network, no new dependency).
- `tests/test_api.py` — adjusted to the additive wire shape.

The `FACT` list in section 2 already described the ratified target shape.
That description is now also the observed implementation state; section 2
was not edited because its wording already matches.

### 15.2 What this section does not do

- It does not ratify anything. The v1 ratification is the user's decision
  recorded in section 13; this reconciliation neither adds to it nor
  reopens it.
- It does not claim that the implementation was authorized by this document.
  The document does not authorize implementation (section 1); the
  implementation exists independently, and the authorization record for it
  is outside the scope of this document.
- It does not extend the contract. `started_at`/`finished_at`,
  `requested_backend` and `requested_device_argument` remain excluded from
  the public projection (sections 4.2, 7, R3, R8), and the limits of
  section 9 are unchanged: the exposed metrics still do not prove a
  backend, an offload, or GPU usage.

### 15.3 Items still genuinely pending

Unchanged from section 13: whether a future revision adds
`started_at`/`finished_at`, introduces opt-in/versioned delivery, extends
any envelope to chat turns, or changes the provisional test filename.

---

## 16. Checks performed for this reconciliation record

- Read `castlearq/api.py` and `tests/test_run_observability_contract.py` and
  compared them against sections 4, 5, 7 and 8 of this document.
- Confirmed that the public projection excludes `started_at`,
  `finished_at`, `requested_backend` and `requested_device_argument`.
- Confirmed that no B9.x identifier is claimed anywhere in this document.
- Modified no code, test, configuration, dependency or roadmap file, and did
  not open the LoRA/QLoRA HADR.
