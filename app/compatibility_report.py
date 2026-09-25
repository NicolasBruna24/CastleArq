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

"""B9.48: pure presentation of an existing compatibility evaluation.

This module makes visible what the evaluation already decided. It is a
**formatter only**:

* it reads an existing
  :class:`~app.evaluate_compatibility.EvaluateModelCompatibilityResult`
  and renders it as text;
* it invents no verdict, no check, no recommendation and no remediation;
* it performs no I/O, no evaluation, no admission and no execution;
* it never changes the meaning of ``PASSED``/``FAILED``/``UNKNOWN`` or of
  ``COMPATIBLE``/``INCOMPATIBLE``/``INSUFFICIENT_EVIDENCE``.

Every line below is derived from data that already exists on the result or
its ``StrictEvaluation``. Where the evaluation carries no reason, this
module prints no reason rather than inventing one (B9.48 section 5).

It is deliberately NOT a service, manager, registry or store: it has no
state, no lifecycle and no collaborator. Adding intelligence here is out of
scope by design.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "evaluation_report",
    "format_evaluation_report",
]


def _items(value: Any) -> tuple[Any, ...]:
    """Return ``value`` as a tuple, tolerating absent or non-sequence data.

    A ``StrictEvaluation`` is a frozen dataclass, so its collections are
    always tuples in production. This helper exists so that presentation
    degrades to "nothing to show" instead of raising when a caller supplies a
    stand-in object (tests) or a partially built result. It never invents a
    check and never changes a status.
    """
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(value)


def _status_text(value: Any) -> str:
    """Render a domain status (``CheckStatus``/``CompatibilityStatus``)."""
    if value is None:
        return "UNKNOWN"
    return str(getattr(value, "value", value)).upper()


def _check_line(check: Any) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(header, [(label, value)])`` for one compatibility check.

    Only fields that already exist on ``CompatibilityCheck`` are read:
    ``name``, ``status``, ``expected``, ``observed`` and ``evidence``.
    """
    name = str(getattr(check, "name", "unnamed"))
    status = _status_text(getattr(check, "status", None))
    header = f"  {name}: {status}"

    details: list[tuple[str, str]] = []
    expected = getattr(check, "expected", None)
    observed = getattr(check, "observed", None)
    if expected is not None or observed is not None:
        details.append(("Expected", repr(expected)))
        details.append(("Observed", repr(observed)))
    for item in _items(getattr(check, "evidence", ())):
        source = str(getattr(item, "source", "unknown"))
        value = repr(getattr(item, "value", None))
        kind = str(getattr(getattr(item, "kind", None), "value", "observed"))
        details.append((f"Evidence ({kind})", f"{source} = {value}"))
    return header, details


def evaluation_report(result: Any) -> list[str]:
    """Build the explanation lines for one evaluation result.

    Accepts an ``EvaluateModelCompatibilityResult``. ``None`` and malformed
    inputs are tolerated (defensive ``getattr`` access) so that a partially
    built result can still be explained instead of crashing presentation.
    """
    if result is None:
        return ["No compatibility evaluation result is available."]

    lines: list[str] = ["Compatibility evaluation"]

    model_id = getattr(result, "model_id", None)
    if model_id:
        lines.append(f"  Model: {model_id}")
    artifact = getattr(result, "artifact", None)
    filename = getattr(artifact, "filename", None)
    if filename:
        quantization = getattr(artifact, "quantization", None)
        suffix = f" ({quantization})" if quantization else ""
        lines.append(f"  Artifact: {filename}{suffix}")
    runtime = getattr(result, "runtime", None)
    if runtime:
        lines.append(f"  Runtime: {runtime}")

    evaluation = getattr(result, "evaluation", None)
    strict = getattr(evaluation, "result", None)

    # A blocked result carries its cause in ``blocking_outcome`` and has no
    # StrictEvaluation to inspect.
    blocking_outcome = getattr(result, "blocking_outcome", None)
    if strict is None:
        status = _status_text(getattr(result, "status", None))
        lines.append(f"  Verdict: {status} (not admitted)")
        if blocking_outcome:
            lines.append(f"  Reason: {blocking_outcome}")
        return lines

    lines.append(f"  Verdict: {_status_text(getattr(strict, 'status', None))}")

    checks = _items(getattr(strict, "checks", ()))
    if checks:
        lines.append("")
        lines.append("Checks:")
        for check in checks:
            header, details = _check_line(check)
            lines.append(header)
            for label, value in details:
                lines.append(f"    {label}: {value}")

    for condition in _items(getattr(strict, "conditions", ())):
        name = str(getattr(condition, "name", "unnamed"))
        description = str(getattr(condition, "description", ""))
        lines.append(f"  Condition: {name}: {description}")

    for warning in _items(getattr(strict, "warnings", ())):
        lines.append(f"  Warning: {warning}")

    if blocking_outcome:
        lines.append(f"  Reason: {blocking_outcome}")

    return lines


def format_evaluation_report(result: Any) -> str:
    """Render :func:`evaluation_report` as a single newline-joined string."""
    return "\n".join(evaluation_report(result))
