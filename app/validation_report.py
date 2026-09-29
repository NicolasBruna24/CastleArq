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

"""P1.3: pure presentation of an already-computed artifact validation.

This module is a **formatter only**, in the same spirit as
:mod:`app.compatibility_report`:

* it invents no verdict, no new status and no new artifact state;
* it creates no type: it renders three ``CheckStatus`` values and one
  optional ``ArtifactState`` label that the caller already derived;
* it performs no I/O, no validation, no resolution and no execution;
* it never changes the meaning of ``PASSED``/``FAILED``/``UNKNOWN``.

The three rendered dimensions are the ones the P1.2 contract defines:

* **safety**  -- did ``ArtifactExecutionPreflight.validate()`` accept the
  artifact as reachable, complete and safe to open;
* **size**    -- does the artifact match ``ArtifactSpec.size_bytes`` when one
  is declared;
* **integrity** -- does the artifact match ``ArtifactSpec.sha256`` when one is
  declared.

``UNKNOWN`` means *insufficient evidence to decide* and is rendered as
``UNKNOWN``. It is never promoted to ``PASSED`` and never demoted to
``FAILED`` -- the same rule the repository already applies to compatibility
checks. In particular an artifact with no declared SHA-256 is reported as
``UNKNOWN``, and this module never claims its contents were verified.

It is deliberately NOT a service, manager, registry or store: it has no
state, no lifecycle and no collaborator.
"""

from __future__ import annotations

from .compatibility_domain import CheckStatus

__all__ = [
    "NO_CHECKSUM_DECLARED",
    "NO_SIZE_DECLARED",
    "format_validation_report",
    "validation_report",
]


# P1.3: these two sentences are the contract. They are stated verbatim so a
# checksum-less artifact can never be read as having been verified, and so a
# missing size declaration is never read as a failing check.
NO_CHECKSUM_DECLARED = "no SHA-256 is declared in the manifest;"
NO_SIZE_DECLARED = "no size is declared in the manifest;"

_DETAIL = {
    ("safety", CheckStatus.PASSED): (
        "final artifact present, regular file, no symlink"
    ),
    ("size", CheckStatus.UNKNOWN): NO_SIZE_DECLARED,
    ("integrity", CheckStatus.UNKNOWN): NO_CHECKSUM_DECLARED,
}


def _status_text(status: object) -> str:
    """Render one ``CheckStatus`` as its repository spelling."""
    return str(getattr(status, "value", status)).upper()


def _dimension(label: str, status: object, detail: str | None = None) -> list[str]:
    """Render one ``label: STATUS`` line plus an optional indented detail."""
    lines = [f"  {label}: {_status_text(status)}"]
    if detail:
        lines.append(f"    {detail}")
    return lines


def validation_report(
    *,
    model_id: str | None,
    filename: str | None,
    safety: CheckStatus,
    size: CheckStatus,
    integrity: CheckStatus,
    state: object | None = None,
    failure: str | None = None,
    size_detail: str | None = None,
    integrity_detail: str | None = None,
) -> list[str]:
    """Build the explanation lines for one artifact validation.

    Every argument is evidence the caller already produced. ``safety``,
    ``size`` and ``integrity`` are ``CheckStatus`` values; ``state`` is the
    already-derived ``ArtifactState`` shown as context only, and ``failure``
    is the existing refusal message (a ``PreflightErrorCode`` message or a
    resolver error) when a check did not pass.

    ``UNKNOWN`` is rendered as ``UNKNOWN``. The function adds no verdict of
    its own and creates no artifact state.
    """
    if model_id and filename:
        lines = [f"{model_id} / {filename}"]
    elif filename:
        lines = [f"/ {filename}"]
    elif model_id:
        lines = [f"{model_id}"]
    else:
        lines = ["Artifact validation"]

    lines += _dimension("safety", safety, _DETAIL.get(("safety", safety)))
    lines += _dimension(
        "size",
        size,
        size_detail if size_detail is not None else _DETAIL.get(("size", size)),
    )
    lines += _dimension(
        "integrity",
        integrity,
        integrity_detail
        if integrity_detail is not None
        else _DETAIL.get(("integrity", integrity)),
    )

    # The integrity detail is split across two lines so the disclaimer stays
    # readable without changing its wording.
    if integrity == CheckStatus.UNKNOWN and integrity_detail is None:
        lines.append("    no content comparison was performed")

    if failure:
        lines.append(f"  Problem: {failure}")
    if state is not None:
        lines.append(f"Artifact state: {_status_text(state)}")
    return lines


def format_validation_report(**kwargs: object) -> str:
    """Render :func:`validation_report` as a single newline-joined string."""
    return "\n".join(validation_report(**kwargs))  # type: ignore[arg-type]