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
| B9.78 | Legacy Admission Cutover | IMPLEMENTED, DOCUMENTED, ALLOCATED (§14) | implementation `8955fc6d91745ef3685fff00c6c8a6b03ac9a28e` (§14.1 is authoritative) | NOT YET DEFINED | YES (this document) | DOC |
| B9.79 | Runtime Artifact Evidence — Pre-Admission | DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED (§15) | implementation 5f781e4674226492adeedb632097a503ef983d8d (§15.1 is authoritative) | NOT YET DEFINED | YES (this document) | DOC |

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
| **B9.79** | Defined — see §15.1 (pre-admission runtime/artifact evidence) | Defined — see §15.1 (18 explicit non-goals) |

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
B9.78 = IMPLEMENTED — see section 14 (14.1, 14.5, 14.7.2)
B9.79 = VERIFIED AND CLOSED — see section 15 (15.14, 15.16)
B9.80 = VERIFIED AND CLOSED — see section 16 (16.6, 16.7)
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

The allocations this document performs are `B9.78` (§14), `B9.79` (§15), and `B9.80` (§16).

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
Status:                   IMPLEMENTED
Origin:                   this document, section 14
Scope:                    see 14.2
Non-goals:                see 14.3
Dependencies:             see 14.4
Current State:            IMPLEMENTED — see 14.5
Acceptance Criteria:      AC1-AC12 — see 14.6
Evidence:                 see 14.7
Human decisions pending:  see 14.8
Evidence Type:            DOC
Implementation Commit:    8955fc6d91745ef3685fff00c6c8a6b03ac9a28e
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
§14 still governs the number.

**Superseded in part, `96618bf3a2334b50ff5c93ee8d20db96fbab67b1`.** The sentence
above recorded the status *at allocation time*, when no implementation existed.
That historical reasoning is preserved here deliberately. The current
authoritative status is **`IMPLEMENTED`** (§14.1, §14.5, §14.7.1), following
implementation at `8955fc6d91745ef3685fff00c6c8a6b03ac9a28e`; `DOCUMENTED` and
`ALLOCATED` remain true and are retained. The §4.0 register row is synchronized
to the same current state.

**AC11 note superseded by CI run #19.** This note originally recorded AC11 as
`PARTIAL` because no Python 3.11-3.13 execution had occurred. That is now
superseded by observed CI evidence (§14.7.2): AC11 is `PASS`. The historical
`PARTIAL` state above is retained deliberately as evidence of what was known
before run #19, not as the current state.

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
IMPLEMENTED at 8955fc6d91745ef3685fff00c6c8a6b03ac9a28e
("refactor: complete B9.78 legacy admission cutover", parent bb209d7).

Targeted verification:   148 passed.
Full local verification: 1806 passed / 2665 subtests / 0 failed / 0 errors /
                         0 skipped, on CPython 3.14.4.

AC1-AC10 and AC12 verified PASS.
AC11 was PARTIAL at this point: the declared Python 3.11-3.13 CI matrix had not
yet been executed after this implementation.

B9.78 verification: COMPLETE. AC1-AC12 all PASS. AC11 is now PASS on observed
CI evidence — ci run #19 (see 14.7.2) executed the declared Python 3.11-3.13
matrix against a descendant of 8955fc6 and all three jobs passed. This
supersedes the limitation above, which is retained as historical evidence.
```

Strict admission is now the sole execution-authority on every active path
(`execute`, `serve`, `run`, `chat`). The legacy `assess_model` verdict survives
only as selection recommendation data (`recommended_runtime`,
`recommended_backend`) and as the input to `recommend_models`; it no longer
refuses execution. `main.py` and `api.py` supply admission — `api.py` forwards
the admission its chat handler had already minted rather than recomputing it.
`ModelExecutionService` remains outside the production path.

B9.78 is post-`v0.4.0` implementation work and created no release, so the
Release Association stays `NOT YET DEFINED`.

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

#### 14.7.1 Implementation evidence

```text
Implementation anchor:
  8955fc6d91745ef3685fff00c6c8a6b03ac9a28e
  "refactor: complete B9.78 legacy admission cutover"
  parent bb209d734889e27f2b01921f27beecf423cd2403 (the formal definition)

Files changed: 11 (5 production, 6 test). Nothing else.
  production: execute_model.py, run_service.py, selection.py, main.py, api.py
  tests:      test_execute_model.py, test_shared_preparation.py,
              test_selection.py, test_execute_model_wiring.py,
              test_b967_execute_imported.py, test_main_chat.py
  untouched:  pyproject.toml, .github/, docs/, config/, LICENSE, README.md,
              castlearq/compatibility.py, castlearq/application_wiring.py,
              castlearq/execution_service.py, test_compatibility.py,
              test_b966_imported_admission.py, test_execution_service.py,
              test_execution_integration.py

Architecture decisions implemented
  D1-A  assess_model retained as the recommendation producer only; its
        INCOMPATIBLE/UNKNOWN verdict no longer refuses execution
  D2-A  optional keyword-only admission parameter on prepare(), run_once()
        and open_chat_session(); None fails closed
  D3-A  api.py forwards the admission its chat handler already minted;
        no second evaluation, no second to_admission

Verification:
  148 targeted tests passed.
  1806 full-suite tests passed / 2665 subtests / 0 failures / 0 errors /
  0 skips.

Acceptance criteria (at this point):
  AC1-AC10 PASS, AC11 PARTIAL, AC12 PASS.

Matrix limitation (superseded by 14.7.2):
  Verification was performed on CPython 3.14.4.
  The declared Python 3.11-3.13 matrix had not yet been executed after this
  implementation. No CI success and no 3.11-3.13 validation is claimed.
  SUPERSEDED by ci run #19 — see 14.7.2. Retained as historical evidence.

Scope:
  No scope creep found.

Release:
  None. B9.78 is post-v0.4.0 work; Release Association stays NOT YET DEFINED.
```

#### 14.7.2 CI matrix evidence (AC11)

The AC11 limitation recorded in 14.5 and 14.7.1 is resolved by observed CI
execution. Every value below was read from the workflow run itself — the
individual jobs and their logs — not inferred from `.github/workflows/ci.yml`
and not from the workflow summary.

```text
Workflow:      ci
Run number:    #19
Run ID:        36808472633
Conclusion:    success
Event:         push
Tested commit: 86da72cf0d143a9663d17b4a735fe430f50497eb
               ("docs: synchronize B9.78 registry state")

Matrix jobs — all actually executed, completed successfully, and were
neither skipped nor cancelled. Each ran the real full pytest suite:

  test (py3.11)  job 110197997345  success
                 platform linux -- Python 3.11.16, pytest 9.1.1
                 1806 passed
  test (py3.12)  job 110197997067  success
                 platform linux -- Python 3.12.14, pytest 9.1.1
                 1806 passed
  test (py3.13)  job 110197997255  success
                 platform linux -- Python 3.13.15, pytest 9.1.1
                 1806 passed

B9.78 relevance:
  The tested commit is a descendant of the B9.78 implementation commit
  8955fc6d91745ef3685fff00c6c8a6b03ac9a28e. Only documentation commits
  (96618bf, 86da72c) intervene, so the tested tree contains the B9.78
  production code exactly as committed.

Exclusion checks:
  Declared matrix is ['3.11', '3.12', '3.13'] and all three versions
  produced their own job: 3 declared, 3 executed, 3 passed.
  No matrix exclusion, no `if:` condition, no `continue-on-error`, and
  `fail-fast: false`. Collected item counts equal passed counts on every
  job, so no test was deselected or bypassed.

AC11:           PASS.

Scope note:     This records exactly one CI execution (run #19). No other
                CI run is claimed as B9.78 evidence.

B9.78 verification: COMPLETE. AC1-AC12 all PASS.
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

---

## 15. B9.79 — Number Allocation Record

`B9.79` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection. This section is the §11 record for that assignment.

```text
Assigned Number:
  B9.79

Allocation Date:
  2026-10-01

Allocation Commit:
  PENDING — established by the commit that introduces section 15
  ("docs: define roadmap block B9.79"). As with the numbering-policy activation
  anchor in section 11, a commit hash cannot be known before the commit exists,
  so it is recorded as PENDING here and fixed in the next controlled commit
  that sets it to that hash.

Corpus/HEAD Anchor:
  f8ddafc3cf162fa0e73bfb242e26a9d3d9d419c8
  git tree object 61a7bc143eea789838a00c725879cbfa3c795a2c

Corpus File Count:
  203

Corpus Integrity Evidence:
  Reproducible, git-native procedure (an equivalent verifiable procedure under
  section 7):
    git rev-parse HEAD         -> f8ddafc3cf162fa0e73bfb242e26a9d3d9d419c8
    git rev-parse HEAD^{tree}  -> 61a7bc143eea789838a00c725879cbfa3c795a2c
    git ls-files | wc -l       -> 203
  The versioned file set is fixed by the git tree object above: any change to
  the file list changes the tree hash. The four SHA-256 digests recorded for
  B9.78 depended on a hashing procedure that is not preserved in the corpus;
  they are not reproduced here, and the git tree object is used in their place.

Identifier Set:
  107 distinct identifiers in 203 versioned files: 51 main
  (B9.0-B9.6, B9.7-B9.16, B9.18-B9.24, B9.29-B9.31, B9.35-B9.37,
  B9.39-B9.48, B9.50-B9.59, B9.66, B9.67, B9.74, B9.76, B9.77, B9.78) and
  56 sub (B9.6.0/.1, B9.46.1-.29, B9.57.1-.8, B9.76.1-.5).

Highest Verified Main Block:
  B9.78 — allocated and implemented at
  8955fc6d91745ef3685fff00c6c8a6b03ac9a28e, recorded in section 14, and
  present in source and tests as an executable block.

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled Cline corpus inspection + formal registration

Candidate Numbers Considered:
  B9.79 — SELECTED (highest verified + 1)
  B9.25, B9.26, B9.27, B9.28, B9.32, B9.33, B9.34, B9.38, B9.49, B9.60,
  B9.61, B9.62, B9.63, B9.64, B9.65, B9.68, B9.69, B9.70, B9.71, B9.72,
  B9.73, B9.75 — rejected: historical gaps, not reusable under section 9
  B9.57.4 — rejected: sub-block, never raises the main floor (section 8)
  B9.80, B9.81, B9.82, B9.83 — rejected: illustrative examples in section 8,
  not allocations
  B9.80.1, B9.80.2, B9.80.3 — rejected: example sub-blocks (section 8)
  B9.76.1, B9.76.2, B9.76.3, B9.76.4, B9.76.5 — rejected: real sub-blocks;
  a sub-block does not advance the main floor (section 8)

Selected Number:
  B9.79

Validity Reason:
  B9.78 is the highest verified allocated main block in the complete 203-file
  corpus. Under the active rule, the next main block is therefore B9.79. No
  allocated main identifier above B9.78 was found: B9.79 through B9.83 occur
  only inside this document — in the section 14 candidate list, as negative
  assertions, or as the section 8 illustrative example — and evidence no
  allocation.
```

### 15.1 Register entry for B9.79

```text
Block ID:                 B9.79
Name:                     Runtime Artifact Evidence — Pre-Admission
Status:                   DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED
Origin:                   this document, section 15
Scope:                    see 15.2
Non-goals:                see 15.12
Dependencies:             see 15.13
Current State:            VERIFIED AND CLOSED — see 15.14 and 15.16
Acceptance Criteria:      AC1-AC10 — see 15.15 (all PASS per 15.16)
Evidence:                 see 15.13 and 15.16
Evidence Type:            DOC
Implementation Commit:    5f781e4674226492adeedb632097a503ef983d8d
                          ("feat: implement B9.79 runtime artifact evidence")
Verification Result:      B9.79 VERIFIED — READ-ONLY audit against the
                          implementation commit; see 15.16
Closure Commit:           recorded by the commit that introduces section 15.16
                          ("docs: close B9.79 verification")
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 15
Retrospective Record:     NO — a prospective allocation and decision record
```

### 15.1.1 Status vocabulary note

`DEFINED` is **not** an allowed status in §3.1, so it was not invented here
either. The closest existing documented status is **`DOCUMENTED`** ("a canonical
block document exists under `docs/`"), which is accurate: this definition is
recorded in this document. `ALLOCATED` is retained because §15 governs the
number.

**Superseded in part by the verification closure (§15.16).** The allocation-time
sentence below is preserved deliberately as historical evidence:

> `IMPLEMENTED` was deliberately absent at allocation time — no production code
> for B9.79 existed then — and B9.79 was not marked `VERIFIED` or `CLOSED`. Only
> a subsequent implementation satisfying AC1-AC10 (§15.15) could close the block.

That implementation now exists at
`5f781e4674226492adeedb632097a503ef983d8d` and the READ-ONLY verification audit
recorded in §15.16 established `B9.79 VERIFIED`. The current authoritative
status is therefore **`DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED`**
(§15.1, §15.14, §15.16).

---

### 15.2 Scope

B9.79 establishes the architectural contract for producing
`RuntimeArtifactEvidence` at the physical runtime/artifact observation boundary
**before** admission, transporting it through the existing evaluation input, and
allowing strict evaluation to use that evidence to characterize the concrete
runtime's compatibility with the artifact.

The implementation must preserve:

```text
1. admission as the sole authority;
2. deny-only behavior;
3. deny-by-default / fail-closed where applicable;
4. `None` or absence of evidence must not become a positive assertion;
5. the existing execution re-validation;
6. the B9.66 and B9.67 contracts;
7. the evaluation/execution separation established earlier.
```

---

### 15.3 Architectural decision (recorded)

The human architectural decision recorded for B9.79 is:

```text
Adopt option A of B9.46.23: obtain `RuntimeArtifactEvidence` through
pre-admission observation of the runtime/artifact.
```

The intent is for CastleArq to obtain physical evidence, before execution is
authorized, about whether the concrete runtime can receive/load the artifact.

This decision does **not** mean that the runtime has demonstrated successful
inference. The following are different properties and must not be conflated:

```text
- artifact received;
- artifact opened/parsed;
- artifact loaded;
- backend initialized;
- inference executed.
```

The preparatory experiment demonstrated evidence A-D for the current runtime
through a load of the form:

```text
llama cli --simple-io --single-turn --model <artifact> --device <device>
  --prompt hi -n 0 -lv 4
```

and established that:

```text
- `-n 0` allows loading without significant generation;
- `--single-turn` avoids remaining in a REPL;
- the model load can be observed through runtime output;
- the process can open a local HTTP socket;
- the operation is not a lightweight dry-run;
- the observed cost for the experimental artifact was approximately 5.64 s
  and ~11.9 GiB of process/environment memory, with ~7.17 GiB of KV cache.
```

These figures are experimental evidence of the tested environment and must
**not** be turned into universal product requirements.

---

### 15.4 Evidence contract

B9.79 evidence must respect the contract ratified for `RuntimeArtifactEvidence`
in B9.46.23.

```text
runtime_identity        required
runtime_version         required
artifact_reference      required
artifact_format         required
artifact_architecture   optional
backend                 optional
observation             required
provenance              required
```

Explicitly outside this contract:

```text
- model_id;
- ModelArtifact.identifier;
- manifest state;
- generated text;
- persistence schema;
- event stream;
- audit log.
```

The evidence is physical/observational and ephemeral in this phase. No
persistence is introduced as part of B9.79.

---

### 15.5 Observation semantics

```text
- positive evidence  -> may be projected to PASSED;
- negative evidence  -> may be projected to FAILED;
- absence / unavailability / non-performance of the observation -> UNKNOWN;
- producer error     -> a production/evaluation error, NOT silently converted
                        into FAILED.
```

`UNKNOWN` remains a valid contractual state. B9.79 does **not** remove
`UNKNOWN`.

---

### 15.6 Limit of the guarantee

```text
B9.79 does NOT guarantee that pre-admission RuntimeArtifactEvidence is
equivalent to successful inference.
```

Pre-admission evidence establishes only what the observed runtime could
demonstrate during the observation operation performed. In particular:

```text
- successful load is not successful inference;
- backend initialization is not successful generation;
- a process exit code of 0 is not proof of inference when no inference ran.
```

---

### 15.7 Cost and known limitation

```text
The currently available experimental implementation requires a real artifact
load, not a lightweight dry-run mechanism.
```

B9.79 therefore acknowledges:

```text
- possible significant time cost;
- possible significant memory cost;
- a possible additional process;
- a possible local HTTP/socket side effect;
- a possible double load if an independent execution is later performed.
```

These costs are part of the design context and must be considered during
implementation. This formalization does **not** invent a caching, persistent
runtime, process reuse, daemonization or new dry-run mechanism.

---

### 15.8 Transport

```text
B9.79 will, in principle, use the architectural seams already identified during
the audit:
- the `evidence_reader` / application-layer evidence seam;
- `evaluate_strict`;
- the existing evaluation input / physical evidence transport.
```

No new architectural layer is created by this formalization. The later
implementation must verify whether these seams are sufficient before
introducing new components.

---

### 15.9 Relationship with B9.78

```text
B9.79 depends conceptually on the admission architecture consolidated by B9.78.
```

B9.79 does **not** replace:

```text
- admission;
- deny-only;
- fail-closed;
- execution re-validation.
```

B9.79 adds evidence for the evaluation performed before admission. The
historical register entry and the closure of B9.78 are not modified.

---

### 15.10 Option B — post-execution evidence (deferred, not implemented)

```text
Post-execution evidence derived from `ExecutionResult` is a possible later
evolution.
```

It is **not** part of the B9.79 implementation, no new identifier is assigned
to it here, and it is **not** an immediate obligation. The architecture must
avoid closing the door to a future coexistence of pre-admission evidence with
post-execution evidence.

---

### 15.11 Option C — UNKNOWN

```text
UNKNOWN remains a valid result when there is insufficient evidence or the
observation cannot be performed.
```

B9.79 does not turn absence of evidence into `PASSED` or into `FAILED`.

---

### 15.12 Non-goals

Declared out of scope for B9.79:

```text
1.  implementing the probe / runtime observer;
2.  changing production code yet;
3.  changing the CLI;
4.  changing the API;
5.  creating evidence persistence;
6.  creating evidence caching;
7.  reusing runtime processes;
8.  creating a daemon / runtime manager;
9.  introducing a non-existent dry-run;
10. implementing post-execution evidence;
11. redefining inference success;
12. modifying B9.78;
13. modifying packaging/release/distribution;
14. introducing Ollama;
15. introducing multi-runtime;
16. introducing multi-GPU / distributed execution;
17. introducing a GUI / web UI;
18. performing unrelated cleanup.
```

---

### 15.13 Dependencies and evidence

References preserved:

```text
B9.46.23 — RuntimeArtifactEvidence contract / architectural alternatives
B9.46.25
B9.46.26
B9.47    — product identity / orchestration boundary
B9.66    — imported artifact tolerance
B9.67    — managed path requirements
B9.78    — legacy admission cutover
experimental runtime/artifact observation performed during B9.79 decision
preparation
```

The decision was preceded by real experimental evidence against the local
runtime and a real GGUF. The experiment is evidence of the tested environment,
not a universal proof for all runtimes/artifacts.

---

### 15.14 Current state

**Superseded in part by the verification closure (§15.16).** The allocation-time
record below is preserved deliberately as historical evidence:

```text
Formally allocated.
Defined.
Architectural decision taken.
Implementation pending.
```

B9.79 was **not** `IMPLEMENTED`, `VERIFIED` or `CLOSED` at allocation time. A
later implementation could close the block only after satisfying its acceptance
criteria (§15.15), which the allocation documentation task did **not** claim to
satisfy.

Current authoritative state: **IMPLEMENTED, VERIFIED AND CLOSED** — implemented
at `5f781e4674226492adeedb632097a503ef983d8d` and verified by the READ-ONLY
audit recorded in §15.16 (AC1-AC10 all PASS).

---

### 15.15 Acceptance criteria

Contractual criteria (not an implementation):

```text
AC1  There is a formal definition of pre-admission RuntimeArtifactEvidence.
AC2  The evidence is obtained at the physical runtime/artifact boundary before
     admission.
AC3  The evidence uses the B9.46.23 contract.
AC4  UNKNOWN remains valid when there is no evidence.
AC5  Positive/negative evidence does not remove the sole authority of
     admission.
AC6  The evaluation/admission/execution separation remains intact.
AC7  B9.78 remains compatible with the decision.
AC8  The limitation that the current observation may require a real artifact
     load is documented.
AC9  Post-execution evidence is explicitly outside the B9.79 implementation.
AC10 No persistence, caching, process reuse, daemonization or dry-run is
     introduced as part of this formalization.
```

**Important.** These acceptance criteria describe the B9.79 contract and were
**not** represented as satisfied by the allocation documentation task. They
became satisfiable only through the implementation at
`5f781e4674226492adeedb632097a503ef983d8d`, and §15.16 records them all PASS
on the READ-ONLY verification audit.

---

### 15.16 Verification and closure record

READ-ONLY verification audit of the implementation commit
`5f781e4674226492adeedb632097a503ef983d8d`
("feat: implement B9.79 runtime artifact evidence").

```text
Verification Result:
  B9.79 VERIFIED

Implementation Commit (verified contents — immutable, never rewritten):
  5f781e4674226492adeedb632097a503ef983d8d

Verification Scope (all established):
  - RuntimeArtifactEvidence contract compliance (8 fields; no model_id,
    ModelArtifact.identifier, manifest state, generated text, ExecutionResult,
    persistence schema, event stream, or audit log; ephemeral)
  - POSITIVE semantics (explicit load marker AND exit 0; exit 0 alone never
    POSITIVE)
  - NEGATIVE semantics (explicit rejection marker; non-zero exit alone never
    NEGATIVE; explicit failure takes precedence)
  - UNKNOWN semantics (insufficient evidence, timeout, missing
    executable/path/device, no reliable signal; timeout never NEGATIVE)
  - producer-error distinction (RuntimeObservationError propagates, never
    folded into NEGATIVE)
  - real executable resolution (absolute path from RuntimeCapability; observer
    launches it directly, independent of PATH lookup)
  - real local llama runtime execution
  - real valid-GGUF POSITIVE observation
  - real nonexistent-GGUF NEGATIVE observation
  - UNKNOWN observation with successful process and no load marker
  - admission integration (POSITIVE->PASSED->compatible;
    NEGATIVE->FAILED->incompatible/denied; UNKNOWN->UNKNOWN->non-blocking)
  - architecture boundary preservation (single execution pipeline; pure
    evaluation layers subprocess-free)
  - full regression compatibility
  - scope integrity
  - clean working tree

Verified Runtime (externally resolved local runtime, not bundled with
CastleArq):
  /home/brunapc/.local/bin/llama
  0.4.0-dev (build 10909, commit a2878d30d)

Regression Result:
  1847 passed / 2672 subtests passed / 0 failed / 0 errors / 0 skipped

Real-Runtime Evidence (measured; concise, no raw logs):
  POSITIVE probe:
    - valid GGUF
    - exit code 0
    - explicit model-load markers observed
    - supports_artifact = True
    - approximately 5.63 s
    - process terminated cleanly
  NEGATIVE probe:
    - nonexistent GGUF
    - exit code 1
    - explicit model-loading rejection markers observed
    - supports_artifact = False
  UNKNOWN probe:
    - successful process
    - no explicit model-load marker
    - observation = UNKNOWN
    - supports_artifact = None

Acceptance Criteria:
  AC1-AC10 all PASS.
```

The implementation commit above is the verified artifact and remains immutable.
This closure record only attests that the verified implementation has been
formally closed; it does not replace the implementation anchor. B9.79 is
**CLOSED**. No B9.80 or any other identifier is allocated here.

---

## 16. B9.80 — Number Allocation Record

`B9.80` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. B9.80 is an allocation only: no implementation,
verification, or closure is claimed here.

```text
Assigned Number:
  B9.80

Title:
  Model Discovery Domain Contract

Allocation Date:
  2026-10-01

Allocation Commit:
  PENDING — established by the commit that introduces section 16
  ("docs: allocate roadmap block B9.80").

Corpus/HEAD Anchor:
  a044e94f2d40bc3d629614776ca81b03fe078c53
  (docs: close B9.79 verification; main ahead 3 of origin/main f8ddafc)

Corpus File Count:
  208 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  git rev-parse HEAD -> a044e94f2d40bc3d629614776ca81b03fe078c53
  git rev-parse origin/main -> f8ddafc3cf162fa0e73bfb242e26a9d3d9d419c8
  git status --porcelain=v1 --branch -> clean, main ahead 3
  git tree object at HEAD -> 3e7ed979e41897c23857851ba120e471bac81318

Identifier Set:
  Main/sub families carried forward from section 15 (51 main through B9.79,
  56 sub), plus illustrative-only strings B9.80, B9.80.1-B9.80.3, B9.81-B9.83
  in sections 7.5, 8, 15. No identifier above B9.79 is in real use in code,
  tests, docs, or configuration outside illustrative/rejection lists.

Highest Verified Main Block:
  B9.79 — allocated in section 15 (925cc46), implemented at 5f781e4,
  verified and closed at a044e94 (15.14, 15.16).

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled Cline corpus inspection + formal registration

Candidate Numbers Considered:
  B9.80 — SELECTED (highest verified + 1)
  Historical gaps — rejected: not reusable under section 9
  B9.57.4 — rejected: sub-block, never raises the main floor (section 8)
  B9.81, B9.82, B9.83 — rejected: illustrative examples in section 8
  B9.80.1, B9.80.2, B9.80.3 — rejected: example sub-blocks (section 8)
  B9.76.1-B9.76.5 — rejected: real sub-blocks, non-advancing (section 8)

Selected Number:
  B9.80

Validity Reason:
  B9.79 is the highest verified allocated main block at a044e94. The next
  main block is therefore B9.80. No allocated main identifier above B9.79
  was found: B9.80-B9.83 and B9.80.1-B9.80.3 occur only as the section 8
  illustrative hierarchy, rejection lists, or negative assertions.
```

**Illustrative-reference note.** The `B9.80`/`B9.80.x`/`B9.81`-`B9.83`
occurrences in section 8 and the section 7.5/15 rejection lists remain valid
as abstract hierarchy illustrations and negative evidence. They are not
modified by this assignment; this section 16 is the sole normative allocation
of `B9.80`. No `B9.80.x` sub-block is assigned here.

### 16.1 Register entry for B9.80

```text
Block ID:                 B9.80
Name:                     Model Discovery Domain Contract
Status:                   DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED
Origin:                   this document, section 16
Scope:                    see 16.2
Non-goals:                see 16.3
Dependencies:             see 16.4
Current State:            VERIFIED AND CLOSED — see 16.6 and 16.7
Acceptance Criteria:      AC1-AC12 — see 16.5 (all PASS per 16.7)
Evidence:                 see 16.4 and 16.7
Evidence Type:            DOC
Implementation Commit:    389f390c7aa5b154a697a6253dcc58b6ceec713e
                          ("feat: implement B9.80 model discovery domain contract")
Verification Result:      B9.80 VERIFIED — READ-ONLY audit against the
                          implementation commit; see 16.7
Closure Commit:           recorded by the commit that introduces section 16.7
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 16
Retrospective Record:     NO — prospective allocation record
```

### 16.2 Scope

B9.80 introduces the domain contract for discovering remote models and
representing remote candidates, variants, and declared remote artifacts,
moving from acquisition of already-known artifacts toward future
search/inspection, without mixing discovery with acquisition, evaluation,
admission, or execution.

```text
ModelDiscovery
 ├── search(query, limit?, cursor?) -> (candidates, next_cursor)
 └── inspect(repository) -> remote artifacts / variants

ModelCandidate        remote search hit: untrusted metadata only
ModelVariant          remote declared grouping (declared_quantization)
DiscoveredArtifact    remote declared/unverified artifact (L1 only)
```

Acquisition boundary (later reuse, not implemented here):

```text
DiscoveredArtifact
    ↓

### 16.3 Non-goals

```text
1.  GUI;  2. CLI;  3. automatic downloads;  4. ModelStore persistence;
5.  evaluation;  6. admission;  7. execution;  8. LoRA;  9. datasets;
10. fine-tuning;  11. multi-GPU;  12. clusters;  13. marketplace/accounts;
14. recommendations/ranking;  15. telemetry;  16. verified quantization;
17. replacement of ArtifactSpec;  18. replacement of DownloadPlan/Planner/
    Downloader;  19. replacement of ModelStore;  20. changes to B9.79;
21. provider implementation;  22. model_identity.py changes or fuzzy matching.
```

### 16.4 Dependencies and evidence

```text
B9.40 — download registration/persistence behavior, reused later
B9.41 — derived ModelStore state, reused later
B9.67 — local artifact/content-identity boundary, remains separate
B9.74 — ModelStore resolution, remains reusable
B9.78 — admission remains the sole execution authority
B9.79 — runtime artifact evidence remains downstream and unchanged;
        B9.79 does NOT depend on B9.80. Direction: B9.80 discovery →
        future acquisition → future stored artifact → B9.79 evidence
```

Prior READ-ONLY audits: single-repo HuggingFaceSource flow, one-row identity
map, and the complete plan→download→verify→store→resolve→evaluate→admit→
execute pipeline verified present; search/candidate/variant/discovered
concepts verified absent (zero corpus hits outside this record).

### 16.5 Acceptance criteria

Contractual criteria, all PENDING at allocation time (not satisfied by this
allocation task; only a later implementation can satisfy them):

```text
AC1  ModelDiscovery exists as a conceptual/contractual boundary.
AC2  search() is defined (query, limit?, cursor? -> candidates + cursor).
AC3  inspect() is defined (repository -> remote artifacts / variants).
AC4  ModelCandidate is defined as remote/untrusted metadata.
AC5  ModelVariant is defined as a remote declared grouping.
AC6  DiscoveredArtifact is defined as a remote/unverified artifact (L1).
AC7  Discovery does not persist to ModelStore.
AC8  Discovery performs no admission and no execution.
AC9  declared_quantization is never treated as verified runtime evidence.
AC10 No AcquisitionPlan duplicate of DownloadPlan is introduced.
AC11 B9.79 remains out of scope and unmodified.
AC12 DiscoveredArtifact → ArtifactSpec conversion sits at the acquisition
     boundary (explicit mapper), not as self-promotion.
```

**Status after implementation.** These acceptance criteria were **not**
represented as satisfied by the allocation documentation task. They became
satisfiable only through the implementation at
`389f390c7aa5b154a697a6253dcc58b6ceec713e`, and §16.7 records them all PASS on
the READ-ONLY verification audit.

### 16.6 Current state

**Superseded in part by the verification closure (§16.7).** The allocation-time
record below is preserved deliberately as historical evidence:

```text
Formally allocated.
Defined.
Architectural decision taken.
Implementation pending.
```

B9.80 was **not** `IMPLEMENTED`, `VERIFIED` or `CLOSED` at allocation time. A
later implementation could close the block only after satisfying its acceptance
criteria (§16.5), which the allocation documentation task did **not** claim to
satisfy.

Current authoritative state: **IMPLEMENTED, VERIFIED AND CLOSED** — implemented
at `389f390c7aa5b154a697a6253dcc58b6ceec713e` and verified by the READ-ONLY
audit recorded in §16.7 (AC1-AC12 all PASS).

No B9.80.x sub-block is assigned. No B9.81 or other identifier is allocated
here. B9.79 remains CLOSED and is not modified retrospectively.

**Formatting repair (closure edit).** The allocation commit introduced the flow
block below without its opening fence line, so this block and the two
paragraphs after it rendered as code. The opening fence line is restored by this
edit; no allocation-time wording is changed or removed.

```text
acquisition mapper (explicit, in acquisition)
    ↓
ArtifactSpec (existing type, unchanged by B9.80)
```

Decisions: ModelDiscovery is a port knowing no HF/filesystem/ModelStore/
evaluation/admission/execution. ModelCandidate carries no file, local state,
path, content identity, or verdict (no catalog_model_id field). Quantization
is declared_quantization, never verified evidence. DiscoveredArtifact carries
no state/content_id/paths/verdicts. No ArtifactSpec redefinition. No
AcquisitionPlan (DownloadPlan/Planner/Downloader reused later).

Trust: L1 Remote metadata (B9.80 ONLY) → L2 Downloaded+verified (future) →
L3 Runtime evidence (B9.79, unchanged). Provider direction:
HuggingFaceDiscoveryProvider implements ModelDiscovery; domain never depends
on Hugging Face. model_identity.py unchanged (no rows, no fuzzy, no ranking).

### 16.7 Verification and closure record

READ-ONLY verification audit of the implementation commit
`389f390c7aa5b154a697a6253dcc58b6ceec713e`
("feat: implement B9.80 model discovery domain contract").

```text
Verification Result:
  B9.80 VERIFIED

Implementation Commit (verified contents — immutable, never rewritten):
  389f390c7aa5b154a697a6253dcc58b6ceec713e

Committed Files (exclusively; exactly two new files):
  castlearq/discovery.py                (new, 142 lines)
  tests/test_b980_model_discovery.py    (new, 137 lines)

Verification Scope (all established):
  - ModelDiscovery domain port exists as an ABC in castlearq/discovery.py,
    imported only from the standard library (abc, dataclasses); no Hugging
    Face, provider, filesystem, network, ModelStore, acquisition,
    evaluation, admission or execution reference in the module (AC1)
  - search(query, *, limit, cursor) defined; returns (candidates,
    next_cursor); cursor is opaque: accepted and returned without
    interpretation; no pagination logic in the port (AC2)
  - inspect(repository) defined; returns remote declared variants
    (artifacts/variants) for the repository; no local resolution (AC3)
  - ModelCandidate frozen dataclass of remote/untrusted metadata only
    (provider_id, repository, display_name, author, description, tags,
    declared_architecture, has_gguf); no local path, content identity,
    state or verdict fields; no catalog_model_id (AC4)
  - ModelVariant frozen dataclass: one ModelCandidate +
    declared_quantization + at least one artifact held in an immutable
    tuple; declared only, never a verified quantization claim (AC5)
  - DiscoveredArtifact frozen dataclass of L1 declared remote metadata
    (repository, filename, format, declared_quantization, declared_size,
    declared_sha256, revision, download_url, source, model_id); no local
    state, no content identity, no admission or execution verdict (AC6)
  - no ModelStore import, persistence, caching or resolver interaction (AC7)
  - no admission, evaluation or execution behavior in discovery (AC8)
  - quantization surfaced only as declared_quantization and documented as
    declared, never as verified runtime evidence (AC9)
  - no AcquisitionPlan type and no download/acquisition behavior; no import
    from the acquisition pipeline (AC10)
  - B9.79 implementation contents unchanged by the commit; B9.79 remains
    CLOSED (AC11)
  - no DiscoveredArtifact -> ArtifactSpec or DiscoveredArtifact ->
    DownloadPlan conversion in the domain; the mapper belongs to the future
    acquisition boundary (AC12)
  - error independence: DiscoveryError is a plain domain Exception,
    independent from the infrastructure SourceError
  - scope integrity: the commit touches only the two new files above; no
    production wiring, CLI, API, packaging, release or roadmap change
  - clean working tree after the commit; formatting and whitespace checked
    with grep-based import inspection and git diff --check (ruff is not
    available in this environment)

Regression Result:
  1862 passed / 2672 subtests passed / 0 failed / 0 errors / 0 skipped
  (B9.80 tests: 15 passed)

Acceptance Criteria:
  AC1-AC12 all PASS.
```

The implementation commit above is the verified artifact and remains immutable.
This closure record only attests that the verified implementation has been
formally closed; it does not replace the implementation anchor. B9.80 is
**CLOSED**. No B9.80.x sub-block is assigned, and no B9.81 or any other
identifier is allocated here.

---

## 17. B9.81 — Number Allocation Record

`B9.81` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.81 was an allocation only: no
implementation, verification, or closure was claimed by this section. The block
has since been implemented, independently verified and formally closed; the
authoritative state is the register entry in §17.1 and the verification and
closure record in §17.9. The allocation-time facts recorded in this section are
preserved unchanged as historical evidence.

```text
Assigned Number:
  B9.81

Title:
  Hugging Face Discovery Provider

Allocation Date:
  2026-10-01

Allocation Commit:
  0a237082b01be95a9a15f058029502dbec358787
  ("docs: allocate roadmap block B9.81").

Corpus/HEAD Anchor:
  64848c7c3e78e876a62883eea6ddf130857bab3e
  (docs: correct roadmap consistency records; main == origin/main)

Corpus File Count:
  210 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  git rev-parse HEAD -> 64848c7c3e78e876a62883eea6ddf130857bab3e
  git rev-parse origin/main -> 64848c7c3e78e876a62883eea6ddf130857bab3e
  git status --porcelain=v1 --branch -> clean, main == origin/main
  git tree object at HEAD -> 0ff620257ecb6aecaf349bd5c3567ed299852763
  sorted path list SHA-256 ->
    1491b101ea4e469f85b455a74703ef2198f51720194ea8e9597f0dde61170c52
  sorted occurrence list SHA-256 ->
    eaa1e59d37b459f35a4fb2fb6be347850ba013a2fe05d77176c82e376e9e9023
  identifier-set SHA-256 ->
    29e6a7c946e1b85674f8602d0a842be793fb4a704735a89c92be05b9c63ddbf7
  mechanism: git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
  | LC_ALL=C sort [-u]; sha256sum over each sorted list

Identifier Set:
  130 distinct identifiers over 2700 occurrences in 210 versioned files:
  83 main-form and 47 sub-form (B9.6.0/.1, B9.46.1-.29, B9.57.1-.8,
  B9.76.1-.5, B9.80.1-.3). The highest main-form string in the corpus is
  B9.83; every occurrence of B9.81, B9.82, B9.83 and B9.80.1-B9.80.3 lies
  inside this document (section 8 illustration, sections 14/15/16
  rejection lists, section 16 negative assertions). Zero files outside
  this document contain B9.81-B9.84. The highest identifier in real use
  outside this document is B9.80.

Highest Verified Main Block:
  B9.80 — allocated in section 16 (67459f8), implemented at 389f390,
  verified and closed at d49a909 and 64848c7 (16.6, 16.7).

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled Cline corpus inspection + formal registration

Candidate Numbers Considered:
  B9.81 — SELECTED (highest verified + 1); its corpus occurrences are the
    section 8 illustration, the sections 14/15/16 rejection lists, and the
    section 16 "not allocated here" assertions — none of which is an
    allocation; this section 17 is the sole normative allocation of B9.81
  Historical gaps (B9.25-B9.28, B9.32-B9.34, B9.38, B9.49, B9.60-B9.65,
    B9.68-B9.73, B9.75, and every other main number below B9.80 that is
    not allocated by sections 14-16) — rejected: historical gaps, not
    reusable under section 9
  B9.80.1, B9.80.2, B9.80.3 — rejected: example sub-blocks (section 8)
  B9.76.1-B9.76.5, B9.57.4 — rejected: real sub-blocks; a sub-block does
    not advance the main floor (section 8)
  B9.82, B9.83 — rejected: illustrative examples in section 8, not
    allocations
  B9.84 and above — rejected: no occurrence of any such identifier exists
    in the corpus; never considered by any prior record

Selected Number:
  B9.81

Validity Reason:
  B9.80 is the highest verified allocated main block at 64848c7: allocated
  in section 16, implemented at 389f390, verified and closed at d49a909
  and 64848c7 (16.6, 16.7). The next main block is therefore B9.81. No
  allocated main identifier above B9.80 was found: B9.81-B9.83 and
  B9.80.1-B9.80.3 occur only as the section 8 illustrative hierarchy,
  rejection lists in sections 14/15/16, or section 16 negative assertions
  scoped to section 16. Sub-blocks never raise the main floor (section 8)
  and historical gaps are not reusable (section 9).
```

**Illustrative-reference note.** The `B9.81`/`B9.82`/`B9.83` occurrences in
section 8 and the rejection lists in sections 14-16 remain valid as abstract
hierarchy illustrations and as time-anchored negative evidence for their
respective allocation-time corpora. They are not modified by this assignment;
this section 17 is the sole normative allocation of `B9.81`. No `B9.80.x`
sub-block is assigned here.

### 17.1 Register entry for B9.81

```text
Block ID:                 B9.81
Name:                     Hugging Face Discovery Provider
Status:                   DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED
Origin:                   this document, section 17
Scope:                    see 17.2
Non-goals:                see 17.3
Dependencies:             see 17.4
Architectural Decisions:  see 17.5
Current State:            CLOSED — implemented, independently verified,
                          (VERIFIED WITH MINOR OBSERVATIONS) and formally
                          closed; authoritative closure record in 17.9
Acceptance Criteria:      AC1-AC15 — see 17.6; all PASS, recorded in 17.9
Evidence:                 see 17.4, prior READ-ONLY discovery audits and 17.9
Evidence Type:            DOC
Implementation Commit:    ef9f9b94c7688d037fb2c7da70fee93f497296a4
                           ("feat: implement B9.81 Hugging Face discovery
                           provider")
Verification Result:      B9.81 VERIFIED WITH MINOR OBSERVATIONS — READ-ONLY
                           audit of the implementation working tree; see 17.9
Closure Commit:           recorded by the commit that introduces section 17.9
                           ("docs: close B9.81 verification")
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 17
Retrospective Record:     NO — prospective allocation record; implementation,
                           verification and closure recorded in 17.9
```

### 17.2 Scope

B9.81 introduces a concrete Hugging Face discovery provider implementing the
CLOSED `ModelDiscovery` domain contract of B9.80, turning remote public
metadata into search and inspection results, without acquiring, persisting,
admitting, or executing anything.

```text
Hugging Face public metadata API
            ↓
HuggingFaceDiscoveryProvider
            ↓
ModelDiscovery            (B9.80 — CLOSED, unchanged)
            ↓
ModelCandidate
ModelVariant
DiscoveredArtifact
```

The provider may perform:

```text
- repository search (query, limit, opaque cursor translation);
- repository inspection;
- GGUF artifact discovery without downloading artifact content;
- declared quantization extraction (declared only, never verified);
- declared metadata extraction (declared size, declared SHA-256 where
  available);
- remote revision/reference extraction as declared information;
- download locator metadata (URL construction) as declared information;
- controlled transport/API error mapping into DiscoveryError.
```

The provider MUST NOT perform acquisition.

### 17.3 Non-goals

```text
1.  DiscoveredArtifact → ArtifactSpec conversion;  2. acquisition mapper;
3.  DownloadPlan;  4. AcquisitionPlan;  5. Downloader;  6. ModelStore;
7.  admission;  8. execution;  9. evaluation;  10. runtime evidence;
11. model_identity.py changes;  12. catalog registration;
13. catalog persistence;  14. ranking;  15. recommendations;
16. fuzzy matching;  17. CLI changes;  18. GUI;  19. model library UI;
20. model marketplace/catalog UX;  21. automatic download;
22. automatic installation;  23. model deletion;
24. caching/persistence of discovery results;  25. verified content claims;
26. modification of B9.80 domain types;  27. modification of B9.79 runtime
    evidence;  28. modification of B9.78 admission;  29. refactoring
    HuggingFaceSource into a shared abstraction;  30. introducing a new
    ArtifactSpec or acquisition-domain type.
```

The block must NOT become the model library. It establishes the real remote
discovery backend that a future model-library surface can consume.

### 17.4 Dependencies and evidence

```text
B9.80 — ModelDiscovery contract (search, inspect, ModelCandidate,
        ModelVariant, DiscoveredArtifact, DiscoveryError), CLOSED and
        unchanged; B9.81 implements the port and never edits it
B9.78 — admission remains the sole execution authority, out of scope
B9.79 — runtime evidence remains downstream and unchanged; B9.79 does NOT
        depend on B9.81. Direction: B9.81 discovery → future acquisition
        mapper → future stored artifact → B9.79 evidence
B9.40/B9.41/B9.67/B9.74 — acquisition/store behavior, unchanged; reused
        only by later blocks, never imported by the provider
HuggingFaceSource — sibling infrastructure adapter; shared pure helpers
        may be reused where safe (decision A), the source itself remains
        functionally unchanged (AC13)

Dependency direction (recorded):

        castlearq.discovery
                ↑
                │ implements
                │
        HuggingFaceDiscoveryProvider
                │
                └── Hugging Face public metadata API

Rejected edges:
        discovery → ArtifactSpec
        discovery → DownloadPlanner
        discovery → Downloader
        discovery → ModelStore
        discovery → admission
        discovery → execution
```

The provider is an infrastructure-side implementation of the domain port; the
domain never depends on Hugging Face.

Prior READ-ONLY audits: the complete plan→download→verify→store→resolve
pipeline (ArtifactSpec → DownloadPlan → Downloader → ModelStore), the
single-repository HuggingFaceSource flow, unmapped-repository rejection at
the source, and the B9.80 contract isolation tests all verified present; the
absence of any production ModelDiscovery implementation and of any
HuggingFaceDiscoveryProvider verified by zero corpus hits outside this
record.

### 17.5 Architectural decisions (recorded)

```text
Decision A — reuse strategy: A-now / C-later.
  Reuse existing pure Hugging Face helpers where safe (validators,
  extractors, transport patterns). Do NOT refactor HuggingFaceSource into
  a shared abstraction in this block; do NOT modify HuggingFaceSource
  merely to prepare for the provider; defer extraction of a shared Hugging
  Face infrastructure layer until duplication becomes justified by
  evidence. The provider remains a sibling of HuggingFaceSource: not a
  subclass, not a wrapper, not a replacement, and it never returns
  ArtifactSpec.

Decision B — discovery vs catalog identity.
  The provider MUST NOT require a repository to exist in
  castlearq/model_identity.py. Unknown/unmapped repositories remain
  discoverable. DiscoveredArtifact.model_id may remain None. No
  modification to model_identity.py is part of this block; model_identity
  is never a discovery gate.

Decision C — revision.
  The provider exposes the remote revision/reference available from Hugging
  Face metadata (for example a model commit SHA or equivalent immutable
  reference) as declared discovery information in
  DiscoveredArtifact.revision. It is never reinterpreted as verified
  content identity. The existing downloader/planner URL contract is not
  modified, and revision-aware acquisition is not solved in this block.

Decision D — cursor.
  The ModelDiscovery cursor contract stays: cursor = opaque. Any Hugging
  Face-specific pagination mechanism is translated behind the provider
  boundary; no Hugging Face pagination type may leak into ModelDiscovery.

Decision E — L1 trust boundary.
  All provider output is DECLARED / UNTRUSTED REMOTE METADATA. The provider
  never produces verified_sha256, verified_quantization, content_id,
  local_path, ArtifactState, admission verdicts, execution verdicts, or
  evaluation verdicts. declared_sha256 remains a remote declaration; it is
  NOT runtime evidence.
```

### 17.6 Acceptance criteria

Contractual criteria, all PENDING at allocation time (not satisfied by this
allocation task; only a later implementation can satisfy them):

```text
AC1  A concrete HuggingFaceDiscoveryProvider exists and implements
     ModelDiscovery.
AC2  search(query, limit, cursor) returns valid ModelCandidate values plus
     the opaque cursor contract required by ModelDiscovery.
AC3  inspect(repository) returns valid ModelVariant values.
AC4  Inspection identifies GGUF artifacts without downloading artifact
     content.
AC5  Artifacts are grouped into valid ModelVariant values with non-empty
     artifact tuples.
AC6  Declared quantization, size, SHA-256, revision and download locator
     information are represented only as declared remote metadata.
AC7  A repository does not need to exist in model_identity.py to be
     discoverable.
AC8  Transport/API failures surface as DiscoveryError, not SourceError.
AC9  Repository, filename, URL and host handling follow the existing
     validated Hugging Face security constraints without permitting unsafe
     paths or hosts.
AC10 The provider does not depend on ModelStore, Downloader,
     DownloadPlanner, ArtifactSpec, admission, execution, evaluation, or
     runtime evidence.
AC11 No download, persistence, installation, deletion or acquisition
     planning occurs.
AC12 castlearq/discovery.py remains unchanged.
AC13 HuggingFaceSource remains functionally unchanged.
AC14 The existing relevant test suites and the complete repository suite
     remain green.
AC15 The provider is a sibling infrastructure adapter to HuggingFaceSource,
     not a subclass, wrapper, or replacement.
```

### 17.7 Implementation surface

Chosen location, recorded at allocation; no files are created by this task:

```text
castlearq/sources/huggingface_discovery.py
    concrete provider module — sibling of sources/huggingface.py; imports
    castlearq.discovery and pure helpers only, never imports acquisition
    modules

tests/test_b981_huggingface_discovery.py
    provider-specific tests covering at minimum: search; opaque cursor
    behavior; inspect; GGUF detection; variant grouping; declared
    quantization; declared size; declared SHA-256; revision; unmapped
    repository discovery; malformed metadata; HTTP/API errors;
    timeout/transport errors; host/repository/filename validation;
    L1 isolation.
```

If repository inspection at implementation time demonstrates a more
appropriate location, the implementing block must record the actual chosen
location in this section.

### 17.8 Verification and closure expectations

```text
Verification: COMPLETED — the READ-ONLY verification audit required by this
  section was performed against the B9.81 implementation and evaluated
  AC1-AC15; the result is recorded in 17.9. This allocation section performed
  no verification of its own.

Closure: COMPLETED — AC1-AC15 all PASS and the standard closure record is 17.9.
  B9.81 is CLOSED. The verification classification is
  "VERIFIED WITH MINOR OBSERVATIONS"; the recorded minor observations are
  non-blocking and required no correction.
```

B9.81 is a completed block: the HuggingFaceDiscoveryProvider and its tests
exist, as recorded in §17.9. No acquisition mapper, CLI, GUI, catalog or
model-library functionality was introduced by this block.
### 17.9 Verification and closure record

READ-ONLY verification audit of the B9.81 implementation, performed against the
working tree that contains the two new files recorded in §17.7, before any
commit.

```text
Verification Result:
  B9.81 VERIFIED WITH MINOR OBSERVATIONS

Implementation Anchor:
  castlearq/sources/huggingface_discovery.py   (new, 432 lines)
  tests/test_b981_huggingface_discovery.py     (new, 733 lines)
  Implementation commit: ef9f9b94c7688d037fb2c7da70fee93f497296a4
  ("feat: implement B9.81 Hugging Face discovery provider")
  No production or test file was modified and no other file was created.

Verification Scope (all established):
  - HuggingFaceDiscoveryProvider implements the B9.80 ModelDiscovery port as a
    frozen dataclass with injectable transport; the module imports
    castlearq.discovery and the standard library only (AC1, AC10)
  - search and inspect query the public Hugging Face metadata API; one request
    per page and per inspection, no per-candidate requests; declared metadata
    only, opaque cursor translated behind the provider boundary (AC2, AC3)
  - GGUF discovered from remote tree metadata without downloading artifact
    content; /resolve/ never requested; download_url is a declared locator,
    not a downloaded, verified or admitted artifact (AC4, AC11)
  - artifacts grouped by declared_quantization into variants with non-empty
    artifact tuples and deterministic ordering; no ranking, recommendation or
    fuzzy matching (AC5)
  - declared quantization, size, SHA-256 (lfs.oid only), revision and download
    locator represented strictly as declared remote metadata (AC6)
  - no model_identity dependency or identity gate; unmapped repositories remain
    discoverable with model_id None (AC7)
  - transport/API failures mapped to DiscoveryError; SourceError neither
    imported nor raised; programming errors remain TypeError/ValueError (AC8)
  - repository, filename, URL/host and cursor validation preserved; the cursor
    cannot introduce a foreign host or path (AC9)
  - castlearq/discovery.py and castlearq/sources/huggingface.py byte-identical
    to their HEAD blobs; no existing code, test or roadmap file was modified
    by the implementation (AC12, AC13)
  - the provider is a sibling adapter: not a subclass, wrapper or replacement
    of HuggingFaceSource (AC15)

Regression Result:
  1921 passed / 2672 subtests passed / 0 failed / 0 errors / 0 skipped
  (B9.81 tests: 59 passed; B9.80 tests: 15 passed; HuggingFaceSource tests:
  18 passed)
  git diff --check: rc 0

Acceptance Criteria:
  AC1-AC15 all PASS.

Non-blocking minor observations (recorded; no correction required):
  - unused api_base parameter in the internal cursor helper
  - internal URL builders rely on the caller-side host gate
  - limit is ignored when an opaque cursor is supplied, and pagination depends
    on the Link response header
  - a single invalid remote entry can abort an entire search or inspection
  - the isolation test inspects the module's direct imports only; the
    pre-existing castlearq/sources/__init__.py package init still pulls
    HuggingFaceSource, models and model_identity into the import closure
    (unchanged by B9.81 and outside its implementation surface)
```

B9.81 is **CLOSED**. No B9.81.x sub-block is assigned and no new identifier is
allocated here. B9.78, B9.79 and B9.80 are not modified by this record. The
implementation anchor above is the verified artifact and remains immutable; this
closure record only attests that the verified implementation has been formally
closed.


---

## 18. B9.82 — Number Allocation Record

`B9.82` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.82 was an allocation only: no
implementation, verification, or closure was claimed by this section. The block
has since been implemented, independently verified and formally closed; the
authoritative state is the register entry in §18.1 and the verification and
closure record in §18.9. The allocation-time facts recorded in this section are
preserved unchanged as historical evidence.

```text
Assigned Number:
  B9.82

Title:
  Discovery-to-Acquisition Boundary

Allocation Date:
  2026-10-02

Allocation Commit:
  a3f4d3e9e0e3ebb5fd7b335b58920b905db348b6
  ("docs: allocate roadmap block B9.82").

Corpus/HEAD Anchor:
  ef452b271ad41c97a47ca508354183aa98373b4c
  (docs: close B9.81 verification; main == HEAD, four commits ahead of
  origin/main 64848c7c3e78e876a62883eea6ddf130857bab3e)

Corpus File Count:
  212 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  git rev-parse HEAD -> ef452b271ad41c97a47ca508354183aa98373b4c
  git tree object at HEAD -> 35085c28a212b0e2f9c1ce468e784c916479fd10
  sorted path list SHA-256 ->
    3af422d3f832d4dbe95f4414d304bb9bdf0f1295cc38cde446c0b2218f92fa50
  sorted occurrence list SHA-256 ->
    1ad077e73169a25a29639dc944b0e1eeeb4f2edf715285387cbf20476fea065f
  identifier-set SHA-256 ->
    efa732b8d6ec04548cad0700ab9580b64466d2db2ae2be585c5cfc2df213576c
  mechanism: git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
    | LC_ALL=C sort [-u]; sha256sum over each sorted list

Identifier Set:
  131 distinct identifiers over 2798 occurrences in 212 versioned files.
  Main-form identifiers above B9.81 present in the corpus: B9.82 (7
  occurrences), B9.83 (13), B9.84 (2). Every one of those occurrences lies
  inside this document, as the section 8 illustration or as rejection
  evidence recorded in the section 14/15/16/17 candidate lists. Zero files
  outside this document contain B9.82, B9.83 or B9.84, so none of them is an
  allocation, a reservation or a proposal. The highest identifier in real
  use outside this document is B9.81.

Highest Verified Main Block:
  B9.81 — allocated in section 17 (0a23708), implemented at ef9f9b9,
  verified and closed at ef452b2 (17.9).

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration

Candidate Numbers Considered:
  B9.82 — SELECTED (highest verified + 1); its pre-existing occurrences are
    the section 8 illustration (line 320) and the section 14/15/16/17
    rejection lists (lines 570, 1010, 1533, 1830, 1861, 1880), none of which
    is an allocation
  B9.83, B9.84 — rejected: illustrative examples in section 8 and
    time-anchored rejection evidence in this document; no allocation and no
    reservation exists for either
  B9.80.1, B9.80.2, B9.80.3 and every other sub-block — rejected: sub-blocks
    do not raise the main-block floor (section 8)
  Historical gaps (B9.25-B9.28, B9.32-B9.34, B9.38, B9.49, B9.60-B9.65,
    B9.68-B9.73, B9.75, and every other main number below B9.81 that is not
    allocated by sections 14-17) — rejected: historical gaps, not reusable
    under section 9
  B9.85 and above — rejected: no occurrence of any such identifier exists
    in the corpus; never considered

Selected Number:
  B9.82

Validity Reason:
  B9.81 is the highest verified allocated main block at ef452b2: allocated in
  section 17, implemented at ef9f9b9, verified and closed at ef452b2 (17.9).
  No allocated main identifier above B9.81 exists: B9.82-B9.84 occur only as
  section 8 illustration and as rejection evidence inside this document, and
  no versioned file outside this document contains them. Sub-blocks never
  raise the main floor (section 8) and historical gaps are not reusable
  (section 9). The next main block is therefore B9.82.
```

### 18.1 Register entry for B9.82

```text
Block ID:                 B9.82
Name:                     Discovery-to-Acquisition Boundary
Status:                   DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED
Origin:                   this document, section 18
Scope:                    see 18.2
Non-goals:                see 18.3
Dependencies:             see 18.4
Architectural Decisions:  see 18.5
Current State:            CLOSED — implemented, independently verified and
                           formally closed; authoritative closure record in 18.9
Acceptance Criteria:      AC1-AC22 — see 18.6; all PASS, recorded in 18.9
Evidence:                 see 18.4, the prior READ-ONLY B9.82 allocation and
                          NAR decision audits, and 18.9
Evidence Type:            DOC
NAR Decision Reference:   READ-ONLY NAR decision audit preceding this
                          allocation: O1 = B (identity resolver injected and
                          required), O2 = C (revision not transported),
                          O3 = future artifact-domain block, O4 =
                          AcquisitionMappingError(Exception); recorded in 18.5
Implementation Commit:    14adcb5fe5dfbd8474b5606fbed688d65866ed2e
                          ("feat: implement B9.82 discovery acquisition boundary")
Verification Result:      B9.82 VERIFIED — READ-ONLY audit against the
                          implementation commit; see 18.9
Closure Commit:           recorded by the commit that introduces the closure
                          record in 18.9
                          ("docs: close roadmap block B9.82")
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 18
Retrospective Record:     NO — prospective allocation record
```

### 18.2 Scope

B9.82 introduces an explicit, pure discovery-to-acquisition boundary: it
converts the declared L1 output of B9.80/B9.81 into the existing acquisition
domain type, without performing, planning, persisting or verifying anything.

```text
ModelDiscovery (B9.80)
        ↓
DiscoveredArtifact / ModelVariant (B9.80)
        ↓
B9.82 acquisition mapper        <- introduced here; pure, no I/O
        ↓
ArtifactSpec (existing, unchanged)
        ↓
DownloadPlanner (existing, reused, unchanged)
        ↓
DownloadPlan (existing, unchanged)
```

The mapper may perform:

```text
- pure translation of one DiscoveredArtifact into one ArtifactSpec, 1:1,
  preserving input order;
- declared-metadata preservation (quantization, size, SHA-256, download
  locator) as DECLARED values, never as verified ones;
- explicit rejection of artifacts whose identity the caller-supplied
  resolver cannot supply;
- translation of mapping failures into AcquisitionMappingError.
```

The mapper MUST NOT acquire, plan, download, persist or verify anything.

### 18.3 Non-goals

```text
1.  modifying castlearq/discovery.py;                 2. modifying
    HuggingFaceDiscoveryProvider;                     3. modifying
    ModelSource;                                      4. modifying
    HuggingFaceSource;                                5. migrating the CLI;
    6. modifying main.py;                             7. modifying
    model_identity.py;                                8. modifying
    DownloadPlanner;                                  9. modifying the
    Downloader;                                      10. modifying
    ModelStore;                                      11. modifying manifests;
    12. modifying manifest_migration;                 13. modifying
    ArtifactSpec;                                    14. introducing an
    AcquisitionPlan;                                 15. changing the
    resolve/main download URL contract;              16. transporting
    revision into ArtifactSpec;                      17. wiring the mapper
    into production;                                 18. catalog; 19. ranking;
    20. recommendations;                             21. fuzzy matching;
    22. GUI;                                         23. admission; 24.
    execution;                                       25. evaluation; 26.
    runtime evidence;                                27. refactoring
    HuggingFaceSource into a shared abstraction.
```

B9.82 is a **pure translation boundary**, not a migration of the existing
system. The legacy `ModelSource.discover_artifacts -> list[ArtifactSpec]` path
and its CLI consumers remain untouched; deprecating them is a separate block.

### 18.4 Dependencies and evidence

```text
B9.80 — ModelDiscovery, ModelCandidate, ModelVariant, DiscoveredArtifact and
        DiscoveryError; CLOSED and unchanged; B9.82 implements nothing in the
        domain and never edits it
B9.81 — HuggingFaceDiscoveryProvider, sibling of HuggingFaceSource; CLOSED
        and unchanged; B9.82 consumes its declared output and never imports
        the provider module
ArtifactSpec / ArtifactState (castlearq/models.py) — existing acquisition
        domain type, reused unchanged. It has no revision field and no runtime
        invariant (no __post_init__); model_id is a required positional str
        used as a path component by ModelStore._safe_model_id; sha256 is
        already documented as an integrity DECLARATION, distinct from the
        computed content_id (B9.67)
DownloadPlanner / DownloadPlan — existing, reused, never reimplemented. Its
        _validate_metadata already enforces source, repository, filename,
        format, the resolve/main URL shape, size and SHA-256, so B9.82 must
        not duplicate that validation
model_identity — never imported by B9.82; identity arrives as input
```

Dependency direction (recorded):

```text
castlearq.discovery
        ↓  (types only)
B9.82 acquisition mapper
        ↓
castlearq.models (ArtifactSpec)
        ↓
castlearq.downloads.planner (existing, unchanged)
```

Rejected edges, unchanged from sections 16 and 17:

```text
discovery → ArtifactSpec
discovery → DownloadPlanner
discovery → Downloader
discovery → ModelStore
discovery → model_identity
discovery → admission
discovery → execution
```

The mapper imports `castlearq.discovery` (types) and `castlearq.models`
(`ArtifactSpec`, `ArtifactState`) only. It must import nothing from
`castlearq.downloads.*`, `castlearq.model_store`, `castlearq.sources.*` or
`castlearq.model_identity`: importing `castlearq.downloads` or
`castlearq.sources` today pulls ModelStore and the Hugging Face source into
the import closure, which is exactly what the mapper must avoid.

### 18.5 Architectural decisions (recorded)

Recorded from the READ-ONLY NAR decision audit that preceded this allocation.

```text
Decision 1 — identity: injected, required resolver (audit option O1 = B).
  identity_resolver is a REQUIRED keyword-only callable with no default.
  The mapper never imports model_identity and never calls logical_model_id()
  on its own account. It never fabricates an identity: neither model_id=None
  nor model_id="Unknown" is ever produced. If the resolver returns None or an
  unsafe identity, the mapping fails explicitly with AcquisitionMappingError.
  This mirrors the existing injectable model_id_provider of
  HuggingFaceSource and the importing.py precedent, where the caller supplies
  identity. Identity resolution is therefore a policy of the caller, not a
  hidden gate inside discovery and not a hidden gate inside the mapper.

Decision 2 — revision: not transported (audit option O2 = C).
  DiscoveredArtifact.revision remains declared discovery metadata (B9.81) but
  is NOT carried into ArtifactSpec by B9.82, and ArtifactSpec is not extended.
  Evidence: revision has zero consumers in production and tests; it does not
  participate in artifact_id, in the model store layout, in manifests or in
  integrity, which is content-hash based (the downloader verifies
  artifact.sha256 and the store recomputes the digest to derive
  VERIFIED/FAILED). A revision-pinned URL would additionally be rejected by
  the existing planner URL contract (resolve/main), which section 17.5
  decision C forbids changing. The discard is explicit and recorded, never a
  silent loss.

Decision 3 — revision ownership (audit option O3).
  Revision-aware acquisition belongs to a FUTURE artifact-domain block, not to
  B9.82. Such a block would have to change a shared domain type, the manifest
  read/write path and the download URL contract as one coherent change. No
  B9.8x identifier is allocated here for it.

Decision 4 — error boundary (audit option O4).
  AcquisitionMappingError, inheriting directly from Exception, is the single
  public error of the discovery-to-acquisition boundary, following the
  existing per-boundary pattern (DiscoveryError, SourceError,
  ArtifactSelectionError). It is raised only for declared boundary data
  conditions, chiefly an identity the resolver cannot supply. It does NOT
  replace DiscoveryError or SourceError, and neither is imported or raised by
  B9.82. Programming errors remain TypeError/ValueError.
```

Mapper contract (recorded):

```text
map_discovered_artifacts(artifacts, *, identity_resolver) -> tuple[ArtifactSpec, ...]

  Input:   ModelVariant or an iterable of DiscoveredArtifact (B9.80 types),
           plus the required identity_resolver
  Output:  a 1:1 tuple of ArtifactSpec in input order:
             model_id      <- identity_resolver(...)
             source        <- source
             repository    <- repository
             filename      <- filename
             format        <- format
             quantization  <- declared_quantization   (renamed, value kept)
             download_url  <- download_url            (declared locator)
             size_bytes    <- declared_size           (renamed, value kept)
             sha256        <- declared_sha256         (declaration, not proof)
             state         <- ArtifactState.NOT_DOWNLOADED
             content_id    <- None                    (computed later, B9.67)
  Identity: input, never computed; never fabricated
  Revision: not transported; the discard is documented at the boundary
  Metadata: declared semantics preserved; no verified_*, no computed hash,
            no URL access, no remote existence check, no filesystem access
  Errors:   TypeError/ValueError for programming errors; AcquisitionMappingError
            for boundary data conditions; partial metadata (absent
            size/sha/url) is not an error and is represented as None
  Purity:   no network, no filesystem, no download, no persistence, no
            logging, no clock, no global state; deterministic
  Imports:  castlearq.discovery and castlearq.models only
```

L1 trust boundary: the mapper translates declared remote metadata into the
acquisition domain. It never produces verified content, computed digests,
content identity, local paths, admission verdicts, execution verdicts or
evaluation verdicts.

### 18.6 Acceptance criteria

Contractual criteria, all PENDING at allocation time (not satisfied by this
allocation task; only a later implementation can satisfy them):

```text
AC1  A pure mapper DiscoveredArtifact -> ArtifactSpec exists.
AC2  The mapping is 1:1 and order-preserving, and deterministic.
AC3  identity_resolver is required; there is no default identity source.
AC4  The module never imports castlearq.model_identity.
AC5  A missing or unsafe identity raises AcquisitionMappingError.
AC6  No identity is ever fabricated: neither None nor "Unknown".
AC7  revision never appears in the mapper output.
AC8  The revision discard is documented at the boundary.
AC9  Declared metadata is preserved exactly, without value changes.
AC10 Every produced ArtifactSpec has state == NOT_DOWNLOADED.
AC11 Every produced ArtifactSpec has content_id is None.
AC12 Absent size, SHA-256 or download URL are represented as None, not as
     errors and not as invented values.
AC13 No verified_* field, claim or verdict is produced.
AC14 No network access occurs.
AC15 No filesystem access occurs.
AC16 No persistence occurs.
AC17 No import of downloads.*, model_store, sources.* or model_identity.
AC18 The planner's validations are not duplicated by the mapper.
AC19 Future integration with DownloadPlanner is verifiable without
     reimplementing the planner.
AC20 discovery.py, sources/*, models.py, model_store.py and downloads/*
     remain unmodified by the implementation commit.
AC21 The complete repository test suite remains green.
AC22 git diff --check is clean for the implementation commit.
```

### 18.7 Implementation surface

Chosen location, recorded at allocation; no files are created by this task:

```text
castlearq/acquisition_mapping.py
    pure discovery-to-acquisition mapper; imports castlearq.discovery and
    castlearq.models only; no downloads.*, model_store, sources.* or
    model_identity; no network, filesystem or persistence

tests/test_b982_acquisition_mapping.py
    mapper-specific tests covering at minimum: 1:1 order-preserving mapping;
    determinism; required identity_resolver; no model_identity import;
    AcquisitionMappingError on absent/unsafe identity; never fabricating
    identity; revision absent from output and its discard documented;
    declared-metadata preservation; state NOT_DOWNLOADED; content_id None;
    partial metadata as None; absence of verified_*; no network; no
    filesystem; no persistence; dependency-direction isolation; and
    verifiable integration with the existing DownloadPlanner
```

Both files are planned surface only. This allocation creates neither.

### 18.8 Verification and closure expectations

```text
Verification: COMPLETED — the READ-ONLY verification audit required by this
  section was performed against the B9.82 implementation commit and evaluated
  AC1-AC22; the result is recorded in 18.9. This allocation section performed
  no verification of its own.

Closure: COMPLETED — AC1-AC22 all PASS and the standard closure record is
  18.9. B9.82 is CLOSED.
```

B9.82 is a completed block: the discovery-to-acquisition mapper and its tests
exist, as recorded in §18.9. No catalog, CLI, or model-library functionality
was introduced by this block. B9.78, B9.79, B9.80 and B9.81 are not modified
by this record.

### 18.9 Verification and closure record

READ-ONLY verification audit of the implementation commit
`14adcb5fe5dfbd8474b5606fbed688d65866ed2e`
("feat: implement B9.82 discovery acquisition boundary").

```text
Verification Result:
  B9.82 VERIFIED

Implementation Commit (verified contents — immutable, never rewritten):
  14adcb5fe5dfbd8474b5606fbed688d65866ed2e

Committed Files (exclusively; exactly two new files):
  castlearq/acquisition_mapping.py          (new, 175 lines)
  tests/test_b982_acquisition_mapping.py    (new, 586 lines)

Verification Scope (established against production behavior, not merely
against the presence of tests):
  - map_discovered_artifacts(artifacts, *, identity_resolver) is the only
    entry point; identity_resolver is keyword-only, has no default, and is
    the sole source of model_id (AC1, AC3)
  - the mapping is 1:1, order-preserving and deterministic (AC2)
  - the module imports castlearq.discovery and castlearq.models only; a fresh
    interpreter that loads it pulls exactly castlearq, castlearq.discovery,
    castlearq.models and castlearq.acquisition_mapping; no downloads.*,
    model_store, sources.* or model_identity is reachable (AC4, AC17)
  - a missing, non-string or unsafe identity raises AcquisitionMappingError;
    ".", "..", absolute paths, ".." segments, non-strings and None are all
    rejected, and no identity is ever fabricated (AC5, AC6)
  - revision is not transported: ArtifactSpec has no revision field, the
    declared value is absent from the output, resolve/main is unchanged, and
    the discard is documented at the boundary (AC7, AC8)
  - declared quantization, size, SHA-256, locator and provenance are preserved
    exactly; state is NOT_DOWNLOADED, content_id is None, absent metadata stays
    None, and no verified_* field or claim is produced (AC9-AC13)
  - a real mapping triggered no external effect: socket, builtins.open,
    pathlib writers, urllib, ModelStore entry points and DownloadPlanner were
    all intercepted and none was called (AC14-AC17)
  - the planner's validations are not duplicated and the planner is never
    executed, while the produced ArtifactSpec is accepted by the real
    DownloadPlanner; "compatible with the planner" and "executes the planner"
    were verified as separate facts (AC18, AC19)
  - discovery.py, sources/*, models.py, model_store.py and downloads/* are
    unmodified by the implementation commit (AC20)

Test Sensitivity:
  14 of 14 meaningful in-memory mutations were detected by the B9.82 suite:
  identity fallback, unsafe identity accepted, computed content_id, promoted
  state, hardcoded quantization, size invented from absent metadata, reversed
  order, TypeError converted into AcquisitionMappingError, memoized resolver,
  ignored resolver, dropped sha256, fabricated download URL.

Regression Result:
  1977 passed / 2672 subtests passed / 0 failed / 0 errors
  (B9.82 tests: 56 passed; pre-existing tests: 1921 passed)
  ruff check on both new files: all checks passed
  git diff --check: clean

Acceptance Criteria:
  AC1-AC22 all PASS.
```

B9.82 is **CLOSED**. No B9.82.x sub-block is assigned, no new identifier is
allocated here, and B9.78, B9.79, B9.80 and B9.81 are not modified by this
record. The highest verified main block is now B9.82; any next main assignment
is computed by the section 6 and section 7 procedure and is deliberately not
made in this record. The implementation commit above is the verified artifact
and remains immutable; this closure record only attests that the verified
implementation has been formally closed.

---

## 19. B9.83 — Number Allocation Record

`B9.83` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.83 is **an allocation only**: no
implementation, verification, or closure is claimed by this section.

The scope was selected by a READ-ONLY NAR decision audit and a human
architectural decision record that preceded this allocation, in the same form
recorded for B9.82 in §18.5. The decision does not modify B9.82: that block's
implementation commit remains immutable, and the revision-discard behaviour
closed in §18.9 is preserved as historical evidence.

```text
Assigned Number:
  B9.83

Title:
  Revision-Aware Acquisition

Allocation Date:
  2026-10-02

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash,
  per the two-step mechanism already stated in section 11 for the numbering
  policy activation anchor. A commit hash cannot be known before the commit
  exists and writing a guessed value would be a fabricated identifier.

Corpus/HEAD Anchor:
  3cd9f3ac48c275c713c7abcc94854e9640a24059
  (docs(castlearq): add project attribution; main == HEAD, working tree
  clean, 0 ahead / 0 behind origin/main)

Corpus File Count:
  214 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  git rev-parse HEAD -> 3cd9f3ac48c275c713c7abcc94854e9640a24059
  git tree object at HEAD -> 486d14c0adf7634f88ed39fd0c5904458d6ead75
  sorted path list SHA-256 ->
    40a84021be0e067694dedc54127a722be2f25e031d634d84004aea900af2148e
  identifier-set SHA-256 ->
    106ac7edf92c98e7742be3666a94e1121fe632c607b9f1dc1137042167540240
  mechanism: git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
    | LC_ALL=C sort [-u]; sha256sum over each sorted list

Identifier Set:
  132 distinct identifiers over 2893 occurrences in 214 versioned files.
  B9.83 — 20 occurrences, every one of them inside this document: the
  section 8 illustration (line 321), the section 14/15/16/17 candidate
  rejection lists, the section 16/17 illustrative-reference notes, and the
  section 18 rejection evidence. Classification at this anchor: illustrative
  example, rejected candidate, or historical reference. None of them is an
  allocation, a reservation, a proposal, a provisional assignment, or an
  implementation/test label. Zero occurrences exist in castlearq/, tests/,
  config/, .github/, README.md, pyproject.toml, requirements.txt, LICENSE, or
  any other versioned file outside this document.
  B9.84 — 2 occurrences, both inside this document; rejected. B9.85 and
  above — no occurrence anywhere in the corpus.
  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3 — illustrative
  only, per the section 8 rule.
  The highest identifier in real use outside this document is B9.81.
  Conflict inspection: only main and origin/main exist as branches; the tags
  v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
  no commit outside this document's history introduces a B9.83 allocation.
  No competing, competing-pending or conflicting identifier was found.


Highest Verified Main Block:
  B9.82 — allocated in section 18 (a3f4d3e), implemented at 14adcb5,
  verified and closed at ef9e57f (18.9); published on origin/main.

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a
  READ-ONLY NAR decision audit and a human architectural decision record

Candidate Numbers Considered:
  B9.83 — SELECTED. highest_verified_main_block + 1 = B9.82 + 1 = B9.83.
    No actual allocation, reservation, provisional allocation or competing
    higher main identifier exists for it
  B9.84 — rejected: not highest_verified + 1; selecting it would skip the
    required next main identifier and create a gap contrary to section 6. No
    allocation or reservation exists for it
  B9.85 and above — rejected: no occurrence of any such identifier exists in
    the corpus; never considered
  B9.80.1, B9.80.2, B9.80.3, B9.81.x, B9.82.x and every other sub-block —
    rejected: sub-blocks do not raise the main-block floor and do not consume
    B9.83 (section 8). B9.80, B9.81 and B9.82 each record that no sub-block is
    assigned
  Historical gaps (B9.25-B9.28, B9.32-B9.34, B9.38, B9.49, B9.60-B9.65,
    B9.68-B9.73, B9.75, and every other main number below B9.82 that is not
    allocated by sections 14-18) — rejected: historical gaps, not reusable
    under section 9 (NOT REUSED, prospective declaration). No gap is claimed
    abandoned, freed, reserved or erroneous (section 13)

Selected Number:
  B9.83

Validity Reason:
  B9.82 is the highest verified allocated main block at 3cd9f3a: allocated in
  section 18, implemented at 14adcb5, verified and closed at ef9e57f (18.9),
  and published on origin/main. A fresh section 7 corpus inspection at this
  anchor found no allocated main identifier above B9.82: B9.83 and B9.84
  occur only inside this document as the section 8 illustration and as
  recorded rejection evidence, and no versioned file outside this document
  contains them. No branch, tag or commit outside this document's history
  establishes an allocation. Sub-blocks never raise the main floor (section 8)
  and historical gaps are not reusable (section 9). The next main block is
  therefore B9.83.
```

### 19.1 Register entry for B9.83

```text
Block ID:                 B9.83
Name:                     Revision-Aware Acquisition
Status:                   DOCUMENTED, ALLOCATED, IMPLEMENTED, VERIFIED, CLOSED
Origin:                   this document, section 19
Scope:                    see 19.2
Non-goals:                see 19.3
Dependencies:             see 19.4
Architectural decision:   see 19.5
Current State:            CLOSED — implemented, independently verified and
                           formally closed; authoritative closure record in 19.8
Acceptance Criteria:      AC1-AC14 — see 19.6; all PASS, recorded in 19.8
Evidence:                 see 19.4, the READ-ONLY B9.83 allocation audit and
                          the preceding decision audit, 19.5, and 19.8
Evidence Type:            DOC
Decision Reference:       READ-ONLY NAR decision audit and human
                          architectural decision record preceding this
                          allocation: SELECT A — Revision-aware acquisition
Implementation Commit:    76d9c993af26e1a755c57b4771eb0cc0aa15e44a
                          ("feat: implement B9.83 revision-aware acquisition")
Verification Result:      B9.83 VERIFIED — READ-ONLY audit against the
                          implementation commit; see 19.8
Closure Commit:           recorded by the commit that introduces the closure
                          record in 19.8
                          ("docs: close roadmap block B9.83")
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 19
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none — OD-1 settled in 19.7
```


### 19.2 Scope

B9.83 establishes revision-aware acquisition: the revision already declared by
B9.81 is preserved and transported by the acquisition domain instead of being
discarded at the B9.82 mapping boundary. It is a coherent change across the
three acquisition contracts named by §18.5 Decision 3:

```text
DiscoveredArtifact.revision (B9.80 / B9.81, declared)
        ↓
B9.82 acquisition mapper (boundary; the discard happens here today)
        ↓
ArtifactSpec (shared artifact domain type)          <- change 1
        ↓
manifest read/write path (ModelStore)               <- change 2
        ↓
download URL contract (DownloadPlanner)             <- change 3
```

The normative basis is §18.5 Decision 3, quoted verbatim:

> Revision-aware acquisition belongs to a FUTURE artifact-domain block, not to
> B9.82. Such a block would have to change a shared domain type, the manifest
> read/write path and the download URL contract as one coherent change.

B9.83 is that block. The three changes are **one coherent change**; a partial
implementation does not satisfy this scope.

Revision is *declared remote metadata*. A revision is an immutable reference
(B9.81 validates it as a 40-hexadecimal commit reference), never verified
content, never a content identity and never a verified quantization claim.
This preserves the L1 trust boundary recorded in §17.5 Decision E and
restated in §18.5.

### 19.3 Non-goals

```text
1.  production wiring of the B9.82 mapper into the CLI, the API or any
    production path;                      2. legacy ModelSource deprecation,
    removal or migration;                 3. model library, catalog,
    marketplace or search UX;             4. GUI;                  5. any new
    discovery provider;                   6. modifying the B9.80 domain
    types;                                7. modifying the B9.81
    HuggingFaceDiscoveryProvider;         8. runtime execution;     9.
    evaluation;                          10. admission;           11.
    unrelated CLI work;                  12. ModelStore redesign;
    13. unrelated migration work, including manifest_migration;
    14. changing B9.82 retroactively;    15. introducing a new
    acquisition type duplicating DownloadPlan;  16. resolving the B9.78
    open human decisions (section 14.8);  17. any claim of verified content,
    content identity or verified quantization derived from a revision.
```

Production integration is expressly **not** part of this block. §18.3 records
that the legacy `ModelSource.discover_artifacts -> list[ArtifactSpec]` path and
its CLI consumers remain untouched and that *"deprecating them is a separate
block"*; that separate block is neither named nor numbered here.


### 19.4 Dependencies and evidence

```text
B9.80 — ModelDiscovery, ModelCandidate, ModelVariant, DiscoveredArtifact and
        DiscoveryError; CLOSED and unchanged. B9.83 changes nothing in the
        discovery domain and never edits it
B9.81 — HuggingFaceDiscoveryProvider; CLOSED and unchanged. It already
        produces the declared revision and already queries the remote tree at
        that revision, so the metadata B9.83 must transport already exists
B9.82 — map_discovered_artifacts; CLOSED and unchanged. It currently discards
        revision as a recorded decision (18.5 Decision 2). B9.83 supersedes
        that boundary behaviour forward, never by rewriting B9.82
ArtifactSpec / ArtifactState (castlearq/models.py) — the shared artifact
        domain type; to be extended. Its artifact_id and content_id semantics
        are preserved subject to the open question in 19.7
ModelStore — the single manifest read/write path; the persisted revision must
        round-trip through it without disturbing the B9.41 rule that state and
        verified are derived, never persisted as authority
DownloadPlanner — the existing download URL contract and its validated
        Hugging Face security constraints; they are respected, not weakened
        and not duplicated
B9.67 — content identity boundary remains separate; integrity remains
        content-hash based
B9.40/B9.41/B9.74 — acquisition, derived-state and store-resolution behaviour
        remain unchanged and are reused, never reimplemented
```

Dependency direction (recorded):

```text
B9.80  ModelDiscovery
B9.81  HuggingFaceDiscoveryProvider
B9.82  acquisition mapper
B9.83  revision-aware acquisition      <- this block
          ↓
future   production integration of the B9.80 -> B9.81 -> B9.82 chain
          ↓
future   stored artifact -> B9.79 runtime evidence
```

This is a **dependency order recorded by the repository**, not a priority
claim. The register contains no priority, ranking or ordering rule (section
13: the document *"does not assign any B9 identifier by itself"*). B9.83 is
next because section 6 fixes the number and a human architectural decision
selected the scope; no statement is made here that B9.83 is the most
important or most preferred work.

Prior READ-ONLY audits: the complete B9.80/B9.81/B9.82 discovery-to-acquisition
chain, the single-repository HuggingFaceSource flow, the plan->download->
verify->store->resolve pipeline, the manifest read/write path, the `resolve/main`
URL contract and the absence of any production caller for the B9.82 mapper were
all verified present at the corpus anchor. They are recorded here as evidence;
this record re-verifies no implementation.

### 19.5 Architectural decision (recorded)

Recorded from the READ-ONLY NAR decision audit and the human architectural
decision record that preceded this allocation.

```text
Decision A (SELECTED) — revision-aware acquisition.
  The revision discovered and declared by B9.81 is preserved by the
  acquisition domain rather than discarded at the B9.82 boundary, as one
  coherent change across the shared domain type, the manifest read/write
  path and the download URL contract. This is the scope §18.5 Decision 3
  named; the decision records it and does not extend it.

Decision B (NOT SELECTED, DEFERRED) — production integration of the
  B9.80 -> B9.81 -> B9.82 chain into the existing production download flow.
  This remains a future architectural step. The production flow still uses
  the legacy ModelSource path (B9.40 registration, planner, downloader and
  store), and B9.82 expressly deferred wiring its mapper. It is deferred
  until the acquisition-domain contract can represent the required revision
  semantics coherently. Deferred is not rejected: the repository records it
  as "a separate block" and no terminal judgement is made.

Not selected: ModelStore redesign; standalone CLI acquisition work; Hugging
  Face model-library or catalog UX; GUI; legacy deprecation as an isolated
  block; CI/lint work; and the B9.78 open human decisions. None of these is
  implied, decided or resolved by this record.
```


### 19.6 Acceptance criteria

Contractual criteria, all **PENDING** at allocation time. They are **not**
satisfied by this allocation; only a later implementation can satisfy them,
exactly as recorded for B9.78, B9.79, B9.80, B9.81 and B9.82.

```text
AC1  ArtifactSpec can represent the declared revision B9.81 produces,
     without changing the B9.80 discovery domain types.
AC2  A missing or absent revision remains representable as such and is
     never fabricated, defaulted or invented.
AC3  Revision survives the manifest write -> read round-trip through the
     existing ModelStore read/write path.
AC4  The B9.41 rule is preserved: state and verified remain derived and are
     never persisted as authority by the revision change.
AC5  The download URL contract can respect a declared revision instead of
     implicitly hard-coding resolve/main.
AC6  The existing validated Hugging Face URL security constraints remain
     intact: HTTPS scheme, huggingface.co host, no credentials, no port,
     and the repository/filename correspondence.
AC7  Existing artifacts and manifests that carry no revision remain
     readable and behave exactly as before.
AC8  Existing identity semantics (artifact_id, content_id) are preserved,
     subject to the open architectural decision recorded in 19.7.
AC9  Revision drift is never silently accepted: a mismatch between the
     declared revision and the acquired content is detected or refused.
AC10 A declared revision is never treated as verified content, a content
     identity, or a verified quantization claim (L1 trust boundary).
AC11 The B9.82 revision-discard contract tests are deliberately superseded
     or replaced with a recorded rationale, never silently deleted.
AC12 The B9.80, B9.81 and B9.82 verified implementations remain untouched
     in their verified parts.
AC13 No discovery, admission, execution or evaluation dependency is
     introduced: discovery never gains a dependency on the store, planner,
     downloader, model_identity, admission, execution or evaluation.
AC14 The complete repository test suite remains green and git diff --check
     is clean for the implementation commit.
```

### 19.7 Human architectural decision (recorded)

OD-1 was opened by this record as an open question. It has since been settled
by a **human architectural decision**, preceded by a READ-ONLY OD-1
inspection. The decision below is a human decision and **not** an inference
drawn from implementation, and it decides only the identity question: it
confers no implementation authorization.

```text
OD-1  Does `revision` participate in `ArtifactSpec.artifact_id`?

      Decision Status: DECIDED
      Human Decision:  OPTION B

Decision:
  `revision` does NOT participate in `ArtifactSpec.artifact_id`.
```

#### 19.7.1 Decision rationale (recorded)

```text
Identity stability.
  `artifact_id` remains the existing provenance-derived identity for
  downloaded/catalog artifacts, computed from source, repository, filename
  and quantization exactly as it is today. `content_id` continues to
  short-circuit `artifact_id` for imported, content-derived artifacts, as
  B9.67 established. `revision` enters neither identity calculation.

B9.67 compatibility.
  Option B preserves the existing invariant that the provenance-derived
  identity of downloaded/catalog artifacts remains unchanged and that
  existing stores remain valid. B9.67 is not extended, weakened or
  reinterpreted by this decision: B9.67 did not decide the B9.83 revision
  question, and this decision preserves rather than reopens it.

Storage compatibility.
  Keeping `revision` outside `artifact_id` prevents a revision field from
  changing the directory identity of existing downloaded artifacts.
  B9.83 therefore does not require artifact-directory migration.

Manifest compatibility.
  `revision` may be persisted independently as declared metadata while
  `artifact_id` remains derived under the existing identity contract.
  Existing manifests that carry no revision must remain readable, with an
  absent revision represented as absent and never invented.

Trust boundary.
  revision            != content_id
  revision            != verified content
  revision            != integrity proof
  `revision` remains declared remote provenance metadata. Content integrity
  continues to depend on content hashing and on verification performed over
  the acquired bytes. A declared revision is never an integrity proof.
```

#### 19.7.2 The four identity concepts, kept separate

```text
artifact_id  = addressing identity (content-derived when `content_id` is
               present; otherwise provenance-derived from
               source|repository|filename|quantization)
revision     = declared remote provenance pointer (optional; L1; untrusted)
content_id   = digest CastleArq computed itself from observed bytes
verified     = derived verification outcome (inspect_manifest recomputes the
               digest and compares)
```

A Hugging Face revision is a 40-hexadecimal upstream repository commit
reference. It is **not** the SHA-256 of the GGUF file and is never treated as
one. No concept above may be substituted for another.

#### 19.7.3 Recorded consequence — multi-revision limitation

This consequence is **not** hidden and is recorded as a known limitation of
Option B.

```text
With the current ModelStore design, two downloaded artifacts having the same
`source`, `repository`, `filename` and `quantization` but different revisions
still resolve to the same `artifact_id` and therefore to the same storage
directory.
```

Consequences, recorded without scope expansion:

```text
1. B9.83 does NOT introduce simultaneous multi-revision storage.
2. A later revision can replace the stored artifact for the same identity
   slot.
3. This does NOT mean B9.83 is required to redesign ModelStore; that remains
   an explicit non-goal (19.3 item 12).
4. Multi-revision coexistence is a separate future architectural question.
   No identifier is allocated for it here, no new block is opened, and
   B9.83's scope is not expanded to cover it.
```

#### 19.7.4 Alternatives considered and not selected

Kept factual. Neither alternative is characterized as bad or incorrect; each
is simply **not selected under the current CastleArq constraints and the
B9.83 scope as allocated**.

```text
Option A — `revision` participates in `artifact_id`. NOT SELECTED.
  It would:
  1. change the existing provenance-derived `artifact_id` for revision-less
     downloaded artifacts;
  2. alter existing ModelStore directory identity;
  3. make existing stored artifacts inaccessible through the current
     artifact-id addressing path, including execution preflight, download
     inspection and cleanup;
  4. cause old manifests to recompute an identity that no longer matches
     their containing directory;
  5. imply artifact identity migration and/or ModelStore changes;
  6. conflict with B9.83's current non-goals concerning migration and
     ModelStore redesign (19.3 items 12 and 13);
  7. conflict with the B9.67 requirement to preserve existing
     downloaded-artifact identity and keep existing stores valid.

Option C — `revision` participates only when present. NOT SELECTED.
  It would make artifact identity depend on whether the discovery source
  happened to supply revision metadata:

    revision absent  -> legacy identity
    revision present -> a different identity

  Identity semantics would then depend on metadata availability rather than
  solely on the established artifact identity contract. Not implemented and
  not allocated here.
```

#### 19.7.5 Effect on the acceptance criteria

No acceptance criterion in 19.6 is satisfied, removed or altered by this
decision. All remain **PENDING**. The decision only removes the ambiguity
that AC8 previously deferred:

```text
AC8  Existing identity semantics (artifact_id, content_id) are preserved,
     subject to the open architectural decision recorded in 19.7.
```

AC8's dependency on an open question is now settled: `revision` does not
participate in `artifact_id`. The future implementation must still establish,
and this decision proves nothing about, every one of the following:

```text
- revision representation on the artifact domain type;
- an absent revision remains representable, and is never fabricated;
- manifest write/read round-trip for the declared revision;
- revision-aware download URL handling within the existing security
  constraints;
- preservation of the existing identity semantics decided above;
- that `revision` does not participate in `artifact_id`;
- that no revision is ever invented or defaulted;
- that no artifact, directory or manifest is migrated;
- that content verification is never conflated with a declared revision;
- that the B9.82 revision-discard tests are deliberately superseded or
  replaced with a recorded rationale, never silently deleted.
```

B9.82 is untouched by this decision. Its scope, implementation, closure,
commit references and tests remain immutable historical evidence; its
revision-discard behaviour is superseded **prospectively** by B9.83.

B9.83 allocation plus this decision define the identifier, the scope and the
identity contract only. The implementation that followed does not reopen any
of them: it realizes the scope exactly as allocated and preserves OD-1
unchanged.

```text
IMPLEMENTATION AUTHORIZED: NO
```

The line above records the state of the *allocation and decision* record
itself: neither of them authorized implementation, and neither may be read as
doing so. Implementation was performed in a separate controlled step, whose
authorization came from the operator and not from this record.

The verification audit and the formal closure that followed are recorded in
19.8; the decision text above is unchanged by either.

---

### 19.8 Verification and closure record

A READ-ONLY verification audit was performed against the implementation commit
`76d9c993af26e1a755c57b4771eb0cc0aa15e44a`
("feat: implement B9.83 revision-aware acquisition"). The audit modified no
file, created no commit and pushed nothing.

```text
Verification Result:
  B9.83 VERIFIED

Implementation Commit (verified contents — immutable, never rewritten):
  76d9c993af26e1a755c57b4771eb0cc0aa15e44a
  "feat: implement B9.83 revision-aware acquisition"

Committed Files (exclusively; exactly eight, all within allocated scope):
  castlearq/models.py                              (+17 / -0)
  castlearq/acquisition_mapping.py                 (+15 / -7)
  castlearq/sources/huggingface.py                 (+36 / -4)
  castlearq/downloads/planner.py                   (+24 / -3)
  castlearq/model_store.py                         (+18 / -0)
  tests/test_b983_revision_aware_acquisition.py    (new, 278 lines)
  tests/test_b982_acquisition_mapping.py           (+63 / -20)
  docs/roadmap-register-and-numbering-policy.md    (+522 / -0)

OD-1 Compliance (human architectural decision, verified against the
implementation and not re-derived from it):
  - `revision` does NOT participate in `ArtifactSpec.artifact_id`. The
    artifact_id property body is byte-identical to the pre-B9.83 baseline;
    the models.py change is purely the added field and its comment.
  - Behavioral identity verification, not dataclass equality: five distinct
    revisions (None, 40-hex x2, "main", "deadbeef") yield exactly one
    artifact_id; the digest is still
    sha256(source|repository|filename|quantization).
  - The content_id short-circuit is unchanged and stable under any revision.
  - No conditional identity formula and no second artifact identity exist;
    the property contains one digest and one content_id return.
  - OD-1 was not rewritten, reopened or replaced by the implementation. It
    remains a human architectural decision recorded in 19.7.

Domain Semantics (four concepts kept separate):
  artifact_id = addressing identity
  revision    = declared remote provenance pointer
  content_id  = digest CastleArq computed from observed bytes
  verified    = derived outcome of inspect_manifest recomputation
  A revision is never content identity, never a verified claim, and never
  the SHA-256 of the downloaded GGUF. state was observed to remain
  NOT_DOWNLOADED and sha256 remained the declared value.

Revision Transport (acquisition mapping boundary):
  - A present DiscoveredArtifact.revision is transported verbatim.
  - An absent revision stays None; it is never fabricated and never
    defaulted to "main".
  - Revision is never converted into content_id or sha256.
  - The mapper remains an explicit boundary adapter: its import closure
    still reaches castlearq, castlearq.discovery, castlearq.models and
    castlearq.acquisition_mapping only.
  - The B9.82 mapper remains NOT production-wired: no production module
    imports it.

Download URL Contract (constructor/validator separation preserved):
  - Declared revision -> https://huggingface.co/<repo>/resolve/<rev>/<file>
  - No declared revision -> the unchanged /resolve/main/ form
  - Mismatch rejection was verified in all three directions: revision R with
    a main URL, revision R with a revision-S URL, and a declared-absent
    artifact carrying a revision-pinned URL are all BLOCKED. No stale or
    mismatched locator is silently accepted.
  - Construction, preservation and validation remain three distinct
    responsibilities: _download_url builds, the B9.82 mapper preserves the
    declared locator verbatim, and the planner validates correspondence.
  - 13 of 14 adversarial URLs were BLOCKED (http, evil host, localhost,
    embedded credentials, explicit port, query, fragment, ../ traversal,
    percent-encoded traversal, file://, wrong repository, wrong filename).
  - 17 of 18 malformed revisions were rejected at construction, including
    empty, dot segments, separators, whitespace padding, over-length and
    percent-encoded forms.

Manifest Contract (write, read, round-trip, legacy compatibility):
  - A declared revision is written and read back exactly.
  - An absent revision is persisted as null and reads back as None.
  - A manifest written before B9.83, with no revision key, remains readable
    and reconstructs revision = None.
  - artifact_id is unchanged by the round trip.
  - state and verified remain derived and are never persisted (B9.41).

ModelStore Invariants:
  - _artifact_directory, artifact directory naming and addressing were not
    modified; only the manifest payload and its reader changed.
  - No second storage identity, no revision index, and no migration were
    introduced. manifest_migration.py is untouched.
  - The documented multi-revision limitation recorded in 19.7.3 remains
    true by design.

B9.82 Supersession (prospective, not retroactive):
  - RevisionDiscardTests was reworked in place as RevisionTransportTests; the
    five assertions that encoded the discard contract were replaced, not
    silently deleted, and the supersession is documented in the test
    docstring, the mapper docstring and the mapper inline comment.
  - The B9.82 closure record, scope, implementation commit and commit
    references remain intact and unmodified.

Regression Result:
  1998 passed / 2672 subtests passed / 0 failed / 0 errors
  (B9.83 targeted tests: 19 passed;
   B9.82 acquisition mapping tests: 58 passed;
   B9.82 purity/isolation tests: 8 passed)
  git diff --check: exit 0, clean

Static Quality (comparison against the pre-B9.83 baseline):
  ruff check castlearq/ : 239 errors before, 239 after — delta 0
  mypy  castlearq/     : 29 errors in 14 files before, 29 after — delta 0
  ruff on the new B9.83 test file: all checks passed
  B9.83 introduced no new lint or type issue. No pre-existing lint or type
  error was fixed, and none is claimed to have been fixed.

Acceptance Criteria:
  AC1-AC14 all PASS.

Provenance Note (recorded fact, not a defect):
  The section 19 allocation record and the OD-1 decision were present as
  uncommitted roadmap changes when the implementation commit was created, so
  that single commit carries the allocation record, the OD-1 decision, the
  implementation state and the implementation itself. History is not
  rewritten and no corrective commit was created to separate them. The
  substantive content of each record was verified intact in the committed
  tree; only their co-commitment is noted here.

Non-blocking Observations (neither is a B9.83 defect; neither was fixed,
and neither reopens B9.83):
  1. An uppercase host such as https://HUGGINGFACE.CO/... is accepted,
     because hostname comparison is case-insensitive. This behaviour is
     identical in the pre-B9.83 baseline and is not a B9.83 regression.
  2. revision="-main" is accepted as a single safe path segment. It is
     permissive but produces no path traversal and no host escape.
```

B9.83 is **CLOSED**. No B9.83.x sub-block is assigned, no new identifier is
allocated here, and B9.78, B9.79, B9.80, B9.81 and B9.82 are not modified by
this record. The highest verified main block is now B9.83; any next main
assignment is computed by the section 6 and section 7 procedure and is
deliberately not made in this record. The implementation commit above is the
verified artifact and remains immutable; this closure record only attests that
the verified implementation has been formally closed.

The multi-revision limitation recorded in 19.7.3 remains an intentional
consequence of the OD-1 decision and was deliberately not redesigned here.
Multi-revision coexistence stays a separate future architectural question with
no identifier allocated.
