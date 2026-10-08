# B9.99 — Acquisition Identity Resolver Integration

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:                 Human Architectural Decision Record (HADR)
SUBJECT:                       B9.99 — Acquisition Integration Failure
                               (Admitted Non-Curated Identity Resolver at
                               the Application Composition Root)
DECISION:                      SELECTED — OPTION D: BIND THE EXISTING
                                resolve_admitted_model_id AUTHORITY AS THE
                                ACQUISITION identity_resolver AT THE
                                APPLICATION COMPOSITION ROOT
DECISION AUTHORITY:            PROJECT OWNER (human decision)
DECISION STATUS:               DECIDED — IMPLEMENTED — ACCEPTED (B9.99 CLOSED)
CLASSIFICATION:                B9.99 IMPLEMENTATION DEFECT (NOT B9.100)
SCOPE:                         A correction WITHIN B9.99 — a single resolver
                               binding at application_wiring; no new
                               architectural milestone
DATE:                          NOT ASSERTED — this record does not establish
                                a date
CODE IMPACT:                   NONE FROM THIS RECORD — this record changes no
                               code, no tests, no wiring; it documents the
                               decision only
B9.100:                        NOT AUTHORIZED
REAL-WORLD ACCEPTANCE:         PASSED (revalidation drill; initial drill FAILED AT ACQUIRE — see §3.1)
FINAL B9.99 ACCEPTANCE:        CLOSED — read-only closure audit passed
PUSH:                          NOT PERFORMED
```

This record formally records the human architectural decision that resolves
the B9.99 real-world acceptance failure at `Acquire`. It is decision
documentation and evidence reconciliation only. It does not itself implement
the correction; implementation requires a separate implementation
authorization.

---

## 2. Historical chain this record belongs to

```text
B9.99 ALLOCATED / AUTHORIZED / IMPLEMENTED / VERIFIED
    (docs/b999-implementation-authorization-human-architectural-decision-record.md)
    ↓
B9.99 B1/B2/B3 FINDINGS RESOLVED + B5 GOVERNANCE RECONCILED
    (docs/b999-human-findings-resolution-human-architectural-decision-record.md;
     docs/b999-b5-governance-reconciliation-human-architectural-decision-record.md)
    ↓
B9.99 AUTOMATED VERIFICATION = 2421 passed / 2801 subtests / 0 failures
    ↓
B9.99 REAL-WORLD ACCEPTANCE DRILL = FAILS AT Acquire
    "Identity could not be resolved for repository:
     TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
    ↓
READ-ONLY ACQUISITION INTEGRATION AUDIT = COMPLETE
    (evidence summarized in section 3 of this record)
    ↓
HUMAN CORRECTION DECISION = OPTION D SELECTED
    (this record)
    ↓
CORRECTION IMPLEMENTATION = NOT YET EXECUTED
    (requires a separate implementation authorization)
    ↓
REAL-WORLD ACCEPTANCE REVALIDATION = PENDING
    (roadmap 42.9 remains open)
    ↓
FINAL B9.99 ACCEPTANCE = PENDING
    (roadmap 42.12 remains open)
```

No step in this chain is collapsed into another. Allocation, authorization,
implementation, verification, acceptance failure, audit, correction decision,
correction implementation, and revalidation are distinct states.

---

## 3. Decision context (evidence)

### 3.1 The failure

B9.99 passed its automated verification:

```text
2421 passed
2801 subtests
0 failures
```

The subsequent real-world acceptance drill used:

```text
repository: TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
artifact:   tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
```

The real journey completed:

```text
Discover → Select → Admit → Describe → Bind
```

and failed at:

```text
Acquire

"Identity could not be resolved for repository:
 TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
```

### 3.2 What the READ-ONLY architectural audit independently verified

```text
B9.96 locator resolution                 = working
Identity Admission                       = working
Admitted identity resolution             = working
Acquisition identity re-attachment       = broken
```

The exact failing path:

```text
run_download
  → ModelAcquisitionService.acquire(model_id)
  → _resolve_repository → resolve_acquisition_locator(model_id)     ✓ (B9.96)
  → discovery (identity-free)                                       ✓
  → selection                                                       ✓
  → map_discovered_artifacts(identity_resolver=...)
      → _resolve_identity: identity_resolver(repository)            ✗ HERE
```

The production composition currently binds (castlearq/application_wiring.py):

```text
identity_resolver(repository)
    =
logical_model_id(source, repository)
```

which consults only:

```text
SOURCE_REPOSITORY_TO_MODEL_ID
```

a curated-only table, and therefore returns `None` for any non-curated
repository, raising `AcquisitionMappingError` at
`castlearq/acquisition_mapping.py` (`_resolve_identity`).

### 3.3 What already exists

```text
resolve_admitted_model_id(source, repository)
    ratified authority order: curated → persisted → derived
    explicitly introduced so non-curated admitted identities have a stable
    identity without extending the curated catalog
```

Additionally verified:

```text
identity_admission.lookup(source, repository) → admitted model_id   ✓ works
bind-time forward check:
    resolve_admitted_model_id(source, repository) == model_id       ✓ holds
B9.96 binding + locator resolution for the admitted model_id        ✓ works
```

### 3.4 Why the automated suite stayed green

The B9.99 journey test simulates the acquired ModelStore artifact instead of
invoking the real acquisition service, and every `acquire()` test injects a
fake identity resolver. No automated test exercises
`compose_acquisition_service()` → real `ModelAcquisitionService.acquire()`
for an admitted non-curated repository. The gap is a test-coverage gap, not a
contradiction of any passing test.

### 3.5 Scope evidence

B9.99 already explicitly authorized:

```text
application composition
+ existing binding
+ existing acquisition service
+ real non-curated acquisition
```

The missing behavior is an incomplete integration of already-existing
architectural capabilities.

---

## 4. The human decision

```text
SELECTED:
Option D — use the existing admitted-aware identity resolution authority
           (resolve_admitted_model_id) at the existing acquisition
           identity_resolver seam at the application composition root.
```

Formally:

```text
Option D
= bind the existing admitted-aware identity resolution authority
  at the existing acquisition identity_resolver seam.
```

This is a **correction within B9.99**, not a new architectural milestone.

```text
B9.100 = NOT CREATED / NOT AUTHORIZED
```

This decision must NOT be reinterpreted as authorization to redesign
acquisition.

---

## 5. Why Option D was selected (alternatives)

### Option A — Direct model_id reuse — REJECTED

The existing B9.82 architecture intentionally uses an injected
`identity_resolver` as the caller-owned identity policy. Bypassing that seam
and threading `model_id` directly into mapping would weaken a ratified
B9.82/B9.93 invariant (identity injection solely through the required,
keyword-only resolver seam) and require changes inside protected acquisition
boundaries (`acquisition_mapping.py`, `acquisition_service.py`), expanding
the blast radius beyond the demonstrated defect.

### Option B — Persisted admission lookup — NOT SELECTED (valid fallback)

Architecturally viable: `identity_admission.lookup(source, repository)`
returns the admitted identity and preserves persisted-registry authority.
But it introduces a runtime acquisition dependency on the persisted
Identity Admission registry — the download path would depend directly on
`identity_admission.json`. The human decision prefers the already-established
pure authority chain instead. **Option B remains a valid fallback if later
evidence invalidates Option D.**

### Option C — Redesign acquisition mapping — REJECTED

Would reopen a previously closed B9.82/B9.85 contract and require changes to
acquisition mapping, acquisition service, related tests, existing resolver
contracts, and potentially B9.97/B9.98 integration surfaces. This is
materially larger than the demonstrated defect.

### Option D — Existing admitted-aware resolver — SELECTED

`resolve_admitted_model_id(source, repository)` already represents the
ratified authority `curated → persisted → derived`. It was explicitly
introduced so non-curated admitted identities could have a stable identity
without extending the curated catalog. Binding this function at the existing
composition-root seam:

```text
application_wiring
    ↓
identity_resolver
    ↓
acquisition_mapping
```

repairs the missing integration without changing:

```text
Identity Admission; acquisition mapping; acquisition service; ModelStore;
binding semantics; revision semantics; artifact lifecycle.
```

---

## 6. Architectural principle — identity and location remain separate

The correction preserves the separation:

```text
IDENTITY
resolve_admitted_model_id(source, repository)
        │
        ▼
logical model identity
```

and:

```text
LOCATION
resolve_acquisition_locator(model_id)
        │
        ▼
source + repository
```

These are separate authorities. The implementation must NOT merge them.

The resulting acquisition path is conceptually:

```text
admitted model_id
       │
       ├───────────────┐
       │               │
       ▼               ▼
identity resolver   locator resolver
       │               │
       ▼               ▼
model identity      source + repository
       │               │
       └───────┬───────┘
               ▼
       discovery / selection
               ▼
          ArtifactSpec
               ▼
            acquire
```

---

## 7. Curated precedence must remain

The selected resolver preserves the existing authority order:

```text
curated → persisted → derived
```

Therefore:

```text
- existing curated models resolve to exactly the same model IDs;
- SOURCE_REPOSITORY_TO_MODEL_ID must not be extended;
- curated entries must not be migrated into Identity Admission;
- curated behavior remains backward compatible.
```

`SOURCE_REPOSITORY_TO_MODEL_ID` must NOT be altered to solve this issue.

---

## 8. Non-curated acquisition remains explicit

Option D does NOT authorize arbitrary repository acquisition. A non-curated
repository must still have:

```text
explicit admission + explicit binding
```

before acquisition can reach the artifact path.

The existing locator boundary remains authoritative:

```text
resolve_acquisition_locator(model_id)
```

and continues to require either:

```text
curated downloadable locator  or  explicit acquisition binding
```

No fallback such as `repository → automatically downloadable` is authorized.

---

## 9. No new registry

This decision does NOT authorize:

```text
- a second identity registry;
- a reverse identity registry;
- acquisition-specific identity persistence;
- new model metadata storage;
- identity aliases;
- automatic registration;
- automatic admission.
```

The existing Identity Admission authority remains unchanged.

---

## 10. Fail-closed behavior

The existing acquisition mapping contract continues to fail closed. The
correction must not allow:

```text
unknown identity → guessed identity → automatic acquisition
```

Expected semantics remain:

```text
invalid/inconsistent identity → acquisition rejected
```

The existing post-resolution identity consistency check
(`spec.model_id != model_id → IDENTITY_UNRESOLVED` in the acquisition
service) must remain intact.

---

## 11. Revision authority (B9.97 unchanged)

This decision does not alter B9.97. Revision remains caller/selector
authority. The correction must not:

```text
- infer revision from identity;
- move revision into Identity Admission;
- move revision into acquisition binding;
- create a second revision source.
```

The existing revision channel remains unchanged.

---

## 12. Artifact lifecycle (B9.98 unchanged)

This decision does not alter B9.98. The following remain unchanged:

```text
- ArtifactSpec lifecycle;
- current-state semantics;
- mismatch → BLOCKED behavior;
- ModelStore manifest semantics;
- artifact identity;
- verification lifecycle.
```

The correction only enables the existing acquisition path to receive the
correct logical identity for an admitted non-curated repository.

---

## 13. B9.99 scope interpretation

This decision explicitly classifies the failure as:

```text
B9.99 IMPLEMENTATION DEFECT
```

not:

```text
B9.100 NEW ARCHITECTURAL REQUIREMENT
```

Reason: B9.99 already explicitly authorized application composition + the
existing binding + the existing acquisition service + real non-curated
acquisition (§42.5.2, §42.5.5, §42.8.6, §42.9). The missing behavior is an
incomplete integration of already-existing architectural capabilities.

---

## 14. Authorized correction boundary

The following correction is authorized **architecturally**; this HADR does
NOT itself constitute implementation execution.

```text
application_wiring
    identity_resolver
        BEFORE:
            logical_model_id(source, repository)

        AFTER:
            resolve_admitted_model_id(source, repository)
```

The exact implementation must preserve existing composition patterns and
dependency direction.

```text
No broader refactor is authorized.
```

---

## 15. Required verification after implementation

Once a separate implementation authorization is issued, verification must
establish at minimum:

### 15.1 Existing curated path

```text
curated repository
→ identity resolution unchanged
→ acquisition behavior unchanged
```

### 15.2 Admitted non-curated path

```text
admit → describe → bind → resolve locator → resolve admitted identity
→ acquire
```

### 15.3 Regression protection

```text
The relevant existing suite must remain green.
```

### 15.4 New integration coverage

A deterministic test must exercise:

```text
compose_acquisition_service()
→ admitted non-curated model
→ real acquisition service
→ identity mapping
```

using local/fake acquisition infrastructure as necessary. The test must NOT
simulate the final ModelStore artifact as a substitute for acquisition.

### 15.5 Real-world revalidation

After automated verification, repeat the real-world public non-curated GGUF
drill. The drill must again reach:

```text
Acquire → Verify → Evaluate → Execute → Chat
```

No curated fallback is permitted.

---

## 16. What this decision does NOT authorize

```text
Explicitly NOT authorized:
- B9.100;
- acquisition-service redesign;
- acquisition-mapping redesign;
- Identity Admission redesign;
- ModelStore redesign;
- GUI;
- HTTP/API expansion;
- automatic model discovery-to-acquisition;
- automatic admission;
- automatic binding;
- automatic reconciliation;
- multi-model lifecycle changes;
- model registry redesign;
- revision architecture changes;
- rollback/history architecture;
- cluster/multi-GPU architecture;
- new product surfaces unrelated to this correction.
```

---

## 17. Governance status (recorded accurately)

```text
B9.99 implementation              = COMPLETE
B1/B2/B3                          = VERIFIED
B5 governance                     = COMPLETE
Automated verification            = COMPLETE
                                    (2421 passed, 2801 subtests, 0 failures)
Real-world acceptance (initial)   = FAILED at Acquire (historical — §3.1)
Acquisition integration audit     = COMPLETE
Human correction decision         = OPTION D SELECTED (this record)
Correction implementation         = COMPLETE (application_wiring.py binding;
                                    full suite 2424 passed / 2801 subtests,
                                    0 failures)
Real-world acceptance (re-run)    = PASSED (Discover→Select→Admit→Describe→
                                    Bind→Acquire→Verify→Evaluate→Execute→
                                    Chat, 10/10)
Final B9.99 acceptance            = CLOSED (closure audit)
B9.100                            = NOT AUTHORIZED
```

B9.99 must not be marked accepted. The acquisition defect must not be marked
resolved until implementation and revalidation are complete.

---

## 18. Decision record

### Decision

```text
SELECTED:
Option D — existing admitted-aware identity resolver
           (resolve_admitted_model_id)
           at the application composition root.
```

### Status

```text
DECIDED — IMPLEMENTED
```

### Rationale (audit evidence summary)

```text
- The drill failure is localized to identity re-attachment at the
  B9.82 mapping boundary: the composition-root identity_resolver is bound
  to curated-only logical_model_id and returns None for non-curated
  repositories.
- B9.96 locator resolution, Identity Admission, and admitted identity
  resolution were all independently verified working.
- resolve_admitted_model_id already embodies the ratified
  curated → persisted → derived authority and is guaranteed consistent
  with any explicitly bound model_id by the bind-time forward check.
- B9.99 already authorized application composition + existing binding +
  existing acquisition service + real non-curated acquisition, so the
  failure is an implementation defect within B9.99 scope, not a new
  requirement.
- The journey test simulates the ModelStore artifact instead of invoking
  the real acquisition service, which is why 2421 passing tests did not
  expose the gap.
```

### Consequences — positive

```text
- enables admitted non-curated acquisition;
- preserves the existing acquisition service;
- preserves the B9.96 locator seam;
- preserves B9.97 revision authority;
- preserves B9.98 lifecycle;
- avoids a second registry;
- preserves curated precedence.
```

### Consequences — negative / trade-off

```text
- acquisition identity resolution becomes admitted-aware;
- resolve_admitted_model_id becomes a production dependency of acquisition
  composition;
- pure derivation is trusted as part of the admitted-aware authority chain;
- inconsistent bound state still relies on downstream fail-closed checks.
```

### Alternatives rejected

```text
A — direct model_id reuse: weakens the ratified B9.82/B9.93
    caller-owned identity-resolver invariant and requires changes inside
    protected acquisition boundaries.

B — persisted admission lookup: viable fallback, but couples the download
    path at runtime to identity_admission.json; not selected.

C — acquisition mapping redesign: reopens closed B9.82/B9.85 contracts and
    ripples into B9.97/B9.98 surfaces; materially larger than the defect.
```

---

## 19. Repository impact of this record

```text
This record is documentation-only.
Files modified by this task:
    docs/b999-acquisition-identity-resolver-human-architectural-decision-record.md
        (NEW governance document — this file)
Source code:         NOT MODIFIED
Tests:               NOT MODIFIED
Application wiring:  NOT MODIFIED
Identity Admission:  NOT MODIFIED
Acquisition mapping: NOT MODIFIED
Acquisition service: NOT MODIFIED
Roadmap status:      NOT MODIFIED (nothing beyond this record was authorized)
Commits:             NOT CREATED
Push:                NOT PERFORMED
```
