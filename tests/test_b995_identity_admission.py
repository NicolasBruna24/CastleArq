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

"""B9.95: persistent, forward-only Identity Admission Registry.

The contract under test, as ratified:

- ``lookup(source, repository)`` and ``register(source, repository, model_id)``
  are the ONLY operations. There is no reverse lookup, no enumeration, no
  removal and no update -- a ``model_id -> repository`` capability would make
  derived identities resolvable by the acquisition gate and therefore
  downloadable, breaking the invariant B9.94 Increment 1 closed on.
- Authority is curated -> persisted -> derived. Curated identity is never
  overwritten; a persisted binding is immutable.
- Every conflict FAILS CLOSED and leaves the registry byte-for-byte unchanged.
- Persistence is atomic AND durable: temporary file, file fsync, os.replace,
  parent-directory fsync.
- Corrupt state is reported loudly and never silently treated as an empty
  registry, because that would be fail-open and would permit silent identity
  reassignment.

The registry is redirected through CASTLEARQ_IDENTITY_REGISTRY_ROOT, so every
test runs against a private temporary directory and never touches a real
user registry.
"""

import ast
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import castlearq.identity_admission as admission
from castlearq.identity_admission import (
    IDENTITY_REGISTRY_ROOT_ENV,
    IdentityAdmissionError,
    lookup,
    register,
    registry_path,
    registry_root,
)
from castlearq.model_identity import derive_model_id, logical_model_id

#: A curated repository and its authoritative identity (B9.93).
CURATED_REPOSITORY = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
CURATED_MODEL_ID = "qwen2.5-coder-7b-instruct"

#: A repository with no curated entry.
UNKNOWN_REPOSITORY = "owner/repository"


class RegistryTestCase(unittest.TestCase):
    """Base case redirecting the registry into a private temporary directory."""

    def setUp(self):
        self._previous = os.environ.get(IDENTITY_REGISTRY_ROOT_ENV)
        self._directory = tempfile.TemporaryDirectory()
        os.environ[IDENTITY_REGISTRY_ROOT_ENV] = self._directory.name
        self.addCleanup(self._restore)

    def _restore(self):
        self._directory.cleanup()
        if self._previous is None:
            os.environ.pop(IDENTITY_REGISTRY_ROOT_ENV, None)
        else:
            os.environ[IDENTITY_REGISTRY_ROOT_ENV] = self._previous

    @property
    def path(self):
        return registry_path()

    def write_registry(self, payload: str) -> None:
        """Write raw registry content, bypassing the module's own writer."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
class LocationTests(RegistryTestCase):
    """Root resolution, environment override and default path."""

    def test_environment_override_selects_the_directory(self):
        self.assertEqual(registry_root(), Path(self._directory.name))

    def test_registry_path_is_the_filename_inside_the_root(self):
        self.assertEqual(
            registry_path(), Path(self._directory.name) / "identity-admission.json"
        )

    def test_default_root_is_dot_castlearq_under_home(self):
        root = registry_root(environ={}, home=Path("/home/example"))

        self.assertEqual(root, Path("/home/example/.castlearq"))

    def test_override_may_be_any_directory_and_is_not_a_file(self):
        resolved = registry_root(environ={IDENTITY_REGISTRY_ROOT_ENV: "/tmp/custom"})

        self.assertEqual(resolved, Path("/tmp/custom"))

    def test_default_path_does_not_use_model_store_resolution(self):
        """The registry must not inherit the artifact-store precedence chain."""
        self.assertNotEqual(registry_root(environ={}), Path.home() / ".local/share")

    def test_environment_name_is_registry_specific(self):
        self.assertEqual(
            IDENTITY_REGISTRY_ROOT_ENV, "CASTLEARQ_IDENTITY_REGISTRY_ROOT"
        )


class LookupTests(RegistryTestCase):
    """Forward lookup only, and absence is not corruption."""

    def test_absent_registry_returns_none(self):
        self.assertIsNone(lookup("huggingface", UNKNOWN_REPOSITORY))

    def test_lookup_does_not_create_the_registry(self):
        lookup("huggingface", UNKNOWN_REPOSITORY)

        self.assertFalse(self.path.exists())

    def test_registered_identity_is_returned(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )

    def test_unknown_locator_in_an_existing_registry_returns_none(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertIsNone(lookup("huggingface", "other/absent"))

    def test_lookup_is_source_scoped(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertIsNone(lookup("other-source", UNKNOWN_REPOSITORY))

    def test_identity_survives_a_fresh_module_state(self):
        """Persistence is on disk, so a new lookup sees the same binding."""
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY),
            admission._load(self.path)[admission._locator_key(
                "huggingface", UNKNOWN_REPOSITORY
            )],
        )


class RegistrationTests(RegistryTestCase):
    """First registration, idempotency and immutability."""

    def test_first_registration_persists(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertTrue(self.path.exists())
        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )

    def test_registration_creates_missing_directories(self):
        nested = Path(self._directory.name) / "deeper" / "still"
        os.environ[IDENTITY_REGISTRY_ROOT_ENV] = str(nested)

        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertTrue((nested / "identity-admission.json").exists())

    def test_identical_registration_succeeds_and_is_idempotent(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")
        before = self.path.read_bytes()

        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )
        self.assertEqual(self.path.read_bytes(), before)

    def test_same_locator_with_a_different_identity_is_rejected(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")
        before = self.path.read_bytes()

        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", UNKNOWN_REPOSITORY, "different-model")

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )

    def test_same_identity_for_a_different_locator_is_rejected(self):
        """No reverse index is persisted, so uniqueness is a forward scan."""
        register("huggingface", UNKNOWN_REPOSITORY, "shared-model")
        before = self.path.read_bytes()

        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", "other/repository", "shared-model")

        self.assertEqual(self.path.read_bytes(), before)

    def test_a_persisted_binding_is_never_rewritten_by_derivation(self):
        """Derivation cannot reassign an already-admitted identity."""
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")
        derived = derive_model_id("huggingface", UNKNOWN_REPOSITORY)

        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", UNKNOWN_REPOSITORY, derived)

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )

    def test_repository_rename_creates_a_new_locator(self):
        register("huggingface", "old-owner/model", "admitted-old")

        register("huggingface", "new-owner/model", "admitted-new")

        self.assertEqual(lookup("huggingface", "old-owner/model"), "admitted-old")
        self.assertEqual(lookup("huggingface", "new-owner/model"), "admitted-new")
class AuthorityTests(RegistryTestCase):
    """curated -> persisted -> derived, with curated never overwritten."""

    def test_curated_identity_is_accepted_unchanged(self):
        register("huggingface", CURATED_REPOSITORY, CURATED_MODEL_ID)

        self.assertEqual(
            lookup("huggingface", CURATED_REPOSITORY), CURATED_MODEL_ID
        )

    def test_curated_identity_may_not_be_overridden(self):
        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", CURATED_REPOSITORY, "rogue-model")

        self.assertFalse(self.path.exists())

    def test_curated_conflict_does_not_create_state(self):
        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", CURATED_REPOSITORY, "rogue-model")

        self.assertEqual(
            logical_model_id("huggingface", CURATED_REPOSITORY), CURATED_MODEL_ID
        )

    def test_unknown_repository_can_be_persisted(self):
        derived = derive_model_id("huggingface", UNKNOWN_REPOSITORY)
        register("huggingface", UNKNOWN_REPOSITORY, derived)

        self.assertEqual(lookup("huggingface", UNKNOWN_REPOSITORY), derived)

    def test_registration_does_not_derive_or_fabricate(self):
        """register() persists exactly what it was given."""
        register("huggingface", UNKNOWN_REPOSITORY, "explicitly-chosen")

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "explicitly-chosen"
        )

    def test_curated_entries_are_not_persisted_implicitly(self):
        """A curated entry is written only when registered explicitly."""
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertIsNone(lookup("huggingface", CURATED_REPOSITORY))


class ValidationTests(RegistryTestCase):
    """Empty or malformed inputs never create invalid authoritative state."""

    def test_empty_components_are_rejected(self):
        for args in (
            ("", UNKNOWN_REPOSITORY, "m"),
            ("huggingface", "", "m"),
            ("huggingface", UNKNOWN_REPOSITORY, ""),
        ):
            with self.subTest(args=args):
                with self.assertRaises(IdentityAdmissionError):
                    register(*args)

    def test_non_string_components_are_rejected(self):
        for args in ((None, "r", "m"), ("s", None, "m"), ("s", "r", None)):
            with self.subTest(args=args):
                with self.assertRaises(IdentityAdmissionError):
                    register(*args)

    def test_rejected_registration_creates_no_file(self):
        with self.assertRaises(IdentityAdmissionError):
            register("", "r", "m")

        self.assertFalse(self.path.exists())

    def test_lookup_validates_its_inputs(self):
        for args in (("", "r"), ("s", "")):
            with self.subTest(args=args):
                with self.assertRaises(IdentityAdmissionError):
                    lookup(*args)

    def test_registry_stores_bindings_not_provider_semantics(self):
        """The registry applies no provider-specific repository rules."""
        register("not-a-real-provider", "no-slash", "admitted-model")

        self.assertEqual(lookup("not-a-real-provider", "no-slash"), "admitted-model")
class CorruptionTests(RegistryTestCase):
    """Corrupt state is reported, never silently treated as empty."""

    def assertCorrupt(self):
        with self.assertRaises(IdentityAdmissionError):
            lookup("huggingface", UNKNOWN_REPOSITORY)

    def write_raw(self, payload) -> None:
        """Write arbitrary (often invalid) JSON without the module's writer."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            payload if isinstance(payload, str) else json.dumps(payload),
            encoding="utf-8",
        )

    def test_malformed_json_fails_loudly(self):
        self.write_raw("{not json")

        self.assertCorrupt()

    def test_missing_schema_version_fails_loudly(self):
        self.write_raw({"identities": {}})

        self.assertCorrupt()

    def test_unknown_schema_version_fails_loudly(self):
        self.write_raw({"schema_version": 2, "identities": {}})

        self.assertCorrupt()

    def test_non_integer_schema_version_fails_loudly(self):
        self.write_raw({"schema_version": "1", "identities": {}})

        self.assertCorrupt()

    def test_boolean_schema_version_fails_loudly(self):
        self.write_raw({"schema_version": True, "identities": {}})

        self.assertCorrupt()

    def test_non_object_top_level_fails_loudly(self):
        self.write_raw([1, 2, 3])

        self.assertCorrupt()

    def test_missing_identities_fails_loudly(self):
        self.write_raw({"schema_version": 1})

        self.assertCorrupt()

    def test_non_object_identities_fails_loudly(self):
        self.write_raw({"schema_version": 1, "identities": []})

        self.assertCorrupt()

    def test_unknown_top_level_field_fails_loudly(self):
        self.write_raw({"schema_version": 1, "identities": {}, "extra": 1})

        self.assertCorrupt()

    def test_unknown_record_field_fails_loudly(self):
        self.write_raw(
            {"schema_version": 1, "identities": {'["s","r"]': {"model_id": "m", "x": 1}}}
        )

        self.assertCorrupt()

    def test_missing_model_id_fails_loudly(self):
        self.write_raw({"schema_version": 1, "identities": {'["s","r"]': {}}})

        self.assertCorrupt()

    def test_empty_model_id_fails_loudly(self):
        self.write_raw(
            {"schema_version": 1, "identities": {'["s","r"]': {"model_id": "  "}}}
        )

        self.assertCorrupt()

    def test_non_string_model_id_fails_loudly(self):
        self.write_raw(
            {"schema_version": 1, "identities": {'["s","r"]': {"model_id": 7}}}
        )

        self.assertCorrupt()

    def test_non_object_record_fails_loudly(self):
        self.write_raw({"schema_version": 1, "identities": {'["s","r"]': "m"}})

        self.assertCorrupt()

    def test_corruption_also_blocks_registration(self):
        """Fail closed: a corrupt registry is not silently overwritten."""
        self.write_raw("{not json")

        with self.assertRaises(IdentityAdmissionError):
            register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(self.path.read_text(), "{not json")

    def test_a_missing_registry_is_not_corruption(self):
        """The distinction between absent and corrupt must stay explicit."""
        self.assertIsNone(lookup("huggingface", UNKNOWN_REPOSITORY))
class SchemaTests(RegistryTestCase):
    """The persisted shape is exactly the ratified one."""

    def test_schema_version_is_always_written(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        payload = json.loads(self.path.read_text())

        self.assertEqual(payload["schema_version"], 1)

    def test_record_contains_exactly_the_three_ratified_fields(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        payload = json.loads(self.path.read_text())

        self.assertEqual(set(payload), {"schema_version", "identities"})
        (record,) = payload["identities"].values()
        self.assertEqual(set(record), {"model_id"})

    def test_locator_key_is_a_json_array_and_is_collision_free(self):
        register("huggingface", "a/b", "model-one")
        register("huggingface", "a", "model-two")

        payload = json.loads(self.path.read_text())

        # ("a","b") and ("a","/b")-style ambiguity is impossible for a JSON array
        # key, unlike any fixed-delimiter join.
        self.assertEqual(len(payload["identities"]), 2)
        for key in payload["identities"]:
            self.assertIsInstance(json.loads(key), list)

    def test_delimiter_joins_would_collide_but_this_does_not(self):
        register("huggingface", "a/b", "model-one")
        register("huggingface", "a", "model-b")

        self.assertEqual(lookup("huggingface", "a/b"), "model-one")
        self.assertEqual(lookup("huggingface", "a"), "model-b")

    def test_serialization_is_deterministic(self):
        register("huggingface", "z/last", "model-z")
        register("huggingface", "a/first", "model-a")
        first = self.path.read_bytes()

        # Rewriting the same logical state must reproduce identical bytes.
        os.unlink(self.path)
        register("huggingface", "a/first", "model-a")
        register("huggingface", "z/last", "model-z")

        self.assertEqual(self.path.read_bytes(), first)

    def test_serialization_uses_indent_and_sorted_keys(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        text = self.path.read_text()

        self.assertIn("\n  ", text)
        self.assertTrue(text.endswith("\n"))

    def test_no_timestamp_or_generated_identifier_is_persisted(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        text = self.path.read_text().lower()

        for forbidden in ("timestamp", "admitted_at", "created", "uuid", "revision"):
            self.assertNotIn(forbidden, text)

    def test_no_reverse_index_is_persisted(self):
        """A model_id -> locator index would make derived IDs downloadable."""
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        payload = json.loads(self.path.read_text())

        # Every stored record holds only model_id; no value is a locator.
        for record in payload["identities"].values():
            self.assertEqual(set(record), {"model_id"})
            self.assertNotIn(UNKNOWN_REPOSITORY, record.values())


class DurabilityTests(RegistryTestCase):
    """Atomic replacement plus file and parent-directory fsync."""

    def test_file_and_directory_fsync_are_invoked(self):
        """Instrumented rather than physically verified."""
        real_fsync = os.fsync
        seen = []

        def recording_fsync(fd):
            seen.append(fd)
            return real_fsync(fd)

        with mock.patch.object(admission.os, "fsync", recording_fsync):
            register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        # One fsync for the temporary file, one for the parent directory.
        self.assertGreaterEqual(len(seen), 2)

    def test_write_uses_a_temporary_file_then_replace(self):
        calls = []
        real_replace = os.replace

        def recording_replace(src, dst):
            calls.append((str(src), str(dst)))
            return real_replace(src, dst)

        with mock.patch.object(admission.os, "replace", recording_replace):
            register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        (source, destination), = calls

        self.assertTrue(source.endswith(".tmp"))
        self.assertEqual(destination, str(self.path))

    def test_no_temporary_file_survives_a_successful_write(self):
        register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(
            [p.name for p in self.path.parent.iterdir()],
            ["identity-admission.json"],
        )

    def test_temporary_file_is_removed_when_the_write_fails(self):
        """The cleanup path guards a failure DURING the write.

        `os.replace` itself failing is a different case: the payload was
        already written and flushed, so the temporary file legitimately
        remains until the next successful write replaces it. Only the
        write-phase failure is covered here, which is what the cleanup in
        `_write` actually protects.
        """
        real_fsync = os.fsync

        def failing_fsync(fd):
            real_fsync(fd)
            raise OSError("fsync failed")

        with mock.patch.object(admission.os, "fsync", failing_fsync):
            with self.assertRaises(OSError):
                register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(list(self.path.parent.iterdir()), [])


class BoundaryTests(unittest.TestCase):
    """Static verification of the ratified architectural boundary.

    The checks parse the AST rather than grepping text, because the module's
    prose legitimately NAMES the modules it must not import while explaining
    why. Only a real import would be a coupling.
    """

    def source_tree(self):
        return ast.parse(inspect.getsource(admission))

    def imported_names(self):
        imported = set()
        for node in ast.walk(self.source_tree()):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        return imported

    def referenced_attributes(self):
        return {
            node.attr
            for node in ast.walk(self.source_tree())
            if isinstance(node, ast.Attribute)
        }

    def test_forbidden_modules_are_not_imported(self):
        imported = self.imported_names()

        for forbidden in (
            "model_store",
            "session",
            "acquisition_service",
            "acquisition_mapping",
            "application_wiring",
            "main",
            "api",
        ):
            self.assertNotIn(forbidden, imported)

    def test_only_model_identity_and_stdlib_are_imported(self):
        imported = self.imported_names()

        # `from .model_identity import logical_model_id` imports the NAME, and
        # the module attribute records the origin.
        self.assertIn("logical_model_id", imported)
        self.assertIn("annotations", imported)
        self.assertIn("json", imported)
        self.assertIn("os", imported)
        self.assertIn("Path", imported)
        self.assertIn("Mapping", imported)

    def test_forbidden_helpers_are_never_referenced(self):
        referenced = self.referenced_attributes()

        for forbidden in (
            "_safe_model_id",
            "save_manifest",
            "list_artifacts",
            "ModelStore",
            "downloadable_locator",
            "resolve_admitted_model_id",
            "SessionError",
        ):
            self.assertNotIn(forbidden, referenced)

    def test_public_api_is_exactly_the_forward_contract(self):
        self.assertEqual(
            sorted(admission.__all__),
            [
                "IdentityAdmissionError",
                "lookup",
                "register",
                "registry_path",
                "registry_root",
            ],
        )

    def test_no_reverse_enumeration_or_mutation_api_exists(self):
        forbidden = (
            "lookup_repository",
            "reverse",
            "list_identities",
            "remove",
            "delete",
            "update",
            "unregister",
            "items",
            "values",
            "keys",
        )

        for name in forbidden:
            self.assertFalse(hasattr(admission, name), name)

    def test_signatures_are_exactly_as_ratified(self):
        self.assertEqual(
            list(inspect.signature(lookup).parameters), ["source", "repository"]
        )
        self.assertEqual(
            list(inspect.signature(register).parameters),
            ["source", "repository", "model_id"],
        )

    def test_exception_is_independent_of_every_other_boundary_error(self):
        from castlearq.model_identity import DerivedIdentityError
        from castlearq.model_store import ModelStoreError
        from castlearq.session import SessionError

        for other in (SessionError, ModelStoreError, DerivedIdentityError):
            self.assertFalse(issubclass(IdentityAdmissionError, other))
            self.assertFalse(issubclass(other, IdentityAdmissionError))

    def test_model_identity_remains_free_of_persistence_and_io(self):
        """The dependency arrow points one way only."""
        import castlearq.model_identity as identity

        tree = ast.parse(inspect.getsource(identity))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)

        self.assertEqual(sorted(imported), ["annotations", "hashlib", "re"])
        self.assertFalse(
            imported & {"json", "os", "sqlite3", "identity_admission"}
        )

    def test_no_network_or_provider_module_is_imported(self):
        imported = self.imported_names()

        for forbidden in ("urllib", "requests", "socket", "http", "huggingface"):
            self.assertNotIn(forbidden, imported)


class ConcurrencyBoundaryTests(RegistryTestCase):
    """The accepted non-locking limitation, asserted deterministically.

    B9.95 accepts that ``read -> modify -> replace`` is not transactional: two
    processes registering DIFFERENT repositories can lose one update. This is
    asserted as a property of the design rather than reproduced with flaky
    multiprocessing.
    """

    def test_no_locking_primitive_is_used(self):
        source = inspect.getsource(admission)

        for forbidden in ("flock", "fcntl", "lockf", "LOCK_EX", "threading.Lock"):
            self.assertNotIn(forbidden, source)

    def test_no_database_is_used(self):
        self.assertNotIn("sqlite3", self.imported_names())

    def test_second_registration_reads_the_persisted_state(self):
        """The file, not in-process state, is the authority between calls."""
        register("huggingface", "first/repo", "model-first")
        register("huggingface", "second/repo", "model-second")

        self.assertEqual(lookup("huggingface", "first/repo"), "model-first")
        self.assertEqual(lookup("huggingface", "second/repo"), "model-second")

    def test_same_locator_repeated_writes_are_benign(self):
        """Identical registrations are idempotent, so no lock is required."""
        for _ in range(5):
            register("huggingface", UNKNOWN_REPOSITORY, "admitted-model")

        self.assertEqual(
            lookup("huggingface", UNKNOWN_REPOSITORY), "admitted-model"
        )

    def test_the_module_docstring_records_the_limitation(self):
        doc = inspect.getdoc(admission)

        self.assertIn("NOT transactional", doc)
        self.assertIn("No locking", doc)

    def imported_names(self):
        imported = set()
        for node in ast.walk(ast.parse(inspect.getsource(admission))):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        return imported


if __name__ == "__main__":
    unittest.main()