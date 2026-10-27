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
"""Discovery-to-acquisition journey for repositories outside the curated catalog.

These tests exercise the ``download <owner/name>`` repository form end to end:
a GGUF repository discovered through the B9.80 port can be acquired without any
static per-repository catalog edit, while identity, selection, integrity and
admission guarantees stay intact.

Everything is deterministic and local: fake discovery transports, a local
downloader writing fixed bytes, the real offline ``DownloadPlanner`` over a
temporary ``ModelStore``, and the real identity/binding registries redirected
through their established environment overrides (using the CORRECT env names,
so no real user registry is ever touched). No Hugging Face network access
occurs, no model is downloaded for real and no inference is executed.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from castlearq import admitted_models as am
from castlearq import main as cli
from castlearq.acquisition_resolution import (
    AcquisitionBindingError,
    resolve_acquisition_locator,
    resolve_binding,
)
from castlearq.admitted_commands import ensure_discovered_repository
from castlearq.admitted_resolution import (
    AdmittedResolutionError,
    resolve_model_for_evaluation,
)
from castlearq.application_wiring import compose_acquisition_service
from castlearq.discovery import (
    DiscoveredArtifact,
    DiscoveryError,
    ModelCandidate,
    ModelVariant,
)
from castlearq.downloads.downloader import DownloadResult, DownloadResultStatus
from castlearq.downloads.planner import DownloadPlanner
from castlearq.identity_admission import (
    IdentityAdmissionError,
    lookup as admission_lookup,
    register as admission_register,
)
from castlearq.main import run_download
from castlearq.model_identity import logical_model_id, resolve_admitted_model_id
from castlearq.model_store import ModelStore
from castlearq.resolver import ModelArtifactResolutionError, ModelArtifactResolver

SRC = "huggingface"
REPO_A = "someowner/discovered-gguf-a"
REPO_B = "anotherowner/discovered-gguf-b"
REPO_EMPTY = "someowner/repo-without-gguf"
CURATED_REPO = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
CURATED_MODEL_ID = "qwen2.5-coder-7b-instruct"

#: The three established test-only registry overrides. The identity-admission
#: registry reads CASTLEARQ_IDENTITY_REGISTRY_ROOT (identity_admission.py).
ENV_ROOTS = (
    "CASTLEARQ_ADMITTED_MODELS_ROOT",
    "CASTLEARQ_IDENTITY_REGISTRY_ROOT",
    "CASTLEARQ_ACQUISITION_BINDINGS_ROOT",
)

#: Fixed local payload; 11 bytes, whose SHA-256 the fake discovery declares.
PAYLOAD = b"GGUF-fake!!"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


def _artifact(repository, filename, quantization, *, sha256=PAYLOAD_SHA256):
    return DiscoveredArtifact(
        repository=repository,
        filename=filename,
        format="GGUF",
        declared_quantization=quantization,
        model_id=None,
        source=SRC,
        download_url=f"https://huggingface.co/{repository}/resolve/main/{filename}",
        declared_size=len(PAYLOAD),
        declared_sha256=sha256,
        revision=None,
    )


def _variant(repository, quantization, *artifacts):
    return ModelVariant(
        candidate=ModelCandidate(
            provider_id=SRC, repository=repository, has_gguf=bool(artifacts)
        ),
        declared_quantization=quantization,
        artifacts=artifacts,
    )


class _FakeDiscovery:
    """A deterministic local B9.80 discovery port: no network, records calls."""

    def __init__(self, variants_by_repository=None, errors=None):
        self.variants_by_repository = variants_by_repository or {}
        self.errors = errors or {}
        self.inspect_calls = []

    def inspect(self, repository):
        self.inspect_calls.append(repository)
        if repository in self.errors:
            raise self.errors[repository]
        return tuple(self.variants_by_repository.get(repository, ()))

    def search(self, query, *, limit=20, cursor=None):  # pragma: no cover
        raise AssertionError("acquisition must never call search()")


class _LocalDownloader:
    """A deterministic local transfer: fixed bytes or an injected failure."""

    def __init__(self, failure_status=None, error=None):
        self.failure_status = failure_status
        self.error = error
        self.calls = []

    def download(self, plan):
        self.calls.append(plan)
        if self.failure_status is not None:
            return DownloadResult(
                False, self.failure_status, plan.destination, 0, self.error
            )
        destination = plan.destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(PAYLOAD)
        return DownloadResult(
            True, DownloadResultStatus.SUCCESS, destination, len(PAYLOAD)
        )


class _RegistryIsolatedTestCase(unittest.TestCase):
    """Shared setup: temporary store and the three registries redirected."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._previous = {key: os.environ.get(key) for key in ENV_ROOTS}
        for key in ENV_ROOTS:
            os.environ[key] = str(Path(self.tmp.name) / key.lower())
        self.addCleanup(self._restore_env)
        self.store = ModelStore(Path(self.tmp.name) / "store")

    def _restore_env(self):
        for key, previous in self._previous.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def _service(self, discovery, downloader=None):
        """Compose through the REAL production composition root."""
        downloader = downloader if downloader is not None else _LocalDownloader()
        service = compose_acquisition_service(
            discovery_provider=discovery,
            model_store=self.store,
            planner_factory=lambda: DownloadPlanner(model_store=self.store),
            downloader_factory=lambda _store: downloader,
        )
        return service, downloader

    def _run(self, target, discovery, downloader=None, **kwargs):
        service, downloader = self._service(discovery, downloader)
        out, err = io.StringIO(), io.StringIO()
        code = run_download(target, service=service, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue(), downloader


class DiscoveredRepositoryAcquisitionTests(_RegistryIsolatedTestCase):
    """The full journey for a GGUF repository outside the curated catalog."""

    def test_discovered_repository_acquires_without_static_mapping(self):
        # The static curated catalog knows nothing about this repository...
        self.assertIsNone(logical_model_id(SRC, REPO_A))
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        code, out, err, _ = self._run(REPO_A, _FakeDiscovery({REPO_A: variants}))

        # ...and it still acquires, through the derived admitted identity.
        mid = resolve_admitted_model_id(SRC, REPO_A)
        self.assertEqual(code, 0, err)
        self.assertIn(f"Repository: {REPO_A}", out)
        self.assertIn(f"Resolved model: {mid}", out)
        self.assertIn("Download complete.", out)
        self.assertIn("SHA-256 verified.", out)
        self.assertIn("Registered manifest:", out)

        # The identity stays derived: the curated table is never edited.
        self.assertIsNone(logical_model_id(SRC, REPO_A))

        # The explicit registries now carry the locator<->identity binding.
        self.assertEqual(admission_lookup(SRC, REPO_A), mid)
        self.assertEqual(resolve_binding(mid), (SRC, REPO_A))
        self.assertEqual(resolve_acquisition_locator(mid), (SRC, REPO_A))

        # The artifact is registered in the store under the logical identity.
        (entry,) = self.store.list_artifacts()
        self.assertEqual(entry.artifact.model_id, mid)
        self.assertEqual(entry.artifact.repository, REPO_A)
        self.assertEqual(entry.artifact.filename, "dis-a-q4_k_m.gguf")
        self.assertEqual(entry.artifact.quantization, "Q4_K_M")
        self.assertEqual(entry.state.value, "downloaded")

    def test_explicit_quantization_and_filename_select_the_exact_artifact(self):
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
            _variant(REPO_A, "Q5_K_M", _artifact(REPO_A, "dis-a-q5_k_m.gguf", "Q5_K_M")),
        )
        code, out, err, _ = self._run(
            REPO_A,
            _FakeDiscovery({REPO_A: variants}),
            # Quantization matching is case-insensitive (B9.84); filename is
            # exact. Both selectors must lead to the very same artifact.
            quantization="q5_k_m",
            filename="dis-a-q5_k_m.gguf",
        )
        self.assertEqual(code, 0, err)
        (entry,) = self.store.list_artifacts()
        self.assertEqual(entry.artifact.filename, "dis-a-q5_k_m.gguf")
        self.assertEqual(entry.artifact.quantization, "Q5_K_M")
        self.assertIn("Artifact: dis-a-q5_k_m.gguf", out)

    def test_two_repositories_do_not_collide_in_identity_or_storage(self):
        variants_a = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        variants_b = (
            _variant(REPO_B, "Q4_K_M", _artifact(REPO_B, "dis-b-q4_k_m.gguf", "Q4_K_M")),
        )
        discovery = _FakeDiscovery({REPO_A: variants_a, REPO_B: variants_b})

        code_a, _, err_a, _ = self._run(REPO_A, discovery)
        code_b, _, err_b, _ = self._run(REPO_B, discovery)
        self.assertEqual(code_a, 0, err_a)
        self.assertEqual(code_b, 0, err_b)

        mid_a = resolve_admitted_model_id(SRC, REPO_A)
        mid_b = resolve_admitted_model_id(SRC, REPO_B)
        self.assertNotEqual(mid_a, mid_b)
        self.assertEqual(resolve_binding(mid_a), (SRC, REPO_A))
        self.assertEqual(resolve_binding(mid_b), (SRC, REPO_B))
        self.assertEqual(admission_lookup(SRC, REPO_A), mid_a)
        self.assertEqual(admission_lookup(SRC, REPO_B), mid_b)

        entries = self.store.list_artifacts()
        self.assertEqual(len(entries), 2)
        by_model = {entry.artifact.model_id: entry for entry in entries}
        self.assertEqual(set(by_model), {mid_a, mid_b})
        self.assertEqual(by_model[mid_a].artifact.filename, "dis-a-q4_k_m.gguf")
        self.assertEqual(by_model[mid_b].artifact.filename, "dis-b-q4_k_m.gguf")
        directories = {self.store.artifact_directory(e.artifact) for e in entries}
        self.assertEqual(len(directories), 2)

    def test_repository_without_selectable_gguf_artifacts_fails_clearly(self):
        code, out, err, downloader = self._run(
            REPO_EMPTY, _FakeDiscovery({REPO_EMPTY: ()}), quantization="Q4_K_M"
        )
        self.assertEqual(code, 1)
        self.assertIn("No GGUF artifacts found.", out)
        self.assertIn("Download error:", err)
        self.assertEqual(downloader.calls, [])
        self.assertEqual(self.store.list_artifacts(), [])

    def test_missing_or_ambiguous_selection_is_rejected(self):
        variants = (
            _variant(
                REPO_A,
                "Q4_K_M",
                _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M"),
                _artifact(REPO_A, "dis-a-q4_k_m-00001-of-00002.gguf", "Q4_K_M"),
            ),
        )
        discovery = _FakeDiscovery({REPO_A: variants})

        # Ambiguity: multiple artifacts, no selector. Never a silent first pick.
        code, out, err, downloader = self._run(REPO_A, discovery)
        self.assertEqual(code, 1)
        self.assertIn("Download error:", err)
        self.assertIn("multiple discovered artifacts", err.lower())
        # Candidates are presented so the user can refine the selection.
        self.assertIn("dis-a-q4_k_m.gguf", out)
        self.assertEqual(downloader.calls, [])
        self.assertEqual(self.store.list_artifacts(), [])

        # A selector that matches nothing is an explicit failure.
        code, out, err, downloader = self._run(REPO_A, discovery, quantization="Q8_XL")
        self.assertEqual(code, 1)
        self.assertIn("No discovered artifact matches quantization", err)
        self.assertEqual(downloader.calls, [])
        self.assertEqual(self.store.list_artifacts(), [])

    def test_discovery_and_download_errors_propagate_via_existing_contracts(self):
        # Discovery failure -> AcquisitionError(DISCOVERY_FAILED) -> exit 1.
        broken = _FakeDiscovery(errors={REPO_A: DiscoveryError("metadata exploded")})
        code, out, err, downloader = self._run(REPO_A, broken)
        self.assertEqual(code, 1)
        self.assertIn("Download error:", err)
        self.assertIn("metadata exploded", err)
        self.assertEqual(downloader.calls, [])

        # Transfer failure -> FAILED outcome with the downloader status.
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        failing = _LocalDownloader(
            failure_status=DownloadResultStatus.NETWORK_ERROR, error="boom"
        )
        code, out, err, _ = self._run(REPO_A, _FakeDiscovery({REPO_A: variants}), failing)
        self.assertEqual(code, 1)
        self.assertIn("boom", err)
        self.assertNotIn("Download complete.", out)
        self.assertEqual(self.store.list_artifacts(), [])

    def test_failed_verification_leaves_nothing_registered_as_verified(self):
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        mismatch = _LocalDownloader(
            failure_status=DownloadResultStatus.CHECKSUM_MISMATCH, error="bad sha"
        )
        code, out, err, _ = self._run(REPO_A, _FakeDiscovery({REPO_A: variants}), mismatch)
        self.assertEqual(code, 1)
        self.assertIn("SHA-256", err)
        self.assertNotIn("Download complete.", out)
        self.assertNotIn("SHA-256 verified.", out)
        self.assertNotIn("Registered manifest:", out)
        # The failed artifact is never registered in the store.
        self.assertEqual(self.store.list_artifacts(), [])

    def test_acquired_artifact_integrates_with_existing_mechanisms(self):
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        code, _, err, _ = self._run(REPO_A, _FakeDiscovery({REPO_A: variants}))
        self.assertEqual(code, 0, err)
        mid = resolve_admitted_model_id(SRC, REPO_A)

        # Listing reports the stored artifact with a derived local state.
        (entry,) = self.store.list_artifacts()
        self.assertEqual(entry.state.value, "downloaded")

        # Resolution for execution stays fail-closed until the model is
        # explicitly described (the existing admission gate is not weakened).
        with self.assertRaises(ModelArtifactResolutionError):
            ModelArtifactResolver(model_store=self.store).resolve(mid)

        am.describe(
            mid,
            SRC,
            REPO_A,
            filename="dis-a-q4_k_m.gguf",
            quantization="Q4_K_M",
            architecture="llama",
            format="GGUF",
        )
        resolved = ModelArtifactResolver(model_store=self.store).resolve(mid)
        self.assertEqual(resolved.model.model_id, mid)
        self.assertEqual(resolved.artifact.filename, "dis-a-q4_k_m.gguf")
        self.assertIsNotNone(resolved.path)

    def test_acquisition_never_admits_a_model_for_execution(self):
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        code, _, err, _ = self._run(REPO_A, _FakeDiscovery({REPO_A: variants}))
        self.assertEqual(code, 0, err)
        mid = resolve_admitted_model_id(SRC, REPO_A)

        # Acquiring creates NO Executable Model Description and no evaluation
        # admission: compatibility/evaluation/execution stay closed until the
        # owner describes and evaluates the model explicitly.
        self.assertIsNone(am.resolve(mid))
        with self.assertRaises(AdmittedResolutionError):
            resolve_model_for_evaluation(mid)
        with self.assertRaises(ModelArtifactResolutionError):
            ModelArtifactResolver(model_store=self.store).resolve(mid)


class KnownIdentityDownloadTests(_RegistryIsolatedTestCase):
    """The pre-existing model-id form keeps its exact behaviour."""

    def test_model_id_form_for_known_identity_is_unchanged(self):
        curated_variants = (
            _variant(
                CURATED_REPO,
                "Q4_K_M",
                _artifact(CURATED_REPO, "curated-q4_k_m.gguf", "Q4_K_M"),
            ),
        )
        discovery = _FakeDiscovery({CURATED_REPO: curated_variants})
        code, out, err, _ = self._run(CURATED_MODEL_ID, discovery)

        self.assertEqual(code, 0, err)
        self.assertIn(f"Model: {CURATED_MODEL_ID}", out)
        self.assertNotIn("Resolved model:", out)
        # No registry state is created for the model-id form.
        self.assertIsNone(resolve_binding(CURATED_MODEL_ID))
        self.assertIsNone(admission_lookup(SRC, CURATED_REPO))
        (entry,) = self.store.list_artifacts()
        self.assertEqual(entry.artifact.model_id, CURATED_MODEL_ID)

    def test_unknown_model_id_without_repository_form_is_still_rejected(self):
        code, out, err, downloader = self._run("unknown-model", _FakeDiscovery())
        self.assertEqual(code, 1)
        self.assertIn("no unique source repository", err)
        self.assertEqual(downloader.calls, [])


class CliDispatchTests(_RegistryIsolatedTestCase):
    """The real CLI dispatch accepts the repository form of ``download``."""

    def test_download_command_forwards_repository_and_selectors(self):
        variants = (
            _variant(REPO_A, "Q4_K_M", _artifact(REPO_A, "dis-a-q4_k_m.gguf", "Q4_K_M")),
        )
        service, _ = self._service(_FakeDiscovery({REPO_A: variants}))
        out, err = io.StringIO(), io.StringIO()
        argv = ["castlearq", "download", REPO_A, "--quantization", "Q4_K_M"]
        with mock.patch.object(cli, "compose_acquisition_service", return_value=service):
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main()

        self.assertEqual(code, 0, err.getvalue())
        text = out.getvalue()
        self.assertIn(f"Repository: {REPO_A}", text)
        self.assertIn(f"Resolved model: {resolve_admitted_model_id(SRC, REPO_A)}", text)
        self.assertIn("Download complete.", text)
        (entry,) = self.store.list_artifacts()
        self.assertEqual(entry.artifact.filename, "dis-a-q4_k_m.gguf")
        self.assertEqual(entry.artifact.quantization, "Q4_K_M")


class EnsureDiscoveredRepositoryTests(_RegistryIsolatedTestCase):
    """The registration helper: idempotent, fail-closed, validation-first."""

    def test_repeated_registration_is_idempotent(self):
        mid = ensure_discovered_repository(SRC, REPO_A)
        self.assertEqual(ensure_discovered_repository(SRC, REPO_A), mid)
        self.assertEqual(admission_lookup(SRC, REPO_A), mid)
        self.assertEqual(resolve_binding(mid), (SRC, REPO_A))

    def test_invalid_repository_shape_is_rejected(self):
        for bad in ("owner", "owner/repo/extra", "owner repo/name", "", "/name", "owner/"):
            with self.subTest(repository=bad):
                with self.assertRaises(ValueError):
                    ensure_discovered_repository(SRC, bad)

    def test_unsupported_source_is_rejected_before_any_write(self):
        with self.assertRaises(AcquisitionBindingError):
            ensure_discovered_repository("not-a-provider", "owner/repo")
        self.assertIsNone(admission_lookup("not-a-provider", "owner/repo"))
        self.assertIsNone(
            resolve_binding(resolve_admitted_model_id("not-a-provider", "owner/repo"))
        )

    def test_conflicting_admitted_identity_fails_closed(self):
        admission_register(SRC, REPO_A, "some-other-identity")
        with self.assertRaises(IdentityAdmissionError):
            ensure_discovered_repository(SRC, REPO_A)
        # Nothing changed: the earlier identity stays authoritative and no
        # acquisition binding was created for the rejected proposal.
        self.assertEqual(admission_lookup(SRC, REPO_A), "some-other-identity")
        self.assertIsNone(resolve_binding("some-other-identity"))
        self.assertIsNone(resolve_binding(resolve_admitted_model_id(SRC, REPO_A)))


if __name__ == "__main__":
    unittest.main()
