# Human Architectural Decision Record — Executable Model Description + Evidence Provenance

## 1. Context

CastleArq has a working curated Qwen GGUF path: Hugging Face discovery and
inspection, local artifact recognition, ModelStore validation, external
`llama` execution, and a real two-turn chat were operationally verified. That
acceptance establishes the curated vertical slice, not a path for an arbitrary
non-curated repository.

The existing architecture has separate concepts for discovery, logical
identity, identity admission, acquisition binding, artifacts, local storage,
compatibility evaluation, and execution admission:

- [ModelSpec](../castlearq/models.py) is a static catalog description with
  estimates and recommendation-oriented fields.
- [ArtifactSpec](../castlearq/models.py) describes an acquirable artifact
  and refers to a logical `model_id`; its `artifact_id` is derived separately.
- [DiscoveredArtifact](../castlearq/discovery.py) carries remote declared
  artifact metadata.
- [identity admission](../castlearq/identity_admission.py) persists an
  explicit forward association from source/repository to logical identity.
- [acquisition resolution](../castlearq/acquisition_resolution.py) stores
  an independently explicit `model_id → source + repository` binding.
- [ModelStore](../castlearq/model_store.py) persists artifact manifests and
  derives local artifact state from manifest expectations and filesystem
  observations.
- [compatibility evaluation](../castlearq/evaluate_compatibility.py) and
  [the evaluation adapter](../castlearq/evaluation_adapter.py) consume a
  model description and artifact. The adapter maps selected `ModelSpec`
  values into strict evaluation input but has no general field-level
  provenance representation.
- The [GGUF reader](../castlearq/gguf_reader.py) obtains physical metadata
  from a local file, and the [runtime artifact observer](../castlearq/runtime_artifact_observer.py)
  produces artifact/runtime observations for a particular execution
  environment.

Search and inspection are observational. Identity admission does not itself
create an executable description, acquisition binding, artifact, compatibility
verdict, or execution permission. The previous Option C HADR established the
direction but left the executable-description representation and evidence
provenance semantics unresolved.

This record resolves those two architectural questions. It does not authorize
implementation or settle schemas, class names, storage formats, commands, or
roadmap allocation.

## 2. Architectural Question

What does an Executable Model Description represent, and how must CastleArq
preserve the provenance and trust level of information used to decide whether
an acquired artifact can run?

The following remain distinct concepts and authorities:

```text
MODEL IDENTITY
        ≠
EXECUTABLE MODEL DESCRIPTION
        ≠
ARTIFACT IDENTITY
        ≠
REVISION
        ≠
EVIDENCE
        ≠
RUNTIME CAPABILITY
```

## 3. Definitions

### Logical Model Identity

The stable CastleArq-owned identifier for one logical model. For a
non-curated model it is established through explicit identity admission and
must remain deterministic and recoverable across processes.

Identity is not the Hugging Face repository, filename, revision, checksum,
artifact ID, or local storage path. None of those values may be promoted to or
substituted for logical identity.

### Executable Model Description

A CastleArq-owned, durable description associated with one logical model
identity. It states what model CastleArq currently associates with that
identity and carries the model-level claims needed by the compatibility
evaluator, together with their declared/verified status and provenance.

It is the model-level input to evaluation, not a verdict that the model is
compatible or executable. It is not:

- the logical identity itself;
- the selected physical artifact or its manifest;
- the acquisition binding or repository locator;
- the ModelStore or an artifact-state authority;
- the current runtime, hardware, or runtime capability; or
- permission to execute.

The description may carry human-readable model metadata, but display/catalog
metadata has no execution authority merely because it is present.

### Evidence

Information supporting a claim about a model, artifact, or execution
environment. Evidence is scoped to the thing observed and the time/context of
observation. Its source and epistemic class must remain identifiable.

### Artifact and Runtime Evidence

Artifact evidence is about a concrete local artifact: existence, filesystem
safety, actual size, checksum comparison, and GGUF metadata read from its
bytes. Runtime evidence is about a particular runtime/device context:
detected capability and observations of that runtime loading that artifact.
These do not become durable model identity or general model facts.

## 4. Evidence / Provenance Semantics

**Selected: Option C — Separate Evidence Layers.**

Declared and verified/observed evidence remain distinct structures and
authorities. They must not be flattened into one unqualified field whose value
can be overwritten as it travels through discovery, admission, persistence,
or evaluation. Each execution-relevant claim must remain attributable to its
origin and evidence class; artifact/runtime observations must additionally
remain scoped to the artifact and environment they concern.

This is a semantic decision, not a prescribed schema. It does not require
persisting every raw observation or defining exact field names.

### Declared / Remote Evidence

Examples include Hugging Face repository metadata, declared architecture or
parameter count, declared quantization, filename-derived characteristics,
declared revision, declared size, and declared checksum. These remain
untrusted claims even when syntactically valid, plausible, or repeated by
multiple remote metadata fields.

### Verified / Observed Evidence

Examples include local file existence and safety, actual file size, comparison
of actual bytes to a declared checksum, actual GGUF metadata read from local
bytes, current runtime capability, and runtime/device observations for a
specific artifact and context.

“Verified” is claim-specific: verifying a checksum establishes a comparison
against the declared digest; it does not prove model identity or runtime
compatibility. Reading GGUF architecture establishes metadata present in that
file; it does not prove the repository description was accurate or that the
runtime supports the model.

Provenance must travel with claims into evaluation. A declared architecture
must never become a verified architecture merely because both use the same
human-readable value. Unknown is represented as unknown, not as a fabricated
claim or a positive default.

### Why not implicit or flat field-level provenance?

Implicit provenance (Option A) relies on callers remembering where a value
came from. The current types already demonstrate the risk: `ModelSpec`
contains catalog estimates/recommendations, while the adapter converts some
fields into strict model facts without general field-level provenance.

Field-level provenance in a single flattened value record (Option B) is better
than implicit inference, but it still makes it possible for one source's value
to replace another source's value in the same slot. Separate evidence layers
make disagreement and unknown states explicit without changing one claim into
another. Provenance remains associated with each claim within its layer; the
layers are not a trust-by-file-location shortcut.

## 5. Unknown and Conflict Semantics

Unknown remains unknown. No verified fact may be inferred from a repository
name, HF declaration, filename, quantization suffix, model name, successful
identity admission, or missing metadata.

Unknown does not have one universal operational consequence:

- Unknown display metadata is acceptable when it is not needed by evaluation.
- Missing revision remains unpinned/unknown provenance. When no revision is
  requested, existing behavior remains; a requested known revision continues
  to use the existing B9.97/B9.98 rules.
- Missing checksum remains unknown integrity evidence. It is not a successful
  verification, and the existing behavior that permits artifacts without a
  declared checksum is not changed by this record.
- Missing required architecture or other required compatibility evidence
  remains insufficient evidence and does not admit execution.
- Missing or unavailable required runtime capability denies execution.
- Runtime artifact-support/backend unknowns retain only the narrowly scoped
  treatment already present in the current admission projection. This ADR does
  not broaden that exception for admitted models.

Conflicts are handled by claim scope and evidence class:

1. A lower-trust declaration never overwrites or outranks verified evidence.
2. If a declared execution-relevant claim disagrees with actual GGUF evidence,
   retain both claims and surface the discrepancy. The declaration is not
   silently rewritten. The discrepancy does not authorize execution; the
   description must be reconciled with the observed artifact before it can be
   treated as a consistent executable description.
3. If two verified/observed claims conflict, or the sources are incomparable
   for the claim, compatibility is not established. The conflict is
   non-admitting until resolved; optimistic evidence cannot cancel it.
4. A declared checksum that differs from the actual bytes remains an integrity
   failure under the existing ModelStore behavior and denies use of that
   artifact. No alternate declaration may mask the mismatch.
5. A conflict or unknown cannot be converted into a pass by identity
   admission, acquisition, or execution request.

These rules preserve the existing strict compatibility and mandatory
execution-admission boundaries; they do not define a new general conflict
resolution framework or alter current policy exceptions.

## 6. Executable Model Description Decision

The description represents **durable model-level claims associated with a
logical identity, with explicit evidence class and provenance, that are
necessary inputs to compatibility evaluation**.

Its minimum conceptual responsibility is:

- associate claims with exactly one CastleArq logical model identity;
- distinguish model-level claims from artifact-specific and runtime-specific
  evidence;
- retain declared/unknown status and claim provenance;
- provide model-level information required by the existing strict evaluator,
  without asserting compatibility or execution permission.

The content boundary is:

| Information | Architectural owner / role |
|---|---|
| Logical `model_id` association | Identity authority; required association, not a model fact inferred from metadata. |
| Display name, provider/author, family, task, descriptive tags | Informational/catalog metadata; not execution authority unless a future evaluator explicitly requires a separately evidenced claim. |
| Architecture, parameter information, context, model capabilities | Model-level claims only when relevant to compatibility; each remains declared, verified, or unknown with provenance. |
| Supported artifact format | Admitted description's declared/allowed format scope; it does not prove the selected file has that format. The artifact and physical checks establish artifact facts. |
| Repository/source | Acquisition locator and claim provenance; not identity and not an executable description's authority. |
| Filename, quantization, declared size/checksum, download URL, revision | Selected-artifact/acquisition metadata under existing `DiscoveredArtifact`/`ArtifactSpec` semantics; not copied into the description as model identity or model fact. |
| Actual size/checksum/GGUF metadata | Evidence about the selected local artifact; retain in artifact evidence/ModelStore's existing authority, not as a replacement for the manifest. |
| Runtime capability and load observation | Current runtime/environment evidence; ephemeral and scoped to the invocation/artifact. |
| Compatibility verdict and execution admission | Evaluator and admission authorities; never stored as a model-description claim. |

The description is associated with the selected artifact during resolution
for evaluation, but does not contain or replace the artifact. A repository or
revision may be retained as provenance for declared claims, but is not an
identity key or a substitute for the independently persisted acquisition
binding.

## 7. ModelSpec Relationship Decision

**Selected: Option D — Introduce a distinct executable-model description.**

This selects distinct architectural semantics and an independent evidence
boundary. It does not prescribe a Python class, module, persistence encoding,
or duplicate evaluator. Evidence-qualified facts may be projected into the
existing strict evaluation machinery where appropriate.

The choice is based on current code:

- `ModelSpec` is the catalog type and carries estimates and recommendation
  fields (`task`, supported runtimes/backends, quantization recommendations).
- `metadata_estimated` exists but does not provide field-level provenance to
  consumers.
- The evaluation adapter copies selected architecture, parameter, and context
  values into strict model facts without a general declaration-versus-
  verification channel.
- `ModelSpec` is not persisted or retrieved through an admitted-model
  authority; the resolver receives catalog entries or synthesizes an imported
  artifact description.

| Option | Advantages | Disadvantages / evidence-based risk | Disposition |
|---|---|---|---|
| A — Reuse `ModelSpec` unchanged | No new description boundary; existing catalog/evaluator input already exists. | Cannot represent claim provenance or distinguish an admitted description from estimates/recommendations; current adapter treats selected fields as model facts. | Rejected: does not satisfy the provenance decision. |
| B — Extend `ModelSpec` | Could add provenance while reusing current consumers. | Changes the catalog contract and risks making optional admitted semantics affect curated consumers; a single mutable field set still invites source replacement and unclear persistence authority. | Rejected: broader compatibility/regression surface without evidence that catalog and admitted semantics are equivalent. |
| C — Wrap `ModelSpec` with explicit evidence | Reuses its descriptive fields and can attach provenance. | Wrapper must still prevent recommendation/estimate fields from being mistaken for authoritative claims; current adapter accepts `ModelSpec`, not a provenance-bearing wrapper. Persistence and consumer boundaries remain ambiguous unless it becomes a distinct representation in practice. | Rejected as the authoritative description. Projection/reuse of eligible fields remains possible. |
| D — Distinct executable-model description | Separates admitted model claims from catalog recommendations and supports durable provenance without changing artifact identity or the evaluator's authority. | Adds a conceptual representation and requires a projection/integration boundary; details belong to future implementation design. | **Selected.** |
| E — Other | No repository evidence supports a superior alternative. | Would add an unsupported architectural concept. | Not selected. |

## 8. Artifact Relationship

The existing identity/artifact separation remains:

```text
Logical Model Identity
        |
        +---- Executable Model Description
        |
        +---- Acquisition Binding
        |
        +---- Selected Artifact
                    |
                    +---- ArtifactSpec
                    +---- ModelStore
```

`ArtifactSpec` remains the acquisition/artifact description and its `model_id`
continues to reference logical identity. ModelStore remains the authority for
persisting and deriving local artifact state. The executable description
cannot replace, absorb, or redefine either one.

The artifact is the physical object selected, acquired, verified, resolved,
and passed to the external runtime. Artifact-specific evidence is scoped to
that artifact and is not generalized to every artifact associated with the
same logical model.

## 9. Revision Relationship

**Revision is provenance, not identity.**

Revision may be retained as declared source/artifact provenance, but it must
not define logical model identity, redefine `ArtifactSpec.artifact_id`, or
become a verified checksum. Absence remains unknown; it is never defaulted to
`main`.

The existing B9.97 independent revision channel and B9.98 single-address
replacement semantics remain unchanged:

- same known requested/stored revision: existing artifact may satisfy the
  request;
- different known revision: blocked, without replacement;
- unknown stored revision with known request: blocked;
- requested revision `None`: preserve existing behavior.

This record introduces no revision history, coexistence, rollback, or
replacement protocol.

## 10. Compatibility Evaluation Relationship

The intended conceptual flow is:

```text
Executable Model Description
        +
selected Artifact
        +
verified physical evidence
        +
runtime evidence
        ↓
strict compatibility evaluation
        ↓
execution admission
```

The description supplies evidence-qualified model-level claims. The artifact
supplies physical facts and artifact-scoped observations. The current runtime
supplies environment-specific capability and observation. The strict
evaluator assesses compatibility; execution admission decides whether the
execution boundary may proceed.

Identity admission is not an evaluation result and cannot bypass the
evaluator. A failed, conflicting, or required-unknown claim remains
non-admitting. A future integration must use the same strict evaluation and
execution-admission boundary rather than adding a second permissive path.

## 11. Persistence / Authority Boundaries

### Must survive a fresh process

- logical identity and explicit admission;
- executable model description and provenance needed to reconstruct its
  claims;
- explicit acquisition binding.

These are durable authorities, but remain separate authorities. Persistence
does not turn a declaration into verified evidence.

### Already persisted elsewhere

- selected/acquired artifact metadata and declared provenance in the
  `ArtifactSpec`/ModelStore manifest;
- artifact identity and locally derived integrity/state under existing
  ModelStore semantics.

The executable description is not a duplicate manifest and cannot become
ModelStore identity authority.

### Runtime/ephemeral

- current runtime capability and device availability;
- artifact-load observation for the current runtime/artifact/context;
- active execution and chat-session state.

Such evidence may be retained for diagnostics only under a future decision;
it is not a durable, unconditional compatibility assertion. Any persisted
observation would remain scoped to its artifact, runtime, and observation
context and must not replace a fresh capability check.

This is an authority and semantic boundary only. It does not decide where or
how these records are stored.

## 12. Curated vs Explicitly Admitted Models

Curated catalog models and explicitly admitted non-curated models remain two
sources of model description, not two execution architectures:

- curated identity and catalog metadata retain their current authority and
  behavior;
- an explicitly admitted non-curated identity resolves to its distinct
  evidence-bearing executable description;
- both descriptions are associated with a selected local artifact and enter
  the same strict compatibility evaluation, execution admission, preflight,
  and external runtime boundaries.

This direction does not redesign or migrate the curated path. Any projection
from curated `ModelSpec` into the common evaluation input must preserve its
current semantics. No declared remote metadata may be silently treated as
verified merely to make the two sources appear uniform.

## 13. Alternatives Considered

### Provenance architecture

| Option | Correctness | Provenance safety | Compatibility | Persistence | Complexity | Recommendation |
|---|---|---|---|---|---|---|
| A — Implicit provenance | Low: consumers must infer origin. | Low: equal values from different sources are indistinguishable. | Superficially high, but current adapter already demonstrates the ambiguity. | No explicit provenance to reconstruct. | Low initially; high risk of hidden trust coupling. | Reject. |
| B — Field-level provenance in flattened fields | Medium/high: source is explicit per value. | Medium: a single field can still be overwritten or selected without preserving disagreement. | Requires adapting consumers to provenance-bearing values. | Can persist provenance, but authority and conflict behavior still need discipline. | Medium. | Reject as the primary structure. |
| C — Separate declared and verified evidence layers | High: preserves evidence class and disagreement. | High: declarations cannot silently replace physical/runtime observations. | Existing declared discovery and physical evaluation boundaries map naturally; adapters must consume the correct layer. | Durable model claims and artifact/runtime-scoped observations stay distinct. | Medium: explicit boundary and projection needed. | **Select.** |
| D — Other | No evidence of a better fit. | Undetermined. | Would add an unsupported model. | Undetermined. | Unjustified. | Reject. |

### Executable description representation

The `ModelSpec` alternatives are evaluated in [§7](#7-modelspec-relationship-decision).
The selected representation is distinct from `ModelSpec` in meaning and
authority, while permitting an explicit projection into existing evaluator
inputs. No specific implementation shape is selected.

## 14. Decision

The architectural decisions are:

**A. Executable Model Description representation:** a distinct, durable,
CastleArq-owned executable-model description associated with a logical model
identity. It contains only model-level claims and provenance needed by
compatibility evaluation; it is neither an artifact manifest nor a verdict.

**B. Evidence provenance semantics:** separate declared and
verified/observed evidence layers. Claims retain their origin, scope, and
unknown status. Declarations are never promoted to verified facts by
copying, persistence, admission, or matching values.

**C. ModelSpec relationship:** do not use `ModelSpec` unchanged, extend it as
the authoritative admitted description, or use a wrapper as the authoritative
record. Preserve it for curated catalog/recommendation semantics; an explicit
projection of eligible facts into existing strict evaluator inputs is allowed
only when provenance and current curated behavior remain intact.

Unknown and conflict semantics are resolved in [§5](#5-unknown-and-conflict-semantics).
Unknown required evidence and unresolved material conflicts do not authorize
execution. Existing narrowly scoped unknown policy exceptions remain
unchanged.

This resolves the architectural ambiguity identified by the previous
readiness audit. It does not authorize implementation, a roadmap allocation,
or a change to the preserved successor-deferral decision.

## 15. Consequences

### Positive

- Logical identity, model description, artifact identity, revision, evidence,
  and runtime capability retain separate meanings and authorities.
- Declared HF metadata cannot silently become verified local/runtime evidence.
- Unknown values remain explicit; required unknowns cannot be converted into
  execution permission.
- Artifact and runtime evidence remain properly scoped.
- The current strict evaluator and execution-admission path can remain the
  compatibility and authorization authorities.
- Curated models can retain their current catalog semantics while eventually
  converging with admitted models at the same evaluation/execution boundary.

### Costs and constraints

- A distinct admitted description and a provenance-preserving evaluation
  projection are architectural responsibilities that a future implementation
  must satisfy.
- Description persistence and fresh-process resolution are required, but
  storage mechanics are intentionally undecided.
- Evidence disagreement must remain visible and fail closed when it cannot be
  reconciled from authoritative evidence.
- Some identities may be admitted while remaining non-executable because
  required evidence is unknown, conflicting, or incompatible.

## 16. Explicit Non-Goals

This HADR does not decide or authorize:

- CLI command names, exact classes, JSON/schema fields, filenames, database
  format, or storage implementation;
- ModelStore, identity, acquisition, resolver, evaluator, or runtime
  implementation changes;
- implementation sequencing, test implementation, or roadmap block number;
- arbitrary formats, non-GGUF runtimes, multi-file/shard orchestration, new
  inference engines, or runtime/backend redesign;
- model coexistence, revision history, rollback, automatic replacement, CAS,
  or garbage-collection redesign;
- automatic identity admission or automatic acquisition binding;
- GUI/model-library UX, HTTP discovery/download, federation, public model
  hosting, or public network exposure;
- B9.99 allocation, creation, reservation, or selection.

## 17. Governance Status

This HADR refines the previously recorded Option C architectural direction. It
is a governance decision about semantics only:

```text
B9.98+ OPTION D:
No Successor Yet / Defer Successor Allocation — PRESERVED

B9.99:
NOT AUTHORIZED / NOT ALLOCATED

IMPLEMENTATION:
NOT AUTHORIZED

ROADMAP ALLOCATION:
NONE
```

This ADR does not authorize implementation, roadmap allocation, B9.99
creation or reservation, code changes, commits, tags, pushes, or releases.
