# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Neutral admission type shared by execution services.

This module exists so that ``execute_model`` and ``run_service`` can both
depend on a common definition of ``EvaluationAdmission`` without either
module importing the other.  It contains NO logic, no behaviour and no
validation: it is a pure data container.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationAdmission:
    """Advisory evaluation signal: a summary copy, never the result object.

    ``status`` is the B9.15/B9.16 outcome (``"evaluated"`` or ``"blocked"``)
    and ``verdict`` the strict verdict name. Admission can deny execution; it
    can never authorize it on its own (B9.19 section 7).
    """

    status: str
    verdict: str | None = None