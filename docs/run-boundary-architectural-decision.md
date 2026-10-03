# Run Boundary Architectural Decision

> **Nature of this document: Human Architectural Decision Record (HADR).**
>
> **Documentation only.** This record formalizes an architectural decision taken
> by the project owner. It does not modify production source code, tests, the
> roadmap register, any Number Allocation Record, or any existing ADR. It
> allocates no roadmap identifier and authorizes no implementation.

---

## 1. Status

```text
STATUS:  HUMAN-RATIFIED
NUMBER:  NONE — NOT ALLOCATED
IMPLEMENTATION: NOT AUTHORIZED BY THIS DOCUMENT
```

Allocation metadata, recorded at allocation time and not part of the decision
itself:

```text
DECISION REFERENCE FOR:  B9.89 — CLI Run Through Application Boundary
NAR:                     docs/roadmap-register-and-numbering-policy.md section 31
```

This is a **decision record**, not an allocation record. It is deliberately
numbered: no `B9.x` identifier is claimed, reserved or implied here. See
section 14.

---

## 2. Baseline

Verified at the time this decision was recorded:

```text
Branch:        main
HEAD:          fe9cd03d19962059e76520d06d3b6acb30f0d139
origin/main:   fe9cd03d19962059e76520d06d3b6acb30f0d139
Ahead/behind:  0  0
Working tree:  clean
```

`fe9cd03` is the commit that closed B9.88. At this baseline, B9.80 through B9.88
are all CLOSED and B9.89 is NOT ALLOCATED.

---

## 3. Decision Question

> Should `run_once` become the authoritative application boundary for the CLI
> one-shot `run` surface?

Answered in section 6.

---

## 4. Context

### 4.1 What the CLI `run` surface does today

```text
CLI  (castlearq/main.py :: run_model)
 ↓
ModelArtifactResolver(store).resolve(...)          main.py:1757
 ↓
detect_llama_capability()                         main.py:1767
 ↓
evaluate_model_compatibility(...)                  main.py:1727   (_admit_for_preparation)
 ↓
to_admission(result)                              main.py:1741
 ↓
prepare(..., admission=admission)                 run_service.py:218
 ↓
LlamaCppRunner(capability).run(...)               main.py:1792
 ↓
presentation: stdout, warnings, exit code         main.py:1795-1815
```

Only `prepare` is an application-level stage. Resolution, capability detection,
evaluation, admission minting, runner construction and invocation are all owned
by the CLI.

### 4.2 What `run_once` already provides

```text
run_once  (castlearq/run_service.py:286)
 ↓
ModelArtifactResolver(store, models=models).resolve(...)
 ↓
prepare(..., admission=admission)
 ↓
deps.runner or LlamaCppRunner(capability)
 ↓
RunOutcome(model_id, output, exit_code, warnings)
```

`run_once` is fully implemented, injectable through `RunDependencies`, never
prints, raises typed `RunServiceError` subclasses, and **has zero production
callers**. Its only behavioural consumers are tests.

### 4.3 The architectural problem

The CLI duplicates application orchestration that already exists, and the
existing application boundary for one-shot execution is unreachable from any
user-facing surface.

---

## 5. Evidence

Facts below are verified from the repository. Interpretation and decision are
marked separately.

### 5.1 Facts

```text
F1  run_once has no production caller. All references are its own definition,
    its __all__ entry, prose in execute_model.py:63, api.py:1576 and
    application_wiring.py:259 (which calls it "legacy"), and test files.

F2  CLI run (main.py:1756-1794) performs resolver -> capability ->
    admit -> prepare -> runner inline.

F3  Both paths call the SAME prepare() (run_service.py:218). The admission
    gate inside it (_require_admission, run_service.py:188) is identical.

F4  Admission is minted ONLY at the surface, by
    evaluate_model_compatibility -> to_admission (main.py:1727-1741).
    run_once never evaluates and never mints; it forwards a supplied
    admission unchanged and denies None (fails closed).

F5  run_once already returns selection warnings through
    RunOutcome.warnings (run_service.py:350-365), aggregating
    preparation.compatibility_warnings, preparation.selection_warnings and
    result.warnings. No warning-transport defect of the kind B9.88 had to
    repair for chat therefore exists here.

F6  Two observable differences exist on failure paths if the CLI adopts
    run_once:
      (a) exception mapping — run_once branches on the message prefix
          "Model not found in the local catalog:" (run_service.py:321),
          while the CLI currently prints ModelArtifactResolutionError text
          directly (main.py:1763-1765);
      (b) warning delivery on preparation failure — PreparationError.warnings
          is a DEDUPLICATED MERGE (run_service.py:106-112), whereas the CLI
          currently prints _prepare_warnings() = compatibility_warnings +
          selection_warnings without that merge (main.py:1693-1698).

F7  run_once has no model-fidelity defect: the CLI builds
    ModelArtifactResolver(store) while run_once passes models=models, but
    resolver.py:80 defaults models to get_catalog(). Equivalent.

F8  Both defaults for execution timeout are 600.0
    (main.py:161 and run_service.py:283). Equivalent.

F9  Neither run_once nor run invokes execute_model; the two are independent.
    AST call-graph analysis of main.py and api.py confirms run_once is never
    called from production code.

F10 execute_model re-resolves internally with the explicit comment
    "a previous evaluation is never an execution authority"
    (execute_model.py:290-291). It is a distinct use case with its own
    dependency record and exception family.

F11 ModelExecutionService (execution_service.py:42) is imported nowhere, has no
    composition root, and is referenced only by its own definition and one
    docstring (acquisition_service.py:34). It duplicates a capability that
    execute_model already provides.

F12 This question has been deferred twice by earlier records: B9.87 HADR 5.2
    and B9.88 HADR section 10, each on the grounds that it is a human
    architectural decision rather than an implementation detail.
```

### 5.2 Architectural interpretation

The preceding READ-ONLY audit interpreted F1-F12 as follows. These are readings,
not measurements.

```text
I1  The CLI duplication of orchestration is the same smell B9.88 resolved for
    chat, but materially less risky: chat required an owner ruling and an
    application-contract change (Amendment A) because a live streaming
    callback and a warning-transport gap both had to be crossed. run_once
    already transports warnings (F5) and needs no streaming seam.

I2  Because both paths share prepare() (F3), the admission POLICY is already
    identical. The unresolved question was never the gate; it is whether the
    CLI should stop OWNING admission minting.

I3  D10 favours a single shared application capability per use case, and D11
    treats an allocated core capability without a real caller as sequencing
    debt. run_once is exactly that shape.

I4  No execution capability is missing. This is a boundary-ownership defect,
    not a capability gap.
```

---

## 6. Human Decision

```text
DECISION: ADOPT
```

**Q1 — Application boundary: ADOPT.**

> `run_once` becomes the authoritative application boundary for the CLI
> one-shot `run` surface. The CLI delegates execution orchestration to it.

Rationale:

- The boundary already exists, is complete, is injectable, is tested, and is
  unreachable from any user-facing surface (F1).
- The CLI currently re-implements exactly that orchestration (F2), so adoption
  removes duplication rather than moving or inventing anything.
- It gives an allocated core capability the production caller that D11 treats
  as sequencing debt, and it aligns `run` with the ownership pattern B9.88
  established for `chat` (I1, I3).
- It creates no new user-facing surface and no product capability.

Architectural consequence: the CLI retains argument validation, dependency
acquisition, evaluation and admission, and presentation; it loses resolution,
preparation and runtime invocation.

---

## 7. Admission Policy

```text
Q2 DECISION: Admission continues to originate at the surface for `run`.
```

Ratified explicitly:

```text
CLI run
 ↓
evaluate_model_compatibility(...)
 ↓
to_admission(result)
 ↓
run_once(..., admission=admission)
```

```text
Application boundary  !=  Admission authority
```

The distinction is preserved deliberately. Consuming an application boundary
does not move admission into it. `run_once` continues to validate the supplied
admission and to fail closed when none is supplied (F4); it gains no power to
evaluate compatibility, mint an admission, or weaken the gate.

Rationale:

- B9.88 already ratified surface-owned evaluation and admission for `chat` in
  its section 8 ("Admission rule"). Adopting `run_once` for `run` applies the
  same already-ratified shape rather than inventing a new policy.
- The admitting decision is made by the strict evaluator while the warning text
  is produced by the legacy `assess_model` verdict inside `prepare`. Keeping
  evaluation at the surface preserves one evaluation per invocation and leaves
  that split exactly where it is today (F3, I2).
- No authorization for application-level evaluation or admission minting is
  granted by this document.

---

## 8. Observable Contract

```text
Q3 DECISION: PRESERVE
```

Adoption **must preserve** the existing observable CLI `run` contract. The two
differences identified as F6 are contractual obligations, not accepted
side-effects.

Specifically, implementation must preserve:

```text
- exit code 2 for missing/blank model-id or prompt (usage)
- exit code 1 for resolution, admission, preparation and execution failure
- exit code 0 on success
- the user-visible "Run error: ..." message text and its prefixes
- successful-path stdout content and successful-path warnings
- warning text and warning destination (stderr, "Warning: {warning}")
```

Where the boundary's typed errors or its deduplicated warning merge would
otherwise alter user-visible text, implementation must adapt either the CLI
adapter or the boundary's error/warning projection so that the observable
contract is preserved.

This does **not** mean `run_once` must be rewritten. It means the observable
contract is the specification, and the two representations must be reconciled
deliberately rather than silently.

Rationale: B9.88 established the same standard — the warning-preservation
correction was made because a pre-existing user-visible line had been lost
(Amendment A). Applying a lower standard here would repeat the exact regression
that required a human ruling last time.

---

## 9. Run vs Execute

```text
Q4 DECISION: `run` and `execute` REMAIN SEPARATE application capabilities.
             Convergence is OUT OF SCOPE and is deferred again.
```

Rationale:

- They are different use cases with different contracts and different exception
  families (F10). `execute_model` is the B9.24 use case with its own dependency
  record; `run` is the legacy one-shot surface.
- Neither invokes the other (F9). Adopting `run_once` requires no change to
  `execute_model` and creates no coupling to it.
- `run` can be made authoritative independently of `execute`.

Recorded for the avoidance of doubt: this decision does not retire `run`, does
not migrate it onto `execute`, and does not authorize any convergence work. A
future decision on convergence would be a separate architectural record.

---

## 10. ModelExecutionService

```text
Q5 DECISION: DOES NOT PARTICIPATE.
```

`ModelExecutionService` is excluded from this decision on the evidence in F11:
it has no production caller, no composition root, no corresponding CLI `run`
interface, and duplicates a capability `execute_model` already provides
authoritatively. Folding it in would import an unused abstraction into a live
path and broaden the scope without serving convergence.

Its classification as unrelated architecture debt is confirmed and carried
forward unchanged. It is **not** deleted, **not** modified and **not** adopted by
this document; its disposition remains a separate matter.

---

## 11. Architectural Consequences

### Positive

- Removes the duplicated resolution/preparation/runtime-invocation orchestration
  from the CLI (F2).
- Gives the existing one-shot application boundary its first production caller,
  closing the same caller-less shape that D11 treats as sequencing debt (I3).
- Aligns `run` with the ownership pattern established by B9.88 for `chat` (I1).
- Restores the separation between presentation and execution orchestration that
  `run_once` was written to provide ("Never prints, never touches the CLI").
- Requires no new application contract: warnings already cross the boundary (F5)
  and no streaming seam is involved.

### Negative / trade-offs

- Real adapter work is required to satisfy Q3: the error-mapping and
  warning-merge differences in F6 must be reconciled deliberately.
- Admission remains surface-owned, so the CLI keeps evaluation and admission
  responsibility; this is a deliberate trade of purity for preserved policy.
- The CLI and `run_once` will each hold a reference to the preparation step,
  and divergence can re-emerge without a structural guarantee.
- `run` and `execute` remain separate, so two one-shot contracts persist.

### Explicit non-consequences

This decision does **not** authorize:

```text
Model Library UX or any browsing experience
GUI
any new user-facing surface
a new runtime, Ollama integration, or multi-GPU
any Chat change or redesign
fine-tuning, LoRA, QLoRA, datasets or checkpoints
conversation abstraction, persistence or chat history
ModelExecutionService adoption, deletion or modification
run/execute convergence
any change to execute_model, evaluation, admission or compatibility policy
any new dependency
unrelated refactoring
```

---

## 12. Explicit Non-Goals

Beyond the non-consequences above, the following are outside this decision
because they are already governed elsewhere and must not be reopened here:

- **Model Library UX** remains NOT ALLOCATED (Product Vision D6).
- **GUI** remains NOT AUTHORIZED (D8).
- **Fine-tuning** still requires a separate ADR (D9).
- **Additional runtime implementations** remain future work and must not be
  represented as current capability (D5).
- **Conversation abstraction** must not be invented or reconstructed
  (D7); none exists in the repository.

---

## 13. Implementation Boundary

The approved architectural intent, expressed without prescribing implementation:

```text
CLI run
 ├─ argument validation and usage errors
 ├─ ModelStore / runtime capability acquisition
 ├─ compatibility evaluation + admission minting (surface-owned)
 ├─ call run_once(..., admission=admission)
 └─ presentation of RunOutcome and typed errors (Q3: PRESERVE)

run_once (authoritative)
 ├─ resolution
 ├─ preparation (admission gate + preflight + selection)
 ├─ runtime invocation
 └─ structured RunOutcome / typed errors
```

Invariants any future implementation must uphold:

```text
- exactly one evaluation per invocation
- exactly one admission, forwarded unchanged
- exactly one preparation, inside the boundary only
- no new application contract, no new streaming seam
- observable CLI contract preserved (section 8)
- ModelExecutionService untouched
- execute_model untouched
```

---

## 14. Roadmap Relationship

```text
This decision does not allocate a roadmap block.

It assigns no number, creates no B9.89, and does not modify
docs/roadmap-register-and-numbering-policy.md.

Any implementation must be separately allocated through the repository's
roadmap procedure, preceded by a controlled corpus inspection and a formal
Number Allocation Record.

This document confers no implementation authorization.
```

---

## 15. Decision Summary

| Question | Decision |
|---|---|
| Q1 — application boundary | **ADOPT** `run_once` as authoritative for CLI one-shot `run` |
| Q2 — admission ownership | **Surface-owned**; `run_once` validates and fails closed, never mints |
| Q3 — observable contract | **PRESERVE** the existing CLI `run` contract; adapt representations, do not accept drift |
| Q4 — `run` vs `execute` | **Remain separate**; convergence out of scope |
| Q5 — `ModelExecutionService` | **DOES NOT PARTICIPATE**; carried forward as unrelated debt |

```text
STATUS: HUMAN-RATIFIED
NUMBER: NONE — NOT ALLOCATED
IMPLEMENTATION: NOT AUTHORIZED
```

This record supersedes the deferrals recorded in B9.87 HADR section 5.2 and
B9.88 HADR section 10 for this question only. Those sections are not rewritten;
this record states the ruling they were waiting for.

---

## 16. AMENDMENT A — human decisions on the B9.89 observable contract

> **Status: HUMAN-RATIFIED ARCHITECTURAL DECISION.** This section was added after
> the B9.89 implementation and its formal verification audit, which returned
> **VERIFICATION BLOCKED**. It records human decisions on two points that
> section 8 left to be "reconciled deliberately rather than silently"
> (section 8, finding F6 and the Negative/trade-offs entry). It **amends** the
> section 8 interpretation of what "preserve the observable contract" requires
> for B9.89. Sections 1-15 above are otherwise unchanged and are not rewritten.
>
> The historical sequence is preserved and must not be collapsed:
>
> ```text
> allocation (9fdd60da6d4b4b308f7c9a09b518b3da3d7d2344)
>   -> implementation (5ee4bb5b20560ec11f7c05e2ad93a49967410068)
>     -> verification (BLOCKED)
>       -> verification finding (this section, 16.1)
>         -> human decision (this section, 16.2 and 16.3)
>           -> corrective implementation (NOT YET AUTHORIZED OR PERFORMED)
>             -> re-verification (PENDING)
>               -> closure (NOT CLOSED)
> ```
>
> This amendment does **not** retroactively claim that commit
> `5ee4bb5b20560ec11f7c05e2ad93a49967410068` satisfied the amended contract. It
> did not; it is non-conforming on 16.2 and is pending a corrective
> implementation.

### 16.1 What the verification audit found

The B9.89 implementation commit routed the CLI `run` command through
`run_service.run_once()` as allocated. The formal verification audit confirmed
C1-C4, C7-C10 and scope integrity, and returned **VERIFICATION BLOCKED** on two
observable-contract points:

```text
(a) LOST RUNTIME STDERR — the pre-B9.89 CLI printed result.stderr to the CLI's
    stderr stream on both the success and the failure path. RunOutcome carries
    only (model_id, output, exit_code, warnings); it has no stderr field, and
    run_service never reads result.stderr. Runtime diagnostics are therefore
    silently discarded.

(b) WARNING MULTIPLICITY — the pre-B9.89 failure path concatenated
    _error_warnings(error) + _prepare_warnings(error) and could print the same
    warning line more than once. The boundary exposes a deduplicated merge.
```

Finding (a) is a genuine loss of a pre-existing user-visible line. This is the
exact regression class the section 8 rationale attributes to B9.88, and the
test suite did not catch it because the pre-existing success-path test asserted
only the exit code.

Both points are governed by section 8, which made the observable contract the
specification and required that the CLI adapter and the boundary projection be
"reconciled deliberately rather than silently". The implementation reconciled
(b) by assumption. This amendment now supplies the human ruling for both.

### 16.2 Decision A — PRESERVE RUNTIME STDERR

The owner ruled:

> **RUNTIME STDERR IS PRESERVED.** The pre-B9.89 CLI emitted the runtime's
> `result.stderr` to the CLI's stderr stream on both the successful and the
> failing path. That is part of the B9.89 observable CLI contract. Runtime
> diagnostics must remain user-visible on CLI stderr and must not be silently
> discarded by the application boundary's result projection.

Consequences:

- The application boundary must transport runtime stderr to its caller. This may
  require an additive, defaulted stderr field on `RunOutcome`; this amendment
  deliberately does not prescribe the exact mechanism, only the contract.
- The CLI adapter must print it on stderr with the pre-B9.89 newline
  normalization, on both the success and the failure path.
- Any such change is an **additive** extension to the application boundary and
  must not alter the boundary's "never prints, never touches the CLI" property.

Implementation is **not authorized by this section**. It requires a separate
corrective implementation task.

### 16.3 Decision B — RATIFY WARNING DEDUPLICATION

The owner ruled:

> **WARNING DEDUPLICATION IS RATIFIED.** The intended B9.89 contract preserves
> the complete distinct warning set, the warning text, the `Warning: `
> presentation, the stderr destination and first-occurrence ordering. Duplicate
> occurrences of the same warning are **not** independently meaningful
> user-visible events and must not be intentionally reproduced.

Consequences:

- The section 8 warning-preservation requirement is satisfied for B9.89 by the
  deduplicated projection. The F6(b) multiplicity difference is **resolved by
  decision, not by oversight**, and is no longer an open verification item.
- This ratifies the warning behavior already present in commit
  `5ee4bb5b20560ec11f7c05e2ad93a49967410068`. It does not ratify 16.2.
- No warning implementation change is required or authorized by this section.

### 16.4 Amended B9.89 observable contract

| Surface                     | Decision                          |
| --------------------------- | --------------------------------- |
| stdout                      | Preserve existing successful output |
| runtime stderr              | **PRESERVE** (16.2)               |
| warnings                    | **DEDUPLICATE** (16.3)            |
| warning text                | Preserve                          |
| warning ordering            | Preserve first occurrence         |
| warning destination         | stderr                            |
| `Run error:` presentation   | Preserve                          |
| success exit code           | 0                                 |
| runtime/preparation failure | 1                                 |
| usage error                 | 2                                 |
| admission ownership         | CLI (section 5, Q2)               |
| admission identity          | Preserve — exact object forwarded |
| compatibility evaluation    | Exactly once                      |
| run/execute convergence     | Out of scope (section 9)          |
| `ModelExecutionService`     | Does not participate (Q5)         |

### 16.5 Standing of this amendment

```text
AMENDMENT A:  HUMAN-RATIFIED ARCHITECTURAL DECISION
              (recorded in this document, section 16)

B9.89 STATE:  ALLOCATED
              IMPLEMENTED
              NOT VERIFIED   (verification returned BLOCKED)
              NOT CLOSED

16.3 warnings:   RESOLVED by decision — no corrective change required
16.2 stderr:     OUTSTANDING  — corrective implementation required
                 NOT YET AUTHORIZED, NOT IMPLEMENTED
```

Sections 1-15 of this record remain in force. Only the section 8 interpretation
of observable-contract preservation is amended, and only as stated above.

---

## 17. B9.89 — Closure Record

```text
STATUS:        CLOSED
IMPLEMENTATION: COMPLETE
VERIFICATION:   COMPLETE
CLOSURE:        COMPLETE
PUBLICATION:    NOT PERFORMED (local only; not pushed at closure time)
```

Sections 1-16 above, including Amendment A, are preserved verbatim and are not
rewritten by this closure. This section records that the ratified scope was
realized exactly as decided.

### 17.1 Closure precondition chain

Closure occurred only after, and in this order:

```text
1. allocation                  9fdd60da6d4b4b308f7c9a09b518b3da3d7d2344
2. implementation              5ee4bb5b20560ec11f7c05e2ad93a49967410068
3. corrective implementation   b266c887fd30a26d0bf1ee0a775ea69b52b6e486
   (authorized by the human Amendment A recorded at b356488)
4. formal verification         PASSED (corrective re-verification)
5. formal closure eligibility  PASSED
   -> this closure
```

No decision in sections 1-15 was reopened, reinterpreted or amended by this
closure.

### 17.2 Corrective history

The first formal verification of commit 5ee4bb5 **failed** and returned BLOCKED,
finding that runtime stderr was not transported through `run_once` and that
warning multiplicity differed because the boundary deduplicates. The human owner
recorded Amendment A (section 16, commit b356488) deciding runtime stderr
PRESERVED and warning deduplication RATIFIED. The corrective implementation at
b266c88 restored the stderr transport and retained the ratified deduplication.

Commit 5ee4bb5 did not satisfy the amended observable contract and was never
recorded as having done so; it remained non-conforming until b266c88.

### 17.3 Final result

```text
CLI run            -> routed through run_once
Admission          -> surface-owned; exact object forwarded; one evaluation
CLI orchestration  -> resolution/preparation/runtime removed from the CLI
Runtime stderr     -> transported and preserved (success and failure)
Success ordering   -> stdout -> runtime stderr -> warnings
Failure ordering   -> runtime stderr -> Run error -> warnings
Warnings           -> deduplicated (ratified by Amendment A)
Exit codes         -> 0 success / 1 failure / 2 usage
run vs execute     -> separate; convergence deferred (Q4)
ModelExecutionService -> does not participate (Q5)
```

### 17.4 Verification evidence

```text
Formal corrective re-verification: PASSED

Focused:  71 passed, 23 subtests passed
Full:     2151 passed, 2706 subtests passed
          0 failed, 0 skipped, exit 0
git diff --check: PASS

Final verified HEAD before closure:
  b266c887fd30a26d0bf1ee0a775ea69b52b6e486

Closure commit: the commit that contains this section 17.
```

The closure commit hash is not written here because a commit cannot contain its
own hash; this record is committed in that commit. The implementation,
amendment and corrective commits are immutable and were not rewritten. This
closure changed documentation only.

Roadmap counterpart: `docs/roadmap-register-and-numbering-policy.md` section 32.
