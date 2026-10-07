# B9.94 — Identity Admission Boundary and Acquisition Separation

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:      Human Architectural Decision Record (HADR)
SUBJECT:            B9.94 — Identity Admission Boundary and Acquisition Separation
DECISION:           ACCEPTED — IDENTITY ADMISSION / ACQUISITION RESOLUTION SEPARATION
DECISION AUTHORITY: PROJECT OWNER
DECISION STATUS:    ACCEPTED — HUMAN ARCHITECTURAL DECISION
PRECEDES:           B9.94 Increment 1 (deterministic identity derivation)
                    B9.95 (persistent forward-only identity admission)
IMPLEMENTATION:     NOT AUTHORIZED by this record
ROADMAP ALLOCATION: NONE — this record does NOT allocate B9.96
CLOSURE:            NOT PERFORMED by this record
CODE IMPACT:        NONE — this record is documentation only
```

### Reconciliation note

The former `ACCEPTED — OPTION D` header was a documentation error. The Option D
defined in §7, “Make ModelStore authoritative for identity to repository,”
remains a rejected alternative. The accepted decision is the boundary stated in
§3, §4 and §12: Identity Admission remains forward-only and Acquisition
Resolution is a separate responsibility; ModelStore is not identity authority.
This correction changes no implementation or downstream architectural
decision. B9.95, B9.96 and B9.97 remain valid and are not reopened. This is a
documentation/governance reconciliation only.

This record is read-only with respect to source. It creates no block,
allocates no identifier, authorizes no implementation, and closes no
roadmap entry.

---

## 2. Context

B9.94 Increment 1 introduced **deterministic derived model identity**: a pure
function mapping `(source, repository)` to a `model_id`, composed of a
normalized readable base plus a SHA-256 suffix over the raw locator. It kept
`logical_model_id()` curated-only and deliberately left the admission
resolver unwired.

B9.95 introduced **persistent forward-only identity admission**: a standalone
JSON registry that remembers admitted identities under `curated -> persisted ->
derived` authority, with immutable bindings and fail-closed conflicts.

Both blocks intentionally **stop at model identity**. Acquisition enters
through `model_id`: `ModelAcquisitionService.acquire(model_id)` resolves the
repository via `downloadable_locator`, which reads exclusively from the curated
static mapping. A non-curated **admitted** identity therefore has no path into
acquisition today.

This exposed a seam between identity admission and acquisition:

```text
(source, repository)  --->  model_id            (Identity Admission — exists)
model_id              --->  acquisition locator (acquisition resolution — absent)
```

**The seam does not mean Identity Admission is incomplete.** Admission's
contract is the forward mapping, and the forward mapping is complete. The
missing edge belongs to a different architectural concern.

---

## 3. Decision

> **Identity Admission is a complete, closed model-identity concern.** It maps
> `(source, repository)` to `model_id` under `curated -> persisted -> derived`
> authority, with deterministic pure derivation and immutable forward-only
> persistence.

> **The mapping from an admitted `model_id` to an acquisition locator is a
> separate architectural concern and MUST NOT be implemented by extending the
> Identity Admission Registry.**

> **Revision selection and artifact resolution remain downstream acquisition
> responsibilities.**

---

## 4. Identity Admission Boundary

Identity Admission **owns**:

```text
curated identity lookup
deterministic derived identity
persistent identity admission
immutable bindings
forward lookup
```

Identity Admission **does NOT own**:

```text
reverse lookup                 (model_id -> repository)
revision                       (acquisition provenance)
artifact identity              (artifact_id)
provider semantics             (source stays opaque)
Hugging Face behaviour
ModelStore                     (artifact storage, not identity authority)
download authorization
acquisition resolution
```

The registry remains forward-only. No reverse index may be persisted and no
reverse operation may be added to it.

---

## 5. Acquisition Boundary

Only what is already decided:

```text
model_id
    ->  future acquisition-resolution concern
    ->  acquisition locator
    ->  revision / variant / artifact
    ->  ModelStore
```

> **The contract and authority model for `model_id -> acquisition locator` are
> NOT decided by this record.**

This ADR does not design, specify or authorize that future system.

---

## 6. Revision and Artifact Identity

The already-ratified distinctions stand unchanged:

```text
model_id              logical model identity
(source, repository)  external repository locator
revision              acquisition provenance
artifact_id           artifact identity under the existing acquisition contract
```

- revision is intentionally **excluded** from `artifact_id` (the ratified
  OD-1 decision);
- two revisions of the same repository therefore **share** a logical
  `model_id`;
- different artifacts and variants remain distinguishable downstream by
  `filename` and `quantization`, which do participate in artifact identity.

---

## 7. Rejected Alternatives

### A — Leave the status quo as the future acquisition solution

Rejected. The current implementation is **complete** for identity admission
but does **not** solve acquisition resolution, and therefore cannot serve as
the future acquisition architecture. Deferral is not a decision; it leaves the
seam undefined.

### B — Revision-aware Identity Admission

Rejected. It conflates logical identity with acquisition provenance and
conflicts with the established identity-layer separation. Making `model_id`
revision-dependent would also destroy admission immutability.

### C — Reverse lookup inside the Identity Admission Registry

Rejected. It violates the forward-only registry boundary and makes identity
persistence responsible for acquisition resolution. It would also make the
acquisition gate depend on mutable on-disk state.

### D — Make ModelStore authoritative for identity to repository

Rejected. `ModelStore` is artifact-addressed storage
(`<root>/<model_id>/<artifact_id>/manifest.json`), not identity authority.
Placing identity authority there would violate the separation already
recorded for B9.95.

---

## 8. Consequences

### Positive

- Identity semantics remain stable and provider-agnostic.
- B9.94 and B9.95 remain small, coherent and independently verifiable.
- The registry remains portable and deterministic.
- Future acquisition architecture can evolve independently.
- Revision handling remains downstream.
- ModelStore remains an artifact/storage concern.
- Existing curated acquisition behaviour is untouched.

### Negative

- A separate acquisition-resolution architecture is still required.
- There is currently **no path** from a non-curated admitted identity to
  acquisition.
- Another architectural decision will be required before broad acquisition
  support can consume admitted identities.

---

## 9. Future Decision Surface

The following remain **UNdecided** and are not resolved by this record:

```text
how model_id resolves to a repository
whether resolution is static, persisted, or derived
resolution authority
reverse cardinality
repository rename behaviour
provider / source namespace semantics
network vs offline resolution behaviour
resolution reproducibility
manifest integration
revision selection contract
variant / revision interaction
```

---

## 10. Scope Boundary

This record does **NOT** authorize:

```text
acquisition implementation
reverse registry lookup
acquisition-service rewiring
ModelStore changes
artifact identity changes
revision identity changes
CLI changes
Model Library
runtime integration
Hugging Face-specific identity logic
B9.96 allocation
```

---

## 11. Relationship to B9.94 and B9.95

```text
B9.94 Increment 1
  -> deterministic model identity derivation

B9.95
  -> persistent forward-only identity admission

This record
  -> formally closes the architectural question around the boundary
     between identity admission and acquisition
```

This record does **not** reopen B9.94 implementation and does not modify any
closed roadmap record.

---

## 12. Final Architectural Statement

**Identity Admission is a complete, closed model-identity concern. It maps
`(source, repository) -> model_id` under `curated -> persisted -> derived`
authority, with deterministic pure derivation, immutable forward-only
persistence, and no reverse lookup, revision, artifact identity, provider
semantics, ModelStore dependency or acquisition authority. The mapping from an
admitted `model_id` to an acquisition locator is a separate architectural
concern, owned downstream and not implemented by extending the Identity
Admission Registry. Revision selection and artifact resolution remain
acquisition responsibilities. No identity layer may be substituted for or
promoted into another to satisfy this boundary.**
**No existing artifact identity contract is altered by this record.**