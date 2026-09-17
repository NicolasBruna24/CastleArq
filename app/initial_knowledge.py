# Copyright 2026 Nicolas Bruna
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""B9.6.1: initial compatibility knowledge dataset -- DECLARATIVE DATA ONLY.

This module is the first real content of the compatibility knowledge base
specified by B9.6.0, built exclusively with the immutable B9.5 structures. It
contains no logic: no functions, no classes, no conditionals, no I/O, no
network, no clock, no system probe, no subprocess and no evaluation (B9.6.0
§23). It only builds constant values plus one ready-to-query registry.

How to read this data (B9.5 semantics, unchanged):

- Scopes match EXACTLY. An omitted scope is a record with an empty scope: it is
  not a wildcard and it is not proof of universal applicability. A platform- or
  version-scoped row is deliberately NOT reachable from an empty-scope query,
  and scope overlap/priority resolution is later work (B9.5).
- The world is open: a query without a matching row returns UNKNOWN, and
  absence is never UNSUPPORTED (§8). Rows stored with state UNKNOWN are
  explicit, non-binding records of "source consulted, no traceable statement
  found"; B9.5 ignores UNKNOWN when deriving a state, so a future supported or
  unsupported row for the same relation/scope is not a conflict.
- Every row carries provenance. Provenance is descriptive metadata: it is not
  truth, confidence, ranking or trust, and the hierarchical level of the source
  is only described in `source_type` text, never scored (§9, §10). References
  are inert documentation strings: CastleArq never opens, downloads, resolves
  or executes them (§23).

Dataset boundary (B9.6.0 §2-§7, §24): runtimes llama.cpp and Ollama only;
format GGUF only; backends CPU, Vulkan, CUDA, ROCm, HIP and SYCL; five
capabilities (text_generation, code_generation, vision, embeddings, tool_use);
platforms Linux, Windows and macOS. Distinct entities are never collapsed
(§4): ROCm != HIP != AMD GPU, SYCL != Level Zero != Intel GPU,
CUDA != NVIDIA GPU, Vulkan != "Vulkan-capable GPU". No transitive reasoning
(§17), no inference from vendor, product name or format (§18), no statement
about the user's hardware (§13): the Intel Arc B-Series verified-device tables
in the upstream SYCL documentation are intentionally NOT encoded here, both
because B9.5 has no hardware kind and because local hardware belongs to
Observation + Compatibility Evaluation (B9.4 §3).

Adjustments made while verifying the §19 candidate list (allowed by §19/§28.1):

- "SYCL on Windows -> UNKNOWN" is withdrawn: the upstream SYCL documentation
  has an explicit Windows section whose release table is "verified and
  recommended" for Windows 11, so llama.cpp + SYCL now has explicit platform
  evidence instead of a gap.
- "tool_use -> UNKNOWN" is withdrawn: both runtimes state tool/function calling
  support explicitly, so it is recorded as SUPPORTED for each of them
  separately, with its own source.
- "Ollama -> architecture UNKNOWN" and "architecture with undocumented support
  -> UNKNOWN" are kept.
- The mandatory runtime/backend UNKNOWN (§4) is kept in three places:
  llama.cpp + ROCm, Ollama + CUDA and Ollama + SYCL.
- `llama.app` (§3, §28.3): no official ggml-org source was found that presents
  it as a runtime, product or distribution, so it is registered as candidate
  alias metadata on the llama.cpp subject only. No assertion targets it, and
  B9.5 never resolves aliases in lookups (alias resolution stays explicit
  normalization, not a dedicated entry).

Coverage note (§21): the expected relation shape "runtime+backend ->
architecture/capability" is NOT present, because no consulted primary source
pairs a backend with an architecture or a capability for either runtime. Per
§11 and §19 nothing is invented to fill that shape; the gap is recorded in
COVERAGE_GAPS for a later iteration.

Size: 37 rows when written (32 SUPPORTED, 5 UNKNOWN, 0 UNSUPPORTED), inside the
~20-40 range of §20. Every row is meant to be reviewable on its own: the
comment above each constant quotes or faithfully paraphrases the exact source
sentence and location it rests on.
"""

from __future__ import annotations

from .compatibility_knowledge import (
    KnowledgeAssertion,
    KnowledgeKind,
    KnowledgePredicate,
    KnowledgeProvenance,
    KnowledgeRegistry,
    KnowledgeScope,
    KnowledgeState,
    KnowledgeSubject,
)

# Review date of the source texts quoted below (declarative string, B9.5 §9).
OBSERVED_AT: str = "2026-09-17"
# ---------------------------------------------------------------------------
# Canonical entities (B9.6.0 §3-§6, §12; B9.5 §27.5)
# ---------------------------------------------------------------------------
# Display names and aliases are metadata for humans: B9.5 lookups compare
# (kind, canonical_id) only, so aliases can never resolve a query implicitly.

LLAMACPP: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.RUNTIME,
    canonical_id="llama.cpp",
    display_name="llama.cpp",
    # §28.3 decision: "llama.app" stays candidate alias metadata (no official
    # source presents it as a runtime), and it is never used as a lookup key.
    aliases=("llamacpp", "llama.app"),
)

OLLAMA: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.RUNTIME,
    canonical_id="ollama",
    display_name="Ollama",
)

BACKEND_CPU: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="cpu", display_name="CPU",
)
BACKEND_VULKAN: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="vulkan", display_name="Vulkan",
)
BACKEND_CUDA: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="cuda", display_name="CUDA",
)
# §4: ROCm (platform/driver stack) and HIP (transport API) are separate
# entities and are never substituted for one another.
BACKEND_ROCM: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="rocm", display_name="ROCm",
)
BACKEND_HIP: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="hip", display_name="HIP",
)
BACKEND_SYCL: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.BACKEND, canonical_id="sycl", display_name="SYCL",
)

FORMAT_GGUF: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.FORMAT, canonical_id="gguf", display_name="GGUF",
)

# Architecture identifiers come from the project's own architecture registry
# (GGUF `general.architecture` values). They are NOT derived from model names
# (§18 rule 2). Only two identifiers are declared (§6 case 1, maximum 2).
ARCHITECTURE_LLAMA: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.ARCHITECTURE, canonical_id="llama",
)
ARCHITECTURE_QWEN3: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.ARCHITECTURE, canonical_id="qwen3",
)

# Capability identifiers reuse the B8.1 taxonomy names (B9.6.0 §7).
CAPABILITY_TEXT_GENERATION: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.CAPABILITY, canonical_id="text_generation",
)
CAPABILITY_CODE_GENERATION: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.CAPABILITY, canonical_id="code_generation",
)
CAPABILITY_VISION: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.CAPABILITY, canonical_id="vision",
)
CAPABILITY_EMBEDDINGS: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.CAPABILITY, canonical_id="embeddings",
)
CAPABILITY_TOOL_USE: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.CAPABILITY, canonical_id="tool_use",
)

# §12 platforms, with canonical lowercase identifiers and source spellings as
# display names.
PLATFORM_LINUX: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.PLATFORM, canonical_id="linux", display_name="Linux",
)
PLATFORM_WINDOWS: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.PLATFORM, canonical_id="windows", display_name="Windows",
)
PLATFORM_MACOS: KnowledgeSubject = KnowledgeSubject(
    kind=KnowledgeKind.PLATFORM, canonical_id="macos", display_name="macOS",
)

# ---------------------------------------------------------------------------
# Scopes (B9.6.0 §11, §12; B9.5: exact matching, no wildcards)
# ---------------------------------------------------------------------------
# Global rows simply omit `scope` (B9.5 default: empty scope = unqualified
# record). `variant` and `backend_id` are intentionally unused: no consulted
# source names a runtime variant distinct from version/platform, and backends
# are modeled as entity objects (B9.6.0 §25), not as scope fields.

SCOPE_PLATFORM_LINUX: KnowledgeScope = KnowledgeScope(platform="linux")
SCOPE_PLATFORM_WINDOWS: KnowledgeScope = KnowledgeScope(platform="windows")
SCOPE_PLATFORM_MACOS: KnowledgeScope = KnowledgeScope(platform="macos")

# Version scope as declarative data (B9.5 §17: no semver, no range matching).
SCOPE_LLAMACPP_B5377: KnowledgeScope = KnowledgeScope(runtime_version="b5377")

# ---------------------------------------------------------------------------
# Provenance records (B9.6.0 §9, §10; B9.5 §9)
# ---------------------------------------------------------------------------
# `source_type` is free descriptive text, never a score or a ranking (§9).
# `published_at` is left unset for every source because the consulted pages and
# repository files do not state a reliable publication date: dates are
# declarative and are never guessed. `observed_at` records the review date.

SOURCE_LLAMACPP_README: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: README.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/README.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_BUILD: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: docs/build.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_SYCL: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: docs/backend/SYCL.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/SYCL.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_MODELS: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: docs/models.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/models.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_SERVER: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: tools/server/README.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_MULTIMODAL: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: docs/multimodal.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_FUNCTION_CALLING: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: docs/function-calling.md",
    source_type="official project documentation",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md",
    observed_at=OBSERVED_AT,
)
SOURCE_LLAMACPP_ARCH_REGISTRY: KnowledgeProvenance = KnowledgeProvenance(
    source="llama.cpp repository: src/llama-arch.cpp (LLM_ARCH_NAMES registry)",
    source_type="official project source file: architecture identifier registry",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/src/llama-arch.cpp",
    observed_at=OBSERVED_AT,
)

SOURCE_OLLAMA_README: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama repository: README.md",
    source_type="official project documentation",
    reference="https://github.com/ollama/ollama/blob/main/README.md",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_GPU: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: Hardware support (gpu)",
    source_type="official documentation",
    reference="https://docs.ollama.com/gpu",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_LINUX: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: Linux",
    source_type="official documentation",
    reference="https://docs.ollama.com/linux",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_WINDOWS: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: Windows",
    source_type="official documentation",
    reference="https://docs.ollama.com/windows",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_MACOS: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: macOS",
    source_type="official documentation",
    reference="https://docs.ollama.com/macos",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_IMPORT: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: Importing a Model",
    source_type="official documentation",
    reference="https://docs.ollama.com/import",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_FAQ: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: FAQ",
    source_type="official documentation",
    reference="https://docs.ollama.com/faq",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_API: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: API reference (Generate a response)",
    source_type="official documentation",
    reference="https://docs.ollama.com/api/generate",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_VISION: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: capabilities/Vision",
    source_type="official documentation",
    reference="https://docs.ollama.com/capabilities/vision",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_EMBEDDINGS: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: capabilities/Embeddings",
    source_type="official documentation",
    reference="https://docs.ollama.com/capabilities/embeddings",
    observed_at=OBSERVED_AT,
)
SOURCE_OLLAMA_TOOL_CALLING: KnowledgeProvenance = KnowledgeProvenance(
    source="Ollama documentation: capabilities/Tool calling",
    source_type="official documentation",
    reference="https://docs.ollama.com/capabilities/tool-calling",
    observed_at=OBSERVED_AT,
)

# Provenance of the deliberate UNKNOWN rows: each records which official page
# was consulted and which statement was NOT found there (B9.6.0 §19, §11).
SOURCE_ABSENT_LLAMACPP_ROCM: KnowledgeProvenance = KnowledgeProvenance(
    source=(
        "llama.cpp docs/build.md consulted: the HIP section names ROCm only as a "
        "prerequisite for the HIP build; no statement about a ROCm backend exists"
    ),
    source_type="official project documentation: absence-of-statement check",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md",
    observed_at=OBSERVED_AT,
)
SOURCE_ABSENT_OLLAMA_CUDA: KnowledgeProvenance = KnowledgeProvenance(
    source=(
        "Ollama docs/gpu and docs/windows consulted: NVIDIA GPUs, drivers and "
        "CUDA_VISIBLE_DEVICES are documented; no CUDA-backend statement exists"
    ),
    source_type="official documentation: absence-of-statement check",
    reference="https://docs.ollama.com/gpu",
    observed_at=OBSERVED_AT,
)
SOURCE_ABSENT_OLLAMA_SYCL: KnowledgeProvenance = KnowledgeProvenance(
    source=(
        "Ollama docs/gpu consulted: Intel GPUs appear only in the Vulkan driver "
        "instructions; no SYCL-backend statement exists"
    ),
    source_type="official documentation: absence-of-statement check",
    reference="https://docs.ollama.com/gpu",
    observed_at=OBSERVED_AT,
)
SOURCE_ABSENT_OLLAMA_ARCHITECTURE: KnowledgeProvenance = KnowledgeProvenance(
    source=(
        "Ollama documentation set consulted (import, Modelfile, capabilities): "
        "model files are named, but no architecture support statement exists"
    ),
    source_type="official documentation: absence-of-statement check",
    reference="https://docs.ollama.com/import",
    observed_at=OBSERVED_AT,
)
SOURCE_ABSENT_LLAMACPP_CODE_GENERATION: KnowledgeProvenance = KnowledgeProvenance(
    source=(
        "llama.cpp documentation set consulted (README, docs, server): generation "
        "of text is documented; no code-generation capability statement exists"
    ),
    source_type="official project documentation: absence-of-statement check",
    reference="https://github.com/ggml-org/llama.cpp/blob/master/README.md",
    observed_at=OBSERVED_AT,
)
# ---------------------------------------------------------------------------
# llama.cpp -> backend (B9.6.0 §4, §15)
# ---------------------------------------------------------------------------
# build.md documents a "## CPU Build" section (the default CMake build) and the
# README states "Plain C/C++ implementation without any dependencies". Neither
# names a platform, so the row stays global (§11, §12).
LLAMACPP_SUPPORTS_CPU: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_CPU,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_BUILD,
)

# build.md "## Vulkan" contains platform-specific subsections: "### For Windows
# Users:", "### For Linux users:" and "### For Mac users:" (the macOS path is
# documented through LunarG's Vulkan SDK for macOS). Each platform therefore has
# its own row (§12) and no global Vulkan row is added.
LLAMACPP_SUPPORTS_VULKAN_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_VULKAN,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_WINDOWS,
    provenance=SOURCE_LLAMACPP_BUILD,
)
LLAMACPP_SUPPORTS_VULKAN_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_VULKAN,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_LINUX,
    provenance=SOURCE_LLAMACPP_BUILD,
)
LLAMACPP_SUPPORTS_VULKAN_MACOS: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_VULKAN,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_MACOS,
    provenance=SOURCE_LLAMACPP_BUILD,
)

# build.md "## CUDA": "This provides GPU acceleration using an NVIDIA GPU." The
# README repeats the backend ("Custom CUDA kernels for running LLMs on NVIDIA
# GPUs"). The section has no per-platform subsection, so no platform scope is
# invented; the NVIDIA mention is vendor wording and does not create any
# hardware or vendor assertion (§13, §18 rule 1).
LLAMACPP_SUPPORTS_CUDA: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_CUDA,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_BUILD,
)

# build.md "## HIP": "This provides GPU acceleration on HIP-supported AMD GPUs.",
# with separate build instructions "Using `CMake` for Linux ..." and "Using
# `CMake` for Windows ...". Global row plus the two platforms named by the
# source; the AMD GPU wording stays vendor wording (§13, §18 rule 1).
LLAMACPP_SUPPORTS_HIP: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_HIP,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_BUILD,
)
LLAMACPP_SUPPORTS_HIP_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_HIP,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_LINUX,
    provenance=SOURCE_LLAMACPP_BUILD,
)
LLAMACPP_SUPPORTS_HIP_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_HIP,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_WINDOWS,
    provenance=SOURCE_LLAMACPP_BUILD,
)
# build.md "## SYCL": "llama.cpp based on SYCL is used to support Intel GPU
# (Data Center Max series, Flex series, Arc series, Built-in GPU and iGPU)"
# (the phrase "support Intel GPU" is bold in the source).
# SYCL.md then gives an OS support table with explicit rows
# "| Linux | Support | Ubuntu 22.04, Fedora Silverblue 39, Arch Linux |" and
# "| Windows | Support | Windows 11 |", which is the platform evidence used
# here (§12). The Intel GPU family wording is vendor wording and is not turned
# into a hardware assertion (§13, §14, §18 rule 1).
LLAMACPP_SUPPORTS_SYCL_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_SYCL,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_LINUX,
    provenance=SOURCE_LLAMACPP_SYCL,
)
LLAMACPP_SUPPORTS_SYCL_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_SYCL,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_WINDOWS,
    provenance=SOURCE_LLAMACPP_SYCL,
)

# SYCL.md "### Windows" states "The following releases are verified and
# recommended:" for the tag b5377, whose verified platform cell lists both
# "Arc B580/Linux/oneAPI 2025.1" and "LNL Arc GPU/Windows 11/oneAPI 2025.1.1"
# with update date 2025-05-15. Because the verified cell spans two platforms,
# only the version is recorded as scope (§11) instead of pairing a version with
# a platform the table does not pair.
LLAMACPP_SUPPORTS_SYCL_B5377: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_SYCL,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_LLAMACPP_B5377,
    provenance=SOURCE_LLAMACPP_SYCL,
)

# Deliberate UNKNOWN (§19): the HIP section names ROCm only as a prerequisite
# for the HIP build, so the documentation never declares a ROCm backend. ROCm
# and HIP are different entities (§4) and one is never substituted for the
# other, hence UNKNOWN and not SUPPORTED, and not UNSUPPORTED either (§8).
LLAMACPP_ROCM_UNKNOWN: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_ROCM,
    state=KnowledgeState.UNKNOWN,
    provenance=SOURCE_ABSENT_LLAMACPP_ROCM,
)

# §15 format: docs/models.md states "`llama.cpp` requires the model to be stored
# in the GGUF file format." GGUF identifies a format only: no architecture,
# capability or backend is inferred from it (§5, §18 rule 3).
LLAMACPP_SUPPORTS_GGUF: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=FORMAT_GGUF,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_MODELS,
)

# ---------------------------------------------------------------------------
# Ollama -> backend (B9.6.0 §4, §15)
# ---------------------------------------------------------------------------
# Ollama's Hardware support page documents CPU execution explicitly: "If you
# want to ignore the GPUs and force CPU usage, use an invalid GPU ID (e.g.,
# "-1")", and the FAQ reports CPU inference ("100% CPU means the model was
# loaded entirely in system memory", "or 3 for CPU inference"). No platform is
# named, so the row stays global.
OLLAMA_SUPPORTS_CPU: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_CPU,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_GPU,
)

# Hardware support "## AMD Radeon": "Ollama supports the following AMD GPUs via
# the ROCm library", with a "### Linux Support" statement ("Ollama requires the
# AMD ROCm v7 driver on Linux") and a "### Windows Support" statement ("Ollama
# requires an AMD ROCm v7 / HIP7-capable driver stack on Windows", repeated as a
# Windows requirement in docs/windows.md). The vendor card lists that follow are
# hardware, out of scope (§13, §14): only the ROCm backend is recorded.
OLLAMA_SUPPORTS_ROCM: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_ROCM,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_GPU,
)
OLLAMA_SUPPORTS_ROCM_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_ROCM,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_LINUX,
    provenance=SOURCE_OLLAMA_GPU,
)
OLLAMA_SUPPORTS_ROCM_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_ROCM,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_WINDOWS,
    provenance=SOURCE_OLLAMA_GPU,
)

# Hardware support "## Vulkan GPU Support": "Additional GPU support on Windows
# and Linux is provided via [Vulkan]." The sentence names exactly two platforms,
# so only those two scoped rows exist: no global Vulkan row (it would widen the
# source) and no macOS row (the same page attributes Apple GPU acceleration to
# the Metal API, which is outside §4).
OLLAMA_SUPPORTS_VULKAN_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_VULKAN,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_WINDOWS,
    provenance=SOURCE_OLLAMA_GPU,
)
OLLAMA_SUPPORTS_VULKAN_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_VULKAN,
    state=KnowledgeState.SUPPORTED,
    scope=SCOPE_PLATFORM_LINUX,
    provenance=SOURCE_OLLAMA_GPU,
)

# Deliberate UNKNOWN (§19, near miss documented in NEAR_MISS_EXCLUSIONS): the
# Hardware support page pairs Ollama with NVIDIA GPUs, driver versions,
# CUDA_VISIBLE_DEVICES and a compute-capability table, but never declares a CUDA
# backend. A GPU vendor is not a backend (§4, §18 rule 1), so CUDA stays
# UNKNOWN and is not inferred from the NVIDIA material.
OLLAMA_CUDA_UNKNOWN: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_CUDA,
    state=KnowledgeState.UNKNOWN,
    provenance=SOURCE_ABSENT_OLLAMA_CUDA,
)

# Deliberate UNKNOWN (§19): no consulted Ollama page declares a SYCL backend.
# Intel GPUs appear only inside the Vulkan driver instructions ("Linux Intel GPU
# Instructions"), and Intel hardware or driver documentation is not a SYCL
# statement (§4, §18 rule 1).
OLLAMA_SYCL_UNKNOWN: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=BACKEND_SYCL,
    state=KnowledgeState.UNKNOWN,
    provenance=SOURCE_ABSENT_OLLAMA_SYCL,
)

# §15 format: "Importing a Model" has an "## Importing a GGUF model" section
# stating "Ollama does not quantize GGUF models during import. Prepare and
# quantize them first with a GGUF tool such as llama.cpp's `llama-quantize`",
# and shows a Modelfile `FROM` entry pointing to a local `.gguf` file (single
# file and split shards). Format support only: no architecture, capability or
# backend is inferred from it (§5, §18 rule 3), and the mention of a llama.cpp
# tool does not create any relation between the two runtimes (§17).
OLLAMA_SUPPORTS_GGUF: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=FORMAT_GGUF,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_IMPORT,
)

# ---------------------------------------------------------------------------
# llama.cpp -> architecture (B9.6.0 §6, §18 rule 2)
# ---------------------------------------------------------------------------
# Identifiers are taken from the runtime's own architecture registry
# (LLM_ARCH_NAMES): `{ LLM_ARCH_LLAMA, "llama" }` and
# `{ LLM_ARCH_QWEN3, "qwen3" }`. The registry is a list of identifiers the
# runtime recognizes: it is not a model catalogue and no model name, family or
# release note is used as evidence.
LLAMACPP_SUPPORTS_ARCHITECTURE_LLAMA: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=ARCHITECTURE_LLAMA,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_ARCH_REGISTRY,
)
LLAMACPP_SUPPORTS_ARCHITECTURE_QWEN3: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=ARCHITECTURE_QWEN3,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_ARCH_REGISTRY,
)

# Deliberate architecture UNKNOWN (§6 case 2, §19): no consulted Ollama page
# states which model architectures the runtime supports. Model names that appear
# in examples (`gemma4`, `qwen3` tags, embedding models) are catalogue entries,
# not architecture support statements (§18 rule 2), so nothing is inferred.
OLLAMA_ARCHITECTURE_LLAMA_UNKNOWN: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=ARCHITECTURE_LLAMA,
    state=KnowledgeState.UNKNOWN,
    provenance=SOURCE_ABSENT_OLLAMA_ARCHITECTURE,
)

# ---------------------------------------------------------------------------
# llama.cpp -> capability (B9.6.0 §7)
# ---------------------------------------------------------------------------
# README: "LLM inference in C/C++"; server README: "LLM inference of F16 and
# quantized models on GPU and CPU" and "Set of LLM REST APIs".
LLAMACPP_SUPPORTS_TEXT_GENERATION: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_TEXT_GENERATION,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_README,
)

# docs/multimodal.md: "llama.cpp supports multimodal input via `libmtmd`" and
# "Currently, we support **image**, **audio** and **video** input." Only the
# vision capability is recorded here; audio is not part of the §7 taxonomy.
LLAMACPP_SUPPORTS_VISION: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_VISION,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_MULTIMODAL,
)

# server README lists "OpenAI API compatible chat completions, responses, and
# embeddings routes".
LLAMACPP_SUPPORTS_EMBEDDINGS: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_EMBEDDINGS,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_SERVER,
)

# server README lists "Function calling / tool use for ~any model", and
# docs/function-calling.md states that "chat.h adds support for OpenAI-style
# function calling". "~any model" is a scope statement about models, not about
# hardware, platforms or backends, so it creates no other assertion (§11).
LLAMACPP_SUPPORTS_TOOL_USE: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_TOOL_USE,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_LLAMACPP_FUNCTION_CALLING,
)

# Deliberate capability UNKNOWN (§19): no consulted llama.cpp source declares a
# code-generation capability. Names such as "Qwen 2.5 Coder" in the
# function-calling page are model names and are never used as evidence
# (§18 rule 2).
LLAMACPP_CODE_GENERATION_UNKNOWN: KnowledgeAssertion = KnowledgeAssertion(
    subject=LLAMACPP,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_CODE_GENERATION,
    state=KnowledgeState.UNKNOWN,
    provenance=SOURCE_ABSENT_LLAMACPP_CODE_GENERATION,
)

# ---------------------------------------------------------------------------
# Ollama -> capability (B9.6.0 §7)
# ---------------------------------------------------------------------------
# API reference for /api/generate: "Generates a response for the provided
# prompt"; the FAQ describes models loaded for inference in system memory or
# VRAM ("system memory when using CPU inference, or VRAM for GPU inference").
OLLAMA_SUPPORTS_TEXT_GENERATION: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_TEXT_GENERATION,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_API,
)

# capabilities/Vision: "Vision models accept images alongside text so the model
# can describe, classify, and answer questions about what it sees."
OLLAMA_SUPPORTS_VISION: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_VISION,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_VISION,
)

# capabilities/Embeddings: "Embeddings turn text into numeric vectors you can
# store in a vector database, search with cosine similarity, or use in RAG
# pipelines." The recommended model list is a catalogue and creates no
# architecture assertion (§18 rule 2).
OLLAMA_SUPPORTS_EMBEDDINGS: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_EMBEDDINGS,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_EMBEDDINGS,
)

# capabilities/Tool calling: "Ollama supports tool calling (also known as
# function calling) which allows a model to invoke tools and incorporate their
# results into its replies."
OLLAMA_SUPPORTS_TOOL_USE: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=CAPABILITY_TOOL_USE,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_TOOL_CALLING,
)

# ---------------------------------------------------------------------------
# Ollama -> platform (B9.6.0 §12)
# ---------------------------------------------------------------------------
# Platform rows describe the operating system the runtime runs on; they are not
# backend rows and no backend is inferred from them (§4, §18 rule 1). Apple GPU
# acceleration, mentioned as a macOS system requirement, is a Metal statement
# and is therefore out of §4.
#
# macOS page, "## System Requirements": "MacOS Sonoma (v14) or newer" and
# "Apple M series (CPU and GPU support) or x86 (CPU only)".
OLLAMA_SUPPORTS_PLATFORM_MACOS: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=PLATFORM_MACOS,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_MACOS,
)

# Windows page: "Ollama runs as a native Windows application, including NVIDIA
# and AMD Radeon GPU support."
OLLAMA_SUPPORTS_PLATFORM_WINDOWS: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=PLATFORM_WINDOWS,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_WINDOWS,
)

# Linux page: a dedicated Linux page with "## Install", "## Manual install",
# "### AMD GPU install" and "### ARM64 install" sections. The AMD GPU package is
# a platform installation artifact; it is not used as backend evidence because
# backend rows have their own source (Hardware support).
OLLAMA_SUPPORTS_PLATFORM_LINUX: KnowledgeAssertion = KnowledgeAssertion(
    subject=OLLAMA,
    predicate=KnowledgePredicate.SUPPORTS,
    object=PLATFORM_LINUX,
    state=KnowledgeState.SUPPORTED,
    provenance=SOURCE_OLLAMA_LINUX,
)

# ---------------------------------------------------------------------------
# The dataset (B9.6.0 §20-§22)
# ---------------------------------------------------------------------------
# 37 rows: 32 SUPPORTED, 5 UNKNOWN, 0 UNSUPPORTED. There is deliberately no
# UNSUPPORTED row: no consulted source states that a runtime does not support a
# backend, format, architecture, capability or platform, and inventing one is
# prohibited (§8, §19). Order in this tuple carries no meaning: the registry
# sorts its entries (§22), and the order-independence test proves it.
INITIAL_KNOWLEDGE: tuple[KnowledgeAssertion, ...] = (
    # llama.cpp: backends and format
    LLAMACPP_SUPPORTS_CPU,
    LLAMACPP_SUPPORTS_VULKAN_WINDOWS,
    LLAMACPP_SUPPORTS_VULKAN_LINUX,
    LLAMACPP_SUPPORTS_VULKAN_MACOS,
    LLAMACPP_SUPPORTS_CUDA,
    LLAMACPP_SUPPORTS_HIP,
    LLAMACPP_SUPPORTS_HIP_LINUX,
    LLAMACPP_SUPPORTS_HIP_WINDOWS,
    LLAMACPP_SUPPORTS_SYCL_LINUX,
    LLAMACPP_SUPPORTS_SYCL_WINDOWS,
    LLAMACPP_SUPPORTS_SYCL_B5377,
    LLAMACPP_ROCM_UNKNOWN,
    LLAMACPP_SUPPORTS_GGUF,
    # Ollama: backends and format
    OLLAMA_SUPPORTS_CPU,
    OLLAMA_SUPPORTS_ROCM,
    OLLAMA_SUPPORTS_ROCM_LINUX,
    OLLAMA_SUPPORTS_ROCM_WINDOWS,
    OLLAMA_SUPPORTS_VULKAN_WINDOWS,
    OLLAMA_SUPPORTS_VULKAN_LINUX,
    OLLAMA_CUDA_UNKNOWN,
    OLLAMA_SYCL_UNKNOWN,
    OLLAMA_SUPPORTS_GGUF,
    # Architectures
    LLAMACPP_SUPPORTS_ARCHITECTURE_LLAMA,
    LLAMACPP_SUPPORTS_ARCHITECTURE_QWEN3,
    OLLAMA_ARCHITECTURE_LLAMA_UNKNOWN,
    # Capabilities
    LLAMACPP_SUPPORTS_TEXT_GENERATION,
    LLAMACPP_SUPPORTS_VISION,
    LLAMACPP_SUPPORTS_EMBEDDINGS,
    LLAMACPP_SUPPORTS_TOOL_USE,
    LLAMACPP_CODE_GENERATION_UNKNOWN,
    OLLAMA_SUPPORTS_TEXT_GENERATION,
    OLLAMA_SUPPORTS_VISION,
    OLLAMA_SUPPORTS_EMBEDDINGS,
    OLLAMA_SUPPORTS_TOOL_USE,
    # Platforms
    OLLAMA_SUPPORTS_PLATFORM_MACOS,
    OLLAMA_SUPPORTS_PLATFORM_WINDOWS,
    OLLAMA_SUPPORTS_PLATFORM_LINUX,
)

# Ready-to-query view of the dataset, built only with the B9.5 public API.
INITIAL_KNOWLEDGE_REGISTRY: KnowledgeRegistry = KnowledgeRegistry(INITIAL_KNOWLEDGE)

# The deliberate UNKNOWN rows, grouped so the mandate of §19 is auditable in one
# place. All of them are stored records, never silent absences.
DELIBERATE_UNKNOWN_ROWS: tuple[KnowledgeAssertion, ...] = (
    LLAMACPP_ROCM_UNKNOWN,
    OLLAMA_CUDA_UNKNOWN,
    OLLAMA_SYCL_UNKNOWN,
    OLLAMA_ARCHITECTURE_LLAMA_UNKNOWN,
    LLAMACPP_CODE_GENERATION_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Reviewer metadata (documentation only: no assertion is derived from these)
# ---------------------------------------------------------------------------
# Deviations from the §19 candidate list, each one settled by primary evidence.
DELIBERATE_ADJUSTMENTS: tuple[str, ...] = (
    (
        "§19 candidate 'SYCL on Windows -> UNKNOWN' withdrawn: docs/backend/SYCL.md "
        "has a Windows section whose release table is 'verified and recommended' for "
        "Windows 11, so llama.cpp + SYCL is recorded as SUPPORTED with platform scope."
    ),
    (
        "§19 candidate 'tool_use -> UNKNOWN' withdrawn: the llama.cpp server feature "
        "list plus docs/function-calling.md, and Ollama's Tool calling page, each state "
        "tool/function calling support, so two separate SUPPORTED rows were recorded."
    ),
    (
        "§19 candidate 'Ollama + architecture -> UNKNOWN' kept as a stored row, which "
        "also satisfies the required architecture UNKNOWN of §6 case 2."
    ),
    (
        "The mandatory runtime/backend UNKNOWN of §4 is kept three times: llama.cpp + "
        "ROCm, Ollama + CUDA and Ollama + SYCL."
    ),
    (
        "§3/§28.3 llama.app: registered only as candidate alias metadata on the llama.cpp "
        "subject. No official ggml-org source presents it as a runtime or distribution, "
        "so no subject, assertion or dedicated registry entry was created for it."
    ),
    (
        "No capability UNKNOWN row was added for Ollama + code_generation: the open world "
        "already answers UNKNOWN for it (§8), and the single mandated capability UNKNOWN "
        "(llama.cpp + code_generation) documents the gap. Duplicating one absence per "
        "runtime would add no information to the dataset."
    ),
)

# Tempting statements that were examined and deliberately NOT encoded. Each is
# either a prerequisite, an artifact label, vendor/hardware material or an
# entity outside §4/§12 - never a compatibility assertion about a runtime.
NEAR_MISS_EXCLUSIONS: tuple[str, ...] = (
    (
        "Ollama docs/gpu 'AMD ROCm v7 / HIP7-capable driver stack on Windows' and the "
        "equivalent docs/windows requirement: a required driver stack for ROCm "
        "acceleration, not a statement of a HIP backend. No Ollama + HIP row exists "
        "(§4, §18 rule 1)."
    ),
    (
        "Ollama docs/windows lists an 'MLX (CUDA)' archive among GPU library packages: an "
        "artifact label, not a CUDA-backend statement, so Ollama + CUDA stays UNKNOWN."
    ),
    (
        "llama.cpp docs/build.md CUDA section requires the CUDA toolkit and points to "
        "NVIDIA's compute-capability page: build prerequisites plus vendor/hardware "
        "material, out of scope (§13)."
    ),
    (
        "llama.cpp docs/build.md '### For Docker users:' inside the Vulkan section: Docker "
        "is not one of the platforms of §12, so it produces no platform-scoped row."
    ),
    (
        "llama.cpp docs/backend/SYCL.md verified-device tables (Intel Arc B-Series, B580) "
        "and oneAPI version requirements: hardware and toolchain requirements. The user's "
        "GPU belongs to Observation + Compatibility Evaluation, not to this dataset "
        "(§13, §14)."
    ),
    (
        "llama.cpp '## BLAS Build' / oneMKL, Ollama's Metal statement for Apple devices, "
        "and Android/Docker sub-pages: constructs outside the §4/§24 backend list and the "
        "§12 platform list remain unrecorded."
    ),
    (
        "Model tags, safetensors import and quantization tooling mentioned by docs/models.md "
        "and docs/import.md: format support is recorded, but no architecture or capability "
        "is inferred from model names or tooling (§18 rules 2-3)."
    ),
)

# Identifiers that exist in the consulted sources but intentionally have no
# subject, no assertion and no entry in this dataset (§24).
EXCLUDED_FROM_INITIAL_DATASET: tuple[str, ...] = (
    (
        "Backends outside the §4 list: metal, blas, blis, onemkl, opencl, cann, musa, "
        "webgpu, openvino, zendnn, rpc, virtgpu, hexagon."
    ),
    (
        "Platforms outside the §12 list: android, docker, ios."
    ),
    (
        "Vendor and hardware entities, never modeled as knowledge subjects: nvidia, amd, "
        "intel, level_zero, apple metal; no hardware family or device model is a subject "
        "(§13, §14, §18 rule 1)."
    ),
    (
        "'llama.app': alias metadata on the llama.cpp subject only, never a runtime "
        "subject (§3, §28.3)."
    ),
    (
        "Architecture identifiers other than the two declared ones: model tags such as "
        "gemma4, qwen3-embedding or embeddinggemma are model catalogue names, not "
        "architecture identifiers (§6, §18 rule 2)."
    ),
    (
        "Runtime variants: no variant scope value is used anywhere in this dataset."
    ),
)

# Known coverage gaps, recorded instead of filled with an invented assertion.
COVERAGE_GAPS: tuple[str, ...] = (
    (
        "The expected relation shape 'runtime+backend -> architecture/capability' (§21) "
        "is empty: no consulted primary source pairs a backend with an architecture or a "
        "capability for either runtime, so no such row exists and no scope was invented "
        "(§11, §19)."
    ),
    (
        "llama.cpp platform scoping is limited to the backends whose own documentation "
        "section names the platform (Vulkan, HIP, SYCL). The CUDA, CPU and GGUF statements "
        "of build.md and models.md are global because their sources are, so a platform "
        "query for them returns UNKNOWN by exact-scope matching."
    ),
    (
        "No runtime-variant scope is used: no consulted source names a variant distinct "
        "from version or platform."
    ),
    (
        "scope.backend_id is unused: backends are modeled as entity objects (§25), so "
        "duplicating a backend inside the scope would duplicate identity."
    ),
    (
        "Historical evidence (release notes, changelogs, older tags) was not used; only "
        "statements currently documented by the projects were encoded. The b5377 row comes "
        "from the 'verified and recommended' release table, not from a changelog."
    ),
    (
        "There are no UNSUPPORTED rows by design: no consulted source states that a runtime "
        "cannot do any of these things, and inventing such a row is prohibited (§8, §19)."
    ),
)
