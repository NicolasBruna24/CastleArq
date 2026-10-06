# B9.97 — Human Architectural Decision Record

## Revision-Aware Acquisition

---

## 1. Decision Status

```text
DOCUMENT TYPE:       Human Architectural Decision Record (HADR)
BLOCK:               B9.97 — Revision-Aware Acquisition
HUMAN ARCHITECTURAL DECISION: RATIFIED
DECISION STATUS:     SELECTED
SELECTED OPTION:     Option C — Independent Revision Channel
CONCRETE CARRIER:    ArtifactSpec.revision: str | None
DECISION AUTHORITY:  Project Owner / Human Architect
IMPLEMENTATION:      LOCAL WORK EXISTS IN WORKTREE — VERIFIED AND CLOSED
VERIFICATION:        PASSED — READ-ONLY implementation verification
ROADMAP ALLOCATION:  ALLOCATED
CLOSURE:             PERFORMED — formal governance closure
CODE IMPACT:         NONE — this record is governance-only and does not modify source code or tests
```

This record documents the formally ratified Human Architectural Decision for B9.97 and reconciles it with the current governance state. It remains:

```text
This document preserves the Option C decision.
This document records B9.97 as formally allocated under the roadmap.
This document confirms B9.97 verification has passed under the READ-ONLY implementation verification gate.
This document records B9.97 closure as performed.
This document does NOT modify source code or tests.
This document does NOT modify production behavior.
This document does NOT create a commit or push.
This document does NOT authorize a historical rewrite of the earlier NOT ALLOCATED state.
```

---

## 2. Baseline Verification

Verified by direct repository inspection at the creation of this record:

```text
Branch:                 main
HEAD:                   943dbfef283623606b8ec6d519a79e528488f536
origin/main:            943dbfef283623606b8ec6d519a79e528488f536
Remote refs/heads/main: 943dbfef283623606b8ec6d519a79e528488f536
Ahead/behind:           0 / 0
HEAD subject:           feat: close B9.96 acquisition resolution
Tracked modifications:  none
Staged changes:         none
```

Lifecycle confirmations:
* **B9.94:** CLOSED (Increment 1 at section 37.12; architectural question at section 37.13)
* **B9.95:** CLOSED (section 38.11)
* **B9.96:** CLOSED (commit `943dbfef283623606b8ec6d519a79e528488f536`, section 39.9)
* **B9.97:** ALLOCATED — governance reconciliation record issued; this document records the decision and the allocation state under the repository's formal block lifecycle.
* **B9.97 Verification:** PASS — dedicated B9.97 service tests passed, neighboring revision-boundary suites passed, and the full repository suite passed.
* **B9.97 Closure:** PERFORMED — formal closure state recorded in this governance update; implementation and verification remain unchanged from the verified local work.

---

## 3. Human Architectural Decision

The human architect has selected and ratified:

### Option C — Independent Revision Channel

Revision is an artifact-state selection concern independent from acquisition-location resolution.

The concrete carrier for this independent channel is:

```text
ArtifactSpec.revision: str | None
```

Therefore:

```text
Acquisition Resolution
model_id → (source, repository)
```

remains unchanged.

And independently:

```text
ArtifactSpec
    ↓
revision
    ↓
ModelAcquisitionService
    ↓
provider-specific revision resolution
    ↓
artifact bytes
```

The acquisition binding MUST NOT contain revision.

---

## 4. Architectural Definition of Revision

> `revision` identifies the requested artifact state/version within the acquisition source. It is not part of logical model identity.

* The architecture MUST remain provider-neutral.
* Revision MUST NOT be defined exclusively as a Hugging Face concept.
* The implementation MAY support provider-specific revision formats internally where required by an existing provider seam, but the generic acquisition architecture MUST NOT become provider-specific.

---

## 5. Identity Separation Invariant

```text
model_id identifies WHAT model is being acquired.

revision identifies WHICH artifact state is being acquired.

artifact_id identifies the stored artifact identity according to
the existing artifact identity mechanism.

revision MUST NOT silently become model identity or artifact identity.
```

Specifically:

`revision` MUST NOT participate in:
* `logical_model_id()`;
* `model_id` derivation;
* Identity Admission;
* Acquisition Binding identity;
* existing `artifact_id` derivation unless future architectural evidence explicitly creates a separate decision.

Artifact identity MUST NOT be redesigned in B9.97.

---

## 6. Acquisition Resolution Invariant

B9.96 is CLOSED and MUST remain architecturally intact.

```text
model_id
    ↓
Acquisition Resolution
    ↓
(source, repository)
```

* The B9.96 `locator_resolver` contract MUST NOT be changed to return revision.
* Do NOT modify:
  ```text
  model_id → locator
  ```
  into:
  ```text
  model_id → locator + revision
  ```
* Revision travels through the independent acquisition request/specification channel.

---

## 7. Revision Authority

> The caller supplying an explicit revision is authoritative for that acquisition request.

```text
explicit caller revision
        ↓
authoritative request value
```

* Discovery is NOT authoritative.
* Persistent acquisition bindings are NOT authoritative.
* `ModelStore` is NOT authoritative for selecting a new revision.
* Providers are responsible for resolving the supplied revision according to their existing provider-specific acquisition semantics, but provider defaults MUST NOT silently override an explicit requested revision.

---

## 8. Optionality

```text
revision: str | None
```

Revision is OPTIONAL.

If revision is absent:
* existing acquisition behavior remains valid;
* no forced migration to pinned revisions occurs;
* B9.97 does not introduce a mandatory revision requirement.

If revision is explicitly supplied:
* it MUST be validated;
* it MUST be propagated deterministically;
* acquisition MUST fail closed if the requested revision cannot be resolved.

---

## 9. Discovery Revision

`DiscoveredArtifact.revision` remains discovery metadata.

It MUST NOT automatically become authoritative merely because discovery produced it.

Therefore:

```text
Discovery
    ↓
DiscoveredArtifact.revision
```

may provide information to future callers or UX, but:

```text
DiscoveredArtifact.revision
    X
    ↓
automatic acquisition authority
```

is NOT part of B9.97.

Any future automatic discovery-to-acquisition pinning policy requires a separate architectural decision.

---

## 10. Persistence Decision

> The revision actually associated with an acquired artifact MUST be persisted in the ModelStore manifest as a non-identity artifact attribute.

The manifest record MUST allow CastleArq to distinguish:
* explicit revision;
* revision absent / provider-default acquisition;
* legacy artifact whose revision was never recorded.

* Do not redesign the `ModelStore`.
* Do not introduce historical version management.
* Do not introduce multi-revision lifecycle management.
* The persistence requirement is limited to recording the revision associated with the acquired artifact.

---

## 11. Immutability / Lifecycle

> Once an artifact has been acquired, its recorded revision MUST NOT be silently mutated.

If a different revision is requested later, it is a new explicit acquisition request.

Do not introduce:
* automatic revision migration;
* background re-pinning;
* upstream tracking;
* historical revision management;
* automatic artifact replacement.

Those concerns remain future architecture.

---

## 12. Conflict Policy

* **Explicit malformed revision:** Fail closed.
* **Explicit revision unavailable:** Fail closed.
* **Explicit requested revision conflicts with stored artifact metadata:** Do not silently overwrite or reinterpret the existing artifact metadata. The acquisition operation must follow an explicit deterministic conflict policy.
* **Discovery revision differs from explicit caller revision:** The explicit caller revision wins. Discovery remains advisory.
* **Revision absent:** Preserve current provider-default behavior. Do not fabricate a revision value merely to make the field non-null.

---

## 13. Manifest Semantics

The architecture explicitly distinguishes:

```text
revision = explicit requested revision
```

from:

```text
revision = absent / provider default / unknown
```

* An absent revision cannot be reconstructed retrospectively unless repository evidence proves that.
* The manifest must represent the information CastleArq actually knows.
* Exact field names MAY be finalized during implementation, but the semantic distinction above is architectural and MUST be preserved.

---

## 14. Backward Compatibility

* Existing callers that do not provide revision MUST continue to work.
* Existing revision-absent behavior MUST remain valid.
* Existing manifests without revision MUST remain readable.
* No mandatory migration of existing stored artifacts is introduced by B9.97.
* No automatic re-download or re-acquisition is introduced.

---

## 15. Provider Neutrality

* Generic CastleArq architecture MUST NOT hard-code Hugging Face revision semantics.
* Provider-specific revision formatting belongs behind the existing provider-specific acquisition seam.
* The generic contract should carry a provider-neutral revision value.
* Do not introduce a new provider abstraction solely for B9.97.

---

## 16. B9.96 Compatibility

B9.97 MUST NOT modify:
* `acquisition_resolution.py` binding semantics;
* Acquisition Binding persistence schema;
* `locator_resolver` return contract;
* Identity Admission;
* persistent identity registry;
* logical model identity derivation.

B9.97 may extend:
* `ArtifactSpec`;
* acquisition request handling;
* provider URL construction;
* `ModelStore` manifest recording.

These are extensions of acquisition behavior, not revisions of the closed identity architecture.

---

## 17. Scope Boundary

Explicitly OUT OF SCOPE:
* reverse identity lookup;
* `model_id` mutation;
* Identity Admission redesign;
* aliases;
* multi-locator acquisition;
* runtime identity inference;
* automatic discovery-to-acquisition pinning;
* CLI redesign;
* GUI;
* Model Library UX;
* chat;
* fine-tuning;
* datasets;
* evaluation;
* clusters;
* multi-GPU;
* Windows support;
* provider discovery redesign;
* broad `ModelStore` redesign;
* historical revision management;
* upstream tracking;
* automatic migration;
* background synchronization.

If implementation reveals that one of these is genuinely unavoidable, implementation MUST STOP and return to architectural governance rather than silently expanding B9.97.

---

## 18. Bounded Acceptance Criteria

Architectural acceptance criteria candidates for the future B9.97 implementation:

### Identity
* revision does not alter `model_id`;
* revision does not alter Identity Admission;
* revision does not enter acquisition binding identity.

### Acquisition
* explicit revision is propagated deterministically;
* explicit revision is not silently overridden;
* revision-aware acquisition resolves the requested artifact state;
* revision-absent acquisition preserves existing behavior.

### Persistence
* acquired revision is recorded in the manifest;
* legacy revision-absent manifests remain readable;
* no existing artifact is silently rewritten solely because of revision metadata.

### Conflicts
* malformed revision fails closed;
* unavailable revision fails closed;
* explicit caller revision takes precedence over discovery metadata;
* conflicting explicit requests do not silently overwrite existing artifact state.

### Boundaries
* `locator_resolver` contract remains unchanged;
* B9.94/B9.95 identity boundaries remain unchanged;
* B9.96 acquisition-binding semantics remain unchanged.

### Provider neutrality
* generic acquisition code remains provider-neutral;
* provider-specific revision formatting remains inside the provider seam.

---

## 19. Rejected Alternatives

### Option B — Revision inside Acquisition Binding
Rejected because it:
* couples artifact version lifecycle to acquisition-location lifecycle;
* reopens closed B9.96 decisions;
* requires binding persistence schema changes;
* creates ambiguity between binding-level and request-level revision authority;
* weakens separation of concerns;
* provides worse per-request reproducibility semantics.

### Option A — ArtifactSpec-only framing
Not rejected as technically incorrect.

Instead:
> Option A is accepted as the concrete carrier mechanism inside the broader Option C architectural framing.

Therefore:
```text
Architectural decision:
Option C — independent revision channel

Concrete carrier:
ArtifactSpec.revision
```

This distinction is explicit and binding.

---

## 20. Architectural Invariant

```text
revision selects artifact state; it never identifies the model,
never enters model_id/artifact_id derivation, never lives in the
acquisition binding, and never alters the locator_resolver contract.
```

---

## 21. Human Decision Status

```text
HUMAN ARCHITECTURAL DECISION:
RATIFIED

SELECTED OPTION:
Option C — Independent Revision Channel

CONCRETE CARRIER:
ArtifactSpec.revision: str | None

B9.97:
NOT YET ALLOCATED
```

This is an architectural ratification only. It is NOT roadmap allocation.
