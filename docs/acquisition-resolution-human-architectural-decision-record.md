# Acquisition Resolution — Human Architectural Decision Record

## PRE-ALLOCATION DECISION — NOT A ROADMAP BLOCK

---

## 1. Decision Status

```text
DOCUMENT TYPE:      Human Architectural Decision Record (HADR)
DOCUMENT CLASS:     PRE-ALLOCATION — no roadmap block is minted or claimed
SUBJECT:            Acquisition Resolution
DECISION:           ACCEPTED — Option D (responsibility boundary)
                     + Option B (independent persistent acquisition binding)
DECISION AUTHORITY: PROJECT OWNER
DECISION STATUS:    ACCEPTED — HUMAN ARCHITECTURAL DECISION
IMPLEMENTATION:     NOT AUTHORIZED
ROADMAP ALLOCATION: NONE — this record allocates NO block, including B9.96
CODE IMPACT:        NONE — this record is documentation only
```

This record decides architecture, not delivery. It creates no identifier,
allocates no block, changes no source, and closes nothing.

---

## 2. Baseline

```text
Branch:          main
Published HEAD:  f51a05eeb881518b5d210fc35b0417e62abe760d
origin/main:     f51a05eeb881518b5d210fc35b0417e62abe760d
B9.93:           CLOSED
B9.94:           CLOSED  (Increment 1 at 37.12; architecture at 37.13)
B9.95:           CLOSED  (section 38.11)
B9.96:           NOT ALLOCATED
```

---

## 3. Context

Identity Admission is closed and complete. It maps a locator to a logical
model identity:

```text
(source, repository)  ->  model_id
```

Acquisition, however, is entered with a `model_id` and must recover a locator
before it can discover anything. Today that recovery happens in exactly one
place:

```text
ModelAcquisitionService.acquire(model_id)      acquisition_service.py:267
  -> _resolve_repository(model_id)             acquisition_service.py:300
     -> locator_resolver(model_id)             injected, acquisition_service.py:250
        -> downloadable_locator(model_id)      model_identity.py:164
           -> iterates SOURCE_REPOSITORY_TO_MODEL_ID ONLY   model_identity.py:151-155
```

That curated mapping holds **one** entry. `resolve_admitted_model_id()`,
`identity_admission.lookup()` and `identity_admission.register()` have **zero
production consumers**. An admitted identity therefore cannot reach
acquisition.

B9.94 established, as a permanent boundary, that this gap MUST NOT be closed by
extending Identity Admission. This record decides how the gap is actually
closed.

---

## 4. Existing Architecture

Verified against the published repository:

```text
Discovery      HuggingFaceDiscoveryProvider.inspect   (identity-free)
  carries      repository, source, revision, filename,
                quantization, download metadata          discovery.py:76-107
Selection      select_discovered_artifact  — variant/revision are selectors
Mapping        map_discovered_artifacts    — revision transported verbatim
Planning       DownloadPlanner             — canonical /resolve/<revision>/
Storage        ModelStore.save_manifest    — already persists model_id,
                source, repository, revision               model_store.py:300-316
Runtime        ModelArtifactResolver.resolve(model_id)  — a SEPARATE concern
```

Two facts materially bound the future design:

- **Revision is already fully implemented downstream** (declared at
  `huggingface_discovery.py:328`, selected at `discovery_selection.py:180`,
  transported at `acquisition_mapping.py:142`, URL-canonicalized at
  `downloads/planner.py:242`). This architecture must not revert it.
- **ModelStore already records `model_id`, `source`, `repository` and
  `revision`.** It receives a fully-formed `ArtifactSpec` and resolves
  nothing. **The seam therefore terminates BEFORE ModelStore**, and no
  ModelStore change is implied.

---

## 5. Architectural Problem

An admitted `model_id` cannot be resolved to an acquisition locator, because
the only existing resolution authority is the curated static mapping and it
contains only the curated entry. The information needed to close the gap —
`source` and `repository` — is present at admission time and is deliberately
**not** recoverable from `model_id`, because the derived identity digest is
one-way and because reversing it would violate the forward-only boundary.

---

## 6. Decision

> **Acquisition Resolution is an independent responsibility from Identity
> Admission. A separate Acquisition Resolver resolves an admitted `model_id`
> to an acquisition locator using independent persistent acquisition
> bindings.**

This decision combines two complementary dimensions:

```text
D = the RESPONSIBILITY BOUNDARY   (a separate concern; never in admission)
B = the STATE MECHANISM          (its own bindings; never identity records)
```

They are complementary, not competing: **D decides who is responsible; B
---

## 7. Responsibility Boundary

```text
Identity Admission:     (source, repository) -> model_id
Acquisition Resolution:  model_id             -> acquisition locator
Acquisition:             locator -> discovery -> revision/variant
                         -> ArtifactSpec -> ModelStore
```

These are three distinct responsibilities. They MUST NOT be collapsed into one
identity system.

---

## 8. Persistent Acquisition Binding Boundary

An acquisition binding associates an admitted logical model identity with an
acquisition locator. It is:

```text
NOT an identity record
NOT a reverse index of Identity Admission
NOT a modification of model_id
NOT owned by ModelStore
```

A binding answers "where do we acquire this model from", never "what is this
model". Identity Admission answers only the latter.

---

## 9. Identity Admission Boundary (preserved unchanged)

```text
1.  Curated identity remains authoritative.
2.  Persisted identity remains authoritative over derived identity.
3.  Derived identity remains deterministic and pure.
4.  logical_model_id() remains curated-only.
5.  Identity Admission remains forward-only.
6.  Identity Admission MUST NOT gain reverse lookup.
7.  Identity Admission MUST NOT resolve acquisition locators.
8.  Identity Admission MUST NOT know ModelStore.
9.  Identity Admission MUST NOT know provider-specific acquisition semantics.
10. Identity Admission MUST NOT select revisions or variants.
```

None of these is modified, weakened or reinterpreted by this record.

---

## 10. Acquisition Resolution Boundary

```text
1.  Acquisition Resolution is a separate architectural concern.
2.  It accepts an admitted model_id.
3.  It may use independent persistent acquisition bindings.
4.  Its bindings are not identity records.
5.  Its bindings are not reverse indexes of Identity Admission.
6.  It does not mutate or redefine model_id.
7.  It does not redefine identity derivation.
8.  It does not modify artifact_id.
9.  It does not own ModelStore.
10. It does not select revision or variant.
11. It terminates at the acquisition locator boundary.
12. Provider-specific semantics remain downstream in acquisition/discovery.
```

---

## 11. Revision and Artifact Identity

```text
model_id              logical model identity
(source, repository)  acquisition locator
revision              declared/provider revision selected during acquisition
variant               selected model artifact variant
artifact_id           artifact identity
local path            ModelStore concern
```

- `ArtifactSpec` carries `revision` (`models.py:79`).
- `artifact_id` **excludes** `revision` (`models.py:81-93`, ratified OD-1).
- **Revision MUST NOT become part of `model_id`.**
- **Revision MUST NOT be added to `artifact_id`** to solve this seam.

---

## 12. Accepted Architecture

```text
(source, repository)
        |
        v
Identity Admission
        |
        v
    model_id
        |
        v
Acquisition Resolution
        |
        v
(source, repository)
        |
        v
Discovery
        |
        v
revision / variant selection
        |
        v
ArtifactSpec
        |
        v
ModelStore
        |
        v
runtime
```

The `model_id -> (source, repository)` edge now exists as an explicit,
separately owned responsibility, terminating before `ArtifactSpec`.

---

## 13. Rejected Alternatives

### Option A — Static curated acquisition mapping

Simple, deterministic, no persistence. **Rejected as the architectural
direction for generalized acquisition resolution**: it cannot naturally support
arbitrary admitted repositories, requires manual curated extension, and does
not scale with CastleArq's discovery direction.

### Option B — Independent persistent acquisition binding

Supports arbitrary admitted models; deterministic and offline once bound;
preserves Identity Admission separation; avoids reverse lookup; requires no
ModelStore coupling. **Accepted as the state mechanism**, while its lifecycle
remains undecided.

### Option C — Derived reconstruction from model_id

**Rejected.** The identity digest is not intended to be inverted. Doing so
violates established identity-layer separation and would reconstruct
acquisition identity from logical identity.

### Option D — Separate Acquisition Resolver

**Accepted** as the responsibility boundary. Complementary to Option B.

### Option E — Discovery-backed resolution

**Rejected as the ownership model.** Discovery must not become an identity
authority. It may supply acquisition metadata, but it must not replace the
Acquisition Resolution boundary or become a source of logical identity.
---

## 14. Consequences

### Positive

- Identity Admission stays small, pure and unchanged.
- Arbitrary admitted identities can eventually reach acquisition.
- The curated path keeps working exactly as before.
- Resolution is deterministic and available offline once bound.
- No ModelStore, `artifact_id`, revision or provider change is implied.
- A future Model Library can consume acquisition bindings without becoming
  an architectural authority.

### Negative

- Persistent state is introduced by Acquisition Resolution.
- Binding lifecycle, authority and conflict semantics remain undefined.
- Two binding sources (curated map and persistent bindings) must coexist,
  which needs an explicit precedence decision.
- The current curated-only path remains in place until a future block
  implements resolution; nothing changes at runtime by this record.

---

## 15. Undecided Future Questions

The following are **future architectural decisions** and are deliberately
NOT resolved here:

```text
 1. Who creates an acquisition binding?
 2. Is binding creation automatic after admission, or explicit?
 3. What is the authoritative source for a binding?
 4. Can one model_id have multiple acquisition locators?
 5. If multiple locators are allowed, how is one selected?
 6. What happens when a repository is renamed?
 7. What happens when an acquisition source becomes unavailable?
 8. Can bindings be deleted?
 9. Can bindings be updated?
10. What conflict policy applies?
11. What schema should persistent acquisition bindings use?
12. Where should the acquisition binding store live?
13. What environment or configuration controls its location?
14. Does acquisition resolution need provenance or audit information?
15. How should offline resolution behave when no binding exists?
16. How should legacy curated mappings coexist with persistent bindings?
17. Should existing curated mappings be migrated into bindings?
18. Should acquisition resolution support aliases?
19. What exact object or type represents an acquisition locator?
20. How should provider-specific acquisition metadata be represented?
```

Whether runtime should resolve derived identities is a **separate** future
decision surface and is not decided here.

---

## 16. Scope Boundary

This record does **NOT**:

```text
allocate B9.96
allocate any future B9.x block
implement an Acquisition Resolver
implement persistent acquisition bindings
create any acquisition binding
define binding lifecycle or conflict semantics
modify castlearq/model_identity.py
modify castlearq/identity_admission.py
modify ModelStore
modify ArtifactSpec
modify artifact_id
modify revision semantics
modify discovery
modify runtime
migrate curated mappings
add CLI commands
add Model Library UX
add Hugging Face provider logic
perform acquisition
change download behaviour
```

---

## 17. Relationship to B9.93

B9.93's governing rule is preserved and reinforced: *no identity layer may be
substituted for or be silently promoted into another.* This decision exists
precisely so that logical identity need never absorb locator authority.

---

## 18. Relationship to B9.94

B9.94 (closed) established Identity Admission as an independent model-identity
concern and forbade closing the acquisition gap by extending it. This record
honours that boundary exactly: it closes the gap **beside** Identity
Admission, never inside it.

---

## 19. Relationship to B9.95

B9.95 (closed) established a standalone, forward-only, provider-agnostic,
immutable admission registry independent of ModelStore and acquisition. That
registry is **unchanged**. Acquisition bindings are a different store with a
different responsibility; they are not a reverse index of the admission
registry.

---

## 20. Relationship to Future Acquisition Architecture

Acquisition Resolution is the missing seam between closed Identity Admission
and acquisition proper. It is a prerequisite for generalized acquisition of
admitted models, and it depends on no Model Library, GUI or runtime work.

---

## 21. Final Architectural Statement

**Acquisition Resolution is an independent architectural responsibility from
Identity Admission. An Acquisition Resolver resolves an admitted `model_id` to
an acquisition locator using independent persistent acquisition bindings.
These bindings are not identity records and are not reverse lookup state for
Identity Admission. Identity Admission remains forward-only and owns only
logical model identity admission. Acquisition Resolution does not redefine
`model_id`, identity derivation, `artifact_id`, revision semantics, or
ModelStore. Revision and variant selection remain downstream acquisition
responsibilities. The exact lifecycle, authority, cardinality, persistence
schema, and operational semantics of acquisition bindings remain future
architectural decisions. No roadmap block is allocated and no implementation is
authorized by this decision.**

---

## 22. Ratification Amendment — B9.96 Decision Set D1–D7

```text
AMENDMENT TYPE:      documentation only — architecture/governance record
RATIFICATION STATUS: RATIFIED WITH DEFERRED SURFACES
DECISION AUTHORITY:  PROJECT OWNER (human architectural decision)
GOVERNANCE RECORD:   docs/roadmap-register-and-numbering-policy.md
                     section 39.7 (decisions D1–D7) and
                     section 39.8 (acceptance criteria AC1–AC14)
```

This amendment converts the behavioral questions that sections 14, 15 and 16
of this record deliberately left open into owner-ratified decisions for
**B9.96 only**. It changes no source, no test, no wiring and no acquisition
behaviour, and it authorizes no implementation step by itself. Preceded by the
READ-ONLY B9.96 Implementation Readiness Audit (NOT READY) and the READ-ONLY
B9.96 Decision Validation Audit (READY TO RATIFY WITH CHANGES); its required
changes are incorporated below.

```text
D1 — CARDINALITY (answers section 15 Q4/Q5 for B9.96)
  At most one active acquisition binding exists for a given model_id.
  B9.96-scoped: no multi-locator selection mechanism exists in B9.96.
  Future multi-locator acquisition remains a possible future architectural
  surface and is NOT permanently prohibited.

D2 — BINDING CREATION (answers Q1/Q2)
  Acquisition Resolution owns explicit binding creation:
      bind(model_id, source, repository)
  Identity Admission does NOT create acquisition bindings automatically, and
  acquisition never infers a binding by reversing (source, repository) ->
  model_id. Admission stays forward-only; B9.95 AC10 is unchanged.

D3 — PRECEDENCE: OPTION A RATIFIED (answers Q3/Q16)
  curated downloadable locator  >  persistent acquisition binding.
  Fall-through condition: the persistent binding is consulted ONLY when the
  curated acquisition path yields no downloadable locator — the composed
  resolver is conceptually:
      downloadable_locator(model_id)  or  binding_lookup(model_id)
  A binding that disagrees with an existing curated locator for the same
  model_id is rejected at registration time (D4), so a disagreeing binding
  cannot exist and silent-ignore is unreachable in normal operation.
  The Decision Validation Audit's recommendation of Option A is RATIFIED;
  Options B and C are REJECTED (B would let persisted state silently
  override curated authority, contrary to the ratified
  "curated -> persisted -> derived" ordering; C's resolution-time refusal is
  unnecessary once registration is guarded).

D4 — CONFLICT AND IDEMPOTENCY (answers Q10)
  1 duplicate model_id registration with a different locator: FAIL CLOSED
  2 any conflicting binding: FAIL CLOSED — store left byte-unchanged;
     never overwritten, never guessed, never defaulted
  3 binding disagreeing with a curated locator: REJECTED at registration
     (the D3 curated check, evaluated before any write)
  4 identical re-registration: IDEMPOTENT SUCCESS, state unchanged
     (mirrors B9.95 registration semantics)
  5 overwrite: NOT ALLOWED through bind() — the only sanctioned mutations
     are the explicit update() and delete() operations
  6 acquire() NEVER mutates binding state
  Every failure leaves the store unchanged (fail-closed, B9.95 philosophy).

D5 — LIFECYCLE (answers Q8/Q9)
  bind / update / delete — all explicit and owner-invoked; no other mutation
  exists. acquire() does not create, update or delete bindings.
      changing an acquisition locator  !=  changing model_id
  Identity is immutable; only acquisition location changes. No historical or
  versioned binding state exists in B9.96 (provenance, Q14, deferred).

D6 — PERSISTENCE (answers Q11/Q12/Q13)
  An INDEPENDENT persistent store is required. Bindings MUST NOT live in
  identity-admission.json, ModelStore, artifact manifests, or session state.
  Store path:   ~/.castlearq/acquisition-bindings.json
                (sibling of identity-admission.json, per the ~/.castlearq
                 state-directory convention)
  Environment:  CASTLEARQ_ACQUISITION_BINDINGS_ROOT
                (a DIRECTORY; tests only; non-empty override wins —
                 mirrors CASTLEARQ_SESSION_ROOT and
                 CASTLEARQ_IDENTITY_REGISTRY_ROOT)
  Record schema (minimum):
      {"schema_version": 1,
       "bindings": {model_id: {"source": ..., "repository": ...}}}
  schema_version is REQUIRED; any other value is rejected, never guessed.
  Strict validation of every record; deterministic serialization; atomic
  durable writes (temp sibling -> flush -> fsync(file) -> os.replace ->
  fsync(dir)). No provider metadata, aliases, provenance, revision, artifact
  identity or runtime state is stored. The locator representation remains
  the existing (source, repository) tuple consumed by LocatorResolver
  (answers Q19 for B9.96).

D7 — AUTHORIZED DOWNLOADABILITY BRIDGE
  Identity Admission:      (source, repository) -> model_id   (forward-only)
  Acquisition Resolution:  model_id -> acquisition locator
  Acquisition:             acquisition locator -> artifact acquisition
  The composed resolver lives OUTSIDE identity_admission.py and
  model_identity.py; it does not modify model_id, is not a second identity
  registry, performs no reverse identity lookup, and does not touch
  ModelStore, artifact identity or revision semantics. It is injected ONLY
  through the existing locator_resolver seam at
  castlearq/application_wiring.py; ModelAcquisitionService is unchanged
  (the LocatorResolver contract is already type-compatible).
  downloadable_locator() remains byte-unchanged and remains the curated
  download gate on every other presentation surface (e.g. the download
  status and model DTO paths).
  Why an admitted model_id may now reach acquisition: an explicitly
  created acquisition fact — not any identity-side reversal — states where
  to acquire it. Identity Admission still never answers the inverse
  question, and admission alone still makes nothing downloadable.

SUPPORTED-SOURCE POLICY — OPTION C RATIFIED
  Registration (bind/update) rejects unsupported sources: early,
  fail-closed failure at write time.
  Resolution re-validates defensively against stored state before returning
  a locator.
  Both consult the single existing authority SUPPORTED_DOWNLOAD_SOURCES in
  castlearq/model_identity.py. No authority is duplicated and no
  provider-specific behaviour is introduced.

BINDING PRECONDITION — OPTION 2 RATIFIED
  bind(model_id, source, repository) requires the FORWARD consistency check:
      resolve_admitted_model_id(source, repository) == model_id
  A mismatch FAILS CLOSED and no state is written. The check is a pure
  forward derivation/admission resolution over the SUPPLIED locator — it is
  NOT a reverse lookup, it adds no identity-side code, and it creates no new
  identity authority. Rationale: a binding must be self-consistent with the
  identity CastleArq would admit for that locator, which prevents binding
  arbitrary foreign model_ids while reusing the ratified derivation
  mechanism unchanged.

DEFERRED SURFACES (remain future architectural decisions; not answered here)
  Q6 automatic rename handling (explicit update() exists as mechanism),
  Q7 unavailable-source policy, Q14 provenance/audit info, Q15 offline
  policy beyond the inherent fail-closed no-binding path, Q17 curated ->
  binding migration, Q18 aliases, Q20 provider acquisition metadata, and
  runtime derived-identity resolution (a separate future decision surface).

SUPERSESSION AND STATUS
  Section 21's clause that lifecycle, authority, cardinality and persistence
  schema "remain future architectural decisions" is superseded FOR B9.96 by
  this amendment; for every other scope section 21 stands unchanged. The
  pre-allocation clause "No roadmap block is allocated" was already
  superseded by the B9.96 allocation at roadmap section 39.
  IMPLEMENTATION: NOT PERFORMED and NOT authorized by this amendment —
  implementation is the next controlled step behind its own readiness gate
  (B9.95 precedent). B9.96 remains ALLOCATED — NOT IMPLEMENTED, NOT
  VERIFIED, NOT CLOSED.
  This HADR is preserved in version history together with the governance
  record that cites it; both are introduced by the same documentation-only
  ratification commit.
