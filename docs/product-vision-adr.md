# CastleArq — Product Vision ADR

> **Nature of this document: FORMAL PRODUCT VISION RECORD.**
>
> This document is **not** a historical block document and **carries no `B9.x`
> identifier**. It does **not** allocate a block number, does not create a
> roadmap allocation, and does not create a NAR.
>
> **`B9.87` is NOT allocated by this document.** `B9.87` remains
> `NOT ALLOCATED`, exactly as recorded in
> `docs/roadmap-register-and-numbering-policy.md` §26.12 and §23.5. This ADR
> places no claim on it and no claim on any other number.
>
> It is an **additional record**. It rewrites nothing: no historical document
> is modified, no source code, test, configuration, tag or release is touched.
> That constraint follows the project's established precedent —
> `docs/B9.59` §6 ("Historical documents are not rewritten; supersession is
> stated here instead") and `docs/release/v0.4.0-manifest.md` §9.

---

## 1. Status and ratification

The decisions recorded in §3–§14 (D1–D12) are **human-ratified product and
architectural decisions**. They were decided by the project owner and are
recorded here verbatim in substance.

Ratification means: **decided, and binding on future work.** It does **not**
mean: implemented, scheduled, allocated or externally validated. Those are four
different statuses and this document keeps them apart.

```text
D1-D12 RATIFICATION:           HUMAN-RATIFIED
D1-D12 IMPLEMENTATION STATUS:  NOT CLAIMED (see section 2)
D1-D12 ALLOCATION STATUS:      NO BLOCK ALLOCATED
D1-D12 EXTERNAL VALIDATION:    NOT VALIDATED (see section 14, D12)
```

---

## 2. Four statuses that must never be conflated

Every statement in this ADR belongs to exactly one of the following
categories. A reader must not promote a statement from one category to
another.

```text
CURRENT IMPLEMENTATION
    Capability that demonstrably exists in the repository today.

ARCHITECTURAL DIRECTION
    A ratified design direction that constrains future work but is not
    implemented capability. Architectural direction may shape boundaries.
    It may never be cited as evidence of current behaviour.

FUTURE PRODUCT SURFACE
    A ratified product idea with no implementation, no allocation and no
    authorization to implement.

UNVALIDATED PRODUCT HYPOTHESIS
    A belief about value, demand or product-market fit for which no
    external evidence exists.
```

The single most important consequence: **architectural direction is not
capability.** Runtime abstraction is architectural direction (§7, D5); the
existence of additional runtime implementations is future work and must not be
represented as currently implemented capability.

---

## 3. D1 — Product problem

CastleArq seeks to reduce the learning curve and operational complexity of using
local AI on Linux by helping users discover, select, acquire, verify, configure,
and operate models appropriate for their hardware and environment while
retaining technical transparency and control.

The original motivation was the practical difficulty of determining the
appropriate model, quantization, runtime, backend, and configuration for a
concrete Linux system.

## 4. D2 — Primary users

Primary users:

1. Students.
2. Professionals/developers.
3. Technical AI/local-AI enthusiasts.

Secondary audience: users with limited terminal/Linux experience who want to
use local AI.

The GUI is intended to reduce the learning barrier for these users without
changing the technical core into a beginner-only product.

## 5. D3 — Job To Be Done

> When I want to use a local AI model on Linux, I want CastleArq to help me
> find, choose, obtain, verify, and execute an appropriate combination of model,
> artifact, and runtime for my system without requiring me to manually solve the
> entire technical complexity myself.

This does **NOT** currently commit CastleArq to: training; distributed
execution; clusters; universal hardware support; any specific runtime as a
permanent requirement.

## 6. D4 — Product thesis

CastleArq is a local-AI operation platform that can use multiple existing
runtimes and infrastructure components while providing a higher-level layer for
discovering, selecting, acquiring, verifying, and operating models in the
context of the user's system.

Ollama, llama.cpp, and future runtimes are therefore **not** inherently required
to be treated as direct competitors. They may serve as runtime/infrastructure
components integrated beneath CastleArq.

The thesis is broader than being only a developer library and broader than
being another standalone chat application.

## 7. D5 — CastleArq core

The core product/architecture consists of the following conceptual chain:

```text
hardware observation
  -> runtime capability observation
  -> model discovery
  -> artifact identity
  -> artifact selection
  -> acquisition
  -> compatibility
  -> evaluation
  -> admission
  -> execution
```

Runtime abstraction is part of the core architectural direction even though
only one production runtime implementation currently exists.

**STATUS:** the chain above is architectural direction. The existence of
additional runtime implementations is **future work** and must not be
represented as currently implemented capability.

## 8. D6 — Model Library

Model Library is a **future product surface** exposing CastleArq's model
discovery, artifact selection, compatibility, and acquisition knowledge.

It must not be reduced conceptually to a generic model search interface.

The intended value is that a user can search for a model and inspect relevant
variants, such as quantizations, while CastleArq can provide contextual
information about suitability for the user's environment.

Example conceptual behavior:

* identify available model/artifact variants;
* expose relevant quantizations;
* evaluate compatibility against the user's environment;
* communicate limitations or uncertainty;
* eventually allow acquisition of an appropriate artifact.

**Model Library UX remains unallocated and is NOT authorized for
implementation by this ADR.** See §15.

## 9. D7 — Chat

Chat is a **product surface**. The initial intended role is straightforward
local-model conversation:

```text
user selects/uses a model
  -> CastleArq starts the appropriate runtime
  -> user chats with the local model
```

Future evolution may allow Chat to expose CastleArq's operational context, such
as explaining compatibility or configuration issues. **That future behavior is
not being implemented or fully specified by this ADR.**

When future Chat work is undertaken, conversation/session lifecycle should be
moved toward an appropriate application-level boundary rather than permanently
remaining as application lifecycle logic inside the HTTP transport layer.

No Conversation ADR is invented or reconstructed here: none currently exists in
the repository.

## 10. D8 — GUI

GUI is accepted as a **future product surface**. Its purpose is to reduce the
learning curve for users who are unfamiliar with terminal-oriented workflows and
to expose CastleArq capabilities through a graphical interface.

The GUI must consume CastleArq's application/core capabilities rather than
developing an independent business-logic implementation.

**GUI is NOT authorized for implementation by this ADR.** See §15.

## 11. D9 — Fine-tuning

Fine-tuning remains **outside the current CastleArq core** and requires a
separate architectural/product ADR before implementation.

The conceptual fine-tuning value chain is materially different:

```text
base model
  -> dataset
  -> training configuration
  -> training job
  -> checkpoint/adapter
  -> evaluation
  -> resulting artifact
  -> deployment/runtime use
```

**No fine-tuning implementation is authorized by this ADR.** See §15.

## 12. D10 — Product-surface boundary

CastleArq should maintain a shared core/application capability model with
multiple possible user-facing surfaces: **CLI; API; GUI.**

Chat, Model Library, diagnostics, and other future capabilities are product
experiences that should **consume the same underlying CastleArq capabilities**
rather than independently reproducing domain/application logic.

```text
CastleArq Core
  -> CLI
  -> API
  -> GUI
  -> future product experiences
```

## 13. D11 — Scope-control rule

No new user-facing surface should become an implementation priority while a
previously allocated core capability lacks a real caller or integration, unless
an explicit human decision justifies the exception.

This rule is intended to prevent uncontrolled expansion into GUI, Chat,
marketplace, agents, RAG, fine-tuning, or other surfaces before the core
provides sufficient value.

This is a **roadmap guardrail, not an implementation task.** Recording it here
creates no allocation and changes no roadmap state.

## 14. D12 — Product-validation status

The CastleArq product thesis is considered a **hypothesis** supported by:

* direct first-person experience with local AI setup complexity;
* the technical architecture already developed;
* the coherence of the proposed product chain.

However, the thesis is **NOT considered externally validated**. There is
currently insufficient evidence to claim broad market demand, strong adoption,
or product-market fit.

Future external user feedback, usage, issues, experiments, or other evidence
may validate or falsify the thesis.

---

## 15. Explicit non-authorizations

The following are **NOT authorized for implementation by this ADR**:

```text
GUI:                  NOT AUTHORIZED
Model Library UX:    NOT ALLOCATED, NOT AUTHORIZED
Chat:                PRODUCT SURFACE ONLY; NO IMPLEMENTATION AUTHORIZED
                      (no Conversation ADR exists or is reconstructed here)
Additional runtimes: FUTURE WORK; NOT IMPLEMENTED CAPABILITY
Fine-tuning:         OUT OF SCOPE; REQUIRES A SEPARATE ADR
B9.87:               NOT ALLOCATED
```

Additionally **NOT performed and NOT authorized by this document**:

* production source code changes;
* test changes;
* CLI/API behaviour changes;
* architecture implementation changes;
* dependency introduction;
* roadmap allocation records;
* NAR (Number Allocation Record);
* fine-tuning scope modification.

---

## 16. Status

```text
PRODUCT VISION ADR: RECORDED
DECISIONS D1-D12:    HUMAN-RATIFIED
IMPLEMENTATION:      NONE PERFORMED
BLOCK ALLOCATION:    NONE (B9.87 NOT ALLOCATED)
EXTERNAL VALIDATION: NOT VALIDATED
```

This document is the authoritative record of the CastleArq product vision as
decided. It does not rewrite, supersede or reinterpret any historical `docs/`
record; those records continue to describe current implementation, and where a
historical record and this vision differ, this vision describes intent and the
historical record describes observed reality.