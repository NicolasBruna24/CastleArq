# B9.99 — Implementation Authorization

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:                 Human Architectural Decision Record (HADR)
SUBJECT:                       B9.99 — Explicit Admitted Hugging Face GGUF
                               Execution Path — Implementation Authorization
DECISION:                      AUTHORIZED — HUMAN IMPLEMENTATION AUTHORIZATION
                               GRANTED FOR B9.99
DECISION AUTHORITY:            PROJECT OWNER (human decision)
DECISION STATUS:               RECORDED — GOVERNANCE RECONCILIATION (B5)
SCOPE AUTHORIZED:              The roadmap scope of section 42 (42.4-42.9)
                               only, bounded by 42.6 non-goals and 42.10
DATE:                          NOT ASSERTED — this record does not establish
                               a date
FINDINGS RESOLUTION:           B1, B2, B3 subsequently resolved; recorded in
                               docs/b999-human-findings-resolution-human-
                               architectural-decision-record.md
VERIFICATION:                  SUCCEEDED — see section 6
REAL-WORLD ACCEPTANCE:         PENDING — drill required by 42.9 not performed
FINAL B9.99 ACCEPTANCE:        PENDING — closure per 42.12 not performed
B9.100:                        NOT CREATED / NOT AUTHORIZED
PUSH:                          NOT PERFORMED
```

This record makes the human implementation authorization required by
§42.10 explicitly representable in the repository. The allocation itself
(§42) did not authorize implementation; a separate human authorization did,
and this record represents it.

---

## 2. Historical chain this record belongs to

```text
B9.98 CLOSED
    ↓
Post-B9.98 Human Architectural Decision
    (docs/post-b998-architectural-direction-human-architectural-decision-record.md)
    ↓
B9.99 ALLOCATED
    (roadmap section 42, Option B; allocation-time state preserved in 42.1/42.13)
    ↓
B9.99 IMPLEMENTATION AUTHORIZED
    (this record)
    ↓
B9.99 IMPLEMENTED
    (section 3)
    ↓
B9.99 B1/B2/B3 FINDINGS RESOLVED
    (docs/b999-human-findings-resolution-human-architectural-decision-record.md)
    ↓
B9.99 B1/B2/B3 VERIFIED
    (section 6; findings record section 4)
    ↓
B9.99 REAL-WORLD ACCEPTANCE PENDING
    (roadmap 42.9/42.12 remain open)
```

No step in this chain is collapsed into another. Allocation, authorization,
implementation, findings resolution, verification, and acceptance are
distinct states.

---

## 3. Scope authorized

```text
AUTHORIZED:
- Implement the section 42.4 objective through the existing authorities only:
  explicit admitted identity + executable model description, explicit
  acquisition binding through the existing ModelStore/acquisition path,
  existing compatibility evaluation, existing mandatory execution
  admission, existing runner execute and chat.
- The minimal corrective changes later decided as findings B1, B2 and B3
  (see the findings-resolution record).
- The explicit CLI/application surface required by B3 on the existing
  castlearq CLI only.

NOT AUTHORIZED (unchanged from the allocation and this authorization):
- New architecture, new product functionality beyond section 42.4.
- B9.100 or any successor.
- GUI, HTTP surface, new backend, new registry.
- Automatic lifecycle behavior (refresh, reconciliation, binding,
  admission, selection all remain explicit).
- Revision history/rollback or model-management expansion.
- The real-world acceptance drill itself and final B9.99 acceptance
  (both remain PENDING under 42.9 and 42.12).
- Push to origin, tags, releases.
```

---

## 4. Subsequent implementation

Implementation subsequently occurred and is contained in the same
governance/implementation commit that introduces this record:

```text
New modules:       castlearq/admitted_models.py
                   castlearq/admitted_resolution.py
                   castlearq/admitted_commands.py
Changed files:     castlearq/resolver.py (explicit admitted-identity
                      resolution branch; curated catalog path untouched)
                   castlearq/main.py (admitted CLI group registration,
                      dispatch, options, flag scoping)
                   castlearq/evaluate_compatibility.py (comment documenting
                      evaluation read-only behavior w.r.t. admitted store)
                   README.md (command-reference rows for admitted --op)
                   docs/roadmap-register-and-numbering-policy.md
                      (section 42 state reconciliation, see 42.13)
New tests:         tests/test_b999_admitted_path.py
                   tests/test_b999_journey.py
```

The commit hash of this record's own commit is not asserted here (a commit
cannot contain its own hash; the repository policy already rejects a second
commit for a single field — see §11 of this roadmap document).

---

## 5. Findings subsequently resolved

After implementation, the Human Findings Resolution Decision was taken:

```text
B1 → correct implicit durable observation mutation     (resolved)
B2 → typed material-conflict discrimination            (resolved)
B3 → minimal user-reachable CLI surface                (resolved)
B5 → reconcile repository governance                   (deferred at decision
                                                        time; executed under
                                                        the separate B5
                                                        authorization)
```

The decision text is preserved verbatim in
`docs/b999-human-findings-resolution-human-architectural-decision-record.md`.

---

## 6. Verification succeeded

```text
Pre-B5 read-only verification audit:
  B1 = VERIFIED, B2 = VERIFIED, B3 = VERIFIED
  Regression = NONE; Architectural scope = CLEAN
  Full suite independently reproduced: 2421 passed, 2801 subtests,
  0 failures

Pre-commit verification rerun (this reconciliation):
  Full suite: 2421 passed, 2801 subtests, 0 failures
  Result: PASSED — identical to the audited baseline
```

---

## 7. What remains pending

```text
Real-world public non-curated Hugging Face GGUF drill: PENDING (42.9)
Read-only closure audit and closure record:            PENDING (42.12)
Final B9.99 acceptance:                                PENDING
B9.100:                                                NOT CREATED /
                                                       NOT AUTHORIZED
Push:                                                  NOT PERFORMED
```

B9.99 must not be represented as accepted or closed until 42.9 and 42.12
are satisfied under a separate authorization.
