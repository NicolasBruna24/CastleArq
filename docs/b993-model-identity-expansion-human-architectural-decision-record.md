# B9.93 — Human Architectural Decision Record

## Model Identity Expansion

```text
DOCUMENT TYPE:     Human Architectural Decision Record (HADR)
SUBJECT:           B9.93 — Model Identity Expansion
STATUS:            RATIFIED — HUMAN DECISION RECORDED
DECISION:          SELECTED — OPTION D (Explicit Multi-Layer Identity Model)
POSTURE:           INCREMENTAL / MINIMAL
BLOCK STATE:       B9.93 NOT ALLOCATED (no allocation is created by this record)
CODE IMPACT:       NONE — this record is READ-ONLY with respect to source
```

---

## Status

```text
THE HUMAN ARCHITECTURAL DECISION HAS BEEN TAKEN AND IS RECORDED HERE.

SELECTED: Option D — Explicit Multi-Layer Identity Model
POSTURE:  Incremental / minimal
```

This record now documents a ratified human decision. It remains:

```text
This document does NOT allocate B9.93.
This document does NOT implement B9.93.
This document does NOT close B9.93.
This document does NOT open, reserve or imply B9.94 or any later identifier.
This document does NOT modify the roadmap register.
This document does NOT modify source code, tests or configuration.
```

The question that was put to the human:

> What architectural contract should CastleArq adopt to represent and resolve
> logical model identity beyond the current static one-row registry?

The human answer:

> **Option D — Explicit Multi-Layer Identity Model**, adopted as an
> architectural conceptual contract, with an incremental/minimal
> implementation posture.

---

## Baseline

Verified by inspection, not assumed.

```text
Branch:            main
HEAD:              3e293e936387c3ec6420a9e7ef0e8ce22b05507a
origin/main:       3e293e936387c3ec6420a9e7ef0e8ce22b05507a
Ahead/behind:      0 / 0
HEAD subject:      docs: close roadmap block B9.92
Tracked mods:      none
Staged changes:    none
Untracked:         docs/post-b990-architectural-decision-preparation.md
```

Authoritative roadmap state at this baseline:

```text
B9.92 STATUS:         CLOSED                                    (register 9709)
B9.92 IMPLEMENTATION: PERFORMED — faf24123540ba5a9590de4eeb5757faf64911e1c
B9.92 VERIFICATION:   PASS — see 35.11
B9.92 CLOSURE:        PERFORMED by the register closure record
B9.93+:               NOT ALLOCATED                             (register 9715, 9840)
```

Recorded observations about the number B9.93, stated without advancing anything:

```text
Highest verified allocated main block at this anchor: B9.92.
Register section 6 fixes the next main-block integer as
highest_verified + 1, which at this anchor arithmetically yields B9.93.

Register section 35 (9211-9213) contains the line "B9.93 and above —
CONSIDERED AND DECLINED ... B9.93 would skip B9.92 and is therefore
invalid." That statement was accurate AT ITS OWN ANCHOR, when B9.92 was
still unallocated, and the register itself preserves it as history rather
than rewriting it (register 9172-9175). It is reproduced here as fact, not
as a current prohibition, and it is not modified by this record.

This arithmetic is a mechanical consequence that FOLLOWS a ratified
decision; it does not constitute one. No allocation SHA is invented,
claimed or recorded here.
```

---

## Problem Statement

Verified facts:

```text
mapping rows .......................... 1
  ("huggingface", "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF")
    -> "qwen2.5-coder-7b-instruct"
supported download sources ............. 1   ({"huggingface"})
ModelSpec entries in the catalog ...... 3
  qwen2.5-coder-7b-instruct
  llama-3.1-8b-instruct
  deepseek-r1-distill-qwen-14b
downloadable models ................... 1
catalog models with no locator ......... 2
```

Two of three catalog models are, by the current contract, permanently not
downloadable. This is visible to users: `main.py:_download_status` derives
its entire availability text from `downloadable_locator`, so those two models
are reported as "not available yet".

The problem this block must address is **not** "which rows to add". The
problem is:

```text
What does "logical model identity" architecturally MEAN in CastleArq,
and which component is its authority, once more than one logical model
(and more than one repository) is in play?
```

---
## Current Contract

`castlearq/model_identity.py` — verified contents and behaviour:

```text
SOURCE_REPOSITORY_TO_MODEL_ID
    dict[tuple[str, str], str]
    {(source, repository) -> model_id}
    1 row. Pure data. No I/O, no network, no local paths.

logical_model_id(source, repository) -> str | None
    Forward lookup. dict.get. Unknown -> None. Never guesses.

source_repositories_for_logical_model(model_id) -> tuple[(source, repo), ...]
    Reverse index. Sorted, therefore deterministic. Multiple locators are
    NEVER collapsed; the caller decides what to do with the length.

SUPPORTED_DOWNLOAD_SOURCES
    frozenset({"huggingface"})

downloadable_locator(model_id) -> tuple[str, str] | None
    len(locators) != 1          -> None
    source not in SUPPORTED_... -> None
    otherwise                   -> the single locator
    No first-match, no fuzzy/substring matching, no aliases, no I/O.
```

Normative module docstring, quoted in substance: `ModelSpec.model_id` is the
canonical logical identity; `ArtifactSpec.model_id` must reference that same
identity and must never carry a source repository; this table is the single
explicit bridge between a `(source, repository)` locator and the logical
model; repositories without an entry have no logical identity and must be
rejected by discovery, planning and migration.

### The central architectural fact

```text
dict[(source, repository), model_id]
```

already permits, structurally and by type, any number of repositories and any
number of logical models — including one repository resolving to several
logical models. **The type is not the constraint.**

The constraint is `downloadable_locator`'s exactly-one rule. Consequences:

1. A logical model with two mirrors (same model, two repositories) is
   **undownloadable**, not "resolved to a preferred mirror".
2. A repository mapped to two logical models makes **both** undownloadable.
3. The failure is silent by design: it returns `None`, and the reason is
   reconstructed downstream in two separate places —
   `main.py:_download_status` ("multiple sources mapped" vs "unsupported
   source") and `acquisition_service._resolve_repository`
   (`MODEL_NOT_RESOLVABLE`, "unsupported source" vs "no unique source
   repository is mapped").
4. Because the discriminator is duplicated in a presentation adapter and an
   application boundary, the *meaning* of "not downloadable" is expressed in
   more than one place.

### Identity representation

Identity is a bare `str` slug. There is no `ModelId` nominal type, no branded
string, and no validation at declaration time. Identity safety is enforced
downstream, twice, by two independent implementations that deliberately do
not share code:

```text
acquisition_mapping._is_safe_identity      (acquisition_mapping.py:169-183)
  "Mirrors the rejections of the store's _safe_model_id ... this module
   must stay free of it."

ModelStore._safe_model_id                  (model_store.py:462-471)
```

Both reject empty, absolute and dot-segmented values.

### Four coexisting identity flavours (verified)

```text
1. Logical model id    "qwen2.5-coder-7b-instruct"
                       model_identity.py + model_catalog.ModelSpec.id

2. Catalog fallback    ModelSpec.model_id == id or name  (models.py:124)
                       an implicit fallback to the DISPLAY NAME.
## Current Architecture

The ratified chain this block sits downstream of, consumed as-is:

```text
B9.80 discovery domain
B9.81 Hugging Face discovery provider
B9.82 discovery -> acquisition mapping
B9.83 revision-aware acquisition (OD-1)
B9.84 deterministic selection boundary
B9.85 acquisition service (application boundary)
B9.86 catalog query boundary
B9.87 CLI catalog query caller
B9.88 chat / application boundary CLI caller
B9.89 run through application boundary
B9.90 canonical revision-aware locator
B9.91 internal Dynamic Model Library (live, stateless)
B9.92 CLI discover -> inspect -> select -> acquire
```

The architecture already distinguishes these layers, and this record does not
collapse them:

```text
repository          ModelCandidate.repository   (discovery, L1, declared)
variant             ModelVariant                (discovery, provider-grouped)
artifact            DiscoveredArtifact          (discovery, L1, declared)
revision            revision: str | None        (L1 provenance, 40-hex, untrusted)
logical identity    model_id: str              (central, curated, resolved)
locator             downloadable_locator(...)  (one-or-none gate)
storage identity    <model_id>/<artifact_id>    (filesystem)
```

### Actual end-to-end flow (traced, not assumed)

```text
model_id (str)
  |
  |-- downloadable_locator(model_id)              [identity CONSUMED here]
  |      acquisition_service._resolve_repository:300
  |      wired at application_wiring.py:352
  |     -> (source, repository)
  |
  v
repository
  |
  v
ModelDiscovery.inspect(repository)                B9.80 / B9.81
  |   HuggingFaceDiscoveryProvider.inspect
  |   DiscoveredArtifact(model_id=None)           <- line 376, ALWAYS
  v
ModelVariant[]  (provider-owned grouping)
  v
select_discovered_artifact(...)                  B9.84
  |   exactly one artifact, or explicit failure
  v
map_discovered_artifacts(..., identity_resolver=...)
  |   B9.82 — identity RE-ATTACHED here
  |   _resolve_identity: identity_resolver(artifact.repository)
  |   None / unsafe -> AcquisitionMappingError (fail closed)
  v
ArtifactSpec(model_id, source, repository, filename, revision, ...)
  |
  v
DownloadPlanner.plan(spec)                       B9.90
  |   canonical locator derived from trusted fields
  |   NOT an identity authority; model_id untouched
  v
Downloader.download(plan)
  |   model_id used ONLY as a directory component (downloader.py:154)
  v
ModelStore.save_manifest(spec)
      _safe_model_id(artifact.model_id) -> directory name
```

Discovery, inspection, selection, planner, downloader and store do not invent
identity. The mapping boundary receives identity from an injected resolver.
Identity is validated twice in `ModelAcquisitionService._map` (lines 382 and
402): once against a provider-declared `model_id`, once against the mapped spec.

### Identity dependency shape

```text
ACQUISITION DEPENDS ON IDENTITY DIRECTLY AT EXACTLY TWO POINTS:
  1. the gate  (downloadable_locator) — may refuse
  2. the mapping boundary (injected resolver) — may refuse

INDIRECTLY AFTERWARDS:
  ArtifactSpec.model_id only reaches the filesystem through
  ModelStore._safe_model_id.

DOWNSTREAM CONSUMERS: application_wiring, acquisition_service,
  sources/huggingface.py, manifest_migration, api._model_dto, main

## Invariants

These are recorded as **current invariants**, each traced to code or to the
ratified register. This record preserves all of them under every option.

| # | Invariant | Evidence |
| --- | --- | --- |
| **I1** | **No silent inference.** An unknown identity is never inferred from basename, filename, fuzzy matching, implicit alias, heuristic, or repository guessing. | `model_identity.py:22-23,64-72`; register 1612, 1705 |
| **I2** | **Caller-owned identity resolution.** Resolution is caller policy. B9.82 requires a keyword-only `identity_resolver` with no default and never imports `model_identity`. Never fabricates `None` nor `"Unknown"`. | `acquisition_mapping.py:26-34`; register 2550-2553 |
| **I3** | **Discovery remains identity-free.** A repository absent from the registry must still be discoverable (AC7). | `discovery.py:84`; `huggingface_discovery.py:376`; register 2079, 4327 |
| **I4** | **Deterministic acquisition.** Ambiguity is a failure, never an arbitrary pick — in both selection and locator resolution. | `discovery_selection.py` D6; `downloadable_locator` `len != 1 -> None` |
| **I5** | **Identity is not revision, not artifact, not content.** `logical identity != revision != artifact != content`. | OD-1; `models.py:63-79`; register 19.7.2 |
| **I6** | **Planner and downloader are not identity authorities.** The planner derives the canonical locator from trusted fields, never from the incoming URL. | `planner._validate_metadata` (B9.90) |
| **I7** | **ModelStore never invents identity.** Local state is derived by inspection, never persisted as authority. | `model_store.py:16-23,223-240` |
| **I8** | **Contradictory provider identity is rejected, not re-resolved.** | `acquisition_service.py:382-387` |
| **I9** | **Identity safety is total.** Empty, absolute, dot-segmented or storage-unsafe identities are rejected. | `_is_safe_identity`; `_safe_model_id` |
| **I10** | **GUI / Model Library UX boundary remains separate.** `Application boundary != Model Library UX`. | register 25.5 (5014-5024); Product Vision ADR D6/D8 |

---

                       Currently unreachable: a contract test asserts every
                       catalog model has a non-None id and model_id != name.

3. Artifact addressing artifact_id = content_id
                       or sha256(source|repository|filename|quantization)
                       (models.py:81-93). Revision deliberately excluded.

4. Imported label      resolver.py:206,233-237
                       imported artifacts store a SANITIZED LABEL in
                       ArtifactSpec.model_id while ModelSpec.id stays None.
                       "The two are deliberately different things, and the
                        label is never copied into ModelSpec.id."
```

Flavour 4 is the decisive evidence that one field currently carries three
semantics (logical identity, provenance-derived address, storage label)
depending on how the artifact got into the store.

---
## Alternatives

### Option A — Expand the existing static identity registry

Keep `SOURCE_REPOSITORY_TO_MODEL_ID` as the concept; add rows, and add the
corresponding `ModelSpec` entries to `model_catalog.CATALOG`.

**Shape**

```text
identity stays a bare str
registry stays curated and hardcoded
discovery stays identity-free
no new domain type, no new boundary
```

**What it solves**

The 1-of-3 downloadability gap, and nothing else. It makes more logical
models acquirable under the exact existing semantics.

**What it does not solve**

Multi-mirror models (the `len == 1` rule survives). Provider generality (the
provider gate is duplicated in `planner`, outside identity). The four
coexisting identity flavours. Variant/artifact addressing. The `id or name`
fallback. Storage and manifest semantics.

**Scaling**

Linear and cheap in code, but the registry becomes a hardcoded product
allow-list: each addition is a source edit in two modules plus a test
fixture, because `test_model_identity.py` hardcodes `EXPECTED_CATALOG_IDS`
and asserts exact equality with the catalog tuple.

**Honest limits**

This is a **product-policy** lever wearing an architectural costume. If the
human's real intent is "CastleArq can acquire any GGUF", Option A answers a
different question and leaves the gate structure untouched.

### Option B — Generalize identity into an explicit domain contract

Introduce a first-class identity abstraction — a nominal `ModelId` type
and/or a domain module that owns identity semantics instead of exposing a
module-level dict.

**Architectural boundary created**

Between *identity as data* and *identity as a domain concept with rules*.
This would be the first component whose job is to answer "what is a logical
model identity" rather than "which repositories are mapped today".

**Reconciliation surface required**

```text
ModelSpec.model_id        (models.py:124 — the `id or name` fallback)
ArtifactSpec.model_id     (three flavours: logical / address / label)
ModelStore._safe_model_id (storage sanitisation)
acquisition_mapping._is_safe_identity (duplicated safety contract)
manifest_migration        (renames directories FROM this table)
api._model_dto            (projects downloadability as a public field)
application_wiring        (binds the resolvers today)
### Option C — Provider/discovery-declared identity

Allow the provider to populate `DiscoveredArtifact.model_id`, which already
exists as an optional field (`discovery.py:84`), and stop re-attaching
identity centrally.

**Feasibility against ratified decisions**

The field exists. Every guard around it currently forbids trusting it:

```text
acquisition_service.py:382-387   a declared model_id contradicting the
                                 request is REFUSED, not re-resolved
acquisition_service.py:39        "never imports model_identity ... never
                                  fabricates an identity"
discovery.py:77                  "One remote declared artifact (L1).
                                 Declared != verified."
register 4327                    "Identity remains outside discovery
                                  metadata; the Hugging Face discovery
                                  provider does not become the owner of
                                  logical model identity."
register AC7                     repository need not exist in
                                  model_identity.py to be DISCOVERABLE —
                                  a statement about discovery, not
                                  acquirability.
```

**Effect on provider responsibility**

The provider becomes the identity authority. Logical model identity would
then inherit provider repository naming, collapsing `logical model` into
`repository` — destroying exactly the distinction I5 and the module
docstring protect.

**Compatibility verdict**

```text
NOT COMPATIBLE with the current baseline.
It requires superseding at least B9.82 decision 1, B9.85 decision D3, and
the register's AC7/"identity stays out of L1 data" invariant.
It is therefore recorded as EVIDENCE-REJECTED under the current baseline,
NOT as a live choice. It is not reopened here.
```

If the human later wants this direction, it requires an explicit, named
supersession decision before any implementation — not a B9.93 detail.

### Option D — Explicit multi-layer identity model

Formally separate `logical model`, `variant`, `artifact`, `revision`,
`locator`, `storage identity` as named layers, with explicit ownership and
explicit non-identity of each.

**CastleArq already has these layers — in two disconnected stacks**

```text
DISCOVERY STACK (identity-free, provider-built)
  ModelCandidate(repository)
    -> ModelVariant(declared_quantization, artifacts)
       -> DiscoveredArtifact(filename, revision, url, size, sha256)

REPRESENTATION STACK (B8.1, consumed only by the evaluation stack)
  Model -> ModelIdentity(name, model_id?) -> ModelArtifact(
              identifier?, precision, quantization, format)

ACQUISITION STACK (identity-bound)
  model_id -> ArtifactSpec -> artifact_id
```

The current acquisition path collapses variant and artifact into a single
B9.84-selected unit, while the B8.1 stack models them explicitly but is not
on the acquisition path.

**Is the distinction architecturally necessary?**

For the **acquisition flow as it exists**: not strictly — B9.84's
select-one-and-fail behaviour is a coherent, ratified contract.

For a future **Model Library**: yes. "Select a logical model, inspect its
variants, acquire a chosen artifact" is not expressible today. The library
must express variant and artifact as selectable things, while the current
gate takes a whole `model_id` and demands exactly one artifact. That tension
is architectural, not cosmetic.

**Recorded explicitly as NOT part of this option**

Connecting B8.1's `Model`/`ModelArtifact` to the acquisition path would
reopen B8.0/B8.1. Option D is **layer declaration and ownership**, not a
merge of the two stacks.

## Comparison Matrix

Qualitative ratings. **No winner is declared and no column is weighted.**

| Dimension | Option A | Option B | Option C | Option D |
| --- | --- | --- | --- | --- |
| Compatibility with current architecture | HIGH | MEDIUM | LOW (evidence-rejected) | MEDIUM |
| Scope | LOW | HIGH | HIGH | HIGH |
| Boundary impact | LOW (identity, catalog, migration, API) | MEDIUM-HIGH (>= 7 modules) | HIGH (reopens 3+ ratified decisions) | MEDIUM-HIGH |
| Identity safety | HIGH (unchanged) | MEDIUM (must re-prove I9) | LOW (defeats the allow-list) | MEDIUM |
| Multi-model support | HIGH | HIGH | HIGH | HIGH |
| Multi-variant support | MEDIUM (discovery-side only) | MEDIUM | MEDIUM | HIGH |
| Revision separation | HIGH (OD-1 untouched) | MEDIUM (temptation to fold in) | MEDIUM | HIGH (explicit) |
| Provider independence | LOW (gate duplicated in planner) | MEDIUM | LOW (opposite of independence) | MEDIUM |
| Model Library readiness | LOW-MEDIUM (browse != acquire) | MEDIUM | LOW (but directly enabling) | HIGH |
| Legacy compatibility | HIGH | MEDIUM | LOW | MEDIUM |
| Acquisition impact | NONE | MEDIUM (safety-rule sharing) | HIGH (reopens B9.82/B9.85) | MEDIUM (must wrap, not penetrate) |
| ModelStore impact | NONE, except possible directory renames | MEDIUM (reconcile sanitised label) | MEDIUM (store inherits provider naming) | MEDIUM-HIGH (raises variant-in-storage question) |
| Migration complexity | LOW-MEDIUM | MEDIUM | HIGH | HIGH |
| Scope risk | LOW | MEDIUM | HIGH | HIGH |
| Reversibility | HIGH | MEDIUM | LOW | LOW-MEDIUM |
| Evidence maturity | HIGH (runtime-verified) | MEDIUM (duplication observed) | HIGH as a rejection, LOW as an option | MEDIUM (both stacks read) |

---

sources/huggingface.py    (legacy second consumer)
B8.1 ModelIdentity        (a fourth representation, see B8.1 section)
```

**Honest assessment of necessity**

The evidence for a *missing contract* is real: a duplicated safety contract
and three semantics in one field. The evidence that identity is the thing
*blocking* a second model is **absent** — Option A demonstrates the current
types already support N models. Option B is a structural improvement whose
necessity depends on the human's answer to Q1.

**Invariants it would touch**

I9 would need explicit supersession: `acquisition_mapping` may no longer
import `model_store`-equivalent logic, so the duplicated safety rules become
shared domain logic rather than two private copies. That is a change to a
ratified boundary's rationale, not a violation of I1-I10.

**Scope**

Largest of the four in affected-boundary count; smallest in conceptual
novelty.

---

EXPLICIT NON-CONSUMERS: discovery, huggingface_discovery,
  discovery_selection, dynamic_model_library (forbidden by test),
  acquisition_mapping (never imports model_identity),
  acquisition_service (never imports model_identity),
  catalog_query_service, model_store, planner, downloader
```

---

## Human Decision Questions — AS PUT, AND AS ANSWERED

These questions were put to the human without weighting, scoring or a
recommended answer attached. The answers below are the human's and are now
part of the ratified record.

### Q1 — Scope of the block

*As put:* Should B9.93 **only widen the set of supported models** under the
existing identity concept, or should it **redefine/generalise the concept of
identity**?

**ANSWER — GENERALISE THE CONCEPT.** B9.93 does not merely add rows. It
ratifies the layered identity concept (Option D). Adding catalog entries
remains possible later but is not what this block decides.

### Q2 — Authority of identity

*As put:* Which component is the authority?

```text
(a) static curated registry              -> Option A
(b) explicit domain contract             -> Option B
(c) provider / discovery                 -> Option C  (evidence-rejected today)
(d) multi-layer domain model             -> Option D
```

**ANSWER — (d) MULTI-LAYER DOMAIN MODEL.** Authority is not moved to a
provider, and it is not moved into a new nominal type in this block. The
authority question is answered by *layer ownership*: each layer has exactly
one owner, and no layer may act as another's identity.

### Q3 — Mapping cardinality

*As put:* May one repository resolve to more than one logical model — and
separately, may one logical model resolve to more than one locator (mirrors)?

Current evidence: the **type** already permits both; `downloadable_locator`
forbids them by returning `None`. Changing this would change three places:
`model_identity.downloadable_locator`, `main._download_status`, and
`acquisition_service._resolve_repository`.

**ANSWER — NO. `1 repository → 1 logical model` REMAINS THE CONSTRAINT OF
B9.93.** See the Cardinality Decision section.

### Q4 — B8.1 connection

*As put:* Should B8.1's `ModelIdentity` be connected to the identity used by
acquisition? Do not assume yes; the evidence is set out in the B8.1
Interaction section.

**ANSWER — NO. B8.1 `ModelIdentity` REMAINS PARALLEL AND NOT CONVERGED.**

### Q5 — Provider gate

*As put:* Should `SUPPORTED_DOWNLOAD_SOURCES = {"huggingface"}` — and its
duplicated equivalent inside `planner._validate_metadata` — remain the
provider gate, or is provider generality in scope for the identity decision?

**ANSWER — THE GATE REMAINS AS IT IS.** Provider federation is a non-goal of
B9.93. The duplication between the gate and the planner is recorded as
existing debt, not resolved here.

### Q6 — Product vs technical capability

*As put:* Does B9.93 authorise *capability* ("CastleArq can acquire any
curated GGUF logical model") or *curation* ("CastleArq declares which
logical models are officially downloadable")?

**ANSWER — NEITHER IS GRANTED BY THIS BLOCK.** B9.93 ratifies a conceptual
architecture. It authorises neither new downloadable models nor a new
curation policy. See the Product Consequence section.

---

## Ratified Architectural Contract — Explicit Multi-Layer Identity Model

This is the substance of the ratified decision. It is an **architectural
conceptual contract**, recorded here with precise semantics.

```text
Logical Model
    │
    ├── Variant
    │      │
    │      └── Artifact
    │              │
    │              └── Revision
    │
    ├── Locator
    │
    └── Storage Identity
```

**Binding reading of this diagram.** It is a statement of layered meaning and
layer ownership. It is **NOT** a requirement that every node immediately
become a new class, module, table, dataclass or persisted entity. Converting
any of these layers into new code structures is **not** authorised by this
decision and would require its own allocation.

### Semantic ownership of each layer

**Logical Model** — the stable logical identity of the model.

```text
Conceptual example: qwen2.5-coder-7b-instruct
Owner:             the curated identity authority (model_identity.py today)
It does NOT represent:
  filename, quantization, revision, repository, storage path,
  download URL, content digest
```

**Variant** — a selectable variant of the logical model. It may distinguish
format, quantization and variant metadata.

```text
Today:  ModelVariant in the discovery domain (provider-owned grouping)
It must NOT be confused with logical model identity. A variant is a
selection within a logical model, never an alternative name for it.
```

**Artifact** — the concrete selectable/acquirable artifact. It may carry
filename, size, sha256, revision and artifact metadata.

```text
Today:  DiscoveredArtifact (L1, declared) -> ArtifactSpec (acquisition)
An artifact NEVER redefines the logical identity of its model. The
identity it carries is a reference, not an assertion.
```

**Revision** — the declared revision of the artifact/repository state.

```text
It remains semantically separate from logical model identity, from
variant identity, from artifact identity and from content identity.
INVARIANT PRESERVED:  revision != identity
Today:  carried verbatim by B9.83; excluded from artifact_id by OD-1
```

**Locator** — the information required to ACQUIRE an artifact.

```text
A locator is NOT the identity of the model.
INVARIANT PRESERVED:  locator != logical model identity
Owner:  acquisition semantics — downloadable_locator (gate) and
        DownloadPlanner (canonical URL construction, B9.90)
```

**Storage Identity** — the identity used for local persistence.

```text
It remains conceptually SEPARATE from logical model identity, from
artifact identity, from revision and from locator.
Today:  <model_id>/<artifact_id>; ModelStore sanitises and derives it.
It is a persistence concern, not a model-identity claim.
```

### The rule that makes the layering meaningful

```text
No layer may be substituted for another.
No layer may be silently promoted to another.
A locator is not an identity. A revision is not an identity. A directory
name is not an identity. A filename is not an identity. A content digest is
not an identity. Provider-declared metadata is not an identity.
```

---

## Current Implementation vs. Target Contract

**Explicit declaration:**

> B9.93 ratifies the Option D conceptual model, but does **not** require an
> immediate transversal rewrite of the existing representations.

The implementation may therefore continue to use:

```text
model_id: str
```

as its operating mechanism while the architecture evolves.

`SOURCE_REPOSITORY_TO_MODEL_ID` **may continue to exist and continue to be
used.** This decision must **not** be read as an obligation to remove it. It
remains the current mechanism for resolving `(source, repository)` to a
logical identity, and `downloadable_locator` remains the current download
gate.

What changes conceptually is only that these mechanisms are now understood to
occupy a **named layer** — the Logical Model layer — rather than being
"identity" in general. The layering is the contract; the mechanism is an
implementation detail of the layer.

---

## Implementation Posture

```text
B9.93 IMPLEMENTATION POSTURE: INCREMENTAL / MINIMAL
```

This means:

```text
- preserve every already-ratified contract;
- introduce only the structures strictly necessary;
- avoid a mass migration;
- do NOT rewrite ModelStore;
- do NOT rewrite discovery;
- do NOT rewrite acquisition;
- do NOT converge B8.1 automatically;
- do NOT introduce provider federation.
```

Option D is an **architectural direction**, not permission for unrestricted
refactoring.

---

## Cardinality Decision

```text
1 repository → 1 logical model
```

**REMAINS THE CONSTRAINT OF B9.93.**

This decision does **NOT** enable:

```text
1 repository → N logical models
```

Recorded reasoning:

```text
1. It avoids reopening `downloadable_locator`, whose exactly-one rule is
   reproduced in two downstream locations (`main._download_status` and
   `acquisition_service._resolve_repository`).
2. It avoids modifying ambiguity semantics (B9.84 D6), which treat
   ambiguity as an explicit failure rather than a hint.
3. It avoids widening acquisition cardinality.
4. It avoids introducing complexity that no current requirement demands.
5. It preserves reversibility.
```

If a real need for multiple logical models per repository appears later, it
**requires a separate architectural decision.** It is not authorised here and
is not silently permitted by this record.


## Technical Recommendation — AS ALIGNED WITH THE RATIFIED DECISION

**The decision has been taken by the human: Option D.** This section is
retained as the technical rationale that supported the selection, and as the
statement of the implementation posture that accompanies it. It does not
select; it records what was selected and why.

```text
SELECTED ARCHITECTURE: Option D — Explicit Multi-Layer Identity Model
IMPLEMENTATION:        INCREMENTAL / MINIMAL
```

### Why Option D

1. **CastleArq already handles several of these layers implicitly.** The
   layers were found by tracing real code, not by inventing a taxonomy:
   `ModelCandidate`/`ModelVariant`/`DiscoveredArtifact` in discovery,
   `model_id`/`ArtifactSpec`/`artifact_id` in acquisition and storage, and
   `revision` and `downloadable_locator` at their own boundaries.
2. **B9.80–B9.92 already established the boundaries.** Repository, variant,
   artifact, revision, selection, locator and acquisition boundaries are
   closed and consumed as-is. Option D names and separates what those blocks
   already own; it does not re-open them.
3. **An explicit conceptual separation reduces future ambiguity.** The single
   most expensive observed fact in this audit is that `ArtifactSpec.model_id`
   currently carries three different semantics (logical identity,
   provenance-derived address, imported storage label). Declaring the layers
   makes that ambiguity visible and prevents it from spreading.
4. **It prepares the future Model Library without implementing it.** Variant
   and artifact become nameable, selectable things, which is precisely what a
   library needs — and precisely what B9.84's one-artifact-or-failure contract
   cannot yet express.
5. **It prevents locator, revision and storage identity from becoming
   pseudo-identities.** Each is now explicitly a non-identity. This is the
   safety value of the decision: it names the failure modes before they occur.
6. **It keeps discovery independent of identity.** Discovery remains
   identity-free, so the provider is not on the path to a model identity.
7. **It keeps provider identity out of discovery.** Option C stays rejected;
   provider-declared metadata remains untrusted declared data.
8. **It permits gradual evolution without a mass migration.** Because the
   contract is conceptual, the mechanism (`model_id: str`, the curated
   registry, the existing store layout) may remain exactly as it is while the
   architecture matures.

### Why the posture is INCREMENTAL / MINIMAL

Option D is an architectural direction, not permission for unrestricted
refactoring. Every one of I1–I10 survives the selection. `model_id: str`,
`SOURCE_REPOSITORY_TO_MODEL_ID`, `downloadable_locator`, `ModelStore`,
discovery and acquisition all remain untouched under this decision.

### Options NOT selected

```text
Option A — widening the registry remains POSSIBLE but is not what this block
            decides. It is compatible with the selected architecture and
            could be pursued under a separate decision.
Option B — a nominal identity type was not selected. It remains available
            and compatible with Option D, but is out of scope here.
Option C — REJECTED. It contradicts I1, I3 and I5 and would require
            superseding B9.82 decision 1, B9.85 decision D3 and the
            "identity stays out of L1 data" invariant. It is not reopened.
```

---

## Human Architectural Decision

```text
===============================================================
  SELECTED — OPTION D
  Explicit Multi-Layer Identity Model
===============================================================

Decided by:   PROJECT OWNER (human architectural decision)
Status:       SELECTED — not provisional, not recommended

SELECTED ARCHITECTURE:
  Option D — Explicit Multi-Layer Identity Model
  (Logical Model / Variant / Artifact / Revision / Locator /
   Storage Identity as explicitly separated layers)

IMPLEMENTATION POSTURE:
  INCREMENTAL / MINIMAL

Repository -> Logical Model cardinality:
  1 -> 1 for B9.93
  (1 repository -> N logical models is NOT enabled)

Discovery identity authority:
  NONE  (Discovery remains identity-free)

Provider-declared identity:
  NOT AUTHORITATIVE  (Option C rejected)

B8.1 ModelIdentity:
  PARALLEL / NOT CONVERGED

Roadmap state:
  B9.93: NOT ALLOCATED  (this decision allocates nothing)

---------------------------------------------------------------
Q1 Block scope:            GENERALISE THE CONCEPT
Q2 Identity authority:     MULTI-LAYER DOMAIN MODEL
Q3 Mapping cardinality:    1 repository -> 1 logical model REMAINS
Q4 B8.1 connection:        NO — PARALLEL / NOT CONVERGED
Q5 Provider gate:          UNCHANGED
Q6 Capability vs curation: NEITHER GRANTED BY THIS BLOCK

Supersessions required:    NONE
B8.0 / B8.1 reopened:      NO
Roadmap register modified: NO
Source / tests modified:   NO
Allocation created:        NO
---------------------------------------------------------------
```

## Consequences

### Option A

**Immediate.** More catalog models become downloadable. `models` output
changes for those entries. `api._model_dto` `downloadable` /
`download_source` / `download_repository` fields become populated where they
were previously null. Existing behavior for the Qwen entry is unchanged.

**Deferred.** The exactly-one-locator rule. The four identity flavours. The
duplicated safety contract. The `id or name` fallback. Variant/artifact
addressing.

**Leverage.** Model Library: browse-then-acquire becomes possible for
curated models. GUI: availability is already a clean boolean projection.
Provider expansion: none — still blocked by the duplicated provider gate.
Multi-variant / multi-artifact: none.

**Cost.** The curated allow-list deepens. Every new model is a code change
plus a hardcoded test fixture. The distinction between "capability" and
"curation" becomes harder to see over time.

### Option B

**Immediate.** A new identity-owning boundary. `ModelSpec.model_id`,
`ArtifactSpec.model_id`, `_safe_model_id`, `_is_safe_identity` and
`manifest_migration` become clients of it.

**Deferred.** Layer declaration (Option D's concern). Model Library
surface. Legacy convergence.

**Leverage.** One place to reconcile the three field semantics. A natural
home for source capability, which would let the provider gate stop being
duplicated. A stable typed concept for a GUI to bind to.

**Cost.** Broadest boundary count. Requires explicit supersession of the
rationale behind B9.82's safety duplication. Introduces a migration surface
(tests, doubles, the legacy `HuggingFaceSource` resolver) that a data-only
change does not need.

### Option C

**Immediate.** Nothing — it is not implementable under the baseline.

**Deferred.** Everything.

**Leverage.** Would make provider-declared identity the natural model for a
federated library.

**Cost.** Would collapse logical model into repository, contradict I1/I3/I5
and the registry docstring, and require superseding B9.82 decision 1, B9.85
decision D3 and the "identity stays out of L1 data" invariant.

### Option D — SELECTED

**Immediate.** Layer ownership becomes explicit and nameable. B9.84 and
B9.90 are documented as operating inside specific layers. Locator, revision
and storage identity are explicitly declared non-identities.

**Deferred.** Connecting the B8.1 and acquisition stacks. Any storage change.
Any new persisted entity. Model Library surface. Provider generality.

**Leverage.** "Select a logical model, inspect its variants, acquire a chosen
artifact" becomes conceptually expressible without a further identity
redesign. It is the option that most directly prepares a future GUI and a
future Model Library — without implementing either.

**Cost.** Highest conceptual and documentation surface, lowest reversibility
of the four (layer naming is hard to unwind once other blocks cite it). It
risks being recorded as a taxonomy that acquisition then routes around —
which is why the INCREMENTAL/MINIMAL posture is bound to it.

### Consequences of the selected decision, specifically

```text
1. "Identity" is no longer an undifferentiated word in CastleArq. It is
   Logical Model identity, or it is not identity.

2. Locator, revision, filename, directory name and content digest are
   formally NON-identities.

3. Nothing changes in code. model_id: str remains the mechanism.
   SOURCE_REPOSITORY_TO_MODEL_ID remains. downloadable_locator remains
   the gate. ModelStore is not redesigned. Discovery is not redesigned.
   Acquisition is not redesigned.

4. The layered contract creates a durable vocabulary for future blocks to
   cite, so that a future Model Library, provider block or storage block does
   not have to re-derive what identity means.

5. Cardinality stays 1 repository -> 1 logical model. The layers are a
   semantic contract, not a permission to widen any cardinality.
```

---

## Non-Goals

Under the ratified Option D decision, B9.93 does **not** decide or implement:

```text
GUI                                    (Product Vision ADR: NOT AUTHORIZED)
Model Library UI                       (register 25.5: NOT ALLOCATED,
                                        NOT AUTHORIZED)
persistent model catalog / database
provider federation
second provider implementation          (register 1705, 2388 item 21)
fuzzy search
semantic search
ranking
recommendation                         (register 17.3 items 14-16, 20 D6, 21.6)
download progress
resumable downloads
ModelStore redesign                    (register 19.3 item 12)
artifact storage redesign
filesystem layout redesign
manifest schema redesign
storage directory redesign
migrations
multi-revision coexistence             (register 19.7.3: no identifier allocated)
multi-GPU
fine-tuning
LoRA / QLoRA
datasets
evaluation infrastructure
legacy convergence / ModelSource retirement   (register 18.3, 19.3 item 2;
                                        "a separate block", unnamed)
CLI redesign
concrete model additions               (adding rows to the registry)
B8.0 / B8.1 record reopening
B8.1 ModelIdentity -> acquisition identity convergence
revision contract changes
new revision semantics
planner / downloader contract changes
provider-declared identity             (Option C stays rejected)
1 repository -> N logical models
B9.94 and any later identifier
```

---
## Dependencies

**Consumed as-is, unchanged, by any option:**

## Supersession / Compatibility

**No prior decision is superseded by this document.**

| Decision | Status after this record |
| --- | --- |
| B9.82 decision 1 (required injected resolver; never import `model_identity`) | UNCHANGED |
| B9.83 OD-1 (revision not in `artifact_id`) | UNCHANGED, immutable |
| B9.84 D5/D6 (no identity resolution; ambiguity is failure) | UNCHANGED |
| B9.85 D3 / D5 (identity-free service; legacy untouched) | UNCHANGED |
| B9.86 invariant 2 (identity outside discovery metadata) | UNCHANGED |
| B9.91 (stateless, composition-only, identity-free) | UNCHANGED |
| Register AC7 (repository need not be in `model_identity.py` to be discoverable) | UNCHANGED |
| Register 25.5 (application boundary != Model Library UX) | UNCHANGED |
| Register 18.3 / 19.3 item 2 (legacy `ModelSource` convergence) | UNCHANGED, unnamed block |
| Register 19.7.3 item 4 (multi-revision coexistence) | UNCHANGED, no identifier allocated |

**Conditional note, recorded not decided:** Option B would require an
explicit, named supersession of the *rationale* behind B9.82's duplicated
safety rules. Option C would require supersession of at least three ratified
decisions and is therefore recorded as evidence-rejected under this baseline.
Neither supersession is performed, prepared or implied here.

---

## Reversibility

| Option | Rating | Why |
| --- | --- | --- |
| **A** | **HIGH** | Data-only. Reverting = deleting rows and catalog entries. No manifest schema, no storage layout, no API contract shape changes. Residual risk: artifacts already downloaded under an added model remain in the store and become addressable only by the same `model_id` string; `manifest_migration` may have renamed directories to match the new mapping — reverting the mapping therefore does **not** automatically revert directory names. |
| **B** | **MEDIUM** | A new boundary is introduced rather than data changed. Reverting means removing a type from `ModelSpec`, `ArtifactSpec`, `ModelStore`, the API projection and the wiring — feasible because no persisted format depends on the *type*, but the mapping-table-driven directory renames are already persisted on disk and would not revert automatically. |
| **C** | **LOW** | Reverting changes discovery semantics, the B9.82 mapping contract and the B9.85 service. Provider-declared identities already written into manifests (`ArtifactSpec.model_id`) would persist and would have to be reinterpreted. |
| **D** | **LOW-MEDIUM** | Layer declarations become cited by other blocks' records; unwinding them is documentation- and expectation-heavy even when no behaviour changed. No persisted schema depends on it, which is what keeps this above LOW. |

**Cross-cutting reversibility facts, option-independent:**

```text
artifact_id  is unchanged by every option -> storage layout stable
revision     never participates in artifact_id (OD-1) -> stable
manifest schema is not modified by any option in this record
api._model_dto gains populated fields under Option A (observable but additive)
manifest_migration is the ONLY component whose on-disk effect is driven by the
  identity table, and directory renames are the least reversible consequence
  of ANY change to that table
```

---


## B8.1 Interaction

### Verified classification

`model_domain.ModelIdentity` and `ModelArtifact.identifier` are **PARALLEL —
ACTIVE IN A DIFFERENT STACK, NOT AN IDENTITY AUTHORITY FOR ACQUIRING**.

Evidence, itemised:

```text
ModelIdentity
  defined        model_domain.py:65-80
                 name mandatory and non-empty; model_id / version / variant
                 all OPTIONAL (may be None). Nothing is invented from
                 missing values.

Consumers       evaluation_adapter.py:111   ModelIdentity(name=spec.name,
                                                 model_id=spec.id)
                 compatibility_evaluator.py (evaluates identity)
                 NOT imported by model_identity, acquisition_mapping,
                 acquisition_service, discovery, huggingface_discovery,
                 planner, downloader, model_store or resolver.

Status          PARALLEL. It is a B8.1 *representation* type for the
                 evaluation/compatibility stack. It is NOT consulted by the
                 acquisition identity contract.

ModelArtifact.identifier
  defined        model_domain.py:227  identifier: str | None = None
                 docstring: "One concrete, storable/distributable variant of
                 a model (B8.0 §2)."

Recorded state  docs/B9.46-real-runtime-e2e-validation.md recorded
                 IDENTITY-DECISION = BLOCKED and "no hay semántica ratificada
                 para ModelArtifact.identifier" (lines 315-319), with
                 IDENTITY-CONTRACT-DECISION = A proposing that to_artifact
                 preserve spec.model_id as ModelArtifact.identifier
                 (lines 457-460).

CURRENT REALITY The code has MOVED SINCE that blocked record:
                 evaluation_adapter.py:133  identifier=_explicit(spec.model_id)
                 and compatibility_evaluator.py:197-228 _check_identity
                 COMPARES identifier against identity.model_id, yielding
                 PASSED / FAILED / UNKNOWN.

  => identifier is therefore ACTIVE as an EVALUATION CHECK, and its
     semantics are settled enough to be compared. It remains NOT an
     identity AUTHORITY: it never resolves, assigns or derives identity;
     it only evaluates a match.

DOC/CODE DRIFT  evaluation_adapter.py:29 still states "ModelArtifact.
                 identifier is always None (N-1)" while line 133 now sets
                 it from spec.model_id. This drift is OBSERVED and RECORDED
                 here; it is NOT fixed by this document, which makes no code
                 change. It should be resolved by whichever block owns
                 adapter documentation, not silently absorbed by B9.93.
```

### Consequences for Q4

Adopting B8.1's `ModelIdentity` as the acquisition identity type would mean:

```text
- giving up the "name is mandatory" rule (identity would inherit a display
  name requirement that model_identity.py explicitly refuses to infer from)
- accepting a type whose model_id is OPTIONAL, against I1's fail-closed rule
- connecting two stacks that today answer different questions
- reopening B8.0/B8.1 records
```

Connecting them is therefore **not** the low-cost move it may appear to be.
Q4 is a genuine architectural question, and this record does not assume its
answer.

---

## Legacy Interaction

Verified: **identity resolution is currently shared by more than one
architecture.** This is the fact that makes any identity change wider than it
looks.

```text
NEW stack
  application_wiring.compose_acquisition_service
    -> identity_resolver = lambda repository:
         logical_model_id("huggingface", repository)
    -> locator_resolver  = downloadable_locator
    -> locator_audit     = source_repositories_for_logical_model
  B9.85 service forwards the bound callable unchanged.

LEGACY stack
  sources/huggingface.py:_default_model_id -> logical_model_id(...)
  HuggingFaceSource.discover_artifacts -> SourceError when model_id is None.
  Still imported by the CLI and still exercised by legacy tests
  (test_huggingface.py: test_default_mapping_assigns_logical_model_id).

MANIFEST MIGRATION
  manifest_migration.py:129  logical_model_id(source, repository)
  Renames on-disk model directories toward the expected layout.
  An unmapped (source, repository) records MigrationAction.UNMAPPED.
  THIS IS THE COMPONENT WITH PERSISTENT ON-DISK EFFECTS.

run
  main.py:1512 run_plan resolves model_id = logical_model_id(...)
  run_download delegates to ModelAcquisitionService via
  compose_acquisition_service.
```

**Recorded scope limit:** this document analyses the legacy interaction
because any identity change reaches it. It does **not** propose, evaluate or
advance legacy convergence. Register 18.3 / 19.3 item 2 keep `ModelSource`
deprecation, removal and migration as a separate, unnamed block; B9.85
decision D5 keeps `ModelSource`, `HuggingFaceSource`,
`artifact_selection.select_artifact` and `resolver.py` untouched; register
25.5 preserves that separation explicitly. **This HADR does not become a
legacy convergence block.**

---

```text
B9.80  discovery domain          identity stays out of L1 data
B9.81  HF discovery provider     emits model_id=None by contract
B9.82  discovery->acquisition    caller-supplied IdentityResolver
B9.83  revision-aware            OD-1 immutable
B9.84  selection                 sole deterministic selection authority
B9.85  acquisition service       D3 identity-free, D5 legacy untouched
B9.86  catalog query boundary    no identity resolution
B9.90  canonical locator         sole locator authority
B9.91  dynamic model library     stateless, composition-only, identity-free
B9.92  CLI discover->acquire     identity-free inspection
```

**Upstream facts the decision depends on:**

```text
model_identity.py          the authority under question
model_catalog.CATALOG      the 3 ModelSpec entries
models.ArtifactSpec        identity field + artifact_id derivation
model_store                storage projection of identity
manifest_migration         directory renames keyed on the identity table
application_wiring         the composition root that binds the resolvers
api._model_dto             public projection of downloadability
```

---

**Scope of the ratified decision, as authorized and not authorized:**

```text
AUTHORIZED:
  - Recording Option D as the selected architectural direction.
  - Recording the explicit layer semantics and their ownership.
  - Recording the invariants that bound the decision.
  - Recording the INCREMENTAL / MINIMAL implementation posture.

NOT AUTHORIZED:
  - Any allocation of B9.93.
  - Any source, test or configuration change.
  - Any modification of the roadmap register.
  - Any change to ModelStore, discovery, acquisition or planner/downloader.
  - Any widening of cardinality.
  - Any B8.0 / B8.1 convergence.
  - Any provider-declared identity.

Required invariants:    I1 - I10, all preserved (see Invariants section)
Ratified supersessions: NONE
B8.0 / B8.1 reopened:   NO
```

---

Should `SUPPORTED_DOWNLOAD_SOURCES = {"huggingface"}` — and its duplicated
equivalent inside `planner._validate_metadata` — remain the provider gate, or
is provider generality in scope for the identity decision?

### Q6 — Product vs technical capability

Does B9.93 authorise *capability* ("CastleArq can acquire any curated GGUF
logical model") or *curation* ("CastleArq declares which logical models are
officially downloadable")? See the Product Question section.

---

**Complexity and reversibility**

Highest complexity of the four; lowest reversibility, because naming layers
tends to be ratified into boundaries and later unwound is expensive even when
no behaviour changed.

---

## ModelStore Interaction

Verified storage model — **not modified by this record**:

```text
Layout:    <root>/<safe_model_id(model_id)>/<artifact_id>/manifest.json
  model_store.py:245  _open_directory(root_fd, _safe_model_id(spec.model_id))
  model_store.py:416  same projection on the read path
  model_store.py:492  manifest key "model_id" read back
  model_store.py:300  manifest writes "model_id": artifact.model_id

Sanitisation  _safe_model_id: reject empty/absolute/dot-segments;
              "/" -> "__", backslash -> "__", [^A-Za-z0-9._-]+ -> "_"
  => two distinct model_ids CANNOT silently collide by ordinary means, but
     the sanitisation is lossy in principle and is not proven injective.

artifact_id  models.py:81-93
  content_id if present, else sha256(source|repository|filename|quantization)
  revision deliberately excluded (OD-1)
```

**Does changing identity cardinality affect existing directories, manifests
or migrations?** Precisely:

| Change | Existing directories | Existing manifests | Migration |
| --- | --- | --- | --- |
| Add a row for a NEW repository (Option A) | unaffected | unaffected | `manifest_migration` may rename existing legacy directories toward the new mapping — the one persistent side effect |
| Change `SUPPORTED_DOWNLOAD_SOURCES` (Q5) | unaffected | unaffected | none |
| Relax `len(locators) == 1` (Q3) | unaffected | unaffected | none; only the resolution gate changes |
| Make identity a nominal type (Option B) | unaffected (same strings) | unaffected (same manifest schema) | none, but every caller and test double must be updated |
| Provider-declared identity (Option C) | at risk | at risk — `model_id` would take provider values | would need re-derivation for existing stores |
| Add layers (Option D) | unaffected unless a layer enters the path | unaffected | none |

**The honest statement:** no option in this record requires a ModelStore
redesign, and `artifact_id` is unchanged by every one of them. The single
genuinely persistent consequence is `manifest_migration`'s directory-rename
behaviour, which is driven by the identity table and is therefore triggered by
adding rows. ModelStore is **not modified**.

---

## Product Question

The distinction the human must hold while answering Q1 and Q6:

```text
TECHNICAL CAPABILITY
  "CastleArq's acquisition machinery can acquire a GGUF artifact for any
   logical model whose (source, repository) pair is mapped."
  This is TRUE TODAY for exactly one model, and becomes true for N the
  moment N rows exist. It is a property of the code.

PRODUCT POLICY
  "CastleArq declares which logical models are OFFICIALLY DOWNLOADABLE."
  This is decided by the CONTENT OF THE TABLE, which is a product
  judgement about what CastleArq stands behind: metadata quality,
  compatibility-engine coverage, revision handling, storage and naming.

CURRENT STATE: the registry FUNCTIONS AS BOTH. model_identity.py is a
mechanism, but `downloadable_locator` is also the sole source of the
user-visible availability string in `castlearq models` and the sole source of
`downloadable` in the HTTP DTO.
```

Consequence for this record: **"add models" and "expand identity" are not the
same block.** Option A is a curation action wearing the name of an
architectural expansion. If the human intends curation, Q6 should say so
explicitly, so that a later reader does not infer that a deeper identity
question was settled.

---

## Decision Readiness

```text
Is the current identity contract fully understood?        YES
  Traced from source and confirmed at runtime: 1 row, 1 source,
  len==1 gate, bare-str representation, four identity flavours.

Are the four alternatives genuinely distinct?             YES
  They differ in WHO OWNS IDENTITY, not in degree:
  table / domain / provider / layered.

Are their consequences understood?                        YES
  Across Model Library, GUI, provider expansion, multi-variant,
  multi-artifact, acquisition, storage, legacy and API.

Unresolved facts that materially prevent a decision?       NONE
Is additional repository research required?                NO
```

**Decision status: DECIDED.** The human selected Option D. The remaining
unknowns recorded in this document are all consequences deliberately deferred
under the INCREMENTAL/MINIMAL posture, not gaps in the decision.

---

## Decision Relationships — Ratified

These relationships are part of the ratified Option D contract.

### Discovery Authority

```text
INVARIANT: Discovery remains identity-free.
The provider/discovery layer does NOT become an authority of logical model
identity.
Current behaviour preserved: DiscoveredArtifact.model_id = None
This behaviour is NOT modified by B9.93. Any change to it requires an
explicit future decision that supersedes this architecture.
```

### Provider Identity

```text
Provider-declared identity is NOT AUTHORITATIVE.
Option C remains REJECTED within this decision.
The following are NOT reopened:
  - B9.82 identity mapping decision
  - B9.85 provider identity safety
  - acquisition mapping authority
A provider may DECLARE metadata; declared metadata never becomes identity.
```

### B8.1 Relationship

```text
B8.1 ModelIdentity remains PARALLEL.
It is NOT decided here that B8.1 ModelIdentity becomes CastleArq's
acquisition identity.
NOT modified: model_domain.py, evaluation_adapter.py,
              ModelArtifact.identifier
Any future convergence is a SEPARATE decision.
```

### ModelStore Relationship

```text
ModelStore storage identity remains a PERSISTENCE concern.
NOT redesigned: filesystem layout, manifest schema, artifact_id,
                migrations, storage directories.
B9.93 establishes ONLY that storage identity must not be conceptually
treated as automatically equivalent to logical model identity.
```

### Acquisition Relationship

```text
Locator belongs to ACQUISITION semantics.

  logical model identity  !=  locator

The planner remains the authority for canonical URL construction (B9.90).
The downloader remains defensive.
Neither contract is modified by this decision.
```

### Revision Relationship

```text
INVARIANT PRESERVED:  revision != identity
The revision contract is NOT changed.
No new revision semantics are introduced.
No multi-revision storage is introduced.
This decision consolidates conceptually the boundary already established
by B9.83/B9.90; it does not extend it.
```

### Product Consequence

This architecture permits a future Model Library to conceptualise:

```text
Search Model
     ↓
Logical Model
     ↓
Variants
     ↓
Artifacts
     ↓
Revision
     ↓
Acquire selected artifact
```

But, explicitly:

```text
Model Library GUI is NOT part of B9.93.
Persistent catalog is NOT authorised.
Database is NOT authorised.
Ranking is NOT authorised.
Semantic search is NOT authorised.
```

---

## Ratified State — Final

```text
Human Architectural Decision:      SELECTED — OPTION D
                                   Explicit Multi-Layer Identity Model
Implementation posture:            INCREMENTAL / MINIMAL
Repository -> Logical Model:       1 -> 1 for B9.93
Discovery identity authority:      NONE
Provider-declared identity:        NOT AUTHORITATIVE
B8.1 ModelIdentity:                PARALLEL / NOT CONVERGED
Supersessions required:            NONE
Roadmap state:                     B9.93: NOT ALLOCATED
Code / tests / roadmap changed:    NONE
```

---

## Final Gate

```text
B9.93 HUMAN ARCHITECTURAL DECISION: OPTION D RATIFIED
```


