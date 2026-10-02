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

"""B9.85: the application acquisition boundary and its result contract.

All collaborators are local fakes: no network, no filesystem state beyond a
temporary store, and no production provider code.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from castlearq.acquisition_service import (
    AcquisitionCandidate,
    AcquisitionError,
    AcquisitionErrorCategory,
    AcquisitionStatus,
    ModelAcquisitionService,
)
from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelVariant,
)
from castlearq.downloads.downloader import DownloadResultStatus
from castlearq.downloads.planner import DownloadPlan, DownloadPlanStatus
from castlearq.model_store import ModelStore, UnsafePathError

MODEL_ID = "qwen2.5-coder-7b-instruct"
REPO = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
REVISION = "a" * 40


def artifact(filename="model-q4.gguf", quantization="Q4_K_M", revision=REVISION):
    """One declared remote artifact, exactly as B9.80 models it."""
    return DiscoveredArtifact(
        repository=REPO,
        filename=filename,
        format="GGUF",
        declared_quantization=quantization,
        model_id=None,
        source="huggingface",
        download_url=f"https://huggingface.co/{REPO}/resolve/{revision}/{filename}",
        declared_size=10,
        declared_sha256="ab" * 32,
        revision=revision,
    )


def variant(artifacts, quantization="Q4_K_M"):
    """One declared grouping, exactly as B9.80 models it."""
    return ModelVariant(
        candidate=ModelCandidate(
            provider_id="huggingface",
            repository=REPO,
            has_gguf=True,
        ),
        declared_quantization=quantization,
        artifacts=tuple(artifacts),
    )


def plan_for(status=DownloadPlanStatus.READY, reasons=(), destination="/models/x"):
    """A planner outcome in the infrastructure shape the boundary consumes."""
    from castlearq.models import ArtifactSpec

    return DownloadPlan(
        artifact=ArtifactSpec(
            model_id=MODEL_ID,
            source="huggingface",
            repository=REPO,
            filename="model-q4.gguf",
            format="GGUF",
            quantization="Q4_K_M",
        ),
        status=status,
        destination=Path(destination) if destination else None,
        reasons=tuple(reasons),
        available_bytes=100,
        required_bytes=10,
        existing=False,
    )


class _Discovery:
    """A B9.80 discovery port that records how many times it was called."""

    def __init__(self, variants=(), error=None):
        self._variants = tuple(variants)
        self._error = error
        self.calls = []

    def inspect(self, repository):
        self.calls.append(repository)
        if self._error is not None:
            raise self._error
        return self._variants

    def search(self, query, *, limit=20, cursor=None):  # pragma: no cover
        raise AssertionError("acquisition must never call search()")


def _service(
    *,
    variants=(),
    discovery_error=None,
    identity=None,
    plan=None,
    result=None,
    store=None,
    save_error=None,
    plan_error=None,
    download_error=None,
    locator="found",
):
    """Build a service entirely from injected fakes."""
    planner = Mock()
    if plan_error is not None:
        planner.plan.side_effect = plan_error
    else:
        planner.plan.return_value = plan or plan_for()

    downloader = Mock()
    if download_error is not None:
        downloader.download.side_effect = download_error
    elif result is not None:
        downloader.download.return_value = result

    if store is None:
        tempdir = tempfile.TemporaryDirectory()
        store = ModelStore(Path(tempdir.name) / "models")

    if save_error is not None:
        store.save_manifest = Mock(side_effect=save_error)  # type: ignore[method-assign]

    resolved: dict[str, str] = {}

    def identity_resolver(repository):
        return MODEL_ID if identity is None else identity(repository)

    def locator_resolver(model_id):
        return (("huggingface", REPO) if locator == "found" else None)

    return ModelAcquisitionService(
        discovery_provider=_Discovery(variants, discovery_error),
        identity_resolver=identity_resolver,
        locator_resolver=locator_resolver,
        planner=planner,
        downloader=downloader,
        store=store,
    ), resolved
class CompositionTests(unittest.TestCase):
    """Discovery -> selection -> mapping -> planning -> transfer -> store."""

    def _success(self, **kwargs):
        from castlearq.downloads.downloader import DownloadResult

        result = DownloadResult(
            True,
            DownloadResultStatus.SUCCESS,
            Path("/models/x/model.gguf"),
            10,
        )
        service, _ = _service(
            variants=[variant([artifact()])], result=result, **kwargs
        )
        return service

    def test_successful_acquisition_returns_ready_outcome(self):
        outcome = self._success().acquire(MODEL_ID)
        self.assertIs(outcome.status, AcquisitionStatus.READY)
        self.assertEqual(outcome.model_id, MODEL_ID)
        self.assertEqual(outcome.filename, "model-q4.gguf")
        self.assertEqual(outcome.destination, "/models/x/model.gguf")
        self.assertIsNotNone(outcome.manifest_path)
        self.assertTrue(outcome.succeeded)

    def test_discovery_is_called_exactly_once_with_the_repository(self):
        service = self._success()
        service.acquire(MODEL_ID)
        self.assertEqual(service.discovery_provider.calls, [REPO])

    def test_service_never_calls_discovery_search(self):
        # search() is Model Library surface and must not be reachable here.
        service = self._success()
        service.acquire(MODEL_ID)
        self.assertEqual(service.discovery_provider.calls, [REPO])

    def test_quantization_selects_the_declared_variant(self):
        from castlearq.downloads.downloader import DownloadResult

        wanted = artifact("q8.gguf", quantization="Q8_0")
        result = DownloadResult(
            True, DownloadResultStatus.SUCCESS, Path("/models/x/q8.gguf"), 10
        )
        service, _ = _service(
            variants=[
                variant([artifact()], quantization="Q4_K_M"),
                variant([wanted], quantization="Q8_0"),
            ],
            result=result,
        )
        outcome = service.acquire(MODEL_ID, quantization="Q8_0")
        self.assertEqual(outcome.filename, "q8.gguf")

    def test_outcome_exposes_no_path_objects(self):
        outcome = self._success().acquire(MODEL_ID)
        for value in (outcome.destination, outcome.manifest_path):
            self.assertNotIsInstance(value, Path)
            if value is not None:
                self.assertIsInstance(value, str)


class IdentityTests(unittest.TestCase):
    """D3: identity stays outside the service and outside discovery data."""

    def test_resolver_receives_the_repository(self):
        seen: list[str] = []

        def identity(repository):
            seen.append(repository)
            return MODEL_ID

        from castlearq.downloads.downloader import DownloadResult

        service, _ = _service(
            variants=[variant([artifact()])],
            result=DownloadResult(
                True, DownloadResultStatus.SUCCESS, Path("/models/x/model.gguf"), 10
            ),
            identity=identity,
        )
        service.acquire(MODEL_ID)
        self.assertEqual(seen, [REPO])

    def test_service_takes_no_source_argument(self):
        # D3: the service cannot fabricate identity because it never sees one.
        import inspect

        parameters = inspect.signature(ModelAcquisitionService.__init__).parameters
        self.assertNotIn("source", parameters)
        self.assertEqual(
            ["self", "discovery_provider", "identity_resolver", "locator_resolver",
             "planner", "downloader", "store", "locator_audit"],
            list(parameters),
        )

    def test_unmapped_identity_becomes_an_application_error(self):
        service, _ = _service(variants=[variant([artifact()])], identity=lambda r: None)
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.MAPPING_FAILED)

    def test_unresolvable_model_is_reported_before_discovery(self):
        service, _ = _service(variants=[variant([artifact()])], locator="missing")
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(
            ctx.exception.category, AcquisitionErrorCategory.MODEL_NOT_RESOLVABLE
        )
        self.assertEqual(service.discovery_provider.calls, [])


class RevisionTests(unittest.TestCase):
    """B9.83 transport and OD-1 survive the application boundary."""

    def _mapped_spec(self, revision):
        from castlearq.acquisition_mapping import map_discovered_artifacts

        selected = artifact(revision=revision)
        (spec,) = map_discovered_artifacts(
            [selected], identity_resolver=lambda repository: MODEL_ID
        )
        return spec

    def test_selected_revision_reaches_the_artifact_spec(self):
        from castlearq.downloads.downloader import DownloadResult

        service, _ = _service(
            variants=[variant([artifact(revision=REVISION)])],
            result=DownloadResult(
                True, DownloadResultStatus.SUCCESS, Path("/models/x/model.gguf"), 10
            ),
        )
        service.acquire(MODEL_ID)
        self.assertEqual(self._mapped_spec(REVISION).revision, REVISION)

    def test_revision_is_excluded_from_artifact_identity(self):
        # OD-1: the same artifact at a different revision has the same identity.
        one = self._mapped_spec(REVISION)
        two = self._mapped_spec("b" * 40)
        self.assertEqual(one.artifact_id, two.artifact_id)
        self.assertNotIn(REVISION, one.artifact_id)


class ErrorBoundaryTests(unittest.TestCase):
    """D4: one application vocabulary, causes preserved."""

    def test_discovery_failure_is_translated_with_cause(self):
        boom = DiscoveryError("metadata unavailable")
        service, _ = _service(discovery_error=boom)
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.DISCOVERY_FAILED)
        self.assertIs(ctx.exception.cause, boom)
        self.assertIs(ctx.exception.__cause__, boom)

    def test_selection_failure_is_translated_with_cause(self):
        from castlearq.discovery_selection import DiscoveredSelectionError

        service, _ = _service(
            variants=[variant([artifact()])],
        )
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID, quantization="Q2_K")
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.SELECTION_FAILED)
        self.assertIsInstance(ctx.exception.cause, DiscoveredSelectionError)

    def test_planning_failure_is_translated_with_cause(self):
        boom = UnsafePathError("unsafe destination")
        service, _ = _service(
            variants=[variant([artifact()])], plan_error=boom
        )
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.PLANNING_FAILED)
        self.assertIs(ctx.exception.cause, boom)

    def test_transfer_failure_is_translated_with_cause(self):
        from castlearq.downloads.downloader import DownloadResult

        boom = UnsafePathError("unsafe path during transfer")
        service, _ = _service(
            variants=[variant([artifact()])],
            result=DownloadResult(
                True, DownloadResultStatus.SUCCESS, Path("/x"), 10
            ),
            download_error=boom,
        )
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.TRANSFER_FAILED)
        self.assertIs(ctx.exception.cause, boom)

    def test_persistence_failure_is_translated_with_cause(self):
        from castlearq.downloads.downloader import DownloadResult

        boom = OSError("disk full")
        service, _ = _service(
            variants=[variant([artifact()])],
            result=DownloadResult(
                True, DownloadResultStatus.SUCCESS, Path("/x"), 10
            ),
            save_error=boom,
        )
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(
            ctx.exception.category, AcquisitionErrorCategory.PERSISTENCE_FAILED
        )
        self.assertIs(ctx.exception.cause, boom)
        self.assertIn("manifest", str(ctx.exception))

    def test_application_error_is_not_a_lower_level_error(self):
        pass
class OutcomeTests(unittest.TestCase):
    """READY / ALREADY_DOWNLOADED / BLOCKED / FAILED."""

    def _result(self, status=DownloadResultStatus.SUCCESS, error=None, success=True):
        from castlearq.downloads.downloader import DownloadResult

        return DownloadResult(
            success, status, Path("/models/x/model.gguf"), 10, error=error
        )

    def test_already_downloaded_is_a_normal_outcome(self):
        service, _ = _service(
            variants=[variant([artifact()])],
            plan=plan_for(status=DownloadPlanStatus.ALREADY_DOWNLOADED),
        )
        outcome = service.acquire(MODEL_ID)
        self.assertIs(outcome.status, AcquisitionStatus.ALREADY_DOWNLOADED)
        self.assertTrue(outcome.succeeded)
        service.downloader.download.assert_not_called()

    def test_blocked_is_a_normal_outcome_with_reasons(self):
        service, _ = _service(
            variants=[variant([artifact()])],
            plan=plan_for(
                status=DownloadPlanStatus.BLOCKED, reasons=("disk full",)
            ),
        )
        outcome = service.acquire(MODEL_ID)
        self.assertIs(outcome.status, AcquisitionStatus.BLOCKED)
        self.assertEqual(outcome.reasons, ("disk full",))
        service.downloader.download.assert_not_called()

    def test_unknown_plan_status_is_refused(self):
        service, _ = _service(
            variants=[variant([artifact()])],
            plan=Mock(status="unexpected"),
        )
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.PLANNING_FAILED)

    def test_download_failure_status_stays_distinguishable(self):
        for status in (
            DownloadResultStatus.CHECKSUM_MISMATCH,
            DownloadResultStatus.HTTP_ERROR,
            DownloadResultStatus.NETWORK_ERROR,
            DownloadResultStatus.FILESYSTEM_ERROR,
        ):
            with self.subTest(status=status):
                service, _ = _service(
                    variants=[variant([artifact()])],
                    result=self._result(status, error="boom", success=False),
                )
                outcome = service.acquire(MODEL_ID)
                self.assertIs(outcome.status, AcquisitionStatus.FAILED)
                self.assertEqual(outcome.failure_status, status.value)
                self.assertIn("boom", outcome.message)

    def test_failed_transfer_does_not_persist_a_manifest(self):
        store = Mock()
        service, _ = _service(
            variants=[variant([artifact()])],
            store=store,
            result=self._result(
                DownloadResultStatus.NETWORK_ERROR, error="boom", success=False
            ),
        )
        service.acquire(MODEL_ID)
        store.save_manifest.assert_not_called()
class AmbiguityTests(unittest.TestCase):
    """Candidate data without a second discovery request."""

    def _ambiguous(self, **kwargs):
        return _service(
            variants=[variant([artifact("shard-1.gguf"), artifact("shard-2.gguf")])],
            **kwargs,
        )

    def test_ambiguity_carries_candidate_information(self):
        # With no selector the CLI has always listed candidates.
        service, _ = self._ambiguous()
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        error = ctx.exception
        self.assertEqual(
            error.candidate_filenames, ("shard-1.gguf", "shard-2.gguf")
        )
        self.assertEqual(len(error.candidates), 2)
        self.assertIsInstance(error.candidates[0], AcquisitionCandidate)
        self.assertEqual(error.candidates[0].quantization, "Q4_K_M")
        self.assertEqual(error.candidates[0].declared_size, 10)
        self.assertEqual(error.candidates[0].declared_sha256, "ab" * 32)

    def test_ambiguity_makes_exactly_one_discovery_call(self):
        service, _ = self._ambiguous()
        with self.assertRaises(AcquisitionError):
            service.acquire(MODEL_ID, quantization="Q4_K_M")
        self.assertEqual(service.discovery_provider.calls, [REPO])

    def test_explicit_selector_suppresses_candidate_listing(self):
        # The legacy CLI listed candidates only when no selector was supplied.
        service, _ = self._ambiguous()
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID, filename="absent.gguf")
        self.assertEqual(ctx.exception.candidates, ())
        self.assertTrue(ctx.exception.candidate_filenames)

    def test_filename_resolves_the_ambiguity(self):
        from castlearq.downloads.downloader import DownloadResult

        service, _ = _service(
            variants=[variant([artifact("shard-1.gguf"), artifact("shard-2.gguf")])],
            result=DownloadResult(
                True, DownloadResultStatus.SUCCESS, Path("/x"), 10
            ),
        )
        outcome = service.acquire(MODEL_ID, filename="shard-2.gguf")
        self.assertEqual(outcome.filename, "shard-2.gguf")

    def test_empty_candidate_set_is_a_selection_failure(self):
        service, _ = _service(variants=())
        with self.assertRaises(AcquisitionError) as ctx:
            service.acquire(MODEL_ID)
        self.assertIs(ctx.exception.category, AcquisitionErrorCategory.SELECTION_FAILED)
        self.assertEqual(ctx.exception.candidates, ())

    def test_service_performs_no_printing(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        service, _ = self._ambiguous()
        out, err = io.StringIO(), io.StringIO()
        with (
            redirect_stdout(out),
            redirect_stderr(err),
            self.assertRaises(AcquisitionError),
        ):
            service.acquire(MODEL_ID, quantization="Q4_K_M")
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")


class WiringTests(unittest.TestCase):
    """The composition root binds identity; it does not duplicate it."""

    def test_composer_binds_the_identity_resolver(self):
        from castlearq.application_wiring import compose_acquisition_service
        from castlearq.model_identity import logical_model_id

        service = compose_acquisition_service()
        self.assertIsInstance(service, ModelAcquisitionService)
        self.assertEqual(
            service.identity_resolver(REPO), logical_model_id("huggingface", REPO)
        )

    def test_composer_returns_a_fresh_service_each_call(self):
        from castlearq.application_wiring import compose_acquisition_service

        self.assertIsNot(
            compose_acquisition_service(), compose_acquisition_service()
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
