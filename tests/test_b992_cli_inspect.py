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

"""B9.92: the CLI ``inspect`` command over the B9.80 discovery port.

Every collaborator here is a local fake. No test performs a network call, no
test constructs a production discovery provider and no test reaches the model
store: the command's read-only, identity-free and acquisition-free behaviour is
proven by observation and structurally, not by running a download.
"""

import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from castlearq import main as cli
from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelVariant,
)

REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
REVISION = "a" * 40


def candidate() -> ModelCandidate:
    return ModelCandidate(
        provider_id="huggingface",
        repository=REPOSITORY,
        has_gguf=True,
    )


def artifact(
    filename,
    *,
    quantization="Q4_K_M",
    size=None,
    sha256=None,
    revision=None,
) -> DiscoveredArtifact:
    return DiscoveredArtifact(
        repository=REPOSITORY,
        filename=filename,
        format="GGUF",
        declared_quantization=quantization,
        declared_size=size,
        declared_sha256=sha256,
        revision=revision,
    )


class FakeDiscovery:
    """A local stand-in for the B9.80 discovery port."""

    def __init__(self, variants=(), error=None):
        self.variants = tuple(variants)
        self.error = error
        self.calls = []

    def inspect(self, repository):
        self.calls.append(repository)
        if self.error is not None:
            raise self.error
        return self.variants

    def search(self, query, *, limit=20, cursor=None):
        raise AssertionError("inspect must not perform a search")


def run_inspect(*argv, discovery=None):
    """Run the real CLI dispatch for ``inspect`` and capture its streams."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(
        cli, "_compose_inspection_discovery", return_value=discovery
    ):
        with mock.patch.object(sys, "argv", ["castlearq", "inspect", *argv]):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main()
    return code, out.getvalue(), err.getvalue()
class BasicInspectionTests(unittest.TestCase):
    def test_repository_reaches_the_discovery_port_verbatim(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        code, _, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertEqual(discovery.calls, [REPOSITORY])

    def test_basic_inspection_reports_repository_and_declared_artifact(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [artifact("model-a.gguf", size=1234, sha256="deadbeef")],
                )
            ]
        )
        code, out, err = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn(REPOSITORY, out)
        self.assertIn("Variant: Q4_K_M", out)
        self.assertIn("model-a.gguf", out)
        self.assertIn("Declared size: 1234", out)
        self.assertIn("Declared SHA-256: deadbeef", out)

    def test_output_exposes_no_internal_object_representation(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertNotIn("object at 0x", out)
        self.assertNotIn("DiscoveredArtifact(", out)
        self.assertNotIn("ModelVariant(", out)


class VariantPreservationTests(unittest.TestCase):
    def test_multiple_variants_remain_separately_represented(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(candidate(), "Q4_K_M", [artifact("a-q4.gguf")]),
                ModelVariant(candidate(), "Q8_0", [artifact("a-q8.gguf")]),
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertIn("Variant: Q4_K_M", out)
        self.assertIn("Variant: Q8_0", out)

    def test_variant_order_is_the_provider_order(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(candidate(), "Q8_0", [artifact("a-q8.gguf")]),
                ModelVariant(candidate(), "Q4_K_M", [artifact("a-q4.gguf")]),
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertLess(out.index("Q8_0"), out.index("Q4_K_M"))

    def test_artifact_order_inside_a_variant_is_preserved(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [
                        artifact("first.gguf"),
                        artifact("second.gguf"),
                        artifact("third.gguf"),
                    ],
                )
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertLess(out.index("first.gguf"), out.index("second.gguf"))
        self.assertLess(out.index("second.gguf"), out.index("third.gguf"))
class DeclaredMetadataTests(unittest.TestCase):
    def test_every_declared_value_is_presented_unchanged(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [
                        artifact(
                            "model-a.gguf",
                            quantization="Q4_K_M",
                            size=4096,
                            sha256="abc123",
                            revision=REVISION,
                        )
                    ],
                )
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertIn("Quantization: Q4_K_M", out)
        self.assertIn("Declared size: 4096", out)
        self.assertIn("Declared SHA-256: abc123", out)
        self.assertIn(f"Revision: {REVISION}", out)

    def test_undeclared_values_are_Unknown_and_are_never_defaulted(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertIn("Declared size: Unknown", out)
        self.assertIn("Declared SHA-256: Unknown", out)
        self.assertIn("Revision: Unknown", out)


class RevisionTests(unittest.TestCase):
    def test_a_forty_character_revision_is_displayed_unchanged(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [artifact("model-a.gguf", revision=REVISION)],
                )
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertIn(f"Revision: {REVISION}", out)
        self.assertNotIn("/resolve/", out)

    def test_an_absent_revision_is_never_invented(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [artifact("model-a.gguf", revision=None)],
                )
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertIn("Revision: Unknown", out)
        self.assertNotIn("/resolve/main/", out)
        self.assertNotIn("huggingface.co", out)


class EmptyInspectionTests(unittest.TestCase):
    def test_no_variants_is_a_completed_inspection_with_exit_zero(self):
        discovery = FakeDiscovery([])
        code, out, err = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn(REPOSITORY, out)
        self.assertIn("No GGUF artifacts found.", out)

    def test_empty_inspection_invokes_no_acquisition(self):
        discovery = FakeDiscovery([])
        with mock.patch.object(cli, "compose_acquisition_service") as acquisition:
            code, _, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        acquisition.assert_not_called()


class ErrorPathTests(unittest.TestCase):
    def test_discovery_error_exits_one_and_keeps_the_message(self):
        discovery = FakeDiscovery(
            error=DiscoveryError("Hugging Face metadata request failed: HTTP 404")
        )
        code, out, err = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Inspect error:", err)
        self.assertIn("HTTP 404", err)

    def test_missing_repository_is_a_usage_error(self):
        code, out, err = run_inspect(discovery=FakeDiscovery([]))

        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("Usage: castlearq inspect <repository>", err)


class IdentityIsolationTests(unittest.TestCase):
    def test_inspection_does_not_resolve_a_logical_model_identity(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        with mock.patch.object(cli, "logical_model_id") as identity:
            code, _, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        identity.assert_not_called()

    def test_a_repository_absent_from_the_identity_table_is_still_inspectable(self):
        discovery = FakeDiscovery([])
        code, _, _ = run_inspect(
            "org/model-not-in-identity-table", discovery=discovery
        )

        self.assertEqual(code, 0)
        self.assertEqual(discovery.calls, ["org/model-not-in-identity-table"])


class AcquisitionIsolationTests(unittest.TestCase):
    def test_inspection_never_composes_or_calls_the_acquisition_chain(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        with mock.patch.object(
            cli, "compose_acquisition_service"
        ) as acquisition, mock.patch.object(
            cli, "DownloadPlanner"
        ) as planner, mock.patch.object(
            cli, "Downloader"
        ) as downloader:
            code, _, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        acquisition.assert_not_called()
        planner.assert_not_called()
        downloader.assert_not_called()

    def test_inspection_resolves_no_model_store(self):
        discovery = FakeDiscovery([])
        with mock.patch.object(cli, "resolve_model_store") as store:
            code, _, _ = run_inspect(REPOSITORY, discovery=discovery)

        self.assertEqual(code, 0)
        store.assert_not_called()


class JsonSurfaceTests(unittest.TestCase):
    def test_json_envelope_is_the_existing_schema_version_one(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [
                        artifact(
                            "model-a.gguf",
                            size=4096,
                            sha256="abc123",
                            revision=REVISION,
                        )
                    ],
                )
            ]
        )
        code, out, _ = run_inspect(REPOSITORY, "--json", discovery=discovery)

        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(document["schema"], "castlearq.cli")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], "inspect")
        self.assertIsNone(document["error"])

    def test_json_carries_the_same_semantic_content_as_the_human_report(self):
        discovery = FakeDiscovery(
            [
                ModelVariant(
                    candidate(),
                    "Q4_K_M",
                    [artifact("model-a.gguf", size=4096, revision=REVISION)],
                )
            ]
        )
        _, human, _ = run_inspect(REPOSITORY, discovery=discovery)
        _, raw, _ = run_inspect(REPOSITORY, "--json", discovery=discovery)

        document = json.loads(raw)
        variants = document["payload"]["variants"]
        self.assertEqual(document["payload"]["repository"], REPOSITORY)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["declared_quantization"], "Q4_K_M")
        entry = variants[0]["artifacts"][0]
        self.assertEqual(entry["filename"], "model-a.gguf")
        self.assertEqual(entry["declared_size"]["value"], 4096)
        self.assertEqual(entry["revision"]["value"], REVISION)

        for fragment in ("Q4_K_M", "model-a.gguf", "4096", REVISION):
            self.assertIn(str(fragment), human)

    def test_undeclared_values_are_explicit_unknown_in_json(self):
        discovery = FakeDiscovery(
            [ModelVariant(candidate(), "Q4_K_M", [artifact("model-a.gguf")])]
        )
        code, out, _ = run_inspect(REPOSITORY, "--json", discovery=discovery)

        document = json.loads(out)
        entry = document["payload"]["variants"][0]["artifacts"][0]
        self.assertEqual(code, 0)
        self.assertEqual(entry["declared_sha256"]["status"], "unknown")
        self.assertEqual(entry["revision"]["status"], "unknown")

    def test_empty_json_inspection_is_a_success_envelope(self):
        discovery = FakeDiscovery([])
        code, out, _ = run_inspect(REPOSITORY, "--json", discovery=discovery)

        document = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(document["payload"]["variants"], [])
        self.assertIsNone(document["error"])

    def test_json_error_uses_the_existing_error_shape(self):
        discovery = FakeDiscovery(error=DiscoveryError("metadata request failed"))
        code, out, _ = run_inspect(REPOSITORY, "--json", discovery=discovery)

        document = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(document["error"]), ["kind", "message"])
        self.assertEqual(document["error"]["kind"], "inspect_discovery_failed")


class CliRegressionTests(unittest.TestCase):
    def test_every_registered_command_is_still_present(self):
        source = pathlib.Path("castlearq/main.py").read_text(encoding="utf-8")

        for command in (
            "detect",
            "diagnose",
            "verify",
            "models",
            "list",
            "runtime",
            "source",
            "search",
            "inspect",
            "plan",
            "compatibility",
            "validate",
            "download",
            "import",
            "run",
            "execute",
            "chat",
            "serve",
            "store",
        ):
            self.assertIn(f'"{command}"', source)

    def test_inspect_does_not_accept_the_selection_flags(self):
        with self.assertRaises(SystemExit) as raised:
            with mock.patch.object(
                sys, "argv", ["castlearq", "inspect", REPOSITORY, "--quantization", "Q4"]
            ):
                with redirect_stderr(io.StringIO()):
                    cli.main()

        self.assertNotEqual(raised.exception.code, 0)

    def test_inspect_rejects_a_second_positional_argument(self):
        with self.assertRaises(SystemExit) as raised:
            with mock.patch.object(
                sys, "argv", ["castlearq", "inspect", REPOSITORY, "extra"]
            ):
                with redirect_stderr(io.StringIO()):
                    cli.main()

        self.assertNotEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
