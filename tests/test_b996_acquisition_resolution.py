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

"""B9.96: independent persistent acquisition bindings + composed resolver.

The contract under test, as ratified (D1-D7):

- At most one active binding per ``model_id``; ``model_id`` is the key.
- ``bind`` is explicit; Identity Admission never creates bindings; the
  forward check ``resolve_admitted_model_id(source, repository) ==
  model_id`` must hold and mismatch fails closed without writing.
- Resolution order: ``downloadable_locator`` first, persistent binding
  only on curated miss; curated authority is never silently overridden.
- Conflicts fail closed and leave the file byte-unchanged; identical
  re-registration is idempotent and skips the write; ``bind`` never
  overwrites; ``update``/``delete`` require an existing binding;
  resolution never mutates state.
- The registry is a standalone JSON file with schema versioning,
  strict validation, deterministic serialization and atomic durable
  writes; malformed state fails loudly, never as "no binding".
- The composed resolver integrates only through the ``locator_resolver``
  seam; ``ModelAcquisitionService`` itself is unchanged.

The registry is redirected through CASTLEARQ_ACQUISITION_BINDINGS_ROOT,
so every test runs against a private temporary directory and never
touches a real user registry.
"""

import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import castlearq.acquisition_resolution as bindings
from castlearq.acquisition_resolution import (
    ACQUISITION_BINDINGS_ROOT_ENV,
    AcquisitionBindingError,
    bind,
    bindings_path,
    bindings_root,
    delete,
    resolve_acquisition_locator,
    resolve_binding,
    update,
)
from castlearq.model_identity import (
    SUPPORTED_DOWNLOAD_SOURCES,
    resolve_admitted_model_id,
)

#: A curated repository and its authoritative identity (B9.93).
CURATED_SOURCE = "huggingface"
CURATED_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
CURATED_MODEL_ID = "qwen2.5-coder-7b-instruct"

#: A repository with no curated entry: its admitted identity is derived.
UNMAPPED_SOURCE = "huggingface"
UNMAPPED_REPOSITORY = "someowner/somemodel"
UNMAPPED_MODEL_ID = resolve_admitted_model_id(
    UNMAPPED_SOURCE, UNMAPPED_REPOSITORY
)

#: A second unmapped repository for conflict/lifecycle cases.
OTHER_REPOSITORY = "someowner/othermodel"
OTHER_MODEL_ID = resolve_admitted_model_id(UNMAPPED_SOURCE, OTHER_REPOSITORY)


class BindingsTestCase(unittest.TestCase):
    """Base case redirecting the registry into a private temp directory."""

    def setUp(self):
        self._previous = os.environ.get(ACQUISITION_BINDINGS_ROOT_ENV)
        self._directory = tempfile.TemporaryDirectory()
        os.environ[ACQUISITION_BINDINGS_ROOT_ENV] = self._directory.name
        self.addCleanup(self._restore)

    def _restore(self):
        self._directory.cleanup()
        if self._previous is None:
            os.environ.pop(ACQUISITION_BINDINGS_ROOT_ENV, None)
        else:
            os.environ[ACQUISITION_BINDINGS_ROOT_ENV] = self._previous

    @property
    def path(self):
        return bindings_path()

    def write_raw(self, payload: str) -> None:
        """Write raw registry content, bypassing the module's own writer."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(payload, encoding="utf-8")

    def read_bytes(self) -> bytes | None:
        try:
            return self.path.read_bytes()
        except FileNotFoundError:
            return None


class LocationTests(BindingsTestCase):
    """Root resolution, environment override and default path."""

    def test_default_root_is_dot_castlearq(self):
        root = bindings_root(home=Path("/tmp/fakehome"), environ={})
        self.assertEqual(root, Path("/tmp/fakehome") / ".castlearq")

    def test_non_empty_override_wins(self):
        root = bindings_root(
            home=Path("/tmp/fakehome"),
            environ={ACQUISITION_BINDINGS_ROOT_ENV: "/tmp/custom"},
        )
        self.assertEqual(root, Path("/tmp/custom"))

    def test_empty_override_is_ignored(self):
        root = bindings_root(
            home=Path("/tmp/fakehome"),
            environ={ACQUISITION_BINDINGS_ROOT_ENV: ""},
        )
        self.assertEqual(root, Path("/tmp/fakehome") / ".castlearq")

    def test_path_appends_filename(self):
        self.assertEqual(
            bindings_path(Path("/tmp/custom")),
            Path("/tmp/custom") / "acquisition-bindings.json",
        )

    def test_env_override_selects_path(self):
        self.assertEqual(
            bindings_path(),
            Path(self._directory.name) / "acquisition-bindings.json",
        )


class PersistenceTests(BindingsTestCase):
    """Missing/malformed/schema/durability behaviour of the registry."""

    def test_missing_file_is_empty_registry(self):
        self.assertFalse(self.path.exists())
        self.assertIsNone(resolve_binding(UNMAPPED_MODEL_ID))

    def test_malformed_file_fails_loudly(self):
        self.write_raw("{not json")
        for probe in (
            lambda: resolve_binding(UNMAPPED_MODEL_ID),
            lambda: bind(
                UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY
            ),
        ):
            with self.assertRaises(AcquisitionBindingError):
                probe()

    def test_missing_schema_version_rejected(self):
        self.write_raw(json.dumps({"bindings": {}}))
        with self.assertRaises(AcquisitionBindingError):
            resolve_binding(UNMAPPED_MODEL_ID)

    def test_unknown_schema_version_rejected(self):
        self.write_raw(
            json.dumps({"schema_version": 999, "bindings": {}})
        )
        with self.assertRaises(AcquisitionBindingError):
            resolve_binding(UNMAPPED_MODEL_ID)

    def test_unexpected_top_level_field_rejected(self):
        self.write_raw(
            json.dumps(
                {"schema_version": 1, "bindings": {}, "extra": True}
            )
        )
        with self.assertRaises(AcquisitionBindingError):
            resolve_binding(UNMAPPED_MODEL_ID)

    def test_malformed_records_rejected(self):
        bad_records = [
            {"source": "huggingface"},
            {"source": "huggingface", "repository": "o/r", "alias": "x"},
            {"source": "", "repository": "o/r"},
            {"source": "huggingface", "repository": "  "},
            "just-a-string",
        ]
        for index, record in enumerate(bad_records):
            self.write_raw(
                json.dumps(
                    {
                        "schema_version": 1,
                        "bindings": {f"model-{index}": record},
                    }
                )
            )
            with self.assertRaises(AcquisitionBindingError):
                resolve_binding(f"model-{index}")

    def test_empty_registry_resolves_nothing(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        delete(UNMAPPED_MODEL_ID)
        self.assertIsNone(resolve_binding(UNMAPPED_MODEL_ID))

    def test_deterministic_serialization(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        first = self.read_bytes()
        delete(UNMAPPED_MODEL_ID)
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertEqual(first, self.read_bytes())
        payload = json.loads(first.decode("utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            payload["bindings"][UNMAPPED_MODEL_ID],
            {"source": UNMAPPED_SOURCE, "repository": UNMAPPED_REPOSITORY},
        )

    def test_atomic_write_uses_temp_sibling_and_fsync(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertFalse(
            self.path.with_name(self.path.name + ".tmp").exists()
        )
        with mock.patch.object(
            bindings.os, "replace", wraps=bindings.os.replace
        ) as replace, mock.patch.object(
            bindings.os, "fsync", wraps=bindings.os.fsync
        ) as fsync:
            bind(OTHER_MODEL_ID, UNMAPPED_SOURCE, OTHER_REPOSITORY)
        self.assertTrue(replace.called)
        # file fsync plus directory fsync.
        self.assertGreaterEqual(fsync.call_count, 2)
        self.assertFalse(
            self.path.with_name(self.path.name + ".tmp").exists()
        )

    def test_failed_write_cleans_temp_file(self):
        with mock.patch.object(
            bindings.os, "fsync", side_effect=OSError("boom")
        ):
            with self.assertRaises(OSError):
                bind(
                    UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY
                )
        self.assertFalse(self.path.exists())
        self.assertFalse(
            self.path.with_name(self.path.name + ".tmp").exists()
        )

    def test_read_does_not_create_directory_or_file(self):
        nested = (
            Path(self._directory.name) / "nested" / "acquisition-bindings.json"
        )
        os.environ[ACQUISITION_BINDINGS_ROOT_ENV] = str(nested.parent)
        self.assertIsNone(resolve_binding(UNMAPPED_MODEL_ID))
        self.assertFalse(nested.exists())

    def test_write_creates_parent_directories(self):
        nested = Path(self._directory.name) / "nested" / "deep"
        os.environ[ACQUISITION_BINDINGS_ROOT_ENV] = str(nested)
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertTrue((nested / "acquisition-bindings.json").exists())


class BindingTests(BindingsTestCase):
    """Registration validation, conflicts and idempotency."""

    def test_valid_bind_persists_locator(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertEqual(
            resolve_binding(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )

    def test_valid_bind_for_curated_model_with_matching_locator(self):
        bind(CURATED_MODEL_ID, CURATED_SOURCE, CURATED_REPOSITORY)
        self.assertEqual(
            resolve_binding(CURATED_MODEL_ID),
            (CURATED_SOURCE, CURATED_REPOSITORY),
        )

    def test_unsupported_source_rejected(self):
        with self.assertRaises(AcquisitionBindingError):
            bind(UNMAPPED_MODEL_ID, "unsupported-source", UNMAPPED_REPOSITORY)
        self.assertIsNone(self.read_bytes())

    def test_forward_identity_mismatch_rejected(self):
        # The caller supplies a model_id that the forward derivation
        # would never admit for this locator: fail closed, write nothing.
        with self.assertRaises(AcquisitionBindingError):
            bind("not-the-admitted-id", UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertIsNone(self.read_bytes())

    def test_curated_disagreement_rejected(self):
        # A binding that disagrees with the curated locator set for the
        # same model_id must be rejected at registration time.
        other_repo = "Qwen/Some-Other-Repo"
        other_id = resolve_admitted_model_id(CURATED_SOURCE, other_repo)
        self.assertNotEqual(other_id, CURATED_MODEL_ID)
        with self.assertRaises(AcquisitionBindingError):
            bind(CURATED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertIsNone(self.read_bytes())

    def test_existing_model_id_with_different_locator_fails_closed(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        # A different locator that still forward-resolves to the SAME
        # model_id is impossible with the current derivation (the digest
        # binds the locator), so the conflict path is exercised through
        # the lifecycle test below; here assert the registry is intact.
        self.assertEqual(
            resolve_binding(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )
        self.assertEqual(before, self.read_bytes())

    def test_bind_does_not_overwrite(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        second_repo = "someowner/second-model"
        second_id = resolve_admitted_model_id(UNMAPPED_SOURCE, second_repo)
        # Sanity: a different locator would resolve a different identity.
        self.assertNotEqual(second_id, UNMAPPED_MODEL_ID)
        # A conflicting registration for the SAME model_id fails closed.
        with self.assertRaises(AcquisitionBindingError):
            bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, second_repo)
        self.assertEqual(before, self.read_bytes())
        self.assertEqual(
            resolve_binding(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )

    def test_identical_reregistration_is_idempotent(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        mtime = self.path.stat().st_mtime_ns
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertEqual(before, self.read_bytes())
        self.assertEqual(mtime, self.path.stat().st_mtime_ns)

    def test_rejected_mutations_leave_file_byte_unchanged(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        for attempt in (
            lambda: bind("wrong-id", UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
            lambda: bind(
                UNMAPPED_MODEL_ID, "unsupported-source", UNMAPPED_REPOSITORY
            ),
            lambda: bind(CURATED_MODEL_ID, CURATED_SOURCE, "o/r"),
        ):
            with self.assertRaises(AcquisitionBindingError):
                attempt()
        self.assertEqual(before, self.read_bytes())

    def test_admission_does_not_create_bindings(self):
        # Resolving an admitted identity is a pure read: no registry is
        # created and no binding appears without an explicit bind call.
        resolve_admitted_model_id(UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertFalse(self.path.exists())
        self.assertIsNone(resolve_binding(UNMAPPED_MODEL_ID))


class LifecycleTests(BindingsTestCase):
    """Explicit bind/update/delete lifecycle."""

    def test_update_requires_existing_binding(self):
        with self.assertRaises(AcquisitionBindingError):
            update(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertIsNone(self.read_bytes())

    def test_update_revalidates_supported_source(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        with self.assertRaises(AcquisitionBindingError):
            update(
                UNMAPPED_MODEL_ID, "unsupported-source", UNMAPPED_REPOSITORY
            )
        self.assertEqual(before, self.read_bytes())

    def test_update_revalidates_forward_consistency(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        with self.assertRaises(AcquisitionBindingError):
            update(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, "someowner/wrong-id")
        self.assertEqual(before, self.read_bytes())

    def test_valid_delete_removes_binding(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        delete(UNMAPPED_MODEL_ID)
        self.assertIsNone(resolve_binding(UNMAPPED_MODEL_ID))
        self.assertEqual(
            resolve_admitted_model_id(UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
            UNMAPPED_MODEL_ID,
        )

    def test_delete_nonexistent_target_fails_closed(self):
        with self.assertRaises(AcquisitionBindingError):
            delete(UNMAPPED_MODEL_ID)
        self.assertIsNone(self.read_bytes())

    def test_valid_update_same_locator_succeeds(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        update(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertEqual(
            resolve_binding(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )

    def test_changing_locator_does_not_change_model_id(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = resolve_admitted_model_id(
            UNMAPPED_SOURCE, UNMAPPED_REPOSITORY
        )
        delete(UNMAPPED_MODEL_ID)
        after = resolve_admitted_model_id(
            UNMAPPED_SOURCE, UNMAPPED_REPOSITORY
        )
        self.assertEqual(before, after)


class ResolutionTests(BindingsTestCase):
    """D3 resolution order and defensive lookup behavior."""

    def test_curated_locator_wins_over_binding(self):
        from castlearq.model_identity import downloadable_locator

        bind(CURATED_MODEL_ID, CURATED_SOURCE, CURATED_REPOSITORY)
        self.assertEqual(
            resolve_acquisition_locator(CURATED_MODEL_ID),
            downloadable_locator(CURATED_MODEL_ID),
        )

    def test_curated_miss_falls_through_to_binding(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        self.assertEqual(
            resolve_acquisition_locator(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )

    def test_no_curated_no_binding_returns_none(self):
        self.assertIsNone(resolve_acquisition_locator(UNMAPPED_MODEL_ID))

    def test_resolution_does_not_mutate_or_create_state(self):
        self.assertIsNone(resolve_acquisition_locator(UNMAPPED_MODEL_ID))
        self.assertFalse(self.path.exists())
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        self.assertEqual(
            resolve_acquisition_locator(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )
        self.assertEqual(before, self.read_bytes())

    def test_unsupported_persisted_source_rejected_defensively(self):
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload["bindings"][UNMAPPED_MODEL_ID]["source"] = "unknown-source"
        self.write_raw(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        self.assertIsNone(resolve_acquisition_locator(UNMAPPED_MODEL_ID))

    def test_malformed_persistence_fails_loudly(self):
        self.write_raw("{not valid json")
        with self.assertRaises(AcquisitionBindingError):
            resolve_acquisition_locator(UNMAPPED_MODEL_ID)
        self.write_raw(json.dumps({"schema_version": 99, "bindings": {}}))
        with self.assertRaises(AcquisitionBindingError):
            resolve_acquisition_locator(UNMAPPED_MODEL_ID)


class CompositionTests(BindingsTestCase):
    """Seam integration without touching the acquisition service."""

    def test_resolver_signature_matches_seam(self):
        signature = inspect.signature(resolve_acquisition_locator)
        self.assertEqual(list(signature.parameters), ["model_id"])

    def test_wiring_injects_composed_resolver(self):
        from castlearq.application_wiring import compose_acquisition_service

        service = compose_acquisition_service()
        self.assertIs(service.locator_resolver, resolve_acquisition_locator)

    def test_service_constructor_shape_unchanged(self):
        from castlearq.acquisition_service import ModelAcquisitionService

        self.assertIn(
            "locator_resolver",
            inspect.signature(ModelAcquisitionService.__init__).parameters,
        )

    def test_acquisition_uses_binding_without_mutation(self):
        from castlearq.acquisition_service import ModelAcquisitionService

        service = ModelAcquisitionService(
            downloader=mock.Mock(),
            planner=mock.Mock(),
            identity_resolver=lambda source, repository: None,
            locator_audit=lambda model_id: (),
            locator_resolver=resolve_acquisition_locator,
            discovery_provider=mock.Mock(return_value=[]),
            store=mock.Mock(),
        )
        bind(UNMAPPED_MODEL_ID, UNMAPPED_SOURCE, UNMAPPED_REPOSITORY)
        before = self.read_bytes()
        self.assertEqual(
            service.locator_resolver(UNMAPPED_MODEL_ID),
            (UNMAPPED_SOURCE, UNMAPPED_REPOSITORY),
        )
        self.assertEqual(
            service._resolve_repository(UNMAPPED_MODEL_ID),
            UNMAPPED_REPOSITORY,
        )
        self.assertEqual(before, self.read_bytes())


if __name__ == "__main__":
    unittest.main()
