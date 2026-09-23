# Application Use Case: Evaluate Model Compatibility — Specification (Correction Pass)

Status: **Application Use Case specification — documentation only.**
Ratified boundaries: **B9.8 / B9.12 / B9.13 / B9.14 / B9.15 — unchanged.**
This document adapts the Use Case to those decisions; it reopens none of them.
It modifies no code, no tests, no contracts, no commits.

Terminology and semantics are inherited from B9.8, B9.11–B9.15.
Where this document conflicts with B9.11–B9.15, B9.11–B9.15 prevail.

Real signatures (normative):

```text
compose_and_integrate() -> IntegrationResult            (B9.14, app/application_wiring.py)
compose_evaluation(                                     (B9.15, app/evaluation_composition.py)
    result: IntegrationResult,      # mandatory, verbatim
    registry: KnowledgeRegistry,    # mandatory, explicit, no default
    spec: ModelSpec,                # caller-supplied
    artifact: ArtifactSpec,         # caller-supplied
    capability: RuntimeCapability,  # caller-supplied (TYPE_CHECKING hint)
    backend: str | None = None,
    required_capabilities: tuple[str, ...] = (),
    scope: KnowledgeScope | None = None,
) -> StrictEvaluation
resolve_runtime(registry, capability) -> KnowledgeSubject   (B9.8, exact canonical_id membership)
```

---

## 1. Purpose

The Alpha Application Use Case **Evaluate Model Compatibility** coordinates,
for one requested model, the production of an **Application Result** stating
whether the model/artifact is compatible with a selected runtime, or why the
Use Case blocked before a compatibility evaluation could be produced.

Application **coordinates**; it does not translate (B9.12), integrate (B9.13),
project knowledge (B9.7), resolve identity beyond delegating to
`resolve_runtime()` (B9.8), reconcile (B9.15), evaluate (B9.3/B9.9), decide
(B9.10), or execute.

---

## 2. Flow model — convergence of independent branches toward B9.15

B9.14 is **not** a linear stage obligatorily prior to model/artifact
resolution, and model/artifact resolution is **not** obligatorily prior to
B9.14. Both are **independent branches with respect to their current
architectural dependencies** whose outputs converge when Application holds the
inputs required to invoke B9.15.

```text
Application
  │
  ├── Runtime selection
  │        ↓
  │   Capability acquisition (Infrastructure: detect/build RuntimeCapability)
  │        ↓
  │   available?
  │      ├── NO → Application blocking outcome (no B9.15 invocation, §4)
  │      └── YES → continue toward convergence
  │
  ├── Model / Artifact resolution (§5)
  │        (model_id → ModelSpec; artifact criteria → ArtifactSpec
  │         via explicit selection; no heuristics)
  │
  └── B9.14 compose_and_integrate()
           ↓
      IntegrationResult {entries, unmapped, trace}

Model/artifact + capability + IntegrationResult (+ registry/context)
                    ↓
          B9.15 compose_evaluation(result=IntegrationResult, ...)
                    ↓
          Application Result (§7)
```

Rules:

- No statement here requires model/artifact resolution before B9.14, or B9.14
  before model/artifact resolution.
- "Independent branches" means **architectural dependency independence only**.
  It prescribes no parallelism, concurrency, threads, async, ordering, or
  optimization. Any invocation order satisfying the input dependencies is
  conformant.
- The **mandatory convergence point** is immediately before B9.15: Application
  may invoke `compose_evaluation()` only when it holds all of: the selected
  runtime identity, an available capability (per Application policy, §4), the
  resolved `ModelSpec` / `ArtifactSpec`, a valid `IntegrationResult`, and the
  `KnowledgeRegistry`/context inputs B9.15 requires.
- `IntegrationResult` must be available before `compose_evaluation()` because
  it is a **mandatory parameter** of its current contract (`result`). B9.15
  cannot be invoked without a valid `IntegrationResult` (§6).

---

## 3. Semantics of `available=False` — Domain vs Application

### 3.1 Domain / B9.15: `available=False` does NOT block

For `RuntimeCapability.available=False`:

- it is **not** a blocking condition of B9.15;
- it does **not** modify `compose_evaluation()`;
- it does **not** modify `resolve_runtime()`;
- it must **not** become a domain rule;
- B9.15 **may receive** a capability with `available=False` and still evaluate.

Evidence: `app/evaluation_composition.py` treats `capability.available` as
contextual information only, and the existing test
`test_unavailable_capability_does_not_block` passes a capability with
`available=False` through `compose_evaluation()` and obtains a
`StrictEvaluation`. `resolve_runtime()` inspects only `name` /
`compatibility_names` by exact canonical-id membership; it never reads
`available`. B9.15 therefore has **no concept** of an "Application blocking
policy" and **requires no `available=True`**.

### 3.2 Application Use Case (Alpha): `available=False` blocks by policy

For **this** Use Case, Application applies its own flow policy:

```text
if capability.available is False:
    Application stops before B9.15
```

This is an **Application flow policy**, not a **Domain evaluation rule**.

Rationale (neutral, normative for this Use Case):

> El Use Case requiere una capability que represente un runtime disponible para
> continuar con la evaluación de compatibilidad. La ausencia de disponibilidad
> se trata como un resultado de flujo de Application y no como una condición de
> evaluación impuesta por B9.15.


---

## 4. Cut-off point (normative)

```text
Capability acquisition
        ↓
available == False
        ↓
Application blocking outcome (blocking_outcome set, evaluation absent,
capability retained for audit)
        ↓
No B9.15 invocation
```

```text
available == True
        ↓
continue
        ↓
resolve model/artifact
+
obtain IntegrationResult (B9.14 branch)
        ↓
B9.15 compose_evaluation(...)   ← convergence
```

- The decision **not to invoke B9.15 when `available=False` belongs exclusively
  to the Application Use Case.**
- No new domain exception is created for this cut-off; no logic is added to
  B9.15; no Application rule leaks into B9.15, `resolve_runtime()`, or
  Knowledge semantics.

---

## 5. Preconditions, inputs, and blocking outcomes

### 5.1 Inputs necessary to continue to B9.15

To invoke `compose_evaluation()`, Application must hold: selected runtime
identity usable by `resolve_runtime()`; acquired `RuntimeCapability`;
capability satisfying the Application availability policy (`available is True`,
else §4 blocking path); `model_id` (from `ModelSpec.id or ModelSpec.name`);
resolved `ModelSpec` (caller-supplied `spec`); artifact criteria and resolved
`ArtifactSpec` (caller-supplied `artifact`; exact explicit selection — zero
matches and ambiguity are errors, never heuristics); valid `IntegrationResult`
from `compose_and_integrate()` (mandatory `result`); `KnowledgeRegistry`
(mandatory `registry`, explicit, no default) plus caller-supplied
evaluation-time values (`backend`, `required_capabilities`, `scope`).

### 5.2 Application blocking outcomes (no new enums)

When any required input cannot be built, Application produces a blocking
outcome instead of invoking B9.15 (or instead of completing it, for B9.14
failure): runtime not available (`capability.available is False`, §4 path);
model not identifiable; artifact not resolvable (zero matches); artifact
ambiguous (multiple matches, explicit selector required); B9.14 failure (no
valid `IntegrationResult`; Class-B defects propagate per B9.14 — Application
records the block without reclassifying, retrying, or substituting).
No error codes or enums are invented; where none exist the outcome
is carried descriptively in `blocking_outcome`.

Scope rule (Alternative A — ratified): `blocked` covers exclusively
pre-B9.15 input-construction failures under Application responsibility
(capability unavailable per Application policy, `ModelArtifactResolutionError`,
B9.14 exception, B9.14 non-`IntegrationResult`). Once B9.15 has been invoked
with valid inputs, the Use Case is past convergence:

```text
B9.15 success → Application Result evaluated
B9.15 failure → exception propagates unchanged to the caller
```

Errors raised during B9.15 execution — including its contractual
`resolve_runtime()` identity `ValueError`s (zero/multiple exact matches),
contract violations, and any other exception forming part of its contract —
belong to B9.15 and propagate without transformation. Application never
converts a post-convergence B9.15 failure into `blocked`; `blocked` never
represents a post-convergence B9.15 outcome. Pre-convergence
domain/boundary `ValueError`s raised while Application builds its own inputs
(e.g. `ModelArtifactResolutionError` causes) are transported into the
Application Result, never redefined.

---

## 6. IntegrationResult contract (preserved, explicit)

```text
compose_and_integrate()
        ↓
IntegrationResult {entries, unmapped, trace}
        ↓
compose_evaluation(result=IntegrationResult, ...)
```

Application shall: retain the `IntegrationResult` from `compose_and_integrate()`;
pass it to B9.15 as the mandatory `result` argument; transmit it **verbatim**
(never transformed, wrapped, serialized, reclassified, or reinterpreted); never
read `entries`, `unmapped`, or `trace` as availability; never use
`IntegrationResult` as a substitute for `RuntimeCapability` (presence/absence
in `entries`/`unmapped` is contextual evidence only and does not block B9.15
per its ratified semantics). B9.15 cannot be invoked without a valid
`IntegrationResult` (`type(result) is not IntegrationResult` → `ValueError`).

---

## 7. Application Result — `EvaluateModelCompatibilityResult` (preserved)

Contract (unchanged; not redesigned):

```text
model_id
artifact
runtime
capability
evaluation
integration
status
blocking_outcome
```

Semantics: `evaluation` holds the `StrictEvaluation` / `CompatibilityResult`
from B9.15 only when B9.15 was invoked and returned; it is **absent** whenever
Application blocked before B9.15 (§4, §5.2). `blocking_outcome` is the
**Application flow result** (which input was missing / which branch blocked) —
never a Knowledge state, never an Evaluation status. `capability` is retained
even when `available=False` for inspection/audit. `integration` carries the
`IntegrationResult` when obtained (verbatim); absent only if the B9.14 branch
itself blocked. `model_id` / `artifact` / `runtime` echo resolved inputs when
available; absent inputs stay absent (no fabrication, no sentinels promoted to
facts). `status` summarizes the Use Case outcome at Application level
(evaluated vs blocked); it creates **no new Evaluation states** and never
encodes `available=False` as a compatibility verdict.

---

## 8. Separation of responsibilities (normative)

```text
Presentation
    ↓
Application Use Case (THIS DOCUMENT: coordinates, decides Use Case flow,
    transports technical results into the Application Result,
    applies its own Use Case policies)
    ↓
B9.14 / B9.15 / Domain (unchanged semantics; know no "Application blocking policy")
    ↓
Infrastructure (acquires/detects capability; executes external effects
    when applicable)
```

Application coordinates branches, decides Use Case flow (incl. the §4
availability cut-off), transforms technical results into the Application
Result, and owns only its own Use Case policies. B9.15 keeps current semantics
(verbatim `result`, explicit `registry`, caller-supplied values,
target-specific reconciliation via `resolve_runtime()` with only zero/multiple
matches blocking; `available`, `entries`/`unmapped` presence, and empty
`runtime_knowledge` non-blocking) and receives no new rules. Infrastructure
acquires/detects `RuntimeCapability` and performs external effects;
availability detection stays there, availability **policy** stays in
Application (§4).

---

## 9. Decisions explicitly NOT reopened

B9.8 (adapter, exact matching, N-1..N-4), B9.12 (boundary translation), B9.13
(integration, `IntegrationResult` shape, UNMAPPED policy), B9.14 (wiring,
stop-line, `compose_and_integrate()`), B9.15 (composition, reconciliation
ownership, `compose_evaluation()` contract), Knowledge semantics, tri-state
projection, `RuntimeCapability` semantics, `resolve_runtime()`, exact matching,
and the Detection / Observation / Integration / Knowledge / Evaluation
distinction. This correction pass adapts the Use Case to them.

---

## 10. Self-check (verification)

1. B9.14 is an independent branch, not a mandatory step before model/artifact
   resolution — §2. 2. Branches converge before B9.15 — §2. 3. `IntegrationResult`
   mandatory for B9.15 — §2, §5.1, §6. 4. Passed verbatim — §6.
2. `available=False` does not block B9.15 by domain semantics — §3.1 + test
   citation. 6. Application blocks before B9.15 for this Use Case — §3.2, §4.
3. That decision is Application policy — §3.2, §4, §8. 8. No conversion of
   `available=False` into Knowledge/Evaluation states — §3.2, §7. 9. Application
   Result permits absent `evaluation` with a blocking outcome — §7. 10. Compatible
   with B9.14/B9.15 without modifying their contracts — header, §8, §9 and
   verbatim signatures. B9.15 failures propagate unchanged (§5.2 scope rule);
   `blocked` never represents a post-convergence B9.15 outcome.

Prohibited readings: B9.15 never "requires" `available=True`;
`available=False` never means the runtime "does not exist"; never reinterpret
`available=False` as `UNSUPPORTED`, `ABSENT`, `UNKNOWN`, or any Knowledge /
Evaluation state. Availability stays a property of the `RuntimeCapability`
value object acquired by Infrastructure; Knowledge absence is expressed only
through projections (`UNKNOWN` downstream), Evaluation states only through
`CompatibilityResult` / `StrictEvaluation`.
