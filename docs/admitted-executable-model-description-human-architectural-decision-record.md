# Explicit Admitted ModelSpec / Executable Model Description

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:          Human Architectural Decision Record (HADR)
SUBJECT:                Explicit Admitted ModelSpec / Executable Model Description
DECISION:               SELECTED — OPTION C
DECISION AUTHORITY:     PROJECT OWNER
DECISION STATUS:        ACCEPTED — HUMAN ARCHITECTURAL DIRECTION
IMPLEMENTATION:         NOT AUTHORIZED
ROADMAP ALLOCATION:     NONE — NO ROADMAP BLOCK IS ALLOCATED
B9.98+ OPTION D:        PRESERVED
B9.99:                  NOT AUTHORIZED / NOT ALLOCATED
CODE IMPACT:            NONE — THIS RECORD IS DOCUMENTATION ONLY
```

This HADR records an architectural direction only. It does not authorize
implementation, roadmap allocation, B9.99 creation, B9.99 reservation, code
changes, commits, tags, pushes, or releases.

```text
ARCHITECTURAL DECISION ANALYSIS ONLY
NO ROADMAP ALLOCATION
NO B9.99
```

---

## 2. Baseline and Evidence

The decision was prepared against the following repository baseline:

```text
Branch:          main
HEAD:            0247a830a106b52b03e0066da5cbaaed8523396f
origin/main:     0247a830a106b52b03e0066da5cbaaed8523396f
HEAD relationship: HEAD == origin/main; ahead/behind 0/0
Tracked changes: none
Staged changes:  none
```

Six previously identified local governance documents were present as untracked
files and were left untouched:

```text
docs/b993-model-identity-expansion-human-architectural-decision-record.md
docs/b994-acquisition-first-human-architectural-decision-record.md
docs/b994-identity-admission-boundary-and-acquisition-separation-human-architectural-decision-record.md
docs/b998-revision-coexistence-and-artifact-lifecycle-human-architectural-decision-record.md
docs/post-b990-architectural-decision-preparation.md
docs/post-b998-architectural-direction-human-architectural-decision-record.md
```

The completed real-model acceptance drill verified the curated Qwen path:
live Hugging Face search and inspection, an explicitly selected Q4_K_M GGUF,
an existing CastleArq-managed artifact whose declared SHA-256 matched the
actual bytes, the external `llama` runtime, real one-shot inference, and a
real two-turn CLI chat that retained context. It established a working curated
vertical slice; it did not establish arbitrary-repository acquisition or
execution.

The remaining product boundary is a user-selected GGUF from a public
Hugging Face repository that is not already curated. Discovery and inspection
can describe such a repository and its declared files, but those observations
alone do not create an admitted executable model.

---

## 3. Context

The current architecture separates remote discovery, identity admission,
acquisition resolution, artifact storage, compatibility evaluation, and
execution admission. A discovered artifact is remote declared metadata. The
existing acquisition flow maps a selected artifact to an `ArtifactSpec` only
when a caller supplies a logical model identity. The current production
composition and executable resolver do not provide a complete admitted
non-curated remote-model path.

Identity admission is necessary to give CastleArq a stable, CastleArq-owned
logical name for a non-curated repository. It is not sufficient for execution:
an identity registration says which logical model CastleArq associates with a
source locator; it does not establish the model architecture, executable
capabilities, artifact integrity, support in the installed runtime, or
compatibility with the selected device.

The current compatibility and execution path consumes both a model
description and a selected artifact. Therefore a future non-curated path needs
a CastleArq-owned executable model description, distinct from the identity
it names and the artifact it references. That description must carry only
evidence-qualified model facts, preserve unknown values, and enter the same
strict compatibility and execution-admission path used for existing models.

This decision addresses only the narrow product boundary:

```text
public Hugging Face repository
+ explicitly selected single GGUF artifact
+ explicit user admission
+ existing external llama.cpp runtime
```

“Arbitrary” does not mean arbitrary architectures, formats, repository
contents, shard sets, automatic selection, automatic admission, or unrestricted
execution.

---

## 4. Decision

> **Select Option C — Explicit Admitted ModelSpec / Executable Model
> Description.**

A future user-selected, non-curated remote model must have:

1. a CastleArq-owned logical model identity, explicitly admitted and stable
   across processes;
2. a separate executable model description associated with that identity,
   containing only appropriately sourced model facts; and
3. a separately selected and locally resolved artifact, evaluated against
   current runtime evidence before execution is admitted.

Identity admission does not create an acquisition binding, an executable
description, a ModelStore artifact, compatibility, or permission to execute.
Acquisition remains a separate operation. Strict compatibility evaluation
remains authoritative, and execution admission remains mandatory.

The intended direction is:

```text
Hugging Face repository
        ↓
DiscoveredArtifact
        ↓
explicit user selection
        ↓
CastleArq logical identity
        ↓
explicit admission
        ↓
Executable Model Description
        ↓
Acquisition binding
        ↓
local ArtifactSpec / ModelStore artifact
        ↓
strict compatibility evaluation
        ↓
execution admission
        ↓
external runtime
```

---

## 5. Identity Boundary

CastleArq logical identity remains a distinct, deterministic logical-model
identity. For a non-curated repository, the identity must be CastleArq-owned
and stable across processes; it must not be silently assigned from provider
metadata or from a selected file.

The identity is not any of the following:

```text
Hugging Face repository
artifact filename
revision
declared or computed checksum
artifact_id
local filesystem path
acquisition locator
runtime compatibility result
```

Repository and source identify where discovery/acquisition occurs. Filename,
quantization, checksum, and revision describe or identify aspects of a
selected artifact under their existing contracts. A ModelStore path is a
storage address. None substitutes for logical model identity.

This HADR does not alter the existing identity derivation, curated authority,
identity-admission registry, artifact identity, or revision rules.

---

## 6. Explicit Admission

Discovery remains observational:

```text
search   -> reports remote candidates as declared
inspect  -> reports remote variants/artifacts as declared
```

Neither `search` nor `inspect` automatically:

- creates or persists a logical identity;
- creates an acquisition binding;
- creates an executable model description;
- selects an artifact on the user's behalf;
- creates a ModelStore artifact; or
- authorizes compatibility or execution.

The user must explicitly select a concrete artifact and explicitly admit its
logical model identity. Admission is a CastleArq identity decision, not an
assertion that provider claims are true and not execution approval. Explicit
execution admission remains downstream of compatibility evaluation.

---

## 7. Executable Model Description

A non-curated admitted model requires a CastleArq-owned executable model
description because identity alone does not supply the model facts consumed by
resolution and compatibility evaluation.

Existing `ModelSpec` may be reused only if its catalog and recommendation
semantics can be cleanly separated from the semantics of an admitted
executable model and its evidence. In particular, estimates, recommendations,
or provider-declared metadata must not be promoted into verified model facts.
If safe reuse is not possible, a focused executable-model representation or
evidence-bearing wrapper is preferable.

The exact representation, persistence encoding, and division of fields
between existing `ModelSpec` and any focused new type remain unresolved
implementation-design questions. This HADR selects the responsibility and
boundary, not the concrete schema.

> **B9.99 resolution note (documentation-only; as-built).** These
> implementation-design questions were resolved by the B9.99
> implementation, without altering the responsibility or boundary selected
> above. The concrete representation is a focused, evidence-bearing
> `AdmittedModelRecord` — accepted model claims (`architecture`,
> `parameter_count_b`, `context_length`, `format`) plus
> `declaration_provenance`, `observations`, and `reconciliations` — which
> is the durable authority (`castlearq/admitted_models.py`). Persistence
> uses a versioned JSON registry (`admitted-models.json`, `_FORMAT_VERSION
> = 1`) with atomic, fsynced writes. `ModelSpec` is a downstream projection,
> not the authority: `project_to_model_spec_kwargs` maps accepted claims to
> `ModelSpec` fields for the evaluation consumer, defaulting unknowns to
> `None`/`"Unknown"`. Estimates and provider-declared metadata are never
> promoted into verified facts. This note records as-built behavior; it does
> not reopen the ratified decision or authorize further implementation.

The executable description is not:

- the logical identity itself;
- a repository or acquisition binding;
- an `ArtifactSpec` or ModelStore manifest;
- a compatibility verdict; or
- a runtime observation.

---

## 8. Evidence Semantics

Declared data and CastleArq-verified or runtime-observed facts must remain
distinguishable.

### Declared evidence

The following remain source declarations unless independently verified:

- Hugging Face repository and repository metadata;
- filename-derived quantization;
- declared architecture;
- declared revision; and
- declared checksum and size.

### Verified or observed evidence

The following are established by CastleArq or the installed runtime through
their existing evidence paths:

- local artifact existence and filesystem safety;
- actual artifact size;
- checksum comparison against a declared checksum, when one is available;
- GGUF metadata actually read from the local artifact;
- detected runtime capability; and
- runtime/device observations for the particular artifact and context.

Unknown values remain unknown. No value is fabricated from a repository name,
filename, tag, missing revision, absent checksum, or a successful identity
registration. A declared checksum is not a successful checksum verification
until compared with the local bytes. A positive runtime load observation is
limited to that observation; it is not a general guarantee of successful
inference, model quality, or resource sufficiency.

---

## 9. Compatibility and Execution Admission

The existing strict compatibility evaluation remains authoritative. Identity
admission, a valid GGUF container, and a verified checksum each answer
different questions and none bypasses evaluation.

The selected local artifact and executable model description must be evaluated
against the currently detected runtime and selected backend using the existing
evidence semantics. Explicitly unsupported required architecture or runtime
facts deny execution. Required unknown architecture/runtime facts remain
insufficient evidence and deny execution. They must not be changed to
“supported” merely to enable the non-curated path.

When the installed runtime explicitly rejects a valid GGUF, execution is
denied and the relevant evidence is surfaced. When architecture or another
required fact is unknown, the result remains unknown/insufficient rather than
being inferred from HF tags or names.

An absent revision remains unknown/unpinned provenance. An absent checksum
remains unknown integrity evidence. This decision does not introduce a new
checksum-required policy or change the current evaluation/admission policy for
existing catalog or imported artifacts.

---

## 10. Acquisition Boundary

Acquisition remains separate from identity admission. The acquisition binding
continues to mean:

```text
model_id -> source + repository
```

It answers where CastleArq acquires a model, not what the model is, which
artifact is selected, or whether the runtime can execute it.

Acquisition receives a selected artifact mapped to an `ArtifactSpec` that
references the admitted `model_id` and retains its source, repository,
filename, declared format/quantization, declared size/checksum, revision, and
acquisition locator under their existing meanings. These are structured,
separate facts; a URL alone is not an identity or artifact description.

The selected user artifact remains distinct from the model identity and
acquisition binding. Acquisition itself does not silently create an identity
or binding. ModelStore persists and validates the artifact; it does not become
identity authority.

Revision remains declared acquisition provenance and does not become model
identity or artifact identity. Existing B9.96/B9.97/B9.98 locator, revision,
single-address, and mismatch-blocking semantics are preserved. This decision
does not introduce automatic replacement, coexistence, history, or rollback.

---

## 11. Resolver Boundary

The future resolution responsibility is to combine a logical identity with a
selected, usable local artifact and return the executable model description
and artifact evidence required by compatibility evaluation:

```text
logical model identity
        +
selected local artifact
        ↓
executable model description
        +
artifact/runtime evidence
```

Resolution must not treat a raw repository, filename, hash, revision, label,
or storage path as a logical model identity. The same resolved model/artifact
semantics must feed `execute` and `chat`; their strict evaluation and execution
admission behavior must remain shared. Existing curated catalog models and
locally imported artifacts retain their current behavior.

The exact resolver representation and persistence lookup for an admitted
executable description are not specified by this decision.

> **B9.99 resolution note (documentation-only; as-built).** The resolver
> representation and persistence lookup were implemented by B9.99.
> `admitted_resolution.resolve_model_for_evaluation(model_id)` reads the
> durable admitted registry and returns an `AdmittedResolution` carrying the
> projected `ModelSpec`, the underlying record, and a `from_admitted` flag.
> It is wired read-only into `castlearq/resolver.py` for non-curated admitted
> identities. Unresolved material declared-vs-observed conflicts fail closed:
> `AdmittedMaterialConflictError` (subclass of `AdmittedResolutionError`) is
> raised by type and surfaced by the resolver as
> `ModelArtifactResolutionError`, so both evaluation and execution deny rather
> than proceed on unverified claims. Curated and imported-artifact paths are
> unchanged. This note records as-built behavior; it does not reopen the
> ratified decision or authorize further implementation.

---

## 12. Alternatives

### Option A — Dynamic CastleArq Identity

**Not selected as the complete direction.** A deterministic, explicitly
admitted CastleArq identity is necessary and remains part of Option C, but
identity alone does not supply an executable model description or the
compatibility evidence needed by the current resolver/evaluator.

### Option B — Artifact-First Execution

**Rejected.** Treating artifact identity as the model/execution identity risks
conflating a file with the logical model it represents and conflicts with the
existing model-description-plus-artifact evaluation contract. It would also
require a parallel execution/evaluation path or a redefinition of those
boundaries.

### Option C — Explicit Admitted ModelSpec / Executable Model Description

**Selected.** An explicitly admitted CastleArq logical identity is associated
with an executable model description distinct from the selected artifact and
acquisition locator. The description and artifact enter the existing strict
compatibility and execution-admission path.

### Option D — Evidence-Based Alternative

No stronger evidence-backed alternative was identified. The verified curated
Qwen vertical slice and the observed non-curated handoff gap support Option C;
they do not support a runtime rewrite or an artifact lifecycle redesign.

---

## 13. Consequences

### Positive

- Logical model identity remains distinct from repository, artifact,
  filename, checksum, revision, and storage path.
- Search and inspection remain observational; admission is explicit and
  auditable.
- Acquisition binding remains separate from identity admission and ModelStore.
- The existing strict compatibility evaluation and execution-admission gate
  remain authoritative for CLI execution and chat.
- Existing runtime, runner, ModelStore, artifact identity, and revision
  semantics need no redesign as a consequence of this decision.
- Curated and imported-artifact paths can retain their current semantics while
  a future admitted non-curated description is resolved explicitly.

### Negative and unresolved

- A new executable-model responsibility must be represented and made
  available to resolution and evaluation.
- Production acquisition and execution composition will need deliberate
  integration and cross-boundary tests; registry unit tests alone are
  insufficient.
- The exact reuse boundary for `ModelSpec`, persistence representation, and
  evidence provenance on executable-description fields remain unresolved.

> **B9.99 resolution note (documentation-only; as-built).** The above was
> unresolved at ratification and was resolved by B9.99. The `ModelSpec`
> reuse boundary is projection, not reuse: `AdmittedModelRecord` is the
> durable authority and `ModelSpec` is produced for the evaluation consumer
> via `project_to_model_spec_kwargs` (unknowns default to
> `None`/`"Unknown"`; no estimate or provider-declared value is promoted
> into a verified fact). Persistence is a versioned JSON registry with
> atomic, fsynced writes. Declaration and observation provenance remain in
> the durable EMD record (`declaration_provenance`, per-observation
> `observation_provenance`, and auditable `reconciliations`). The one
> remaining item is optional and unproven, not a demonstrated defect or
> requirement: provenance is **not** propagated into the projected
> evaluation `ModelSpec` (which carries no provenance field); no current
> test or product evidence shows the evaluation/admission consumer must
> distinguish declared-only from verified evidence beyond the existing
> binary material-conflict gate.
>
> **EMD status: CLOSED-AS-BUILT** for the responsibility and boundary
> selected by this decision. This note records as-built behavior and does
> not reopen the ratified decision, authorize further implementation, or
> allocate any roadmap block.
- Unknown required compatibility evidence must continue to block; some
  non-curated models may therefore be admitted as identities but not admitted
  for execution.
- The selected scope is intentionally narrow and does not make arbitrary
  repository contents executable.

---

## 14. Non-Goals

This decision does not authorize or imply:

- arbitrary formats or non-GGUF runtimes;
- arbitrary Hugging Face repository contents;
- multi-file or sharded-model orchestration;
- automatic model selection or automatic identity admission;
- automatic acquisition-binding creation;
- runtime/backend redesign, new inference engines, or
  Transformers/PyTorch integration;
- multi-GPU orchestration;
- artifact identity or content-addressable storage redesign;
- revision coexistence, model history, rollback, automatic replacement, or
  garbage-collection redesign;
- federation, GUI, or model-library user-experience expansion;
- HTTP discovery, HTTP download, HTTP streaming, or public model hosting;
- public network exposure; or
- any B9.99 creation, reservation, selection, or allocation.

---

## 15. Governance Compatibility

```text
B9.98+ OPTION D:
PRESERVED — No Successor Yet / Defer Successor Allocation

B9.99 STATUS:
NOT AUTHORIZED / NOT ALLOCATED

IMPLEMENTATION:
NOT AUTHORIZED

ROADMAP IMPACT:
NONE AT THIS TIME
```

This architectural direction is not a roadmap allocation. If implementation
is later proposed and requires a roadmap block, it must follow the established
sequence:

```text
evidence
    → human architectural decision
    → formal allocation
    → implementation
```

This HADR records an architectural direction only. It does not authorize
implementation, roadmap allocation, B9.99 creation, B9.99 reservation, code
changes, commits, tags, pushes, or releases.

---
