# Post-B9.99 — Human Architectural Decision Record

## Option B — Stabilize CastleArq Core First (selected direction)

**Decision Status:** DECIDED — OPTION B SELECTED
**Decision Type:** Human Architectural Direction
**Scope:** Post-B9.99 architectural direction
**Implementation Authorization:** NOT GRANTED BY THIS RECORD
**Successor Allocation:** NOT CREATED BY THIS RECORD
**B9.100:** NOT AUTHORIZED
**Repository Mutation:** NONE AUTHORIZED BY THIS RECORD

---

## 1. Status

```text
DOCUMENT TYPE:                 Human Architectural Decision Record (HADR)
SUBJECT:                       Post-B9.99 Architectural Direction
DECISION:                      SELECT — OPTION B (architectural direction, ratified)
DECISION STATUS:               RATIFIED
B9.99:                         CLOSED
B9.100:                        NOT CREATED / NOT AUTHORIZED
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

## 1.1 Follow-up Decision Record

The follow-up decision recorded under the Option B direction is **Option C — Bounded
Stabilization + Validation**.

**Decision Status:** DECIDED — OPTION C SELECTED

```text
Selected:                     Option C — Bounded Stabilization + Validation
Purpose:                      Establish objective behavioral evidence about the
                               coexistence of legacy `run` and application
                               `execute` execution paths before any architectural
                               change is considered.
Explicit non-decision:          This decision does NOT decide convergence, retention,
                               deprecation, replacement, canonicalization, or
                               removal of either path. Those remain future human
                               decisions.
Evidence boundary:              P1 Genuine Current Core Problems = 0; two execution
                               roads exist; architectural divergence exists; behavioral
                               divergence has NOT been demonstrated; no parity test
                               currently establishes equivalence;
                               B9.12/B9.13/B9.19 are already implemented;
                               Observation → Knowledge → Evaluation is integrated;
                               B9.14 application wiring is implemented and tested.
Next authorized phase:          Only a READ-ONLY behavioral evidence audit comparing
                               `run` and `execute`. No implementation authorization
                               is granted.
```

---

## 2. Decision Context

B9.99 is closed.

The B9.99 admitted Hugging Face GGUF execution path has passed:

```text
Discover
→ Select
→ Admit
→ Describe
→ Bind
→ Acquire
→ Verify
→ Evaluate
→ Execute
→ Chat
```

The final implementation and governance state is clean and synchronized:

```text
HEAD:
d131adf0739291fe0000eb72bc8aebd6ef462b2f

origin/main:
d131adf0739291fe0000eb72bc8aebd6ef462b2f

Working tree:
CLEAN
```

B9.99 was therefore accepted and closed.

A subsequent READ-ONLY post-B9.99 architectural audit evaluated four possible directions:

* **A — Continue evolving acquisition/model lifecycle**
* **B — Stabilize CastleArq Core First**
* **C — Begin CastleArq Desktop**
* **D — Defer successor allocation**

The audit found that CastleArq is functionally coherent and that its principal remaining architectural concerns are not centered on acquisition correctness, but on the consistency and maturity of the application-facing core.

In particular, the audit identified evidence around:

* B9.12 boundary adapter remaining specification-only;
* B9.13 integration remaining specification-only;
* multiple execution roads remaining in the repository;
* B9.19 application-level execution use case remaining specification-only/not started;
* an application boundary that exists in parts but is not yet fully stabilized as a coherent public-facing contract;
* structured diagnostics and chat lifecycle abstractions that remain more internal than stable application contracts.

These findings do **not** constitute implementation authorization.

They constitute the architectural context for the human decision recorded here.

---

## 3. Options Considered

### Option A — Continue evolving acquisition/model lifecycle

This would continue the acquisition/model-management line represented by B9.83–B9.99.

Assessment:

* Strategic fit: MEDIUM
* Architectural fit: MEDIUM
* Evidence strength: MEDIUM
* Current necessity: WEAK
* Risk: MEDIUM
* Reversibility: HIGH

The post-B9.98 and post-B9.99 evidence does not demonstrate a sufficiently strong current requirement for another acquisition/lifecycle evolution immediately after B9.99.

The acquisition path is now materially stronger than it was before B9.99, including successful real-world validation of a non-curated admitted GGUF path.

Therefore Option A is not selected as the immediate architectural direction.

---

### Option B — Stabilize CastleArq Core First

This direction prioritizes architectural coherence and application-boundary stabilization before expanding CastleArq into larger product surfaces.

Assessment:

* Strategic fit: MEDIUM
* Architectural fit: HIGH
* Evidence strength: MEDIUM
* Current necessity: MEDIUM
* Risk: MEDIUM-LOW
* Reversibility: HIGH

The strongest evidence supporting this option is that CastleArq already possesses substantial functional capability, while several architectural boundaries intended to organize those capabilities remain incomplete or insufficiently stabilized.

This creates an opportunity to improve the coherence of the existing system before adding a larger consumer surface.

**Option B is therefore selected.**

---

### Option C — Begin CastleArq Desktop

This would move directly toward a desktop/GUI product surface.

Assessment:

* Strategic fit: WEAK
* Architectural fit: WEAK
* Evidence strength: WEAK
* Current necessity: WEAK
* Risk: HIGH
* Reversibility: MEDIUM

The existing system does not yet expose sufficiently stable application-level contracts to justify making a Desktop surface the immediate architectural priority.

A Desktop implementation at this point would risk coupling the new surface directly to:

* ModelStore internals;
* identity-admission registry details;
* acquisition binding mechanisms;
* runtime-specific session implementation;
* internal diagnostics;
* transitional execution paths.

Option C is therefore rejected as the immediate direction.

This rejection is **not** a permanent rejection of CastleArq Desktop.

It means only that Desktop should not be the next architectural commitment.

---

### Option D — Defer successor allocation

This would make no immediate architectural commitment after B9.99.

Assessment:

* Strategic fit: MEDIUM
* Architectural fit: MEDIUM
* Evidence strength: MEDIUM
* Current necessity: MEDIUM
* Risk: LOW
* Reversibility: HIGH

Option D remains defensible because:

* B9.99 is closed;
* the test suite is green;
* the product is coherent;
* no critical production failure requires immediate intervention;
* additional real-world usage could provide useful evidence.

However, the READ-ONLY audit identified concrete architectural concerns that are sufficiently substantiated to justify bounded stabilization work.

Therefore Option D is not selected.

---

## 4. Human Decision

### DECISION: OPTION B — STABILIZE CASTLEARQ CORE FIRST

The human architectural decision is to prioritize **stabilization of CastleArq's existing core architecture** before pursuing a new product surface or another acquisition/model-lifecycle expansion.

The purpose of this direction is to reduce architectural ambiguity and consolidate the existing capabilities into stronger application-facing boundaries.

The decision is intentionally broader than any single implementation task.

It establishes a **direction**, not an implementation specification.

---

## 5. What "Stabilize the Core" Means

For purposes of this decision, stabilization means investigating and, where justified by subsequent evidence and authorization, improving the coherence of the existing application architecture.

Areas that may be relevant include:

1. Boundary between observation/knowledge/evaluation layers.
2. Integration between the existing domain capabilities and application layer.
3. Consolidation of execution paths.
4. Stabilization of application-level execution contracts.
5. Clarification of diagnostics as an application-facing capability.
6. Clarification of chat/session lifecycle at the application boundary.
7. Establishment of sufficiently stable DTOs/contracts where external consumers would otherwise depend on implementation details.

These are **areas of investigation**, not automatically authorized implementation tasks.

No individual item in this list is independently authorized by this ADR.

---

## 6. What This Decision Does NOT Mean

Selecting Option B does **not** mean:

* automatically implementing B9.12;
* automatically implementing B9.13;
* automatically implementing B9.19;
* automatically allocating B9.100;
* automatically creating a new roadmap block;
* automatically modifying execution architecture;
* automatically deleting legacy execution paths;
* automatically creating a public API contract;
* automatically creating a Desktop application;
* automatically creating a Model Library;
* automatically expanding supported runtimes;
* automatically changing the acquisition architecture;
* automatically changing Identity Admission;
* automatically changing Artifact Lifecycle;
* automatically changing B9.99;
* automatically modifying the roadmap register.

Each concrete implementation must remain subject to its own evidence review, architectural decision, explicit scope, implementation authorization, verification, and closure.

---

## 7. Relationship to B9.99

B9.99 remains closed.

This decision does not reopen B9.99.

The B9.99 implementation, acceptance evidence, correction history, and governance reconciliation remain authoritative historical records.

The successful B9.99 real-world validation is treated as evidence that the admitted acquisition/execution path is sufficiently functional to permit attention to move toward core architectural stabilization.

No B9.99 behavior is to be changed merely because Option B has been selected.

---

## 8. Architectural Rationale

The principal reason for selecting Option B is **not that CastleArq is broken**.

CastleArq is not considered architecturally failed.

Rather, the evidence indicates that CastleArq has reached a point where:

```text
functional capability
        >
architectural boundary maturity
```

in several areas.

The system already contains meaningful capabilities for:

* discovery;
* selection;
* identity admission;
* acquisition;
* verification;
* model storage;
* compatibility evaluation;
* admission;
* execution;
* chat;
* CLI access;
* HTTP/API access.

The architectural concern is that some of these capabilities do not yet converge cleanly through a single mature application-facing structure.

Stabilizing those boundaries before adding another major surface reduces the probability that future consumers will become coupled directly to internal implementation details.

---

## 9. Execution Architecture Consideration

Execution receives particular attention under this decision.

The current system contains more than one execution road, including legacy execution surfaces and the newer application-oriented direction represented by the B9.19 specification.

The existence of multiple roads is not by itself proof that immediate deletion or replacement is required.

Therefore the human decision is:

> **Investigate execution-path convergence as part of core stabilization, without prescribing the final implementation architecture in advance.**

Any future decision to unify, deprecate, retain, or replace a specific execution path must be supported by a separate evidence-based decision.

---

## 10. B9.12 and B9.13 Consideration

The post-B9.99 audit identified:

```text
B9.12 — specification exists; implementation not present
B9.13 — specification exists; implementation not present
```

These specifications are therefore relevant evidence for Option B.

However:

> Their existence does not automatically establish that both must now be implemented.

The next architectural work must first determine whether the specifications still represent the correct boundaries for the current system.

If implementation is later justified, it must receive explicit authorization.

---

## 11. B9.19 Consideration

B9.19 represents an application-level execution use case that remains specification-only/not started according to the current audit.

It is therefore relevant to the execution-boundary stabilization question.

However, this ADR does not authorize B9.19 implementation.

A future READ-ONLY evidence audit may determine whether:

* B9.19 remains the correct application boundary;
* it requires revision;
* it should be implemented;
* it should be replaced by another design;
* or it should be deferred.

The human decision remains intentionally independent of that implementation question.

---

## 12. Desktop Direction

Desktop remains a possible long-term product direction.

Option B does not cancel that goal.

Instead, the architectural position is:

```text
Core stabilization
        ↓
Stronger application boundaries
        ↓
Future product surfaces become safer
```

A future Desktop decision should therefore be made against the stabilized architecture rather than against the current collection of internal services and transitional paths.

No Desktop implementation is authorized by this ADR.

---

## 13. Product Scope Boundary

This decision does not expand CastleArq's product scope.

The following remain outside the scope of this decision unless separately authorized:

* GUI/Desktop;
* Model Library;
* multi-runtime orchestration;
* multi-GPU orchestration;
* clusters;
* distributed execution;
* fine-tuning;
* LoRA/QLoRA;
* RAG;
* agents;
* marketplace;
* hosted/cloud inference;
* unrelated acquisition lifecycle features.

The objective is **architectural consolidation of the existing CastleArq core**, not broad product expansion.

---

## 14. Evidence Threshold for Subsequent Work

Future implementation proposals under this direction should establish:

1. The exact architectural problem.
2. Existing implementation evidence.
3. Existing specification/ADR evidence.
4. Why the problem matters now.
5. The smallest viable architectural correction.
6. Compatibility implications.
7. Legacy-path implications.
8. Test and verification implications.
9. Whether an existing specification remains valid.
10. Whether the proposed work requires a new roadmap block.

No implementation should be inferred merely from the selection of Option B.

---

## 15. Governance Constraints

The following constraints remain active:

### B9.99

```text
CLOSED
```

### B9.100

```text
NOT CREATED
NOT AUTHORIZED
```

### Successor allocation

```text
NONE
```

### Repository mutation

This ADR itself does not authorize:

* source modifications;
* test modifications;
* documentation mutations elsewhere;
* commits;
* pushes;
* roadmap allocation;
* implementation.

---

## 16. Required Workflow After This Decision

Future work should continue using the established CastleArq governance sequence:

```text
READ-ONLY evidence audit
        ↓
Human architectural decision
        ↓
Explicit implementation authorization
        ↓
Scoped implementation
        ↓
Verification
        ↓
Real-world acceptance where applicable
        ↓
Closure audit
        ↓
Governance reconciliation
        ↓
Explicit commit authorization
        ↓
Explicit push authorization
```

Selecting Option B does not bypass this sequence.

---

## 17. Final Human Decision Statement

> **CastleArq will prioritize stabilization of its existing core architecture before beginning Desktop development or pursuing another acquisition/model-lifecycle expansion.**
>
> The immediate objective is to improve architectural coherence, clarify application-facing boundaries, and reduce transitional execution-path ambiguity.
>
> This decision establishes architectural direction only. It does not authorize implementation of B9.12, B9.13, B9.19, B9.100, or any other successor block.
>
> Each concrete architectural change must be independently supported by evidence and explicitly authorized before implementation.

---

## 18. Final Status

| Item                         | Decision                                      |
| ---------------------------- | --------------------------------------------- |
| B9.99                        | **CLOSED**                                    |
| Post-B9.99 direction         | **OPTION B — STABILIZE CASTLEARQ CORE FIRST** |
| Option A (post-B9.99 audit)  | Not selected                                  |
| Option B (selected direction)| **SELECTED**                                  |
| Option C (post-B9.99 audit)  | Not selected                                  |
| Option D (post-B9.99 audit)  | Not selected                                  |
| Option C (this record)       | **SELECTED — Bounded Stabilization + Validation** |
| B9.12                        | Not authorized by this ADR                    |
| B9.13                        | Not authorized by this ADR                    |
| B9.19                        | Not authorized by this ADR                    |
| B9.100                       | **NOT CREATED / NOT AUTHORIZED**              |
| Successor allocation         | **NONE**                                      |
| Implementation authorization | **NONE**                                      |
| Repository mutation          | **NONE AUTHORIZED**                           |
| Commit                       | **NONE**                                      |
| Push                         | **NONE**                                      |

---

## 19. Architectural Direction

**FINAL HUMAN DECISION:**

```text
POST-B9.99
        ↓
OPTION B SELECTED
        ↓
STABILIZE CASTLEARQ CORE FIRST
        ↓
NO AUTOMATIC IMPLEMENTATION
        ↓
NO B9.100
        ↓
NEXT STEP: READ-ONLY EVIDENCE AUDIT
        ↓
NEXT LEVEL: OPTION C — BOUNDED STABILIZATION + VALIDATION
```

This record intentionally separates the architectural direction from the implementation decision.

**B is selected.** The architectural direction is stabilization of the core.

**C is selected as a bounded follow-up decision.** Under this direction, the human has selected
bounded stabilization + validation: an evidence-gathering phase that authorizes a
READ-ONLY behavioral evidence audit comparing `run` and `execute`, and decides NO execution
architecture (no convergence, retention, deprecation, or replacement).

**The implementation scope remains undecided.**
