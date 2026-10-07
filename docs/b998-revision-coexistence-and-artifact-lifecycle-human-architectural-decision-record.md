# B9.98 — Revision Coexistence and Artifact Lifecycle

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:      Human Architectural Decision Record (HADR)
SUBJECT:            B9.98 — Revision Coexistence and Artifact Lifecycle
DECISION:           SELECTED — OPTION A
DECISION AUTHORITY: PROJECT OWNER
ALLOCATION:         NOT ALLOCATED
IMPLEMENTATION:     NOT AUTHORIZED
VERIFICATION:       NOT PERFORMED
CLOSURE:            NOT CLOSED
CODE IMPACT:        NONE — this record is documentation only
```

This is a local-only decision record. It does not allocate B9.98, modify the
roadmap register, authorize implementation, or claim verification or closure.

---

## 2. Baseline

Baseline verified before recording this decision:

```text
Branch:          main
HEAD:            3268f8336ed4f979fa0be88a0dd747ef99e8b458
origin/main:     3268f8336ed4f979fa0be88a0dd747ef99e8b458
HEAD subject:    3268f83 feat(acquisition): implement revision-aware acquisition
Tracked changes: none
Staged changes:  none
Untracked:       four previously known local-only governance documents
```

The four pre-existing local-only documents were left unchanged.

---

## 3. Context

B9.97 ratified Option C — Independent Revision Channel. It carries revision
separately through acquisition and persists it as non-identity artifact
metadata. Revision does not participate in `model_id`, `artifact_id`, or
acquisition binding identity, and does not change the `locator_resolver`
contract.

The current implementation has these relevant properties:

```text
ArtifactSpec.artifact_id
  = content_id, when present;
    otherwise the established digest of source|repository|filename|quantization
  revision is excluded

ModelStore
  stores the artifact and its manifest at the established artifact address
  records revision as metadata

DownloadPlanner
  reports a healthy artifact at that address as ALREADY_DOWNLOADED
  without establishing that its revision satisfies a different requested revision

Downloader
  does not publish over an existing artifact file
```

The roadmap records that artifacts differing only by revision share the
current `artifact_id` and storage directory, and that multi-revision
coexistence was left as a future question. B9.97 explicitly excluded
historical revision management, multi-revision lifecycle, and automatic
artifact replacement. The current implementation therefore does not establish
a replacement lifecycle merely because revision is carried and persisted.

The concrete architectural gap is that an existing healthy artifact can occupy
the requested artifact address while its stored revision differs from the
requested revision. That situation must not be silently interpreted as
satisfying the request.

---

## 4. Decision

### Selected Option A — Single Current Artifact State + Explicit Revision-Aware Replacement Policy

CastleArq will continue to maintain a **single current physical artifact state
at the established artifact address**. Revision remains lifecycle metadata and
does not become part of artifact identity.

When an existing artifact is healthy but its stored revision does not satisfy
the requested revision, the system MUST NOT silently treat the existing
artifact as already satisfying that request. The mismatch must enter an
**explicit revision-aware lifecycle/replacement decision**.

This decision does not authorize unconditional or automatic overwriting. Any
future implementation must define a safe transition from the current artifact
state to the newly requested revision, preserving artifact integrity and
avoiding partial publication or unsafe interference with active use.

> Single current state does not mean silent overwrite.

This selects an explicit replacement/lifecycle direction rather than
revision-keyed physical coexistence. It does not specify the transition
mechanism or authorize its implementation.

---

## 5. Rationale

Option A addresses the demonstrated mismatch between requested and stored
revision while retaining the current single-address storage model. Repository
evidence does not establish simultaneous local revision coexistence as a
product requirement.

The alternatives are not selected:

```text
Option B — Revision-Keyed Physical Coexistence
  Not selected: it adds simultaneous revision storage and requires additional
  retention and consumer-selection semantics not established as necessary.

Option C — Content/Artifact Deduplication Layer
  Not selected: current content_id use is limited to imported content, and the
  repository does not establish a need for shared physical storage,
  reference ownership, or garbage collection across revision states.

Option D — Revision-Aware Lifecycle Registry
  Not selected: ModelStore already owns artifact manifests and derives local
  artifact state. A separate registry would introduce another artifact
  lifecycle authority without evidence that it is required.
```

Option A is the narrowest selected architecture that addresses the demonstrated
gap without assuming multi-version retention, adding an identity layer, or
creating a second competing artifact registry.

---

## 6. Consequences

### Positive

- Existing identity boundaries are preserved.
- ModelStore remains responsible for artifact storage and local artifact state,
  not model identity, identity admission, or acquisition binding authority.
- Premature multi-version storage is avoided.
- Revision mismatch has a defined architectural place: an explicit
  lifecycle/replacement decision rather than silent satisfaction.
- A future implementation can remain bounded to this lifecycle transition.

### Negative and unresolved

Implementation and its own decision/verification gates will still need to
determine:

- how stored revision and requested revision are compared;
- how legacy manifests without a revision are treated;
- what exact condition authorizes replacement;
- how active artifact use is protected;
- how replacement publication is made safe and atomic;
- whether any previous state is recoverable if replacement fails.

This record does not resolve those implementation details.

---

## 7. Explicit Exclusions

B9.98 does NOT authorize:

```text
multi-revision local coexistence
revision history or historical version management
rollback management
automatic or unconditional artifact replacement
broad artifact garbage-collection redesign
content-addressed storage or content deduplication architecture
new model, artifact, storage, or acquisition-binding identity systems
provider federation
GUI or Model Library work
automatic discovery-to-admission
automatic discovery-to-acquisition or automatic binding
changes to locator resolution semantics
```

---

## 8. Protected Architectural Invariants

Any later implementation must preserve:

1. `revision != model_id`.
2. `revision != artifact_id`; revision does not enter the established
   `artifact_id` derivation.
3. `revision != acquisition_binding_id`; revision does not enter acquisition
   binding identity.
4. Revision remains independent from every other established identity key.
5. Identity Admission remains explicit, persistent, forward-only, and separate
   from ModelStore.
6. ModelStore does not become identity or identity-admission authority.
7. Discovery remains advisory and does not become acquisition authority.
8. Acquisition Resolution remains separate from Identity Admission.
9. Locator resolution does not become responsible for artifact lifecycle
   history or replacement.
10. No second competing artifact registry is introduced.
11. Existing legacy artifacts and manifests remain interpretable; absence of
    revision is not silently reinterpreted as a matching revision.
12. The B9.97 independent revision channel and explicit caller authority remain
    intact.

---

## 9. Relationship to B9.97

B9.97 remains valid and closed. It established revision-aware acquisition,
independent revision propagation, and persistence of revision as
non-identity metadata. It deliberately did not establish historical revision
management, multi-revision lifecycle, or automatic replacement.

This record captures a narrowly scoped follow-up decision concerning lifecycle
handling when stored and requested revisions differ. It does not retroactively
reinterpret B9.97 as having solved replacement or lifecycle semantics, and it
does not change B9.97's identity or locator-resolution contracts.

---

## 10. Governance State

| Stage | State |
|---|---|
| Candidate discovery | COMPLETE |
| Architectural analysis | COMPLETE |
| Human decision | SELECTED — OPTION A |
| ADR recording | COMPLETE |
| Roadmap allocation | NOT ALLOCATED |
| Implementation | NOT AUTHORIZED |
| Verification | PENDING |
| Closure | NOT CLOSED |

---

## 11. Final Architectural Statement

**The selected direction is one current physical artifact state at the
established artifact address, with explicit revision-aware handling when a
healthy stored artifact does not satisfy a requested revision. Revision remains
metadata/state independent of model identity, artifact identity, acquisition
binding identity, and locator resolution. This decision does not authorize
automatic overwriting, simultaneous multi-revision storage, a revision history
system, a second artifact registry, or implementation. B9.98 remains
unallocated.**
