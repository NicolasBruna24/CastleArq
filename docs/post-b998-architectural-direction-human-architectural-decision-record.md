# Post-B9.98 Architectural Direction — Human Architectural Decision Record

## Option D — No Successor Yet / Defer Successor Allocation

---

## 1. Status

```text
DOCUMENT TYPE:                 Human Architectural Decision Record (HADR)
SUBJECT:                       Post-B9.98 Architectural Direction
DECISION:                      SELECTED — OPTION D (No Successor Yet /
                               Defer Successor Allocation)
DECISION AUTHORITY:            PROJECT OWNER (human architectural decision)
DECISION STATUS:               RATIFIED
B9.99:                         NOT ALLOCATED — not reserved, not selected,
                               not authorized
IMPLEMENTATION AUTHORIZATION:  NONE
ROADMAP MODIFIED:              NO — no roadmap section, register entry or
                               allocation record is created by this document
CODE IMPACT:                   NONE — this record is documentation only
COMMIT/PUSH:                   NOT PERFORMED
```

This document is a local-only governance record. It does not allocate any B9
identifier, does not create or reserve B9.99, does not modify the roadmap
register, and authorizes no implementation of any kind.

---

## 2. Baseline

Verified before recording this decision:

```text
branch:       main
HEAD:         de07a8b78b9832956c29790cf52f544427921a26
origin/main:  de07a8b78b9832956c29790cf52f544427921a26
              (HEAD == origin/main)

B9.98 state:  IMPLEMENTED / VERIFIED / CLOSED / PUBLISHED
              implementation commit 60d7f6f9d5a94af7333bd0482c1b5224c7e898d6
              closure commit        de07a8b78b9832956c29790cf52f544427921a26

Full suite:   2413 passed, 2801 subtests, 0 failures
B9.98 tests:  5 passed, 2 subtests, 0 failures
```

B9.98 is the highest verified main roadmap block at this baseline.

---

## 3. Decision Context

B9.98 established the Single Current Artifact State architecture with an
Explicit Revision-Aware Replacement Policy: revision is metadata/state, not
artifact identity. The verified behavior is:

```text
known requested revision == stored revision     -> ALREADY_DOWNLOADED
known requested revision != stored revision     -> BLOCKED
unknown stored revision + known request         -> BLOCKED
requested revision == None                      -> preserve legacy behavior
```

The B9.98 tests explicitly validate that BLOCKED preserves artifact bytes,
manifest bytes and directory contents. BLOCKED is the currently ratified
policy; it is not an unfinished implementation.

Three read-only audits preceded this decision:

1. the B9.98+ Post-B9.98 Architectural Direction Evidence Audit, which
   compared Option A/B/C/D and returned "EVIDENCE SUFFICIENT FOR HUMAN
   DECISION";
2. the B9.98+ Human Architectural Decision Preparation Audit, which
   re-verified the decision-sensitive claims and returned "READY FOR HUMAN
   ARCHITECTURAL DECISION";
3. this record, which documents the resulting human decision.

The audits established, among other facts: no demonstrated requirement for
revision coexistence, rollback, history or replacement; a fully green test
suite; a single production acquisition authority chain; a display/test-seam
only role for legacy `ModelSource`; substantial internal Discovery/Library
backend capability with presentation surfaces explicitly unauthorized; and
governance that permits deferring successor allocation.

---

## 4. Considered Options

```text
OPTION A — Revision Lifecycle Evolution
OPTION B — Acquisition / Source Convergence
OPTION C — Discovery / Model Library Direction
OPTION D — No Successor Yet
```

Option A lacked any demonstrated current requirement: no evidence of
simultaneous physical revisions, revision history, rollback, or replacement
instead of refusal. Option B had the strongest positive architectural
continuity but its remaining work classifies as already-ratified execution,
deferred policy questions, and one bounded future decision surface (legacy
`ModelSource` convergence) — see section 7.2. Option C's internal backend
capability already exists, while persistent Model Library, GUI/presentation
and ranking remain explicitly unauthorized and undemanded. Option D is
governance-valid under the roadmap's allocation policy and preserves every
ratified decision.

## 5. Human Decision

**Selected: Option D — No Successor Yet / Defer Successor Allocation**

> CastleArq will not allocate a successor block after B9.98 at this time.

B9.98 remains the highest verified main roadmap block.

No B9.99 identifier is allocated, reserved, selected, or authorized by this
decision.

This is an intentional architectural/governance decision, not an omission.

---

## 6. Rationale

Option D is selected because:

1. B9.98 is complete and verified (full suite 2413 passed / 2801 subtests /
   0 failures; B9.98 targeted 5 passed / 2 subtests).
2. The current architecture is coherent across
   `Discovery → Identity Admission → Acquisition Resolution → Artifact Lifecycle`.
3. No current architectural conflict has been demonstrated.
4. No current revision lifecycle requirement has been demonstrated; B9.98's
   BLOCKED behavior is verified, tested, and sufficient for all evidenced
   workflows.
5. Acquisition-First (B9.94) remains valid without requiring immediate
   continuation.
6. Legacy `ModelSource` does not currently create competing acquisition
   authority.
7. Discovery/Library backend capability is sufficient for currently
   authorized scope.
8. GUI/persistent-library expansion remains intentionally unauthorized.
9. No demonstrated user requirement forces a successor (the issue tracker is
   empty).
10. Governance explicitly permits deferring successor allocation: the roadmap
    numbering rule computes the next number only when an allocation procedure
    runs, prior closure records allocate no successor identifier, and the
    repository's own decision-space precedent includes "Defer allocation;
    allocate no new block".
11. Future allocation remains possible whenever concrete evidence appears.

> Option D is an active architectural decision to preserve the current
> stable boundary, not a statement that CastleArq's architecture is
> permanently complete.

---

## 7. Acquisition-First Continuity

### 7.1 Ratified direction vs. successor allocation

B9.94 Acquisition-First remains valid. It is NOT rescinded. It remains part
of CastleArq's architectural direction.

However:

> The existence of a ratified architectural direction does not constitute
> standing authorization to continuously allocate successor roadmap blocks.

B9.94 explicitly permits future increments; it does not require immediate
continuation. Therefore:

```text
B9.94 remains OPEN for future increments
        ≠
B9.99 must be allocated now
```

This decision does NOT invalidate:

- B9.94 (Acquisition-First Product Direction);
- B9.95 (Identity Admission Registry);
- B9.96 (Acquisition Resolution Boundary);
- B9.97 (Revision-Aware Acquisition);
- B9.98 (Revision-Aware Artifact Lifecycle);
- the Acquisition-First architectural model.

It simply establishes B9.98 as the current verified endpoint.

### 7.2 Option B considered seriously; remaining work classified

Option B was considered seriously because it has the strongest positive
architectural continuity. Its remaining work is classified as follows.

Already ratified / implemented (no new block required merely because further
execution or user-facing exposure remains possible):

- Identity Admission (deterministic derivation, persistent forward-only
  registry);
- acquisition bindings and acquisition resolution;
- canonical locator resolution;
- revision-aware acquisition;
- revision-aware lifecycle policy (B9.98).

Legacy `ModelSource`: remains a legacy seam. Current evidence shows no
competing production acquisition authority, no correctness defect, no failing
test, no issue requiring its removal, and no current invariant violation. Its
current role is effectively metadata display and a compatibility/test seam.

> `ModelSource` convergence is recognized as a legitimate future
> architectural decision surface, but there is insufficient present
> evidence to allocate that decision now.

The future possibility of a bounded `ModelSource` convergence decision is
explicitly preserved. It is NOT authorized here.

Deferred policy questions (B9.96 deferred surfaces, including multi-locator
acquisition and runtime derived-identity resolution) remain future decision
surfaces where previously documented; none is a demonstrated current
requirement.

---

## 8. Option C — Discovery / Model Library

CastleArq already has substantial internal backend capability: discovery
search, repository inspection, variants, discovered artifacts, the
catalog/query boundary, dynamic model library composition (live/stateless),
and the Discovery → Acquisition flow, with CLI `search` and `inspect`
surfaces.

The evidence does NOT establish a current requirement for:

- a persistent Model Library;
- a GUI or presentation layer;
- ranking, recommendation, or fuzzy matching;
- presentation-layer expansion.

Existing governance explicitly withholds authorization for those surfaces
(Product Vision ADR D6/D8/D11/D12 and their explicit non-authorizations; the
roadmap record requiring any presentation mechanism to obtain its own
architectural decision; repeated block non-goals).

> Option C is not selected.

Existing backend capability is not reinterpreted as authorization to build
the future product surface. Product vision alone is not treated as user
demand.

---

## 9. Consequences

```text
Highest verified main block: B9.98
Successor allocated:          NO
B9.99 reserved:               NO
B9.99 selected:               NO
Implementation authorized:    NO
Architecture frozen forever:  NO
Future allocation possible:   YES
```

Future numbering must continue to follow the repository's allocation
procedure (roadmap register sections 6, 7 and 11). When a future
architectural trigger exists, the allocation procedure must be executed
again.

This document does NOT pre-create B9.99, does NOT reserve the identifier,
and does NOT create placeholder roadmap sections.

## 10. Future Triggers

Future triggers listed below are future triggers, not current requirements.

| Trigger | Condition that could justify reopening |
| --- | --- |
| **Trigger A — Revision Lifecycle** | Evidence demonstrating an actual requirement such as: simultaneous physical revisions; rollback; revision history; replacement instead of refusal; or another concrete workflow where BLOCKED is insufficient. |
| **Trigger B — Acquisition / Source Convergence** | A real architectural conflict involving `ModelSource`; a concrete requirement to converge/deprecate the legacy seam; activation of the deferred admission/binding surface; a concrete multi-locator requirement; a concrete runtime derived-identity requirement; or another explicitly activated Acquisition-First architectural surface. |
| **Trigger C — Discovery / Library** | Actual user/product requirements demonstrated; a human ADR authorizing persistent library behavior; a human ADR authorizing GUI/presentation; or ranking/recommendation becoming an explicitly justified architectural requirement. Product vision alone is not sufficient evidence. |
| **Trigger D — Reopen Decision** | New evidence demonstrating that the current architecture is insufficient, at which point a new human architectural decision is required. |

---

## 11. Explicit Non-Decisions

This ADR does NOT decide:

- multi-revision coexistence;
- rollback;
- revision history;
- replacement semantics;
- `ModelSource` removal;
- `ModelSource` deprecation;
- persistent Model Library;
- GUI;
- ranking;
- recommendation;
- fuzzy matching;
- multi-locator acquisition;
- runtime derived identity;
- new identity registries;
- locator redesign;
- acquisition authority redesign;
- automatic binding mutation;
- provider federation;
- new user-facing admission/binding surfaces.

These remain future decision surfaces where previously documented.

---

## 12. Preserved Architectural Invariants

This decision preserves the current architectural invariants:

1. Discovery remains distinct from Identity Admission.
2. Identity Admission remains distinct from Acquisition Resolution.
3. Acquisition Resolution remains distinct from Artifact Lifecycle.
4. Revision remains metadata, not model identity.
5. The B9.98 single-current-state lifecycle policy remains authoritative.
6. `BLOCKED` remains the correct result for unauthorized revision mismatch.
7. Acquisition does not mutate persistent bindings automatically.
8. Canonical acquisition resolution remains authoritative.
9. No GUI is authorized.
10. No persistent Model Library is authorized.
11. No ranking/recommendation layer is authorized.
12. Legacy `ModelSource` remains outside production acquisition authority.

No new invariant is introduced by this decision.

---

## 13. Risk Assessment

| Risk | Assessment |
| --- | --- |
| Architectural | LOW — no boundary moves; every ratified contract stays in force. |
| Scope | LOW — no scope is opened; recorded deferrals stay where they are. |
| Authority | LOW — no authority is created, duplicated or transferred. |
| Complexity | LOW — no new mechanism, abstraction or registry is introduced. |
| Premature abstraction | LOW — nothing is built ahead of demonstrated need. |
| Dependency | LOW — no dependency, manifest, storage or surface is affected. |

The decision is reversible:

> Deferring successor allocation does not prevent future allocation; it
> preserves the ability to respond to evidence later.

The architecture is not described as permanently frozen; section 10 defines
the evidence-based reopening path.

## 14. Future Allocation Rule

> No successor block is created by this ADR.

If a future trigger appears, the repository must return to the formal
allocation procedure. The next computed main block would then be derived from
the highest verified main block at that future time, rather than being
reserved now. At the current baseline, that floor is B9.98.

---

## 15. Evidence References

- B9.98 implementation and closure: roadmap register section 41
  (allocation record and closure record §41.12); implementation commit
  `60d7f6f9d5a94af7333bd0482c1b5224c7e898d6`; closure commit
  `de07a8b78b9832956c29790cf52f544427921a26`.
- B9.98 HADR:
  `docs/b998-revision-coexistence-and-artifact-lifecycle-human-architectural-decision-record.md`.
- B9.98+ Post-B9.98 Architectural Direction Evidence Audit — read-only audit
  performed in this session (evidence report; not a repository file).
- B9.98+ Human Architectural Decision Preparation Audit — read-only audit
  performed in this session (evidence report; not a repository file).
- B9.94 Acquisition-First HADR:
  `docs/b994-acquisition-first-human-architectural-decision-record.md`, and
  the B9.94 Identity Admission Boundary and Acquisition Separation HADR:
  `docs/b994-identity-admission-boundary-and-acquisition-separation-human-architectural-decision-record.md`;
  roadmap register section 37.
- B9.95 Identity Admission Registry decision: roadmap register section 38.
- B9.96 Acquisition Resolution decision:
  `docs/acquisition-resolution-human-architectural-decision-record.md`;
  roadmap register section 39 (D1–D7 ratified with deferred surfaces).
- B9.97 Revision-Aware Acquisition decision:
  `docs/b997-revision-aware-acquisition-human-architectural-decision-record.md`;
  roadmap register section 40.
- Product Vision ADR: `docs/product-vision-adr.md` (D6, D8, D11, D12 and
  explicit non-authorizations).
- Post-B9.90 decision-preparation record (decision-space precedent,
  including "Defer allocation; allocate no new block"):
  `docs/post-b990-architectural-decision-preparation.md`.

---

## 16. Final Decision Statement

```text
Decision:                     SELECTED
Option:                       D — No Successor Yet / Defer Successor
                              Allocation
Status:                       RATIFIED
B9.99:                        NOT ALLOCATED
Implementation authorization: NONE
```

Evidence → Human Architectural Decision → D selected → no successor
allocation → stable verified endpoint at B9.98 → future trigger-based
reopening under the repository's formal allocation procedure.



