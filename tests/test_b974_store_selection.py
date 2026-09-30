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

"""B9.74: the ratified model-store selection policy and store visibility.

Every test runs inside one temporary environment: ``HOME``, ``XDG_DATA_HOME``
and ``XDG_CONFIG_HOME`` all point inside a ``TemporaryDirectory``, so no test
can read, create or modify the developer's real stores
(``~/.local/share/castlearq/models``, ``~/.local/share/localai-hub/models``) or
any real GGUF artifact.

The policy under test:

```text
1. --model-store PATH
2. config.toml [models] directory
3. XDG_DATA_HOME/castlearq/models
4. ~/.local/share/castlearq/models
5. legacy compatibility fallback
```

Selection follows the user's declared intention, never the filesystem.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import main as cli
from app.model_store import (
    STORE_SOURCE_CLI,
    STORE_SOURCE_CONFIG,
    STORE_SOURCE_DEFAULT,
    STORE_SOURCE_LEGACY,
    STORE_SOURCE_XDG,
    ModelStore,
    legacy_store_notice,
    resolve_model_store,
)


def _gguf() -> bytes:
    """Minimal GGUF the existing reader accepts (as in the B9.67 tests)."""
    data = bytearray(b"GGUF" + struct.pack("<IQQ", 3, 0, 1))
    key = b"general.architecture"
    raw = b"qwen2"
    data += struct.pack("<Q", len(key)) + key
    data += struct.pack("<I", 8)
    data += struct.pack("<Q", len(raw)) + raw
    return bytes(data)


GGUF = _gguf()


@contextlib.contextmanager
def store_environment(root: Path, *, xdg_data_home: Path | None = None):
    """An isolated HOME/XDG environment; no real user path is reachable.

    Yields a mapping with the paths the policy talks about. ``XDG_DATA_HOME``
    is set only when asked for and removed from the environment otherwise, so
    "unset" is tested rather than inherited from the machine running the suite.
    """
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    environment = {"HOME": str(home), "XDG_CONFIG_HOME": str(root / "config")}
    if xdg_data_home is not None:
        environment["XDG_DATA_HOME"] = str(xdg_data_home)
    with mock.patch.dict(os.environ, environment, clear=False):
        if xdg_data_home is None:
            os.environ.pop("XDG_DATA_HOME", None)
        yield {
            "home": home,
            "legacy": home / ".local" / "share" / "localai-hub" / "models",
            "default": home / ".local" / "share" / "castlearq" / "models",
            "config": root / "config" / "castlearq" / "config.toml",
        }


def write_config(path: Path, directory: str) -> Path:
    """Write a ``[models] directory`` config file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'# B9.74 test configuration\n[models]\ndirectory = "{directory}"\n',
        encoding="utf-8",
    )
    return path


def run_cli(*argv):
    """Run ``main()`` with injected argv/streams; return (code, out, err)."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["castlearq", *argv]), mock.patch.object(
        sys, "stdout", new=out
    ), mock.patch.object(sys, "stderr", new=err):
        try:
            code = cli.main()
        except SystemExit as exit_error:
            code = exit_error.code if isinstance(exit_error.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def tree_snapshot(root: Path) -> dict[str, str]:
    """Every filesystem entry under ``root``, with a digest for regular files."""
    snapshot: dict[str, str] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        if path.is_file():
            snapshot[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            snapshot[key] = "directory"
    return snapshot


def store_report(out: str) -> dict[str, str]:
    """Parse the ``castlearq store`` report into a mapping."""
    report: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            report[key.strip()] = value.strip()
    return report


class SelectionPolicyTests(unittest.TestCase):
    """The precedence table itself, one test per invariant."""

    def test_1_xdg_wins_even_when_its_directory_is_absent(self):
        """An existing legacy store does not outrank an explicit XDG."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                xdg_store = root / "data" / "castlearq" / "models"
                resolution = resolve_model_store()
                self.assertEqual(resolution.path, xdg_store)
                self.assertEqual(resolution.source, STORE_SOURCE_XDG)
                self.assertTrue(resolution.legacy_detected)
                self.assertFalse(resolution.legacy_used)
                self.assertFalse(resolution.path.exists())
                # The command layer resolves the same store.
                self.assertEqual(ModelStore().root, xdg_store)

    def test_2_creating_the_xdg_store_does_not_change_the_selection(self):
        """``mkdir`` must not be able to move the selection."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                before = resolve_model_store()
                before.path.mkdir(parents=True)
                after = resolve_model_store()
                self.assertEqual(before, after)
                self.assertTrue(after.path.exists())

    def test_3_config_directory_wins_over_an_existing_legacy_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_store = root / "config-store"
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                write_config(paths["config"], str(config_store))
                resolution = resolve_model_store()
                self.assertEqual(resolution.path, config_store)
                self.assertEqual(resolution.source, STORE_SOURCE_CONFIG)
                self.assertFalse(config_store.exists())
                self.assertTrue(resolution.legacy_detected)
                self.assertFalse(resolution.legacy_used)

    def test_4_existing_config_store_still_wins_over_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_store = root / "config-store"
            config_store.mkdir(parents=True)
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                write_config(paths["config"], str(config_store))
                self.assertEqual(resolve_model_store().path, config_store)
                self.assertEqual(
                    resolve_model_store().source, STORE_SOURCE_CONFIG
                )

    def test_5_config_outranks_xdg(self):
        """config.toml > XDG_DATA_HOME, declared directories or not."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_store = root / "config-store"
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                write_config(paths["config"], str(config_store))
                resolution = resolve_model_store()
                self.assertEqual(resolution.path, config_store)
                self.assertEqual(resolution.source, STORE_SOURCE_CONFIG)
                self.assertFalse(config_store.exists())
                self.assertFalse((root / "data").exists())

    def test_6_cli_outranks_config_xdg_and_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli_store = root / "cli-store"
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                write_config(paths["config"], str(root / "config-store"))
                resolution = resolve_model_store(str(cli_store))
                self.assertEqual(resolution.path, cli_store)
                self.assertEqual(resolution.source, STORE_SOURCE_CLI)
                self.assertTrue(resolution.legacy_detected)
                self.assertFalse(resolution.legacy_used)
                self.assertFalse(cli_store.exists())

    def test_10_explicit_selection_wins_while_legacy_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit-store"
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                resolution = resolve_model_store(explicit)
                self.assertEqual(resolution.path, explicit)
                self.assertNotEqual(resolution.path, paths["legacy"])
                self.assertFalse(resolution.legacy_used)

    def test_7_no_selection_falls_back_to_the_legacy_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                resolution = resolve_model_store()
                self.assertEqual(resolution.path, paths["legacy"])
                self.assertEqual(resolution.source, STORE_SOURCE_LEGACY)
                self.assertTrue(resolution.legacy_detected)
                self.assertTrue(resolution.legacy_used)

    def test_8_no_selection_and_no_legacy_uses_the_castlearq_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root) as paths:
                resolution = resolve_model_store()
                self.assertEqual(resolution.path, paths["default"])
                self.assertEqual(resolution.source, STORE_SOURCE_DEFAULT)
                self.assertFalse(resolution.legacy_detected)
                self.assertFalse(resolution.legacy_used)

    def test_15_legacy_regression_still_finds_an_existing_legacy_store(self):
        """The historical case keeps working, through both entry points."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                self.assertEqual(ModelStore().root, paths["legacy"])
                self.assertEqual(resolve_model_store().path, paths["legacy"])

    def test_9_two_xdg_values_select_two_independent_stores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = ModelStore((root / "data-a" / "castlearq" / "models"))
            with store_environment(root, xdg_data_home=root / "data-a"):
                store_a = resolve_model_store()
                ModelStore(store_a.path).save_manifest(_artifact())
                self.assertEqual(len(ModelStore(store_a.path).list_artifacts()), 1)
            with store_environment(root, xdg_data_home=root / "data-b"):
                store_b = resolve_model_store()
            self.assertNotEqual(store_a.path, store_b.path)
            self.assertEqual(store_a.path, first.root)
            self.assertEqual(ModelStore(store_b.path).list_artifacts(), [])
            self.assertEqual(store_b.path, root / "data-b" / "castlearq" / "models")



    def test_11_resolution_and_the_store_command_create_nothing(self):
        """Resolving and reporting must not touch the filesystem."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                before = tree_snapshot(root)
                resolve_model_store()
                self.assertEqual(tree_snapshot(root), before)
                code, out, _ = run_cli("store")
                self.assertEqual(code, 0)
                self.assertIn("Exists: no", out)
                self.assertEqual(tree_snapshot(root), before)
                self.assertFalse((root / "data").exists())

    def test_12_legacy_selection_is_announced_on_stderr_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                notice = legacy_store_notice(resolve_model_store())
                self.assertIsNotNone(notice)
                self.assertIn("legacy predecessor store", notice)
                self.assertIn(str(paths["legacy"]), notice)
                self.assertIn("nothing is moved, copied or deleted", notice)
                code, out, err = run_cli("list")
                self.assertEqual(code, 0)
                self.assertIn(str(paths["legacy"]), err)
                self.assertNotIn("legacy", out.lower())

    def test_12b_explicit_selection_produces_no_legacy_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit-store"
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                self.assertTrue(resolve_model_store().legacy_used)
                self.assertIsNone(legacy_store_notice(resolve_model_store(explicit)))
                code, out, err = run_cli("--model-store", str(explicit), "list")
                self.assertEqual(code, 0)
                self.assertEqual(err, "")
                self.assertNotIn("legacy", (out + err).lower())

    def test_13_store_command_reports_the_whole_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root, xdg_data_home=root / "data") as paths:
                paths["legacy"].mkdir(parents=True)
                self.assertEqual(store_report(run_cli("store")[1]), {
                    "Path": str(root / "data" / "castlearq" / "models"),
                    "Source": "xdg",
                    "Exists": "no",
                    "Legacy detected": "yes",
                    "Legacy used": "no",
                })
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True, exist_ok=True)
                self.assertEqual(store_report(run_cli("store")[1]), {
                    "Path": str(paths["legacy"]),
                    "Source": "legacy-compatibility",
                    "Exists": "yes",
                    "Legacy detected": "yes",
                    "Legacy used": "yes",
                })

    def test_13b_store_command_with_an_explicit_store_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit-store"
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                legacy_before = tree_snapshot(paths["legacy"])
                code, out, _ = run_cli("--model-store", str(explicit), "store")
                self.assertEqual(code, 0)
                self.assertEqual(store_report(out), {
                    "Path": str(explicit),
                    "Source": "cli",
                    "Exists": "no",
                    "Legacy detected": "yes",
                    "Legacy used": "no",
                })
                self.assertFalse(explicit.exists())
                self.assertEqual(tree_snapshot(paths["legacy"]), legacy_before)

    def test_14_import_writes_only_into_the_selected_store(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / "explicit-store"
            external = root / "external"
            external.mkdir()
            source = external / "model.gguf"
            source.write_bytes(GGUF)
            with store_environment(root) as paths:
                paths["legacy"].mkdir(parents=True)
                (paths["legacy"] / "existing.gguf").write_bytes(b"legacy bytes")
                legacy_before = tree_snapshot(paths["legacy"])
                code, out, err = run_cli(
                    "--model-store", str(explicit), "import", str(source)
                )
                self.assertEqual(code, 0, out + err)
                self.assertIn("Status: IMPORTED", out)
                self.assertIn(str(explicit), out)
                self.assertEqual(tree_snapshot(paths["legacy"]), legacy_before)
                self.assertEqual(
                    sorted(p.name for p in paths["legacy"].rglob("*.gguf")),
                    ["existing.gguf"],
                )
                managed = sorted(p for p in explicit.rglob("*.gguf") if p.is_file())
                self.assertEqual(len(managed), 1)
                self.assertEqual(managed[0].read_bytes(), GGUF)

    def test_16_model_store_flag_is_rejected_where_no_store_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with store_environment(root):
                code, _, err = run_cli("--model-store", str(root / "s"), "detect")
                self.assertEqual(code, 2)
                self.assertIn("--model-store is not valid for command 'detect'", err)
                code, _, err = run_cli("--model-store", "", "list")
                self.assertEqual(code, 2)
                self.assertIn("--model-store requires a non-empty path", err)


def _artifact():
    """One declared artifact, for the two-store independence check."""
    from app.models import ArtifactSpec

    return ArtifactSpec(
        model_id="qwen/coder",
        source="huggingface",
        repository="owner/repository",
        filename="model-q4.gguf",
        format="GGUF",
        quantization="Q4_K_M",
    )


if __name__ == "__main__":
    unittest.main()

