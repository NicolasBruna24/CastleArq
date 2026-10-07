# B9.99 — Human Findings Resolution Decision

## Human Architectural Decision Record

---

## 1. Decision Status

```text
DOCUMENT TYPE:      Human Architectural Decision Record (HADR)
SUBJECT:            B9.99 — Post-Implementation Findings Resolution
                    (B1, B2, B3, B5)
DECISION:           RESOLVED — B1, B2, B3 CORRECTED IN THE IMPLEMENTATION;
                    B5 DEFERRED TO A SEPARATE HUMAN AUTHORIZATION
DECISION AUTHORITY: PROJECT OWNER (human decision)
DECISION STATUS:    RATIFIED — the decision as taken is preserved in
                    section 2; this record does not rewrite it
SCOPE:              Governance and the minimal corrective changes to the
                    existing B9.99 implementation only
DATE:               NOT ASSERTED — this record does not establish a date
CODE IMPACT:        NONE FROM THIS RECORD — the B1/B2/B3 corrective changes
                    are part of the B9.99 implementation itself; this
                    record changes no code
PUSH:               NOT PERFORMED
```

This record represents — it does not rewrite — the previously decided B9.99
Human Findings Resolution Decision. The decision text is preserved verbatim in
section 2. No new finding is introduced here, and the decision is not
converted into a roadmap milestone.

---

## 2. The decision as taken

```text
B1
→ correct implicit durable observation mutation

B2
→ replace stringly-typed material-conflict discrimination with typed signal

B3
→ provide minimal user-reachable CLI/application surface

B5
→ reconcile repository governance
```

---

## 3. Resolution and verification status (evidence-based)

### B1 — RESOLVED / VERIFIED

Durable observation writes are confined to the single explicit path
`observe_command` in `castlearq/admitted_commands.py`. Ordinary compatibility
evaluation and model resolution only read admitted observations (material
conflicts feed the fail-closed gate); they never create, append, or persist
observations and never mutate durable admitted state. Pinned by
`tests/test_b999_admitted_path.py::B9999Tests` —
`test_evaluation_does_not_implicitly_record_observations` and
`test_explicit_observe_and_cli_surface`.

### B2 — RESOLVED / VERIFIED

Material conflicts are discriminated by the typed exception
`AdmittedMaterialConflictError` (subclass of `AdmittedResolutionError`) in
`castlearq/admitted_resolution.py`, caught by type in
`castlearq/resolver.py`, and failed closed as
`ModelArtifactResolutionError` with the typed cause preserved. No
message-substring control flow exists on any admitted/resolver/evaluation
path. Unknown identities continue to fall through to the B9.67
imported-label fallback. Pinned by
`tests/test_b999_admitted_path.py::B9999Tests::test_conflict_blocks_and_reconcile_preserves_history`
(the typed exception is asserted directly).

### B3 — RESOLVED / VERIFIED

The user-reachable surface is the single existing `castlearq` CLI group
`admitted` with explicit `--op` selection (`admit`, `describe`, `bind`,
`show`, `observe`, `refresh`, `reconcile`), registered in
`castlearq/main.py`, documented in `README.md`, and contract-pinned in both
directions by `tests/test_api_serve_contract.py::ReadmeCommandReferenceTests`.
No GUI, HTTP endpoint, new backend, or automatic lifecycle behavior was
introduced.

### B5 — RESOLVED BY SEPARATE AUTHORIZATION

B5 was intentionally deferred at decision time and later executed under the
separate human B5 governance reconciliation authorization. Its outcome is
recorded in
`docs/b999-b5-governance-reconciliation-human-architectural-decision-record.md`.

---

## 4. Verification result

```text
Pre-B5 read-only verification audit:  B1 VERIFIED, B2 VERIFIED, B3 VERIFIED,
                                      regression NONE, architectural scope CLEAN
Full test suite:                      2421 passed, 2801 subtests passed,
                                      0 failures (independently reproduced by
                                      the audit, re-confirmed before the
                                      B9.99 governance/implementation commit)
Targeted B9.99 + contract reruns:     passed, 0 failures
Real-world non-curated GGUF drill:    NOT PERFORMED — still PENDING (roadmap 42.9)
Final B9.99 acceptance:               PENDING — closure per roadmap 42.12
                                      not yet performed
B9.100:                               NOT CREATED / NOT AUTHORIZED
```

Automated verification is explicitly not a substitute for the real-world
public non-curated Hugging Face GGUF acceptance drill.

---

## 5. What this record does not do

```text
This record does NOT introduce any new finding.
This record does NOT rewrite the architectural decision text (section 2).
This record does NOT convert the decision into a roadmap milestone.
This record does NOT authorize B9.100 or any successor.
This record does NOT mark B9.99 accepted or closed.
This record does NOT authorize a push or a tag.
```
