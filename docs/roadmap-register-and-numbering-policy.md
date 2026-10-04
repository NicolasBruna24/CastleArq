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
---

## 20. B9.84 — Human Architectural Decision Record

**This section is a human architectural decision record only.** It allocates no
identifier, implements nothing, modifies no production code and no test, and
authorizes no implementation work. It is deliberately **not** a §11 Number
Allocation Record: under the §6/§7 procedure a `B9.84` assignment requires a
recorded corpus inspection at allocation time, and that inspection has not been
performed. Consequently `B9.84` is, at the moment of this record, an
**unallocated candidate identifier** carrying a recorded human decision and a
recorded scope. Nothing here may be cited as an allocated B9 identifier, and no
B9.85 is created.

> **CROSS-REFERENCE (added by the section 21 Number Allocation Record).** The
> paragraph above states the position **as of this section alone**. The §7 corpus
> inspection was subsequently performed and `B9.84` is **ALLOCATED** by §21,
> which cites this section as its authoritative decision record. This section's
> eight decisions, its scope (20.3) and its non-goals (20.4) are unchanged by
> §21; only the allocation status asserted in this paragraph is superseded
> prospectively by §21. No other line of §20 is altered.

Context (recorded, not re-verified here): the discovery/acquisition foundation
is complete — B9.80 (discovery domain) and B9.81 (Hugging Face discovery
provider) are **CLOSED**, and B9.82 (acquisition mapper) is a closed, pure 1:1
translator that has no production caller. The gap recorded by the READ-ONLY
decision matrix is the missing **discovery-domain selection contract** between
that foundation and a future product/library surface. B9.84 is that contract.
It is explicitly **not** the Model Library UX itself.

The eight decisions below are **human architectural decisions**. They are not
inferences drawn from implementation, they were not derived by the repository,
and they decide only what this record states.

### 20.1 The eight recorded human decisions (D1–D8)

#### D1 — Selection input domain

```text
Decision:  A — `ModelVariant[]`
Status:    DECIDED (human architectural decision)

Rationale (recorded):
  - preserves the B9.80/B9.81 model -> variant -> artifact hierarchy;
  - consumes the grouping already established by B9.81;
  - avoids re-deriving quantization grouping from a flat `DiscoveredArtifact[]`;
  - naturally supports variants containing multiple artifacts, including
    sharded artifacts;
  - is directly compatible with the B9.82 mapper's accepted `ModelVariant`
    input.

Constraint:
  No new selection type is introduced.
```

#### D2 — Selection boundary

```text
Decision:  A — selection occurs upstream of B9.82
Status:    DECIDED (human architectural decision)

Required flow (recorded, normative):
  Discovery -> Selection -> B9.82 Mapping -> Acquisition

Rationale (recorded):
  - B9.84 chooses;
#### D4 — Existing selector relationship

```text
Decision:  B — create a separate discovery-domain selection contract
Status:    DECIDED (human architectural decision)

Rationale (recorded):
  - existing callers depend on the current `ArtifactSpec` semantics of
    `select_artifact()`;
  - discovery uses `declared_quantization`, while the legacy selector uses
    acquisition-domain fields;
  - changing the existing selector would unnecessarily reopen a closed
    production contract.

Constraint:
  `select_artifact()` is not refactored into a shared abstraction as part of
  B9.84.
```

#### D5 — Identity responsibility

```text
Decision:  B — identity remains the responsibility of the B9.82 caller
Status:    DECIDED (human architectural decision)

Rationale (recorded):
  B9.84 must not resolve or fabricate `model_id`.

B9.82 Decision 1 preserved (recorded):
  - selection operates on discovery data;
  - the caller of B9.82 supplies the identity resolver;
  - B9.82 remains responsible for injecting/resolving identity at its existing
    boundary.

Constraint:
  No model-identity coupling is added to B9.84.
```

#### D6 — Cardinality

```text
Decision:  A — exactly one result or explicit failure
Status:    DECIDED (human architectural decision)

Normative behaviour (recorded):
  - exactly one match   -> return that artifact;
  - zero matches       -> explicit failure;
  - more than one match -> explicit ambiguity failure.

Constraint:
  No ranking, scoring, fuzzy matching, recommendation, or incidental-order
  selection is introduced.
```

#### D7 — Error ownership

```text
Decision:  A — dedicated selection-boundary error
Status:    DECIDED (human architectural decision)

Rationale (recorded):
  - `ArtifactSelectionError` belongs to the existing acquisition-domain
    selector;
  - `DiscoveryError` represents discovery/provider failures;
  - B9.84 is a distinct discovery-domain selection boundary and owns its own
    selection failures.

Constraint:
  B9.84 reuses neither `ArtifactSelectionError` nor `DiscoveryError`. The future
  error symbol is named by a future implementation under the repository's
### 20.2 Architectural invariants (immutable for B9.84)

```text
 1. B9.80 remains closed.
 2. B9.81 remains closed.
 3. B9.82 remains a pure 1:1 mapper and does not choose.
 4. B9.83 remains closed.
 5. `revision` remains excluded from `artifact_id`.
 6. B9.84 performs no network access.
 7. B9.84 performs no persistence or filesystem access.
 8. B9.84 performs no identity resolution.
 9. B9.84 performs no ranking/recommendation/fuzzy matching.
10. B9.84 does not implement Model Library UX.
11. B9.84 does not wire the production acquisition pipeline.
12. B9.84 does not redesign ModelStore.
13. The existing `select_artifact()` behavior remains unchanged.
```

### 20.3 Formal scope (recorded)

> **B9.84 — Discovery-Domain Deterministic Artifact Selection**
>
> Define a pure discovery-domain selection contract that accepts the
> already-discovered `ModelVariant[]` domain and deterministic explicit
> selection criteria, producing exactly one `DiscoveredArtifact` or an
> explicit selection-boundary failure. The contract operates upstream of
> B9.82, preserves B9.82 identity responsibility, supports revision as an
> explicit criterion without changing artifact identity, and leaves the
> existing acquisition-domain selector untouched.

### 20.4 Non-goals (recorded)

```text
 - Model Library UI
 - model catalog/search redesign
 - Hugging Face provider redesign
 - discovery protocol redesign
 - ranking
 - scoring
 - recommendations
 - fuzzy matching
 - automatic "best" artifact selection
 - production CLI/API wiring
 - ModelSource deprecation/removal
 - ModelStore redesign
 - multi-revision storage redesign
 - runtime/evaluation/admission
 - fine-tuning/LoRA/QLoRA
 - B9.82 mapper redesign
 - B9.83 revision redesign
 - changes to the existing `select_artifact()` behavior
```

### 20.5 Effect on closed records

```text
  - B9.80, B9.81, B9.82 and B9.83 allocation records, scopes, implementation
    commits, closures and tests are untouched by this record.
  - B9.83 OD-1 (19.7) is not rewritten, reopened or replaced.
  - Sections 14 through 19 of this register are not modified.
  - No acceptance criterion of any earlier block is satisfied, removed or
    altered here.
```

### 20.6 Authorization state (recorded)

```text
IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
ALLOCATION RECORDED:        NO (no section 11 NAR is created by this record)
B9.85 CREATED:              NO
PUSHES PERFORMED:           0
```

> **CROSS-REFERENCE (added by the section 21 Number Allocation Record).** The
> `ALLOCATION RECORDED` line above describes **this section's own state only**:
> §20 created no NAR. The allocation was subsequently recorded in §21, which
> allocates `B9.84` on the evidence of the §7 corpus inspection and cites this
> section as its decision record. Every other line above — including
> `IMPLEMENTATION AUTHORIZED: NO`, `TESTS AUTHORIZED: NO`, `B9.85 CREATED: NO`
> and `PUSHES PERFORMED: 0` — remains true and is repeated in §21.7. No other
> line of §20 is altered.

This line records the state of the decision record itself. The eight decisions
above, the scope in 20.3 and the non-goals in 20.4 define an intent and its
boundaries. Any later allocation, implementation, verification or closure is a
separate controlled step, authorized by the operator and not by this record.

---
  naming conventions; no error type is implemented by this record, and no
  symbol name is fabricated here.
```

#### D8 — Empty candidate set

```text
Decision:  A — explicit selection error
Status:    DECIDED (human architectural decision)

Normative behaviour (recorded):
  An empty candidate collection is an explicit B9.84 selection failure and
  must remain distinguishable from:
  - a non-empty candidate set with no matching criteria;
  - an ambiguous match;
  - malformed/inconsistent candidate data.

Constraint:
  An empty collection is never silently interpreted as success, as `None`, or
  as a generic discovery failure.
```
  - B9.82 remains a pure 1:1 translator;
  - B9.82 must not receive multiple alternatives merely to have them discarded
    later.

Constraint:
  Selection is NOT moved after mapping.
```

#### D3 — Revision selection

```text
Decision:  A — revision is a first-class selection criterion
Status:    DECIDED (human architectural decision)

Meaning (recorded):
  Revision may be used to express which discovered revision the caller intends
  to acquire.

Invariants explicitly preserved:
  - revision is not content identity;
  - revision is not `artifact_id`;
  - revision is not verified content;
  - B9.83 OD-1 (19.7) remains immutable;
  - selecting a revision does not alter artifact identity or storage identity.

Constraint:
  No revision-aware storage and no multi-revision coexistence is introduced in
  B9.84. The multi-revision limitation recorded in 19.7.3 is unchanged.
```
## 21. B9.84 — Number Allocation Record

`B9.84` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.84 is **an allocation only**: no
implementation, no verification and no closure is claimed by this section.

The scope is **not chosen by this record**. It was fixed beforehand by the human
architectural decision record in §20 and is reproduced here verbatim. This
section allocates the number that carries that scope; it does not widen,
reinterpret or extend it.

```text
Assigned Number:
  B9.84

Title:
  Discovery-Domain Deterministic Artifact Selection

Allocation Date:
  2026-10-02

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash, per
  the two-step mechanism already stated in section 11 for the numbering policy
  activation anchor. A commit hash cannot be known before the commit exists and
  writing a guessed value would be a fabricated identifier.

Corpus/HEAD Anchor:
  3a4c4a5bbd31863e48a4b52614d07292a42dc2ae
  (main == HEAD == origin/main, working tree carrying only the section 20 human
  architectural decision record, 0 ahead / 0 behind origin/main)

Corpus File Count:
  215 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  git rev-parse HEAD -> 3a4c4a5bbd31863e48a4b52614d07292a42dc2ae
  git tree object at HEAD -> e390e4e0931febeb3a46c7e73a56f0bc56817bef
  sorted path list SHA-256 ->
    d993f49106e1e77be83da6832df1495263306438addffd62b67d763f64aa5ea4
  identifier-set SHA-256 ->
    106ac7edf92c98e7742be3666a94e1121fe632c607b9f1dc1137042167540240
  mechanism: git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
    | LC_ALL=C sort [-u]; sha256sum over each sorted list

Identifier Set:
  132 distinct identifiers over 3121 occurrences in 215 versioned files.
  Highest main identifier in real use: B9.83 (section 19, CLOSED).
  B9.84 — 30 occurrences, every one of them inside this document:
    the section 14-19 candidate rejection lists (lines 1863, 2260, 2285, 2303,
    2746, 2775, 2797), the section 20 human architectural decision record, and
    nothing else. `git ls-files -z | xargs -0 grep -ln 'B9\.84'` returns exactly
    one path: this document. Zero occurrences exist in castlearq/, tests/,
    config/, .github/, README.md, pyproject.toml, requirements.txt, LICENSE or
    any other versioned file outside this document.
  Classification at this anchor: illustrative example, rejected candidate,
  historical reference, or section 20 decision record. Before section 21 no
  occurrence was an allocation, a reservation, a proposal, a provisional
  assignment or an implementation/test label.
  B9.85 — 5 occurrences, all inside this document (lines 2294, 2746, 2778, 3367,
    3553), each an explicit rejection or a negative assertion. No allocation,
  reservation or proposal exists for it. B9.86 and above — no occurrence
  anywhere in the corpus.
  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3 — illustrative only,
  per the section 8 rule.
  Conflict inspection: only main and origin/main exist as branches; the tags
  v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations; no
  commit outside this document's history introduces a B9.84 allocation. No
  competing, competing-pending or conflicting identifier was found.

Highest Verified Main Block:
  B9.83 — allocated in section 19, implemented at 76d9c99, verified and closed
  in 19.8; published on origin/main.

Rule in Force:
  Prospective monotonic main numbering (section 6)

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
  decision matrix and the human architectural decision record in section 20

Candidate Numbers Considered:
  B9.84 — SELECTED. highest_verified_main_block + 1 = B9.83 + 1 = B9.84. No
    allocation, reservation, provisional allocation or competing higher main
    identifier exists for it
  B9.85 — rejected: no occurrence of any such identifier exists in the corpus
    outside recorded rejections inside this document; never considered
  B9.86 and above — rejected: no occurrence anywhere in the corpus; never
    considered
  B9.83.1 and every other sub-block — rejected: sub-blocks do not raise the
    main-block floor and do not consume B9.84 (section 8). B9.80, B9.81, B9.82
  and B9.83 each record that no sub-block is assigned
  B9.78 through B9.83 — rejected: already allocated by sections 14-19; not
    reusable under section 9
  Historical gaps (B9.25-B9.28, B9.32-B9.34, B9.38, B9.49, B9.60-B9.65,
    B9.68-B9.73, B9.75, and every other main number below B9.84 that is not
    allocated by sections 14-19) — rejected: historical gaps, not reusable under
    section 9 (NOT REUSED, prospective declaration). No gap is claimed
    abandoned, freed, reserved or erroneous (section 13)

Selected Number:
  B9.84

Validity Reason:
### 21.1 Register entry for B9.84

```text
Block ID:                 B9.84
Name:                     Discovery-Domain Deterministic Artifact Selection
Status:                   DOCUMENTED, ALLOCATED
Origin:                   this document, section 21
Scope:                    see 21.2 (normative: section 20.3)
Non-goals:                see 21.3 (normative: section 20.4)
Dependencies:             see 21.4
Architectural decision:   see 20.1 (D1-D8) — precedes this allocation
Current State:            ALLOCATED — no implementation, no verification, no
                          closure. Implementation is NOT AUTHORIZED by this
                          record; see 21.7
Acceptance Criteria:      not established by this allocation; to be recorded by
                          a later controlled step, as for sections 14-19
Evidence:                 the section 7 corpus inspection above, the READ-ONLY
                          decision matrix, and the section 20 human
                          architectural decision record
Decision Reference:       section 20 — human architectural decision record,
                          D1-D8, recorded before this allocation
Implementation Commit:    NONE — no implementation exists
Verification Result:      NOT VERIFIED — no implementation to verify
Closure Commit:           NONE — B9.84 is not closed
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 21
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none — D1-D8 all DECIDED in 20.1
```
  B9.83 is the highest verified allocated main block at 3a4c4a5: allocated in
  section 19, implemented at 76d9c99, verified and closed in 19.8, and published
### 21.2 Scope (allocated)

The scope is the one recorded in §20.3, reproduced verbatim. It is quoted here
and is not restated, broadened or reinterpreted:

> **B9.84 — Discovery-Domain Deterministic Artifact Selection**
>
> Define a pure discovery-domain selection contract that accepts the
> already-discovered `ModelVariant[]` domain and deterministic explicit
> selection criteria, producing exactly one `DiscoveredArtifact` or an
> explicit selection-boundary failure. The contract operates upstream of
> B9.82, preserves B9.82 identity responsibility, supports revision as an
> explicit criterion without changing artifact identity, and leaves the
> existing acquisition-domain selector untouched.

The contract this scope names:

```text
B9.80  ModelDiscovery / ModelVariant / DiscoveredArtifact   (CLOSED, untouched)
B9.81  HuggingFaceDiscoveryProvider                          (CLOSED, untouched)
          ↓
B9.84  discovery-domain deterministic selection             <- this block
          ↓
B9.82  map_discovered_artifacts — pure 1:1 translator        (CLOSED, untouched)
          ↓
       ArtifactSpec -> acquisition infrastructure             (existing, unwired)
```

### 21.3 Allocated boundary

These constraints are normative for B9.84. They are the D1-D8 decisions of
§20.1 restated as the boundary of this allocation; where the two texts differ,
§20.1 is the human decision and governs.

```text
 1. Input domain: `ModelVariant[]`.
 2. Selection occurs upstream of B9.82
    (Discovery -> Selection -> B9.82 Mapping -> Acquisition).
 3. Revision is a first-class selection criterion.
 4. Revision remains distinct from `artifact_id`, content identity and
    verification; B9.83 OD-1 (19.7) is immutable.
 5. The existing `select_artifact()` remains untouched.
 6. Identity remains the responsibility of the B9.82 caller; B9.84 neither
    resolves nor fabricates `model_id`.
 7. Successful selection produces exactly one `DiscoveredArtifact`.
 8. Zero matches and ambiguous matches are explicit failures.
 9. Empty candidate input is an explicit selection error.
10. B9.84 owns a dedicated selection-boundary error; it reuses neither
    `ArtifactSelectionError` nor `DiscoveryError`.
11. No network access.
12. No persistence or filesystem access.
13. No ranking, scoring, recommendation or fuzzy matching.
14. No Model Library UX.
15. No production wiring.
16. No ModelStore redesign.
17. No B9.82 redesign.
18. No B9.83 redesign.
```

### 21.4 Dependencies and evidence

```text
B9.80 — ModelDiscovery, ModelVariant, DiscoveredArtifact, DiscoveryError;
        CLOSED. B9.84 consumes its domain types and changes none of them
B9.81 — HuggingFaceDiscoveryProvider; CLOSED. It already produces the declared
        revision and already groups artifacts into variants; B9.84 consumes
        that grouping and changes none of it
B9.82 — map_discovered_artifacts; CLOSED and unchanged. It remains a pure 1:1
        translator that does not choose; B9.84 never hands it multiple
        alternatives for later discarding, and never redesigns it
B9.83 — revision-aware acquisition; CLOSED. OD-1 (19.7) is preserved verbatim;
### 21.5 Non-goals

Recorded identically to §20.4. B9.84 does not:

```text
 - Model Library UI
 - model catalog/search redesign
 - Hugging Face provider redesign
 - discovery protocol redesign
 - ranking
 - scoring
 - recommendations
 - fuzzy matching
 - automatic "best" artifact selection
 - production CLI/API wiring
 - ModelSource deprecation/removal
 - ModelStore redesign
 - multi-revision storage redesign
 - runtime/evaluation/admission
 - fine-tuning/LoRA/QLoRA
 - B9.82 mapper redesign
 - B9.83 revision redesign
 - changes to the existing `select_artifact()` behavior
```

### 21.6 Explicitly excluded deferrals

Each item below was explicitly deferred or expressly excluded by an earlier
block. B9.84 does **not** absorb any of them. They remain separate future work
with no identifier allocated by this record:

```text
 - Model Library UX. Section 17.3 non-goal 19 and section 19.3 non-goal 3
   exclude it; section 17.3 states the block "must NOT become the model
   library". B9.84 explicitly does not implement it.
 - Production pipeline wiring. Section 18.3 records that the legacy
   ModelSource.discover_artifacts -> list[ArtifactSpec] path and its CLI
   consumers remain untouched and that deprecating them "is a separate block";
   section 19.3 non-goal 1 excludes wiring the B9.82 mapper into any production
   path. That separate block is neither named nor numbered here.
 - ModelSource deprecation / removal / migration. Section 19.3 non-goal 2. Not
   absorbed.
 - ModelStore redesign. Section 19.3 non-goal 12 and the multi-revision
   limitation in 19.7.3. Not absorbed.
 - Multi-revision storage coexistence. Section 19.7.3 records it as "a separate
   future architectural question" with no identifier allocated. B9.84 supports
   revision as a *selection criterion* only and introduces no storage change.
 - Runtime, evaluation and admission. Section 19.3 non-goals 8, 9, 10; the
   B9.79 runtime evidence boundary is untouched.
 - Ranking, recommendation and fuzzy matching. Section 17.3 non-goals 14, 15, 16
   and section 20 D6. Not absorbed.
 - Provider redesign. Section 19.3 non-goal 5 (any new discovery provider) and
   section 17.3 (the B9.81 HuggingFaceDiscoveryProvider itself). Not absorbed.
```

### 21.7 Implementation authorization

```text
IMPLEMENTATION AUTHORIZED: NO
```

This is stated explicitly because the question must not be left to inference:

> Allocation of B9.84 does not by itself authorize implementation unless the
> repository's roadmap policy defines allocation as implementation authorization.

The roadmap policy does not define allocation as implementation authorization.
Sections 14 through 19 record the same: each states that the block is "an
allocation only" and that implementation, verification and closure are separate
controlled steps whose authorization comes from the operator. The same
discipline is applied to B9.84. The allocation in this section confers no
implementation authority, and the section 20 decision record conferred none
either.

```text
IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
VERIFICATION AUTHORIZED:    NO
CLOSURE AUTHORIZED:         NO
B9.85 CREATED:              NO
PUSHES PERFORMED:           0
```

Implementation may begin only when the allocation has been reviewed and the next
controlled implementation step is explicitly initiated by the operator. Nothing
in this section anticipates, requests or substitutes for that initiation.

---
        `revision` still does not participate in `artifact_id`, and the
        multi-revision limitation recorded in 19.7.3 is unchanged
artifact_selection.py — the existing acquisition-domain selector. Its
        `select_artifact()` contract and its `ArtifactSelectionError` are
        untouched by B9.84 and are not refactored into a shared abstraction
section 20 — the human architectural decision record that precedes and
        authoritatively fixes this scope
```

Prerequisite check (recorded): all four architectural prerequisites above —
B9.80, B9.81, B9.82 and B9.83 — are closed and published. The section 20 human
architectural decision record is present and complete: D1-D8 are all recorded as
DECIDED, with scope in 20.3 and non-goals in 20.4. B9.84 therefore has no unmet
prerequisite, and this allocation re-verifies no implementation.
  on origin/main. A fresh section 7 corpus inspection at this anchor found no
  allocated main identifier above B9.83: B9.84 occurs only inside this document
  (section 8 illustration, section 14-19 rejection evidence, and the section 20
  decision record) and in no other versioned file, while B9.85 occurs only as a
  recorded rejection. No branch, tag or commit outside this document's history
  establishes an allocation. Sub-blocks never raise the main floor (section 8)
  and historical gaps are not reusable (section 9). The next main block is
  therefore B9.84.
```
---

## 22. B9.84 — Closure Record

### 22.1 Closure status

B9.84 is formally **CLOSED**. The decision record (section 20) and the
allocation record (section 21) precede this record and are unchanged by it. This
section attests that the verified implementation exists, was published, and
matches the allocated scope exactly.

### 22.2 Implementation identity

```text
Implementation commit:
  cb69c854c771121ea05c3abd8b15ba7cdd25a755
Commit message:
  feat: implement B9.84 discovery-domain artifact selection
Branch:
  main
Publication state:
  pushed to origin/main (HEAD == origin/main at closure time)
Parent commit:
  3a4c4a5bbd31863e48a4b52614d07292a42dc2ae
```

Committed files, exclusively, and both new:

```text
A  castlearq/discovery_selection.py        (+316 / -0)
A  tests/test_b984_discovery_selection.py  (+597 / -0)
```

The implementation commit contains no roadmap change. The section 20/21/22
records remain a separate, still-uncommitted documentation change at the moment
this section is authored, exactly as recorded in 21.1.

### 22.3 Implemented scope

B9.84 implemented the scope allocated in 21.2, which reproduces the scope
recorded in 20.3: **Discovery-domain deterministic artifact selection**. The
implemented contract:

- consumes `ModelVariant` candidates and selects from existing
  `DiscoveredArtifact` objects, without reconstructing or regrouping them;
- supports explicit quantization, filename, and revision criteria;
- combines those criteria with logical AND;
- returns exactly one artifact when uniquely matched, returning the original
  discovered object rather than a derived copy;
- raises an explicit selection-boundary error (`DiscoveredSelectionError`) for
  empty candidates, no match, ambiguity, or invalid selector, keeping those
  four conditions distinguishable;
- does not perform ranking, scoring, fuzzy matching, recommendation, or
  implicit ordering, and never selects a first, last, best or latest match;
- does not resolve or fabricate model identity: no identity resolver is
  accepted, and `model_id` is never read, resolved, fabricated or mutated;
- remains upstream of B9.82, which continues to receive exactly one already
  selected artifact;
- leaves the existing acquisition-domain `select_artifact()` untouched.

### 22.4 Verification evidence

Re-verified against the published implementation commit:

```text
Targeted B9.84 tests:   42 passed  (tests/test_b984_discovery_selection.py)
Regression suite:      200 passed  (artifact_selection, b974 store selection,
                                    selection, B9.80, B9.81, B9.82, B9.83)
Full suite:           2040 passed
Full-suite subtests:  2699 passed
Failures:                   0
Errors:                     0
Skipped:                    0
Ruff on the two new files:  clean ("All checks passed")
Repository Ruff delta:     0 (castlearq/ reports 239 errors before and after,
                             the pre-B9.83 baseline recorded in 19.8)
mypy on the new module:     clean ("Success: no issues found in 1 source file")
git diff --check:          clean (exit 0)
```

Protected files were confirmed untouched by the implementation commit:

```text
castlearq/discovery.py, castlearq/sources/huggingface_discovery.py,
castlearq/acquisition_mapping.py, castlearq/artifact_selection.py,
castlearq/models.py, castlearq/model_store.py, castlearq/__init__.py,
castlearq/main.py, castlearq/resolver.py, castlearq/selection.py
  -> none appear in cb69c854c771121ea05c3abd8b15ba7cdd25a755
```

### 22.5 Boundary compliance

The following were intentionally **not** implemented and remain separate future
work with no identifier allocated by this record:

```text
 - Model Library UX / catalog / search redesign
 - production wiring (CLI, API, or any production path)
 - Hugging Face provider redesign
 - discovery-domain type redesign (B9.80 untouched)
 - B9.82 mapper redesign
 - B9.83 revision-aware acquisition redesign
 - ModelStore redesign
 - multi-revision storage coexistence
 - legacy select_artifact() refactor or shared-abstract extraction
 - ranking / scoring / fuzzy matching / recommendation
 - runtime, evaluation and admission changes
 - GUI
 - fine-tuning / LoRA / QLoRA
 - unrelated CLI/API expansion
```

### 22.6 Compatibility

B9.80, B9.81, B9.82 and B9.83 remain intact and their contracts are unaltered by
B9.84. B9.84 is additive: it consumes the B9.80 domain types, consumes the
grouping and declared revision already produced by B9.81, sits strictly
upstream of the B9.82 mapper, and preserves the B9.83 OD-1 identity decision
(`revision` still does not participate in `artifact_id`, and an absent revision
is still never invented or defaulted). The human architectural decisions D1-D8
recorded in 20.1 were realized exactly as decided and were not reopened,
reinterpreted or amended by the implementation.

### 22.7 Repository state

```text
Implementation commit published successfully:  YES
HEAD == origin/main:                           YES
  both cb69c854c771121ea05c3abd8b15ba7cdd25a755
Implementation files remaining modified:       none
Modification present at closure-record authoring time:
  docs/roadmap-register-and-numbering-policy.md (this document)
```

The implementation commit is the verified artifact and remains immutable; it is
never rewritten or amended. This closure record only attests that it has been
formally closed. No B9.85 or any other identifier is created here.

### 22.8 Closure authorization

```text
B9.84 STATUS: CLOSED
B9.84 IMPLEMENTATION: COMPLETE
B9.84 VERIFICATION: COMPLETE
B9.84 PUBLICATION: COMPLETE
B9.84 CLOSURE: COMPLETE
```
---

## 23. B9.85 — Number Allocation Record

`B9.85` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.85 is **an allocation only**: no
implementation, no verification and no closure is claimed by this section.

The scope was **not chosen by this record**. It was fixed beforehand by a
Human Architectural Decision Record that the project owner approved, preceded by
a READ-ONLY roadmap allocation audit and a READ-ONLY Human Architectural
Decision Audit. This section allocates the number that carries that scope; it
does not widen, reinterpret or extend it.

```text
Assigned Number:
  B9.85

Title:
  Application Acquisition Boundary + cmd_download Integration

Allocation Date:
  2026-10-02

Allocation Commit:
  9bd1f016b14c3d30f0bb255a90adb94c67e3617e
    ("docs: allocate roadmap block B9.85")

  Recorded by the two-step mechanism already stated in section 11 for the
  numbering policy activation anchor and used identically by sections 19 and 21:
  at authoring time the hash did not exist and the field read "PENDING — fixed by
  the next controlled commit that sets it to that hash"; a commit hash cannot be
  known before the commit exists, and writing a guessed value would be a
  fabricated identifier. The value above is the actual hash of that commit,
  obtained from Git after the fact. The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 22 — B9.84 Closure Record
Section for this allocation:
  section 23 — this record

Corpus/HEAD Anchor:
  5a40421d188b8dc4dd4fb3669c6aea831c6b1f54
  ("docs: close roadmap block B9.84"; main == HEAD == origin/main, working tree
  clean)

Tree object at anchor:
  64644233cee6631983661e9b8a1de9574a409f5e

Branch:
  main

Working tree at anchor:
  clean (no staged, modified or untracked files)

Corpus File Count:
  217 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  sorted path list SHA-256 ->
    731ae96f8979dac69ff840815992adcf36628734e66f222f086b5438b0410e6d
  identifier-set SHA-256 ->
    f269adb2c3142666ff3485f699f669406444de2fd25ed0636b2a09c30274c3a6
  identifier set: 134 distinct identifiers over 3271 occurrences in 217
    versioned files
  mechanism: git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
    | LC_ALL=C sort [-u]; sha256sum over each sorted list

Identifier Set:
  Highest main identifier in real use: B9.84 (section 21 NAR, section 22
  closure; implementation commit cb69c854c771121ea05c3abd8b15ba7cdd25a755,
  which is an ancestor of origin/main).
  B9.85 — 12 occurrences before this record, every one of them a negative or
    rejected reference inside this document: lines 2294, 2746, 2778, 3367,
    3561, 3570, 3690, 3719, 3921, 3947 and 4089 (2294/2746/2778/3690/3719/
    3947 are recorded candidate rejections; 3367/3561/3570/3921/4089 are
    explicit negative assertions such as "B9.85 CREATED: NO").
    `git ls-files -z | xargs -0 grep -ln 'B9\.85'` returned exactly one path:
    this document. Zero occurrences existed in castlearq/, tests/, config/,
    README.md, pyproject.toml or any other versioned file.
    Classification at this anchor: rejected candidate or negative assertion.
    None was an allocation, reservation, proposal, provisional assignment or
    implementation/test label.
  B9.86 and above — 2 occurrences, both recorded rejections (lines 3692 and
    3721). No allocation or reservation exists for any of them.
  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3 — illustrative only,
    per the section 8 rule. No B9.85.x sub-block is assigned.
  Conflict inspection: only main and origin/main exist as branches; the tags
    v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
    no commit outside this document's history introduces a B9.85 allocation.
    No competing, competing-pending or conflicting identifier was found.

Preceding Block:
  B9.84 — Discovery-Domain Deterministic Artifact Selection

Preceding Block Status:
  ALLOCATED (section 21), IMPLEMENTED (cb69c85), CLOSED (section 22),
  published on origin/main

Highest Verified Allocation:
  B9.84

Rule in Force:
  Prospective monotonic main numbering (section 6)

Allocation Rule Applied:
  highest_verified_allocated_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
### 23.1 Register entry for B9.85

```text
Block ID:                 B9.85
Name:                     Application Acquisition Boundary + cmd_download Integration
Status:                   CLOSED
Origin:                   this document, sections 23 (NAR) and 24 (Closure Record)
Scope:                    see 23.2 — approved by the ADR
Non-goals:                see 23.3
Architectural decision:   approved Human Architectural Decision Record
                          (D1-D8 all APPROVED), preceding this allocation
Current State:            CLOSED — allocated by section 23, implemented at
                          f2540dd022d1a3eb4ef2470265c25ac93d04a41f, verified
                          PASS, closed by section 24
Implementation Commit:    f2540dd022d1a3eb4ef2470265c25ac93d04a41f
                          ("feat: implement B9.85 application acquisition boundary")
Allocation Commit:       9bd1f016b14c3d30f0bb255a90adb94c67e3617e
                          ("docs: allocate roadmap block B9.85")
Verification Result:      PASS — see section 24.4
Closure Commit:           PENDING — fixed by the next controlled commit that sets
                          it to that hash, per the two-step mechanism stated in
                          section 11 and used identically by sections 19, 21 and
                          23. A commit hash cannot be known before the commit
                          exists, and writing a guessed value would be a
                          fabricated identifier.
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 23
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none — D1-D8 all APPROVED
```

### 23.2 Scope attached to this allocation

The scope was fixed by the approved ADR and is recorded here without
reinterpretation.

```text
Application Acquisition Boundary
+
Real production integration through cmd_download
```

**Included:**

```text
 1. application acquisition service;
 2. dependency injection;
 3. discovery orchestration;
 4. deterministic discovery selection;
 5. acquisition mapping;
 6. identity resolver supply;
 7. application-level error semantics;
 8. dedicated application acquisition result;
 9. integration into cmd_download;
10. tests required for the new application contract;
11. CLI regression preservation.
```

The approved architectural decisions carried by this allocation, recorded here
for traceability and not restated as a re-decision:

```text
D1 = A — one block: application boundary + production wiring
D2 = A — service class with injected collaborators
D3 = A — resolver backed by logical_model_id
D4 = A — application-level error category + preserved causes
D5 = A — ModelSource coexistence
D6 = B — main.py cmd_download as first production caller
D7 = B — dedicated application acquisition result
D8 = approved application-boundary + cmd_download scope
```

### 23.3 Non-goals

```text
 - Model Library
 - Model Library GUI
 - Model Library UX
 - catalog / search UX
 - ranking
 - recommendations
 - fuzzy matching
 - multi-revision storage redesign
 - B9.80 redesign
### 23.4 Dependencies and preserved contracts

B9.85 **composes** the following closed contracts; it does not redesign any of
them.

```text
B9.80 — discovery domain; consumed as-is, no field/type/port change, identity
        stays out of L1 data
B9.81 — Hugging Face discovery provider; used as the injected discovery
        provider, its variant grouping and declared revision consumed as-is
B9.82 — acquisition mapping + caller-supplied
        IdentityResolver = Callable[[str], str | None]; signature unchanged
B9.83 — revision-aware ArtifactSpec/acquisition; DiscoveredArtifact is passed
        through unmodified, revision reaches ArtifactSpec exactly as B9.83
        specifies, and OD-1 remains immutable
B9.84 — deterministic discovery-domain selection; called once by the boundary
        upstream of B9.82, its four failure categories remain distinguishable,
        and the legacy select_artifact() is not refactored into a shared
        abstraction
```

Architectural invariants carried by this allocation:

```text
 1. Domain contracts remain unchanged; B9.85 consumes B9.80-B9.84.
 2. Identity remains outside discovery metadata; the Hugging Face discovery
    provider does not become the owner of logical model identity.
 3. The resolver signature remains
    IdentityResolver = Callable[[str], str | None].
 4. Selection remains deterministic; no ranking, scoring, fuzzy matching or
    recommendation is introduced.
 5. Revision semantics remain B9.83's responsibility.
 6. The CLI is an adapter; cmd_download must not retain application
    orchestration logic after B9.85.
 7. ModelSource remains operational; B9.85 does not retire or deprecate the
    legacy source architecture.
 8. The application result is independent of CLI presentation.
 9. The Model Library is downstream; it may consume the application boundary
    but is not implemented by B9.85.
```

### 23.5 Explicit non-allocation

```text
B9.86: NOT ALLOCATED
B9.87+: NOT ALLOCATED
Model Library: NOT ALLOCATED BY B9.85
ModelSource retirement: NOT ALLOCATED BY B9.85
API integration: NOT ALLOCATED BY B9.85
Multi-revision storage: NOT ALLOCATED BY B9.85
```

No other block and no B9.85.x sub-block is allocated by this record.

### 23.6 Allocation versus implementation state

The distinction is explicit and is not implied anywhere in this record:

```text
B9.85 = ALLOCATED
B9.85 = NOT IMPLEMENTED
B9.85 = NOT VERIFIED
B9.85 = NOT CLOSED
```

> **SUPERSESSION (added by section 24, Closure Record).** The four lines above
> state the position **as of section 23 alone** and remain the accurate
> description of what this NAR itself did: it allocated a number and nothing
> more. The lifecycle status asserted by them is superseded prospectively by
> §24, which records the implementation, verification and closure that occurred
> afterwards. The current, authoritative state of B9.85 is:
>
> ```text
> B9.85 = ALLOCATED   (this section)
> B9.85 = IMPLEMENTED  (f2540dd022d1a3eb4ef2470265c25ac93d04a41f)
> B9.85 = VERIFIED    (PASS — section 24.4)
> B9.85 = CLOSED      (section 24)
> ```
>
> The allocation evidence recorded in this section — the §7 corpus inspection,
> the corpus integrity hashes, the candidate-number rejections and the
> validity reason — is unchanged and is not rewritten by §24.

### 23.7 Human approval reference

```text
ADR STATUS: APPROVED
ARCHITECTURAL SCOPE: APPROVED
NUMBER ALLOCATION: APPROVED BY THIS NAR
IMPLEMENTATION: NOT STARTED
```

> **SUPERSESSION (added by section 24, Closure Record).** `IMPLEMENTATION:
> NOT STARTED` describes this section's own state at authoring time. It was
> superseded when the implementation was committed at
> `f2540dd022d1a3eb4ef2470265c25ac93d04a41f` and subsequently verified and
> closed by §24. `ADR STATUS: APPROVED`, `ARCHITECTURAL SCOPE: APPROVED` and
> `NUMBER ALLOCATION: APPROVED BY THIS NAR` remain true and are unaffected.

This record allocates a number and attaches an already-approved scope. It
confers **no implementation authorization**. Implementation planning and
execution were a separate step, which began after this record was committed.

```text
IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
VERIFICATION AUTHORIZED:    NO
CLOSURE AUTHORIZED:         NO
```

B9.78 through B9.84 are not modified by this record.
 - B9.81 redesign
 - B9.82 redesign
 - B9.83 redesign
 - B9.84 redesign
 - resolver signature redesign
 - provider-supplied identity
 - ModelStore redesign
 - runtime redesign
 - evaluation
 - admission
 - fine-tuning
 - LoRA/QLoRA
 - API adapter integration
 - unrelated CLI redesign
 - ModelSource removal / deprecation
```
  roadmap allocation audit, a Human Architectural Decision Audit, and an
  approved Human Architectural Decision Record

Candidate Numbers Considered:
  B9.85 — SELECTED. highest_verified_allocated_block + 1 = B9.84 + 1 = B9.85.
    No allocation, reservation, provisional assignment or competing higher
    main identifier exists for it
  B9.86 and above — rejected: present only as recorded rejections at lines 3692
    and 3721; never considered
  B9.85.x and every other sub-block — rejected: sub-blocks do not raise the
    main-block floor and do not consume B9.85 (section 8)
  B9.78 through B9.84 — rejected: already allocated by sections 14-21 and
    closed; not reusable
  Historical gaps (every main number below B9.85 not allocated by sections
    14-21) — rejected: historical gaps, not reusable under section 9 (NOT
    REUSED, prospective declaration). No gap is claimed abandoned, freed,
    reserved or erroneous (section 13)

Selected Number:
  B9.85

Validity Reason:
  B9.84 is the highest verified allocated block at 5a40421: allocated in section
  21, implemented at cb69c85, verified and closed in section 22, and published on
  origin/main. A fresh section 7 corpus inspection at this anchor found no
  allocated main identifier above B9.84: B9.85 and B9.86 occur only as recorded
  rejections and negative assertions inside this document, and in no other
  versioned file. No branch, tag or commit outside this document's history
  establishes an allocation. Sub-blocks never raise the main floor (section 8)
  and historical gaps are not reusable (section 9). The next main block is
  therefore B9.85.
```
---

## 24. B9.85 — Closure Record

### 24.1 Closure status

B9.85 is formally **CLOSED**. The allocation record (section 23) precedes this
record and is not rewritten by it; where its status statements are superseded,
that supersession is stated explicitly as a cross-reference inside section 23
and recorded here. This section attests that the verified implementation
exists, was published, and matches the allocated scope exactly.

### 24.2 Implementation identity

```text
Implementation commit:
  f2540dd022d1a3eb4ef2470265c25ac93d04a41f
Commit message:
  feat: implement B9.85 application acquisition boundary
Branch:
  main
Publication state:
  pushed to origin/main (HEAD == origin/main at closure time)
Parent commit:
  9bd1f016b14c3d30f0bb255a90adb94c67e3617e  (the section 23 NAR)
```

Committed files, exclusively:

```text
A  castlearq/acquisition_service.py            (+491 / -0)
M  castlearq/application_wiring.py             (+74 / -)  additive composition seam
M  castlearq/main.py                           (+356 / -) run_download reduced to a CLI adapter
A  tests/test_b985_acquisition_service.py      (+544 / -0)
M  tests/test_download_cli.py                  (CLI regression preservation)
M  tests/test_main_execute.py                  (structural boundary allow-list)
```

The implementation commit contains no roadmap change: `docs/` does not appear in
it. The closure of B9.85 is this separate documentation commit.

### 24.3 Implemented scope

B9.85 implemented the scope allocated in 23.2: **Application Acquisition
Boundary + Real production integration through cmd_download**. The implemented
production path is:

```text
main.run_download
  -> application_wiring.compose_acquisition_service
  -> ModelAcquisitionService.acquire
  -> downloadable locator (injected locator_resolver)
  -> ModelDiscovery.inspect                      exactly once
  -> select_discovered_artifact                 B9.84, called once, unmodified
  -> map_discovered_artifacts                   B9.82, identity_resolver forwarded unchanged
  -> DownloadPlanner.plan
  -> Downloader.download
  -> ModelStore.save_manifest                   only after a successful transfer
  -> AcquisitionOutcome
  -> CLI presentation / exit status
```

Confirmed properties of the implementation:

```text
  - the boundary is a service class with every collaborator injected at the
    composition root; it builds nothing, caches nothing, and there is no hidden
    global service state;
  - discovery runs exactly once; the second call that would be needed for
    candidate presentation is eliminated by deriving candidates from data the
    service already holds;
  - `search()` is never called on the download path; no ranking, scoring, fuzzy
    matching or recommendation is introduced;
  - the service holds no identity knowledge: it receives an
    `IdentityResolver = Callable[[str], str | None]` bound at the composition
    root to `logical_model_id`, and forwards it unchanged to B9.82;
### 24.4 Verification evidence

Re-verified against the published implementation commit:

```text
B9.85 targeted tests:   61 passed  (tests/test_b985_acquisition_service.py,
                                        tests/test_download_cli.py)
B9.80-B9.84 regression: 260 passed (b980 discovery, b981 huggingface discovery,
                                        b982 acquisition mapping, b983 revision-aware
                                        acquisition, b984 discovery selection,
                                        artifact_selection, huggingface, selection,
                                        b974 store selection)
Full suite:            2070 passed
Full-suite subtests:   2703 passed
Failures:                   0
Errors:                     0
Ruff on the B9.85 files:   PASS ("All checks passed!" for
                                     castlearq/acquisition_service.py and
                                     tests/test_b985_acquisition_service.py)
mypy on the B9.85 module:  0 errors in castlearq/acquisition_service.py
git diff --check:          PASS (clean)
```

Mypy scope, stated precisely: 7 errors are reported project-wide, all of them
pre-existing and all of them located in modules the B9.85 implementation did
not touch (`castlearq/acquisition_mapping.py`, `castlearq/hardware.py`,
`castlearq/sources/huggingface.py`, `castlearq/compatibility.py`,
`castlearq/model_store.py`, `castlearq/downloads/downloader.py`). This record
does **not** assert that the repository is free of pre-existing type debt; it
asserts only that B9.85 introduced none, and that none of the pre-existing
errors were repaired in the course of B9.85.

Protected files confirmed untouched by the implementation commit:

```text
castlearq/discovery.py, castlearq/sources/huggingface_discovery.py,
castlearq/discovery_selection.py, castlearq/acquisition_mapping.py,
castlearq/resolver.py, castlearq/artifact_selection.py, castlearq/chat.py,
castlearq/run_service.py, castlearq/api.py, castlearq/model_store.py
  -> none appear in f2540dd022d1a3eb4ef2470265c25ac93d04a41f
```

### 24.5 CI follow-up (Python 3.11)

```text
CI failure:
  tests/test_chat_sessions.py::LifecycleHardeningTests::
    test_creation_concurrent_around_limit
  (expected sum(close_counts) == 2; observed 3)

Classification:
  E — FLAKY/NON-DETERMINISTIC TEST

B9.85 causality:   NOT ESTABLISHED — no causal path found
Closure impact:    NON-BLOCKING
```

A dedicated READ-ONLY regression audit was performed after the implementation
commit. It established that `tests/test_chat_sessions.py` was not modified by
B9.85, that the chat-session lifecycle modules (`castlearq/api.py`,
`castlearq/run_service.py`, `castlearq/chat.py`) are byte-identical to the
parent commit, and that the B9.85 diff introduces no threading, lock, barrier,
HTTP-lifecycle, session-cleanup, process-shutdown or global-state change. The
failure mechanism is a race between the registry's `is_full()` pre-check and its
atomic `register()`: a create rejected after its launch adds one additional
close, which is a legitimate interleaving that the test's
`sum(close_counts) == 2` assertion does not admit. Python 3.11 was the only CI
version that hit that interleaving in the run; the test passed on Python 3.12
and Python 3.13, and passed locally in 18 of 18 runs under the available
interpreter.

**The test was not modified as part of B9.85, it has not been fixed, and this
record does not claim that Python 3.11 CI is green.** The flaky assertion
remains a known, separately-owned test-quality issue with no identifier
allocated by this record. The incident did not block closure because no B9.85
correctness problem was identified.

### 24.6 Boundary compliance

The following were intentionally **not** implemented and remain separate future
work with no identifier allocated by this record:

```text
  - Model Library / Model Library GUI / Model Library UX
  - catalog / search UX
  - ranking, scoring, recommendation, fuzzy matching
  - multi-revision storage redesign
  - ModelStore redesign
  - ModelSource retirement or deprecation
  - B9.80, B9.81, B9.82, B9.83, B9.84 redesign
  - resolver signature redesign
  - API adapter integration
  - runtime execution changes
  - evaluation / admission changes
  - fine-tuning / LoRA / QLoRA
  - release / distribution redesign
  - B9.86 or any higher identifier (NOT ALLOCATED)
```

The legacy architecture remains operational and untouched: `ModelSource`,
`HuggingFaceSource`, `artifact_selection.select_artifact()` and `resolver.py`
are unmodified. The `_LegacySourceDiscoveryAdapter` introduced in `main.py` is a
compatibility shim for the pre-existing `source_factory` test seam only; it is
reachable only when `source_factory` is supplied and is not part of the normal
production download dispatch.

### 24.7 Repository state

```text
Implementation commit published successfully:  YES
HEAD == origin/main at implementation time:     YES
                                                    both f2540dd022d1a3eb4ef2470265c25ac93d04a41f
Implementation files remaining modified:       none
Modification present at closure-record authoring time:
  docs/roadmap-register-and-numbering-policy.md (this document) — this file only
```

The implementation commit is the verified artifact and remains immutable; it is
never rewritten or amended. This closure record only attests that it has been
formally closed. No B9.86 or any other identifier is created here.

### 24.8 Closure authorization

```text
B9.85 STATUS: CLOSED
B9.85 IMPLEMENTATION: COMPLETE
B9.85 VERIFICATION: COMPLETE
B9.85 PUBLICATION: COMPLETE
B9.85 CI PY3.11 INCIDENT: DISPOSITIONED — NON-BLOCKING
B9.85 CLOSURE: COMPLETE
```
  - expected failures are translated into `AcquisitionError` with a stable
    application category, preserving the original exception both as `cause` and
    as the Python exception cause; no blanket `except Exception` is used;
  - `run_download` retains argument validation, presentation and the exit status
    only; no orchestration logic remains in the CLI adapter;
  - exactly one `ModelStore` instance is created per use-case invocation and is
    shared by the planner, the downloader and manifest registration;
  - the application result is independent of CLI presentation and exposes no
    `Path`, `DownloadPlan` or `DownloadResult`.
```

The approved decisions D1-D8 recorded in 23.2 were realized exactly as decided:
D1 boundary and wiring in one block; D2 service class with injected
collaborators; D3 identity resolver backed by `logical_model_id`; D4
application-level error category with preserved causes; D5 ModelSource
coexistence; D6 production integration through `cmd_download`; D7 dedicated
application acquisition result; D8 scope limited to application acquisition
orchestration and its real production integration. None was reopened,
reinterpreted or amended.

---

## 25. B9.86 — Number Allocation Record

`B9.86` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.86 is **an allocation only**: no
implementation, no verification and no closure is claimed by this section.

The scope was **not chosen by this record**. It was fixed beforehand by a Human
Architectural Decision Record that the project owner approved, preceded by a
READ-ONLY roadmap allocation audit and a READ-ONLY Human Architectural Decision
Audit. This section allocates the number that carries that scope; it does not
widen, reinterpret or extend it.

```text
Assigned Number:
  B9.86

Title:
  Application Catalog / Query Boundary

Allocation Date:
  2026-10-02

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash.

  Recorded by the two-step mechanism already stated in section 11 for the
  numbering policy activation anchor and used identically by sections 19, 21
  and 23: at authoring time the hash did not exist and the field read "PENDING
  — fixed by the next controlled commit that sets it to that hash"; a commit
  hash cannot be known before the commit exists, and writing a guessed value
  would be a fabricated identifier. The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 24 — B9.85 Closure Record
Section for this allocation:
  section 25 — this record

Corpus/HEAD Anchor:
  c2eeb44cc31c9e605c5f877e6e62009002978c5b
  ("docs: close roadmap block B9.85"; main == HEAD == origin/main, working tree
  clean)

Tree object at anchor:
  b7c22c316d30191fee98a75d07b32bd58cdec098

Branch:
  main

Working tree at anchor:
  clean (no staged, modified or untracked files)

Corpus File Count:
  219 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  corpus integrity digest SHA-256 ->
    680614800a94e841fd4dc1b9a12c9a36fb88385d590e2601ee42b86ecf5ac66d
  identifier-set SHA-256 ->
    ae6fe6b2498003e25a5d85f51fc9299d021a4d44fb96d929d268b60e21247e1a
  identifier set: 135 distinct identifiers
  mechanism:
    git ls-tree -r HEAD --format='%(objectname)  %(path)' | sha256sum
      -> corpus integrity digest
    git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
      | LC_ALL=C sort -u | sha256sum
      -> identifier-set digest

Identifier Set:
  Highest main identifier in real use: B9.85 (section 23 NAR, section 24
  closure; implementation commit f2540dd022d1a3eb4ef2470265c25ac93d04a41f,
  which is an ancestor of origin/main).
  B9.86 — 9 occurrences before this record, every one of them inside this
    document and every one of them a recorded rejection or an explicit
    non-allocation statement: lines 3692, 3721, 4186, 4346, 4436, 4454, 4633
    and 4656.
    `git ls-files -z | xargs -0 grep -lnE 'B9\.8[67]'` returned exactly one
    path: this document. Zero occurrences existed in castlearq/, tests/,
    config/, .github/, README.md, pyproject.toml or any other versioned file.
    Classification at this anchor: recorded rejection or explicit
    non-allocation. None was an allocation, reservation, proposal, provisional
    assignment or implementation/test label.
  B9.87 and above — 1 occurrence (line 4347, "B9.87+: NOT ALLOCATED").
    No allocation or reservation exists for any of them.
  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.86.x sub-block
    is assigned by this record.
  Conflict inspection: only main and origin/main exist as branches; the tags
    v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
    no commit outside this document's history introduces a B9.86 allocation.
    No competing, competing-pending or conflicting identifier was found.

Preceding Block:
  B9.85 — Application Acquisition Boundary + cmd_download Integration

Preceding Block Status:
  ALLOCATED (section 23), IMPLEMENTED (f2540dd), CLOSED (section 24),
  published on origin/main

Highest Verified Allocation:
  B9.85

Rule in Force:
  Prospective monotonic main numbering (section 6)

Allocation Rule Applied:
  highest_verified_allocated_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
  Human Architectural Decision Record and a READ-ONLY allocation audit

Candidate Numbers Considered:
  B9.86 — SELECTED. It is the integer immediately following the highest main
    block already assigned and verified in the activation corpus (section 6).
  B9.87 — CONSIDERED AND DECLINED. Section 6 requires the integer immediately
    following the highest verified block; selecting 87 would leave 86
    permanently unused and would contradict the prospective monotonic rule.
  B9.88 and above — CONSIDERED AND DECLINED, for the same reason: each would
    introduce a gap above the highest verified block.
  B9.85.x and every other sub-block — CONSIDERED AND DECLINED. Section 6 states
    that only integers of the form B9.x raise the floor; sub-blocks do not
    raise the floor.
  Any lower or gap-filling identifier (for example B9.17 or B9.86x) —
    CONSIDERED AND DECLINED. Section 6 fixes the floor at the highest VERIFIED
    allocated identifier, not at the first unused identifier.

Selected Number:
  B9.86

Validity Reason:
  B9.85 is the highest main block assigned and verified in the activation
  corpus at the anchor recorded above. B9.86 is the integer immediately
  following it, as section 6 requires. Every pre-existing occurrence of B9.86
  in the corpus is a recorded rejection or an explicit non-allocation, so no
  competing allocation exists. The number is therefore valid under the active
  rule.

Release Association:
  NOT YET DEFINED

Supersession:
  none

Documented?:
  YES — this document

Number Allocation Record:
  PRESENT — section 25

Retrospective Record:
  NO — prospective allocation record

Human decisions pending:
  none — D1 and D2 both APPROVED
```

### 25.1 Register entry for B9.86

```text
Block ID:                 B9.86
Name:                     Application Catalog / Query Boundary
Status:                   ALLOCATED
Origin:                   this document, section 25 (NAR)
Scope:                    see 25.2 — approved by the ADR
Non-goals:                see 25.3
Architectural decision:   approved Human Architectural Decision Record
                          (D1 = A, D2 = APPROVED), preceding this allocation
Current State:            ALLOCATED — allocated by section 25
Implementation Commit:    NONE — NOT IMPLEMENTED
Verification Result:      NONE — NOT VERIFIED
Closure Commit:           NONE — NOT CLOSED
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document
Number Allocation Record: PRESENT — section 25
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none — D1 and D2 both APPROVED
```

The lifecycle state asserted by this record is, in full and without implication
of anything further:

```text
B9.86 = ALLOCATED
B9.86 = NOT IMPLEMENTED
B9.86 = NOT VERIFIED
B9.86 = NOT CLOSED
```

> **SUPERSESSION NOTE.** Earlier records in this document state that B9.86 is
> not allocated (section 23.5 line 4346, line 4347 for B9.87+, section 24.6
> line 4633, and the recorded rejections at lines 3692, 3721, 4186, 4436 and
> 4454). Those statements remain the accurate description of the corpus **at
> their own anchors** and are **not** rewritten by this section. The current,
> authoritative state of B9.86 is the one asserted above. The allocation
> evidence recorded in earlier sections is unchanged.

### 25.2 Scope attached to this allocation

The scope was fixed by the approved ADR and is recorded here without
reinterpretation.

```text
Application Catalog / Query Boundary
```

**Architectural purpose, as approved:**

```text
Introduce the application-level consumer boundary for
ModelDiscovery.search(), providing an application contract
for remote model candidates and opaque pagination without
introducing any user-facing Model Library surface.
```

**Included:**

```text
- application service around ModelDiscovery.search()
- application result contract
- application error category
- cause preservation
- opaque next_cursor pass-through
- composition-root wiring
- focused tests
```

The approved architectural decisions carried by this allocation, recorded here
for traceability and not restated as a re-decision:

```text
D1 = A       — the application catalog/query boundary is an architectural
               layer DISTINCT from Model Library UX
D2 = APPROVED — the negative scope and boundary are fixed as recorded in
               25.3 and 25.4
```

**The intended dependency, as approved:**

```text
ModelDiscovery.search()
        ↓
Application Catalog / Query Boundary
        ↓
application result
    ├── candidates
    └── opaque next_cursor
```

**No presentation layer is authorized by this allocation.**

### 25.3 Non-goals

The scope was fixed by the approved ADR and is recorded here without
reinterpretation.

```text
- Model Library UX
- GUI
- CLI browse/search command
- API endpoint
- ranking/scoring/recommendation
- fuzzy matching
- identity resolution
- artifact selection
- acquisition
- ModelSource migration/deprecation
- ModelStore changes
- runtime/execution
- evaluation/admission
- fine-tuning
- distribution/release redesign
```

These non-goals are carried forward unchanged from the closing record of B9.85
(section 24.6), each of which remains in force independently of this
allocation. This allocation does not authorize any of them, and does not open,
reserve, imply or provisionally assign an identifier for any of them.

### 25.4 Architectural constraints approved with this allocation

Persisted without expansion or reinterpretation.

```text
- Inject ModelDiscovery as collaborator.
- Invoke search() exactly once per application call.
- Pass query, limit and cursor unchanged.
- Preserve ModelCandidate metadata losslessly.
- Preserve next_cursor verbatim and opaque.
- Translate discovery failures to an application-level error category.
- Preserve original cause and __cause__.
- No blanket exception handling.
- TypeError / ValueError caller-contract violations propagate.
- Construct the service only through application_wiring.
- No provider construction inside the service.
- No caching.
- No sorting.
- No scoring.
- No ranking.
- No recommendation.
- No persistence.
- No network outside the injected provider.
- Independent of ModelAcquisitionService.
```

### 25.5 Architectural boundary preserved by this allocation

This allocation exists to separate the application layer from the product
surface. The following distinction is normative and is recorded here so that no
later record can silently collapse the two layers:

```text
Application boundary ≠ Model Library UX
```

The architectural invariant, as approved:

```text
The application catalog/query boundary exposes discovery capability.
It does not become a product surface.
```

Consequences that are fixed by this allocation:

- the boundary owns no screen, no command, no endpoint, no transport and no
  persisted state;
- Model Library / UX / GUI remains **NOT ALLOCATED** and **NOT AUTHORIZED**;
- a future block requiring any presentation mechanism is a different block and
  requires its own architectural decision;
- B9.85's `ModelSource` coexistence (D5) is preserved: `ModelSource`,
  `HuggingFaceSource`, `artifact_selection.select_artifact()` and `resolver.py`
  are untouched, and the unnamed "separate block" for legacy source convergence
  recorded in sections 18.3 and 19.3 remains unclaimed by this allocation;
- B9.85's invariant that the acquisition service never calls `search()` remains
  in force and is structurally guaranteed by section 25.3.

### 25.6 Preservation of closed records

This allocation changes no closed record. It is fixed by the following, all of
which it consumes as-is:

```text
B9.80 — discovery domain; consumed as-is. No field, type or port change.
        Identity stays out of L1 data.
B9.81 — Hugging Face discovery provider; used as the injected discovery
        collaborator, consumed as-is. Its cursor encoding, validation and
        metadata-only constraint remain its sole ownership.
B9.82 — acquisition mapping; untouched.
B9.83 — revision-aware acquisition; untouched. OD-1 remains immutable.
B9.84 — deterministic discovery-domain selection; untouched. Its four failure
        categories remain distinguishable and `select_artifact()` is not
        refactored into a shared abstraction.
B9.85 — application acquisition boundary; untouched. Its error precedent,
        result-contract pattern and composition-root discipline are followed,
        not modified.
```

Architectural invariants carried by this allocation:

```text
 1. Domain contracts remain unchanged; B9.86 consumes B9.80-B9.85.
 2. Identity remains outside discovery metadata and outside this boundary.
 3. Selection remains deterministic; no ranking, scoring, fuzzy matching or
    recommendation is introduced.
 4. The application result is independent of any presentation.
 5. Evaluation and admission separation is not reopened.
 6. The legacy source architecture remains operational and is not retired,
    deprecated or migrated by this allocation.
 7. No user-facing surface is created by this allocation.
```

### 25.7 Allocation versus implementation state

The distinction is explicit and is not implied anywhere in this record:

```text
B9.86 = ALLOCATED
B9.86 = NOT IMPLEMENTED
B9.86 = NOT VERIFIED
B9.86 = NOT CLOSED
```

> **SUPERSESSION (added by section 26, Closure Record).** The four lines above
> state the position **as of section 25 alone** and remain the accurate
> description of what this NAR did: it allocated a number and nothing more. They
> are not rewritten by section 26. The current, authoritative state of B9.86 is:
>
> ```text
> B9.86 = ALLOCATED   (this section)
> B9.86 = IMPLEMENTED  (6cb9e1d8ab9c6f0790210a590ef48dcc11690822)
> B9.86 = VERIFIED    (section 26.7)
> B9.86 = CLOSED      (section 26)
> ```
>
> The allocation evidence recorded in this section — the corpus anchor, the
> corpus integrity digests, the identifier-set disposition, the candidate-number
> rejections, the approved scope, the non-goals, the approved constraints and the
> validity reason — is unchanged and is not rewritten by section 26.

### 25.8 Human approval reference

```text
ADR STATUS: APPROVED
ARCHITECTURAL SCOPE: APPROVED
NUMBER ALLOCATION: APPROVED BY THIS NAR
IMPLEMENTATION: NOT STARTED
```

Implementation is **not** authorized by this record. The next required step is a
READ-ONLY implementation-design audit; no implementation file, test, surface or
refactoring is authorized here.

---

## 26. B9.86 — Closure Record

### 26.1 Closure status

B9.86 is formally **CLOSED**. The allocation record (section 25) precedes this
record and is not rewritten by it; where its status statements are superseded,
that supersession is stated explicitly as a cross-reference inside section 25
and recorded here. This section attests that the verified implementation
exists, was published, and matches the allocated scope exactly.

A READ-ONLY verification audit was performed before this closure and returned
`READY FOR CLOSURE`. Its findings F1-F5 are dispositioned in 26.9 and none of
them is blocking.

### 26.2 Implementation identity

```text
Block ID:
  B9.86

Name:
  Application Catalog / Query Boundary

Implementation commit:
  6cb9e1d8ab9c6f0790210a590ef48dcc11690822

Commit message:
  feat: implement B9.86 application catalog query boundary

Branch:
  main

Publication state:
  pushed to origin/main (HEAD == origin/main at closure time)

Allocation commit:
  a8be7ae33a477f39eb828bc8b5d9a39e6ec84840
    ("docs: allocate roadmap block B9.86"; section 25 NAR)

Parent commit:
  a8be7ae33a477f39eb828bc8b5d9a39e6ec84840  (the section 25 NAR)

Closure commit:
  PENDING — fixed by the next controlled commit that sets it to that hash,
  per the two-step mechanism stated in section 11 and used identically by
  sections 19, 21, 23 and 24. A commit hash cannot be known before the commit
  exists, and writing a guessed value would be a fabricated identifier.
```

Committed files, exclusively:

```text
A  castlearq/catalog_query_service.py       (+204 / -0)
M  castlearq/application_wiring.py           (+35  / -)  additive composition seam
A  tests/test_b986_catalog_query_service.py  (+513 / -0)
```

The implementation commit contains no roadmap change: `docs/` does not appear in
it. The closure of B9.86 is this separate documentation commit.

### 26.3 Human architectural decision reference

```text
D1 = A        — the application catalog/query boundary is an architectural layer
                DISTINCT from Model Library UX
D2 = APPROVED  — the negative scope and boundary are fixed as recorded in
                section 25.3 and 25.4
```

Neither decision was reopened, reinterpreted or amended by the implementation or
by this closure.

### 26.4 Allocation reference

```text
Allocation record:      section 25 (B9.86 — Number Allocation Record)
Allocation commit:      a8be7ae33a477f39eb828bc8b5d9a39e6ec84840
Allocated scope:        section 25.2
Allocated non-goals:    section 25.3
Approved constraints:   section 25.4
Boundary invariant:     section 25.5
Preserved records:      section 25.6
```

### 26.5 Implemented scope

B9.86 implemented exactly the scope allocated in 25.2:

```text
- application service around ModelDiscovery.search()
- application result contract
- application error category
- cause preservation
- opaque next_cursor pass-through
- composition-root wiring
- focused tests
```

Realized as:

```text
castlearq/catalog_query_service.py
  CatalogQueryErrorCategory(str, Enum)   DISCOVERY_FAILED, INVALID_CURSOR
  CatalogQueryError(Exception)            .category, .message, .cause, .__cause__
  CatalogQueryOutcome                     @dataclass(frozen=True)
                                          candidates, next_cursor
  ModelCatalogQueryService
    __init__(discovery_provider: ModelDiscovery)
    query(query, *, limit=20, cursor=None) -> CatalogQueryOutcome

castlearq/application_wiring.py
  compose_catalog_query_service(*, discovery_provider: ModelDiscovery | None = None)

tests/test_b986_catalog_query_service.py
  37 focused tests, local fakes only
```

The service imports only the discovery **port** plus standard-library
constructs. It instantiates no provider, builds no collaborator, caches
nothing, performs no network call and touches no filesystem.

### 26.6 Explicit non-goals

None of the following was implemented. None was partially implemented. None is
claimed by this record.

```text
- Model Library UX
- GUI
- CLI browse/search surface
- API catalog endpoint
- ranking
- scoring
- recommendation
- fuzzy matching
- query rewriting
- identity resolution
- artifact selection
- quantization selection
- acquisition
- ModelSource migration/deprecation
- ModelStore changes
- runtime/execution changes
- evaluation/admission
- fine-tuning
- datasets/training
- distribution/release redesign
```

No new identifier is created by this closure:

```text
B9.87:        NOT ALLOCATED
B9.88+:       NOT ALLOCATED
Model Library UX:      NOT ALLOCATED
Model Library GUI:     NOT ALLOCATED
GUI:                   NOT AUTHORIZED
```

This closure authorizes none of the capabilities above.

### 26.7 Verification evidence

Verified by a READ-ONLY verification audit executed before this closure, at
`6cb9e1d8ab9c6f0790210a590ef48dcc11690822` with `HEAD == origin/main` and a
clean working tree.

```text
B9.86 focused tests:
  tests.test_b986_catalog_query_service — 37 passed

B9.80-B9.85 regression:
  249 passed

Full suite:
  python3 -m unittest discover -s tests -t . — 2070 passed

Ruff:
  PASS on both B9.86 new files
  (castlearq/catalog_query_service.py, tests/test_b986_catalog_query_service.py)

mypy:
  11 pre-existing errors across 9 unrelated files
  0 new B9.86 errors

git diff --check:
  PASS (exit 0)

Working tree:
  clean

HEAD:
  6cb9e1d8ab9c6f0790210a590ef48dcc11690822

origin/main:
  same commit
```

Closure criteria C1-C10 — allocation compliance, ADR compliance, contract
correctness, cursor authority, dependency injection, acquisition isolation,
presentation isolation, regression safety, commit integrity and repository
integrity — were each evaluated and each returned PASS. No criterion returned
FAIL. No failure is attributable to B9.86.

The pre-existing mypy errors were **not** fixed by B9.86 and are **not**
claimed as fixed by this record. The pre-existing Ruff findings in
`castlearq/application_wiring.py` were **not** fixed and are **not** claimed as
fixed.

### 26.8 Architectural boundary compliance

B9.86 realizes the dependency direction fixed by the approved ADR:

```text
ModelDiscovery.search()
        ↓
Application Catalog / Query Boundary      (B9.86)
        ↓
future presentation layer                 (NOT IMPLEMENTED, NOT AUTHORIZED)
```

Verified compliance:

```text
- ModelDiscovery remains the domain port; unchanged by B9.86
- B9.81 remains the provider and cursor-validation authority
- B9.86 does not become a presentation surface
- B9.86 has no production caller, by design
- acquisition continues to use inspect() and never search()
- B9.86 does not depend on acquisition in any direction
- the composition root remains the sole construction boundary
```

The load-bearing invariant of 25.5 is preserved verbatim:

```text
Application boundary != Model Library UX
```

and

```text
The application catalog/query boundary exposes discovery capability.
It does not become a product surface.
```

Preserved closed records, confirmed unchanged by the implementation commit:

```text
B9.80 discovery domain        unchanged
B9.81 HF discovery provider   unchanged (cursor authority intact)
B9.82 acquisition mapping     unchanged
B9.83 revision-aware acq.     unchanged
B9.84 discovery selection     unchanged
B9.85 acquisition boundary    unchanged (ModelSource coexistence preserved)
ModelSource / HuggingFaceSource / resolver.py / ModelStore   unchanged
execution boundary and evaluation/admission separation       unchanged
```

The B9.80 port now has two independent consumers, with no edge between them:

```text
B9.80 ModelDiscovery
   |
   +-- inspect() --> B9.85 Acquisition
   |
   +-- search()  --> B9.86 Catalog Query
                        |
                        +--> future presentation layer (not implemented)
```

### 26.9 Findings and disposition

Recorded from the verification audit. None is blocking. None was repaired.

```text
F1  Pre-existing Ruff findings in castlearq/application_wiring.py
    (I001, UP035, UP017)
    -> PRE-EXISTING / OUT-OF-SCOPE
    Identical at the pre-change baseline. Not repaired by B9.86 and not
    repaired by this closure.

F2  11 pre-existing mypy errors across 9 unrelated files
    -> PRE-EXISTING / OUT-OF-SCOPE
    Zero errors in B9.86 scope. Not repaired and not claimed as fixed.

F3  _category() derives INVALID_CURSOR from the message text of an
    already-raised, provider-originated DiscoveryError
    -> ACCEPTED NON-BLOCKING CHARACTERISTIC
    B9.86 does NOT validate the cursor. B9.81 remains the validation
    authority and still performs all cursor decoding, syntax checks and
    pagination rules. B9.86 only classifies an error that has already been
    raised: it never receives the cursor value, never decodes or parses it,
    and cannot manufacture a cursor error of its own. The classification is
    a labeling of an already-known domain failure, not a second authority.
    It cannot accept an invalid cursor, because the provider already
    rejected it, and cannot reject a valid one, because the provider would
    not have raised. Recorded as a characteristic of the boundary, not as a
    defect, and not repaired.

F4  application_wiring.__all__ does not include compose_catalog_query_service
    -> PRE-EXISTING / OUT-OF-SCOPE
    The same omission already applies to compose_acquisition_service from
    B9.85. The function is reachable by direct import. Not repaired.

F5  No production caller exists for B9.86
    -> INTENTIONAL / OUT-OF-SCOPE BY DESIGN
    Section 25.3 excludes every presentation surface. The absence is a
    consequence of the approved scope, not a gap. No caller was added.
```

### 26.10 Repository state

```text
Implementation commit published successfully:  YES
HEAD == origin/main at implementation time:     YES
                        both 6cb9e1d8ab9c6f0790210a590ef48dcc11690822
Implementation files remaining modified:       none
Production code changed by the closure:        none
Tests changed by the closure:                   none
Generated files added:                          none
```

The implementation commit is the verified artifact and remains immutable; it is
never rewritten or amended. This closure record only attests that it has been
formally closed. Only
`docs/roadmap-register-and-numbering-policy.md` is modified by the closure
commit.

### 26.11 State transition and history preservation

Section 25 records the state of B9.86 **at allocation time** and is not
rewritten. Those statements remain accurate for their own anchor:

```text
ORIGINAL ALLOCATION STATE (section 25, preserved):
  B9.86 = ALLOCATED
  B9.86 = NOT IMPLEMENTED
  B9.86 = NOT VERIFIED
  B9.86 = NOT CLOSED

CURRENT CLOSURE STATE (this section, authoritative):
  B9.86 = ALLOCATED     (section 25 NAR)
  B9.86 = IMPLEMENTED    (6cb9e1d8ab9c6f0790210a590ef48dcc11690822)
  B9.86 = VERIFIED       (section 26.7)
  B9.86 = CLOSED         (this section)
```

B9.86 was not allocated as CLOSED, and no historical record has been rewritten
to suggest that it was.

### 26.12 Closure authorization

```text
B9.86 STATUS: CLOSED
B9.86 IMPLEMENTATION: COMPLETE
B9.86 VERIFICATION: COMPLETE
B9.86 PUBLICATION: COMPLETE
B9.86 CLOSURE: COMPLETE

B9.87+: NOT ALLOCATED
Model Library UX: NOT ALLOCATED
Model Library GUI: NOT ALLOCATED
GUI: NOT AUTHORIZED
```

The approved decisions D1 and D2 recorded in 25.2 were realized exactly as
decided: an application-layer catalog/query boundary distinct from Model Library
UX, with the negative scope fixed by the allocation. Neither was reopened,
reinterpreted or amended. This closure allocates no successor identifier and
authorizes no future capability.
---

## 27. B9.87 — Number Allocation Record

`B9.87` is allocated as the next main block under §6, on the evidence of a §7
corpus inspection performed at allocation time. This section is the §11 record
for that assignment. At allocation time B9.87 is **an allocation only**: no
implementation, no verification and no closure is claimed by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified Human Architectural Decision Record
`docs/B9.87-cli-catalog-query-caller-decision.md`, which was preceded by a
READ-ONLY roadmap allocation audit. This section allocates the number that
carries that scope; it does not widen, reinterpret or extend it.

### 27.1 Allocation evidence block

```text
Assigned Number:
  B9.87

Title:
  CLI Catalog Query Caller — First Production Caller for B9.86
  ModelCatalogQueryService

Allocation Date:
  2026-10-02

Allocation Commit:
  5f0431166a06289aa455e080ed02e002119186ea
    ("docs: allocate roadmap block B9.87"; section 27 NAR)

  Recorded by the two-step mechanism already stated in section 11 and used
  identically by sections 19, 21, 23 and 25: at authoring time the hash did not
  exist and the field read "PENDING — fixed by the next controlled commit that
  sets it to that hash"; a commit hash cannot be known before the commit
  exists, and writing a guessed value would be a fabricated identifier. The
  allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 26 — B9.86 Closure Record
Section for this allocation:
  section 27 — this record

Human Architectural Decision Record:
  docs/B9.87-cli-catalog-query-caller-decision.md
  HADR STATUS: HUMAN-RATIFIED
  ARCHITECTURAL SCOPE: APPROVED
  NUMBER ALLOCATION: APPROVED BY THIS HADR; RECORDED IN §27
  IMPLEMENTATION: NOT STARTED

Corpus/HEAD Anchor:
  aacbc8e12b1098adeedb5bb64b4bdc621b1524d8
  ("docs: close roadmap block B9.86"; main == HEAD == origin/main)

Tree object at anchor:
  76067f78e8a713ba49ccace1e21e2c33501e090e

Branch:
  main

Working tree at anchor:
  tracked tree clean; one untracked file present, docs/product-vision-adr.md —
  the human-ratified Product Vision ADR recorded under the separate, prior
  documentation-only authorization. It is untracked at this anchor and is
  therefore NOT part of the corpus fixed below. Its presence does not change the
  identifier set, which is asserted over tracked files only.

Corpus File Count:
  221 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  corpus integrity digest SHA-256 ->
    9f48eb7acec94febef1673c285be0ea27191c8ea6041dce67c5d3fd3f4982a39
  identifier-set SHA-256 ->
    82af630eed5bd9c78abd7368460aaa68b857e0e16196e5b8fc298073c228c0ce
  identifier set: 137 distinct identifiers
  mechanism:
    git ls-tree -r HEAD --format='%(objectname)  %(path)' | sha256sum
      -> corpus integrity digest
    git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
      | LC_ALL=C sort -u | sha256sum
      -> identifier-set digest

Identifier Set:
  Highest main identifier in real use: B9.86 (section 25 NAR, section 26
    closure; implementation commit
    6cb9e1d8ab9c6f0790210a590ef48dcc11690822, an ancestor of origin/main).
  B9.87 — 6 occurrences before this record, every one of them inside this
    document and every one of them an explicit non-allocation statement, a
    recorded rejection, a supersession cross-reference or a corpus-inspection
    note: lines 4347, 4774, 4810, 4886, 5262 and 5470.
    `git ls-files -z | xargs -0 grep -lnE 'B9\.8[789]'` returned exactly one
    path: this document. Zero occurrences existed in castlearq/, tests/,
    config/, .github/, README.md, pyproject.toml or any other versioned file.
    Classification at this anchor: explicit non-allocation or recorded
    rejection. None was an allocation, reservation, proposal, provisional
    assignment or implementation/test label.
  B9.88 and above — 2 occurrences before this record, both inside this document
    (lines 4813 and 5263), both an explicit non-allocation or a recorded-decline
    statement. No allocation or reservation exists for any of them.
  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.87.x sub-block
    is assigned by this record.
  Conflict inspection: only main and origin/main exist as branches; the tags
    v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
    no commit outside this document's history introduces a B9.87 allocation.
    No competing, competing-pending or conflicting identifier was found.

Preceding Block:
  B9.86 — Application Catalog / Query Boundary

Preceding Block Status:
  ALLOCATED (section 25), IMPLEMENTED (6cb9e1d8), VERIFIED (section 26.7),
  CLOSED (section 26.12), published on origin/main

Highest Verified Allocation:
  B9.86

Rule in Force:
  Prospective monotonic main numbering (section 6)

Allocation Rule Applied:
  highest_verified_allocated_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
  roadmap allocation audit and a human-ratified HADR

Candidate Numbers Considered:
  B9.87 — SELECTED. highest_verified_allocated_block + 1 = B9.86 + 1. No
    allocation, reservation, provisional assignment or competing higher main
    identifier exists for it; every pre-existing occurrence is an explicit
    non-allocation or a recorded rejection inside this document.
  B9.88 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
    immediately following the highest verified block; selecting 88 or above
    would leave 87 permanently unused and would contradict the prospective
    monotonic rule.
  B9.87.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
    integers of the form B9.x raise the main-block floor.
  Any lower or gap-filling identifier (for example B9.17 or B9.84) —
    CONSIDERED AND DECLINED. Section 6 fixes the floor at the highest VERIFIED
    allocated identifier; section 9 declares gaps NOT REUSED prospectively. No
    gap is claimed abandoned, freed, reserved or erroneous (section 13).

Selected Number:
  B9.87

Validity Reason:
  B9.86 is the highest main block assigned, implemented, verified and closed in
  the activation corpus at the anchor recorded above. B9.87 is the integer
  immediately following it, as section 6 requires. Every pre-existing occurrence
  of B9.87 in the corpus is an explicit non-allocation or a recorded rejection,
  so no competing allocation exists. The number is therefore valid under the
  active rule.

Release Association:
  NOT YET DEFINED

Supersession:
  none

Documented?:
  YES — this document (section 27) plus
  docs/B9.87-cli-catalog-query-caller-decision.md

Number Allocation Record:
  PRESENT — section 27

Retrospective Record:
  NO — prospective allocation record

Human decisions pending:
  none — the HADR is HUMAN-RATIFIED and its architectural scope is APPROVED
```

### 27.2 Register entry for B9.87

```text
Block ID:                 B9.87
Name:                     CLI Catalog Query Caller — First Production Caller
                          for B9.86 ModelCatalogQueryService
Status:                   CLOSED
Origin:                   this document, sections 27 (NAR) and 28 (Closure
                          Record)
Scope:                    see 27.3 — approved by the HADR
Non-goals:                see 27.4
Architectural decision:   HUMAN-RATIFIED Human Architectural Decision Record
                          (docs/B9.87-cli-catalog-query-caller-decision.md),
                          preceding this allocation
Current State:            CLOSED — allocated by section 27, implemented at
                          df99949f922789f2b1cc4a507a090c86a01c5e84, verified
                          PASS, closed by section 28
Implementation Commit:    df99949f922789f2b1cc4a507a090c86a01c5e84
                          ("feat: implement B9.87 CLI catalog query caller")
Allocation Commit:        5f0431166a06289aa455e080ed02e002119186ea
                          ("docs: allocate roadmap block B9.87")
Verification Result:      PASS — see section 28.7
Closure Commit:           PENDING — fixed by the next controlled commit that sets
                          it to that hash, per the two-step mechanism stated in
                          section 11 and used identically by sections 19, 21, 23
                          and 25. A commit hash cannot be known before the commit
                          exists, and writing a guessed value would be a
                          fabricated identifier. The same field is left PENDING in
                          section 23.1 for B9.85 and section 26.2 for B9.86.
Release Association:      NOT YET DEFINED
Supersession:             none — the allocation-time state below is preserved
                          and superseded by explicit cross-reference only
Documented?:              YES — this document + the HADR
Number Allocation Record: PRESENT — section 27
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none
```

The lifecycle state asserted by this record **at allocation time** is, in full
and without implication of anything further:

```text
B9.87 = ALLOCATED
B9.87 = NOT IMPLEMENTED
B9.87 = NOT VERIFIED
B9.87 = NOT CLOSED
```

Those four statements remain the accurate description of B9.87 **at the
allocation anchor recorded in 27.1** and are **not** rewritten. The current,
authoritative lifecycle state is asserted by section 28.11:

```text
B9.87 = ALLOCATED   (section 27 NAR, 5f0431166a06289aa455e080ed02e002119186ea)
B9.87 = IMPLEMENTED  (df99949f922789f2b1cc4a507a090c86a01c5e84)
B9.87 = VERIFIED     (section 28.7)
B9.87 = CLOSED       (section 28)
```

> **SUPERSESSION NOTE.** Earlier records in this document state that B9.87 is
> not allocated (section 23.5 line 4347; the corpus-inspection note at line 4774;
> the recorded decline at line 4810; the cross-reference at line 4886; section
> 26.6 line 5262; and section 26.12 line 5470). Those statements remain the
> accurate description of the corpus **at their own anchors** and are **not**
> rewritten by this section. The current, authoritative state of B9.87 is the one
> asserted above. The allocation evidence recorded in earlier sections is
> unchanged, and no historical allocation record is altered by this one.

### 27.3 Scope attached to this allocation

The scope was fixed by the human-ratified HADR and is recorded here without
reinterpretation.

```text
CLI Catalog Query Caller — First Production Caller for B9.86
ModelCatalogQueryService
```

**Architectural purpose, as approved:**

```text
Give the closed B9.86 application catalog/query boundary its first production
caller, through a minimal read-only CLI `search` command that presents what the
boundary returns and interprets nothing.
```

**Dependency on B9.86 (completed prerequisite):**

```text
B9.86 = ALLOCATED (25), IMPLEMENTED (6cb9e1d8), VERIFIED (26.7),
        CLOSED (26.12)
```

B9.87 consumes the following closed contracts and does not redesign any of
them:

```text
B9.80 — discovery domain; ModelDiscovery.search(query, limit, cursor) is
        consumed as-is; ModelCandidate passes through by identity
B9.81 — Hugging Face discovery provider; search(), cursor encoding/decoding,
        limit validation and Link-header pagination consumed as-is
B9.86 — application catalog/query boundary; ModelCatalogQueryService.query(),
        CatalogQueryOutcome(candidates, next_cursor) and
        CatalogQueryErrorCategory consumed as authoritative
application_wiring.compose_catalog_query_service() — composition point
        consumed as-is; the provider is constructed there, not by the CLI
```

**Included:**

```text
- a CLI `search` command;
- routing it through the existing ModelCatalogQueryService;
- use of the existing application composition root;
- presentation of discovered catalog candidates;
- preservation of the opaque next_cursor contract;
- the existing human-readable / structured output conventions where applicable;
- mapping of application errors to existing CLI error behaviour;
- focused tests for the new adapter;
- the CLI documentation/help-text update required by the public-surface
  contract enforced in tests/test_api_serve_contract.py;
- preservation of every B9.86 architectural invariant.
```

### 27.4 Explicit non-goals

```text
- Model Library UX
- GUI
- model cards
- quantization selection UI
- compatibility warnings in the search path
- hardware suitability recommendations
- ranking
- scoring
- recommendation
- fuzzy search
- query rewriting
- caching
- persistence
- automatic pagination
- acquisition from search
- artifact selection
- identity resolution
- Chat changes
- a Conversation abstraction
- Chat lifecycle migration out of api.py
- second runtime
- Ollama integration
- multi-runtime execution
- multi-GPU
- execution-path convergence (`run` vs `execute`)
- compatibility / evaluation / admission expansion
- fine-tuning
- datasets
- RAG
- agents
- MCP
- telemetry
- accounts
- cloud services
- a new HTTP endpoint
- any new dependency
```

This allocation authorizes none of the above, opens no identifier for any of
them, and reserves none of them.

### 27.5 Architectural invariants approved with this allocation

Persisted without expansion or reinterpretation.

```text
- The boundary CLI -> Application -> Discovery port -> Discovery provider is
  preserved.
- The CLI does not instantiate or import HuggingFaceDiscoveryProvider for the
  search path; the composition root constructs the provider.
- The CLI contains no discovery logic.
- The CLI does not reinterpret the catalog query contract.
- The CLI does not rank, score or recommend models.
- The CLI does not turn the search feature into a Model Library.
- ModelCatalogQueryService remains authoritative and is consumed as-is:
  candidates pass through by identity, next_cursor stays verbatim and opaque,
  exactly one search() call occurs per query() call, and no second validation
  authority is introduced.
- Application errors are translated by the adapter, never re-validated.
- The application boundary is not moved, renamed or re-shaped.
```

### 27.6 Allocation versus implementation state

The distinction is explicit and is not implied anywhere in this record:

```text
This record allocates an identifier and attaches an already-approved scope.

B9.87  = ALLOCATED
B9.87  = NOT IMPLEMENTED
B9.87  = NOT VERIFIED
B9.87  = NOT CLOSED

IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
VERIFICATION AUTHORIZED:    NO
CLOSURE AUTHORIZED:         NO
```

No `search` command exists at this anchor: `castlearq/main.py:2537` lists
`detect, diagnose, verify, models, list, runtime, source, plan, compatibility,
validate, download, import, run, execute, chat, serve, store`. Nothing in this
record changes that.

> **SUPERSESSION NOTE (state only, added at closure).** The statement above is
> preserved exactly as written and remains accurate **for the allocation anchor
> recorded in 27.1** (`aacbc8e12b1098adeedb5bb64b4bdc621b1524d8`), where no
> `search` command existed. B9.87 was subsequently implemented and closed:
>
> ```text
> ALLOCATION-TIME STATE (section 27, preserved):
>   B9.87 = ALLOCATED / NOT IMPLEMENTED / NOT VERIFIED / NOT CLOSED
>   no `search` command existed at anchor aacbc8e
>
> CURRENT STATE (section 28, authoritative):
>   B9.87 = ALLOCATED / IMPLEMENTED / VERIFIED / CLOSED
>   `castlearq search <query>` exists, implemented at
>   df99949f922789f2b1cc4a507a090c86a01c5e84
> ```
>
> No allocation evidence, corpus count, identifier set, digest or anchor in this
> section was altered by the implementation or by the closure. This paragraph is
> a cross-reference, following the pattern of sections 25.1 and 26.11.

---

---

## 28. B9.87 — Closure Record

### 28.1 Closure status

B9.87 is formally **CLOSED**. The allocation record (section 27) and the Human
Architectural Decision Record
`docs/B9.87-cli-catalog-query-caller-decision.md` both precede this record and
are not rewritten by it; where their status statements are superseded, that
supersession is stated explicitly as a cross-reference inside section 27 and
inside the HADR, and recorded here. This section attests that the verified
implementation exists, was published, and matches the allocated scope exactly.

A READ-ONLY closure eligibility audit was performed before this closure and
returned `CLOSURE-ELIGIBLE WITH DOCUMENTATION FOLLOW-UP`. Its findings are
dispositioned in 28.10 and none of them is blocking. The documentation
follow-up identified by that audit is discharged by this closure commit.

### 28.2 Implementation identity

```text
Block ID:
  B9.87

Name:
  CLI Catalog Query Caller — First Production Caller for B9.86
  ModelCatalogQueryService

Implementation commit:
  df99949f922789f2b1cc4a507a090c86a01c5e84

Commit message:
  feat: implement B9.87 CLI catalog query caller

Branch:
  main

Publication state:
  pushed to origin/main (HEAD == origin/main at closure time)

Parent commit:
  aacbc8e12b1098adeedb5bb64b4bdc621b1524d8  ("docs: close roadmap block B9.86")
```

Committed files, exclusively:

```text
M  castlearq/main.py                        (+167 / -2)   the `search` CLI adapter
A  tests/test_b987_cli_search.py            (+395 / -0)   focused adapter tests
M  tests/test_b9765_json_cli.py             (+4 / -)      JSON surface exact set
M  tests/test_main_execute.py               (+5 / -)      composition boundary set
M  README.md                                (+25 / -1)    CLI documentation
```

The implementation commit contains no roadmap change: `docs/` does not appear in
it. The allocation documentation (section 27, the HADR and the Product Vision
ADR) is the separate commit `5f0431166a06289aa455e080ed02e002119186ea`, and the
closure of B9.87 is this separate documentation commit.

### 28.3 Human architectural decision reference

```text
docs/B9.87-cli-catalog-query-caller-decision.md

DECISION:              HUMAN-RATIFIED
ARCHITECTURAL SCOPE:  APPROVED
IMPLEMENTATION:       approved by a separate implementation task
                       (df99949f922789f2b1cc4a507a090c86a01c5e84)
```

No decision in the HADR was reopened, reinterpreted or amended by the
implementation or by this closure. The HADR's own status block
(`IMPLEMENTATION: NOT STARTED`, `VERIFICATION: NONE`, `CLOSURE: NONE`) is
preserved verbatim as the allocation-time state and is superseded only by the
explicit cross-reference added to that document.

### 28.4 Allocation reference

```text
Allocation record:      section 27 (B9.87 — Number Allocation Record)
Allocation commit:      5f0431166a06289aa455e080ed02e002119186ea
                        ("docs: allocate roadmap block B9.87")
Allocation anchor:      aacbc8e12b1098adeedb5bb64b4bdc621b1524d8
                        ("docs: close roadmap block B9.86")
Allocated scope:        section 27.3
Allocated non-goals:    section 27.4
Boundary invariants:    section 27.5
Preserved records:      section 27.6
Human-ratified scope:   "Give the closed B9.86 application catalog/query
                        boundary its first production caller, through a minimal
                        read-only CLI `search` command that presents what the
                        boundary returns and interprets nothing."
```

### 28.5 Implemented scope

B9.87 implemented exactly the scope allocated in 27.3. The realized product
surface is:

```text
castlearq search <query>
```

The realized production path is:

```text
CLI
  castlearq/main.py :: search_command
  -> application composition
       application_wiring.compose_catalog_query_service()
  -> ModelCatalogQueryService.query()
  -> ModelDiscovery.search()
  -> HuggingFaceDiscoveryProvider.search()
```

Realized as:

```text
- a CLI `search` command, routed through the existing ModelCatalogQueryService
- use of the existing application composition root
  (compose_catalog_query_service), never a second one
- presentation of discovered catalog candidates, in the boundary's own order,
  with no field added, renamed, derived, normalized or omitted
- preservation of the opaque next_cursor contract: printed verbatim in human
  output, exposed as `next_cursor` in JSON, never decoded, validated or rebuilt
- the existing human-readable and structured output conventions
  (`search` added to _JSON_COMMANDS; no new envelope shape)
- `--limit` and `--cursor`, accepted for `search` only and rejected elsewhere
  by the existing per-command supported_flags table
- mapping of application errors to existing CLI error behaviour
  (CatalogQueryError -> exit 1, JSON kind `search_<category>`; usage errors ->
  exit 2 through the existing CLI conventions)
- focused tests (tests/test_b987_cli_search.py, 23 tests)
- the CLI documentation update required by the public-surface contract
  enforced in tests/test_api_serve_contract.py (README.md and the help text)
- preservation of every B9.86 architectural invariant
```

A completed query that returned no candidates is a success: exit 0, human
output prints "No candidates found.", and JSON output carries an empty
`candidates` list with no `error` member.

### 28.6 Contract-test changes

Two pre-existing exact-set assertions were widened by exactly one name each.
Neither was weakened, skipped, relaxed or made tolerant; both remain exact
equality assertions and both still fail on any unintended addition or removal.

```text
tests/test_b9765_json_cli.py
  test_wired_commands_are_exactly_the_ratified_set
    -> `_JSON_COMMANDS` gains "search".
    Required because the assertion is an exact tuple equality; the alternative
    would be to deny the search command the existing JSON envelope, which the
    HADR (7.1 item 6) does not authorize.

tests/test_main_execute.py
  test_new_flow_module_imports_are_exactly_the_three_allowed_modules
    -> the `application_wiring` name set gains
       "compose_catalog_query_service".
    Required because the assertion is an exact equality over the names imported
    from `application_wiring`; the alternative would be a second composition
    root or a direct provider import, both forbidden by 27.5.
    The outer assertion still enforces "exactly the three allowed modules";
    only a name inside the already-allowed module grew.

Precedent: B9.85 (commit f2540dd) made the structurally identical edit to the
same assertion, adding "compose_acquisition_service", following the same
inline-rationale convention. B9.74 did the same for the `evaluate_compatibility`
set. B9.87 is the third block in that established series.
```

### 28.7 Verification evidence

```text
python3 -m pytest tests/test_b987_cli_search.py -q
  -> 23 passed, 3 subtests passed

python3 -m pytest tests/test_b987_cli_search.py \
                    tests/test_b986_catalog_query_service.py \
                    tests/test_api_serve_contract.py -q
  -> 90 passed, 3 subtests passed

python3 -m pytest -q
  -> 2130 passed, 2706 subtests passed

git diff --check
  -> clean
```

The declared validator is the one recorded in `pyproject.toml`
(`[project.optional-dependencies] dev -> pytest==9.1.1`). No lint, coverage or
type-check tool is configured by this repository, and none was introduced. The
full suite passed both before the implementation commit and again on the
committed tree; no test was skipped, deselected or excluded to reach this
result.

Every collaborator in the new test file is a local fake: no test performs a
network call and no test constructs a production discovery provider. The
command's dependency on the provider is proven structurally, by AST inspection
of `castlearq/main.py`, not by running one.

### 28.8 Architectural boundary compliance

```text
B9.86 application boundary unchanged:                 YES
  castlearq/catalog_query_service.py                   unmodified
  castlearq/application_wiring.py                      unmodified
  castlearq/discovery.py                               unmodified
  castlearq/sources/huggingface_discovery.py           unmodified
  (verified: git diff --name-only over those four paths is empty)

ModelCatalogQueryService remains authoritative:        YES
  consumed as-is; no second validation authority was introduced

CLI does not depend on HuggingFaceDiscoveryProvider:   YES
  castlearq/main.py does not name the concrete discovery provider at all;
  the provider is constructed by the composition root
  (application_wiring.py:384-389), unchanged

next_cursor remains opaque and verbatim:               YES
  never decoded, validated, rebuilt, persisted or auto-followed

Candidate ordering preserved:                         YES
  asserted by test_candidate_order_is_the_boundary_order

No ranking, scoring, recommendation, fuzzy search:     YES
  none present; asserted by
  test_search_never_reorders_or_deduplicates and
  test_search_adds_no_field_beyond_the_discovery_domain

No deduplication:                                     YES
  a repeated repository is printed twice, as returned

No second discovery path:                             YES
  the only production call site of ModelDiscovery.search() remains
  catalog_query_service.py
```

The boundary `CLI -> Application -> Discovery port -> Discovery provider` is
preserved end to end.

### 28.9 Explicit non-goals

B9.87 did **not** implement any of the following. Each was verified absent from
the implementation commit `df99949`:

```text
Model Library UX                                  NOT IMPLEMENTED
GUI                                               NOT IMPLEMENTED
model cards                                       NOT IMPLEMENTED
quantization selection UI                         NOT IMPLEMENTED
compatibility warnings in the search path         NOT IMPLEMENTED
hardware suitability recommendations              NOT IMPLEMENTED
ranking / scoring / recommendation                NOT IMPLEMENTED
fuzzy search                                      NOT IMPLEMENTED
query rewriting                                   NOT IMPLEMENTED
caching                                           NOT IMPLEMENTED
persistence                                       NOT IMPLEMENTED
automatic pagination                              NOT IMPLEMENTED
acquisition from search                           NOT IMPLEMENTED
artifact selection                                NOT IMPLEMENTED
identity resolution                               NOT IMPLEMENTED
Chat changes                                      NOT IMPLEMENTED
a Conversation abstraction                        NOT IMPLEMENTED
Chat lifecycle migration out of api.py            NOT IMPLEMENTED
second runtime                                    NOT IMPLEMENTED
Ollama integration                                NOT IMPLEMENTED
multi-runtime execution                           NOT IMPLEMENTED
multi-GPU                                         NOT IMPLEMENTED
execution-path convergence (run vs execute)       NOT IMPLEMENTED
compatibility / evaluation / admission expansion  NOT IMPLEMENTED
fine-tuning                                       NOT IMPLEMENTED
datasets                                          NOT IMPLEMENTED
RAG / agents / MCP                                NOT IMPLEMENTED
telemetry / accounts / cloud services             NOT IMPLEMENTED
a new HTTP endpoint                               NOT IMPLEMENTED
any new dependency                                NOT IMPLEMENTED
  (requirements.txt remains standard library only; pyproject.toml unchanged)
unrelated main.py refactoring                     NOT PERFORMED
```

### 28.10 Findings and disposition

The repository configures no linter: `ruff` is installed in the maintainer's
environment but is not declared in `pyproject.toml`, and there is no
`ruff.toml`, `.ruff.toml`, `setup.cfg` or `.flake8`. It is therefore not part of
any validation contract, and its findings are advisory only.

```text
Repository-wide `ruff check .` at the implementation commit: 415 findings
  Pre-existing across the repository; unchanged by B9.87 in kind.

castlearq/main.py: 27 findings at df99949, 25 at its parent
  Delta = the two added imports. Breakdown: 22 F401, 1 F821, 2 FURB105,
  1 I001, 1 UP037. Every one of those rules is pre-existing in the file.

F1  tests/test_b987_cli_search.py raises 6 findings (4x SIM117, 2x SIM102)
    -> NON-BLOCKING
    All six are stylistic. Both rules already occur 33 times elsewhere in
    tests/, including the `assertRaises` + `mock.patch` + `redirect_*` nesting
    this file follows for consistency with the surrounding suite. Changing
    them would be a style edit to satisfy a tool the repository has not
    adopted. Nothing was auto-fixed.

F2  castlearq/main.py imports CatalogQueryErrorCategory without using it (F401)
    -> NON-BLOCKING
    One unused import name in a module that already carries 21 other F401
    findings at its parent. Cosmetic; removing it would be an unrelated lint
    cleanup, which this closure does not perform.

F3  castlearq/main.py adds a FURB105 empty `print("")` separator
    -> NON-BLOCKING / CONSISTENT WITH EXISTING STYLE
    The identical idiom is already present in the file and in the CLI
    presentation code it sits beside.
```

No finding is blocking. No lint finding was fixed, and no finding outside the
B9.87 changes was touched. The test file is **not** lint-clean and is not
claimed to be.

### 28.11 State transition and history preservation

Section 27 and the HADR record the state of B9.87 **at allocation time** and are
not rewritten. Those statements remain accurate for their own anchor:

```text
ORIGINAL ALLOCATION STATE (section 27 and the HADR, preserved):
  B9.87 = ALLOCATED
  B9.87 = NOT IMPLEMENTED
  B9.87 = NOT VERIFIED
  B9.87 = NOT CLOSED
  no `search` command existed at anchor aacbc8e

CURRENT CLOSURE STATE (this section, authoritative):
  B9.87 = ALLOCATED    (section 27 NAR, 5f0431166a06289aa455e080ed02e002119186ea)
  B9.87 = IMPLEMENTED   (df99949f922789f2b1cc4a507a090c86a01c5e84)
  B9.87 = VERIFIED      (section 28.7)
  B9.87 = CLOSED        (this section)
```

B9.87 was not allocated as closed, and no historical record has been rewritten
to suggest that it was. The supersession is stated by cross-reference only:
inside section 27.2, inside section 27.6, inside the HADR, and here. No
allocation evidence — corpus count, corpus digest, identifier set, corpus/HEAD
anchor, tree object or candidate-number analysis — was altered.

### 28.12 Product Vision alignment

`docs/product-vision-adr.md` is authoritative for product direction. B9.87
applied it and did not reopen any of its decisions.

```text
D1  — ENGAGED AND SATISFIED: reduces the uncertainty between user intent and
       local runtime invocation. The README states that results are remote,
       unverified metadata — what a source declares, not what a machine can
       run.
D3  — ENGAGED AND SATISFIED: makes the "find" stage of the JTBD reachable; it
       is now the first step of the CLI usage flow.
D5  — ENGAGED AND SATISFIED: exposes an existing core discovery step. No
       domain, no provider and no core-chain step was added or extended.
D6  — RESPECTED: Model Library UX remains NOT ALLOCATED and NOT authorized.
       The adapter presents what the boundary returns and interprets nothing.
D7  — NOT ENGAGED: no Chat change; the lifecycle migration remains deferred.
D8  — RESPECTED: GUI remains NOT AUTHORIZED; none was built.
D9  — RESPECTED: fine-tuning remains out of scope and still requires a
       separate ADR.
D10 — ENGAGED AND SATISFIED: the CLI surface consumes the shared application
       capability and adds no domain logic of its own.
D11 — ENGAGED AND SATISFIED: this block existed precisely to give an
       already-allocated, caller-less core capability a real caller, using an
       already-existing surface, before any new surface was considered.
D12 — RESPECTED, NOT ASSERTED: the product thesis remains an UNVALIDATED
       HYPOTHESIS. B9.87 makes and implies no claim of market demand, adoption
       or product-market fit, and does not present implementation completion as
       evidence of product validation. The two remain distinct, exactly as the
       ADR section 2 requires.
```

### 28.13 Repository state

```text
Implementation commit published successfully:  YES
HEAD == origin/main at closure time:             YES
                        both df99949f922789f2b1cc4a507a090c86a01c5e84
Implementation files remaining modified:        none
Production code changed by the closure:         none
Tests changed by the closure:                    none
Generated files added:                           none
Dependencies added:                              none
```

The implementation commit is the verified artifact and remains immutable; it is
never rewritten or amended. Only
`docs/roadmap-register-and-numbering-policy.md` and
`docs/B9.87-cli-catalog-query-caller-decision.md` are modified by this closure.
`docs/product-vision-adr.md` and `README.md` were not modified by it.

### 28.14 Closure authorization

```text
B9.87 STATUS: CLOSED
B9.87 IMPLEMENTATION: COMPLETE
B9.87 VERIFICATION: COMPLETE
B9.87 PUBLICATION: COMPLETE
B9.87 CLOSURE: COMPLETE

B9.88+: NOT ALLOCATED
Model Library UX: NOT ALLOCATED
Model Library GUI: NOT ALLOCATED
GUI: NOT AUTHORIZED
Product thesis: UNVALIDATED HYPOTHESIS (D12), unchanged by this closure
```

The HADR's ratified scope was realized exactly as decided: a minimal read-only
CLI adapter that presents what the closed B9.86 boundary returns and interprets
nothing. It is explicitly not a Model Library surface. No decision was reopened,
reinterpreted or amended. This closure allocates no successor identifier and
authorizes no future capability.
---

## 29. B9.88 — Number Allocation Record

`B9.88` is allocated as the next main block under section 6, on the evidence of
a section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.88 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified Human Architectural Decision Record
`docs/B9.88-chat-application-boundary-cli-caller-decision.md`, which was
preceded by a READ-ONLY next-roadmap-allocation audit. This section allocates
the number that carries that scope; it does not widen, reinterpret or extend
it.

### 29.1 Allocation evidence block

```text
Assigned Number:
  B9.88

Title:
  Chat Application Boundary: CLI Caller

Allocation Date:
  2026-10-02

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash.

  Recorded by the two-step mechanism already stated in section 11 and used
  identically by sections 19, 21, 23, 25 and 27: at authoring time the hash did
  not exist and the field read "PENDING — fixed by the next controlled commit
  that sets it to that hash"; a commit hash cannot be known before the commit
  exists, and writing a guessed value would be a fabricated identifier. The
  allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 28 — B9.87 Closure Record
Section for this allocation:
  section 29 — this record

Human Architectural Decision Record:
  docs/B9.88-chat-application-boundary-cli-caller-decision.md
  HADR STATUS: HUMAN-RATIFIED
  ARCHITECTURAL SCOPE: APPROVED
  NUMBER ALLOCATION: APPROVED BY THIS HADR; RECORDED IN SECTION 29
  IMPLEMENTATION: NOT STARTED

Corpus/HEAD Anchor:
  036669c2c923989f79e25631f98b0b06f59de971
  ("docs: close roadmap block B9.87"; main == HEAD == origin/main)

Branch:
  main

Working tree at anchor:
  tracked tree clean; no untracked files.

Corpus File Count:
  224 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  corpus integrity digest SHA-256 ->
    60551cddbb418214cc2fee0f91a93e9217d90abe4afed475ff2d564e5a5c72c3
  identifier-set SHA-256 ->
    82af630eed5bd9c78abd7368460aaa68b857e0e16196e5b8fc298073c228c0ce
  mechanism:
    git ls-tree -r HEAD --format='%(objectname)  %(path)' | sha256sum
      -> corpus integrity digest
    git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
      | LC_ALL=C sort -u | sha256sum
      -> identifier-set digest

Identifier Set:
  Highest main identifier in real use: B9.88 (this section)
  Preceding closed block: B9.87 (section 28), implemented at
    df99949f922789f2b1cc4a507a090c86a01c5e84, published on origin/main
  The identifier-set digest above is identical to the one recorded at the
    B9.87 allocation (section 27.1). B9.88 did not previously appear anywhere
    in the corpus, so the identifier set is unchanged by this record; B9.88
    enters the set through the set of allocated-and-recorded identifiers, not
    through a pre-existing corpus occurrence.

Pre-existing occurrences of B9.88 in the anchor corpus: 5
  All five are explicit non-allocations or recorded declines:
    - section 25.1 (B9.86 candidate analysis): "B9.88 and above —
      CONSIDERED AND DECLINED"
    - section 26.6: "B9.88+: NOT ALLOCATED"
    - section 27.1 (B9.87 corpus inspection): "B9.88 and above — 2 occurrences
      before this record, both inside this document"
    - section 27.1: "B9.88 and above — CONSIDERED AND DECLINED. Section 6
      requires the integer"
    - section 28.14: "B9.88+: NOT ALLOCATED"
  None of them allocates B9.88. No competing, competing-pending or conflicting
  identifier was found.

  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.88.x sub-block
    is assigned by this record.
  Conflict inspection: only main and origin/main exist as branches; the tags
    v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
    no commit outside this document's history introduces a B9.88 allocation.

Preceding Block:
  B9.87 — CLI Catalog Query Caller (First Production Caller for B9.86
  ModelCatalogQueryService)

Preceding Block Status:
  ALLOCATED (section 27), IMPLEMENTED (df99949f922789f2b1cc4a507a090c86a01c5e84),
  VERIFIED (section 28.7), CLOSED (section 28.14), published on origin/main

Highest Verified Allocation:
  B9.87

Rule in Force:
  Prospective monotonic main numbering (section 6)

Allocation Rule Applied:
  highest_verified_allocated_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
  next-roadmap-allocation audit and a human-ratified HADR

Allocation basis:
  B9.88 READ-ONLY Next Roadmap Allocation Audit, which concluded
  "PROPOSE B9.88 — Chat Application Boundary: CLI Caller through
  run_service.open_chat_session", followed by the project owner's ruling:
  "APPROVE B9.88 with the minimal CLI-only scope proposed by the audit."

Candidate Numbers Considered:
  B9.88 — SELECTED. highest_verified_allocated_block + 1 = B9.87 + 1. No
    allocation, reservation, provisional assignment or competing higher main
    identifier exists for it; every pre-existing occurrence is an explicit
    non-allocation or a recorded decline inside this document.
  B9.89 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
    immediately following the highest verified block; selecting 89 or above
    would leave 88 permanently unused and would contradict the prospective
    monotonic rule.
  B9.88.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
    integers of the form B9.x raise the main-block floor.
  Any lower or gap-filling identifier (for example B9.17 or B9.85) —
    CONSIDERED AND DECLINED. Section 6 fixes the floor at the highest VERIFIED
    allocated identifier; section 9 declares gaps NOT REUSED prospectively. No
    gap is claimed abandoned, freed, reserved or erroneous (section 13).

Selected Number:
  B9.88

Validity Reason:
  B9.87 is the highest main block assigned, implemented, verified and closed in
  the activation corpus at the anchor recorded above. B9.88 is the integer
  immediately following it, as section 6 requires. Every pre-existing
  occurrence of B9.88 in the corpus is an explicit non-allocation or a recorded
  decline, so no competing allocation exists. The number is therefore valid
  under the active rule.

Release Association:
  NOT YET DEFINED

Supersession:
  none — the earlier "B9.88 and above: NOT ALLOCATED" statements remain the
  accurate description of the corpus at their own anchors and are not
  rewritten; they are superseded by this record as a cross-reference only

Documented?:
  YES — this document (section 29) plus
  docs/B9.88-chat-application-boundary-cli-caller-decision.md

Number Allocation Record:
  PRESENT — section 29

Retrospective Record:
  NO — prospective allocation record

Human decisions pending:
  none — the HADR is HUMAN-RATIFIED and its architectural scope is APPROVED
```

### 29.2 Register entry for B9.88

```text
Block ID:                 B9.88
Name:                     Chat Application Boundary: CLI Caller
Status:                   CLOSED
Origin:                   this document, sections 29 (NAR) and 30 (Closure
                          Record)
Scope:                    see 29.3 — approved by the HADR
Non-goals:                see 29.4
Architectural decision:   HUMAN-RATIFIED Human Architectural Decision Record
                          (docs/B9.88-chat-application-boundary-cli-caller-decision.md),
                          preceding this allocation
Current State:            CLOSED — allocated by section 29, implemented at
                          ee5844fdc694e50e430a8b860d33a1c4d1e9ae58, corrected at
                          4459386dd8e3e9945a9ee35c307f616d628e42f1, verified
                          PASS, closed by section 30
Implementation Commit:    ee5844fdc694e50e430a8b860d33a1c4d1e9ae58
                          ("feat: route CLI chat through application service")
Correction Commit:        4459386dd8e3e9945a9ee35c307f616d628e42f1
                          ("fix: preserve chat selection warnings";
                          HADR Amendment A)
Allocation Commit:        66b3dcd4b9b5f1718e0034b37649053b91fc266b
                          ("docs: allocate roadmap block B9.88")
Allocation Anchor:        036669c2c923989f79e25631f98b0b06f59de971
                          ("docs: close roadmap block B9.87") — preserved from 29.1
Verification Result:      PASS — see section 30.7
Closure Commit:           PENDING — fixed by the next controlled commit that sets
                          it to that hash, per the two-step mechanism stated in
                          section 11 and used identically by sections 19, 21, 23,
                          25 and 27. A commit hash cannot be known before the
                          commit exists, and writing a guessed value would be a
                          fabricated identifier. The same field is left PENDING in
                          section 23.1 for B9.85 and section 26.2 for B9.86.
Release Association:      NOT YET DEFINED
Supersession:             none — the allocation-time state below is preserved
                          and superseded by explicit cross-reference only
Documented?:              YES — this document + the HADR
Number Allocation Record: PRESENT — section 29
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none
```

The lifecycle state asserted by this record **at allocation time** is, in full
and without implication of anything further:

```text
B9.88 = ALLOCATED
B9.88 = NOT IMPLEMENTED
B9.88 = NOT VERIFIED
B9.88 = NOT CLOSED
```

Those four statements remain the accurate description of B9.88 **at the
allocation anchor recorded in 29.1** and are **not** rewritten. The current,
authoritative lifecycle state is asserted by section 30.11:

```text
B9.88 = ALLOCATED   (section 29 NAR, 66b3dcd4b9b5f1718e0034b37649053b91fc266b)
B9.88 = IMPLEMENTED  (ee5844fdc694e50e430a8b860d33a1c4d1e9ae58)
B9.88 = VERIFIED     (section 30.7)
B9.88 = CLOSED       (section 30)
```

> **SUPERSESSION NOTE.** Earlier records in this document state that B9.88 and
> higher identifiers are not allocated (section 25.1; section 26.6; the
> recorded declines in sections 27.1 and 28.14). Those statements remain the
> accurate description of the corpus **at their own anchors** and are **not**
> rewritten by this section. The current, authoritative state of B9.88 is the
> one asserted above. The allocation evidence recorded in earlier sections is
> unchanged.

### 29.3 Scope attached to this allocation

The scope was fixed by the human-ratified HADR and is recorded here without
reinterpretation.

```text
Chat Application Boundary: CLI Caller
```

**Architectural purpose, as approved:**

```text
Route the existing CLI `chat` command through the already-established
application boundary run_service.open_chat_session, replacing the CLI's
duplicated resolver -> admission -> preparation -> runtime-session pipeline
with the shared application service.
```

**Architectural target:**

```text
CLI chat
    ↓
run_service.open_chat_session()
    ↓
existing chat runtime
```

**In scope:**

```text
- route the existing CLI `chat` command through
  run_service.open_chat_session
- preservation of current chat behaviour
- preserve existing admission handling: the admission already minted by
  _admit_for_preparation is forwarded into the application service, using the
  existing `admission` parameter
- preserve current CLI output, exit codes and user-visible warnings
- preserve current chat runtime semantics
- focused regression coverage proving the boundary is being consumed
- CLI documentation/help text updated only if the boundary change makes an
  existing statement inaccurate
```

**Dependency on already-closed contracts (consumed as-is, not redesigned):**

```text
run_service.open_chat_session — application boundary; already exported in
        run_service.py:72 and already production-called by
        castlearq/api.py:1234
run_service.prepare           — preparation stage inside that boundary
chat.LlamaCppChatSession      — the existing chat runtime primitive the service
                               launches; untouched by this allocation
EvaluationAdmission           — already minted by _admit_for_preparation and
                               forwarded, exactly as api.py:1242 does
evaluate_compatibility / to_admission — the single existing evaluation path
```

### 29.4 Explicit non-goals

```text
Chat architecture expansion
  a Conversation domain object
  conversation persistence
  chat history storage
  generic history policy
  prompt templating
  system-prompt policy
  session persistence
  conversation listing
  model selection UX
  chat marketplace / chat library
  a streaming application contract

Other execution work
  run / execute convergence
  run_service.run_once / run_model redesign
  ModelExecutionService adoption
  execution policy changes
  execution API changes

Product surfaces
  GUI
  Model Library UX
  Model Library GUI
  new HTTP endpoints
  new CLI commands

Runtime expansion
  second runtime
  Ollama runtime
  multi-GPU
  distributed execution

Training
  LoRA
  QLoRA
  datasets
  training jobs
  checkpoints
  fine-tuning

Infrastructure
  telemetry
  accounts
  cloud
  persistence
  new dependencies

Other
  unrelated refactoring
```

This allocation authorizes none of the above, opens no identifier for any of
them, and reserves none of them.

### 29.5 Architectural invariants approved with this allocation

Persisted without expansion or reinterpretation.

```text
- The boundary CLI -> Application (run_service.open_chat_session) -> existing
  chat runtime primitive is preserved.
- The CLI no longer duplicates the resolver -> admission -> preparation ->
  session-opening pipeline inline.
- Exactly one evaluation and exactly one admission per CLI `chat` invocation.
  The existing admission is forwarded; admission is neither redesigned nor
  duplicated.
- run_service.open_chat_session remains authoritative and is consumed as-is.
- The existing llama.cpp chat integration, its ready marker, its metrics block
  parsing, its cancellation semantics and its shutdown behaviour are untouched.
- No second resolver path, no second evaluation, no second admission.
- No new runtime and no new core-chain stage.
- No new user-facing surface: `castlearq chat` already exists and is unchanged.
- Existing CLI exit codes, output text and user-visible warnings are preserved.
- The `run` versus `execute` question is NOT resolved by this allocation and
  remains deferred.
- ModelExecutionService is NOT adopted by this allocation; it is recorded as
  existing architectural debt outside this scope.
```

### 29.6 Allocation versus implementation state

The distinction is explicit and is not implied anywhere in this record:

```text
This record allocates an identifier and attaches an already-approved scope.

B9.88  = ALLOCATED
B9.88  = NOT IMPLEMENTED
B9.88  = NOT VERIFIED
B9.88  = NOT CLOSED

IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
VERIFICATION AUTHORIZED:    NO
CLOSURE AUTHORIZED:         NO
```

The CLI `chat` command at this anchor still performs its preparation and
session-opening sequence inline: `castlearq/main.py:1813` `chat_model`
constructs `ModelStore`, `ModelArtifactResolver`, calls `resolver.resolve`,
`detect_llama_capability`, `_admit_for_preparation` and `_prepare`, then calls
`start_chat_session` directly at `main.py:1883`. It does **not** call
`run_service.open_chat_session`. Nothing in this record changes that.

The four statuses are distinct and are not conflated anywhere in this record:

```text
ALLOCATION  !=  IMPLEMENTATION  !=  VERIFICATION  !=  CLOSURE
```

This task establishes authorization only. No implementation work is authorized
beyond what will be performed in the subsequent controlled implementation phase.

### 29.7 Relation to the B9.87 allocation and closure

B9.87 (section 27 NAR; section 28 Closure Record) is the immediately preceding
block and is ALLOCATED, IMPLEMENTED (`df99949f922789f2b1cc4a507a090c86a01c5e84`),
VERIFIED and CLOSED, published on origin/main. B9.88 does not modify, reopen or
reinterpret B9.87.

B9.87 is not a technical prerequisite of B9.88: B9.88's dependency is
`run_service.open_chat_session`, which predates B9.87 and was introduced by
Block 3.1 of the run-service work. B9.87's relevance is documentary: its HADR
section 5.1 considered and deferred this exact candidate, and its section 5.2
recorded that the separate `run` / `execute` question remains a human decision.

### 29.8 Relation to the Product Vision ADR

`docs/product-vision-adr.md` is authoritative for product direction. B9.88
applies it without reopening any of its decisions. The register's own closure
language (28.14) already records `GUI: NOT AUTHORIZED` and
`Model Library UX: NOT ALLOCATED`; this allocation preserves both statements.

```text
D1  — NOT ENGAGED: no claim about the product problem is made.
D2  — NOT ENGAGED: no claim about the user population is made.
D3  — NOT ENGAGED: no claim about the Job To Be Done is made.
D4  — NOT ENGAGED: no claim about the runtime thesis is made.
D5  — RESPECTED: no new runtime and no new core-chain stage.
D6  — RESPECTED: Model Library UX remains NOT ALLOCATED and NOT authorized.
D7  — ENGAGED: B9.88 addresses the application-boundary seam D7 names for future
      Chat work. No Conversation abstraction is invented; D7 states none exists
      in the repository and forbids reconstructing one.
D8  — RESPECTED: GUI remains NOT AUTHORIZED.
D9  — RESPECTED: fine-tuning remains out of scope and requires a separate ADR.
D10 — ENGAGED: CLI and API consume one shared application capability rather
      than each owning lifecycle logic.
D11 — RESPECTED: no new user-facing surface is created; the existing `chat`
      surface is consumed.
D12 — RESPECTED: no claim of validated demand, adoption or product-market fit is
      made or implied. B9.88 is not product validation.
```

### 29.9 Human approval reference

```text
HADR STATUS:           HUMAN-RATIFIED
ARCHITECTURAL SCOPE:   APPROVED
NUMBER ALLOCATION:     APPROVED BY THIS NAR
IMPLEMENTATION:        NOT STARTED
```

> Implementation is **not** authorized by this record. The next required step
> is a separate implementation task that consumes B9.88. No source file, test,
> surface or refactoring is authorized here.

B9.80 through B9.87 are not modified by this record.

---

## 30. B9.88 — Closure Record

### 30.1 Closure status

B9.88 is formally **CLOSED**. The allocation record (section 29) and the Human
Architectural Decision Record
`docs/B9.88-chat-application-boundary-cli-caller-decision.md` both precede this
record and are not rewritten by it; where their status statements are
superseded, that supersession is stated explicitly as a cross-reference inside
section 29 and inside the HADR, and recorded here. This section attests that the
verified implementation exists, was published, and matches the allocated scope
exactly.

An independent READ-ONLY closure eligibility audit was performed before this
closure and returned `CLOSURE ELIGIBLE`. All ten criteria C1-C10 passed. Its
findings are dispositioned in 30.10 and none of them is blocking.

### 30.2 Implementation identity

```text
Block ID:
  B9.88

Name:
  Chat Application Boundary: CLI Caller

Allocation commit:
  66b3dcd4b9b5f1718e0034b37649053b91fc266b
    ("docs: allocate roadmap block B9.88")

Implementation commit:
  ee5844fdc694e50e430a8b860d33a1c4d1e9ae58
    ("feat: route CLI chat through application service")

Correction commit:
  4459386dd8e3e9945a9ee35c307f616d628e42f1
    ("fix: preserve chat selection warnings"; HADR Amendment A)

Allocation anchor (preserved from 29.1):
  036669c2c923989f79e25631f98b0b06f59de971
    ("docs: close roadmap block B9.87")

Branch:
  main

Publication state:
  pushed to origin/main (HEAD == origin/main at closure time)

Parent chain:
  4459386 -> ee5844f -> 66b3dcd -> 036669c (B9.87 closure)
```

Committed files, per commit, exclusively:

```text
66b3dcd  A  docs/B9.88-chat-application-boundary-cli-caller-decision.md
         M  docs/roadmap-register-and-numbering-policy.md   (section 29 NAR)

ee5844f  M  castlearq/main.py                       (+82 / -)  chat delegates to the boundary
         M  tests/test_main_chat.py                  (+176)     fixture retarget + boundary tests
         M  tests/test_main.py                       (+28 / -)   stale patch targets retargeted
         M  tests/test_shared_preparation.py         (+8 / -)    stale patch target retargeted

4459386  M  castlearq/run_service.py                (+11 / -2)  additive ChatSessionOpened.warnings
         M  castlearq/main.py                        (+6)        restore warning output
         M  docs/B9.88-...-decision.md               (+111)      Amendment A recorded
         M  tests/test_main_chat.py                  (+87)       warning preservation tests
         M  tests/test_chat_sessions.py              (+48 / -1)  propagation tests + stub field
```

`castlearq/api.py`, `castlearq/chat.py` and
`castlearq/application_wiring.py` were **not** modified by B9.88.

### 30.3 Human architectural decision reference

```text
docs/B9.88-chat-application-boundary-cli-caller-decision.md

DECISION:              HUMAN-RATIFIED
ARCHITECTURAL SCOPE:  APPROVED
IMPLEMENTATION:       approved by a separate implementation task
                       (ee5844fdc694e50e430a8b860d33a1c4d1e9ae58)

AMENDMENT A:           HUMAN-RATIFIED CLARIFICATION
                       (recorded in that document, section 15)
                       implemented at 4459386dd8e3e9945a9ee35c307f616d628e42f1
```

No decision in the HADR was reopened, reinterpreted or amended beyond the
narrowly authorized Amendment A. Sections 1-14 and Amendment A itself are
preserved verbatim.

### 30.4 Allocation reference

```text
Allocation record:      section 29 (B9.88 — Number Allocation Record)
Allocation commit:      66b3dcd4b9b5f1718e0034b37649053b91fc266b
Allocation anchor:      036669c2c923989f79e25631f98b0b06f59de971
Allocated scope:        section 29.3
Allocated non-goals:    section 29.4
Boundary invariants:    section 29.5
Preserved records:      section 29.6
Human-ratified scope:   "Route the existing CLI `chat` command through the
                        already-established application boundary
                        run_service.open_chat_session, replacing the CLI's
                        duplicated resolver -> admission -> preparation ->
                        runtime-session pipeline with the shared application
                        service."
```

### 30.5 Implemented scope

B9.88 implemented exactly the scope allocated in 29.3. The realized production
path is:

```text
CLI
  castlearq/main.py :: chat_model
  -> CLI-owned compatibility evaluation and admission
       _admit_for_preparation()
  -> application boundary
       run_service.open_chat_session()
  -> existing preparation and session pipeline
       resolver -> prepare -> session factory
  -> existing ChatSession
  -> existing CLI interaction loop
```

Realized as:

```text
- the CLI chat path no longer constructs ModelArtifactResolver, calls
  resolver.resolve(), calls _prepare(), or starts a session itself
- resolution, capability preparation and session opening are delegated to
  run_service.open_chat_session, the boundary the HTTP API already consumes
- the admission minted by the CLI is forwarded unchanged into the service
- the existing ChatDependencies.session_factory seam carries the CLI chunk
  callback, preserving incremental streaming without any new streaming
  contract
- existing CLI behaviour, output, exit codes, warnings, prompts, /exit, EOF,
  Ctrl+C, cancellation, session close and the interaction loop are preserved
- focused regression coverage for delegation, admission identity, single
  evaluation, streaming and service error mapping
```

The separation was verified by AST inspection of `chat_model`: `ModelArtifactResolver`,
`resolver`, `_prepare` and `prepare` are all absent from that function.

### 30.6 Amendment A — warning preservation

The closure eligibility audit confirmed that the first implementation commit
dropped one pre-existing user-visible behaviour: successful-path
`selection_warnings`, printed by the CLI before B9.88, were no longer surfaced,
because `open_chat_session` computed them during preparation but
`ChatSessionOpened` did not return them. That was a genuine regression against
the ratified warning-preservation invariant, and it was classified
`HUMAN DECISION REQUIRED`.

The owner authorized exactly one additive correction (HADR Amendment A). The
preserved chain is:

```text
RuntimeBackendSelector.select()      # MARGINAL verdict only
  -> ExecutionPreparation.selection_warnings
  -> ChatSessionOpened.warnings      # additive, defaulted to ()
  -> CLI stderr, "Warning: {warning}", before the successful banner
```

Implementation commit `4459386`. The API is unaffected: it reads only
`opened.session` and `opened.model_id`, and every existing `ChatSessionOpened`
construction site uses keyword arguments, so the defaulted field is compatible.

The sibling one-shot path already propagated the same data through
`RunOutcome.warnings`; this correction brings the chat path into consistency
with it and introduces no new concept.

### 30.7 Verification evidence

```text
python3 -m pytest tests/test_main_chat.py -q
  -> 21 passed

python3 -m pytest tests/test_chat_sessions.py -q
  -> 70 passed

python3 -m pytest tests/test_chat.py -q
  -> 26 passed

python3 -m pytest tests/test_main.py tests/test_shared_preparation.py -q
  -> 57 passed, 19 subtests passed

python3 -m pytest -q
  -> 2142 passed, 2706 subtests passed

git diff --check
  -> clean
```

Every one of these was executed on the final committed tree during the closure
eligibility audit. No test was skipped, deselected or excluded to reach these
results. The declared validator is the one recorded in `pyproject.toml`
(`[project.optional-dependencies] dev -> pytest==9.1.1`); no lint, coverage or
type-check tool is configured by this repository and none was introduced.

### 30.8 Architectural boundary compliance

```text
CLI -> Application -> existing chat runtime:         preserved
One evaluation per chat invocation:                 proven (test_chat_evaluates_compatibility_exactly_once)
One admission per chat invocation:                  proven (test_chat_forwards_the_cli_admission_unchanged,
                                                   identity-level)
One preparation operation:                          preserved (inside the boundary only)
Direct CLI resolver/preparation/session startup:    removed
chunk_callback added to open_chat_session:          NO — signature unchanged
Streaming mechanism:                                existing ChatDependencies.session_factory seam
API endpoint or contract introduced:                NO
Product expansion:                                  NONE
```

### 30.9 Explicit non-goals

B9.88 did **not** implement any of the following. Each was verified absent from
the B9.88 commits `ee5844f` and `4459386`:

```text
a Conversation domain object            NOT IMPLEMENTED
conversation persistence                NOT IMPLEMENTED
chat history storage                    NOT IMPLEMENTED
generic history policy                  NOT IMPLEMENTED
prompt templating / system-prompt policy NOT IMPLEMENTED
session persistence                     NOT IMPLEMENTED
conversation listing                    NOT IMPLEMENTED
model selection UX                      NOT IMPLEMENTED
chat marketplace / chat library         NOT IMPLEMENTED
a streaming application contract        NOT IMPLEMENTED
run / execute convergence               NOT IMPLEMENTED
run_service.run_once redesign           NOT IMPLEMENTED
run_service.run_model migration         NOT IMPLEMENTED
ModelExecutionService adoption          NOT IMPLEMENTED
execution policy or API changes        NOT IMPLEMENTED
GUI                                     NOT IMPLEMENTED
Model Library UX                        NOT IMPLEMENTED
Model Library GUI                       NOT IMPLEMENTED
new HTTP endpoints                      NOT IMPLEMENTED
new CLI commands                        NOT IMPLEMENTED
second runtime / Ollama / multi-GPU     NOT IMPLEMENTED
distributed execution                   NOT IMPLEMENTED
LoRA / QLoRA / datasets / training      NOT IMPLEMENTED
checkpoints / fine-tuning               NOT IMPLEMENTED
telemetry / accounts / cloud            NOT IMPLEMENTED
persistence                             NOT IMPLEMENTED
new dependencies                        NOT IMPLEMENTED
```

`run_model` retains its own CLI-owned pipeline untouched, as HADR section 10
requires. `ModelExecutionService` remains recorded architectural debt and was
not adopted, per HADR section 11.

### 30.10 Findings and disposition

```text
F1  The first implementation commit (ee5844f) dropped successful-path
    selection_warnings from the CLI chat output.
    -> GENUINE REGRESSION, DISPOSITIONED
    Classified by the READ-ONLY compliance audit as HUMAN DECISION REQUIRED.
    The owner authorized an additive ChatSessionOpened.warnings field
    (HADR Amendment A), implemented at 4459386 and verified in 30.7. Resolved;
    not blocking.

F2  Three pre-existing test fixtures patched castlearq.main seams that B9.88
    deliberately removed (ModelArtifactResolver, _prepare,
    start_chat_session).
    -> MECHANICAL FIXTURE ADAPTATION, DISPOSITIONED
    Patch targets were retargeted to the module that now owns each seam. No
    behavioral assertion was weakened or removed. The full suite passes.
```

No finding is blocking. No lint finding was fixed and no unrelated code was
touched.

### 30.11 State transition and history preservation

Section 29 and the HADR record the state of B9.88 **at allocation time** and are
not rewritten. Those statements remain accurate for their own anchor:

```text
ORIGINAL ALLOCATION STATE (section 29 and the HADR, preserved):
  B9.88 = ALLOCATED
  B9.88 = NOT IMPLEMENTED
  B9.88 = NOT VERIFIED
  B9.88 = NOT CLOSED
  the CLI chat pipeline was still duplicated at anchor 036669c

CURRENT CLOSURE STATE (this section, authoritative):
  B9.88 = ALLOCATED    (section 29 NAR, 66b3dcd4b9b5f1718e0034b37649053b91fc266b)
  B9.88 = IMPLEMENTED   (ee5844fdc694e50e430a8b860d33a1c4d1e9ae58)
  B9.88 = VERIFIED      (section 30.7)
  B9.88 = CLOSED        (this section)
```

B9.88 was not allocated as closed, and no historical record has been rewritten
to suggest that it was. The supersession is stated by cross-reference only:
inside section 29.2 and inside the HADR. No allocation evidence — corpus count,
corpus digest, identifier set, corpus/HEAD anchor or candidate-number analysis —
was altered.

### 30.12 Product Vision alignment

`docs/product-vision-adr.md` is authoritative for product direction. B9.88
applied it and did not reopen any of its decisions.

```text
D1-D4 — NOT ENGAGED: no claim about the product problem, the user population,
         the Job To Be Done or the runtime thesis is made.
D5  — RESPECTED: no new runtime and no new core-chain stage.
D6  — RESPECTED: Model Library UX remains NOT ALLOCATED and NOT authorized.
D7  — ENGAGED AND SATISFIED: B9.88 is precisely the application-boundary seam
       D7 names for future Chat work. The CLI now consumes the boundary the API
       already used. No Conversation abstraction was invented; D7 states none
       exists in the repository and forbids reconstructing one.
D8  — RESPECTED: GUI remains NOT AUTHORIZED.
D9  — RESPECTED: fine-tuning remains out of scope and requires a separate ADR.
D10 — ENGAGED AND SATISFIED: the CLI and the API now consume one shared
       application capability instead of each owning lifecycle logic.
D11 — RESPECTED: no new user-facing surface was created; the existing `chat`
       surface is consumed.
D12 — RESPECTED: no claim of validated demand, adoption or product-market fit is
       made or implied. B9.88 is not product validation.
```

### 30.13 Repository state

```text
Implementation commit published successfully:  YES
Correction commit published successfully:        YES
HEAD == origin/main at closure time:             YES
Implementation files remaining modified:        none
Production code changed by the closure:         none
Tests changed by the closure:                    none
Generated files added:                           none
Dependencies added:                              none
```

The implementation and correction commits are the verified artifacts and remain
immutable; neither was amended or rewritten. This closure modifies only
`docs/roadmap-register-and-numbering-policy.md` and
`docs/B9.88-chat-application-boundary-cli-caller-decision.md`.

### 30.14 Closure authorization

```text
B9.88 STATUS: CLOSED
B9.88 IMPLEMENTATION: COMPLETE
B9.88 VERIFICATION: COMPLETE
B9.88 PUBLICATION: COMPLETE
B9.88 CLOSURE: COMPLETE

B9.89+: NOT ALLOCATED
Model Library UX: NOT ALLOCATED
Model Library GUI: NOT ALLOCATED
GUI: NOT AUTHORIZED
Product thesis: UNVALIDATED HYPOTHESIS (D12), unchanged by this closure
```

The HADR's ratified scope was realized exactly as decided: the existing CLI
`chat` command now consumes the existing application boundary, and no new Chat
product architecture was introduced. No decision was reopened, reinterpreted or
amended beyond the owner's authorized Amendment A. This closure allocates no
successor identifier and authorizes no future capability.

---

## 31. B9.89 — Number Allocation Record

`B9.89` is allocated as the next main block under section 6, on the evidence of
a section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.89 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified Human Architectural Decision Record
`docs/run-boundary-architectural-decision.md`, which was preceded by a
READ-ONLY architectural decision audit and a READ-ONLY allocation audit. This
section allocates the number that carries that scope; it does not widen,
reinterpret or extend it.

### 31.1 Allocation evidence block

```text
Assigned Number:
  B9.89

Title:
  CLI Run Through Application Boundary

Allocation Date:
  2026-10-02

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash.

  Recorded by the two-step mechanism already stated in section 11 and used
  identically by sections 19, 21, 23, 25, 27 and 29: at authoring time the hash
  did not exist and the field read "PENDING — fixed by the next controlled
  commit that sets it to that hash"; a commit hash cannot be known before the
  commit exists, and writing a guessed value would be a fabricated identifier.
  The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 30 — B9.88 Closure Record
Section for this allocation:
  section 31 — this record

Human Architectural Decision Record:
  docs/run-boundary-architectural-decision.md
  STATUS: HUMAN-RATIFIED
  DECISION: ADOPT
  Q1: ADOPT               — run_once becomes the authoritative application
                            boundary for the CLI one-shot run surface
  Q2: SURFACE-OWNED       — admission continues to originate at the CLI
                            surface; run_once never evaluates or mints
  Q3: PRESERVE            — the existing observable CLI run contract must be
                            preserved
  Q4: REMAIN SEPARATE     — run and execute remain separate capabilities;
                            convergence is out of scope
  Q5: DOES NOT PARTICIPATE— ModelExecutionService is excluded and its
                            architecture-debt classification is unchanged
  NUMBER (at ratification): NONE — the decision record itself assigned no
                            identifier; this section performs the allocation

Corpus/HEAD Anchor:
  fe9cd03d19962059e76520d06d3b6acb30f0d139
  ("docs: close roadmap block B9.88"; main == HEAD == origin/main)

Branch:
  main

Working tree at anchor:
  tracked tree clean; one untracked file present,
  docs/run-boundary-architectural-decision.md — the human-ratified decision
  record. It is untracked at this anchor and is persisted by the allocation
  commit, which contains both this record and the decision record.

Corpus File Count:
  225 (git ls-files at allocation HEAD)

Corpus Integrity Evidence:
  corpus integrity digest SHA-256 ->
    dce0f798590029ad37c5cd42d86512c23018dca867720fd9d4c885ae35f93f00
  identifier-set SHA-256 ->
    202a3a296d2762a927ede55075be6096579bc9ea7088de21ebdbc64739df0358
  mechanism:
    git ls-tree -r HEAD --format='%(objectname)  %(path)' | sha256sum
      -> corpus integrity digest
    git ls-files -z | xargs -0 grep -hoE 'B9\.[0-9]+(\.[0-9]+)?'
      | LC_ALL=C sort -u | sha256sum
      -> identifier-set digest

Identifier Set:
  Highest main identifier in real use: B9.89 (this section)
  Preceding closed block: B9.88 (section 30), implemented at
    ee5844fdc694e50e430a8b860d33a1c4d1e9ae58 and corrected at
    4459386dd8e3e9945a9ee35c307f616d628e42f1, published on origin/main
  B9.89 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.89 in the anchor corpus: 2
  Both are explicit non-allocations:
    - section 29.1 (B9.88 candidate analysis): "B9.89 and above —
      CONSIDERED AND DECLINED. Section 6 requires the integer"
    - section 30.14: "B9.89+: NOT ALLOCATED"
  None of them allocates B9.89. No competing, competing-pending or
  conflicting identifier was found.

  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.89.x sub-block
    is assigned by this record.
  Conflict inspection: only main and origin/main exist as branches; the tags
    v0.1.0, v0.2.0, v0.3.0 and v0.4.0 are release tags, not block allocations;
    no commit outside this document's history introduces a B9.89 allocation.

Preceding Block:
  B9.88 — Chat Application Boundary: CLI Caller

Preceding Block Status:
  ALLOCATED (section 29), IMPLEMENTED
  (ee5844fdc694e50e430a8b860d33a1c4d1e9ae58), corrected at
  (4459386dd8e3e9945a9ee35c307f616d628e42f1), VERIFIED (section 30.7),
  CLOSED (section 30.14), published on origin/main

Highest Verified Allocation:
  B9.88

Rule in Force:
  Prospective monotonic main numbering (section 6)

Allocation Rule Applied:
  highest_verified_allocated_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled corpus inspection + formal registration, preceded by a READ-ONLY
  architectural decision audit, a human-ratified HADR and a READ-ONLY
  allocation audit that returned ALLOCATION READY

Allocation basis:
  CastleArq run/run_once Architectural Decision Audit, followed by the project
  owner's ratification of the decision record
  docs/run-boundary-architectural-decision.md (ADOPT), followed by the
  B9.89 Allocation Audit which classified the block ALLOCATION READY.

Candidate Numbers Considered:
  B9.89 — SELECTED. highest_verified_allocated_block + 1 = B9.88 + 1. No
    allocation, reservation, provisional assignment or competing higher main
    identifier exists for it; every pre-existing occurrence is an explicit
    non-allocation or a recorded decline inside this document.
  B9.90 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
    immediately following the highest verified block; selecting 90 or above
    would leave 89 permanently unused and would contradict the prospective
    monotonic rule.
  B9.89.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
    integers of the form B9.x raise the main-block floor.
  Any lower or gap-filling identifier — CONSIDERED AND DECLINED. Section 6 fixes
    the floor at the highest VERIFIED allocated identifier; section 9 declares
    gaps NOT REUSED prospectively. No gap is claimed abandoned, freed, reserved
    or erroneous (section 13).

Selected Number:
  B9.89

Validity Reason:
  B9.88 is the highest main block assigned, implemented, verified and closed in
  the activation corpus at the anchor recorded above. B9.89 is the integer
  immediately following it, as section 6 requires. Every pre-existing
  occurrence of B9.89 in the corpus is an explicit non-allocation or a recorded
  decline, so no competing allocation exists. The number is therefore valid
  under the active rule.

Release Association:
  NOT YET DEFINED

Supersession:
  none — the earlier "B9.89 and above: NOT ALLOCATED" statement remains the
  accurate description of the corpus at its own anchor and is not rewritten;
  it is superseded by this record as a cross-reference only

Documented?:
  YES — this document (section 31) plus
  docs/run-boundary-architectural-decision.md

Number Allocation Record:
  PRESENT — section 31

Retrospective Record:
  NO — prospective allocation record

Human decisions pending:
  none — the decision record is HUMAN-RATIFIED with DECISION: ADOPT
```

### 31.2 Register entry for B9.89

```text
Block ID:                 B9.89
Name:                     CLI Run Through Application Boundary
Status:                   ALLOCATED
Origin:                   this document, section 31 (NAR)
Scope:                    see 31.3 — approved by the HADR
Non-goals:                see 31.4
Architectural decision:   HUMAN-RATIFIED Human Architectural Decision Record
                          (docs/run-boundary-architectural-decision.md),
                          DECISION: ADOPT, preceding this allocation
Current State:            ALLOCATED — allocated by section 31
Implementation Commit:    NONE — NOT IMPLEMENTED
Verification Result:      NONE — NOT VERIFIED
Closure Commit:           NONE — NOT CLOSED
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document + the decision record
Number Allocation Record: PRESENT — section 31
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none
```

The lifecycle state asserted by this record is, in full and without implication
of anything further:

```text
B9.89 = ALLOCATED
B9.89 = NOT IMPLEMENTED
B9.89 = NOT VERIFIED
B9.89 = NOT CLOSED
```

> **SUPERSESSION NOTE.** Earlier records in this document state that B9.89 and
> higher identifiers are not allocated (section 29.1; section 30.14). Those
> statements remain the accurate description of the corpus **at their own
> anchors** and are **not** rewritten by this section. The current,
> authoritative state of B9.89 is the one asserted above.

### 31.3 Scope attached to this allocation

The scope was fixed by the HUMAN-RATIFIED decision record and is recorded here
without reinterpretation.

```text
CLI Run Through Application Boundary
```

**Architectural purpose, as approved:**

```text
Route the existing CLI one-shot `run` surface through the already-authorized
`run_once` application boundary while:
  - preserving surface-owned admission
  - preserving the existing observable CLI contract
  - eliminating duplicated resolver/preparation/runtime orchestration from
    the CLI
```

**Architectural target:**

```text
CLI run
  ├─ argument validation
  ├─ ModelStore / runtime capability acquisition
  ├─ compatibility evaluation and admission creation
  ├─ run_once(..., admission=admission)
  └─ presentation

run_once (authoritative)
  ├─ resolution
  ├─ preparation (admission gate, preflight, selection)
  ├─ runtime invocation
  └─ RunOutcome / typed errors
```

**Dependency on already-closed contracts (consumed as-is, not redesigned):**

```text
run_service.run_once    — the application boundary being adopted; already
                          implemented, injectable and tested; requires an
                          admission and never mints one
run_service.prepare     — preparation stage inside that boundary, unchanged
_run_service._require_admission — the B9.78 fail-closed admission gate
RunOutcome              — structured successful result, including warnings
RunServiceError family  — ModelNotFoundError, RunPreparationFailedError,
                          RunExecutionFailedError
evaluate_model_compatibility / to_admission — the single surface-owned
                          evaluation and admission path (B9.78)
LlamaCppRunner          — runtime invocation, owned by the boundary
execute_model           — NOT touched; `run` and `execute` remain separate
```

**In scope:**

```text
- CLI `run` delegates to `run_once`
- CLI retains argument validation
- CLI retains ModelStore / runtime capability acquisition
- CLI retains compatibility evaluation
- CLI retains admission creation
- the existing admission is forwarded unchanged into run_once
- run_once owns resolution, preparation and runtime invocation
- successful output is preserved
- warning behaviour is preserved
- failure and error behaviour is preserved
- focused regression tests for delegation, admission and contract
  compatibility
```

### 31.4 Explicit non-goals

```text
execute_model convergence (HADR Q4)
ModelExecutionService participation or modification (HADR Q5)
any Chat change or redesign
Model Library UX
GUI
a new runtime, Ollama integration, or multi-GPU
fine-tuning, LoRA, QLoRA
datasets or training jobs
a conversation abstraction
persistence or chat history
streaming redesign
telemetry, accounts, cloud
a new generic execution abstraction
a redesign of RunOutcome or of the error hierarchy beyond what strict
  contract preservation requires
unrelated CLI refactoring
unrelated architectural change
```

This allocation authorizes none of the above, opens no identifier for any of
them, and reserves none of them.

### 31.5 Acceptance criteria

Persisted from the READ-ONLY allocation audit and not weakened here.

```text
C1  CLI run invokes run_once
C2  CLI no longer executes resolver, preparation or runner itself, except
    where explicitly required for presentation or existing surface
    responsibilities
C3  CLI remains responsible for evaluation and admission; run_once neither
    evaluates nor mints
C4  Exactly one compatibility evaluation occurs per CLI run invocation
C5  Existing successful stdout remains compatible
C6  Warning text, semantics, destination and ordering remain compatible
C7  Error presentation and exit behavior remain compatible
C8  RunOutcome and the typed-error contract remain coherent
C9  No run -> execute_model convergence
C10 No unrelated architectural change
```

The two observable deltas identified by the architectural decision audit —
error-message mapping, and warning merge/delivery on failure paths — are
contractual obligations under C6 and C7, not accepted side-effects.

### 31.6 Verification plan

Defined at allocation time. No verification has been performed.

```text
Focused suites
  tests/test_main.py -q                     (CLI run surface)
  tests/test_run_service_errors.py -q       (run_service error contract)
  tests/test_shared_preparation.py -q       (shared preparation wiring)
  plus any other focused suite the delta
  actually touches

Structural verification
  AST / call-graph proof that CLI run calls run_once
  AST proof that CLI run no longer references ModelArtifactResolver,
  _prepare or LlamaCppRunner for its own execution path

Behavioural verification
  exactly-one-evaluation      — one evaluate_model_compatibility and one
                                to_admission per invocation
  admission identity           — the same admission object is forwarded
                                unchanged into run_once
  missing-admission fail-closed— None or a non-admitting verdict is denied,
                                never bypassed
  successful output            — stdout content and exit 0 unchanged
  marginal warning             — warning text, ordering and stderr destination
                                unchanged
  preparation failure          — exit 1 and existing "Run error:" text
  runtime failure              — exit 1 with the existing error text

Whole-repository verification
  python3 -m pytest -q
  git diff --check
```

### 31.7 Architectural invariants approved with this allocation

Persisted without expansion or reinterpretation.

```text
- run_once remains the authoritative application boundary for CLI one-shot
  execution and is consumed as-is.
- Admission authority is unchanged: the CLI surface evaluates compatibility and
  mints admission; run_once validates the supplied admission and fails closed.
  Application boundary != admission authority.
- Exactly one evaluation and exactly one admission per CLI run invocation.
- run_once does not gain the power to evaluate compatibility or mint an
  admission.
- The observable CLI run contract is preserved: exit behavior, "Run error:"
  presentation, successful stdout, warning text, warning destination, warning
  semantics and relevant failure-path behavior.
- RunOutcome and the RunServiceError family remain coherent and are not
  redesigned.
- `run` and `execute` remain separate application capabilities; no convergence
  is authorized.
- ModelExecutionService is not adopted, not modified and not removed; its
  architecture-debt classification is unchanged.
- No new user-facing surface, no new runtime, no new dependency.

### 31.8 Allocation versus implementation state

The distinction is explicit and is not implied anywhere in this record:

```text
This record allocates an identifier and attaches an already-approved scope.

B9.89  = ALLOCATED
B9.89  = NOT IMPLEMENTED
B9.89  = NOT VERIFIED
B9.89  = NOT CLOSED

IMPLEMENTATION AUTHORIZED: NO
TESTS AUTHORIZED:           NO
VERIFICATION AUTHORIZED:    NO
CLOSURE AUTHORIZED:         NO
```

At this anchor the CLI one-shot `run` path still performs its own resolver,
preparation and runner invocation inline, and `run_service.run_once` still has
no production caller. Nothing in this record changes that.

```text
ALLOCATION != IMPLEMENTATION != VERIFICATION != CLOSURE
```

### 31.9 Product Vision alignment

`docs/product-vision-adr.md` is authoritative for product direction. B9.89
applies it without reopening any of its decisions. The register's own closure
language (30.14) already records `GUI: NOT AUTHORIZED` and
`Model Library UX: NOT ALLOCATED`; this allocation preserves both statements.

```text
D1-D4 — NOT ENGAGED: no claim about the product problem, the user population,
         the Job To Be Done or the runtime thesis is made.
D5  — RESPECTED: no new runtime and no new core-chain stage.
D6  — RESPECTED: Model Library UX remains NOT ALLOCATED and NOT authorized.
D7  — RESPECTED: no Chat change; the chat boundary is untouched.
D8  — RESPECTED: GUI remains NOT AUTHORIZED.
D9  — RESPECTED: fine-tuning remains out of scope and requires a separate ADR.
D10 — ENGAGED: the CLI surface consumes the shared application capability for
      one-shot execution instead of duplicating it.
D11 — RESPECTED: no new user-facing surface is created; the existing `run`
      surface is consumed. An allocated core capability gains its real caller.
D12 — RESPECTED: no claim of validated demand, adoption or product-market fit
      is made or implied. B9.89 is not product validation.
```

### 31.10 Human approval reference

```text
DECISION RECORD STATUS:  HUMAN-RATIFIED
DECISION:                ADOPT
NUMBER ALLOCATION:       APPROVED BY THIS NAR
IMPLEMENTATION:          NOT STARTED
```

> Implementation is **not** authorized by this record. The next required step
> is a separate implementation task that consumes B9.89. No source file, test,
> surface or refactoring is authorized here.

B9.80 through B9.88 are not modified by this record.

### 31.11 Cross-reference — HADR Amendment A

Recorded for traceability only. This subsection changes nothing allocated in
31.1-31.10.

```text
HADR Amendment A:   HUMAN-RATIFIED ARCHITECTURAL DECISION
                    (docs/run-boundary-architectural-decision.md, section 16)
                    recorded after the formal verification audit, which
                    returned VERIFICATION BLOCKED.

Allocation record:  UNCHANGED (number, identity, allocation commit)
Implementation:     UNCHANGED — IMPLEMENTED at
                    5ee4bb5b20560ec11f7c05e2ad93a49967410068
Verification:       NOT VERIFIED — audit returned BLOCKED; not marked passed
Closure:            NOT CLOSED
```

Amendment A records two human decisions on the B9.89 observable contract:

```text
16.2 runtime stderr      PRESERVE   — corrective implementation REQUIRED,
                                      NOT YET AUTHORIZED, NOT IMPLEMENTED
16.3 warning multiplicity DEDUPLICATE — RATIFIED, no corrective change required
```

No closure record is created by this subsection, and verification is not marked
passed. The historical chain (allocation -> implementation -> verification ->
finding -> human decision -> corrective implementation -> re-verification ->
closure) is preserved and remains open at "human decision".

---

## 32. B9.89 — Closure Record

```text
B9.89 STATUS:        CLOSED
B9.89 IMPLEMENTATION: COMPLETE
B9.89 VERIFICATION:   COMPLETE
B9.89 PUBLICATION:    NOT PERFORMED (local only; not pushed at closure time)
B9.89 CLOSURE:        COMPLETE

B9.90+: NOT ALLOCATED
Model Library UX: NOT ALLOCATED
Model Library GUI: NOT ALLOCATED
GUI: NOT AUTHORIZED
```

Sections 31.1 through 31.11 are preserved verbatim. In particular, 31.8 and 31.10
remain the **allocation-time** statement ("NOT IMPLEMENTED", "NOT VERIFIED",
"NOT CLOSED") and are not rewritten by this closure; this section is the
contemporaneous lifecycle record that follows them, exactly as section 30
followed section 29 for B9.88.

### 32.1 Title and allocation

```text
Title:              B9.89 — CLI Run Through Application Boundary
Allocation Commit:  9fdd60da6d4b4b308f7c9a09b518b3da3d7d2344
Allocation anchor:  fe9cd03d19962059e76520d06d3b6acb30f0d139
                    (the pre-implementation B9.88 closure state)
Decision record:    docs/run-boundary-architectural-decision.md
                    (HUMAN-RATIFIED, DECISION REFERENCE FOR B9.89)
```

### 32.2 Commit chain

```text
Allocation commit:              9fdd60da6d4b4b308f7c9a09b518b3da3d7d2344
                                ("docs: allocate roadmap block B9.89")
Original implementation commit: 5ee4bb5b20560ec11f7c05e2ad93a49967410068
                                ("feat: route CLI run through application service")
Amendment commit:               b356488f324cebf2d35e0d75ff4f5e69ffa419c7
                                ("docs: record B9.89 observable contract amendment")
Corrective implementation:      b266c887fd30a26d0bf1ee0a775ea69b52b6e486
                                ("fix: preserve runtime stderr through run boundary")
Closure commit:                 the commit that contains this section 32
                                (a commit cannot contain its own hash; this
                                record is committed in that commit)
```

### 32.3 Corrective history — stated accurately

The first formal verification did **not** pass. It found two deviations from the
observable contract and returned BLOCKED:

```text
(1) RUNTIME STDERR WAS NOT TRANSPORTED. The pre-B9.89 CLI emitted the
    runtime's result.stderr to CLI stderr on both the success and the failure
    path. RunOutcome carried only (model_id, output, exit_code, warnings) and
    RunExecutionFailedError carried only (message, error_code), so runtime
    diagnostics were silently discarded.

(2) WARNING MULTIPLICITY DIFFERED. The pre-B9.89 failure path concatenated
    _error_warnings(error) + _prepare_warnings(error) and could repeat a
    warning line; the application boundary exposes a deduplicated merge.
```

Human Amendment A (HADR section 16) then decided both points explicitly:

```text
RUNTIME STDERR:       PRESERVE    — corrective implementation required
WARNING MULTIPLICITY: DEDUPLICATE — RATIFIED, no corrective change required
```

The corrective implementation resolved (1) by transporting
`ExecutionResult.stderr` through `RunOutcome.stderr` on success and
`RunExecutionFailedError.stderr` on failure, and by printing it from the CLI. It
retained the human-ratified deduplication from (2) unchanged.

The original implementation at 5ee4bb5 did **not** satisfy the amended
observable contract and was never retroactively recorded as having done so; it
remained non-conforming until the corrective commit.

### 32.4 Final implementation result

The final B9.89 implementation:

- routes the CLI one-shot `run` through `run_once`;
- keeps compatibility evaluation and admission minting at the CLI/application
  surface, which is Q2's surface-owned admission decision;
- forwards the **exact** admission object into `run_once`;
- removes the CLI's direct resolution, preparation and runtime invocation
  orchestration;
- preserves runtime stderr through the application boundary;
- preserves success ordering: stdout -> runtime stderr -> warnings;
- preserves failure ordering: runtime stderr -> `Run error:` -> warnings;
- preserves warning deduplication as ratified by Amendment A;
- preserves exit codes 0 (success), 1 (runtime/preparation failure) and
  2 (usage error);
- leaves `run` and `execute` separate; convergence remains deferred (Q4);
- does not involve `ModelExecutionService` (Q5).

No architectural claim beyond the ratified HADR is made by this closure.

### 32.5 Verification result

```text
Formal verification (first pass):          BLOCKED
Human Amendment A (decisions recorded):    b356488
Formal corrective re-verification:         PASSED
Formal closure eligibility audit:          PASSED

Focused tests:   71 passed, 23 subtests passed
Full suite:      2151 passed, 2706 subtests passed
                 0 failed, 0 skipped, exit 0
git diff --check: PASS

Final verified HEAD before closure: b266c887fd30a26d0bf1ee0a775ea69b52b6e486
```

### 32.6 Scope

Files touched by the original implementation commit (5ee4bb5):

```text
castlearq/main.py
castlearq/run_service.py
tests/test_main.py
tests/test_shared_preparation.py
tests/test_compatibility_report.py
tests/test_gpu_diagnosis_cli.py
```

The two extra test files were audited as mechanical retargeting required to
preserve their "no runtime invoked" guards after `castlearq.main.LlamaCppRunner`
ceased to exist; that decision is not reopened here.

Files touched by the corrective implementation commit (b266c88):

```text
castlearq/main.py
castlearq/run_service.py
tests/test_main.py
tests/test_run_service_errors.py
```

Not modified by B9.89: `castlearq/api.py`, `castlearq/chat.py`,
`castlearq/runner.py`, `castlearq/execute_model.py`,
`castlearq/execution_service.py`, and no product-vision document. No telemetry,
persistence, accounts, GUI, Model Library, Hugging Face UX, fine-tuning, second
runtime, Ollama or multi-GPU work was introduced.

### 32.7 Repository state at closure

```text
Working tree clean:                              YES
Production code changed by this closure:         none
Tests changed by this closure:                   none
Documentation changed by this closure:           this file, plus the HADR
Branches pushed at closure time:                 none
```

The implementation, amendment and corrective commits are the verified
artifacts and remain immutable; none was amended or rewritten by this closure.
This closure modifies only `docs/roadmap-register-and-numbering-policy.md` and
`docs/run-boundary-architectural-decision.md`.

B9.80 through B9.88 are not modified by this closure. This closure allocates no
successor identifier and authorizes no future capability.
---

## 33. B9.90 — Number Allocation Record

`B9.90` is allocated as the next main block under section 6, on the evidence of
a section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.90 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified Human Architectural Decision Record for the revision-aware
acquisition locator (DownloadPlanner as sole primary authority for the
`revision ↔ download_url` invariant), which was preceded by a READ-ONLY
architectural decision audit, a READ-ONLY ADR-preparation audit, a human
architectural decision, and a READ-ONLY formal roadmap allocation audit. This
section allocates the number that carries that scope; it does not widen,
reinterpret or extend it.

### 33.1 Allocation evidence block

```text
Assigned Number:
  B9.90

Title:
  Planner-Canonicalized Revision-Aware Acquisition Locator

Allocation Date:
  2026-10-03

Allocation Commit:
  8cf2ef9de03a3b5d32cec606e0fdda97f9dfe204
  ("docs: allocate roadmap block B9.90")
```
  Recorded by the two-step mechanism already stated in section 11 and used
  identically by sections 19, 21, 23, 25, 27, 29 and 31: at authoring time the
  hash did not exist and the field read "PENDING — fixed by the next controlled
  commit that sets it to that hash"; a commit hash cannot be known before the
  commit exists, and writing a guessed value would be a fabricated identifier.
  The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 32 — B9.89 Closure Record
Section for this allocation:
  section 33 — this record

Human Architectural Decision Record:
  Planner-as-canonical-authority decision for revision ↔ download_url
  STATUS: HUMAN-RATIFIED
  DECISION: ADOPT
  Primary authority:            DownloadPlanner
  URL construction authority:   DownloadPlanner (canonical derivation + validation)
  Defensive validation:         Downloader, aligned to the planner rule only
  Transport-only:               HuggingFaceDiscoveryProvider, B9.84 selection,
                                B9.82 acquisition mapper
  ArtifactSpec:                 declared-provenance carrier only; no
                                construction-time cross-field invariant
  NUMBER (at ratification): NONE — the decision record itself assigned no
                            identifier; this section performs the allocation

Corpus/HEAD Anchor:
Corpus File Count:
  recorded by the allocation audit at the anchor above.

Identifier Set:
  Highest main identifier in real use after this section: B9.90 (this section)
  Preceding closed block: B9.89 (sections 31-32), CLOSED at
    55b1cbabe2714d3bdbe931273d3714398c818f34.
  B9.90 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.90 in the anchor corpus: 2
  Both are explicit non-allocations:
    - section 31.1 (B9.89 candidate analysis): "B9.90 and above —
      CONSIDERED AND DECLINED. Section 6 requires the integer"
    - section 32 header block: "B9.90+: NOT ALLOCATED"
  None of them allocates B9.90. No competing, competing-pending or
  conflicting identifier was found.

  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.90.x sub-block
    is assigned by this record.

Preceding Block:
  B9.89 — CLI Run Through Application Boundary

Preceding Block Status:
  ALLOCATED (section 31), IMPLEMENTED, VERIFIED, CLOSED (section 32),
  published state main == HEAD == origin/main at the anchor above.

Highest Verified Allocation:
  B9.89
```

Candidate Numbers Considered:

```text
B9.90 — SELECTED. highest_verified_allocated_block + 1 = B9.89 + 1. No
  allocation, reservation, provisional assignment or competing higher main
  identifier exists for it; every pre-existing occurrence is an explicit
  non-allocation or a recorded decline inside this document.
B9.91 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
  immediately following the highest verified block; selecting 91 or above
  would leave 90 permanently unused and would contradict the prospective
  monotonic rule. B9.91+ REMAINS NOT ALLOCATED by this record.
B9.90.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
  integers of the form B9.x raise the main-block floor.
Any lower or gap-filling identifier — CONSIDERED AND DECLINED. Section 6 fixes
  the floor at the highest VERIFIED allocated identifier; section 9 declares
  gaps NOT REUSED prospectively. No gap is claimed abandoned, freed, reserved
  or erroneous (section 13).
```

Selected Number:

```text
B9.90
```

Validity Reason:

```text
B9.89 is the highest main block assigned, implemented, verified and closed in
the activation corpus at the anchor recorded above. B9.90 is the integer
immediately following it, as section 6 requires. Every pre-existing
occurrence of B9.90 in the corpus is an explicit non-allocation or a recorded
decline, so no competing allocation exists. The number is therefore valid
under the active rule.
```

Release Association:

```text
NOT YET DEFINED
```

Supersession:

```text
none — the earlier "B9.90+: NOT ALLOCATED" statements remain the
accurate description of the corpus at their own anchors and are not rewritten;
they are superseded by this record as a cross-reference only
```

Documented?:

```text
YES — this document (section 33) plus the human-ratified planner-authority
decision record referenced in 33.1
```

Number Allocation Record:

```text
PRESENT — section 33
```

Retrospective Record:

```text
NO — prospective allocation record
```

Human decisions pending:

```text
none — the planner-authority decision record is HUMAN-RATIFIED with DECISION: ADOPT
```

  55b1cbabe2714d3bdbe931273d3714398c818f34
  ("docs: close roadmap block B9.89"; main == HEAD == origin/main)

Branch:
  main

### 33.2 Register entry for B9.90

```text
Block ID:                 B9.90
Name:                     Planner-Canonicalized Revision-Aware Acquisition Locator
Status:                   CLOSED
Origin:                   this document, section 33 (NAR)
Scope:                    see 33.3 — fixed by the HADR, recorded without reinterpretation
Non-goals:                see 33.4
Architectural decision:   HUMAN-RATIFIED Human Architectural Decision Record
                          (planner-as-canonical-authority for revision ↔ download_url),
                          DECISION: ADOPT, preceding this allocation
Current State:            CLOSED — allocated by section 33; implemented,
                          verified and closed by the controlled closure
                          transition recorded in this section
Implementation Commit:    e2f520822f356e36acb2b03f0494edcfdcb37bb0
                          ("feat: canonicalize revision-aware acquisition locators")
Verification Result:      COMPLETE — evidence audits PASSED; full test suite
                          2160 passed, 2718 subtests passed, 0 failures,
                          0 errors; closure readiness audit:
                          READY FOR FORMAL CLOSURE
Closure Commit:           the commit that contains this closure update
                          (a commit cannot contain its own hash; this record is
                          committed in that commit — the section 32.2 convention)
Release Association:      NOT YET DEFINED
Supersession:             none
Documented?:              YES — this document + the decision record
Number Allocation Record: PRESENT — section 33
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none
```

The lifecycle state asserted by this record is, in full and without implication
of anything further:

```text
B9.90 = ALLOCATED
B9.90 = IMPLEMENTED
B9.90 = VERIFIED
B9.90 = CLOSED
```

> **SUPERSESSION NOTE.** Earlier records in this document state that B9.90 and
> higher identifiers are not allocated (section 31.1; section 32 header block).
> Those statements remain the accurate description of the corpus **at their own
> anchors** and are **not** rewritten by this section. The current,
> authoritative state of B9.90 is the one asserted above.

### 33.3 Scope attached to this allocation

The scope was fixed by the HUMAN-RATIFIED decision record and is recorded here
without reinterpretation.

```text
Planner-Canonicalized Revision-Aware Acquisition Locator
```

**Canonical invariant, as decided:**

```text
revision == None
    → acquisition URL path uses /resolve/main/

revision == R (R satisfies the existing 40-hex revision contract)
    → acquisition URL path uses /resolve/R/
```

**Architectural authority, as decided:**

```text
Primary authority:          DownloadPlanner
URL construction authority: DownloadPlanner (canonical derivation + validation)
Defensive validation:       Downloader, aligned to the planner rule only
Transport-only:             HuggingFaceDiscoveryProvider, B9.84 selection,
                            B9.82 acquisition mapper
ArtifactSpec:               declared-provenance carrier only; no
                            construction-time cross-field invariant
```

**Key semantic change planned for B9.90:**

```text
Planner:
reject revision/URL mismatch
        ↓
canonicalize revision-aware locator
        ↓
validate canonical locator
```

The planner becomes the sole canonical acquisition-locator derivation
authority. The downloader remains defensive only and MUST NOT become an
independent URL-construction authority.

**Dependency on already-closed contracts (consumed as-is, not redesigned):**

```text
B9.80 — Model Discovery domain contract (DiscoveredArtifact / provider port)
B9.81 — Hugging Face discovery provider (L1 remote metadata, R1
         zero-acquisition-coupling)
B9.82 — Discovery-to-Acquisition Boundary (pure 1:1 translation)
B9.83 — Revision-aware acquisition (ArtifactSpec.revision, manifest
         persistence, revision-aware planner URL contract, OD-1)
B9.84 — Selection boundary (revision as selection criterion, before mapping,
         mapper stays pure)
B9.85 — Production chain (provider → selection → mapper → planner →
         downloader → ModelStore)
B9.89 — Previous closed roadmap block / numbering predecessor
```

**In scope:**

```text
- planner derives the canonical acquisition locator from trusted artifact
  fields (repository, filename, revision) and validates it
- revision == None → canonical locator uses /resolve/main/, revision stays absent
- revision == R (40-hex per the existing contract) → canonical locator uses
  /resolve/R/, including canonicalizing an incoming /resolve/main/ locator
  that declares R, rather than terminally rejecting the mismatch
- malformed revisions remain rejected; revision syntax is NOT broadened
```

- malformed revisions remain rejected; revision syntax is NOT broadened
- existing URL security validation (scheme, host, credentials, port, query,
  fragment, repository, filename, path safety, allowed-host constraints)
  remains enforced; the canonical locator is validated under that model
- downloader defensive validation is aligned to the planner canonical
  contract; no second URL-construction mechanism is introduced
- end-to-end revision path: a genuine provider-produced 40-hex revision with
  the provider's existing main-form URL flows through
  provider → selection → mapper → ArtifactSpec → planner → downloader,
  with the planner producing the canonical revision-aware READY plan
- revision remains outside artifact_id (OD-1 preserved)
- focused tests for planner canonicalization, main fallback, downloader
  alignment, security preservation, and the end-to-end revision path
```

**Implementation surface:**

```text
MUST CHANGE:      castlearq/downloads/planner.py
MUST CHANGE:      castlearq/downloads/downloader.py (defensive alignment only)
MUST CHANGE:      corresponding tests
MUST NOT CHANGE:  castlearq/models.py
MUST NOT CHANGE:  B9.82 acquisition mapper (castlearq/acquisition_mapping.py)
MUST NOT CHANGE:  B9.81 HuggingFaceDiscoveryProvider
                  (castlearq/sources/huggingface_discovery.py)
MUST NOT CHANGE:  B9.84 selection boundary (castlearq/discovery_selection.py)
MUST NOT CHANGE:  ModelStore architecture
MUST NOT CHANGE:  legacy ModelSource acquisition (castlearq/sources/*, resolver,
                  legacy source command)
MUST NOT CHANGE:  CLI wiring, GUI / Model Library UX, identity / portfolio metadata
```

### 33.4 Explicit non-goals

```text
GUI implementation
Model Library UX
Hugging Face model browser
GGUF catalog UX
model search UI
variant-selection UI
ModelStore redesign (identity, multi-revision storage, paths, manifest schema)
provider redesign or replacement; new providers; any change to B9.81 R1
revision syntax broadening beyond the existing 40-hex contract
ArtifactSpec redesign (__post_init__ invariant, identity changes,
  revision entering artifact_id)
artifact identity redesign
CLI redesign
legacy acquisition convergence (ModelSource / HuggingFaceSource / resolver /
  legacy source command untouched)
portfolio/identity work
unrelated refactoring
B9.91+ or any speculative future block
```

This allocation authorizes none of the above, opens no identifier for any of
them, and reserves none of them.

### 33.5 Acceptance criteria

Persisted from the READ-ONLY allocation audit and not weakened here.

```text
AC1  Planner canonicalization — given revision R (40-hex), planner output uses
     /resolve/R/ (incoming /resolve/main/ with declared R is canonicalized,
     not terminally rejected)
AC2  Main fallback — given no revision, planner output uses /resolve/main/
     and the revision remains absent
AC3  Provider boundary — B9.81 provider behavior and zero-acquisition-coupling
     boundary remain unchanged (no provider source change)
AC4  Mapper purity — B9.82 mapper remains pure; no URL construction,
     normalization, acquisition imports, or cross-field validation enter it
AC5  Downloader alignment — downloader validation agrees with the planner
     canonical contract (revision-aware defensive validation) and introduces
     no independent URL construction or second URL template
AC6  Security preservation — existing URL security invariants (scheme, host,
     credentials, port, query, fragment, repository, filename, path safety)
     remain enforced after canonicalization
AC7  End-to-end revision path — a real provider-produced 40-hex revision
     flows provider → selection → mapper → planner → downloader with the
     planner producing the canonical revision-aware locator (READY plan)
AC8  Identity preservation — artifact identity semantics unchanged;
     revision ∉ artifact_id (OD-1)
AC9  Legacy boundary preservation — legacy acquisition remains unchanged and
     outside the B9.90 implementation scope
AC10 Regression safety — existing relevant tests for B9.80–B9.85 and legacy
     behavior remain passing
```

### 33.6 Verification plan

```text
V1 Planner unit tests: None+main, R+/resolve/R/, R+main→canonicalized to R,
   malformed revision rejected, security cases preserved
V2 Downloader tests: R+/resolve/R/ accepted defensively; no construction logic
V3 End-to-end test with a genuine provider-produced 40-hex revision through
   provider → selection → mapper → planner → downloader
V4 Regression run over B9.80–B9.85 and legacy acquisition tests
V5 Diff-surface check: only planner, downloader (alignment), and tests change
```

Verification is NOT performed by this record.

### 33.7 Architectural invariants approved with this allocation

```text
I1 Planner is the sole primary authority for revision ↔ download_url
I2 Canonical locator derivation lives only in the planner
I3 Provider, selection, mapper are transport-only for this correspondence
I4 ArtifactSpec carries declared provenance; no construction-time invariant
I5 Downloader is READY-gated and defensive-only; no URL construction
I6 40-hex revision contract is authoritative for B9.90; no broadening
I7 URL security model is preserved, not redesigned
I8 OD-1 identity (revision ∉ artifact_id) is preserved
```

### 33.8 Allocation versus implementation state

```text
NUMBER ALLOCATION:        APPROVED BY THIS NAR
IMPLEMENTATION AUTHORIZED: NO (by this NAR) — executed by the separate
                          implementation task, commit
                          e2f520822f356e36acb2b03f0494edcfdcb37bb0
                          ("feat: canonicalize revision-aware acquisition
                          locators")
IMPLEMENTATION:           COMPLETE
VERIFICATION AUTHORIZED:  NO (by this NAR) — executed by the separate
                          READ-ONLY evidence audits
VERIFICATION:             COMPLETE — full test suite 2160 passed,
                          2718 subtests passed, 0 failures, 0 errors;
                          closure readiness audit: READY FOR FORMAL CLOSURE
CLOSURE AUTHORIZED:       YES — formal closure operation (this transition)
CLOSURE:                  CLOSED
```

At this anchor the planner still rejects revision/URL mismatch, the downloader
still validates main-only, and no canonicalization exists. Nothing in this
record changes that.

```text
ALLOCATION != IMPLEMENTATION != VERIFICATION != CLOSURE
```

### 33.9 Product Vision alignment

`docs/product-vision-adr.md` is authoritative for product direction. B9.90
applies it without reopening any of its decisions. The register's closure
language (30.14; section 32) already records `GUI: NOT AUTHORIZED` and
`Model Library UX: NOT ALLOCATED`; this allocation preserves both statements.

```text
D1-D4 — NOT ENGAGED: no claim about the product problem, the user population,
         the Job To Be Done or the runtime thesis is made.
D5  — RESPECTED: no new runtime and no new core-chain stage.
D6  — RESPECTED: Model Library UX remains NOT ALLOCATED and NOT authorized.
D7  — RESPECTED: no Chat change; the chat boundary is untouched.
D8  — RESPECTED: GUI remains NOT AUTHORIZED.
D9  — RESPECTED: fine-tuning remains out of scope and requires a separate ADR.
D10 — RESPECTED: no new user-facing surface is created by this allocation.
D11 — RESPECTED: the existing acquisition chain is consumed; the planner
      locator authority is made coherent without new surfaces.
D12 — RESPECTED: no claim of validated demand, adoption or product-market fit
      is made or implied. B9.90 is not product validation.
```

### 33.10 Human approval reference

```text
DECISION RECORD STATUS:  HUMAN-RATIFIED
DECISION:                ADOPT
NUMBER ALLOCATION:       APPROVED BY THIS NAR
IMPLEMENTATION:          COMPLETE — by the separate task, commit
                         e2f520822f356e36acb2b03f0494edcfdcb37bb0
                         (not by this NAR)
```

> Implementation is **not** authorized by this record. The next required step
> was a separate implementation task that consumes B9.90 (completed by commit
> e2f520822f356e36acb2b03f0494edcfdcb37bb0). No source file, test,
> surface or refactoring was authorized here.

B9.80 through B9.89 are not modified by this record. B9.91+ is NOT allocated
by this record.

### 33.11 Register entry state summary

```text
B9.90 STATUS:        CLOSED
B9.90 IMPLEMENTATION: COMPLETE
B9.90 VERIFICATION:   COMPLETE
B9.90 CLOSURE:        CLOSED
B9.89:               CLOSED — preserved verbatim (sections 31–32), immutable
B9.91+:              NOT ALLOCATED
```

Working tree at anchor:
  tracked tree clean; git diff --check clean; ahead/behind origin/main 0/0.
```
---

## 34. B9.91 — Number Allocation Record

`B9.91` is allocated as the next main block under section 6, on the evidence of a
section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.91 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified Human Architectural Decision Record for the **Internal Dynamic
Model Library Capability**, which was preceded by a READ-ONLY architectural
analysis, a READ-ONLY decision-preparation audit, a human architectural
decision, and a READ-ONLY formal roadmap allocation audit (which concluded
`Allocation Readiness: READY FOR ALLOCATION`). This section allocates the number
that carries that scope; it does not widen, reinterpret or extend it.

### 34.1 Allocation evidence block

```text
Assigned Number:
  B9.91

Title:
  Internal Dynamic Model Library Capability (Live/Stateless)

Allocation Date:
  2026-10-03

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash
  ("docs: allocate roadmap block B9.91")
```
  Recorded by the two-step mechanism stated in section 11 and used identically
  by sections 14, 16, 19, 21, 23, 25, 27, 29, 31 and 33: at authoring time the
  hash did not exist and the field reads PENDING; a commit hash cannot be known
  before the commit exists, and writing a guessed value would be a fabricated
  identifier. The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 33 — B9.90 Closure Record
Section for this allocation:
  section 34 — this record

Human Architectural Decision Record:
  Internal Dynamic Model Library Capability
  STATUS: HUMAN-RATIFIED
  DECISION: AUTHORIZE
  Discovery authority:        ModelDiscovery (B9.80)
  Selection authority:        B9.84 — deterministic selection
  Translation authority:      B9.82 — discovery-to-acquisition mapping
  Locator authority:          B9.90 / DownloadPlanner — canonical locator
  Download authority:         Downloader
  Persistence authority:      ModelStore
  Orchestration authority:    ModelAcquisitionService (B9.85)
  NUMBER (at ratification):   NONE — the decision record assigned no identifier;
                              this section performs the allocation

Corpus/HEAD Anchor:
  85754680b6c600dc2edb5d23ac3f383b55485b19
Corpus File Count:
  227 versioned files (git ls-files at the anchor above)

Corpus Integrity Evidence:
  The corpus is fixed by the anchor commit itself: HEAD and origin/main both
  name 85754680b6c600dc2edb5d23ac3f383b55485b19, the tracked working tree is
  clean (git diff --check empty; git diff and git diff --cached empty), and the
  only untracked file at the anchor is the pre-existing, deliberately unstaged
  docs/post-b990-architectural-decision-preparation.md. Identifier discovery was
  performed across the whole tracked corpus with git grep, not by reading
  documents alone (section 6 requires corpus inspection, not document reading).

Identifier Set:
  Highest main identifier in real use before this section: B9.90
  Preceding closed block: B9.90 (section 33), CLOSED.
  B9.91 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.91 in the anchor corpus: 5
  All five are explicit non-allocations; none allocates B9.91:
    - section 33.1: "B9.91 and above — CONSIDERED AND DECLINED ..."
    - section 33.1: "B9.91+ REMAINS NOT ALLOCATED by this record."
    - section 33.3: "B9.91+ or any speculative future block"
    - section 33.10: "B9.91+ is NOT allocated by this record."
    - section 33.11: "B9.91+: NOT ALLOCATED"
  No competing, competing-pending, reserved or conflicting identifier was found
  in the corpus. The identifier "Dynamic Model Library" appears zero times in
  tracked content at this anchor.

  Sub-block identifiers in use: B9.80.1, B9.80.2, B9.80.3, B9.83.1 —
    pre-existing and illustrative, per the section 8 rule. No B9.91.x sub-block
    is assigned by this record.

Preceding Block:
  B9.90 — Planner-Canonicalized Revision-Aware Acquisition Locator

Preceding Block Status:
  ALLOCATED (section 33), IMPLEMENTED, VERIFIED, CLOSED (section 33),
  published state main == HEAD == origin/main at the anchor above.

Highest Verified Allocation:
  B9.90

Branch:
  main
```
Candidate Numbers Considered:

```text
B9.91 — SELECTED. highest_verified_allocated_block + 1 = B9.90 + 1. No
  allocation, reservation, provisional assignment, sub-block or competing
  claim exists for it anywhere in the anchor corpus; every pre-existing
  occurrence is an explicit non-allocation or a recorded decline.

B9.90 and below — CONSIDERED AND DECLINED. Section 6 fixes the floor at the
  highest VERIFIED allocated identifier; section 9 declares gaps NOT REUSED
  prospectively. B9.90 is already allocated, implemented, verified and closed.
  No gap is claimed abandoned, freed, reserved or erroneous (section 13).

B9.92 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
  immediately following the highest verified main block. B9.92 would skip
  B9.91 and is therefore invalid.

B9.91.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
  integers of the form B9.x raise the main-block floor, and a sub-block does
  not by itself advance the next main block number.

Any alias, umbrella or renamed identifier — CONSIDERED AND DECLINED. Section 6
  admits only the integer form; no alias is minted.
```

Selected Number:

```text
B9.91
```

Validity Reason:

```text
B9.90 is the highest main block assigned, implemented, verified and closed in
the activation corpus at the anchor recorded above. B9.91 is the integer
immediately following it, as section 6 requires. Every pre-existing occurrence
of B9.91 in the corpus is an explicit non-allocation or a recorded decline, so
no competing allocation exists. The number is therefore valid under the active
rule, and the section 7 corpus inspection record is present above.
```

Release Association:

```text
NOT YET DEFINED
```

Supersession:

```text
none as to B9.90 — the B9.90 closure record (section 33) remains the accurate
description of B9.90 and is not rewritten by this section.

cross-reference only — the five "B9.91+: NOT ALLOCATED" statements in section 33
remain the accurate description of the corpus at their own anchors and are not
rewritten. They are superseded by this record as a cross-reference only.
```

Documented?:

```text
YES — this document (section 34), plus the human-ratified Internal Dynamic
Model Library Capability decision record referenced in 34.1
```

Number Allocation Record:

```text
PRESENT — section 34
```

Retrospective Record:

```text
NO — prospective allocation record
```

Human decisions pending:

```text
none as to allocation — the Internal Dynamic Model Library Capability decision
record is HUMAN-RATIFIED with DECISION: AUTHORIZE, and the READ-ONLY allocation
audit concluded READY FOR ALLOCATION.

Future human decisions NOT discharged by this record:
  - implementation authorization (a separate task, not this NAR)
  - any presentation surface (GUI / UX / CLI / API), which remains NOT AUTHORIZED
  - any persistent catalog, provider federation, ModelStore redesign, legacy
    convergence, model-domain unification or compatibility-evaluation integration
```

### 34.2 Register entry for B9.91

```text
Block ID:                 B9.91
Name:                     Internal Dynamic Model Library Capability
                           (Live/Stateless)
Status:                   ALLOCATED
Origin:                   this document, section 34 (NAR)
Scope:                    see 34.3 — fixed by the HADR, recorded without
                           reinterpretation
Non-goals:                see 34.4
Architectural decision:   HUMAN-RATIFIED HADR — Internal Dynamic Model Library
                          Capability; DECISION: AUTHORIZE, preceding this
                          allocation
Current State:            CLOSED — allocated by section 34; implemented, verified
                          and closed by the controlled closure transition
                          recorded in this section
Implementation Commit:    4d2c068c87748db7aa3a3251077ad353cb29dab1
                          ("feat: implement B9.91 dynamic model library")
Verification Result:      COMPLETE — evidence audit PASSED WITH OBSERVATIONS;
                          focused suite 51 tests passed; full suite 2211 passed,
                          2718 subtests passed, 0 failures, 0 errors, 0 skipped
Closure Commit:           the commit that contains this closure update
                          (a commit cannot contain its own hash; this record is
                          committed in that commit — the section 32.2 convention)
Release Association:      NOT YET DEFINED
Supersession:             none (cross-reference only, as recorded above)
Documented?:              YES — this document + the decision record
Number Allocation Record: PRESENT — section 34
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none
```

The lifecycle state asserted by this record is, in full and without implication
of anything further:

```text
B9.91 = ALLOCATED
B9.91 = IMPLEMENTED
B9.91 = VERIFIED
B9.91 = CLOSED
```

> **SUPERSESSION NOTE.** Section 33 states that B9.91 and higher identifiers are
> not allocated. Those statements remain the accurate description of the corpus
> **at their own anchors** and are **not** rewritten by this section. The
> current, authoritative state of B9.91 is the one asserted above.
### 34.3 Scope attached to this allocation

The scope was fixed by the HUMAN-RATIFIED decision record and is recorded here
without reinterpretation.

```text
Internal Dynamic Model Library Capability (Live/Stateless)
```

**Purpose, as decided:**

> Establish the internal Dynamic Model Library capability as a live, stateless,
> model-oriented composition over the existing discovery architecture, so that
> discovered candidates, variants and artifacts can be organized through one
> model-oriented capability while preserving existing discovery, selection and
> acquisition authorities.

This is an **architectural capability allocation**. It is NOT an allocation for
a visible Model Library product surface.

**Authorized behavior, as decided:**

```text
internal capability
live / dynamic behavior
stateless operation (no persistent state, no catalog, no cache)
model-oriented organization of discovery results
reuse of the existing ModelDiscovery boundary
reuse of the existing deterministic selection authority
handoff to the existing acquisition pipeline
Hugging Face as the initial discovery provider through the existing port
existing GGUF discovery capability as the initial format focus
```

**In scope:**

```text
- live model discovery consumption
- model-oriented organization of discovery results
- repository inspection composition
- candidate organization
- variant organization
- artifact organization
- GGUF artifact visibility
- declared quantization metadata
- declared architecture metadata where already available
- declared provider metadata
- declared revision/provenance metadata
- reuse of existing deterministic selection
- handoff to existing acquisition
- Hugging Face as the initial discovery provider through the existing port
```

The allocation fixes the responsibility. It does not prescribe an unnecessary
implementation structure.

### 34.4 Non-goals

The following are explicit B9.91 non-goals. None of them is silently included in
the allocated capability.

```text
Presentation:
  - GUI
  - Model Library UX
  - visible Model Library
  - visual model browser
  - new CLI Model Library command
  - new API endpoint
  - web UI
  - marketplace presentation

Persistence:
  - persistent catalog
  - database
  - filesystem catalog
  - cache
  - offline index
### 34.5 Architectural authorities consumed, not replaced

B9.91 composes existing authorities. Composing them grants the capability no
technical authority over them.

```text
ModelDiscovery / HuggingFaceDiscoveryProvider (B9.80, B9.81)
    → discovery authority

B9.84 selection
    → deterministic selection authority

B9.82 mapping
    → discovery-to-acquisition translation authority

B9.90 / DownloadPlanner
    → canonical acquisition locator authority

Downloader
    → download execution and defensive validation

ModelStore
    → model persistence

ModelAcquisitionService / B9.85
    → acquisition orchestration
```

Acquisition relationship as decided:

```text
Dynamic Model Library
        ↓
existing deterministic selection (B9.84)
        ↓
existing acquisition (B9.82 / B9.85)
        ↓
planner (B9.90)
        ↓
downloader
        ↓
ModelStore
```

B9.91 does **not** own, and must not duplicate:

```text
- URL construction
- download validation
- downloading
- acquisition planning
- ModelStore persistence
- acquisition orchestration
```

### 34.6 Dependencies (verified closed)

```text
B9.80 — Model Discovery domain contract                  CLOSED
B9.81 — Hugging Face discovery provider                 CLOSED
B9.82 — Discovery-to-Acquisition Boundary                CLOSED
B9.83 — Revision-Aware Acquisition                       CLOSED
B9.84 — Selection Boundary                               CLOSED
B9.85 — Production Acquisition Chain                     CLOSED
B9.86 — Catalog Query Boundary                           CLOSED
B9.90 — Canonical Acquisition Locator                    CLOSED
```

`B9.87` (CLI search caller) is recorded as **contextual precedent** for the
separation between an application boundary and any product surface; it is not a
technical dependency of B9.91.

No additional prerequisite was identified. No dependency is invented, and none
of the following is a dependency: GUI, UX, presentation, persistence, legacy
migration, ModelStore redesign, multi-provider acquisition, model-domain
unification, compatibility evaluation.

### 34.7 Identity, revision, GGUF and variant semantics

**Identity.** B9.91 does not authorize a new persistent identity system. The
existing distinctions are preserved and remain distinct:

```text
provider identity
repository identity
candidate identity
variant identity ((provider, repository, declared_quantization), derived live)
artifact identity (repository + filename)
acquisition locator (planner-owned canonical)
revision / provenance
storage identity (content_id, or the OD-1 provenance digest; revision-blind)
```

A stateless capability operates on existing live identities. Persistent
identity is therefore **not** a B9.91 dependency. An artifact that lacks a
logical model identity required by an unrelated downstream consumer is a future
policy/architecture question and is **not** a B9.91 blocker.

**Revision.**

```text
revision = selection/provenance metadata
revision ≠ persistent library identity
```

B9.91 may expose and transport existing revision/provenance information. It
must not redefine revision, broaden revision syntax, make revision a persistent
library identity, redesign ModelStore identity, or introduce revision
coexistence. B9.83 and B9.90 are unchanged.

**GGUF / variants.** B9.91 may organize already-existing declared variant
information such as Q4_K_M, Q5_K_M, Q6_K, Q8_0 and any further declared value
produced by the existing discovery architecture. It does not allocate
quantization ranking, quality inference, recommendation, or a new quantization
taxonomy. Provider-declared values remain **declared / unverified** unless an
existing contract establishes otherwise.

### 34.8 ModelStore, legacy and persistence boundaries

```text
ModelStore         = UNCHANGED by B9.91
Legacy acquisition = NOT A DEPENDENCY of B9.91
B9.91              = LIVE / STATELESS
```

- The existing revision-coexistence limitation (same repository, same filename,
  different revision sharing one storage identity by OD-1; recorded limitation
  19.7.3) remains a **future concern** and is not addressed, solved or worsened
  by this allocation.
- Legacy acquisition (`ModelSource`, `HuggingFaceSource`, the legacy CLI path)
  is untouched, is not migrated, removed, deprecated or converged by B9.91, and
  remains operational. Legacy consolidation remains a future architectural
  decision.
- No database, cache, index, snapshot, synchronization or freshness mechanism is
  allocated. Persistence is an explicit non-goal, not an omission.
  - snapshots
  - synchronization
  - invalidation
  - freshness management

Search intelligence:
  - ranking
  - recommendations
  - fuzzy search
  - semantic search
  - embeddings
  - popularity scoring
  - quality scoring

Provider expansion:
  - provider federation
  - provider registry redesign
  - provider normalization framework
  - second acquisition backend

Storage:
  - ModelStore redesign
  - multi-revision coexistence
  - persistent library identity
  - storage identity redesign

Legacy:
  - ModelSource migration
  - HuggingFaceSource removal
  - legacy acquisition convergence
  - legacy CLI migration

Other domains:
  - execution
  - chat lifecycle
  - fine-tuning
  - evaluation
  - datasets
  - multi-GPU
  - cluster orchestration

Representation:
  - broad model_domain unification
  - a third parallel model representation
  - a large Model / ModelFamily / ModelVariant / ModelArtifact / CatalogEntry
    hierarchy, unless independently justified during implementation
```

### 34.9 Acceptance criteria

Objective architectural criteria for B9.91. No numeric test target is invented.

```text
AC1  — Discovery boundary: the capability consumes the existing ModelDiscovery
       boundary for search/inspect and does not bypass it.

AC2  — Model-oriented organization: the capability provides a coherent
       model-oriented organization of existing candidates, variants and
       artifacts without introducing an unnecessary parallel domain hierarchy.

AC3  — Metadata preservation: existing provider-declared metadata remains
       available without being silently normalized, reinterpreted or promoted
       to verified facts.

AC4  — Variant/artifact distinction: variants and artifacts remain distinct
       concepts and existing GGUF/quantization metadata remains available.

AC5  — Selection authority: existing B9.84 deterministic selection remains
       authoritative; its semantics are not re-implemented.

AC6  — Revision semantics: revision remains provenance/selection metadata and
       is not promoted to persistent library identity.

AC7  — Acquisition handoff: selected artifacts can hand off to the existing
       B9.82 / B9.85 / B9.90 acquisition chain without duplicating planner,
       downloader or ModelStore responsibilities.

AC8  — Statelessness: the capability introduces no persistent catalog,
       database, cache or offline index.

AC9  — Presentation isolation: no GUI, UX, CLI command, API endpoint or other
       presentation surface is introduced by B9.91.

AC10 — Provider scope: Hugging Face remains the initial provider through the
       existing discovery boundary; no provider federation is introduced.

AC11 — Storage isolation: ModelStore remains unchanged.

AC12 — Legacy isolation: legacy acquisition remains untouched and is not
       required for B9.91.

AC13 — Representation containment: no broad model_domain unification and no
       unnecessary third model representation is introduced.

AC14 — Scope integrity: B9.91 does not modify or absorb responsibilities
       belonging to B9.80–B9.90.
```

### 34.10 Implementation boundary

B9.91 fixes the **responsibility boundary and architectural contracts**, not a
specific file layout or implementation mechanism.

Implementation may later determine whether the capability is best represented by:

```text
- a new internal service
- an extension of an existing application service
- a formal composition
- another architecture-compatible mechanism
```

That choice is intentionally deferred to the implementation phase. No module is
prescribed by this allocation.

### 34.11 Closure evidence expected

Before closure, B9.91 will require:

```text
- an implementation commit
- implementation verification
- relevant focused tests
- the full repository test suite where applicable
- an explicit scope audit
- confirmation that B9.80–B9.90 remain unchanged
- confirmation that GUI / UX, persistence, provider federation, ModelStore
  redesign and legacy migration were not introduced
- evidence that AC1–AC14 are satisfied
- a closure transition in this roadmap register
```

**None** of this evidence is produced, claimed or implied by this allocation
record.

### 34.12 Relationship to the prior Model Library restriction (narrowing)

The prior restriction is recorded normatively in:

```text
register section 25.5         — "Application boundary ≠ Model Library UX";
                                Model Library / UX / GUI remains NOT ALLOCATED
                                and NOT AUTHORIZED; a future block requiring any
                                presentation mechanism is a different block and
                                requires its own architectural decision
docs/product-vision-adr.md D6 — Model Library UX remains unallocated and is NOT
                                authorized for implementation by this ADR
docs/product-vision-adr.md D8 — GUI is NOT authorized for implementation by this ADR
docs/product-vision-adr.md §15 — Model Library UX: NOT ALLOCATED, NOT AUTHORIZED
```

**None of those records is modified by this allocation.** They remain accurate
and authoritative.

B9.91 **narrows the semantic interpretation** of the prior restriction by
authorizing an internal capability while leaving every presentation and
product-surface restriction unchanged:

```text
Model Library capability ≠ Model Library UX
Model Library capability ≠ GUI
Model Library capability ≠ persistent catalog
Model Library capability ≠ marketplace
Model Library capability ≠ generic presentation layer
```

After this record:

```text
Model Library UX      = NOT AUTHORIZED (unchanged)
GUI                   = NOT AUTHORIZED (unchanged)
Persistent catalog    = NOT AUTHORIZED (unchanged)
Visible Model Library = NOT AUTHORIZED (unchanged)

Internal Dynamic Model Library capability = ALLOCATED (this record)
```

The narrowing is semantic, not textual: the prior records are cited, not
rewritten, in the manner established by `docs/B9.59` §6 and section 13 of this
document. A reader encountering `Model Library` in an earlier record must read it
against this section for the capability/UX distinction.

### 34.13 Product Vision alignment

`docs/product-vision-adr.md` is authoritative for product direction. B9.91
applies it without reopening any of its decisions.

```text
D1-D4 — NOT ENGAGED: no claim about the product problem, the user population,
         the Job To Be Done or the runtime thesis is made.
D5  — RESPECTED: no new runtime and no new core-chain stage.
D6  — RESPECTED AND NARROWED (34.12): Model Library UX remains NOT ALLOCATED
       and NOT authorized; an internal capability substrate is allocated. The
       D6 clause "must not be reduced conceptually to a generic model search
       interface", and D6's inclusion of compatibility evaluation against the
       user's environment, remain NOT DISCHARGED by this allocation and remain a
       future obligation.
D7  — RESPECTED: no Chat change; the chat boundary is untouched.
D8  — RESPECTED: GUI remains NOT AUTHORIZED.
D9  — RESPECTED: fine-tuning remains out of scope and requires a separate ADR.
D10 — RESPECTED: no new user-facing surface is created by this allocation.
D11 — RESPECTED: the closed discovery/acquisition chain is consumed; no new
       surface is created.
D12 — RESPECTED: no claim of validated demand, adoption or product-market fit
       is made or implied. B9.91 is not product validation.
```

### 34.14 Allocation versus implementation state

```text
NUMBER ALLOCATION:         APPROVED BY THIS NAR
IMPLEMENTATION AUTHORIZED: NO — by this NAR; executed by the separate
                           implementation task, commit
                           4d2c068c87748db7aa3a3251077ad353cb29dab1
                           ("feat: implement B9.91 dynamic model library")
IMPLEMENTATION:           COMPLETE
VERIFICATION AUTHORIZED:   NO — by this NAR; executed by the separate
                           READ-ONLY evidence audit
VERIFICATION:             COMPLETE — evidence audit PASSED WITH OBSERVATIONS;
                           focused suite 51 tests passed; full suite 2211 passed,
                           2718 subtests passed, 0 failures, 0 errors, 0 skipped
CLOSURE AUTHORIZED:        YES — formal closure operation (this transition)
CLOSURE:                   CLOSED
```

The implementation and verification above were performed by separate tasks and
are recorded here by this closure transition only. Nothing in this section
retroactively authorized them.

```text
ALLOCATION != IMPLEMENTATION != VERIFICATION != CLOSURE
```

### 34.15 Human approval reference

```text
DECISION RECORD STATUS: HUMAN-RATIFIED
DECISION:               AUTHORIZE — internal stateless Dynamic Model Library
                        capability
NUMBER ALLOCATION:      APPROVED BY THIS NAR
IMPLEMENTATION:         COMPLETE — by the separate implementation task, commit
                        4d2c068c87748db7aa3a3251077ad353cb29dab1
                        (not by this NAR)
VERIFICATION:           COMPLETE — by the separate READ-ONLY evidence audit
                        (not by this NAR)
CLOSURE:                CLOSED — by this controlled closure transition
```

> Implementation and verification were **not** authorized by the NAR; they were
> executed by the separate tasks referenced above. This closure transition only
> records their completed state in the register.

B9.80 through B9.90 are not modified by this record. B9.92+ is NOT allocated by
this record.

### 34.16 Register entry state summary

```text
B9.91 STATUS:         CLOSED
B9.91 IMPLEMENTATION: COMPLETE
B9.91 VERIFICATION:   COMPLETE
B9.91 CLOSURE:        CLOSED
B9.90:                CLOSED — preserved verbatim (section 33), immutable
B9.92+:               NOT ALLOCATED
```

B9.91 closure transition (this section, commit "docs: close roadmap block
B9.91") modified only this document. Source, tests, configuration, packaging,
ADRs and the pre-existing untracked decision-preparation document were not
touched by this transition.

Working tree at anchor:
  tracked tree clean apart from this allocation record; git diff --check clean;
  ahead/behind origin/main 0/0; the only untracked file is the pre-existing,
  unstaged docs/post-b990-architectural-decision-preparation.md.

---

## 35. B9.92 — Number Allocation Record

`B9.92` is allocated as the next main block under section 6, on the evidence of a
section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.92 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified product/architectural decision for the CLI discovery-to-
acquisition flow, which was preceded by a READ-ONLY CLI/Terminal Alpha Readiness
Audit, a READ-ONLY human product/architectural decision audit, a READ-ONLY
formal roadmap allocation audit, and the human ratification that selected
Option A as the boundary. This section allocates the number that carries that
scope; it does not widen, reinterpret or extend it.

### 35.1 Allocation evidence block

```text
Assigned Number:
  B9.92

Title:
  CLI Discovery-to-Acquisition Product Flow

Allocation Date:
  2026-10-03

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash
  ("docs: allocate roadmap block B9.92")
```
  Recorded by the two-step mechanism stated in section 11 and used identically
  by sections 14, 16, 19, 21, 23, 25, 27, 29, 31, 33 and 34: at authoring time
  the hash did not exist and the field reads PENDING; a commit hash cannot be
  known before the commit exists, and writing a guessed value would be a
  fabricated identifier. The allocation itself is unchanged.

Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 34 — B9.91 Number Allocation Record and closure transition
Section for this allocation:
  section 35 — this record

Origin:
  controlled B9.92 product/architectural decision and formal allocation audit

Human Product / Architectural Decision Record:
  CLI Discovery-to-Acquisition Product Flow
  STATUS: HUMAN-RATIFIED
  BOUNDARY DECISION: OPTION A (ratified)
  NUMBER (at ratification): NONE — the decision record assigned no identifier;
                              this section performs the allocation

Corpus/HEAD Anchor:
  d50809d5599ad9472692d45588aa95525c365859
Corpus File Count:
  227 versioned files (git ls-files at the anchor above)

Corpus Integrity Evidence:
  The corpus is fixed by the anchor commit itself: HEAD and origin/main both
  name d50809d5599ad9472692d45588aa95525c365859, the tracked working tree is
  clean (git diff --check empty; git diff and git diff --cached empty), and the
  only untracked file at the anchor is the pre-existing, deliberately unstaged
  docs/post-b990-architectural-decision-preparation.md. Identifier discovery was
  performed across the whole tracked corpus, not by reading documents alone
  (section 6 requires corpus inspection, not document reading).

Identifier Set:
  Highest main identifier in real use before this section: B9.91
  Preceding closed block: B9.91 (section 34), ALLOCATED / IMPLEMENTED /
    VERIFIED / CLOSED, published at d50809d5599ad9472692d45588aa95525c365859.
  B9.92 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.92 in the anchor corpus:
  They are explicit non-allocations or historical declines; none allocates
  B9.92:
    - section 34.1: "B9.92 and above — CONSIDERED AND DECLINED. Section 6
      requires the integer immediately following the highest verified main
      block. B9.92 would skip B9.91 and is therefore invalid."
    - section 34.15: "B9.92+ is NOT allocated by this record."
    - section 34.16: "B9.92+: NOT ALLOCATED"
  The decline recorded inside section 34 was accurate **at its own anchor**,
  when B9.91 was still unallocated. It is preserved as history and is not
  rewritten; the current authoritative state of B9.92 is the one asserted by
  this section.

  No competing, competing-pending, reserved or conflicting identifier was found
  in the corpus, and no B9.93 or later main block, sub-block or alias is
  assigned by this record.

Preceding Block:
  B9.91 — Internal Dynamic Model Library Capability (Live/Stateless)

Preceding Block Status:
  ALLOCATED (section 34), IMPLEMENTED, VERIFIED, CLOSED (section 34),
  published state main == HEAD == origin/main at the anchor above.

Highest Verified Allocation:
  B9.91

Branch:
  main
```

Candidate Numbers Considered:

```text
B9.92 — SELECTED. highest_verified_allocated_block + 1 = B9.91 + 1. No
  allocation, reservation, provisional assignment, sub-block or competing
  claim exists for it anywhere in the anchor corpus; every pre-existing
  occurrence is either an explicit non-allocation or the historical decline
  recorded at section 34.1, which was accurate at its own anchor and is
  preserved rather than rewritten.

B9.91 and below — CONSIDERED AND DECLINED. Section 6 fixes the floor at the
  highest VERIFIED allocated identifier; section 9 declares gaps NOT REUSED
  prospectively. B9.91 is already allocated, implemented, verified, closed and
  published. No gap is claimed abandoned, freed, reserved or erroneous
  (section 13).

B9.93 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
  immediately following the highest verified main block. B9.93 would skip
  B9.92 and is therefore invalid.

B9.92.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
  integers of the form B9.x raise the main-block floor, and a sub-block does
  not by itself advance the next main block number.

Any alias, umbrella or renamed identifier — CONSIDERED AND DECLINED. Section 6
  admits only the integer form; no alias is minted.
```

Selected Number:

```text
B9.92
```

Validity Reason:

```text
B9.91 is the highest main block assigned, implemented, verified and closed in
the activation corpus at the anchor recorded above. B9.92 is the integer
immediately following it, as section 6 requires. Every pre-existing occurrence
of B9.92 in the corpus is either an explicit non-allocation or a historical
decline that was accurate at its own anchor, so no competing allocation
exists. The number is therefore valid under the active rule, and the section 7
corpus inspection record is present above.
```

Release Association:

```text
NOT YET DEFINED
```

Supersession:

```text
none as to B9.90 or B9.91 — those closure records remain the accurate
description of those blocks and are not rewritten by this section.

cross-reference only — the "B9.92 and above — CONSIDERED AND DECLINED"
statement and the "B9.92+: NOT ALLOCATED" statements in section 34 remain the
accurate description of the corpus at their own anchors and are not rewritten.
They are superseded by this record as a cross-reference only.
```

Documented?:

```text
YES — this document (section 35) plus the ratified product/architectural
decision and the completed allocation audit it cites
```

Number Allocation Record:

```text
PRESENT — section 35
```

Retrospective Record:

```text
NO — prospective allocation record
```

Human decisions pending:

```text
none as to allocation — the CLI Discovery-to-Acquisition Product Flow decision
is HUMAN-RATIFIED and the READ-ONLY allocation audit concluded READY WITH
OBSERVATIONS.

Future human decisions NOT discharged by this record:
  - implementation authorization (a separate task, not this NAR)
  - expansion of model_identity.py, which remains a separate future decision
  - any Model Library UX or GUI surface
  - legacy source/plan/run convergence, download progress, and every other
    recorded deferral listed in section 35.4
```

### 35.2 Register entry for B9.92

```text
Block ID:                 B9.92
Name:                     CLI Discovery-to-Acquisition Product Flow
Status:                   CLOSED
Origin:                   controlled B9.92 product/architectural decision and
                           formal allocation audit
Scope:                    see 35.3 — fixed by the ratified decision, recorded
                           without reinterpretation
Boundary decision:        OPTION A — CLI uses ModelCatalogQueryService.query
                           for search and ModelDiscovery.inspect(repository)
                           for repository-keyed inspection
Non-goals:                see 35.4
Architectural decision:   HUMAN-RATIFIED product/architectural decision,
                           preceding this allocation
Current State:            CLOSED — allocated by section 35, implemented at
                           faf24123540ba5a9590de4eeb5757faf64911e1c, verified,
                           and closed. See 35.11 for the closure evidence.
Implementation Commit:    faf24123540ba5a9590de4eeb5757faf64911e1c
                           ("feat: add CLI model inspection flow"), published at
                           origin/main
Verification Result:      PASS — see 35.11
Closure Commit:           PENDING — fixed by the controlled commit that carries
                           this closure record ("docs: close roadmap block
                           B9.92"), by the section 11 two-step mechanism
Release Association:      NOT YET DEFINED
Supersession:             none (cross-reference only, as recorded above)
Documented?:              YES — this document + the decision record
Number Allocation Record: PRESENT — section 35
Retrospective Record:     NO — prospective allocation record
Human decisions pending:  none as to allocation
```

The lifecycle state asserted by this record is, in full and without implication
of anything further:

```text
B9.92 = CLOSED
```

> **SUPERSESSION NOTE.** Section 34 states that B9.92 and higher identifiers are
> not allocated. Those statements remain the accurate description of the corpus
> **at their own anchors** and are **not** rewritten by this section. The
> current, authoritative state of B9.92 is the one asserted above.

### 35.3 Scope attached to this allocation

The scope was fixed by the HUMAN-RATIFIED decision and is recorded here without
reinterpretation.

```text
CLI Discovery-to-Acquisition Product Flow
```

**Objective, as decided:**

> Establish a coherent, additive CLI surface allowing a user to search a remote
> model, inspect its discovered variants/artifacts and declared metadata
> including revision, express selection intent through the existing selection
> flags, continue through the existing canonical acquisition path, and proceed
> to the existing execution path.

This is a **product-surface block, not a new domain architecture block**.

**Boundary decision, as ratified:**

```text
Option A

CLI
 ↓
ModelCatalogQueryService.query         (search, B9.86 boundary, unchanged)
ModelDiscovery.inspect(repository)     (repository-keyed inspection, B9.80/81)
```

Recorded consequences of that decision:

```text
DynamicModelLibrary remains internal and unchanged.
B9.91 remains stateless and composition-only.
B9.91 does not become a public CLI or API surface.
The CLI does not fabricate a ModelCandidate merely to invoke B9.91.
No new higher-level service is introduced.
No new discovery abstraction is introduced.
Option B is NOT the selected implementation architecture.
```

**Required scope:**

```text
 1. Add one read-only `inspect <repository>` CLI surface.
 2. Keep the existing 18 commands unchanged; B9.92 adds the 19th command.
 3. Consume the modern discovery boundary.
 4. Resolve the inspection input by repository.
 5. Present: repository; variant / declared_quantization; filename;
    declared_size; declared_sha256; revision.
 6. Treat all provider metadata as DECLARED / unverified.
 7. Display missing values as Unknown.
 8. Preserve discovery-produced variant grouping and ordering.
 9. Preserve B9.84 as the sole selection authority.
10. Preserve B9.90 as the sole revision-aware locator authority.
11. Preserve the existing acquisition path.
12. Maintain exit-code discipline 0 / 1 / 2.
13. Add focused tests during the later implementation phase.
```

**Optional scope (optional, never mandatory):**

```text
- `--json` using the existing JSON envelope and schema (schema_version = 1).
- README / help onboarding updates.
```

**CLI contract and intended user journey:**

```text
castlearq search <query>
castlearq inspect <repository>
castlearq download <model-id> [selection flags]
castlearq execute ...

search → inspect → select → acquire → execute
```

`inspect` is additive. No existing command is renamed, removed or re-scoped.
Existing legacy commands remain untouched and functional.

**Discovery and metadata contract.** `ModelDiscovery.search` and
`ModelDiscovery.inspect(repository)` are consumed unchanged. The CLI preserves
repository identity, discovery-produced variant grouping, artifact ordering,
declared quantization, filename, declared size, declared SHA-256 and declared
revision. No metadata is promoted from DECLARED to VERIFIED during inspection.

**Revision contract.** Revision is **display-only provenance** in B9.92. No
`--revision` input is part of this allocation. B9.90 remains the authority:

```text
revision == None → /resolve/main/
revision == R    → /resolve/R/
```

**Model identity boundary:**

```text
DISCOVERABLE ≠ INSPECTABLE ≠ SELECTABLE ≠ ACQUIRABLE ≠ EXECUTABLE
```

Inspection must succeed for any discoverable repository, including repositories
with no entry in `model_identity.py`. No identity entry may be added as part of
this allocation or of the later implementation.

**Alpha qualification, as decided:**

> B9.92 improves the Alpha terminal workflow for models that CastleArq can
> currently acquire. Discovery and inspection are broader than current
> acquisition identity coverage; expansion of `model_identity.py` is a separate
> future decision and is not part of B9.92.

This prevents the roadmap from implying that every discoverable model is
currently acquirable.

**Architectural authorities consumed, not replaced.** B9.92 is only a CLI product
adapter over existing authorities:

```text
ModelDiscovery                  discovery authority
ModelCatalogQueryService        search/query boundary
B9.84 deterministic selection   selection authority
B9.82 mapping                   discovery-to-acquisition translation
B9.90 / DownloadPlanner         canonical acquisition locator authority
Downloader                      download execution and defensive validation
ModelStore                      model persistence
ModelAcquisitionService (B9.85) acquisition orchestration
```

The CLI must not construct `ArtifactSpec`, download URLs, planner state,
downloader state, ModelStore state, model identities, selection algorithms or
revision semantics.

**Expected implementation surface (expected, not authorized here):**

```text
castlearq/main.py
tests/test_b992_*.py
README.md                        (optional)
```

The following are expected to remain untouched unless future implementation
evidence proves an additive change strictly necessary:

```text
castlearq/dynamic_model_library.py
castlearq/discovery.py
castlearq/sources/huggingface_discovery.py
castlearq/discovery_selection.py
castlearq/acquisition_*.py
castlearq/downloads/*
castlearq/model_store.py
castlearq/model_identity.py
castlearq/model_domain.py
castlearq/application_wiring.py
```

**Output contract.** Human-readable output is mandatory and must expose
repository, variant/declared_quantization, filename, declared_size,
declared_sha256 and revision, with explicit DECLARED/unverified semantics and
`Unknown` handling. `--json` is optional and, if implemented, must reuse
`_emit_json_envelope` and `schema_version = 1`. No second JSON schema may be
introduced.

**Error and exit-code contract:**

```text
0 = success
1 = operational/application failure
2 = usage/input error
```

Errors remain categorized and user-facing. No separate error architecture is
introduced.

### 35.4 Non-goals

The following are explicit B9.92 non-goals. None of them is silently included
in the allocated capability.

```text
Identity:
  - model identity expansion (model_identity.py)
  - arbitrary repository acquisition
  - persistent library identity
  - new model hierarchy
  - model_domain unification

Acquisition:
  - download progress
  - resumable downloads
  - new acquisition backend
  - ModelStore redesign
  - multi-revision storage
  - a second acquisition path

Selection and discovery:
  - new selection algorithm
  - new revision semantics
  - new provider
  - provider federation
  - ranking
  - recommendation
  - fuzzy search
  - semantic search
  - embeddings

Legacy and convergence:
  - legacy migration
  - legacy source/plan convergence
  - legacy run/execute convergence

Product surfaces and storage:
  - GUI
  - web UI
  - persistent catalog
  - database
  - cache
  - offline snapshots
  - synchronization / invalidation

Other domains:
  - fine-tuning
  - evaluation
  - datasets
  - multi-GPU
  - clusters
  - chat lifecycle redesign
```

### 35.5 Dependencies (verified closed)

```text
B9.80 — Model Discovery domain contract        CLOSED
B9.81 — Hugging Face discovery provider       CLOSED
B9.84 — Selection Boundary                    CLOSED
B9.85 — Production Acquisition Chain          CLOSED
B9.86 — Catalog Query Boundary                CLOSED
B9.90 — Canonical Acquisition Locator         CLOSED
B9.91 — Internal Dynamic Model Library        CLOSED / PUBLISHED
```

B9.91 is recorded here for completeness: under the ratified Option A boundary it
is **not** required as a production caller dependency. B9.92 does not depend on
B9.91 becoming a product surface.

No additional prerequisite was identified, and no dependency on GUI,
persistence, legacy migration, ModelStore redesign or multi-provider acquisition
is invented by this record.

### 35.6 Acceptance criteria

Objective, independently verifiable criteria. No numeric test target is
invented.

```text
AC1  A read-only CLI command inspects a repository and reaches the modern
     ModelDiscovery boundary without using the legacy HuggingFaceSource path.

AC2  Inspection succeeds for any discoverable repository, including repositories
     without a logical model identity; no identity-table entry is created or
     required.

AC3  Output exposes repository, variant/declared_quantization, filename,
     declared_size, declared_sha256 and revision without inventing metadata.

AC4  Exposed metadata remains DECLARED/unverified; absent values are shown as
     Unknown and are never defaulted or promoted.

AC5  Discovery-produced variant grouping is preserved and is not re-derived,
     re-sorted, or re-grouped by the CLI.

AC6  B9.84 remains the sole deterministic selection authority; B9.92 introduces
     no selection algorithm, ranking, preference, fallback, or ambiguity
     resolution.

AC7  Acquisition remains unchanged; the CLI constructs no ArtifactSpec, URL,
     planner, downloader, or ModelStore state and introduces no second
     acquisition path.

AC8  Revision is display-only in B9.92; B9.90 locator semantics remain
     untouched.

AC9  model_identity.py, model_domain.py, ModelStore, downloads/*, and the
     B9.80-B9.91 contracts remain unmodified.

AC10 The change is additive; no existing command is renamed, removed, or
     re-scoped.

AC11 Legacy source/plan/run commands remain functional and are not migrated.

AC12 No GUI, persistence, catalog, cache, ranking, recommendation, fuzzy/semantic
     search, provider federation, or new model hierarchy is introduced.

AC13 Exit codes follow the documented 0/1/2 convention and errors remain
     categorized.

AC14 Focused tests cover the inspection behavior and the full suite passes.
```

### 35.7 Closure evidence expected

Before closure, B9.92 will require:

```text
- an implementation commit
- implementation verification
- relevant focused tests
- the full repository test suite where applicable
- an explicit scope audit
- confirmation that B9.80-B9.91 remain unchanged
- confirmation that model identity was not expanded and that no legacy command
  was migrated
- evidence that AC1-AC14 are satisfied
- a closure transition in this roadmap register
```

**None** of this evidence is produced, claimed or implied by this allocation
record.

### 35.8 Allocation versus implementation state (as asserted by this NAR)

```text
NUMBER ALLOCATION:         APPROVED BY THIS NAR
IMPLEMENTATION AUTHORIZED: NO — by this NAR
IMPLEMENTATION:            NOT PERFORMED
VERIFICATION AUTHORIZED:   NO — by this NAR
VERIFICATION:              NOT PERFORMED
CLOSURE AUTHORIZED:        NO — by this NAR
CLOSURE:                   NOT PERFORMED
```

The statements below are **historical**: they describe the corpus **at the
allocation anchor recorded in 35.1**, before any B9.92 implementation existed.
They were accurate at that anchor and are preserved verbatim as the
allocation-time record. They are **not** the current state of B9.92, which is
recorded in 35.2 and evidenced in 35.11.

> Historical, allocation-anchor statement (not current state): at this anchor no
> `inspect` CLI command exists, no JSON support exists for it, no README change
> has been made, and no application, discovery, selection, acquisition, storage
> or identity code is authorized here. Nothing in this record changes that.

```text
ALLOCATION != IMPLEMENTATION != VERIFICATION != CLOSURE
```

### 35.9 Human approval reference

```text
DECISION RECORD STATUS: HUMAN-RATIFIED
DECISION:               ESTABLISH the CLI Discovery-to-Acquisition Product Flow
BOUNDARY:               OPTION A (ratified)
NUMBER ALLOCATION:      APPROVED BY THIS NAR
IMPLEMENTATION:         NOT AUTHORIZED by this record
VERIFICATION:           NOT PERFORMED
CLOSURE:                NOT PERFORMED
```

> Implementation is **not** authorized by this record. The next required step is
> a separate implementation task consuming B9.92. No source file, test, command,
> endpoint or refactoring is authorized here.

B9.80 through B9.91 are not modified by this record. B9.93+ is NOT allocated by
this record.

### 35.10 Register entry state summary

```text
B9.92 STATUS:         CLOSED
B9.92 IMPLEMENTATION: PERFORMED — faf24123540ba5a9590de4eeb5757faf64911e1c
B9.92 VERIFICATION:   PASS — see 35.11
B9.92 CLOSURE:        PERFORMED — by this record (closure commit PENDING by the
                      section 11 two-step mechanism)
B9.91:                CLOSED / PUBLISHED — preserved verbatim (section 34)
B9.93+:               NOT ALLOCATED
```

Working tree at the allocation anchor (historical, see 35.8):
  tracked tree clean apart from this allocation record; git diff --check clean;
  ahead/behind origin/main 0/0; the only untracked file is the pre-existing,
  unstaged docs/post-b990-architectural-decision-preparation.md.

### 35.11 B9.92 Closure Record

This record transitions B9.92 from ALLOCATED to CLOSED. It was preceded by a
READ-ONLY Implementation Readiness Audit, the implementation task, a READ-ONLY
Evidence Completion Audit, a READ-ONLY Publication Preflight, a fast-forward
publication, and a READ-ONLY Closure / Roadmap Completion Audit. Each gate is
recorded below with the evidence it actually produced.

**Implementation commit (published):**

```text
faf24123540ba5a9590de4eeb5757faf64911e1c
feat: add CLI model inspection flow
```

Changed paths, exactly:

```text
README.md                      command-reference row and read-only command list
castlearq/main.py              inspect_command, projection, composition adapter,
                               and the additive CLI registration points
tests/test_b9765_json_cli.py   exact _JSON_COMMANDS tuple extension
tests/test_b992_cli_inspect.py focused B9.92 tests (new)
```

**Verification evidence, as actually measured:**

```text
Focused B9.92 tests:        26 passed
Relevant regression tests:  435 passed, 71 subtests passed
Full repository suite:      2237 passed, 2718 subtests passed
Failures:                   0
Errors:                     0
AC1-AC14:                   PASS (individually evidenced)
```

**Acceptance criteria results.** Each criterion was audited separately against
source, tests, observed CLI behaviour and published repository state. No
criterion was weakened, merged or removed, and no criterion was added.

```text
AC1   PASS  read-only inspect reaches the B9.80 ModelDiscovery boundary; the
            legacy HuggingFaceSource path is not used
AC2   PASS  inspection succeeds for repositories absent from the identity
            table; no identity entry is created or required
AC3   PASS  repository, variant/declared_quantization, filename,
            declared_size, declared_sha256 and revision are exposed; nothing
            is invented
AC4   PASS  metadata stays DECLARED/unverified; absent values print Unknown and
            are never defaulted or promoted
AC5   PASS  discovery-produced variant grouping and artifact order are
            reproduced, not re-derived, re-sorted or re-grouped
AC6   PASS  B9.84 remains the sole deterministic selection authority; no
            selection algorithm, ranking, preference or fallback was added
AC7   PASS  acquisition unchanged; no ArtifactSpec, URL, planner, downloader or
            ModelStore state is constructed, and no second acquisition path exists
AC8   PASS  revision is display-only; B9.90 locator semantics are untouched
AC9   PASS  model_identity.py, model_domain.py, model_store.py, downloads/* and
            the B9.80-B9.91 contracts are unmodified
AC10  PASS  additive only; no existing command renamed, removed or re-scoped
AC11  PASS  legacy source/plan/run commands remain functional and unmigrated
AC12  PASS  no GUI, persistence, catalog, cache, ranking, recommendation,
            fuzzy/semantic search, provider federation or new model hierarchy
AC13  PASS  exit codes follow the documented 0/1/2 convention; errors remain
            categorized (inspect_discovery_failed)
AC14  PASS  focused B9.92 tests cover the inspection behaviour and the full
            suite passes
```

**Boundary and dependency evidence.**

```text
Protected architecture diff at faf2412: EMPTY
  discovery.py, sources/huggingface_discovery.py, catalog_query_service.py,
  discovery_selection.py, application_wiring.py, acquisition_service.py,
  acquisition_mapping.py, downloads/, model_identity.py, model_domain.py,
  dynamic_model_library.py, model_store.py

Dependencies CLOSED:
  B9.80  d49a909  B9.81  ef452b2  B9.84  5a40421  B9.85  c2eeb44
  B9.86  aacbc8e  B9.90  8575468  B9.91  d50809d
```

**Publication evidence.**

```text
origin/main = faf24123540ba5a9590de4eeb5757faf64911e1c
Remote transition: e843ebd -> faf2412, a normal fast-forward.
No force push, no --force-with-lease, and no history rewrite were used.
```

**Terminology reconciliation.** Sections 35.2 and 35.3 previously named the
application-boundary method `ModelCatalogQueryService.search(...)`. The actual
existing service contract is `ModelCatalogQueryService.query(...)`. B9.92 does
not invoke that method directly, so the mismatch was non-blocking documentation
drift. Only the two B9.92 references were corrected; the method was **not**
renamed in code and no B9.80-B9.91 record was modified. Other blocks already
describe the same method as `query()`.

**Allocation commit field.** Section 35.1 records `Allocation Commit: PENDING`
by the section 11 two-step mechanism. No separate commit titled "docs: allocate
roadmap block B9.92" exists in the rewritten history, so no authoritative
allocation SHA can be proven. The field therefore **remains PENDING** and no
hash was fabricated. The implementation, verification and closure evidence in
this record is authoritative; it does not depend on that field.

**Closure statement.**

```text
IMPLEMENTATION:   PERFORMED
VERIFICATION:     PASS
PUBLICATION:      PERFORMED (origin/main == faf2412)
CLOSURE:          PERFORMED

B9.92 = CLOSED
```

B9.93+ remains NOT ALLOCATED. No new block, scope, decision or capability is
introduced by this record.

---

## 36. B9.93 — Number Allocation Record

`B9.93` is allocated as the next main block under section 6, on the evidence of a
section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.93 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified architectural decision recorded in
`docs/b993-model-identity-expansion-human-architectural-decision-record.md`,
which was preceded by a READ-ONLY Human Architectural Decision Preparation
Audit and a READ-ONLY Formal Roadmap Allocation Audit, both of which returned
PASS. This section allocates the number that carries that scope; it does not
widen, reinterpret or extend it.

### 36.1 Allocation evidence block

```text
Assigned Number:
  B9.93

Title:
  Model Identity Expansion — Explicit Multi-Layer Identity Model

Allocation Date:
  2026-10-03

Allocation Commit:
  b8d754b41234880b0d83fee6f31de1a8c5c07691
  ("docs: allocate roadmap block B9.93")
```
  Fixed by the next controlled commit, per the two-step mechanism stated in
  section 11 and used identically by sections 14, 16, 19, 21, 23, 25, 27, 29,
  31, 33, 34 and 35. At allocation-authoring time the hash did not exist and
  the field read PENDING; a commit hash cannot be known before the commit
  exists, and writing a guessed value would be a fabricated identifier. The
  allocation itself is unchanged by this fix.

```text
Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 35 — B9.92 Number Allocation Record and closure transition
Section for this allocation:
  section 36 — this record

Origin:
  controlled B9.93 human architectural decision and formal allocation audit

Human Product / Architectural Decision Record:
  Model Identity Expansion — Explicit Multi-Layer Identity Model
  docs/b993-model-identity-expansion-human-architectural-decision-record.md
  STATUS: HUMAN-RATIFIED
  DECISION: OPTION D — EXPLICIT MULTI-LAYER IDENTITY MODEL (ratified)
  POSTURE: INCREMENTAL / MINIMAL
  NUMBER (at ratification): NONE — the decision record assigned no identifier;
                              this section performs the allocation

Corpus/HEAD Anchor:
  3e293e936387c3ec6420a9e7ef0e8ce22b05507a
Corpus File Count:
  230 versioned files (git ls-files at the anchor above)

Corpus Integrity Evidence:
  The corpus is fixed by the anchor commit itself: HEAD and origin/main both
  name 3e293e936387c3ec6420a9e7ef0e8ce22b05507a, the tracked working tree is
  clean (git diff and git diff --cached empty), and the only untracked files at
  the anchor are the pre-existing, deliberately unstaged
  docs/post-b990-architectural-decision-preparation.md and the ratified but
  deliberately unstaged
  docs/b993-model-identity-expansion-human-architectural-decision-record.md.
  Identifier discovery was performed across the whole tracked corpus, not by
  reading documents alone (section 6 requires corpus inspection, not document
  reading).

Identifier Set:
  Highest main identifier in real use before this section: B9.92
  Preceding closed block: B9.92 (section 35), ALLOCATED / IMPLEMENTED /
    VERIFIED / CLOSED, published at 3e293e936387c3ec6420a9e7ef0e8ce22b05507a.
  B9.93 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.93 in the anchor corpus:
  They are explicit non-allocations or historical declines; none allocates
  B9.93:
    - section 35.1: "no B9.93 or later main block, sub-block or alias is
      assigned by this record."
    - section 35.2 candidate analysis: "B9.93 and above — CONSIDERED AND
      DECLINED ... B9.93 would skip B9.92 and is therefore invalid." That
      decline was accurate at its own anchor, when B9.92 was still
      unallocated, and is preserved as history rather than rewritten, exactly
      as section 35 itself recorded for B9.92.
    - section 35.13: "B9.93+ is NOT allocated by this record."
    - section 35.14: "B9.93+: NOT ALLOCATED"
    - section 35.11 closure statement: "B9.93+ remains NOT ALLOCATED."

Highest Verified Main Block:
  B9.92

Rule in Force:
  Section 6 — next_main_block = highest_verified_main_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled human allocation. The architectural direction was selected by the
  project owner; the number is assigned by this section under the section 6
  and section 7 procedure. No sub-block, alias or renamed identifier is minted.

Candidate Numbers Considered:
```text
B9.93 — SELECTED. highest_verified_allocated_block + 1 = B9.92 + 1. No
  allocation, reservation, provisional assignment, sub-block or competing
  claim exists for it anywhere in the anchor corpus; every pre-existing
  occurrence is an explicit non-allocation or the historical decline recorded
  at section 35.2, which was accurate at its own anchor and is preserved
  rather than rewritten.

B9.92 and below — CONSIDERED AND DECLINED. Section 6 fixes the floor at the
  highest VERIFIED allocated identifier; B9.92 is already allocated,
  implemented, verified, closed and published. No gap is claimed abandoned,
  freed, reserved or erroneous (section 13).

B9.94 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
  immediately following the highest verified main block. B9.94 would skip
  B9.93 and is therefore invalid.

B9.93.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
  integers of the form B9.x raise the main-block floor, and a sub-block does
  not by itself advance the next main block number.

Any alias, umbrella or renamed identifier — CONSIDERED AND DECLINED. Section 6
  admits only the integer form; no alias is minted.
```

Selected Number:
```text
B9.93
```

Validity Reason:
  B9.92 is the highest allocated, implemented, verified, closed and published
  main block in the corpus anchor named above, and B9.93 was free of any
  competing claim there. The assignment therefore satisfies section 6 and is
  accompanied by the complete section 11 record.

### 36.2 Register entry for B9.93

```text
B9.93 — Model Identity Expansion (Explicit Multi-Layer Identity Model)
STATUS: CLOSED
IMPLEMENTATION: PERFORMED — 44e04261f42b179dc9f91c60a594f305dfa2512e
VERIFICATION:   PASS — see 36.11
CLOSURE:        PERFORMED — by this record (closure commit PENDING by the
                section 11 two-step mechanism)
```

### 36.3 Scope attached to this allocation

```text
CONTRACT DECLARATION + CONTRACT TESTS ONLY
No behaviour change.
```

The ratified architectural decision encoded by this allocation:

```text
DECISION:            Option D — Explicit Multi-Layer Identity Model
IMPLEMENTATION
POSTURE:             INCREMENTAL / MINIMAL
CARDINALITY:         1 repository -> 1 logical model
DISCOVERY:           IDENTITY-FREE
PROVIDER IDENTITY:   NOT AUTHORITATIVE
B8.1 ModelIdentity:  PARALLEL / NOT CONVERGED
```

Layer separation ratified as an architectural conceptual contract:

```text
1. Logical Model
2. Variant
3. Artifact
4. Revision
5. Locator
6. Storage Identity

Governing rule:
  No layer may be substituted for or silently promoted to another layer.
```

Logical identity under this allocation:

```text
model_id: str remains the canonical logical model identity.
logical_model_id(...) remains the single identity authority.
No new nominal identity type is introduced.
SOURCE_REPOSITORY_TO_MODEL_ID remains in place and remains in use.
downloadable_locator remains the download gate.
```

Intended minimal implementation surface (declared here, NOT performed by this
record):

```text
castlearq/model_identity.py   documentation contract only; zero executable
                              statement may change
tests/                        focused B9.93 layer-contract tests, following the
                              per-block focused-test convention used by B9.80-B9.92
```

All other modules are outside the implementation surface, including
`model_domain.py`, `discovery.py`, `sources/huggingface_discovery.py`,
`discovery_selection.py`, `acquisition_mapping.py`, `acquisition_service.py`,
`downloads/planner.py`, `downloads/downloader.py`, `model_store.py`,
`manifest_migration.py`, `api.py`, `main.py`, `application_wiring.py` and
`models.py`.

### 36.4 Non-goals

B9.93 MUST NOT include, and this allocation does not authorize:

```text
GUI
Model Library UI
persistent catalog
database
provider federation
second provider
fuzzy search
semantic search
ranking
recommendation
download progress
resumable downloads
ModelStore redesign
filesystem redesign
manifest redesign
migration redesign
multi-revision coexistence
multi-GPU
fine-tuning
LoRA / QLoRA
datasets
evaluation infrastructure
legacy convergence
CLI redesign
B8.1 convergence
provider-declared identity
1 -> N repository/model mapping
concrete model registry expansion
B9.94 and any later identifier
```

No future work is added to B9.93 by this record.

### 36.5 Dependencies (verified closed)

```text
NOT A DEPENDENCY (consumed as-is, unchanged by B9.93):
  B9.80  discovery domain
  B9.81  Hugging Face discovery provider
  B9.82  discovery -> acquisition mapping
  B9.83  revision-aware acquisition (OD-1)
  B9.84  selection boundary
  B9.85  acquisition service
  B9.86  catalog query boundary
  B9.87  CLI catalog query caller
  B9.88  chat / application boundary CLI caller
  B9.89  run boundary
  B9.90  canonical revision-aware locator
  B9.91  internal Dynamic Model Library
  B9.92  CLI discover -> inspect -> select -> acquire

PARALLEL (explicitly not converged):
  B8.1 model_domain.ModelIdentity / ModelArtifact

NOT A DEPENDENCY (untouched):
  legacy ModelSource architecture
  ModelStore

PREREQUISITE BLOCKS: NONE
```

### 36.6 Acceptance criteria

Drafted at allocation time. They are objective and do not weaken, weaken-and-
reinterpret or relax any ratified invariant.

```text
AC1  Logical identity semantics: `model_id` remains a str;
     `logical_model_id` remains the sole authority; no nominal identity
     type is introduced.

AC2  Variant separation: `ModelVariant` remains provider-owned,
     identity-free and ungrouped by B9.93.

AC3  Artifact separation: `ArtifactSpec.model_id` remains a REFERENCE to
     the logical identity; no artifact field redefines model identity.

AC4  Revision separation: revision remains distinct from logical identity
     and remains EXCLUDED from `artifact_id`; an absent revision stays
     None; the B9.83/B9.90 revision contract is unchanged.

AC5  Locator separation: `downloadable_locator` remains an acquisition
     concern; a locator is never stored as identity and never becomes
     logical model identity.

AC6  Storage identity separation: ModelStore layout, the `artifact_id`
     formula and the manifest schema are unchanged; no storage migration
     occurs; storage identity remains a persistence concern.

AC7  Discovery remains identity-free: `DiscoveredArtifact.model_id`
     remains None; no logical identity is added to the discovery domain.

AC8  Provider remains non-authoritative: provider-declared identity is
     not trusted; the contradictory-declared-identity rejection in the
     acquisition service is unchanged; B9.82 and B9.85 are not reopened.

AC9  Cardinality preserved: 1 repository -> 1 logical model;
     `downloadable_locator` still returns None when the locator count is
     not exactly one; no 1 -> N mapping is introduced.

AC10 B8.1 remains parallel: `model_domain.py`, `evaluation_adapter.py` and
     `ModelArtifact.identifier` are unmodified; no convergence occurs.

AC11 Acquisition behaviour preserved: `model_identity.py` has zero change
     to any executable statement; discovery, mapping, planner, downloader,
     store and migration contracts are unchanged.

AC12 Regression suite: the full existing test suite remains green; the new
     B9.93 tests cover the layer-separation contract only and do not
     weaken any existing test.
```

### 36.7 Closure evidence expected

```text
Before closure, B9.93 will require:
  - the implementation commit actually performed;
  - the focused B9.93 test results;
  - confirmation that AC1-AC12 are evaluated against observable behaviour;
  - confirmation that model_identity.py changed documentation only;
  - confirmation that the protected architecture diff is EMPTY;
  - confirmation that no roadmap record above this section was modified;
  - confirmation that no source file outside the declared implementation
    surface changed;
  - the two-step allocation-commit field resolved to a real hash.
```

### 36.8 Allocation versus implementation state (as asserted by this NAR)

This subsection recorded the ALLOCATION-TIME state and is preserved verbatim
as history; the authoritative post-implementation state is recorded in 36.11.

```text
AT ALLOCATION TIME (preserved, historical):

B9.93 IS:     an allocated identifier carrying a ratified scope
B9.93 IS NOT: implemented
B9.93 IS NOT: verified
B9.93 IS NOT: closed

IMPLEMENTATION: NOT PERFORMED
VERIFICATION:   NOT PERFORMED
PUBLICATION:    NOT PERFORMED
CLOSURE:        NOT PERFORMED

Protected architecture diff at this anchor: EMPTY
  model_domain.py, discovery.py, sources/huggingface_discovery.py,
  discovery_selection.py, acquisition_mapping.py, acquisition_service.py,
  downloads/, model_store.py, manifest_migration.py, api.py, main.py,
  application_wiring.py, models.py
```

### 36.9 Human approval reference

```text
Human Architectural Decision:
  SELECTED — OPTION D — EXPLICIT MULTI-LAYER IDENTITY MODEL
  Source record:
    docs/b993-model-identity-expansion-human-architectural-decision-record.md
  READ-ONLY audits preceding the allocation:
    Human Architectural Decision Preparation Audit
    Formal Roadmap Allocation Audit — PASS

The decision is not reopened, re-compared or re-scored by this record.
```

### 36.10 Register entry state summary

```text
B9.92  CLOSED
B9.93  CLOSED
B9.94+ NOT ALLOCATED
```

B9.94+ remains NOT ALLOCATED. No new block, scope, decision or capability is
introduced by this record beyond the B9.93 closure stated above.

### 36.11 B9.93 Closure Record

This record transitions B9.93 from ALLOCATED to CLOSED. It was preceded by the
implementation commit
44e04261f42b179dc9f91c60a594f305dfa2512e
("feat: formalize B9.93 model identity layer contract"), which was itself
preceded by the human-ratified decision record and by three READ-ONLY audits:
Implementation Evidence, Evidence Completion, and Closure Audit. The Closure
Audit returned PASS — READY FOR FORMAL CLOSURE.

```text
IMPLEMENTATION COMMIT:
  44e04261f42b179dc9f91c60a594f305dfa2512e
  "feat: formalize B9.93 model identity layer contract"
  Parent: 792493be4f48fd6c5387a0e5433a06d3ed3f4318

Files changed by the implementation commit (exactly 2):
  castlearq/model_identity.py                     (documentation only)
  tests/test_b993_layer_separation_contract.py    (new, 9 tests / 5 classes)
```

**Scope evidence.** The implementation is exactly the scope allocated in
36.3: CONTRACT DECLARATION + CONTRACT TESTS ONLY, with no behaviour change.

```text
castlearq/model_identity.py
  documentation-only change: 97 insertions, 0 deletions
  executable AST IDENTICAL between the parent commit and the working tree
    non-docstring executable statements: 15
    sha256(ast-dump, docstrings stripped):
      0bed473b971fc2aa70bbb5254a8bc40a076d7b22a56d07efb783e54d532d80b4
  no new def, class, constant, mapping, import or public symbol
  no change to SOURCE_REPOSITORY_TO_MODEL_ID, SUPPORTED_DOWNLOAD_SOURCES,
    logical_model_id, source_repositories_for_logical_model,
    downloadable_locator
```

**Verification evidence (AC1-AC12).**

```text
AC1  PASS  logical model identity canonical, still str; unmapped repository
            yields no identity
AC2  PASS  ModelVariant untouched, provider-owned, identity-free
AC3  PASS  quantization shapes artifact_id while model_id is unchanged
AC4  PASS  differing revision yields identical artifact_id (OD-1)
AC5  PASS  supported model resolves to its locator; unknown model resolves
            to None
AC6  PASS  ModelStore layout, artifact_id formula and manifest schema
            unchanged; no storage migration
AC7  PASS  DiscoveredArtifact.model_id is None
AC8  PASS  provider-declared model_id is non-authoritative and creates no
            registry entry
AC9  PASS  zero locators -> None; two locators -> None (exactly-one gate)
AC10 PASS  model_domain.py unchanged; B8.1 remains parallel / not converged
AC11 PASS  no runtime redesign; executable AST identical; 1 modified source
            file and 1 new test file only
AC12 PASS  full regression verification green

Test evidence:
  tests/test_b993_layer_separation_contract.py     9 passed
  tests/test_model_identity.py                   14 passed, 11 subtests
  B9.80-B9.92 focused regression set (9 files)   275 passed, 31 subtests
  full suite                                   2246 passed, 2718 subtests
  failures: 0   errors: 0
```

**Boundary and dependency evidence.**

```text
Protected architecture diff at 44e0426: EMPTY
  model_domain.py, discovery.py, sources/huggingface_discovery.py,
  discovery_selection.py, acquisition_mapping.py, acquisition_service.py,
  downloads/planner.py, downloads/downloader.py, model_store.py,
  manifest_migration.py, api.py, main.py, application_wiring.py, models.py,
  tests/test_model_identity.py

No roadmap record above section 36 was modified by this closure.
No ADR or preparation document was modified by this closure.
No prior B9.80-B9.92 decision was reopened or superseded by B9.93.
```

**Preserved decisions.** The ratified Option D architecture is unchanged by
this closure: Option D (Explicit Multi-Layer Identity Model); INCREMENTAL /
MINIMAL posture; the Logical Model / Variant / Artifact / Revision / Locator /
Storage Identity separation with the governing rule that no layer may
substitute for or be silently promoted to another; 1 repository -> 1 logical
model cardinality; discovery identity-free; provider-declared identity not
authoritative; B8.1 parallel and unconverged. Every non-goal in 36.4 remains in
force, including no GUI, no persistent Model Library, no ModelStore redesign, no
provider federation, no 1 -> N identity expansion and no legacy convergence.
No acceptance criterion, dependency, non-goal or scope item was added, removed or
weakened by this closure.

**Allocation evidence.** 36.1 records `Allocation Commit:
b8d754b41234880b0d83fee6f31de1a8c5c07691`, fixed by
792493be4f48fd6c5387a0e5433a06d3ed3f4318
("docs: fix B9.93 allocation commit anchor"). That anchor is unchanged by this
closure and must not be confused with the implementation commit above.

**Publication state.** NOT PERFORMED. This closure exists locally only; at the
time of this record `main` is two commits ahead of `origin/main`
(792493be4f48fd6c5387a0e5433a06d3ed3f4318) and nothing has been pushed.

**Closure statement.**

```text
IMPLEMENTATION:   PERFORMED — 44e04261f42b179dc9f91c60a594f305dfa2512e
VERIFICATION:     PASS
PUBLICATION:      NOT PERFORMED
CLOSURE:          PERFORMED — by this record

B9.93 = CLOSED
```

B9.94+ remains NOT ALLOCATED. No new block, scope, decision or capability is
introduced by this record.

---

## 37. B9.94 — Number Allocation Record

`B9.94` is allocated as the next main block under section 6, on the evidence of a
section 7 corpus inspection performed at allocation time. This section is the
section 11 record for that assignment. At allocation time B9.94 is **an
allocation only**: no implementation, no verification and no closure is claimed
by this section.

The scope was **not chosen by this record**. It was fixed beforehand by the
human-ratified product/architectural decision recorded in
`docs/b994-acquisition-first-human-architectural-decision-record.md`, which was
preceded by a READ-ONLY Human Architectural Decision Audit and a READ-ONLY Formal
Roadmap Allocation Audit, both of which returned PASS. This section allocates the
number that carries that scope; it does not widen, reinterpret or extend it.

### 37.1 Allocation evidence block

```text
Assigned Number:
  B9.94

Title:
  Acquisition-First Product Direction

Allocation Date:
  2026-10-04

Allocation Commit:
  PENDING — fixed by the next controlled commit that sets it to that hash
  ("docs: allocate roadmap block B9.94")
```
  Recorded by the two-step mechanism stated in section 11 and used identically
  by sections 14, 16, 19, 21, 23, 25, 27, 29, 31, 33, 34, 35 and 36: at
  authoring time the hash did not exist and the field reads PENDING; a commit
  hash cannot be known before the commit exists, and writing a guessed value
  would be a fabricated identifier. The allocation itself is unchanged.

```text
Roadmap file:
  docs/roadmap-register-and-numbering-policy.md
Highest existing section before this one:
  section 36 — B9.93 Number Allocation Record and closure transition
Section for this allocation:
  section 37 — this record

Origin:
  controlled B9.94 human architectural decision and formal allocation audit

Human Product / Architectural Decision Record:
  Acquisition-First Product Direction
  docs/b994-acquisition-first-human-architectural-decision-record.md
  STATUS: HUMAN-RATIFIED
  DECISION: OPTION 1 — ACQUISITION-FIRST (ratified)
  DECISION AUTHORITY: PROJECT OWNER
  POSTURE: INCREMENTAL / IDENTITY-PRESERVING
  NUMBER (at ratification): NONE — the decision record assigned no identifier;
                              this section performs the allocation

Corpus/HEAD Anchor:
  3fc5231f3569b2f2331f56b01ea1b6eb71def5d6
Corpus File Count:
  231 versioned files (git ls-files at the anchor above)

Corpus Integrity Evidence:
  The corpus is fixed by the anchor commit itself: HEAD, origin/main and
  refs/remotes/origin/main all name
  3fc5231f3569b2f2331f56b01ea1b6eb71def5d6, the tracked working tree is clean
  (git diff and git diff --cached empty), and the only untracked files at the
  anchor are the pre-existing, deliberately unstaged
  docs/post-b990-architectural-decision-preparation.md, the ratified but
  deliberately unstaged
  docs/b993-model-identity-expansion-human-architectural-decision-record.md and
  the ratified but deliberately unstaged
  docs/b994-acquisition-first-human-architectural-decision-record.md.
  Identifier discovery was performed across the whole tracked corpus, not by
  reading documents alone (section 6 requires corpus inspection, not document
  reading).

Identifier Set:
  Highest main identifier in real use before this section: B9.93
  Preceding closed block: B9.93 (section 36), ALLOCATED / IMPLEMENTED /
    VERIFIED / CLOSED, published at
    3fc5231f3569b2f2331f56b01ea1b6eb71def5d6.
  B9.94 does not previously appear as an allocation anywhere in the corpus.

Pre-existing occurrences of B9.94 in the anchor corpus:
  They are explicit non-allocations or historical declines; none allocates
  B9.94:
    - section 36.2 candidate analysis: "B9.94 and above — CONSIDERED AND
      DECLINED ... B9.94 would skip B9.93 and is therefore invalid."
    - section 36.4 non-goals: "B9.94 and any later identifier"
    - section 36.10: "B9.94+ NOT ALLOCATED"
    - section 36.11 closure statement: "B9.94+ remains NOT ALLOCATED."
  Each of those statements was accurate at its own anchor, when B9.93 was
  already the highest verified main block, and each is preserved as history
  rather than rewritten. The current authoritative state of B9.94 is the one
  asserted by this section.
    - Untracked, non-allocating: line 32 and line 1064 of
      docs/b993-model-identity-expansion-human-architectural-decision-record.md
      ("does NOT open, reserve or imply B9.94 or any later identifier").
    - Untracked, non-allocating: the B9.94 decision record itself, whose
      sections 1, 3 and 14 state that it does not allocate B9.94 and that
      B9.94 / B9.95+ remain NOT ALLOCATED.

  No competing, pending, provisional, reserved or conflicting identifier was
  found in the corpus. No B9.95 or later main block, sub-block or alias is
  assigned by this record.

Preceding Block:
  B9.93 — Model Identity Expansion (Explicit Multi-Layer Identity Model)

Preceding Block Status:
  ALLOCATED (section 36), IMPLEMENTED (44e0426), VERIFIED, CLOSED
  (section 36.11), published state main == HEAD == origin/main at the anchor
  above.

Highest Verified Main Block:
  B9.93

Rule in Force:
  Section 6 — next_main_block = highest_verified_main_block + 1

Rule Activation Anchor:
  f77f00d6c0eee177a7b53c87584f391e460f11e3

Actor/Process:
  Controlled human allocation. The strategic direction was selected by the
  project owner; the number is assigned by this section under the section 6 and
  section 7 procedure. No sub-block, alias or renamed identifier is minted.

Candidate Numbers Considered:
```text
B9.94 — SELECTED. highest_verified_allocated_block + 1 = B9.93 + 1. No
  allocation, reservation, provisional assignment, sub-block or competing
  claim exists for it anywhere in the anchor corpus; every pre-existing
  occurrence is an explicit non-allocation or the historical decline recorded
  at section 36.2, which was accurate at its own anchor and is preserved
  rather than rewritten.

B9.93 and below — CONSIDERED AND DECLINED. Section 6 fixes the floor at the
  highest VERIFIED allocated identifier; B9.93 is already allocated,
  implemented, verified, closed and published. No gap is claimed abandoned,
  freed, reserved or erroneous (section 9, section 13).

B9.95 and above — CONSIDERED AND DECLINED. Section 6 requires the integer
  immediately following the highest verified main block. B9.95 would skip
  B9.94 and is therefore invalid.

B9.94.x and every other sub-block — CONSIDERED AND DECLINED. Section 8: only
  integers of the form B9.x raise the main-block floor, and a sub-block does
  not by itself advance the next main block number.

Any alias, umbrella or renamed identifier — CONSIDERED AND DECLINED. Section 6
  admits only the integer form; no alias is minted.
```

Selected Number:

```text
B9.94
```

Validity Reason:
  B9.93 is the highest allocated, implemented, verified, closed and published
  main block in the corpus anchor named above, and B9.94 was free of any
  competing claim there. The assignment therefore satisfies section 6 and is
  accompanied by the complete section 11 record.

Release Association:

```text
NOT YET DEFINED
```

Supersession:

```text
none as to B9.93 or any earlier block — those allocation and closure records
remain the accurate description of those blocks and are not rewritten by this
section.

cross-reference only — the "B9.94 and above — CONSIDERED AND DECLINED",
"B9.94 and any later identifier", "B9.94+ NOT ALLOCATED" and "B9.94+ remains
NOT ALLOCATED" statements in section 36 remain the accurate description of the
corpus at their own anchors and are not rewritten. They are superseded by this
record as a cross-reference only.
```

Documented?:

```text
YES — this section.
```

### 37.2 Register entry for B9.94

```text
B9.94 — Acquisition-First Product Direction
STATUS: ALLOCATED
IMPLEMENTATION: NOT PERFORMED
VERIFICATION:   NOT PERFORMED
CLOSURE:        NOT PERFORMED
```

### 37.3 Scope attached to this allocation

```text
PRODUCT / ARCHITECTURAL DIRECTION ALLOCATION ONLY.
No source, test, configuration, packaging, CLI or roadmap-surface change is
performed or authorized by this section.
```

The ratified direction encoded by this allocation:

> Evolve CastleArq from its current curated model-acquisition admission
> boundary toward a user-selected Hugging Face GGUF acquisition flow, while
> preserving the explicit separation between logical model identity,
> repository, variant, artifact, revision, locator, and storage identity.

Architectural boundary preserved by this allocation:

```text
CURRENT (as ratified by B9.93 and unchanged by this allocation):
  arbitrary discovery / inspection
      -> curated identity admission
          -> acquisition

TARGET DIRECTION (authorized direction, mechanism undecided):
  user-selected GGUF repository / artifact
      -> explicit acquisition admission
          -> existing acquisition chain
```

The admission gate remains a gate. What may change is what is permitted to pass
through it, and under which explicit, tested, fail-closed contract.

Constraints preserved in full and binding on any future B9.94 implementation:

```text
Logical Model    !=  Repository
Logical Model    !=  Variant
Logical Model    !=  Artifact
Logical Model    !=  Revision
Logical Model    !=  Locator
Logical Model    !=  Storage Identity

Governing rule (restated from B9.93, unchanged):
  No layer may be substituted for or be silently promoted to another layer.

CARDINALITY:              1 repository -> 1 logical model, PRESERVED
DISCOVERY:                IDENTITY-FREE
PROVIDER-DECLARED ID:     NOT AUTHORITATIVE
REVISION:                 SEPARATE from logical identity; excluded from artifact
                          identity under the ratified OD-1 decision
B8.1 ModelIdentity:       PARALLEL / NOT CONVERGED
```

The existing curated registry behaviour remains valid unless and until a B9.94
implementation design explicitly supersedes it. The concept of the gate is not
deleted in order to widen it.

### 37.4 Identity-admission mechanism is NOT prescribed

The B9.94 decision deliberately leaves the identity-admission mechanism
undecided. This allocation therefore MUST NOT, and does not, prescribe:

```text
user-supplied identity as the final mechanism
deterministic identity derivation as the final mechanism
automatic registry insertion as the final mechanism
repository-backed identity registration as the final mechanism
any database identity mechanism
any provider-declared identity mechanism
any filename-derived identity
any revision-derived identity
any URL- or locator-derived identity
any storage-path-derived identity
```

The seam is preserved as a seam:

```text
user-selected repository / artifact
    -> identity / acquisition admission boundary
        -> existing acquisition chain
```

The concrete mechanism must be determined during the B9.94 implementation-design
phase, subject in full to the B9.94 decision record and to the constraints
recorded in 37.3. If an implementation appears to require collapsing two identity
layers, that is evidence that the mechanism is wrong, not evidence that the
constraint may be relaxed.

### 37.5 Non-goals

B9.94 MUST NOT include, and this allocation does not authorize:

```text
GUI
Model Library UI
persistent user-facing Model Library
persistent catalog
database
semantic search
fuzzy search
ranking
recommendation
multiple providers
provider federation
ModelStore redesign
manifest redesign
filesystem layout redesign
migration redesign
multi-revision storage coexistence
1 -> N repository/model cardinality
provider-declared identity becoming authoritative
repository, filename or quantization becoming a logical model identity
hardware-aware planning
context / KV-cache calculation
GPU layer-offload planning
execution-parameter emission
llama.cpp provisioning
runtime / binary preparation
Windows support
macOS support
WSL2 support
any non-Linux execution claim
B8.1 ModelIdentity convergence
legacy ModelSource removal or convergence
run versus execute redesign
ModelExecutionService redesign
B9.95 and any later identifier
```

No future work is added to B9.94 by this record.

### 37.6 Dependencies

```text
REQUIRED (B9.94 cannot be implemented without these; all are CLOSED):

  B9.80  Model Discovery domain contract
  B9.81  Hugging Face discovery provider
  B9.82  Discovery-to-Acquisition mapping boundary
  B9.85  Production acquisition chain
  B9.90  Revision-aware acquisition
  B9.93  Explicit multi-layer identity model

HELPFUL (improve B9.94 but are NOT required; must NOT become requirements):

  B9.84  Selection boundary
  B9.91  Internal Dynamic Model Library (live / stateless)
  B9.92  CLI Discovery-to-Acquisition inspection flow

SEPARATE FUTURE DECISION SURFACES (must NOT become B9.94 dependencies):

  Model Library UX
  hardware-aware planning
  runtime autonomy / llama.cpp provisioning
  Windows / macOS / WSL2
  B8.1 ModelIdentity convergence
  legacy ModelSource convergence
  ModelStore / manifest / migration redesign
  multi-provider / federation

PARALLEL (explicitly not converged):
  B8.1 model_domain.ModelIdentity / ModelArtifact

PREREQUISITE BLOCKS: NONE beyond the REQUIRED set above, all already CLOSED.
```

### 37.7 Acceptance criteria basis

Carried forward from the B9.94 decision record, section 13. These are the
architectural basis on which a later implementation would be drafted and
verified. This section neither satisfies nor verifies any of them, and it does not
convert them into implementation steps.

```text
AC1  User-selected GGUF acquisition becomes possible WITHOUT collapsing
     repository into logical model identity.

AC2  Logical model, repository, variant, artifact, revision, locator and
     storage identity remain distinct and separately governed.

AC3  Revision-aware acquisition semantics remain valid, including the
     ratified OD-1 decision that revision does not participate in artifact
     identity.

AC4  Discovery remains identity-free: repository and artifact inspection stays
     independent of acquisition identity.

AC5  Acquisition admission is explicit and fails closed when required identity
     information is unavailable. No identity is fabricated, guessed or
     defaulted, and no fuzzy, basename or inference heuristic is used.

AC6  The 1 -> 1 repository/logical-model cardinality contract remains intact
     unless a separate architectural decision explicitly authorizes another
     cardinality; any such need is escalated, not resolved incidentally.

AC7  Existing curated acquisition behaviour remains valid unless and until
     explicitly superseded by the B9.94 implementation design.

AC8  No GUI, database, persistent catalog, multi-provider, hardware-planning or
     runtime-provisioning behaviour is introduced unless separately authorized.

AC9  Existing B9.80 - B9.93 contracts remain regression-safe.

AC10 B9.94 does not pre-empt the later decisions concerning hardware-aware
     planning, runtime autonomy, cross-platform support, Model Library UX or
     identity convergence.
```

### 37.8 Closure evidence expected

```text
Before closure, B9.94 will require:
  - the implementation commit actually performed;
  - the focused B9.94 test results and the full regression-suite result;
  - confirmation that AC1-AC10 are evaluated against observable behaviour;
  - the explicitly designed and documented acquisition-admission contract,
    including its fail-closed behaviour;
  - confirmation that the identity-admission mechanism chosen by the
    implementation design is recorded and does not collapse any identity layer;
  - confirmation that the 1 -> 1 cardinality contract is preserved, or that a
    separate architectural decision was taken before any change;
  - confirmation that curated acquisition behaviour was preserved or explicitly
    superseded;
  - confirmation that the protected architecture diff is EMPTY for every
    module outside the declared implementation surface;
  - confirmation that no roadmap record above this section was modified;
  - confirmation that no ADR was amended by the implementation;
  - the two-step allocation-commit field resolved to a real hash.
```

### 37.9 Allocation versus implementation state (as asserted by this NAR)

```text
AT ALLOCATION TIME:

B9.94 IS:     an allocated identifier carrying a ratified scope
B9.94 IS NOT: implemented
B9.94 IS NOT: verified
B9.94 IS NOT: closed

IMPLEMENTATION: NOT PERFORMED
VERIFICATION:   NOT PERFORMED
PUBLICATION:    NOT PERFORMED
CLOSURE:        NOT PERFORMED

Protected architecture diff at this anchor: EMPTY
  source, tests, configuration and packaging are unchanged by this section;
  the only file mutated by this allocation is
  docs/roadmap-register-and-numbering-policy.md itself.
```

Lifecycle separation asserted by this section:

```text
allocation    !=  implementation
implementation !=  verification
verification  !=  closure
```

### 37.10 Human approval reference

```text
Human Architectural Decision:
  SELECTED — OPTION 1 — ACQUISITION-FIRST
  Decision Authority: PROJECT OWNER
  Source record:
    docs/b994-acquisition-first-human-architectural-decision-record.md
  READ-ONLY audits preceding the allocation:
    Human Architectural Decision Audit — PASS
    Formal Roadmap Allocation Audit — PASS (outcome A — READY FOR FORMAL
    ALLOCATION)

The decision is not reopened, re-compared, re-scored, widened, weakened or
strengthened by this record.
```

### 37.11 Register entry state summary

```text
B9.92  CLOSED
B9.93  CLOSED
B9.94  ALLOCATED — implementation, verification and closure NOT PERFORMED
B9.95+ NOT ALLOCATED
```

B9.95+ remains NOT ALLOCATED. No new block, scope, decision or capability is
introduced by this record beyond the B9.94 allocation stated above.
