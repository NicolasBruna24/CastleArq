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

"""B9.82 tests: discovery-to-acquisition mapping boundary (AC1-AC22)."""
from __future__ import annotations

import ast
import dataclasses
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from castlearq.acquisition_mapping import (
    AcquisitionMappingError,
    map_discovered_artifacts,
)
from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelVariant,
)
from castlearq.models import ArtifactSpec, ArtifactState

MODULE_PATH = Path("castlearq/acquisition_mapping.py")
REPO = "owner/repository"
SHA = "ab" * 32
REVISION = "0" * 40
# B9.83: the declared locator must correspond to the declared revision. A
# revision-aware acquisition flow pins the exact upstream reference; the
# unpinned `/resolve/main/` form remains the contract when none is declared.
URL = f"https://huggingface.co/{REPO}/resolve/main/model-Q4_K_M.gguf"
REVISION_URL = f"https://huggingface.co/{REPO}/resolve/{REVISION}/model-Q4_K_M.gguf"
MODEL_ID = "test-model"


class RecordingResolver:
    """Caller-owned identity policy; records every repository it is asked."""

    def __init__(self, value=MODEL_ID):
        self.value = value
        self.calls: list[str] = []

    def __call__(self, repository):
        self.calls.append(repository)
        return self.value


def artifact(**over):
    base = {
        "repository": REPO,
        "filename": "model-Q4_K_M.gguf",
        "format": "GGUF",
        "declared_quantization": "Q4_K_M",
        "model_id": None,
        "source": "huggingface",
        "download_url": REVISION_URL,
        "declared_size": 1234,
        "declared_sha256": SHA,
        "revision": REVISION,
    }
    base.update(over)
    if base["revision"] is None:
        # No declared revision means the unpinned `main` locator; the two
        # must never disagree.
        base.setdefault("download_url", URL)
    return DiscoveredArtifact(**base)


def candidate(**over):
    base = {"provider_id": "huggingface", "repository": REPO}
    base.update(over)
    return ModelCandidate(**base)


def variant(*artifacts, **over):
    items = artifacts or (artifact(),)
    base = {
        "candidate": candidate(),
        "declared_quantization": "Q4_K_M",
        "artifacts": items,
    }
    base.update(over)
    return ModelVariant(**base)


def mapped(artifacts=None, **over):
    resolver = over.pop("identity_resolver", None) or RecordingResolver()
    return map_discovered_artifacts(
        artifact() if artifacts is None else artifacts,
        identity_resolver=resolver,
    )


def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def imported_modules() -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(module_source())):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


class VariantInputTests(unittest.TestCase):
    """Input shapes, 1:1 cardinality and order preservation (AC1, AC2)."""

    def test_variant_produces_artifact_spec(self):
        specs = mapped(variant())
        self.assertIsInstance(specs, tuple)
        self.assertEqual(len(specs), 1)
        self.assertIsInstance(specs[0], ArtifactSpec)

    def test_iterable_produces_tuple(self):
        specs = mapped([artifact()])
        self.assertIsInstance(specs, tuple)
        self.assertEqual(len(specs), 1)

    def test_generator_is_accepted(self):
        specs = mapped(a for a in (artifact(),))
        self.assertEqual(len(specs), 1)

    def test_empty_iterable_produces_empty_tuple(self):
        resolver = RecordingResolver()
        self.assertEqual(
            map_discovered_artifacts([], identity_resolver=resolver), ()
        )
        self.assertEqual(resolver.calls, [])

    def test_mapping_is_one_to_one(self):
        artifacts = [
            artifact(filename="a.gguf"),
            artifact(filename="b.gguf"),
            artifact(filename="c.gguf"),
        ]
        specs = mapped(artifacts)
        self.assertEqual(len(specs), len(artifacts))
        self.assertEqual(
            [spec.filename for spec in specs], ["a.gguf", "b.gguf", "c.gguf"]
        )

    def test_order_is_preserved(self):
        artifacts = [
            artifact(filename="z.gguf"),
            artifact(filename="a.gguf"),
            artifact(filename="m.gguf"),
        ]
        specs = mapped(artifacts)
        self.assertEqual(
            [spec.filename for spec in specs],
            [item.filename for item in artifacts],
        )

    def test_variant_with_several_artifacts_keeps_order(self):
        artifacts = (
            artifact(filename="q8.gguf", declared_quantization="Q8_0"),
            artifact(filename="q4.gguf"),
        )
        specs = mapped(variant(*artifacts))
        self.assertEqual([spec.filename for spec in specs], ["q8.gguf", "q4.gguf"])


class FieldMappingTests(unittest.TestCase):
    """Every declared field is preserved exactly (AC9)."""

    def setUp(self):
        (self.spec,) = mapped([artifact()])

    def test_source_repository_filename_format(self):
        self.assertEqual(self.spec.source, "huggingface")
        self.assertEqual(self.spec.repository, REPO)
        self.assertEqual(self.spec.filename, "model-Q4_K_M.gguf")
        self.assertEqual(self.spec.format, "GGUF")

    def test_declared_quantization_becomes_quantization(self):
        self.assertEqual(self.spec.quantization, "Q4_K_M")

    def test_declared_size_becomes_size_bytes(self):
        self.assertEqual(self.spec.size_bytes, 1234)

    def test_declared_sha256_becomes_sha256(self):
        self.assertEqual(self.spec.sha256, SHA)

    def test_download_url_preserved(self):
        # B9.83: the declared locator is preserved exactly. The fixture
        # declares a revision, so its locator is the revision-pinned form.
        (source,) = [artifact()]
        (self.spec,) = mapped([source])
        self.assertEqual(self.spec.download_url, source.download_url)
        self.assertEqual(self.spec.download_url, REVISION_URL)

    def test_values_are_not_rewritten(self):
        for source in (artifact(), artifact(declared_size=0), artifact(
                declared_quantization="Unknown", declared_size=0)):
            (spec,) = mapped([source])
            self.assertEqual(spec.repository, source.repository)
            self.assertEqual(spec.filename, source.filename)
            self.assertEqual(spec.format, source.format)
            self.assertEqual(spec.quantization, source.declared_quantization)
            self.assertEqual(spec.size_bytes, source.declared_size)
            self.assertEqual(spec.sha256, source.declared_sha256)
            self.assertEqual(spec.download_url, source.download_url)
            self.assertEqual(spec.source, source.source)


class IdentityContractTests(unittest.TestCase):
    """The resolver is required, used, and never bypassed (AC3-AC6)."""

    def test_identity_resolver_is_keyword_only_and_required(self):
        with self.assertRaises(TypeError):
            map_discovered_artifacts([artifact()])  # no resolver
        with self.assertRaises(TypeError):
            map_discovered_artifacts([artifact()], RecordingResolver())

    def test_identity_resolver_must_be_callable(self):
        for not_callable in (None, "resolver", 42, object()):
            with self.assertRaises(TypeError):
                map_discovered_artifacts(
                    [artifact()], identity_resolver=not_callable
                )

    def test_resolver_receives_the_repository(self):
        resolver = RecordingResolver("resolved/model")
        (spec,) = map_discovered_artifacts(
            [artifact()], identity_resolver=resolver
        )
        self.assertEqual(resolver.calls, [REPO])
        self.assertEqual(spec.model_id, "resolved/model")

    def test_resolver_is_used_for_every_artifact(self):
        resolver = RecordingResolver()
        map_discovered_artifacts(
            [artifact(filename="a.gguf"), artifact(filename="b.gguf")],
            identity_resolver=resolver,
        )
        self.assertEqual(resolver.calls, [REPO, REPO])

    def test_resolver_is_the_only_identity_source(self):
        # A resolver that returns a different value per call is honoured
        # verbatim; nothing else can influence model_id.
        values = iter(["first", "second"])
        specs = map_discovered_artifacts(
            [artifact(filename="a.gguf"), artifact(filename="b.gguf")],
            identity_resolver=lambda repository: next(values),
        )
        self.assertEqual([spec.model_id for spec in specs], ["first", "second"])

    def test_absent_identity_raises_mapping_error(self):
        with self.assertRaises(AcquisitionMappingError):
            mapped([artifact()], identity_resolver=lambda repository: None)

    def test_unsafe_identity_raises_mapping_error(self):
        for unsafe in ("", "   ", ".", "..", "../escape", "/absolute",
                       "a/../../b"):
            with self.assertRaises(AcquisitionMappingError):
                mapped([artifact()], identity_resolver=lambda r, v=unsafe: v)

    def test_non_string_identity_raises_mapping_error(self):
        for value in (42, 1.5, object(), b"bytes", ["list"]):
            with self.assertRaises(AcquisitionMappingError):
                mapped([artifact()], identity_resolver=lambda r, v=value: v)

    def test_identity_is_never_fabricated(self):
        with self.assertRaises(AcquisitionMappingError):
            mapped([artifact()], identity_resolver=lambda repository: None)
        (spec,) = mapped([artifact()])
        self.assertIsNotNone(spec.model_id)
        self.assertNotEqual(spec.model_id, "Unknown")
        self.assertNotEqual(spec.model_id, "")
        self.assertIsInstance(spec.model_id, str)

    def test_failed_mapping_produces_no_partial_output(self):
        with self.assertRaises(AcquisitionMappingError):
            mapped(
                [artifact(filename="a.gguf"), artifact(filename="b.gguf")],
                identity_resolver=lambda repository: None,
            )

    def test_mapping_error_is_independent(self):
        self.assertTrue(issubclass(AcquisitionMappingError, Exception))
        self.assertIsNot(AcquisitionMappingError, DiscoveryError)
        self.assertFalse(issubclass(AcquisitionMappingError, DiscoveryError))


class RevisionTransportTests(unittest.TestCase):
    """B9.83 supersedes the B9.82 revision-discard contract (AC1, AC2, AC9).

    B9.82 asserted that the declared revision stopped at this boundary. That
    contract is deliberately superseded here, not silently deleted: the
    revision is now transported verbatim, while its trust level and its
    exclusion from artifact identity (OD-1) are asserted explicitly.
    """

    def test_artifact_spec_supports_an_optional_revision(self):
        self.assertIn("revision", ArtifactSpec.__dataclass_fields__)
        fields = ArtifactSpec.__dataclass_fields__["revision"]
        self.assertTrue(fields.default is None)
        # Absence must be representable as None and never fabricated.
        self.assertIsNone(
            ArtifactSpec(
                model_id="m", source="huggingface", repository=REPO,
                filename="f.gguf",
            ).revision
        )

    def test_revision_is_transported_verbatim(self):
        source = artifact(revision=REVISION)
        self.assertEqual(source.revision, REVISION)
        (spec,) = mapped([source])
        self.assertEqual(spec.revision, REVISION)
        self.assertIn("revision", {f.name for f in dataclasses.fields(spec)})

    def test_absent_revision_stays_absent(self):
        (spec,) = mapped([artifact(revision=None, download_url=URL)])
        self.assertIsNone(spec.revision)
        # Absence is never invented and never defaulted to "main".
        self.assertNotIn("main", repr(spec.revision or ""))

    def test_revision_is_never_promoted_to_content_or_integrity(self):
        (spec,) = mapped([artifact(revision=REVISION)])
        # A declared revision is not content identity and not an integrity
        # proof: content_id stays None and sha256 stays the declared value.
        self.assertIsNone(spec.content_id)
        self.assertEqual(spec.sha256, SHA)
        self.assertNotEqual(spec.revision, spec.sha256)
        self.assertIs(spec.state, ArtifactState.NOT_DOWNLOADED)

    def test_mapping_documents_the_supersession(self):
        source = module_source()
        self.assertIn("revision", source)
        self.assertIn("transported verbatim", source)
        self.assertIn("B9.82 decision 2", source)

    def test_download_url_is_preserved_and_revision_correspondent(self):
        (spec,) = mapped([artifact(revision=REVISION)])
        # The declared locator is preserved exactly; the mapper does not
        # rewrite it. It corresponds to the declared revision.
        self.assertEqual(spec.download_url, REVISION_URL)
        self.assertIn(f"/resolve/{REVISION}/", spec.download_url)

    def test_no_revision_keeps_the_unpinned_locator(self):
        (spec,) = mapped([artifact(revision=None, download_url=URL)])
        self.assertIn("/resolve/main/", spec.download_url)
        self.assertNotIn(REVISION, spec.download_url)


class OutputContractTests(unittest.TestCase):
    """State, content identity and the absence of verified claims."""

    def test_state_is_never_downloaded(self):
        for source in (artifact(), artifact(declared_size=0)):
            (spec,) = mapped([source])
            self.assertIs(spec.state, ArtifactState.NOT_DOWNLOADED)

    def test_state_is_not_promoted(self):
        (spec,) = mapped([artifact()])
        for promoted in (ArtifactState.DOWNLOADED, ArtifactState.VERIFIED,
                         ArtifactState.DOWNLOADING):
            self.assertNotEqual(spec.state, promoted)

    def test_content_id_is_always_none(self):
        for source in (artifact(), artifact(declared_sha256=SHA), artifact(
                declared_size=0, declared_sha256=None)):
            (spec,) = mapped([source])
            self.assertIsNone(spec.content_id)

    def test_content_id_is_never_computed_from_declared_data(self):
        (spec,) = mapped([artifact(declared_sha256=SHA)])
        self.assertIsNone(spec.content_id)
        self.assertNotEqual(spec.content_id, spec.sha256)
        self.assertNotEqual(spec.artifact_id, spec.sha256)

    def test_no_verified_field_is_produced(self):
        (spec,) = mapped([artifact()])
        field_names = {f.name for f in dataclasses.fields(spec)}
        for forbidden in ("verified_sha256", "verified_quantization",
                          "verified", "content_identity", "verdict",
                          "admission", "execution", "local_path"):
            self.assertNotIn(forbidden, field_names)
            self.assertFalse(hasattr(spec, forbidden))

    def test_declared_semantics_are_preserved_in_the_type(self):
        fields = ArtifactSpec.__dataclass_fields__
        self.assertIs(fields["state"].default, ArtifactState.NOT_DOWNLOADED)
        self.assertIsNone(fields["content_id"].default)
        self.assertIsNone(fields["sha256"].default)
        self.assertIsNone(fields["size_bytes"].default)
        self.assertEqual(fields["quantization"].default, "Unknown")


class PartialMetadataTests(unittest.TestCase):
    """Absent declared metadata maps to None, never to placeholders."""

    def test_all_optional_metadata_absent(self):
        source = artifact(
            download_url=None, declared_size=None, declared_sha256=None,
            revision=None,
        )
        (spec,) = mapped([source])
        self.assertIsNone(spec.download_url)
        self.assertIsNone(spec.size_bytes)
        self.assertIsNone(spec.sha256)
        self.assertIsNone(spec.content_id)

    def test_absence_is_not_replaced_by_placeholders(self):
        source = artifact(declared_size=None, declared_sha256=None)
        (spec,) = mapped([source])
        self.assertIsNone(spec.size_bytes)
        self.assertIsNone(spec.sha256)
        for spec_value in (spec.size_bytes, spec.sha256, spec.download_url):
            self.assertNotIn(spec_value, ("unknown", "Unknown", "", 0, False))

    def test_partial_metadata_still_maps_successfully(self):
        specs = mapped([
            artifact(filename="a.gguf", declared_size=None),
            artifact(filename="b.gguf", declared_sha256=None),
            artifact(filename="c.gguf", download_url=None),
        ])
        self.assertEqual(len(specs), 3)
        self.assertIsNone(specs[0].size_bytes)
        self.assertIsNone(specs[1].sha256)
        self.assertIsNone(specs[2].download_url)

    def test_optional_source_is_preserved(self):
        (spec,) = mapped([artifact(source=None)])
        self.assertIsNone(spec.source)
        self.assertEqual(spec.model_id, MODEL_ID)

    def test_repository_is_required_by_the_discovery_contract(self):
        # B9.80 requires a non-empty repository, so a declared artifact can
        # never carry None there and the mapper never has to invent one.
        with self.assertRaises(ValueError):
            artifact(repository=None)


class ProgrammingErrorTests(unittest.TestCase):
    """Programming errors keep their natural semantics (AC30)."""

    def test_non_iterable_input_raises_type_error(self):
        for value in (None, 42, object(), object()):
            with self.assertRaises(TypeError):
                mapped(value)

    def test_string_input_raises_type_error(self):
        for value in ("owner/repo", b"owner/repo", bytearray(b"x")):
            with self.assertRaises(TypeError):
                mapped(value)

    def test_a_bare_artifact_is_not_an_accepted_input(self):
        # The contract accepts a ModelVariant or an iterable of artifacts; a
        # single DiscoveredArtifact is a shape mistake, not a mapping failure.
        with self.assertRaises(TypeError):
            mapped(artifact())
        try:
            mapped(artifact())
        except AcquisitionMappingError as error:  # pragma: no cover
            self.fail(f"shape mistake reported as mapping failure: {error}")
        except TypeError:
            pass

    def test_non_discovered_elements_raise_type_error(self):
        for element in (None, 42, "a.gguf", {"filename": "a.gguf"},
                        ArtifactSpec("m", "huggingface", REPO, "a.gguf")):
            with self.assertRaises(TypeError):
                mapped([artifact(), element])

    def test_programming_errors_are_not_mapping_errors(self):
        try:
            mapped([artifact(), 42])
        except AcquisitionMappingError as error:  # pragma: no cover
            self.fail(f"programming error converted: {error}")
        except TypeError:
            pass
        else:
            self.fail("no error raised")

    def test_contract_errors_from_the_domain_are_not_swallowed(self):
        # B9.80 validation still applies: an invalid artifact is rejected
        # upstream, not by this boundary.
        with self.assertRaises(ValueError):
            artifact(filename="")


class PurityAndIsolationTests(unittest.TestCase):
    """No network, no filesystem, no persistence, no forbidden imports."""

    def test_module_imports_only_discovery_and_models(self):
        forbidden = (
            "model_identity", "downloads", "model_store", "sources",
            "main", "urllib", "requests", "socket", "http", "huggingface_hub",
            "os", "shutil", "subprocess", "sqlite3", "pickle",
        )
        for module in imported_modules():
            for bad in forbidden:
                self.assertFalse(
                    module == bad or module.startswith(bad + "."),
                    f"forbidden import: {module}",
                )

    def test_module_has_no_forbidden_references(self):
        source = module_source().lower()
        for bad in ("logical_model_id", "downloadplanner", "downloadplan",
                    "modelstore", "acquisitionplan", "urlopen", "requests",
                    "socket.", "verified_sha256", "verified_quantization"):
            self.assertNotIn(bad, source)

    def test_no_file_write_or_network_calls_in_the_module(self):
        tree = ast.parse(module_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval"})

    def test_importing_the_mapper_loads_only_the_domain_modules(self):
        script = (
            "import sys\n"
            "import castlearq.acquisition_mapping\n"
            "loaded = sorted(m for m in sys.modules if m.startswith('castlearq'))\n"
            "forbidden = [m for m in loaded if any(k in m for k in "
            "('model_identity', 'model_store', 'downloads', 'sources'))]\n"
            "assert not forbidden, forbidden\n"
            "assert 'castlearq.discovery' in loaded, loaded\n"
            "assert 'castlearq.models' in loaded, loaded\n"
            "print('ok')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_mapping_performs_no_network_filesystem_or_persistence(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("external effect attempted")

        with mock.patch("socket.socket", forbidden), \
                mock.patch("socket.create_connection", forbidden), \
                mock.patch("builtins.open", forbidden), \
                mock.patch("pathlib.Path.open", forbidden), \
                mock.patch("pathlib.Path.mkdir", forbidden), \
                mock.patch("pathlib.Path.write_bytes", forbidden), \
                mock.patch("urllib.request.urlopen", forbidden):
            specs = mapped([
                artifact(filename="a.gguf"),
                artifact(filename="b.gguf"),
            ])
        self.assertEqual(len(specs), 2)

    def test_mapping_is_deterministic(self):
        artifacts = [
            artifact(filename="a.gguf"),
            artifact(filename="b.gguf"),
        ]
        first = mapped(artifacts)
        second = mapped(artifacts)
        self.assertEqual(first, second)

    def test_planner_validations_are_not_duplicated(self):
        # The mapper accepts what discovery declared; it does not re-validate
        # URL shape, size or digest the way DownloadPlanner._validate_metadata
        # does, and it does not import the planner.
        source = module_source()
        for planner_symbol in ("DownloadPlanner", "DownloadPlan",
                               "_validate_url", "_validate_metadata"):
            self.assertNotIn(planner_symbol, source)

    def test_planner_is_not_executed_by_the_mapper(self):
        from castlearq.downloads.planner import DownloadPlanner

        with mock.patch.object(
            DownloadPlanner, "plan",
            side_effect=AssertionError("planner must not run"),
        ):
            self.assertEqual(len(mapped([artifact()])), 1)


class PlannerIntegrationTests(unittest.TestCase):
    """The mapped specs are consumable by the existing planner (AC19)."""

    def test_mapped_spec_is_accepted_by_download_planner(self):
        from castlearq.downloads.planner import DownloadPlanner, DownloadPlanStatus
        from castlearq.model_store import ModelStore

        with tempfile.TemporaryDirectory() as root:
            store = ModelStore(root=Path(root))
            (spec,) = mapped([artifact()])
            plan = DownloadPlanner(
                model_store=store, disk_usage_provider=lambda path: 10**12
            ).plan(spec)
        self.assertIn(
            plan.status,
            {DownloadPlanStatus.READY, DownloadPlanStatus.BLOCKED},
        )
        self.assertIs(plan.artifact, spec)

    def test_partial_metadata_is_reported_by_the_planner_not_invented(self):
        from castlearq.downloads.planner import DownloadPlanner, DownloadPlanStatus
        from castlearq.model_store import ModelStore

        with tempfile.TemporaryDirectory() as root:
            (spec,) = mapped([artifact(declared_size=None)])
            plan = DownloadPlanner(
                model_store=ModelStore(root=Path(root)),
                disk_usage_provider=lambda path: 10**12,
            ).plan(spec)
        self.assertIs(plan.status, DownloadPlanStatus.UNKNOWN)
        self.assertIsNone(spec.size_bytes)


if __name__ == "__main__":
    unittest.main()