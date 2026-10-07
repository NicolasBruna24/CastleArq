# Post-B9.90 Architectural Decision Preparation Record

```text
DOCUMENT TYPE:    Decision preparation / architectural decision material
STATUS:           PREPARATION / HUMAN RATIFICATION PENDING
DECISION STATUS:  PENDING HUMAN RATIFICATION
ALLOCATES BLOCK:  NO
ROADMAP MODIFIED: NO
IMPLEMENTATION:   NONE
PUSH:             NOT PERFORMED
```

Copyright 2026 Nicolas Bruna. Licensed under the Apache License, Version 2.0 (the
same terms as the rest of this repository).

---

## 0. What this document is

This document prepares the evidence needed for the **project owner** to decide
which architectural concern, if any, should become the next formally allocated
roadmap block.

It is written **before** the decision. It therefore:

- records only items the repository supports as `FACT`, `RECORDED DECISION`,
  `RECORDED DEFERRAL` or `OPEN QUESTION`;
- presents a **neutral decision space** without ranking, scoring or recommending;
- leaves every decision field **empty** for ratification.

## 1. What this document is NOT

```text
This document does NOT allocate B9.91.
This document does NOT authorize implementation of anything.
This document does NOT modify the roadmap register or its numbering policy.
This document does NOT alter the B9.90 CLOSED record.
This document does NOT select, rank, score or prefer any option.
```

`B9.91` remains **NOT ALLOCATED** until a subsequent formal allocation procedure
records a ratified scope and satisfies the roadmap numbering/allocation policy
(register sections 6, 7 and 11).

## 2. Evidence classification legend

| Label | Meaning |
| --- | --- |
| `FACT` | Directly verifiable in the current repository (code, tests or recorded evidence) |
| `RECORDED DECISION` | An explicit ratified decision already present in an ADR or roadmap record |
| `RECORDED DEFERRAL` | The repository explicitly defers or excludes the concern |
| `OPEN QUESTION` | The repository itself records the matter as undecided |
| `POSSIBLE OPTION` | A direction assembled only from recorded deferrals; no scope exists yet |
| `NEW PROPOSAL` | Not supported by current project intent; labeled explicitly where used |

## 3. Verified architectural baseline (immediately after B9.90)

`FACT` — acquisition path, production wired and closed:

```text
CLI (castlearq/main.py)
  -> application_wiring.compose_acquisition_service
  -> ModelAcquisitionService                     (B9.85)
  -> ModelDiscovery port / HuggingFaceDiscoveryProvider (B9.80 / B9.81)
  -> select_discovered_artifact                  (B9.84)
  -> map_discovered_artifacts                    (B9.82)
  -> ArtifactSpec                                (carrier only; B9.83)
  -> DownloadPlanner                             (canonical locator authority; B9.90)
  -> Downloader                                  (defensive validation only)
  -> ModelStore                                  (identity + manifest persistence)
```

`FACT` — execution path, separate by ratified decision:

```text
CLI "run"     -> run_service.run_once   (authoritative one-shot run boundary; B9.89)
CLI "execute" -> execute_model          (stateless use case per docs/B9.19 spec)
```

`FACT` — other boundaries present at this anchor:

| Component | State |
| --- | --- |
| `catalog_query_service` + CLI `search` | Closed (B9.86); consumes `ModelDiscovery.search` |
| `ModelExecutionService` (`execution_service.py:42`) | **LEGACY / test-only**; no production reachability |
| `HuggingFaceSource.discover_artifacts` | **LEGACY**; still referenced by the CLI (`main.py:1156`) |
| Legacy-to-port adapter (`main.py:1522-1538`) | Production; adapts legacy `ModelSource` to the B9.80 port without retiring it |

`FACT` — identity and persistence:

- `artifact_id` = `content_id` when present, otherwise a provenance digest of
  `source|repository|filename|quantization` (`models.py:82-93`). `revision` and
  `download_url` are excluded (OD-1).
- `ModelStore` persists `revision` as declared provenance and reads it back
  (`model_store.py:309-318`, `model_store.py:512-533`).
- Multi-revision coexistence is a **recorded limitation**, not implemented
  (register 19.7.3).

No proposal is made in this section.

---

## 4. Candidate analysis

Each candidate reports: current state, recorded evidence, the architectural
question, dependencies, affected boundaries and unresolved questions.
**No candidate is preferred, ranked or scored.** The order below is the order in
which the concerns were recorded in the repository, not an evaluation.

### 4.A — `run` versus `execute` convergence

- **Current state** (`FACT`): both CLI commands exist (`main.py:2694`,
  dispatched at `main.py:2935` and `main.py:2945`). `run` accepts
  `(prompt, quantization, filename)` (`main.py:2788`); `execute` accepts
  `(quantization, filename)` (`main.py:2789`). `run` routes through
  `run_service.run_once`; `execute` routes through `castlearq/execute_model.py`,
  a stateless coordinator implementing
  `docs/B9.19-execute-application-use-case-specification.md`
  (`resolve -> fresh capability -> advisory admission -> legacy compatibility
  gate -> preflight -> target selection -> ExecutionRequest -> ModelRunner ->
  ExecutionResult`).
- **Recorded decision** (`RECORDED DECISION`):
  `docs/run-boundary-architectural-decision.md` is HUMAN-RATIFIED; **Q4: REMAIN
  SEPARATE** — "run and execute remain separate capabilities; convergence is out
  of scope" (register 31, quoted at 7233-7234). Q2 (admission stays
  surface-owned) and Q3 (observable CLI contract preserved) constrain any
  future change.
- **Recorded deferral** (`RECORDED DEFERRAL`): "execution-path convergence
  (run vs execute) — NOT IMPLEMENTED" (register 28.9 at 6167; register 30.9 at
  7042); explicit B9.89 non-goal "execute_model convergence (HADR Q4)"
  (register 31.4 at 7485).
- **Provenance** (`FACT`): the B9.87 HADR section 5.2 recorded the question as
  "remains a human decision"; B9.88 recorded it as "NOT resolved by this
  allocation and remains deferred" (register at 6710-6711); B9.89's closure
  recorded "convergence remains deferred (Q4)" (register at 7784).
- **Architectural question**: should the one-shot run boundary and the execute
  use case become one capability; if so, which becomes authoritative and what
  happens to the advisory-versus-enforcing admission distinction.
- **Dependencies**: B9.89 run boundary (CLOSED); B9.19 execute specification;
  admission contract; observable CLI contract (exit codes, output ordering, stderr
  transport, warning deduplication).
- **Affected boundaries**: CLI `run`/`execute`, `run_service`, `execute_model`,
  `application_wiring` composition root, admission ownership.
- **Unresolved questions**: is convergence desirable at all; which surface owns
  admission afterwards; whether the `api.py` execute path is in scope; what
  backward-compatibility guarantee applies to the existing CLI verbs.

### 4.B — `ModelExecutionService` adoption or retirement

- **Current state** (`FACT`): `class ModelExecutionService` exists at
  `castlearq/execution_service.py:42`. A repository-wide search finds **no
  production consumer**; reachability is limited to
  `tests/test_execution_service.py` and `tests/test_execution_integration.py`.
- **Recorded classification** (`RECORDED DECISION`): the B9.78 production
  migration classified it "legacy/test-only" and excluded migrating it (register
  14.3 non-goal 3 at 663-664; reachability audit at 817-822).
- **Recorded deferral** (`RECORDED DEFERRAL`): HADR **Q5: DOES NOT
  PARTICIPATE** — "ModelExecutionService is excluded and its architecture-debt
  classification is unchanged" (register 31, at 7235-7236); a B9.89 explicit
  non-goal (7486); recorded as "recorded architectural debt" (register 30.9 at
  7062).
- **Architectural question**: keep the recorded debt, formally retire the class,
  or adopt it as a single execution boundary — and if adopted, which gate decides
  execution.
- **Dependencies**: B9.19 execute use case; B9.78 cutover decision ("a cutover,
  not a legacy cleanup"); deny-only admission contract; legacy-only tests.
- **Affected boundaries**: `execution_service.py`, execution use cases,
  test-only dependents, architecture-debt register state.
- **Unresolved questions**: is "legacy/test-only" permanent or a pending
  transition; does retirement require deleting legacy-only tests (previously an
  explicit non-goal); what is the migration path if adoption is chosen.

### 4.C — Legacy acquisition coexistence

- **Current state** (`FACT`): `HuggingFaceSource` is imported by the CLI
  (`main.py:110`) and its `discover_artifacts` is still called in production
  (`main.py:1156`). A production adapter exposes a legacy `ModelSource` through
  the B9.80 discovery port (`main.py:1522-1538`) and "never retires or deprecates
  `ModelSource`" (`main.py:1538`).
- **Recorded deferral** (`RECORDED DEFERRAL`): register 18.3 / 19.3 non-goal 2 —
  "legacy ModelSource deprecation, removal or migration" is excluded; deprecating
  the legacy `ModelSource.discover_artifacts -> list[ArtifactSpec]` path and its
  CLI consumers "is a separate block", "neither named nor numbered"
  (register at 2879-2898; also 21.6 at 3877-3883). B9.86 preserved the
  separation (register at 5027-5028). B9.85 invariant D5 keeps `ModelSource`,
  `HuggingFaceSource`, `select_artifact()` and `resolver.py` untouched
  (`acquisition_service.py:44`).
- **Architectural question**: retire, deprecate or migrate the legacy
  discovery/source path, and what the single production discovery boundary
  becomes.
- **Dependencies**: B9.80 discovery port and its legacy adapter; B9.85
  acquisition wiring; CLI consumers; legacy tests; `resolver.py` /
  `artifact_selection.py`.
- **Affected boundaries**: CLI discovery surfaces, legacy source adapter,
  discovery port, acquisition mapping inputs, existing manifests.
- **Unresolved questions**: which CLI commands are legacy consumers; what
  deprecation concretely means here (warning, removal, alias); whether stored
  manifests or documented behavior depend on legacy identifiers; whether the
  adapter is a permanent seam.

### 4.D — ModelStore / multi-revision storage coexistence

- **Current state** (`FACT`): `artifact_id` excludes `revision`
  (`models.py:82-93`), so two artifacts differing only by revision resolve to the
  same storage directory (`model_store.py:281-282`). `revision` is persisted as
  declared provenance and read back (`model_store.py:309-318`, `512-533`).
- **Recorded decision** (`RECORDED DECISION`): OD-1 — `revision` does not
  participate in `artifact_id`; absence stays `None`; existing stored artifacts
  are not relocated.
- **Recorded limitation** (`RECORDED DEFERRAL`): register 19.7.3 — artifacts
  differing only by revision "still resolve to the same artifact_id and therefore
  to the same storage directory"; a later revision can replace the stored
  artifact; "multi-revision coexistence is a separate future architectural
  question. No identifier is allocated for it here". Alternative Option A
  (revision participates in `artifact_id`) was recorded **NOT SELECTED**, with its
  consequences for existing directory identity (register at 3126-3130). B9.84
  left the limitation unchanged (3627-3628); B9.83 excluded ModelStore redesign
  (19.3 non-goal 12).
- **Architectural question**: should storage identity become revision-aware; is
  coexistence required; what happens to existing manifests and directory identity
  if identity changes.
- **Dependencies**: OD-1; B9.83 revision contract (40-hex); B9.90 canonical
  locator; manifest read/write and migration paths; `artifact_id` consumers
  (storage, importer, evaluator).
- **Affected boundaries**: `ModelStore`, `ArtifactSpec.artifact_id`, manifest
  schema and migration, importer/resolver, catalog APIs.
- **Unresolved questions**: is coexistence a real need or theoretical; would
  identity change require migrating existing stores; what compatibility guarantee
  is owed to already-downloaded artifacts; how identity would interact with
  `content_id`.

### 4.E — Model Library / HF / GGUF browsing and presentation

- **Current state** (`FACT`): discovery capability exists as
  `ModelDiscovery.inspect` / `ModelDiscovery.search`
  (`discovery.py:135-140`; `huggingface_discovery.py:298,320`), consumed by the
  B9.86 catalog/query boundary and the CLI `search` command. There is **no**
  presentation layer: no GUI, no model browser, no ranking engine in the
  repository.
- **Recorded decision** (`RECORDED DECISION`): the Product Vision ADR records
  D6 Model Library as "a **future product surface**" and D8 GUI as "accepted as a
  **future product surface**", with "GUI is **NOT authorized for implementation**
  by this ADR" and "Model Library UX remains unallocated and is NOT authorized"
  (`docs/product-vision-adr.md` §8, §10, §15). The GUI, if ever built, "must
  consume CastleArq's application/core capabilities rather than developing an
  independent business-logic implementation".
- **Recorded deferral** (`RECORDED DEFERRAL`): the catalog/query boundary "exposes
  discovery capability" and "does not become a product surface"; Model Library /
  UX / GUI remains "**NOT ALLOCATED** and **NOT AUTHORIZED**"; "a future block
  requiring any presentation mechanism is a different block **and requires its own
  architectural decision**" (register at 5014-5024). Ranking, recommendation and
  fuzzy matching were recorded as excluded and not absorbed (register 21.6 at
  3891-3892; 17.3 non-goals 14-16; 20 D6). HF model browser, GGUF catalog UX,
  model search UI and variant-selection UI are explicit B9.90 non-goals
  (register at 8190-8193).
- **Architectural question**: whether a presentation surface is authorized at
  all, and if so, which capability it consumes and which invariants bind it.
- **Dependencies**: D6/D8 in the Product Vision ADR; the catalog/query boundary
  invariant; CLI/API surface rules; discovery domain stability.
- **Affected boundaries**: discovery port, catalog/query boundary, model metadata
  representation, variant/quantization presentation, new surface(s).
- **Unresolved questions**: does authorization require a superseding ADR; is the
  GUI and Model Library one concern or two; where does ranking belong if ever
  introduced; how would a presentation surface consume acquisition without
  duplicating domain logic.

### 4.F — Chat conversation/session lifecycle

- **Current state** (`FACT`): Chat exists as a product surface with
  `run_service.open_chat_session` consumed by the CLI and the HTTP layer. No
  Conversation abstraction exists in the repository.
- **Recorded deferral** (`RECORDED DEFERRAL`): the Product Vision ADR records
  that "when future Chat work is undertaken, conversation/session lifecycle should
  be moved toward an appropriate application-level boundary rather than
  permanently remaining as application lifecycle logic inside the HTTP transport
  layer", and that "**No Conversation ADR is invented or reconstructed here: none
  currently exists in the repository**" (`product-vision-adr.md` §9). Register
  28.9 records "Chat changes / a Conversation abstraction / Chat lifecycle
  migration out of api.py" as NOT IMPLEMENTED (6160-6162); B9.88 engaged the
  application-boundary seam while leaving "the lifecycle migration ... deferred"
  (register at 6777-6779).
- **Architectural question**: whether session/conversation lifecycle should leave
  the HTTP transport layer, and whether that requires a Conversation ADR first.
- **Dependencies**: B9.88 chat application boundary (CLOSED); `api.py` chat
  handler; `run_service.open_chat_session`; session registry lifecycle.
- **Affected boundaries**: HTTP transport (`api.py`), chat application boundary,
  session lifecycle management.
- **Unresolved questions**: is a Conversation ADR a prerequisite; what is the
  target application-level seam; how is session identity/cleanup preserved.

### 4.G — Recorded CI follow-up (flaky chat-session test)

- **Current state** (`FACT`): `tests/test_chat_sessions.py:1325`
  `test_creation_concurrent_around_limit` still exists and was green in the
  post-B9.90 full suite (2160 passed / 2718 subtests / 0 failures).
- **Recorded classification** (`RECORDED DEFERRAL`): register 24.5 classified a
  CI occurrence of this test as `E — FLAKY/NON-DETERMINISTIC TEST`, with
  "B9.85 causality: NOT ESTABLISHED" and "Closure impact: NON-BLOCKING"
  (register at 4579-4600). CI/lint work was explicitly "not selected" elsewhere
  (register at 2977-2979).
- **Architectural question**: none established by the repository. This item is
  recorded here only to classify it: on the recorded evidence it is
  **test infrastructure / ordinary maintenance**, not an architectural concern.
- **Dependencies**: chat session registry; concurrency behavior under test.
- **Affected boundaries**: none architectural.
- **Unresolved questions**: whether it warrants a block, a maintenance task, or
  no action.

---

## 5. Cross-cutting architectural analysis

### 5.1 Existing stable contracts (protected unless the decision changes them)

| Contract | Evidence |
| --- | --- |
| Discovery is a port with no identity/storage side effects | B9.80/B9.81; B9.82 consumes it without modification |
| Selection is deterministic and never mutates metadata | B9.84 |
| Acquisition mapping is pure transport (no URL construction, no validation) | B9.82; preserved unchanged by B9.83/B9.90 |
| `ArtifactSpec` is a carrier; `revision` is declared provenance, not identity | `models.py:79-93`; OD-1 |
| 40-hex revision contract; no syntax broadening | register 33.7 I6 |
| `DownloadPlanner` is the sole canonical locator authority | B9.90 (CLOSED); `planner.py:305-319` |
| `Downloader` validates defensively and never constructs or repairs | B9.90; `downloader.py:115-125` |
| URL security model preserved | `planner.py:353-368`; B9.90 invariants I7 |
| Production acquisition wiring (CLI -> application_wiring -> service) | B9.85; `application_wiring.py:301`, `main.py:1510` |
| CLI surface consumes application capabilities and owns no domain logic | B9.87/B9.88; B9.89 Q2 |
| Manifest read/write round-trips `revision` without deriving state | B9.83; `model_store.py:512-533` |

### 5.2 Existing architectural debt (explicitly recorded)

```text
ModelExecutionService      LEGACY / test-only; "recorded architectural debt"
                           (register 14.7, 30.9, 31 Q5)
Legacy ModelSource path    untouched by design; deprecation "is a separate block"
                           (register 18.3, 19.3, 21.6)
Multi-revision storage     recorded limitation; "a separate future architectural
                           question" (register 19.7.3)
run / execute              separate by ratified decision; convergence deferred
                           (run-boundary ADR Q4; register 32.4)
Presentation surfaces      NOT ALLOCATED / NOT AUTHORIZED (Product Vision D6/D8)
```

### 5.3 Existing deferred decisions (only those the repository names)

1. `run` vs `execute` convergence — HADR Q4, deferred through B9.87/B9.88/B9.89.
2. `ModelExecutionService` adoption — HADR Q5, classification "unchanged".
3. Legacy source convergence — "a separate block", unnamed and unnumbered.
4. Multi-revision storage coexistence — "a separate future architectural
   question", no identifier.
5. Presentation mechanism (Model Library / GUI) — requires its own architectural
   decision before any block could exist.
6. Chat lifecycle migration — deferred pending future Chat work.
7. Ranking / recommendation / fuzzy matching — excluded, not absorbed.

### 5.4 Potentially coupled concerns

```text
legacy acquisition  <->  CLI discovery surfaces  <->  discovery port adapter
                     <->  existing manifests / artifact_selection / resolver

run vs execute      <->  ModelExecutionService    <->  admission ownership
                     <->  observable CLI contract  <->  api.py execute path

multi-revision      <->  ModelStore identity      <->  manifest schema/migration
                     <->  importer / evaluator     <->  B9.90 canonical locator

Model Library/GUI   <->  discovery port           <->  model metadata/variants
                     <->  catalog/query boundary  <->  new surface(s)
```

Coupling is recorded as fact only. It is **not** converted into a plan or a
sequence here.

---

## 6. Decision space

Options are listed in the order in which their concerns appear in the
repository. **They are not ranked, weighted or scored.** Every option is a
`POSSIBLE OPTION` unless explicitly labeled otherwise.

### O-01 — `run`/`execute` convergence

- **Evidence**: run-boundary ADR Q4 (REMAIN SEPARATE); register 28.9, 30.9, 32.4.
- **Boundary affected**: CLI execution surface; `run_service`; `execute_model`;
  admission ownership.
- **Dependencies**: B9.89 run boundary; B9.19 execute spec; admission contract.
- **New invariants required**: (to be defined by the decision) which boundary is
  authoritative; whether admission stays surface-owned.
- **Potentially affected components**: `main.py`, `run_service.py`,
  `execute_model.py`, `application_wiring.py`, `api.py`.
- **Explicit non-goals unless ratified**: no behavior change to the observable
  CLI contract without an explicit decision.
- **Consequences**: would reopen a ratified decision (Q4) and require a new ADR.
- **Unknowns**: desirability; surface ownership; api.py scope; compatibility.

### O-02 — `ModelExecutionService` retirement or adoption

- **Evidence**: `execution_service.py:42`; register 14.3, 14.7, 30.9, 31 Q5.
- **Boundary affected**: execution boundary ownership; architecture-debt register.
- **Dependencies**: B9.19 use case; B9.78 cutover; legacy-only tests.
- **New invariants required**: (to be defined) treatment of legacy-only tests.
- **Potentially affected components**: `execution_service.py`, its two test
  modules, execution composition root.
- **Explicit non-goals unless ratified**: no deletion of legacy-only tests.
- **Consequences**: either settles or reaffirms a recorded debt.
- **Unknowns**: permanent-vs-transitional classification; migration path.

### O-03 — Legacy acquisition convergence

- **Evidence**: `main.py:1156`, `main.py:1522-1538`; register 18.3, 19.3, 21.6,
  B9.85 D5.
- **Boundary affected**: discovery port and its legacy adapter; CLI discovery
  surfaces.
- **Dependencies**: B9.80 port; B9.85 wiring; `resolver.py`;
  `artifact_selection.py`; legacy tests.
- **New invariants required**: (to be defined) meaning of deprecation; the single
  production discovery boundary.
- **Potentially affected components**: `main.py`, `sources/huggingface.py`,
  `resolver.py`, `artifact_selection.py`, related tests.
- **Explicit non-goals unless ratified**: no removal, no behavior change.
- **Consequences**: would remove the longest-standing dual-boundary coexistence.
- **Unknowns**: consumer inventory; manifest implications; adapter permanence.

### O-04 — ModelStore / multi-revision coexistence

- **Evidence**: `models.py:82-93`; `model_store.py:281-282,309-318,512-533`;
  register 19.7.3 (and Option A recorded NOT SELECTED at 3126-3130).
- **Boundary affected**: storage identity; manifest schema; migration.
- **Dependencies**: OD-1; B9.83; B9.90; importer/evaluator consumers.
- **New invariants required**: (to be defined) revision-aware identity and its
  migration guarantee.
- **Potentially affected components**: `model_store.py`, `models.py`, manifest
  migration, importer, evaluator, catalog APIs.
- **Explicit non-goals unless ratified**: no identity change; no storage
  migration.
- **Consequences**: would reopen OD-1 and every closed identity contract.
- **Unknowns**: real demand; migration cost; content-identity interaction.

### O-05 — Authorize a presentation surface (Model Library / GUI)

- **Evidence**: Product Vision ADR §8, §10, §15; register 5014-5024.
- **Boundary affected**: new surface(s); discovery port consumption.
- **Dependencies**: superseding product decision; catalog/query invariant.
- **New invariants required**: (to be defined) surfaces consume application/core
  capabilities and never duplicate domain logic.
- **Potentially affected components**: new surface(s); possibly discovery and
  metadata representation.
- **Explicit non-goals unless ratified**: no GUI; no browser; no ranking;
  no new search API.
- **Consequences**: would require authorizing what two ADRs currently withhold.
- **Unknowns**: one concern or two; ranking ownership; ADR supersession.

### O-06 — Chat lifecycle migration

- **Evidence**: Product Vision ADR §9; register 6160-6162, 6777-6779.
- **Boundary affected**: HTTP transport; chat application boundary.
- **Dependencies**: B9.88 boundary (CLOSED); `api.py`; session registry.
- **New invariants required**: (to be defined) target application-level seam.
- **Potentially affected components**: `api.py`, `run_service.py`, session
  lifecycle code.
- **Explicit non-goals unless ratified**: no Conversation abstraction invented
  without an ADR.
- **Consequences**: ADR-first sequence would be implied.
- **Unknowns**: ADR prerequisite; target seam; session identity preservation.

### O-07 — Recorded CI follow-up (flaky chat-session test)

- **Evidence**: register 24.5 (`E — FLAKY/NON-DETERMINISTIC`, NON-BLOCKING).
- **Boundary affected**: none architectural.
- **Dependencies**: chat session registry behavior under concurrency.
- **New invariants required**: none architectural.
- **Potentially affected components**: `tests/test_chat_sessions.py` only.
- **Explicit non-goals unless ratified**: no test modification.
- **Consequences**: maintenance-level only, on the recorded evidence.
- **Unknowns**: whether it warrants a block at all.

### O-08 — Defer allocation; allocate no new block

- **Evidence**: the register has designated no successor; B9.90's allocation
  explicitly "opens no identifier ... and reserves none of them" (register at
  8208-8209); §6 fixes numbering only when an allocation procedure runs.
- **Boundary affected**: none.
- **Dependencies**: none.
- **New invariants required**: none.
- **Potentially affected components**: none.
- **Explicit non-goals**: none.
- **Consequences**: the roadmap remains at its current closed state.
- **Unknowns**: none.

### O-09 — Any other architectural concern

```text
NEW PROPOSAL — NOT CURRENT PROJECT INTENT
```

Any concern not recorded in sections 4.A-4.G would require the project owner to
introduce it explicitly. This document does not invent such a concern.

---

## 7. Decision criteria (neutral, unweighted)

The project owner may consider, without any weighting applied by this document:

1. Architectural coherence — does the direction resolve a real boundary tension or
   add a new one?
2. Boundary ownership — does it clarify which component owns a decision?
3. Compatibility — does it preserve closed contracts and observable behavior?
4. Migration cost — what existing artifacts, manifests, surfaces or documents are
   affected?
5. Scope containment — can it be delivered as one coherent change?
6. Testability — can it be verified by observable contracts?
7. Operational risk — what can regress for existing users?
8. Relationship to existing closed contracts — does it reopen a ratified
   decision, and is that intended?
9. Dependency count — how many other boundaries must move with it?
10. Whether a new ADR is required before allocation.
11. Whether the concern is architectural at all, or maintenance.

No score, weight or ordering is assigned to any criterion, and no criterion is
used here to select an option.

---

## 8. HUMAN DECISION REQUIRED

```text
Decision:
[TO BE RATIFIED BY PROJECT OWNER]

Chosen architectural direction:
[TO BE RATIFIED]

Reason:
[TO BE PROVIDED BY PROJECT OWNER]

Scope authorized:
[TO BE DEFINED]

Scope explicitly not authorized:
[TO BE DEFINED]

Required invariants:
[TO BE RATIFIED]

Required dependencies:
[TO BE CONFIRMED]
```

Additional fields the project owner may wish to complete:

```text
Whether a new ADR is required before allocation:  [TO BE DEFINED]
Whether an existing ratified decision is reopened: [TO BE DEFINED]
Numbering/corpus inspection required before allocation (register 6, 7, 11):
                                                        [TO BE CONFIRMED]
```

---

## 9. Relationship to B9.91

```text
This decision record does not allocate B9.91.
```

`B9.91` remains **NOT ALLOCATED** until a subsequent formal allocation procedure
records a ratified scope and satisfies the roadmap numbering/allocation policy
(register sections 6, 7 and 11).

Additional statements:

- No B9.91 allocation entry is created by this document.
- The B9.90 CLOSED record (register section 33) is not altered by this document.
- No identifier is opened, reserved or implied by this document.
- Under register section 6 the next main-block integer would be the successor of
  the highest verified main block; that arithmetic is a mechanical step that
  follows a ratified decision and does not constitute one.

---

## 10. Evidence index

All statements in this document were read from the repository at the anchor
below. No claim is sourced from outside it.

```text
Anchor commit:   1fe09421924b64b5eb91a8ae2bd70be7f3465856
                  ("docs: close roadmap block B9.90")
branch:          main
origin/main:     1fe09421924b64b5eb91a8ae2bd70be7f3465856

Roadmap register: docs/roadmap-register-and-numbering-policy.md
  sections 6, 7, 9, 11, 14.3, 14.7, 18.3, 19.3, 19.7.3, 20, 21.6, 24.5, 25.x,
  28.9, 29.7, 30.9, 31 (31.4), 32.4, 33 (33.4, 33.7, 33.11)

ADRs:
  docs/product-vision-adr.md            (D6, D8, D9, §8, §9, §10, §15)
  docs/run-boundary-architectural-decision.md  (Q1-Q5, HUMAN-RATIFIED)
  docs/B9.19-execute-application-use-case-specification.md
  docs/b9.87-cli-catalog-query-caller-decision.md
  docs/b9.88-chat-application-boundary-cli-caller-decision.md

Source inspected:
  castlearq/main.py, castlearq/application_wiring.py,
  castlearq/acquisition_service.py, castlearq/acquisition_mapping.py,
  castlearq/discovery_selection.py, castlearq/discovery.py,
  castlearq/sources/huggingface_discovery.py, castlearq/sources/huggingface.py,
  castlearq/downloads/planner.py, castlearq/downloads/downloader.py,
  castlearq/model_store.py, castlearq/models.py,
  castlearq/execute_model.py, castlearq/execution_service.py,
  castlearq/catalog_query_service.py

Tests observed (read-only):
  tests/test_chat_sessions.py:1325 (recorded CI follow-up)
  tests/test_execution_service.py, tests/test_execution_integration.py
  tests/test_b990_canonical_acquisition_locator.py (B9.90 end-to-end)
```

---

## 11. Status of this document

```text
PREPARATION / HUMAN RATIFICATION PENDING
Decision = PENDING HUMAN RATIFICATION
No option selected.
No ranking, scoring or recommendation expressed.
No implementation authorized.
No block allocated.
No commit created by this preparation step.
```
