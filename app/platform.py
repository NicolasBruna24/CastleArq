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

"""Single source of truth for the operating environment (Block B6).

Answers *"what platform are we on?"* as one read-only, deterministic model:
:data:`PlatformInfo`. It reuses the existing conventions of the project
instead of introducing new ones:

* the canonical platform token comes from :func:`app.hardware.detect_platform`
  (``linux``/``windows``/``macos`` or ``""`` when unknown);
* the distribution identity comes from the existing ``/etc/os-release``
  parser in :mod:`app.gpu_setup` (:class:`OsReleaseInfo`);
* the architecture follows the existing ``platform.machine()`` convention
  (``"Unknown"`` when it cannot be determined).

Nothing here executes commands, touches the network, or writes anything.
Unknown facts stay empty (``""``) — nothing is invented and Linux/Ubuntu/apt
are never assumed from missing evidence.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Callable

from pathlib import Path

from .gpu_setup import OsReleaseInfo, read_os_release_info
from .hardware import detect_platform

OsReleaseReader = Callable[[Path], str]


#: Distribution families recognised from ``/etc/os-release`` evidence.
_DISTRIBUTION_FAMILIES: frozenset[str] = frozenset({
    "ubuntu", "debian", "fedora", "arch", "manjaro", "opensuse",
    "centos", "rhel", "rocky", "almalinux", "gentoo", "alpine", "nixos",
})

#: Distros whose ``ID`` is distinct but whose family is well known via
#: ``ID_LIKE`` conventions; used only when the ``ID`` itself is not a family.
_DISTRIBUTION_ALIASES: dict[str, str] = {
    "linuxmint": "debian",
    "kali": "debian",
    "raspbian": "debian",
    "pop": "ubuntu",
    "neon": "ubuntu",
    "elementary": "ubuntu",
    "zorin": "ubuntu",
    "endeavouros": "arch",
    "garuda": "arch",
    "sles": "opensuse",
}


@dataclass(frozen=True)
class PlatformInfo:
    """Read-only description of the operating environment.

    Empty strings mean "could not be determined"; nothing is inferred from
    missing evidence.
    """

    platform: str = ""
    distribution: str = ""
    distribution_version: str = ""
    architecture: str = ""
    pretty_name: str = ""


def _canonical_distribution(release: OsReleaseInfo) -> str:
    """Canonical distribution token from explicit evidence only."""
    for candidate in (release.id, *release.id_like):
        token = (candidate or "").strip().lower()
        if not token:
            continue
        if token in _DISTRIBUTION_FAMILIES:
            return token
        if token in _DISTRIBUTION_ALIASES:
            return _DISTRIBUTION_ALIASES[token]
    return ""


def detect_platform_info(
    *,
    read: OsReleaseReader | None = None,
    operating_system: str | None = None,
    system: str | None = None,
    machine: str | None = None,
) -> PlatformInfo:
    """Build :class:`PlatformInfo` from injectable, read-only sources.

    ``read`` injects the ``/etc/os-release`` reader (tests); ``system`` and
    ``machine`` inject the ``platform.system()``/``platform.machine()``
    primitives (tests). All default to the real environment. The os-release
    file is consulted only when the platform is Linux; Windows/macOS get no
    distribution fields, and an unknown platform stays unknown.
    """
    token = detect_platform(operating_system, system=system)
    if machine is not None:
        architecture = machine or "Unknown"
    else:
        architecture = platform.machine() or "Unknown"
    if token != "linux":
        return PlatformInfo(platform=token, architecture=architecture)
    release = read_os_release_info(read)
    return PlatformInfo(
        platform=token,
        distribution=_canonical_distribution(release),
        distribution_version=release.version_id or "",
        architecture=architecture,
        pretty_name=release.pretty_name or "",
    )
