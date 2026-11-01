# Local LoRA/QLoRA Training — Product-Scope Human Architectural Decision Record

> **Nature of this document: DRAFT Human Architectural Decision Record (HADR) for
> human review.**
>
> This document prepares a **product-scope decision** for the human maintainer.
> It does not record a ratified decision. Creating, reading, or committing this
> file does not ratify any outcome.

---

## 1. Status and authorization

```text
DOCUMENT TYPE:                  Human Architectural Decision Record (HADR)
DOCUMENT STATE:                 DRAFT — AWAITING HUMAN DECISION
SUBJECT:                        Local LoRA/QLoRA Training — Product Scope
DECISION TYPE:                  PRODUCT SCOPE ONLY
DECISION AUTHORITY:             PROJECT OWNER (human maintainer) — PENDING
DECISION STATUS:                NOT YET RATIFIED — see section 11
ROADMAP NUMBER ALLOCATED:       NONE
NUMBER ALLOCATION RECORD:       NONE
B9.100:                         NOT CREATED / NOT AUTHORIZED
SUCCESSOR ALLOCATION:           NONE
ARCHITECTURE DECISION:          NOT MADE — NOT AUTHORIZED BY THIS DRAFT
IMPLEMENTATION AUTHORIZATION:   NONE — NOT GRANTED BY THIS DRAFT
REPOSITORY MUTATION:            NONE AUTHORIZED BY THIS DRAFT
COMMIT/PUSH:                    NOT PERFORMED
LAST DOCUMENTAL RECONCILIATION: 2026-10-16 — premises re-verified against the
                            working tree; see §1.1 and §4.2. No decision change.
```

**What this draft is:** an evidence-grounded decision-support record presenting
alternatives and a provisional recommendation, so that the human maintainer can
make and record an explicit product-scope decision.

**What this draft is not:** a ratified decision, an architecture design, a
roadmap allocation, a Number Allocation Record, or an implementation
authorization. Section 11 contains an intentionally unselected decision field.

**Revision history (documental).** The 2026-10-16 reconciliation updated §1.1
(baseline), §2.1 and §3.2–§3.4 (capability and dependency premises), §4/§4.1
and the new §4.2 (training-prototype evidence), §5–§8 (ratings, recommendation
rationale, re-entry conditions), and §12 (sources, verified claims, conflicts).
No decision was made, no option was selected, and the document remains an
unratified draft.

**Status of ratification claims found in cited records.** Some records cited
below declare `RATIFIED` in their own text. This draft does not treat a
self-declared `RATIFIED` label as independent proof. Where ratification is
material, the available evidence is described in section 12.

### 1.1 Verified baseline used to prepare this draft

Recorded at preparation time by direct inspection, not copied from another
document. **Re-verified on 2026-10-16** during a documental reconciliation; the
baseline below is the 2026-10-16 state, which supersedes the original
drafting-time baseline (`873b059`, clean tree — no longer current):

```text
Repository root:            /home/brunapc/LocalAI Hub
Branch:                     main
HEAD:                       88229ee1af1c63a2f43deef8cb4db140d78b8780
                            ("docs: correct run admission descriptions")
Parent of HEAD:             bfa7ac05fc654581f90f615b5c9d45dfd77954ab
origin/main:                88229ee1af1c63a2f43deef8cb4db140d78b8780 —
                            the LOCAL ref origin/main coincided with HEAD at
                            verification time. No fetch was performed, so this
                            does NOT assert that the remote still serves that
                            commit; it records the local ref state only.
Ahead / behind origin/main: 0 ahead / 0 behind (by local refs; no push
                            authorized or performed)
Working tree:               DIRTY — uncommitted changes exist. HEAD itself is
                            clean documentation/fix history; the tree state
                            below is NOT part of any commit.
Uncommitted modifications:  castlearq/evaluate_compatibility.py
                            castlearq/main.py
                            castlearq/training.py
                            tests/test_b979_runtime_artifact_integration.py
                            tests/test_compatibility_report.py
                            tests/test_main.py
                            tests/test_training.py
Untracked files:            docs/lora-qlora-product-scope-human-architectural-
                              decision-record.md  (this draft)
                            tests/test_b967_imported_execution_flow.py
Relevant recent commits:    88229ee  docs: correct run admission descriptions
                            bfa7ac0  docs: reconcile post-B9.99 consumer
                              boundary documentation
                            d7464f8  fix: expose training device and metadata
                              in CLI
                            a7523db  feat: add bounded SFT+LoRA training
                              prototype with device evidence
```

**Commit state vs. working-tree state (important).** The bounded SFT+LoRA
training prototype is **committed** at HEAD: `a7523db` added
`castlearq/training.py`, `castlearq/training_runner.py` and their tests;
`d7464f8` exposed training device/metadata in the CLI. Separately, the working
tree carries **uncommitted** modifications: training-related changes in
`castlearq/training.py` and `tests/test_training.py` (additive
`dataset_path`/`output_dir`/`files` metadata fields and their tests), recent
compatibility changes in `castlearq/evaluate_compatibility.py`,
`castlearq/main.py` and three compatibility/CLI test files, and an untracked
`tests/test_b967_imported_execution_flow.py`. This draft describes the
committed prototype (§4.2) and notes the uncommitted deltas where material;
neither is ratified, authorized, or validated by this document.

Both post-B9.99 governance records were confirmed **tracked** at this baseline
via `git ls-files`:

```text
docs/post-b999-architectural-direction-human-architectural-decision-record.md
docs/post-b999-option-c-bounded-stabilization-validation-human-architectural-decision-record.md
```

Verification method: `git status --short`, `git rev-parse HEAD`,
`git rev-parse HEAD^`, `git rev-parse origin/main` (local ref only),
`git log --oneline -5`, `git ls-files`, direct file inspection, and
repository-wide searches for training artifacts. No reference was fetched or
mutated.

---

## 2. Decision question

> **Should local model training through LoRA/QLoRA be admitted into CastleArq's
> future product scope, or should it be deferred subject to explicit, verifiable
> re-entry conditions?**

### 2.1 Definitions

**LoRA/QLoRA** denote **parameter-efficient fine-tuning (PEFT)** methods: rather
than updating all model weights, they train a small set of added low-rank
parameters (an *adapter*) while the base model weights remain frozen. QLoRA
additionally quantizes the base model to reduce memory use. Both require a
**training loop**: a dataset, a training configuration, iterative optimization,
checkpointing, and a resulting adapter artifact.

**Training is not inference, and not acquisition.** This distinction is
load-bearing for the whole decision:

| Responsibility | What it does | Does CastleArq have it? |
|---|---|---|
| **Inference / execution** | Load a fixed model, produce output for one prompt | **Yes** — delegated to the external `llama` runtime (`castlearq/runner.py:45` `ModelRunner` ABC; `:57` `LlamaCppRunner`) |
| **Acquisition** | Locate, download, verify, store a model artifact | **Yes** — `castlearq/acquisition_service.py`, `castlearq/model_store.py` |
| **Training** | Improve a model by fitting it to a dataset over many steps, producing a new adapter artifact | **Prototype only** — a bounded, synchronous SFT+LoRA use case exists in `castlearq/training.py`/`training_runner.py` (§4.2); it is not an authorized, validated, or product-integrated capability — see section 4 |

Training introduces a value chain that is materially different from anything
CastleArq currently owns. `docs/product-vision-adr.md` §11 (D9) states it
directly:

```text
base model
  -> dataset
  -> training configuration
  -> training job
  -> checkpoint/adapter
  -> evaluation
  -> resulting artifact
  -> deployment/runtime use
```

### 2.2 Scope of this question

This question concerns **product scope only** — whether training may ever be a
CastleArq responsibility. It does not ask *how* training would be built, *when*
it would be scheduled, or *whether* code would be written. Those are separate
later decisions (section 10).

---

## 3. Current product identity and constraints

### 3.1 Established product identity

`docs/B9.47-product-identity-and-value-audit.md` §14 ("Product Identity
Decision") states CastleArq's current identity:

> "Un gestor/orquestador local de artifacts y ejecución para un runtime local,
> que prepara, protege, evalúa y proyecta una ejecución real de llama.cpp con una
> UX y una propiedad local del artifact."

And answers the "why should this exist?" question:

> "para hacer segura y repetible la operación completa alrededor de un runtime,
> **no para mejorar el modelo ni implementar inferencia propia**."

That final clause is decisive for this decision: the audit explicitly separates
CastleArq's purpose from **improving the model** — which is precisely what
training is. `docs/B9.47…md` §16 records `Verdict: PRODUCT-IDENTITY-RESOLVED`.

The reconstructed user journey (§2, lines 17–29) runs:

```text
user CLI/API request
  -> catalog/model identity
  -> artifact resolution and ModelStore
  -> hardware/runtime/backend detection
  -> strict/operational compatibility evaluation
  -> EvaluationAdmission when wired
  -> ArtifactExecutionPreflight
  -> RuntimeBackendSelector
  -> LlamaCppRunner
  -> real llama.cpp process
  -> ExecutionResult / stdout / exit status
```

Every stage concerns **operating an existing model safely and reproducibly**.
None concerns changing the model.

### 3.2 Why execution, acquisition, and storage do not establish a training capability

This is an inference the draft draws, and it is important to state the reasoning
rather than assert a conclusion:

- **Execution ≠ training.** CastleArq builds an argv, launches a subprocess, and
  projects its output (`docs/B9.47…md` §7: "Inferencia | request, argv, result
  projection | carga y ejecuta modelo"). A training loop needs an optimizer,
  gradient steps, loss tracking, and checkpoint resumption — none of which are
  argv-shaped. `docs/B9.47…md` §9 warns that translating a `llamafactory-cli`
  into argv "sería wrapper".
- **Acquisition ≠ dataset management.** Acquisition fetches one immutable
  artifact identified by checksum. A training dataset is a mutable, versioned,
  quality-sensitive collection requiring provenance and validation — a different
  identity problem.
- **Storage ≠ adapter lifecycle.** `ModelStore` (`castlearq/model_store.py:211`)
  stores GGUF artifacts with manifests and SHA-256 verification. It has no
  concept of base-model/adapter pairing, adapter compatibility, promotion, or
  rollback.

`docs/B9.47…md` §9 ("LLaMA-Factory Conceptual Test") enumerates the
responsibilities that would have to exist, and states plainly that they do not:

> "Responsabilidades que no existen: dataset identity, experiment spec, training
> lifecycle, checkpoint/adapter identity, dataset provenance, training
> compatibility, outcome evaluation, artifact promotion/rollback y comparación."

### 3.3 Current dependency and execution constraints

Verified by direct inspection at the baseline:

- `requirements.txt` contains exactly one line:
  `# CastleArq currently uses only the Python standard library.`
- `pyproject.toml` declares **no `dependencies` key** (verified: `grep -c
  '^dependencies' pyproject.toml` → `0`). `requires-python = ">=3.11"`;
  `version = "0.5.1"`.
- No `torch`, `peft`, `transformers`, `datasets`, `accelerate`, or `trl`
  reference appears in either file.

This is a ratified architectural constraint, repeatedly reasserted in the
roadmap closure records — for example `docs/roadmap-register-and-numbering-policy.md`
§28 (B9.87 — Closure Record) records `any new dependency — NOT IMPLEMENTED
(requirements.txt remains standard library only; pyproject.toml unchanged)`.
Section 30 (B9.88 — Closure Record) corroborates the same invariant in shorter
form as `new dependencies — NOT IMPLEMENTED`, without that parenthetical.

**Consequence (inference):** LoRA/QLoRA training cannot be implemented without
introducing a substantial third-party dependency stack (a tensor framework plus
a PEFT library), which would break an actively maintained and test-relevant
invariant. This is a hard cost of any future admission — not a reason training
could never be added, but a cost that must be weighed explicitly.

Additionally, `docs/roadmap-register-and-numbering-policy.md` §42.6 (B9.99
"Out-of-scope and non-goals") lists `PyTorch` among the non-goals, alongside
`B9.100 allocation or creation` and `automatic successor creation`.

### 3.4 Existing explicit training non-goals

Training is excluded by several ratified records:

| Source | Section | Exact constraint |
|---|---|---|
| `docs/product-vision-adr.md` | §11 (D9) | "Fine-tuning remains **outside the current CastleArq core** and requires a separate architectural/product ADR before implementation." |
| `docs/product-vision-adr.md` | §15 | `Fine-tuning: OUT OF SCOPE; REQUIRES A SEPARATE ADR` |
| `docs/product-vision-adr.md` | §13 (D11) | Names `fine-tuning` among surfaces guarded against uncontrolled expansion |
| `docs/B9.47-product-identity-and-value-audit.md` | §12 | "no debe ser plataforma universal de runtimes, **trainer, experiment manager**, cluster scheduler, **LoRA manager**…" |
| `docs/B9.47-product-identity-and-value-audit.md` | §15 | "**No añadir LLaMA-Factory**, nuevos runtimes, GUI ni observability." |
| `docs/run-boundary-architectural-decision.md` | §11 | `fine-tuning, LoRA, QLoRA, datasets or checkpoints` — explicitly not authorized |
| `docs/run-boundary-architectural-decision.md` | §12 | "**Fine-tuning** still requires a separate ADR (D9)." |
| `docs/post-b999-architectural-direction-…md` | §13 | Lists `fine-tuning` and `LoRA/QLoRA` as outside that decision's scope "unless separately authorized" |
| `docs/roadmap-register-and-numbering-policy.md` | §16.3, §20, §22, §29, §30 | Recurring non-goal lists naming LoRA/QLoRA/datasets/training/checkpoints |

**Reading these correctly (important):** these records establish that training is
**currently out of scope and requires a separate ADR before implementation**.
They do **not** establish that training is permanently forbidden. D9 and
`run-boundary` §12 both name the mechanism for changing this — a separate ADR,
which is what this draft prepares. **Absence of a capability is not evidence that
it must never be added**; it is evidence about present scope only.

### 3.5 Why the four decisions are separate

| Decision | Question | Status here |
|---|---|---|
| **Product scope** | May training ever be a CastleArq responsibility? | **The only question in this draft** |
| **Architecture design** | If yes, how — delegated or dedicated subsystem? | **Not made; not authorized** |
| **Roadmap allocation** | Which block number, under roadmap §7 procedure? | **Not allocated; §7 requires corpus inspection** |
| **Implementation authorization** | May code be written? | **Not granted** |

`docs/post-b999-architectural-direction-…md` §16 ("Required Workflow After This
Decision") sets the sequence, and states: "Selecting Option B does not bypass
this sequence." The same discipline applies here.

---

## 4. Verified current-state evidence

Each row distinguishes what was **independently verified** during preparation of
this draft from what was **inherited** from an existing governance document.

| # | Claim | Evidence source | Verification | Product-scope implication | Limitation / uncertainty |
|---|---|---|---|---|---|
| E1 | A bounded SFT+LoRA training prototype exists (§4.2); QLoRA was not found — no quantization config, no bitsandbytes integration. See §4.2 for the full prototype description. | `grep -rniE '\blora\b\|\bqlora\b\|\bpeft\b\|fine.?tun\|train\|checkpoint\|optimizer\|gradient' castlearq/ --include='*.py'` → drafting history only; current evidence is `castlearq/training.py` + `castlearq/training_runner.py` (synchronous in-process SFT+LoRA; staging + atomic rename; device preference XPU > CUDA > CPU) | **Re-verified 2026-10-16** (this task) | A prototype exists but is not an authorized, validated, or product-integrated capability | Prototype existence is not execution evidence; device preference alone proves nothing per-device |
| E2 | Double-based unit tests for the SFT+LoRA prototype exist; no real-training validation was performed (see §4.2) | `grep -rliE 'lora\|fine.?tun\|qlora'` (drafting history). Current evidence: double-based unit-test validation via `tests/test_training.py` (validation, admission, simulated execution, errors, device selection); the CPU smoke test was deliberately omitted | **Re-verified 2026-10-16** (this task); the drafting-time grep is obsolete | Double-based tests exist, but no execution evidence and no acceptance criteria for real training | The omitted smoke test must not be described as real training validation |
| E3 | No dataset/provenance concept | Only `dataset` matches in committed code are the **compatibility-knowledge** corpus (`castlearq/initial_knowledge.py:15`, `:40`, `:846`) — declarative runtime knowledge, not training data. (Uncommitted `dataset_path` metadata fields in `training.py` name a path parameter only; they add no provenance concept.) | **Independently verified; re-checked 2026-10-16** | Dataset identity/provenance would be entirely new | The word "dataset" is overloaded; do not conflate the two senses |
| E4 | Dependency surface is standard library only | `requirements.txt` (one comment line); `pyproject.toml` has no `dependencies` key (`grep -c` → `0`) | **Independently verified** | Training would require a major dependency-stack change | — |
| E5 | No long-running job lifecycle | `castlearq/execute_model.py` is a one-shot coordinator; `DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0` (line 64); no job entity, scheduler, cancellation, or resume concept | **Independently verified** | Training-run lifecycle would be new | — |
| E6 | No adapter identity/storage | `castlearq/model_store.py:211` `ModelStore` stores GGUF artifacts with SHA-256 (`:537`); `castlearq/models.py:39` `ArtifactSpec` | **Independently verified** | Adapter identity, versioning, compatibility, promotion would be new | — |
| E7 | Evaluation measures *fit*, not *quality* | `castlearq/evaluate_compatibility.py`, `castlearq/evaluation_pipeline.py`, `castlearq/compatibility_evaluator.py` — compatibility/feasibility, not model-quality scoring | **Independently verified** | A quality-evaluation and baseline mechanism would be new | — |
| E8 | Inference is delegated | `castlearq/runner.py:45` `ModelRunner` (ABC), `:57` `LlamaCppRunner` | **Independently verified** | Training could likewise be delegated — relevant to architecture, **not decided here** | — |
| E9 | Nine training responsibilities do not exist | `docs/B9.47…md` §9: "dataset identity, experiment spec, training lifecycle, checkpoint/adapter identity, dataset provenance, training compatibility, outcome evaluation, artifact promotion/rollback y comparación" | **Inherited** (re-checked against re-verified E1–E7; E1–E2 now record a prototype with tests, E3–E7 still absent) | Substantial new subsystem would be required | The prototype (§4.2) supplies none of these nine |
| E10 | Product identity excludes model improvement | `docs/B9.47…md` §14: "no para mejorar el modelo ni implementar inferencia propia"; §16 `PRODUCT-IDENTITY-RESOLVED` | **Inherited** | Training is outside the resolved identity | Identity is a conclusion of a prior audit, not a permanent law |
| E11 | Product thesis is unvalidated | `docs/product-vision-adr.md` §14 (D12): "the thesis is **NOT considered externally validated**… insufficient evidence to claim broad market demand" | **Inherited** | Demand for training is even less evidenced than demand for the core product | No user research of any kind exists in the repository |
| E12 | Scope-control guardrail | `docs/product-vision-adr.md` §13 (D11): no new surface becomes a priority while an allocated core capability "lacks a real caller or integration, unless an explicit human decision justifies the exception" | **Inherited** | Argues against admitting training now; **but** D11 contains an explicit human-override path | D11 governs *priority*, not *discussion* |
| E13 | B9.99 non-goals include PyTorch | `docs/roadmap-register-and-numbering-policy.md` §42.6; also `B9.100 allocation or creation`, `automatic successor creation` | **Inherited** | Training backend would conflict with a ratified non-goal | These bind the B9.99 scope, not all future work |
| E14 | Closure does not authorize successors | §42.12: "Closure does not authorize B9.100 or any successor." | **Inherited** | No automatic path to a training block | — |
| E15 | Stabilization direction excludes training | `docs/post-b999-architectural-direction-…md` §13 lists `fine-tuning`, `LoRA/QLoRA` outside scope "unless separately authorized" | **Inherited** | The current direction prioritizes core stabilization over new surfaces | The phrase "unless separately authorized" preserves a path |
| E16 | Currently authorized next phase is a read-only `run`/`execute` audit | `docs/post-b999-option-c-…md` §1.3: "Only a READ-ONLY behavioral evidence audit comparing `run` and `execute`. No implementation authorization is granted." | **Inherited** | A training decision does not replace or supersede this phase | This HADR must not be read as performing that audit |

### 4.1 On the reported local experiment (Intel Arc Pro B70 / PyTorch XPU / SmolLM2-135M / LoRA)

A prior conversation reported local experiments on Intel Arc Pro B70 hardware
using PyTorch XPU, SmolLM2-135M, and LoRA, including training smoke tests,
successful adapter loading for inference, a small synthetic four-class
classification experiment, and a constrained-decoding result of 16/20 versus
15/20 for the base model.

**This draft does not treat those results as verified evidence**, for the
following reasons established by direct inspection:

- **No artifacts exist in the repository.** A filesystem search for `*adapter*`,
  `*.safetensors`, `*smollm*`, `*.ipynb`, `*lora*`, and `*arc*b70*` returned
  **no training artifacts**. The only `adapter` matches are
  `castlearq/boundary_adapter.py` ("B9.12 I1: Boundary Adapter — pure translation
  domain core") and `castlearq/evaluation_adapter.py` ("B9.8: pure adapter from
  the execution domain to the strict B9.3 domain") — **domain-translation
  adapters, unrelated to LoRA adapters**.
- **No report exists in `docs/`.** `grep -rniE '\bxpu\b|smollm|arc pro' docs/`
  returned **no matches in tracked records** (this draft is untracked and discusses the reported claims only to exclude them, §§4.1/7.3/8). The only Intel Arc reference in tracked records is
  `docs/B9.6.0-initial-knowledge-specification.md` §14 ("Intel Arc /
  Battlemage Case"), which concerns *inference* suitability under
  Vulkan/SYCL/llama.cpp — not training.
- **Prototype exists, but no execution evidence.** Per re-verified E1, `castlearq/` now contains a bounded SFT+LoRA path that *could* mechanically produce an adapter — but no artifact, log, or report from the reported runs was found, and no training was executed during the audit. The gap is execution evidence, not code.

Consequently the experiments are classified as **previously reported but
independently unverified**, and are **excluded from the evidence base** for the
recommendation. This is stated as an evidentiary limitation, not as a claim that
the experiments did not happen.

Separating the four feasibility layers — the correct frame for evaluating such
results *if* artifacts were later produced:

| Layer | Question | What a smoke test would establish | What it would **not** establish |
|---|---|---|---|
| **Hardware/backend feasibility** | Can the accelerator run a training loop at all? | That XPU is usable for this workload | Anything about quality or cost |
| **Training pipeline feasibility** | Does the mechanical loop complete? | That tooling can train, save, and reload an adapter | That training is *reproducible* or *provenanced* |
| **Model quality / generalization** | Does the adapter make the model better? | Little on its own | A 16/20 vs 15/20 result on **synthetic** data is **+1 example on n=20** — inside noise, and cannot support a generalization claim |
| **Product readiness** | Should CastleArq ship this? | Nothing | Nothing about user need, lifecycle, provenance, or evaluation |

**Conclusion:** even taken at face value, the reported results speak only to the
first two layers. They do not address quality, generalization, or product need,
and they cannot substitute for the re-entry conditions in section 8.

### 4.2 Training prototype found in the reviewed tree (re-verified 2026-10-16)

The drafting-time claim that no training implementation or tests exist is
**obsolete**. Direct inspection of the reviewed tree finds a bounded SFT+LoRA
prototype, committed at HEAD (`a7523db` added `castlearq/training.py`,
`castlearq/training_runner.py` and their tests; `d7464f8` exposed training
device/metadata in the CLI). The working tree additionally carries uncommitted
training-path deltas described in §1.1. What follows describes the reviewed
code only; it grants no authorization and records no validation.

- **Flow (synchronous, in-process).** `castlearq/training.py` documents the
  ordering as `validate request -> resolve/validate base model -> admission
  -> runner (staging dir) -> publish adapter -> TrainingResult`. The use case
  runs the runner in a staging directory created beside the destination
  (`tempfile.mkdtemp`), writes run metadata there, and publishes the result
  with an atomic `os.rename(staging, output_dir)`; a failed publish surfaces
  as typed `PUBLISH_FAILED`, and un-published staging directories are removed
  without touching user data. There is no job entity, scheduler, cancellation,
  or resume concept — persistence, cancellation, and reanudación remain
  absent.
- **Delegation to external libraries.** The use-case module never imports heavy
  ML dependencies; the runner owns all lazy imports (`torch`, `transformers`,
  `peft`, `trl`, `datasets` — `SftLoraRunner.REQUIRED`). A missing training
  stack surfaces as typed `DEPENDENCIES_MISSING`, never an `ImportError` at
  CastleArq import time. The stack was not installed in the audit environment,
  and no real training was executed.
- **Deliberate boundaries.** The base model must be an explicitly supplied
  local Transformers-compatible checkpoint directory; GGUF inputs are rejected
  with `UNSUPPORTED_MODEL_FORMAT` before any runner runs. `EvaluationAdmission`
  keeps deny-by-default semantics when supplied, and `TrainingResult
  .admission_path` records which boundary admitted each run. Adapter output
  goes to a caller-selected directory **outside** the managed model store:
  `ModelStore`/`ArtifactSpec` remain GGUF-artifact-addressed with no
  base-model/adapter pairing, so adapter–ModelStore integration, dataset
  provenance, and quality evaluation remain absent or pending.
- **Device selection.** `select_training_device()` prefers XPU, then CUDA, then
  CPU, by availability probing. `RunnerOutcome` carries both `selected_device`
  (the selection) and `effective_device` (what the initialized Trainer
  reports, `None` when unavailable — explicitly never to be read as claiming
  a device). Availability-based selection does **not** by itself prove that
  training works on each device.
- **Tests.** `tests/test_training.py` provides double-based unit tests covering
  validation, admission, simulated execution, errors, and device selection.
  The CPU training smoke test was deliberately omitted, so it must not be
  described as real training validation.
- **QLoRA.** Not implemented in the inspected prototype code: no quantization
  configuration and no bitsandbytes integration were found.

**Net effect on this draft:** E1–E2 are corrected above; the limitation relevant
to the re-entry conditions (§8) is lack of *training-execution* evidence, not
absence of code. The prototype changes none of the product-identity, scope,
or dependency constraints in §3.

---

## 5. Alternatives

> **Option-letter warning.** The letters A–D below belong **only to this HADR**.
> They must not be confused with the option letters used in
> `docs/roadmap-register-and-numbering-policy.md` §42.1.1 (the **B9.99
> "Full Explicit Arbitrary-HF-GGUF Vertical Slice" allocation**) or in
> `docs/post-b999-architectural-direction-…md` §3 (the **post-B9.99 "Stabilize
> CastleArq Core First" direction**), nor with `docs/post-b999-option-c-…md`
> (**"Bounded Stabilization + Validation"**). External option references in this
> document are always qualified by decision title.

### Option A — Admit LoRA/QLoRA to future product scope

Authorize further product and architecture planning for training. Does **not**
authorize architecture, allocation, or implementation.

- **Product-identity coherence:** **Low.** Contradicts `B9.47` §14 ("no para
  mejorar el modelo") and §12 (non-goals name "trainer, experiment manager…
  LoRA manager"). Coherent only if the identity is *first* deliberately revised.
- **Value to the intended user:** **Unproven.** No user problem is documented
  (E11); D12 declares even the core thesis unvalidated. Value is speculative.
- **Scope and maintenance burden:** **High.** Nine new responsibility areas
  (E9), plus dependency maintenance and hardware-specific behavior.
- **Dependency/runtime implications:** **Severe.** Breaks the standard-library
  invariant (E4); conflicts with the PyTorch non-goal (E13).
- **Interaction with current architecture:** **Tense.** Would sit beside — not
  within — the inference/acquisition chain. Artifact and adapter identity would
  diverge (`ArtifactSpec` is GGUF-oriented, E6).
- **Evidence strength:** **Weak.** No verified artifact, report, or quality
  signal (§4.1).
- **Reversibility:** **Moderate for the scope decision itself; the distinction
  matters.** Option A authorizes no code, dependency, or boundary change, so the
  *scope decision* is as reversible as any documentation record — a later human
  decision can reverse it. The cost cited below attaches to a *later*
  implementation decision, not to this one: the dependency-stack and identity
  changes that implementation would invite are costly to unwind. Because
  admitting scope creates momentum toward that later work, this dimension is not
  rated simply Favourable; the commitment risk is assessed separately under
  "Risk of premature commitment" below. See also section 6, where
  "Reversibility" and "Preserves optionality for a real future need" are distinct
  dimensions and their differing ratings for Option A are intentional.
- **Risk of premature commitment:** **High.** Commits direction before a problem
  is demonstrated; the precise failure `B9.47` §10 warns about ("no confundir
  arquitectura posible con valor realizado").
- **Conditions and consequences:** Requires the human to override D11 explicitly
  (D11 permits this "unless an explicit human decision justifies the exception").
  If selected, architecture design remains a separate later decision.

### Option B — Defer training with explicit re-entry conditions

Keep training outside current product scope until verifiable conditions
(section 8) are met.

- **Product-identity coherence:** **High.** Consistent with `B9.47` §14/§16,
  D9, D11, `run-boundary` §12, and post-B9.99 §13.
- **Value to the intended user:** **Neutral.** Focuses effort on the
  already-evidenced problem: making local execution safe and reproducible.
- **Scope and maintenance burden:** **None added.**
- **Dependency/runtime implications:** **None.** Preserves the standard-library
  invariant and the PyTorch non-goal.
- **Interaction with current architecture:** **None.** No boundary changes.
- **Evidence strength:** **Strong for the negative on product scope.** Every verified and
  inherited record points the same way on scope (E1–E16 as re-verified: a prototype exists, but authorization, execution evidence, lifecycle, provenance, quality evaluation, and product need are all still absent).
- **Reversibility:** **Highest.** A named-condition deferral can be revisited on
  demand without undoing anything.
- **Risk of premature commitment:** **Lowest.**
- **Conditions and consequences:** Training remains out of scope; no
  implementation follows. Section 8 makes the deferral *verifiable* rather than
  vague, so it does not become an indefinite refusal by neglect.

### Option C — Reject training as a CastleArq product responsibility

Treat training as permanently or indefinitely outside CastleArq's
responsibility.

- **Product-identity coherence:** **High** for the current identity, but it goes
  further than any existing record. `B9.47` §12 scopes non-goals to
  "CastleArq 0.1"; D9 says "outside the current core… requires a separate ADR" —
  not "never".
- **Value to the intended user:** **Neutral.**
- **Scope and maintenance burden:** **None added.**
- **Dependency/runtime implications:** **None.**
- **Interaction with current architecture:** **None.**
- **Evidence strength:** **Moderate for the negative, but overreaching.** No
  record supports a permanent prohibition; the corpus consistently leaves a
  reopening path.
- **Reversibility:** **Low.** Requires an explicit reopening decision, discarding
  accumulated evidence and any future hardware or UX developments.
- **Risk of premature commitment:** **Moderate.** Forecloses on today's evidence
  what may be a legitimate future capability; the mirror image of Option A's
  risk.
- **Conditions and consequences:** Reopening would require an explicit human
  decision that supersedes this one. Note the asymmetry with Option B: B
  preserves optionality cheaply, C spends it.

### Option D — Gather additional evidence before deciding

Make no admission or rejection decision yet; identify the specific evidence
needed.

- **Product-identity coherence:** **Neutral.** Changes nothing.
- **Value to the intended user:** **Neutral**, pending evidence.
- **Scope and maintenance burden:** **Small if bounded**; unbounded evidence
  gathering becomes a hidden workstream.
- **Dependency/runtime implications:** **None** if read-only.
- **Interaction with current architecture:** **None.**
- **Evidence strength:** **N/A** — this option is about acquiring evidence.
- **Reversibility:** **Highest**, but it defers the decision itself.
- **Risk of premature commitment:** **None**, but risks **decision drift** — the
  question stays open indefinitely without a trigger.
- **Conditions and consequences:** Only sensible if the evidence to gather is
  named, bounded, and read-only. **Critically, the repository already authorizes
  one such evidence activity**: the read-only `run`/`execute` behavioral audit
  (Option-C record §1.3). Layering an additional open-ended evidence phase on top
  would duplicate that authorization without adding a distinct artifact.

**Note on the overlap between B and D.** Option B *contains* the substance of
Option D: section 8 names exactly the evidence a future review would need. B
records a decision now and defines the trigger; D records no decision and risks
drift. This is a principal reason the provisional recommendation in section 7 is
B rather than D.

---

## 6. Comparative decision matrix

Ratings are **ordinal judgments**, not measurements. No numeric score is
assigned, because no measured quantity underlies these judgments; inventing
weights would create false precision and could let an aggregate override an
explicit governance restriction.

Legend: **Favourable / Neutral / Unfavourable / Blocking**

**Note on two Option A ratings before reading the table.** "Reversibility" and
"Preserves optionality for a real future need" measure different things, and
Option A is rated differently on each on purpose.

- *Reversibility* asks how costly it is to **undo this decision later**. Option A
  is rated Neutral rather than Favourable because, although the scope decision
  itself is easily reversed, admitting scope creates momentum toward a later
  implementation whose dependency-stack and identity changes are costly to unwind.
- *Preserves optionality for a real future need* asks whether the decision
  **forecloses a capability that may later prove valuable**. On that measure
  Option A is Favourable and Option C is Unfavourable, because C spends the
  option while A keeps it open.

These ratings are therefore consistent with each other and with the Option A
narrative in section 5, which states the same distinction explicitly.

| Criterion | A — Admit | B — Defer w/ conditions | C — Reject | D — Gather evidence |
|---|---|---|---|---|
| Product-identity coherence (`B9.47` §14, §16) | Unfavourable | **Favourable** | Favourable | Neutral |
| Demonstrated user value (E11, D12) | Unfavourable | Neutral | Neutral | Neutral |
| Scope / maintenance burden (E9) | Unfavourable | **Favourable** | Favourable | Neutral |
| Dependency impact (E4, E13) | **Blocking for implementation** | **Favourable** | Favourable | Favourable |
| Architectural coherence / separation of concerns | Unfavourable | **Favourable** | Favourable | Neutral |
| Reversibility | Neutral | **Favourable** | Unfavourable | Favourable |
| Governance compatibility (D9, D11, §42.6, post-B9.99 §13) | Unfavourable | **Favourable** | Neutral | Favourable |
| Risk of premature commitment | Unfavourable | **Favourable** | Neutral | Neutral |
| Preserves optionality for a real future need | Favourable | **Favourable** | Unfavourable | Favourable |
| Decision recorded now (avoids drift) | Favourable | **Favourable** | Favourable | Unfavourable |

### 6.1 Hard governance constraints vs. preferences

**Hard constraints (cannot be outweighed by any preference):**

1. No roadmap allocation without the §7 corpus-inspection procedure —
   `docs/roadmap-register-and-numbering-policy.md` §7.
2. No B9.100 or automatic successor — §42.6, §42.12, post-B9.99 §15.
3. No implementation authorization — post-B9.99 §16 requires the full sequence.
4. The read-only `run`/`execute` audit remains the currently authorized phase —
   Option-C record §1.3.
5. Fine-tuning requires a separate ADR before implementation — D9,
   `run-boundary` §12.

**Preferences (the human may weigh differently):** how much value to place on
preserving optionality versus decisiveness; whether the dependency-stack cost is
acceptable in principle; how much weight to give the `B9.47` identity conclusion.

**All four options satisfy the hard constraints.** None allocates a number,
creates B9.100, or authorizes implementation. The matrix therefore reflects
preferences, not constraint satisfaction — which is why the recommendation below
is explicitly a *recommendation*.

**Reading of the matrix:** Option B is favourable on every criterion and
unfavourable on none. Option A is unfavourable on most. Option C matches B on
coherence but sacrifices reversibility and optionality without any record
requiring a permanent prohibition. Option D is broadly neutral but uniquely
unfavourable on recording a decision now.

---

## 7. Recommendation

> **Provisional recommendation (preparer's opinion, NOT the human decision):
> Option B — Defer LoRA/QLoRA training from the current CastleArq product scope
> until explicit re-entry conditions are met.**

### 7.1 Rationale, grounded in verified evidence

**1. The current product identity explicitly excludes model improvement.**
`B9.47` §14 answers "why should this exist?" with "no para mejorar el modelo ni
implementar inferencia propia", and §16 records `PRODUCT-IDENTITY-RESOLVED`.
Training is the one activity the identity statement names as out of purpose.

**2. Technical feasibility and product need are different things.** A bounded SFT+LoRA prototype with double-based tests exists (re-verified E1/E2, §4.2), but no training was executed during the audit, no experiment artifact or report
exists in the repository (§4.1), and QLoRA was not found. A backend that *can* run a training loop says
nothing about whether CastleArq *should* own one. `B9.47` §10 states the
discipline directly: "no confundir arquitectura posible con valor realizado."

**3. Nine responsibilities would have to be established first.** `B9.47` §9
names them: dataset identity, experiment spec, training lifecycle,
checkpoint/adapter identity, dataset provenance, training compatibility, outcome
evaluation, artifact promotion/rollback, and comparison. Re-verified E3–E7
confirm the surrounding capabilities are still absent, and §4.2 records that the
prototype supplies none of these nine (no job persistence, cancellation,
resumption, adapter–ModelStore integration, dataset provenance, or quality
evaluation). Admitting scope before any is designed would be scope
without substance.

**4. The dependency cost is severe and conflicts with ratified non-goals.** The
standard-library invariant (E4) is actively reasserted in closure records, and
§42.6 names PyTorch as a B9.99 non-goal (E13). Any admission eventually requires
overturning both.

**5. No demonstrated core need is being crowded out.** D12 declares the core
product thesis itself unvalidated (E11), and D11 guards against new surfaces
while allocated capabilities lack real callers (E12). Adding training now would
expand the surface precisely when the existing one is still unproven.

**6. Option B costs nothing and keeps the door open.** Unlike Option C, it
records no permanent prohibition — no existing record supports one — and it names
verifiable conditions, so deferral cannot silently become refusal by neglect.

### 7.2 Strongest argument against the recommendation

**The strongest counterargument is that Option B may under-value a genuine
strategic opportunity, and that deferral can become permanent in practice.**

- CastleArq's whole value proposition is *reducing uncertainty for local-AI
  users*. A user who cannot get adequate behavior from an off-the-shelf model
  faces exactly that uncertainty, and adaptation may be the natural next step in
  the same product chain — not a foreign capability.
- The project's reference hardware (Intel Arc B70, `docs/B9.6.0-…md` §14) already
  sits inside the product's knowledge model. If XPU-based adaptation were
  practical, CastleArq would be unusually well placed to make it usable, because
  it already reasons about that hardware. **This is an untested hypothesis, not a
  finding.** No competitor or market analysis exists in the repository, so no
  claim of differentiation over other tools can be supported here; the point is
  only that CastleArq's existing hardware knowledge is a plausible advantage
  *if* a user need were first demonstrated.
- `B9.47` §12 scopes its non-goals to "CastleArq 0.1", not to all future
  versions. Reading them as permanent over-extends that audit.
- A deferral with ten conditions can function as a high bar that is never
  cleared, producing the same practical outcome as Option C while appearing more
  open.

**Evidence that would justify Option A instead:** a documented, specific user
problem that inference and acquisition cannot solve; a named intended user with a
concrete workflow; credible evidence that the workflow belongs inside CastleArq
rather than in an external tool; and a reproducible evaluation showing an adapter
produces improvement distinguishable from noise on non-synthetic data. Section 8
conditions 1–3 and 8 are the operative ones.

### 7.3 Conflicts between verified evidence and this recommendation

**One material conflict is disclosed rather than concealed.** If the human
maintainer holds that the Intel Arc Pro B70 / PyTorch XPU / LoRA experiments
demonstrated real, reproducible training feasibility, then condition 9 of
section 8 would move from *contested* to *partially evidenced*, and the
"evidence strength" rating for Option A would rise from weak toward moderate.
This draft could not verify that (§4.1: no artifacts, no report, no execution evidence despite the prototype),
and therefore recommends on the verifiable record alone. **The recommendation is
sensitive to that one input**; the human is better placed than this draft to
judge it.

A second, lesser tension: `B9.47` §15 recommends closing the pending B9.46.29
acceptance and keeping 0.1 focused, which supports deferral — but that audit
predates B9.99's closure, so its "current" framing is itself dated.

---

## 8. Re-entry conditions

Observable, testable conditions under which a future human decision could
reconsider a deferral. **None of these is asserted as satisfied.** Each is marked
**satisfied / partially evidenced / unsatisfied / not yet evaluated**, with
justification drawn from section 4.

These conditions **create no roadmap block, allocate no number, and authorize no
work.** They exist so a future review has concrete criteria rather than an open
question. Satisfying a condition does not admit training; only a human decision
does.

| # | Condition | Status | Justification |
|---|---|---|---|
| 1 | A documented user problem that current inference/acquisition cannot adequately solve | **Unsatisfied** | No such document exists. `B9.47` §3 defines the current problem as reproducible safe *execution*. D12 (E11) declares even the core thesis unvalidated. |
| 2 | A clearly identified intended user and concrete training workflow | **Unsatisfied** | No user or workflow is named anywhere in the repository. `B9.47` §4 describes a developer/operator with a local GGUF — an inference user. |
| 3 | Evidence that training belongs inside CastleArq rather than an external tool | **Unsatisfied** | `B9.47` §9 raises the question and leaves it open: LLaMA-Factory "sería una tool specialization… no orquestación mientras CastleArq sólo componga argumentos." No comparison exists. |
| 4 | A bounded initial use case and explicit exclusions | **Not yet evaluated** | Cannot be defined before conditions 1–2 exist. |
| 5 | A credible design for dataset identity and provenance | **Unsatisfied** | E3: no dataset concept exists. The only "dataset" is the declarative compatibility-knowledge corpus, a different thing. |
| 6 | Training-run specification, lifecycle, cancellation, and failure handling | **Unsatisfied** | E5: execution is one-shot with a 600 s ceiling; no job entity, scheduler, cancellation, or resume concept. |
| 7 | Checkpoint/adapter identity, storage, compatibility, promotion | **Unsatisfied** | E6: `ModelStore`/`ArtifactSpec` handle GGUF artifacts only; no base-model/adapter pairing or compatibility concept. |
| 8 | Evaluation criteria and a reproducible baseline distinguishing improvement from noise | **Unsatisfied** | E7: evaluation measures compatibility/fit, not quality. No baseline harness exists. A reported 16/20 vs 15/20 on synthetic n=20 would not meet this bar (§4.1). |
| 9 | Verified backend/runtime feasibility on supported hardware, with resource and dependency costs understood | **Unsatisfied on the verifiable record; possibly partially evidenced by unverified reports** | Re-verified E1/E2/E4: a bounded SFT+LoRA prototype with double-based tests exists (§4.2), but no training was executed during the audit, the optional stack was not installed, the CPU smoke test was deliberately omitted, and §42.6 still names PyTorch a non-goal. §4.1: no experiment artifact or report in the repository. `docs/B9.6.0-…md` §14 establishes Intel Arc B70 as *inference* reference hardware only. **See §7.3 — the human may hold evidence this draft could not verify.** |
| 10 | A separate architectural review, then the roadmap-allocation procedure and explicit implementation authorization, if scope is later affirmative | **Not yet evaluated** | Correctly sequenced but not begun. Requires §7 corpus inspection; §42.12 confirms closure authorizes no successor. |

### 8.1 Summary of condition status

```text
SATISFIED:              0
PARTIALLY EVIDENCED:    0
UNSATISFIED:            7  (conditions 1, 2, 3, 5, 6, 7, 8)
NOT YET EVALUATED:      2  (conditions 4, 10)
CONTESTED:              1  (condition 9; see 7.3 and section 8, row 9)

Total:                  10 — each condition counted exactly once
```

Condition 9 is counted once, under `CONTESTED`, because its verifiable record is
unsatisfied while the human maintainer may hold experiment evidence this draft
could not inspect. It is therefore neither fully unsatisfied nor merely
unevaluated, and it is not double-counted in any other category above.

**No condition is claimed satisfied.** Conditions 1–3 and 8 are the substantive
gates: they concern demonstrated need and the ability to tell improvement from
noise. Conditions 5–7 and 9 are engineering prerequisites that become relevant
only once 1–3 hold.

---

## 9. Consequences and non-goals

### 9.1 Consequences of each likely decision

**If Option B is selected (defer with conditions).** Training remains outside
current product scope. No implementation, no architecture work, no allocation
follows. The read-only `run`/`execute` audit continues as the currently
authorized phase. Section 8 conditions become the criteria a future review must
address, and the question may be reopened without undoing anything.

**If Option A is selected (admit to future scope).** This authorizes **further
product and architecture deliberation only**. It does **not** authorize
implementation, does not allocate a block, and does not create B9.100. The
architecture question — delegated external tool versus dedicated subsystem — is
opened and remains a separate decision. The dependency conflict (E4, E13) and the
identity tension (`B9.47` §14) remain to be resolved in that later work, not
here.

**If Option C is selected (reject).** Training is treated as outside CastleArq's
responsibility. Reopening requires an **explicit human decision that supersedes
this record** — the matter cannot be reopened by inference, by a later audit, or
by technical feasibility alone. This is the key difference from Option B, where
the named conditions provide a standing path back.

**If Option D is selected (gather evidence).** No admission or rejection is
recorded. The bounded, read-only evidence work named in section 8 becomes the
next step — but note that the repository **already authorizes one such phase**
(the `run`/`execute` audit, Option-C record §1.3), and this option should not be
used to imply a second open-ended evidence mandate. The decision itself stays
open, with the drift risk described in §5.

### 9.2 Explicit exclusions

This HADR excludes, and does not authorize:

```text
Trainer or training-job implementation
LoRA/QLoRA code, adapter management, datasets, or training dependencies
GUI, experiment-manager, or observability work
Changes to model identity, ArtifactSpec, ModelStore, or execution semantics
Changes to the roadmap register
Creation of B9.100 or any successor allocation
Automatic milestone allocation
Implementation authorization
```

It also does not perform, supersede, or imply completion of the authorized
read-only `run`/`execute` behavioral evidence audit.

---

## 10. Governance and sequencing

If training is eventually admitted, the required sequence is unchanged from the
established CastleArq process (`docs/post-b999-architectural-direction-…md` §16):

```text
1. Human ratification of product scope          <- this HADR's decision (section 11)
2. Separate architecture decision               NOT AUTHORIZED HERE
3. Evidence and boundary review                NOT AUTHORIZED HERE
4. Explicit roadmap allocation under existing
   policy (roadmap section 7 corpus
   inspection, then a Number Allocation
   Record)                                      NOT AUTHORIZED HERE
5. Separate implementation authorization        NOT AUTHORIZED HERE
6. Implementation and validation under the
   authorized scope                             NOT AUTHORIZED HERE
```

**Ratifying product scope does not skip any later gate.** Steps 2–6 each require
their own human decision. `docs/post-b999-architectural-direction-…md` §14 adds
that future proposals should establish, among other things, "whether the proposed
work requires a new roadmap block" — and §16 states: "Selecting Option B does not
bypass this sequence."

**Preservation of the currently authorized phase.** The bounded read-only
`run`/`execute` behavioral evidence audit selected under
`docs/post-b999-option-c-bounded-stabilization-validation-…md` §1.3 remains the
authorized next phase. This HADR neither performs it, supersedes it, nor implies
its completion. Both can proceed independently.

---

## 11. Human decision record

> **Amendment 2026-10-16 (maintainer-authorized):** Option E below was added
> to express the maintainer's communicated decision (SFT+LoRA in experimental
> scope; QLoRA out of current scope). Options A–D are retained unchanged as
> drafting history. The preparer's provisional recommendation in section 7 is
> **not** recorded here as the human decision.

```text
HUMAN DECISION: RATIFIED — OPTION E (2026-10-16)
```

### 11.1 Options presented for human selection

```text
OPTION A — Admit LoRA/QLoRA to future product scope.
           Authorizes further product and architecture planning only.
           Does NOT authorize architecture, allocation, or implementation.

OPTION B — Defer LoRA/QLoRA training with explicit re-entry conditions
           (section 8). Training remains outside current product scope.

OPTION C — Reject training as a CastleArq product responsibility.
           Reopening requires an explicit future human decision.

OPTION D — Gather additional evidence before deciding.
           Names bounded, read-only evidence work (section 8); records no
           admission or rejection yet.

OPTION E — Admit SFT+LoRA to experimental product scope; QLoRA out of current scope.
            Admits the bounded SFT+LoRA prototype (§4.2) to experimental product
            scope only. QLoRA remains out of current scope and requires a future
            decision. Authorizes planning within experimental scope only. Does NOT
            authorize architecture design, roadmap allocation, Number Allocation
            Record creation, implementation, dependencies, training functionality,
            adapters, datasets, or any real training execution.
```

### 11.2 Decision fields — to be completed by the human maintainer

```text
SELECTED OPTION:                    [ E ]

HUMAN RATIONALE:                    Maintainer decision: admit SFT+LoRA to experimental product scope; QLoRA excluded from current scope pending a future decision. The existing prototype is not validated for general use; reproducible validation remains pending.

ACCEPTED RISKS:                     Experimental scope only: the prototype may not generalize; no real training has been executed; validation is pending; QLoRA remains excluded pending a separate future decision.

RE-ENTRY CONDITIONS OR EVIDENCE
REQUIREMENTS ACCEPTED:              QLoRA requires a future human decision before any admission. Reproducible validation of the SFT+LoRA prototype on real hardware and a non-synthetic quality evaluation remain pending before implementation or roadmap allocation.

RATIFICATION DATE:                  2026-10-16

DECISION AUTHORITY:                 PROJECT OWNER (human maintainer)

CONFIRMATION — ROADMAP ALLOCATION NOT INCLUDED:
  This decision does not allocate a roadmap block, does not create a Number
  Allocation Record, and does not create or authorize B9.100 or any successor.
                                     [X] CONFIRMED BY HUMAN

CONFIRMATION — IMPLEMENTATION AUTHORIZATION NOT INCLUDED:
  This decision does not authorize architecture design, code, tests,
  dependencies, training functionality, adapters, or datasets.
                                     [X] CONFIRMED BY HUMAN

CONFIRMATION — EXISTING AUTHORIZED PHASE PRESERVED:
  The bounded read-only run/execute behavioral evidence audit remains the
  currently authorized next phase and is unaffected by this decision.
  Confirmed by the human maintainer: this decision (OPTION E, 2026-10-16)
  does not supersede or extend the authorized phase; see
  docs/post-b999-option-c-bounded-stabilization-validation-human-architectural-decision-record.md
  §1.3 (read-only run/execute behavioral evidence audit).
                                     [X] CONFIRMED BY HUMAN
```

**No identity, signature, or third-party approval is invented in this section.**
`HUMAN DECISION` is `RATIFIED — OPTION E (2026-10-16)` per the maintainer's communicated decision; see section 11.2 for the recorded fields. All confirmations in section 11.2 are now confirmed by the human maintainer.

---

## 12. References and evidence limitations

### 12.1 Sources used

| Path | Sections relied upon |
|---|---|
| `docs/product-vision-adr.md` | §11 (D9 — Fine-tuning); §12 (D10 — Product-surface boundary); §13 (D11 — Scope-control rule); §14 (D12 — Product-validation status); §15 (Explicit non-authorizations); §16 (Status) |
| `docs/B9.47-product-identity-and-value-audit.md` | §1 (Executive Summary); §2 (Current Product Reconstruction); §3 (Current User Problem); §4 (Current User / Use Case); §5 (Wrapper vs Orchestration); §7 (Responsibility Boundary); §9 (LLaMA-Factory Conceptual Test); §10 (Overarchitecture Audit); §12 (Explicit Non-Goals); §14 (Product Identity Decision); §15 (Recommended Next Step); §16 (Verdict) |
| `docs/run-boundary-architectural-decision.md` | §3 (Decision Question); §11 (Explicit non-consequences); §12 (Explicit Non-Goals); §13 (Implementation Boundary); §14 (Roadmap Relationship) |
| `docs/roadmap-register-and-numbering-policy.md` | §7 (corpus inspection is a precondition); §16.3 (B9.80 non-goals); §20/§22 (B9.84 HADR and closure); §29 (B9.88 NAR); §30 (B9.88 closure — dependency invariant); §42.1 (allocation decision); §42.6 (out-of-scope and non-goals); §42.12 (closure definition); §42.13 (allocation and reconciliation state) |
| `docs/post-b999-architectural-direction-human-architectural-decision-record.md` | §1 (Status); §1.1 (Follow-up Decision Record); §8 (Architectural Rationale); §9 (Execution Architecture Consideration); §10–§11 (B9.12/B9.13/B9.19); §13 (Product Scope Boundary); §14 (Evidence Threshold); §15 (Governance Constraints); §16 (Required Workflow); §17–§18 (Final Decision Statement, Final Status) |
| `docs/post-b999-option-c-bounded-stabilization-validation-human-architectural-decision-record.md` | §1 (Purpose); §1.1 (Explicit non-decision); §1.2 (Evidence boundary); §1.3 (Next authorized phase); §2 (Final Governance State) |
| `docs/B9.6.0-initial-knowledge-specification.md` | §14 (Intel Arc / Battlemage Case) — *inference* hardware context only |
| `castlearq/` | `runner.py` (`ModelRunner`, `LlamaCppRunner`); `model_store.py` (`ModelStore`, `_sha256`); `models.py` (`ArtifactSpec`, `ModelSpec`); `execute_model.py` (`DEFAULT_EXECUTION_TIMEOUT_SECONDS`); `evaluate_compatibility.py`; `evaluation_pipeline.py`; `compatibility_evaluator.py`; `initial_knowledge.py`; `boundary_adapter.py`; `evaluation_adapter.py`; **`training.py` + `training_runner.py` (bounded SFT+LoRA prototype — see §4.2; re-verified 2026-10-16)** |
| `tests/` | `test_training.py` (double-based unit tests for the SFT+LoRA prototype — see §4.2; the CPU smoke test was deliberately omitted, so no real-training validation exists) |
| `pyproject.toml`, `requirements.txt` | Dependency surface (`version = "0.5.1"`, `requires-python = ">=3.11"`, no `dependencies` key; standard-library-only comment) |

### 12.2 Claims independently verified during preparation of this draft

1. The bounded SFT+LoRA prototype in `castlearq/training.py` + `castlearq/training_runner.py` (§4.2); QLoRA not found (no quantization config, no bitsandbytes). The drafting-time absence grep is obsolete.
2. The double-based unit tests in `tests/test_training.py` (§4.2); no real-training validation (CPU smoke test deliberately omitted).
3. That the only `dataset` occurrences are the compatibility-knowledge corpus.
4. The dependency surface: standard library only; no `dependencies` key.
5. That `execute_model` is one-shot with a 600 s default timeout and no job lifecycle.
6. That `ModelStore`/`ArtifactSpec` handle GGUF artifacts with no adapter concept.
7. That evaluation measures compatibility/fit rather than model quality.
8. That inference is delegated through the `ModelRunner` abstraction.
9. That no training *execution* evidence — experiment artifact, adapter file, notebook, report, or run log — exists
   in the repository. A prototype with double-based tests does exist (§4.2); the gap is execution, not code.
10. That `boundary_adapter.py` and `evaluation_adapter.py` are domain-translation
    adapters (B9.12 and B9.8 respectively), **not** LoRA adapters.
11. That no XPU / SmolLM / Arc Pro reference exists in tracked `docs/` records (this untracked draft's own mentions in §§4.1/7.3/8/12.4 excluded — they report claims only to exclude them).
12. The repository baseline recorded in §1.1 (branch, HEAD, origin, working tree,
    tracking state).

### 12.3 Claims inherited but not independently revalidated

1. The `B9.47` product-identity conclusion and its `PRODUCT-IDENTITY-RESOLVED`
   verdict (§14, §16). **Quoted as an audit conclusion, not re-derived here.**
2. The nine missing training responsibilities (§9) — independently *consistent*
   with items 12.2(3)–(8) as re-verified (prototype noted, execution and lifecycle still absent), but the original analysis was not redone.
3. The D9/D11/D12 product-vision positions — quoted; the reasoning behind them
   was not re-examined.
4. The `post-B9.99` §13 scope boundary and §16 workflow — quoted as ratified
   direction.
5. The Option-C record's §1.2 evidence-boundary findings, including
   "P1 Genuine Current Core Problems = 0" and "B9.12/B9.13/B9.19 are already
   implemented". **The underlying audit is not present in `docs/`; these are
   cited, not confirmed.**
6. The B9.99 closure state (§42.13) — accepted as recorded.
7. The reported local experiments (§4.1) — **previously reported, independently
   unverified, and excluded from the evidence base.**

### 12.4 Missing evidence that could materially change the recommendation

1. **Artifacts or a report substantiating the reported B70 / XPU / LoRA
   experiments.** This is the single most consequential gap. If reproducible
   feasibility were documented, condition 9 would improve and Option A's evidence
   rating would rise (§7.3). The human maintainer may hold this evidence; this
   draft could not find it.
2. **Any documented user problem involving model adaptation.** Would move
   conditions 1–2 and materially strengthen Option A.
3. **Any comparison against an external training tool.** Would inform condition 3
   and the later architecture decision.
4. **A reproducible quality evaluation on non-synthetic data.** Would address
   condition 8, which the reported 16/20-vs-15/20 result does not.
5. **External user feedback of any kind.** D12 declares the core thesis itself
   unvalidated; no such evidence exists in the repository.

### 12.5 Conflicts and ambiguities requiring human attention

1. **Internal inconsistency in `docs/post-b999-architectural-direction-…md`.**
   §1.1 (line 58) and Option-C §1.2 (line 45) state "B9.12/B9.13/B9.19 are
   already implemented", while §10 (lines 360–361) states "B9.12 — specification
   exists; implementation not present" and §11 (line 378) states B9.19 "remains
   specification-only/not started". These cannot both be correct. **This draft
   does not rely on either claim** for its training conclusion, but the
   contradiction is material to the stabilization direction and warrants human
   resolution.
2. **Baseline metadata in older records.** `docs/post-b999-architectural-direction-…md` §1
   records `HEAD: d131adf…` and `Working tree: CLEAN`, accurate when written but
   predating commits `b6fde7c` and `873b059`. Preserved deliberately per the
   convention that historical records are not rewritten; §1.1 of this draft
   records its own verified baseline rather than copying it.
3. **Ratification evidence.** Records cited here declare `RATIFIED` in their own
   text. For the two post-B9.99 records, external corroboration exists in that
   the human explicitly authorized committing them unchanged (commit `873b059`).
   No independent attestation exists for the decision text itself. Treated as
   governance evidence, not as proof of independent verification.
4. **"Option" letter reuse.** This HADR uses A–E for training-scope alternatives
   only. The B9.99 allocation (§42.1.1), the post-B9.99 stabilization direction
   (§3), and the bounded-validation decision (§1.3) each use their own unrelated
   A–D sets. All external references in this document are qualified by decision
   title.
5. **Local ref alignment at reconciliation time (supersedes the drafting-time note retained below).** At the 2026-10-16 verification, local `main`, HEAD, and the local `origin/main` ref coincided at `88229ee` (no fetch performed; see §1.1).

   Drafting-time note, retained as history: `main` was 2 commits ahead of `origin/main` (`873b059`, `b6fde7c`); no push authorized by this draft.

---

*End of draft. This document records the ratified human decision (OPTION E, 2026-10-16). See section 11.*
