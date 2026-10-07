# B9.94 — Human Architectural Decision Record

## Acquisition-First Product Direction

---

## 1. Decision Status

```text
DOCUMENT TYPE:     Human Architectural Decision Record (HADR)
SUBJECT:           B9.94 — Acquisition-First Product Direction
DECISION:          SELECTED — OPTION 1 (ACQUISITION-FIRST)
DECISION AUTHORITY: PROJECT OWNER
DECISION STATUS:   SELECTED
IMPLEMENTATION:    NOT PERFORMED
VERIFICATION:      NOT PERFORMED
ROADMAP ALLOCATION: NOT ALLOCATED
CLOSURE:           NOT PERFORMED
CODE IMPACT:       NONE — this record is READ-ONLY with respect to source
```

This record documents a ratified human architectural decision. It remains:

```text
This document does NOT allocate B9.94.
This document does NOT implement B9.94.
This document does NOT verify B9.94.
This document does NOT close B9.94.
This document does NOT reserve, imply or open B9.95 or any later identifier.
This document does NOT modify the roadmap register.
This document does NOT modify source code, tests, configuration or packaging.
This document does NOT create a commit, tag or branch.
```

---

## 2. Baseline

Verified by inspection at the moment this record was written, not assumed:

```text
Branch:                 main
HEAD:                   3fc5231f3569b2f2331f56b01ea1b6eb71def5d6
origin/main:            3fc5231f3569b2f2331f56b01ea1b6eb71def5d6
Remote refs/heads/main: 3fc5231f3569b2f2331f56b01ea1b6eb71def5d6
Ahead/behind:           0 / 0
HEAD subject:           docs: close roadmap block B9.93
Tracked modifications:  none
Staged changes:         none
```

Known untracked files present at this baseline (left untouched by this record):

```text
docs/b993-model-identity-expansion-human-architectural-decision-record.md
docs/post-b990-architectural-decision-preparation.md
```

No commit SHA is fabricated anywhere in this record. No implementation evidence
is claimed anywhere in this record.

---

## 3. Context

The following facts were verified against the published repository and are
recorded here unchanged. This record alters none of them.

```text
B9.80 - B9.92   discovery -> inspection -> selection -> acquisition
                architecture, complete and CLOSED.

B9.92           CLOSED  (CLI discover -> inspect -> select -> acquire)

B9.93           CLOSED  (Explicit Multi-Layer Identity Model).
                Allocation, implementation and closure are published;
                origin/main points at the B9.93 closure commit.
                No post-closure drift exists.

B9.94           NOT ALLOCATED. Not allocated, not implemented, not verified,
                not closed, not reserved. Every pre-existing occurrence of the
                identifier B9.94 in the corpus is an explicit non-allocation.

B9.95+          NOT ALLOCATED.
```

**The architectural situation this record responds to.**

```text
- B9.93 explicitly established the multi-layer identity model: Logical Model,
  Variant, Artifact, Revision, Locator and Storage Identity, governed by
  "no layer may substitute for or be silently promoted to another layer".

- Discovery is identity-free. A discovered artifact carries no logical model
  identity; identity is re-attached only at the explicit
  discovery-to-acquisition mapping boundary through a caller-supplied resolver.

- Provider-declared identity is not authoritative. Declared metadata is L1 and
  untrusted; a provider never becomes the owner of logical model identity.

- The current acquisition path is constrained by the logical-model identity
  admission gate. The curated registry is a single hard-coded mapping from
  (source, repository) to logical model id, and the "downloadable" predicate
  resolves a logical model only when it maps to exactly one locator whose
  source is supported.

- Arbitrary Hugging Face repository acquisition is currently NOT generally
  supported. CastleArq can inspect an arbitrary repository, but acquisition of
  that repository's artifacts is refused unless the repository has an entry in
  the curated registry.

- The current downloadable catalog is deliberately limited. The curated
  registry is the intended acquisition boundary, not an oversight.

- Model Library UX is not implemented. The existing library capability is
  internal, live and stateless; a persistent user-facing library is explicitly
  NOT AUTHORIZED.

- Hardware-aware planning is not implemented. Memory estimation is
  parameter-count driven; context, KV-cache, runtime-buffer and GPU
  layer-offload planning do not exist.

- Runtime/binary provisioning is not implemented. CastleArq requires a
  pre-provisioned runtime binary on PATH and never installs one.
```

None of the above is altered, reopened or superseded by this record.

---

## 4. Human Architectural Decision

The question put to the human:

> What strategic product direction should CastleArq adopt for B9.94?

The human answer:

> **OPTION 1 — ACQUISITION-FIRST**

Formal decision, as ratified:

> CastleArq should evolve from a curated model catalog toward a system capable
> of acquiring user-selected GGUF models from Hugging Face, while strictly
> preserving the separation between logical model identity, repository,
> variant, artifact, revision, locator, and storage identity established by
> B9.93.

```text
Human Architectural Decision: SELECTED — OPTION 1
Decision Authority:           PROJECT OWNER
Decision Status:              SELECTED
Implementation Status:        NOT PERFORMED
Roadmap Allocation Status:    NOT ALLOCATED
Closure Status:               NOT CLOSED
```

This is a decision about **product direction**, not about implementation
mechanics. It authorizes a direction and constrains its shape. It does not
authorize any specific mechanism, module, class, function or CLI surface.

---

## 5. Architectural Intent

### 5.1 Current flow

```text
HF repository
    -> search
    -> inspect
    -> select
    -> identity admission
    -> acquire
    -> store
```

### 5.2 Current limitation

CastleArq can inspect arbitrary Hugging Face repositories, but acquisition is
restricted by a curated logical-model identity registry. Everything upstream of
the identity gate is general; everything downstream of it is restricted to a
deliberately narrow, hand-curated set.

### 5.3 Target direction

```text
HF repository
    -> search
    -> inspect
    -> select
    -> acquisition admission
    -> acquire
    -> store
```

### 5.4 The architectural goal

The goal is to make **acquisition admission** capable of accepting
user-selected GGUF repositories and artifacts **without violating the identity
model established by B9.93**.

The step changes name, not position: the identity gate remains a gate. What may
change is what is permitted to pass through it, and under which explicit,
tested, fail-closed contract.

### 5.5 What is intentionally NOT decided here

The exact implementation mechanism is intentionally NOT decided by this record.
See section 7.

---

## 6. B9.93 Identity Constraints

**B9.93 remains normative.** The following separation is preserved in full and
is a binding constraint on any future B9.94 implementation:

```text
Logical Model    !=  Repository
Logical Model    !=  Variant
Logical Model    !=  Artifact
Logical Model    !=  Revision
Logical Model    !=  Locator
Logical Model    !=  Storage Identity
```

Governing rule, restated from B9.93 and unchanged:

```text
No layer may be substituted for or be silently promoted to another layer.
```

Specifically:

- **Repository must not silently become logical model identity.**
- **Filename must not become logical model identity.**
- **Quantization must not become logical model identity.**
- **Revision must not become logical model identity.**
- **URL / locator must not become logical model identity.**
- **Storage path must not become logical model identity.**
- **Provider-declared identity must not automatically become authoritative.**
- **No identity layer may be silently promoted into another layer.**

The future acquisition mechanism must be designed **around** these constraints,
never by relaxing them implicitly. If an implementation appears to require
collapsing two layers, that is evidence the mechanism is wrong, not evidence
that the constraint should be dropped.

Preserved B9.93 semantics that remain normative:

- Discovery remains identity-free.
- Cardinality remains 1 repository -> 1 logical model (see section 6.1).
- The "exactly one supported locator" acquisition predicate remains the shape
  of the gate.
- Unknown identity fails closed; it is never inferred, guessed or defaulted.
- Revision remains declared provenance and remains excluded from artifact
  identity under the ratified OD-1 decision.
- The B8.1 representation domain remains parallel and unconverged.

### 6.1 Cardinality

```text
1 repository -> 1 logical model
```

This cardinality is preserved unless a future architectural decision explicitly
authorizes another cardinality.

B9.94 must NOT silently introduce:

```text
1 repository -> N logical models
```

If arbitrary Hugging Face acquisition creates a genuine need for different
cardinality semantics, that need must be identified and recorded as a
**separate future architectural decision**. It must not be resolved
incidentally, as a side effect of an implementation choice.

---

## 7. Acquisition Admission Direction

### 7.1 The seam

The current identity gate is an **architectural seam**, not merely an
implementation detail:

```text
model_id
    -> downloadable_locator
        -> repository
            -> discovery
                -> artifact
                    -> acquisition
```

Discovery produces everything needed to acquire, and stops at identity.
Acquisition requires identity, and cannot start without it. The two halves of
the product meet at a single curated table.

### 7.2 The decision

The decision is to **investigate and evolve the admission boundary** so that
user-selected repositories and artifacts can become acquirable, under an
explicit contract that preserves section 6 in full.

### 7.3 What this record does NOT prescribe

This record MUST NOT, and does not, prescribe the final identity-generation or
identity-assignment algorithm.

Mechanisms that remain open for a future B9.94 implementation design include,
without limitation:

- explicit user-supplied logical identity;
- deterministic identity derivation under a formally defined contract;
- catalog admission;
- repository-backed identity registration;
- another mechanism discovered during B9.94 implementation design.

**No mechanism is selected by this record.** The architectural decision is
about product direction. The mechanism is a separate, later, evidence-backed
step, and the roadmap register's existing allocation mechanism governs it.

---

## 8. Scope

The scope of this record is:

```text
DOCUMENTATION ONLY — a recorded human architectural decision.

Authorizes:
  - the strategic direction "Acquisition-First";
  - the constraint that any future implementation must preserve the B9.93
    multi-layer identity model;
  - the constraint that acquisition admission must be explicit and fail
    closed.

Does NOT authorize:
  - any source, test, configuration, packaging or CLI change;
  - any roadmap allocation;
  - any implementation mechanism;
  - any of the items enumerated in section 9.
```

---

## 9. Explicit Non-Goals

Acquisition-first does **NOT** mean any of the following. Each item below is a
**future or separate architectural question**. Selecting this direction does not
authorize any of them, and none of them may be treated as decided, implied,
scheduled or bundled because it appears in this record.

```text
Product surfaces
  - a GUI
  - a Model Library UI
  - a persistent user-facing Model Library
  - a database
  - a persistent catalog

Retrieval and ordering
  - semantic search
  - fuzzy search
  - ranking
  - recommendation

Providers
  - multiple providers
  - provider federation

Storage
  - ModelStore redesign
  - manifest redesign
  - filesystem layout change
  - migration redesign
  - multi-revision storage coexistence

Identity
  - expanding repository:model cardinality from 1:1 to 1:N
  - provider-declared identity becoming authoritative
  - collapsing repository into logical model identity
  - filename or quantization becoming a model identity

Execution and hardware
  - hardware-aware planning
  - context / KV-cache calculation
  - GPU layer-offload planning
  - execution-parameter emission
  - provisioning llama.cpp binaries
  - runtime/binary preparation

Platform
  - Windows support
  - macOS support
  - WSL2 support
  - any non-Linux execution claim

Legacy and adjacent architecture
  - converging B8.1 ModelIdentity
  - removing or deprecating legacy ModelSource
  - redesigning run versus execute
  - changing ModelExecutionService
  - changing the runtime architecture
```

---

## 10. Future Decision Surfaces

The following remain **separate future decision surfaces**. Each is stated as a
question, not as a plan.

### 10.1 Hardware Planning

Future question:

> Should CastleArq evolve from compatibility/admission toward hardware-aware
> execution planning involving VRAM, RAM, context, KV cache, GPU layer
> offload, runtime buffers and execution parameters?

**B9.94 does NOT decide this.**

### 10.2 Runtime Autonomy

Future question:

> Should CastleArq acquire, pin, verify, prepare or otherwise provision
> llama.cpp / runtime components?

**B9.94 does NOT decide this.**

### 10.3 Cross-platform Support

Future question:

> Should CastleArq claim and implement Windows / macOS support?

**B9.94 does NOT decide this.**

### 10.4 Model Library UX

Future question:

> Should CastleArq expose a persistent user-facing Model Library?

**B9.94 does NOT decide this.** Acquiring more models does not authorize a
library that persists, curates or orders them.

### 10.5 Identity Convergence

B8.1 `ModelIdentity` remains **parallel / non-converged** unless a separate
decision authorizes convergence.

**B9.94 does NOT decide this.**

### 10.6 Intended user value

Recorded as direction, not as a promise of specific syntax:

```text
CastleArq should eventually be able to move beyond:

    "CastleArq knows about these specific registered models."

toward:

    "CastleArq can acquire a GGUF artifact selected by the user from
     Hugging Face."
```

A conceptual user flow, described as direction only:

```text
castlearq search <query>
    -> castlearq inspect <repository>
        -> select variant / artifact
            -> acquire selected artifact
```

This is conceptual direction. No final CLI syntax is promised, specified or
authorized by this record.

---

## 11. Decision Rationale

Recorded in neutral architectural terms.

1. **It addresses the current largest acquisition limitation.** Only a narrow
   curated set of models is directly acquirable today. Discovery is general;
   acquisition is not. This is the most consequential gap between what
   CastleArq can see and what it can obtain.

2. **It builds directly on completed architecture.** B9.80 through B9.93
   already provide the discovery, inspection, selection, mapping, acquisition
   and identity layers this direction extends. Nothing here requires replacing
   a completed boundary; it requires evolving one seam.

3. **B9.93 supplies the required identity vocabulary.** Because logical model,
   repository, variant, artifact, revision, locator and storage identity are
   now explicitly separated, acquisition can be widened while remaining precise
   about which layer any given value belongs to. Without B9.93's vocabulary,
   widening acquisition would have meant conflating layers.

4. **It provides immediate product value.** Users gain access to models they
   actually want, through a capability that already exists end to end.

5. **It is incrementally implementable.** It requires no GUI, no persistent
   database, no persistent catalog, no semantic search, no ranking, no
   recommendation, no multi-provider architecture and no runtime provisioning.

6. **It preserves later independent directions.** Hardware-aware planning and
   runtime autonomy remain fully available as subsequent, independent roadmap
   directions. Selecting acquisition-first consumes neither of them.

7. **It strengthens the ground for a future Model Library without requiring
   one.** A library needs acquirable content and a coherent identity story.
   This direction supplies the first; it does not build the second.

---

## 12. Architectural Risks

### R1 — Identity ambiguity

Allowing arbitrary repositories without a clear logical identity contract could
undermine B9.93 by making "the same model" mean different things in different
paths.

**Mitigation:** identity admission must be explicitly designed and explicitly
tested. Ambiguity must fail closed, never resolve by inference, fuzzy match,
basename heuristic or default.

### R2 — Repository/model conflation

Using a repository name as logical model identity would collapse the Repository
and Logical Model layers and would violate the multi-layer identity model.

**Mitigation:** the repository remains a separate layer. Admission must bind a
logical model to a repository without merging them.

### R3 — Scope explosion

Arbitrary acquisition creates obvious pressure toward ranking, recommendation, a
GUI, a persistent catalog, multiple providers, curation and refresh — all of
which are explicit non-goals.

**Mitigation:** keep B9.94 acquisition admission **narrowly scoped**. Anything
that orders, persists, curates or ranks acquired models is out of scope by
construction, not merely by omission.

### R4 — Catalog semantics

Relaxing or removing the curated registry could silently change the meaning of
"downloadable model", which is currently a precise, deterministic predicate.

**Mitigation:** define acquisition admission **explicitly**. Do not delete the
concept of the gate in order to widen it; redefine what may pass through it,
under a stated contract, with the existing curated behavior preserved unless
explicitly superseded.

### R5 — Provider coupling

A Hugging Face repository may legitimately be the acquisition source for an
artifact, while remaining a provider-declared value that must not become the
authoritative owner of CastleArq logical model identity.

**Mitigation:** provider identity remains non-authoritative unless a future
decision explicitly changes this. Source and identity stay separate concerns.

---

## 13. Future Implementation Success Criteria

Architectural success criteria for a future B9.94 implementation. These are
architectural, not implementation-step criteria. They are stated here for the
future block that would carry them; this record neither satisfies nor verifies
any of them.

```text
AC1  User-selected GGUF acquisition is architecturally supported WITHOUT
     collapsing repository into logical model identity.

AC2  The existing B9.93 identity layers remain distinct: Logical Model,
     Variant, Artifact, Revision, Locator and Storage Identity are still
     separately observable and separately governed.

AC3  Existing deterministic revision-aware acquisition semantics remain valid,
     including the OD-1 decision that revision does not participate in
     artifact identity.

AC4  Discovery remains capable of inspecting repositories independently of
     acquisition identity; discovery stays identity-free.

AC5  Acquisition admission is explicit and fails closed when required
     identity information is unavailable. No identity is fabricated, guessed
     or defaulted.

AC6  The implementation does not silently introduce repository-to-logical-model
     cardinality beyond the ratified 1:1 contract. Any need for another
     cardinality is escalated as a separate architectural decision.

AC7  Existing curated acquisition behavior remains valid unless explicitly
     superseded by the B9.94 implementation design.

AC8  No GUI, database, persistent catalog, multi-provider, hardware-planning or
     runtime-provisioning behavior is introduced unless separately authorized.

AC9  Existing B9.80 - B9.93 contracts remain regression-safe.

AC10 The future implementation remains incrementally extensible toward
     Hardware Planning, Runtime Autonomy and Model Library UX, without
     pre-empting any of those decisions.
```

---

## 14. Roadmap Relationship

```text
B9.92  CLOSED
B9.93  CLOSED
B9.94  strategic direction SELECTED but NOT YET ALLOCATED
B9.95+ NOT ALLOCATED
```

This record does not, and must not be read as:

```text
- creating a roadmap allocation record;
- assigning a block number beyond B9.94;
- altering the lifecycle state of B9.94 in the roadmap register;
- reserving B9.94 or any later identifier;
- creating, amending or superseding any ADR;
- reopening any closed block or any existing decision.
```

The roadmap register remains authoritative for allocation. When an allocation is
made, it will be made through that document's existing formal mechanism and
under that document's numbering policy, in a separate step, by the project
owner.

---

## 15. Human Approval

```text
Human Architectural Decision:  SELECTED — OPTION 1 (ACQUISITION-FIRST)
Decision Authority:            PROJECT OWNER
Decision Status:               SELECTED
Posture:                       INCREMENTAL / IDENTITY-PRESERVING
B9.93 identity model:          PRESERVED AND NORMATIVE
Cardinality:                   1 repository -> 1 logical model, PRESERVED
Identity admission mechanism:  NOT DECIDED BY THIS RECORD

IMPLEMENTATION:   NOT PERFORMED
VERIFICATION:     NOT PERFORMED
PUBLICATION:      NOT PERFORMED
CLOSURE:          NOT PERFORMED

B9.94 is a SELECTED STRATEGIC DIRECTION and is NOT ALLOCATED.
```

The decision is recorded. It is not reopened, re-compared or re-scored by this
record.
