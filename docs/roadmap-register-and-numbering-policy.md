# CastleArq — Roadmap Register, Numbering Policy and Allocation Record

> **Nature of this document: PROSPECTIVE FORMALIZATION, AFTER `v0.4.0`.**
>
> This document is **not** a historical block document and **carries no `B9.x`
> identifier**. It records two things that must never be confused:
>
> 1. **HISTORY** — what the repository demonstrably contains (§2, §4, §5).
> 2. **NEW POLICY** — what the project decides to apply from the activation
>    commit onward (§6, §7, §8, §9).
>
> Everything in §6–§9 is **new policy**. None of it is a reconstruction of the
> historical rule, and none of it may be cited as evidence of what the project
> previously decided.
>
> It is an **additional record**. It rewrites nothing: no historical document is
> modified, no tag moves, no release changes. That constraint follows the
> project's own established precedent — `docs/B9.59` §6 ("Historical documents
> are not rewritten; supersession is stated here instead") and
> `docs/release/v0.4.0-manifest.md` §9.

---

## 1. Why this document exists

The repository has **no canonical roadmap register**. Block identifiers are
allocated in a single documented instance, `docs/B9.59` §7, which states:

> This block is `B9.59`. The corpus was inspected before allocating it: `B9.58`
> is in real use — nine references across five `B9.57.x` documents … and no
> `B9.59`, `B9.6x` or `B10` identifier appears anywhere in the repository.
> `59` is therefore the next unused number, not an arbitrary one.

That is a **procedure**, and it is stated correctly — but it was performed
narratively, inside one block document, and no artifact of the inspection
survives it. Six identifiers came into use after that commit
(`47a9210`, `62ba823`, `e32bd4e`, `ed96da0`, `fb1f67d`, `2f9464c`), all above the
range inspected at the time. The procedure therefore cannot be re-executed, and
no number can currently be proven valid under it.

`docs/B9.59` §6 already identified the missing artifact:

> **Roadmap restructuring.** A forward-looking roadmap register is a separate
> documentation block and is not started here.

This document starts it. It does not assign any number.

---

## 2. HISTORY — evidence rules

The following facts are demonstrable from the repository at the baseline commit.

| Fact | Evidence |
|---|---|
| An identifier is **allocated** if it is in use **anywhere**, documented or not | `docs/B9.59` §7 allocated `59` precisely because `B9.58` was "in real use" with nine references **and no document of its own** |
| Block identifiers are minted in **tests and source**, not only in `docs/` | `tests/test_b966_imported_admission.py:1`, `tests/test_b9765_json_cli.py:15`, `castlearq/json_output.py:15` |
| The historical rule is **"next unused after corpus inspection"**, not "highest + 1" | `docs/B9.59` §7 — the allocation of `59` was justified by absence of the identifier, not by arithmetic |
| Superseded identifiers are **retained, never reused** | `docs/B9.57.2:3` carries a supersession note while remaining in use |
| Historical documents are **not rewritten** | `docs/B9.59` §6; `docs/release/v0.4.0-manifest.md` §9 |
| A retrospective record **without contemporaneous authorship** is acceptable | `docs/B9.29-linux-distribution-readiness.md:3` — "**Materialización retrospectiva.** … la ausencia histórica de un archivo B9.29 individual no significa que el bloque no haya ocurrido" |
| Recording verifiable facts **inside** an existing document, without altering it, is acceptable | B9.58 closure/supersession notes in `docs/B9.57.2:3`, `.3:3`, `.5:3`, `.6:3`, `.7:5,234` |

**Deliberately NOT claimed as history.** The repository contains **no** clause
stating that unused identifiers must be reused, are reserved, are free, were
formally abandoned, are errors to be corrected, or must be filled before work
continues. The historical reason for each gap is therefore **UNKNOWN / NOT
RECOVERABLE**, and §9 below says so rather than inventing a cause.

---

## 3. HISTORY — register fields

Every register entry must carry these fields. Absence is recorded as
`NOT RECOVERABLE`, never as an inference.

```text
Block ID
Name
Status
Origin
Scope
Non-goals
Dependencies
Evidence
Evidence Type
Implementation Commit
Release Association
Supersession
Current State
Documented?
Number Allocation Record
Retrospective Record
```

### 3.1 Status values

A deliberately small vocabulary. An entry may carry more than one status when
they describe different axes.

```text
IMPLEMENTED    the work exists in the tree
DOCUMENTED     a canonical block document exists under docs/
RETROSPECTIVE  the entry was recorded after the work, from evidence only
SUPERSEDED     replaced by a later block; the record is kept, not deleted
DEFERRED       explicitly deferred by a decision that is still in force
UNKNOWN        the repository does not determine it
```

`NOT RECOVERABLE` is **not a status**. It is the value of a *field* when that
field's content cannot be determined — principally `Scope` and `Non-goals`.

### 3.2 Evidence Type values

```text
## 4. HISTORY — documented blocks (register seed)

These entries exist to make the register usable. They carry **only** what the
repository already demonstrates; no scope, rationale or acceptance criterion is
invented. `Scope` and `Non-goals` are recorded in §4.1 by reference, not
reproduced as a claim about intent.

| Block ID | Name | Status | Origin / Impl. Commit | Release | Documented? | Evidence Type |
|---|---|---|---|---|---|---|
| B9.0 | Compatibility engine design | IMPLEMENTED, DOCUMENTED | `3537b65` | pre-v0.1.0 | YES | DOC |
| B9.2 | Compatibility evaluation rules | IMPLEMENTED, DOCUMENTED | `7e406ed` | pre-v0.1.0 | YES | DOC |
| B9.4 | Compatibility knowledge design | IMPLEMENTED, DOCUMENTED | `cf6bb72` | pre-v0.1.0 | YES | DOC |
| B9.6.0 | Initial knowledge specification | IMPLEMENTED, DOCUMENTED | `90c0e9b` | pre-v0.1.0 | YES | DOC |
| B9.8 | Evaluation adapter design | IMPLEMENTED, DOCUMENTED | `d508f78` | pre-v0.1.0 | YES | DOC |
| B9.9 | Evaluation pipeline design | IMPLEMENTED, DOCUMENTED | `4653fa6` | pre-v0.1.0 | YES | DOC |
| B9.10 | Decision policy specification | IMPLEMENTED, DOCUMENTED | `4653fa6` | pre-v0.1.0 | YES | DOC |
| B9.11 | Observation specification | IMPLEMENTED, DOCUMENTED | `1898ae0`, ratified `68befde` | pre-v0.1.0 | YES | DOC |
| B9.12 | Boundary adapter specification | IMPLEMENTED, DOCUMENTED | `1e254b8`, implemented `7ccf0f2` | pre-v0.1.0 | YES | DOC |
| B9.13 | Integration specification | IMPLEMENTED, DOCUMENTED | `844788e` | pre-v0.1.0 | YES | DOC |
| B9.14 | Application wiring specification | IMPLEMENTED, DOCUMENTED | `7f39c2c` | pre-v0.1.0 | YES | DOC |
| B9.15 | Evaluation composition specification | IMPLEMENTED, DOCUMENTED | `4c6ed01` | pre-v0.1.0 | YES | DOC |
| B9.19 | Execute application use case | IMPLEMENTED, DOCUMENTED | `374335c` | pre-v0.1.0 | YES | DOC |
| B9.23 | Product caller vertical slice | IMPLEMENTED, DOCUMENTED | `374335c` | pre-v0.1.0 | YES | DOC |
| B9.29 | Linux distribution readiness | IMPLEMENTED, DOCUMENTED (retrospective materialization) | `39f5f66` | pre-v0.1.0 | YES | DOC |
| B9.30 | User-level Python packaging | IMPLEMENTED, DOCUMENTED | `39f5f66` | v0.1.0 | YES | DOC |
| B9.31 | Unified llama runtime discovery | IMPLEMENTED, DOCUMENTED | `6323ec0` | v0.1.0 | YES | DOC |
| B9.35 | Release 0.1 readiness audit | IMPLEMENTED, DOCUMENTED | `6b08922` | v0.1.0 | YES | DOC |
### 4.0 Undocumented blocks (retrospective register entries)

Each row is a retrospective record under §10. None carries an invented scope,
rationale or acceptance criterion.

| Block ID | Name | Status | Origin / Impl. Commit | Release | Documented? | Evidence Type |
|---|---|---|---|---|---|---|
| B9.48 | *(no document)* | IMPLEMENTED, RETROSPECTIVE | `4f0b6898ddf1a67d10d3880996af7a1d421bf100` | pre-v0.1.0 | NO | COMMIT |
| B9.50 | *(no document)* | IMPLEMENTED, RETROSPECTIVE | `e1c34e34d33102915925e0ce63e20e0cd6e0033a` | pre-v0.1.0 | NO | COMMIT |
| B9.52 | HTTP admission contract implementation | IMPLEMENTED, RETROSPECTIVE | `ca4f5b3` | v0.1.0 | NO | COMMIT |
| B9.53 | Public surface claims | IMPLEMENTED, RETROSPECTIVE, SUPERSEDED in part | `d9d06d49fda13156ac6d38cede5c0cb9e92e7a6f`; enforced by `tests/test_public_surface.py` | pre-v0.1.0 | NO | ABSENCE + TEST |
| B9.54 | Public surface implementation | IMPLEMENTED, RETROSPECTIVE | `d9d06d49fda13156ac6d38cede5c0cb9e92e7a6f` | pre-v0.1.0 | NO | COMMIT + ABSENCE |
| B9.57.1 | Shared-preparation hermeticity remediation | IMPLEMENTED, RETROSPECTIVE | `83adc06` | v0.2.0 | NO | REF |
| B9.58 | Documentation consolidation | IMPLEMENTED, RETROSPECTIVE | first appearance `6429ec9dc3e33bf67076c02772badf5a1c0f39aa` | pre-v0.2.0 | NO | REF (9 in-document) + ABSENCE |
| B9.66 | Imported-artifact admission and memory policy | IMPLEMENTED, RETROSPECTIVE | `47a92100b9b68f42e7d7dec829a6e52c0cf20d46` | **v0.3.0** | NO | TEST + SRC |
| B9.67 | Local GGUF import and execution | IMPLEMENTED, RETROSPECTIVE | `47a92100b9b68f42e7d7dec829a6e52c0cf20d46` | **v0.3.0** | NO | TEST + SRC |
| B9.74 | Model-store selection policy and store visibility | IMPLEMENTED, RETROSPECTIVE | `62ba823c102a546ce6cac08ceefc513d6ea9196a` | **v0.4.0** | NO | TEST + SRC |
| B9.76.1 | `--json` CLI envelope contract | IMPLEMENTED, RETROSPECTIVE | `e32bd4e1307a978a5de380076818c26e8a80c554` | **v0.4.0** | NO | SRC + TEST |
| B9.76.2 | Shared CLI JSON output layer | IMPLEMENTED, RETROSPECTIVE | `e32bd4e1307a978a5de380076818c26e8a80c554` | **v0.4.0** | NO | SRC + TEST |
| B9.76.3 | JSON output for core CLI queries (initial) | IMPLEMENTED, RETROSPECTIVE | `e32bd4e1307a978a5de380076818c26e8a80c554` | **v0.4.0** | NO | TEST + SRC |
| B9.76.4 | `castlearq import --json` | IMPLEMENTED, RETROSPECTIVE | `ed96da01c6d07f4cc874b26aa70958c9b2c9e359` | **v0.4.0** | NO | TEST |
| B9.76.5 | `--json` for SHOULD-surface commands | IMPLEMENTED, RETROSPECTIVE | `fb1f67dc8ed53a6c60033c86892f270bfdd49137` | **v0.4.0** | NO | TEST + SRC |
| B9.77 | *(scope not recoverable — see §5)* | IMPLEMENTED, RETROSPECTIVE | `2f9464ce860d6576b9ab528bb82b3d26295d8c92` | **v0.4.0** | NO | TEST |
| B9.78 | Legacy Admission Cutover | DOCUMENTED, ALLOCATED (§14) | this document's §14 record | NOT YET DEFINED | YES (this document) | DOC |

### 4.0.1 Excluded from the register

Identifiers that appear **only** as cross-references to other blocks are not
registered as blocks of their own. Excluded on that basis, with the reason
recorded as §10 requires:

```text
B9.1, B9.3, B9.5, B9.7, B9.16, B9.18, B9.20, B9.21, B9.40
    Reason: REF evidence type — referenced by other blocks; whether each was a
### 4.1 `Scope` and `Non-goals` availability

| Block | Scope | Non-goals |
|---|---|---|
| Documented blocks (B9.0 … B9.59) | Stated by their document | Stated by their document |
| B9.66 | Stated at `tests/test_b966_imported_admission.py:1-8` | NOT RECOVERABLE |
| B9.74 | Stated at `tests/test_b974_store_selection.py:15-25` | NOT RECOVERABLE |
| B9.76.2 | Stated at `castlearq/json_output.py:15` and `tests/test_json_output.py:15` | NOT RECOVERABLE |
| B9.76.4 | Stated at `tests/test_b9764_import_json.py:15-25` | NOT RECOVERABLE |
| B9.48, B9.50, B9.52, B9.54, B9.57.1, B9.58 | NOT RECOVERABLE | NOT RECOVERABLE |
| B9.53 | Partial — the §17 requirement is recoverable through `docs/B9.59` §2 and `tests/test_public_surface.py` | NOT RECOVERABLE |
| **B9.77** | **NOT RECOVERABLE** (§5) | **NOT RECOVERABLE** |
| **B9.78** | Defined — see §14.1 (cutover; not a legacy cleanup) | Defined — see §14.1 (12 explicit non-goals) |

`Scope` and `Non-goals` are recorded by **reference** to the cited evidence, not
restated. Restating a scope from a single sentence of test code would convert a
citation into an assertion of intent, which §10 forbids.

---

## 5. B9.77 — the evidence boundary

B9.77 is recorded **only** as follows.

```text
Block ID:                 B9.77
Name:                     NOT RECOVERABLE
Status:                   IMPLEMENTED, RETROSPECTIVE
Origin:                   commit 2f9464ce860d6576b9ab528bb82b3d26295d8c92
Implementation Commit:    2f9464ce860d6576b9ab528bb82b3d26295d8c92
Release Association:      v0.4.0
Scope:                    NOT RECOVERABLE
Non-goals:                NOT RECOVERABLE
Rationale:                NOT RECOVERABLE
Acceptance Criteria:      NOT RECOVERABLE
Alternatives Considered:  NOT FOUND
Ratification:             NOT FOUND
Dependencies:             NOT RECOVERABLE
Supersession:             none recorded
Current State:            implemented and shipped in v0.4.0
Documented?:              NO — identifier evidence exists, but no canonical
                          block document was found
Retrospective Record:     YES
Evidence Type:            TEST-COMMENT
Number Allocation Record: NOT RECOVERABLE — no allocation record was produced at
                          the time, and none can be reconstructed
```

**Evidence, in full.** Exactly two occurrences exist in the entire repository,
both explanatory comments inside test files, both attributed by `git blame` to
`2f9464ce`:

```text
tests/test_compatibility_report.py:657
tests/test_execute_model_wiring.py:326
```

They state why two guards were added — a `glob`/`rglob` over an unresolvable
path returns an empty collection, which would make an assertion pass vacuously.
That is a **test-hygiene rationale for two assertions**. It is not a block
scope, and it does not bound what the identifier was intended to cover.

**Explicitly NOT claimed:**

## 6. NEW POLICY — main block numbering

> **PROSPECTIVE POLICY.** From the activation commit of this document, a new
> main block `B9.x` receives the integer immediately following the highest main
> `B9.x` block already assigned **and verified in the activation corpus**.

```text
next_main_block = highest_verified_main_block + 1
```

The operative word is **verified**. Consulting `docs/` is not sufficient: block
identifiers are minted in tests and source (§2), and six identifiers above the
last inspected range exist only there (§4.0). The floor is established by a
corpus inspection under §7, not by reading documents.

**This is a new policy.** The historical rule, whatever its precise semantics,
was *"next unused after corpus inspection"* (`docs/B9.59` §7). The rule below
differs from it in exactly one respect: it **fixes the floor at the highest
allocated identifier** instead of leaving "next unused" to interpretation. That
difference removes the ambiguity identified in §1.

**It does not retroactively reinterpret any historical allocation.** B9.59
remains a valid application of the rule in force at its time, and `docs/B9.59`
§7 keeps its own historical context unmodified.

**Sub-blocks are not main blocks.** Only integers of the form `B9.x` raise the
floor. See §8.

---

## 7. NEW POLICY — corpus inspection is a precondition

> **PROSPECTIVE POLICY.** A block number assignment is **INVALID / UNVERIFIED**
> unless a corpus inspection is recorded for it. The record must include, at
> minimum, the following fields.

```text
Corpus/HEAD Anchor            the commit the corpus was read at
Corpus File Count             how many versioned files were inspected
Corpus Integrity Evidence     the reproducible mechanism used to fix that
                              corpus (file list + per-file blob hash, or an
                              equivalent verifiable procedure)
Identifier Set                every B9.x and B9.x.y identifier found
Highest Verified Main Block   maximum B9.x in that set
Rule in Force                 the policy under which the number is assigned
Rule Activation Anchor        the commit that activated that policy
Candidate Numbers Considered  every number considered, including every gap
                              that was evaluated and not chosen
Selected Number               the number assigned
Validity Reason               why it is valid under the active rule, in the
                              form used by docs/B9.59 section 7
```

`Candidate Numbers Considered` is the field that closes the historical gap:
it makes visible that unused identifiers were **evaluated and declined**, not
overlooked. A record that omits it does not satisfy this policy.

This section makes the principle already expressed in `docs/B9.59` §7
reproducible. B9.59's inspection was narrative and did not survive; this one is
an artifact.

---

## 8. NEW POLICY — sub-blocks

> **PROSPECTIVE POLICY.** A sub-block `B9.X.Y` denotes a subdivision or phase
> explicitly associated with a main block `B9.X`. The existence of a sub-block
> does **not** by itself advance the next main block number.

```text
B9.80
B9.80.1
B9.80.2
B9.80.3
B9.81
```

Here `B9.80.1`, `B9.80.2` and `B9.80.3` do **not** consume `B9.81`, `B9.82` or
`B9.83`. The next main assignment is determined **exclusively** by the highest
main block assigned under the rule in force.

**This is a prospective policy, not a reconstruction.** The repository does not
state how sub-block numeration has functioned historically. Dotted numerics are
demonstrably used for phases — `B9.46.1`–`B9.46.29`, `B9.57.1`–`B9.57.8`,
`B9.76.1`–`B9.76.5` — and sub-numbers are demonstrably skipped (`B9.57.4`
appears nowhere). **Why** any particular sub-number was skipped is **UNKNOWN /
NOT RECOVERABLE**, and this policy does not attempt to explain it.

The transition from the last observed sub-block to the next main block
(`B9.76.5` in `fb1f67d`, then `B9.77` in `2f9464c`) is a **single observation**,
never stated as a rule in the corpus. It is recorded here as observation only
and is not offered as precedent.

**Not specified by this policy**, because the corpus supplies no basis: when to
subdivide; whether a closed family reserves the following number; how a skipped
sub-number may later be used; and how a sub-block is distinguished from a main
block at read time.

---
## 9. NEW POLICY — historical gaps

> **PROSPECTIVE POLICY.** Identifiers not used under the evidence currently
> available will **not be reused** for new main block assignments after this
> policy's activation.

This governs **future use only**. It makes no claim about why any gap exists.

The repository contains no clause requiring reuse, no reservation, and no
statement of intent for any gap. Accordingly:

```text
Historical reason for each gap:  UNKNOWN / NOT RECOVERABLE
Future treatment:                NOT REUSED (prospective declaration)
```

This policy is **not** a claim that gaps were abandoned, freed, reserved,
erroneous, or never contemplated. Those are all historical assertions, and none
is supported. `docs/B9.57` `.1` and `.4` are sufficient illustration of why the
distinction matters: `.1` is real completed work and `.4` appears nowhere, both
inside one otherwise contiguous family, with no surviving explanation for either
difference.

The wording is deliberately **prospective** ("will not be reused after
activation") rather than **retrospective** ("were abandoned"), because the
former is a decision the project can take and the latter is a finding it cannot.

## 10. NEW POLICY — retrospective records

A **retrospective record** is a register entry that:

```text
- is created after the original work;
- does not claim to be contemporaneous;
- records only verifiable facts;
- does not invent rationale;
- does not invent acceptance criteria;
- does not invent non-goals;
- does not attribute a scope that cannot be recovered;
- does not modify the original historical document.
```

Every entry in §4.0 is such a record, and each one carries
`Retrospective Record: YES` in its register data. Every entry in the §4 table
carries `Retrospective Record: NO`.

**Precedent, cited and not rewritten.** `docs/B9.29-linux-distribution-readiness.md:3`
already establishes the form:

> **Materialización retrospectiva.** Este documento conserva el resultado de la
> auditoría/decisión B9.29. B9 fue principalmente una secuencia de work-blocks y
> la ausencia histórica de un archivo B9.29 individual no significa que el bloque
> no haya ocurrido.

`docs/B9.29` is **not modified by this document**. It is cited only as the
conceptual precedent for recording a block whose canonical document is absent.

The second precedent is B9.58, which recorded verifiable facts **inside** six
existing `B9.57.x` documents without altering their historical content
(`docs/B9.57.5:3` — "CLOSURE NOTE (added by B9.58, historical content
unchanged) … Nothing below is altered"). B9.58 itself has no document, yet its
work is fully traceable. This register applies the same discipline to B9.58 and
to the six post-v0.2.0 identifiers.

**Blocks excluded from the register.** No entry is created for any identifier
whose inclusion would require inferring intent. The exclusion list and its
reasons are recorded in §4.0.1.

---

## 11. NEW POLICY — Number Allocation Record schema

Every future assignment must record:

```text
Assigned Number
Allocation Date
Allocation Commit
Corpus/HEAD Anchor
Corpus File Count
Corpus Integrity Evidence
Identifier Set
Highest Verified Main Block
Rule in Force
Rule Activation Anchor
Actor/Process
Candidate Numbers Considered
Selected Number
Validity Reason
```

An assignment without a complete record is:

```text
INVALID / UNVERIFIED
```

and must not be cited as an allocated identifier in a later register entry.

**Numbering Policy Activation Commit:**

```text
f77f00d6c0eee177a7b53c87584f391e460f11e3
```

The activation anchor is this document's own implementation commit. A commit
hash cannot be known before the commit exists, and writing a guessed value would
be a fabricated identifier. The placeholder is therefore left in place
**deliberately**, and this paragraph is the mechanism that resolves it:

> The anchor is established by the commit that introduces this file. It is
> recorded as `PENDING` in that commit and is fixed in **the next controlled
> commit** that sets it to that hash — the same two-step discipline this project
> already applies to publication, where `docs/release/v0.4.0-manifest.md` §1
> states that the release identity is resolved from the tag itself rather than
> written in advance.

No automated rewrite of this file after committing is performed, because doing so
would require a second commit for a single field.

**Until the anchor is set, §6–§10 are drafted but not yet in force.** A number
may be assigned only after this field names a real commit.

---

## 12. Current allocation state

```text
B9.78 = FORMALLY ALLOCATED — see section 14
```

`B9.78` was **not** a register entry when this document was written: at that
moment it was an identifier named only in the negative assertions below, and
§12 stated its status as the absence of an assignment. That is now superseded by
§14, which allocates it through the §6 and §7 procedure and records the
evidence under §11.

Two figures remain distinct from any allocation:

- the highest main block identifier in use in the corpus is `B9.77`;
- the highest **documented** block with a canonical `docs/` document is `B9.59`.

Neither is an allocation of `B9.78`; they are the floor from which §14 computes.

Any number after `B9.78` is computed by the procedure in §6 and §7 — through a
corpus inspection recorded under §11 — and never by this document.

---

## 13. What this document does not do

```text
It does not assign any B9 identifier by itself.
It does not modify docs/B9.57-*, docs/B9.58-*, docs/B9.59-*, docs/B9.29-*.
It does not modify docs/release/*, any manifest, README, tag or release.
It does not move, re-create or re-point the v0.4.0 tag.
It does not claim that any gap was abandoned, reserved, freed or erroneous.
It does not claim that any sub-block rule was the historical rule.
It does not attribute a scope to B9.77.
It does not retroactively reinterpret the allocation of B9.59.
It does not define what B9.78 will contain.
```

The single allocation this document performs is `B9.78`, recorded in §14.

---

## 14. B9.78 — Number Allocation Record

`B9.78` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection. This section is the §11 record for that assignment.

```text
Assigned Number:
  B9.78

Allocation Date:
  2026-09-30

Allocation Commit:
  e6063e5a5589cb6b952ed84f91529eb52c4f3727

Corpus/HEAD Anchor:
  61753e97f7a9ba65f939400a06aadd30ad96e236
  git tree object b44c27270afe3d5a28279cb362a5e84ecf4516ca

Corpus File Count:
  203

Corpus Integrity Evidence:
  paths SHA-256:
    80212c1ac55b3e7bea09212798ca826474e97bddb4e4e7cbfda45a05e9a379c4
  tree SHA-256:
    528880bb29ad6f27b7ca57e47203ace8ab448674906038dab987845a028c1146
  occurrence SHA-256:
    91a02e80bd171ddd23be621ce8f36af1921c5a9475eb719e5b0bb57660afd90d
  identifier-set SHA-256:
    de455bbf61b77c6c4bda9cf23da2ba359f7b661f5e3a72241c80d1ff6d05dae7

Identifier Set:
  106 distinct identifiers over 2326 occurrences in 203 versioned files:
  50 main (B9.0-B9.6, B9.7-B9.16, B9.18-B9.24, B9.29-B9.31, B9.35-B9.37,
  B9.39-B9.48, B9.50-B9.59, B9.66, B9.67, B9.74, B9.76, B9.77) and 56 sub
  (B9.6.0/.1, B9.46.1-.29, B9.57.1-.8, B9.76.1-.5).

Highest Verified Main Block:
  B9.77 — 10 occurrences; allocation-grade evidence at
  tests/test_compatibility_report.py:657 and tests/test_execute_model_wiring.py:326,
  both attributed by git blame to 2f9464ce.

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled Cline corpus inspection + formal registration

Candidate Numbers Considered:
  B9.78 — SELECTED (highest verified + 1)
  B9.25, B9.26, B9.27, B9.28, B9.32, B9.33, B9.34, B9.38, B9.49, B9.60,
  B9.61, B9.62, B9.63, B9.64, B9.65, B9.68, B9.69, B9.70, B9.71, B9.72,
  B9.73, B9.75 — rejected: historical gaps, not reusable under section 9
  B9.57.4 — rejected: sub-block, never raises the main floor (section 8)
  B9.79 — rejected: not highest + 1
  B9.80, B9.81, B9.82, B9.83 — rejected: illustrative examples in section 8,
  not allocations
  B9.80.1, B9.80.2, B9.80.3 — rejected: example sub-blocks (section 8)
  B9.76.1, B9.76.2, B9.76.3, B9.76.4, B9.76.5 — rejected: real sub-blocks;
  a sub-block does not advance the main floor (section 8)

Selected Number:
  B9.78

Validity Reason:
  B9.77 is the highest verified allocated main block in the complete 203-file
  corpus. Under the active rule, the next main block is therefore B9.78. No
  allocated main identifier above B9.77 was found: B9.78 through B9.83 occur
  only inside this document, as negative assertions or as the section 8
  illustrative example, and evidence no allocation.
```

### 14.1 Register entry for B9.78

```text
Block ID:                 B9.78
Name:                     Legacy Admission Cutover
Status:                   DOCUMENTED, ALLOCATED
Origin:                   this document, section 14
Scope:                    see 14.2
Non-goals:                see 14.3
Dependencies:             see 14.4
Current State:            IMPLEMENTATION NOT STARTED — see 14.5
Acceptance Criteria:      AC1-AC12 — see 14.6
Evidence:                 see 14.7
Human decisions pending:  see 14.8
Evidence Type:            DOC
Implementation Commit:    NOT YET DEFINED — no implementation has occurred
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 14
Retrospective Record:     NO — this is a prospective allocation, not a record
                          of past work
```

### 14.1.1 Status vocabulary note

`DEFINED` is **not** an allowed status in §3.1, so it was not invented. The
closest existing documented status is **`DOCUMENTED`** ("a canonical block
document exists under `docs/`"), which is accurate here: the definition is
recorded in this document. `ALLOCATED` is retained because it remains true —
§14 still governs the number. `IMPLEMENTED` was **not** selected, because no
implementation has occurred (§14.5).

---

### 14.2 Scope

Make strict evaluation admission the mandatory execution gate on the currently
active product paths that still depend on the legacy `assess_model` gate,
completing the migration documented by `docs/B9.42` §14 and `docs/B9.59:118-119`.

The cutover covers the active `execute_model.py`, `run_service.py`,
`selection.py` and `application_wiring.py` surfaces identified by the
historical migration contract, while preserving the existing admission,
deny-only, execution re-validation, imported-artifact and evaluation-error
contracts.

`ModelExecutionService` is **explicitly outside** the B9.78 production migration
boundary: the repository verifies no production reachability and explicitly
classifies it as legacy/test-only.

**This is a CUTOVER, not a legacy cleanup.** What changes is which gate decides
execution, not whether legacy code still exists.

---

### 14.3 Non-goals

```text
1.  Deleting `assess_model` solely because it is no longer used by active
    production paths.
2.  Deleting or rewriting legacy-only tests solely because they exercise
    `assess_model`.
3.  Migrating `ModelExecutionService`; it has no production reachability and is
    explicitly classified as legacy/test-only.
4.  Redefining the semantics of `INSUFFICIENT_EVIDENCE`.
5.  Changing the deny-only admission contract (B9.19 section 7).
6.  Changing the `blocked` behavior (B9.19 section 7).
7.  Changing the raised-evaluation/error distinction (B9.48 P0-2).
8.  Changing B9.66 imported-artifact tolerance.
9.  Changing B9.67 verified-managed-path requirements.
10. Adding new CLI commands, runtime capabilities, model catalogs,
    GUI/web functionality, Ollama integration, or multi-runtime support
    (no authorization exists; B9.47:164,168 via B9.59:122-123, and B9.59:121).
11. Merging, facading, renaming, moving, or extracting the two compatibility
    engines — B9.42 section 14 item 4.
12. Changing release/distribution packaging.
```

---

### 14.4 Dependencies

```text
1. docs/B9.19 section 7 — the admission contract this cutover implements.
2. docs/B9.42 section 14 — the migration boundary and the future cutover
   decision that B9.78 constitutes.
3. docs/B9.59:118-119 — the separate legacy admission cutover block.
4. The existing `to_admission` and strict evaluation implementation
   (castlearq/evaluate_compatibility.py, castlearq/api.py:1066,
   castlearq/main.py:1680-1682).
5. The existing deny-only and deny-by-default behavior
   (castlearq/execute_model.py:67-69, :181-199).
6. The existing B9.48 P0-2 evaluation-error contract
   (castlearq/main.py:1664-1682).
7. The existing B9.66 and B9.67 execution/admission contracts
   (castlearq/execute_model.py:159-161, :299-308).
8. The current tests covering execution, selection, admission, API and CLI
   behavior.
```

None of these is a new capability; each is an existing contract B9.78 must
preserve.

---

### 14.5 Current State

```text
IMPLEMENTATION NOT STARTED.
```

B9.78 is formally defined but not yet implemented. The legacy `assess_model`
gate remains active on the identified production paths. `main.py` and `api.py`
already supply admission signals to `execute_model`. `ModelExecutionService` is
not part of the active production path.
---

### 14.6 Acceptance Criteria

```text
AC1  Strict gate
     Strict evaluation admission is mandatory on all active B9.78 migration
     paths.

AC2  Legacy execution dependency removed
     No active production execution path depends on `assess_model` as its
     admission gate.

AC3  Deny-only preserved
     Admission remains deny-only: the admission signal cannot independently
     authorize execution outside the established strict verdict contract.

AC4  Blocked preserved
     `blocked` never authorizes execution.

AC5  Deny-by-default preserved
     INSUFFICIENT_EVIDENCE continues to deny by default. B9.78 does not
     redefine its semantics.

AC6  Execution re-validation preserved
     Execution continues to re-resolve and re-validate rather than treating a
     prior evaluation as execution authority.

AC7  Evaluation-error semantics preserved
     An evaluation that raises remains distinct from a compatibility denial,
     preserving the B9.48 P0-2 contract.

AC8  Imported artifact contracts preserved
     B9.66 and B9.67 behavior remains intact.

AC9  No unrelated public-surface change
     No unrelated CLI, API, runtime, model-catalog, GUI, or distribution
     behavior is introduced by B9.78.

AC10 Test integrity
     Existing tests covering preserved behavior remain green. Tests that encode
     intentionally removed legacy-path behavior may be migrated only where
     required by the cutover. This is NOT authorization to delete legacy tests
     automatically; test disposition remains the pending decision in 14.8.

AC11 CI
     The declared CI test matrix remains green after implementation.

AC12 Legacy service exclusion
     `ModelExecutionService` remains outside the production migration boundary.
```

---

### 14.7 Evidence

```text
Contracts
  docs/B9.19 section 7    admission contract (deny-only, deny-by-default)
  docs/B9.19 section 8    legacy vs strict CompatibilityResult boundary
  docs/B9.19 section 11   evaluation is point-in-time and goes stale
  docs/B9.42 section 8 #5 the four reject-set consumers
  docs/B9.42 section 14   the migration boundary and cutover decision
  docs/B9.59:118-119      the separate legacy admission cutover block
  docs/B9.23:163-165      ModelExecutionService classified LEGACY, not a
                         product surface

Production surfaces in scope
  castlearq/execute_model.py
  castlearq/run_service.py
  castlearq/selection.py
  castlearq/application_wiring.py

Existing strict path
  castlearq/evaluate_compatibility.py

Boundary guards
  tests/test_execute_model_wiring.py
  tests/test_evaluation_policy.py

Reachability audit (read-only, at 397231bbe25d05540037ff982e1348e7a736731b)
  ModelExecutionService:
    no production reachability
    test-only reachability
    explicitly classified LEGACY
```

---

### 14.8 Human decisions preserved as future work

B9.78 does not decide the following. Each remains open and is **not** settled by
this definition:

```text
- whether `assess_model` should eventually be deleted;
- whether legacy-only tests should eventually be removed;
- whether any legacy compatibility API should eventually be removed;
- whether future work should redefine INSUFFICIENT_EVIDENCE.
```

None of these is implied by the cutover, and none may be treated as decided
because B9.78 exists.

`NOT YET DEFINED` is used deliberately and is **not** interchangeable with
`NOT RECOVERABLE`. `NOT RECOVERABLE` means the repository can no longer supply
the information; `NOT YET DEFINED` means it has not been decided. Only a
subsequent decision can fill these fields, and nothing in this document decides
them.
