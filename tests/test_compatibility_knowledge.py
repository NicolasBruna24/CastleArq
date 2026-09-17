# Copyright 2026 Nicolas Bruna
# Licensed under the Apache License, Version 2.0.

"""B9.5: fictional knowledge only; no registry/evaluator integration."""

import ast
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, fields, replace
from itertools import permutations
from pathlib import Path
import unittest
from unittest.mock import patch

from app import compatibility_knowledge as ck


STATE = ck.KnowledgeState
KIND = ck.KnowledgeKind
PREDICATE = ck.KnowledgePredicate
ALPHA = ck.KnowledgeSubject(KIND.RUNTIME, "alpha")
BETA = ck.KnowledgeSubject(KIND.BACKEND, "beta")


def assertion(**overrides):
    return ck.KnowledgeAssertion(**{
        "subject": ALPHA, "predicate": PREDICATE.SUPPORTS,
        "object": BETA, "state": STATE.SUPPORTED, **overrides,
    })


class EnumTests(unittest.TestCase):
    def test_states(self):
        self.assertEqual({s.name for s in STATE},
                         {"SUPPORTED", "UNSUPPORTED", "UNKNOWN"})
        self.assertNotEqual(STATE.UNKNOWN, STATE.UNSUPPORTED)

    def test_predicates(self):
        self.assertEqual(tuple(PREDICATE), (PREDICATE.SUPPORTS,))

    def test_kinds(self):
        self.assertEqual({k.value for k in KIND},
                         {"runtime", "backend", "format", "architecture",
                          "capability", "platform"})

    def test_arbitrary_enum_values_rejected(self):
        for enum in (STATE, PREDICATE, KIND):
            with self.subTest(enum=enum), self.assertRaises(ValueError):
                enum("arbitrary")


class SubjectTests(unittest.TestCase):
    def test_canonical_identity_and_metadata(self):
        subject = ck.KnowledgeSubject(KIND.RUNTIME, "alpha", "Alpha", ["A"])
        self.assertEqual(subject.canonical_id, "alpha")
        self.assertEqual(subject.display_name, "Alpha")
        self.assertEqual(subject.aliases, ("A",))

    def test_invalid_identifiers_not_normalized(self):
        for value in ("", "  ", " alpha", "alpha ", None, 1, [], lambda: None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ck.KnowledgeSubject(KIND.RUNTIME, value)

    def test_kind_must_be_enum(self):
        for value in (None, "runtime", "", [], 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ck.KnowledgeSubject(value, "alpha")

    def test_invalid_aliases(self):
        for value in ("A", {"A"}, [""], [" "], [None], [1], [lambda: None]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ck.KnowledgeSubject(KIND.RUNTIME, "alpha", aliases=value)

    def test_invalid_display_name(self):
        for value in ("", " ", [], 4):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ck.KnowledgeSubject(KIND.RUNTIME, "alpha", display_name=value)

    def test_alias_input_is_copied(self):
        aliases = ["A"]
        subject = ck.KnowledgeSubject(KIND.RUNTIME, "alpha", aliases=aliases)
        aliases.append("B")
        self.assertEqual(subject.aliases, ("A",))
        self.assertEqual(subject.canonical_id, "alpha")


class MetadataTests(unittest.TestCase):
    def test_unknown_metadata_remains_none(self):
        for cls in (ck.KnowledgeScope, ck.KnowledgeProvenance):
            obj = cls()
            for field in fields(obj):
                self.assertIsNone(getattr(obj, field.name))

    def test_scope_fields_preserved(self):
        scope = ck.KnowledgeScope("alpha", ">=2, <10", "beta", "platform-p", "v")
        self.assertEqual(scope.runtime_id, "alpha")
        self.assertEqual(scope.runtime_version, ">=2, <10")
        self.assertEqual(scope.backend_id, "beta")
        self.assertEqual(scope.platform, "platform-p")
        self.assertEqual(scope.variant, "v")

    def test_provenance_preserved_verbatim(self):
        values = ("Author A", "declaration", "urn:fiction:source-a", "release-date", "review-date")
        provenance = ck.KnowledgeProvenance(*values)
        self.assertEqual(tuple(getattr(provenance, f.name) for f in fields(provenance)), values)

    def test_metadata_fields_reject_invalid_values(self):
        for cls in (ck.KnowledgeScope, ck.KnowledgeProvenance):
            for field in fields(cls):
                for value in ("", " ", 1, [], {}, lambda: None):
                    with self.subTest(cls=cls, field=field.name, value=value):
                        with self.assertRaises(ValueError):
                            cls(**{field.name: value})


class AssertionTests(unittest.TestCase):
    def test_valid_construction(self):
        item = assertion()
        self.assertIs(item.subject, ALPHA)
        self.assertIs(item.object, BETA)
        self.assertIs(item.state, STATE.SUPPORTED)
        self.assertEqual(item.scope, ck.KnowledgeScope())
        self.assertEqual(item.provenance, ck.KnowledgeProvenance())

    def test_invalid_domain_fields(self):
        for field in fields(ck.KnowledgeAssertion):
            for value in (None, "supports", [], lambda: None):
                with self.subTest(field=field.name, value=value):
                    with self.assertRaises(ValueError):
                        assertion(**{field.name: value})

    def test_all_states_remain_explicit(self):
        for state in STATE:
            self.assertIs(assertion(state=state).state, state)


class RegistryTests(unittest.TestCase):
    def test_empty_registry_is_unknown(self):
        registry = ck.KnowledgeRegistry()
        self.assertEqual(registry.entries, ())
        self.assertEqual(registry.query(ALPHA, BETA), ())
        self.assertIs(registry.state_for(ALPHA, BETA), STATE.UNKNOWN)
        self.assertFalse(registry.has_conflict(ALPHA, BETA))
        self.assertEqual(registry.conflicts(), ())

    def test_supported(self):
        item = assertion()
        registry = ck.KnowledgeRegistry([item])
        self.assertEqual(registry.query(ALPHA, BETA), (item,))
        self.assertIs(registry.state_for(ALPHA, BETA), STATE.SUPPORTED)

    def test_unsupported(self):
        registry = ck.KnowledgeRegistry([assertion(state=STATE.UNSUPPORTED)])
        self.assertIs(registry.state_for(ALPHA, BETA), STATE.UNSUPPORTED)

    def test_absence_is_not_unsupported(self):
        registry = ck.KnowledgeRegistry([assertion()])
        gamma = ck.KnowledgeSubject(KIND.BACKEND, "gamma")
        self.assertIs(registry.state_for(ALPHA, gamma), STATE.UNKNOWN)

    def test_explicit_unknown(self):
        item = assertion(state=STATE.UNKNOWN)
        registry = ck.KnowledgeRegistry([item])
        self.assertEqual(registry.query(ALPHA, BETA), (item,))
        self.assertIs(registry.state_for(ALPHA, BETA), STATE.UNKNOWN)

    def test_unknown_does_not_contradict_explicit_state(self):
        for state in (STATE.SUPPORTED, STATE.UNSUPPORTED):
            registry = ck.KnowledgeRegistry([
                assertion(state=STATE.UNKNOWN), assertion(state=state)])
            self.assertIs(registry.state_for(ALPHA, BETA), state)
            self.assertFalse(registry.has_conflict(ALPHA, BETA))
            self.assertEqual(len(registry.query(ALPHA, BETA)), 2)

    def test_add_returns_new_registry(self):
        original = ck.KnowledgeRegistry()
        added = original.add(assertion())
        self.assertEqual(original.entries, ())
        self.assertEqual(added.entries, (assertion(),))

    def test_deduplicate_identical_assertions(self):
        item = assertion()
        registry = ck.KnowledgeRegistry([item, item]).add(item)
        self.assertEqual(registry.entries, (item,))
        self.assertFalse(registry.has_conflict(ALPHA, BETA))

    def test_different_provenance_is_not_deduplicated(self):
        items = [assertion(provenance=ck.KnowledgeProvenance(source=s))
                 for s in ("source-a", "source-b")]
        registry = ck.KnowledgeRegistry(items)
        self.assertEqual(set(registry.query(ALPHA, BETA)), set(items))
        self.assertFalse(registry.has_conflict(ALPHA, BETA))

    def test_inputs_are_copied(self):
        items = [assertion()]
        registry = ck.KnowledgeRegistry(items)
        items.clear()
        self.assertEqual(registry.entries, (assertion(),))

    def test_invalid_registry_contents(self):
        for value in (None, "text", {}, [None], [lambda: None]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ck.KnowledgeRegistry(value)

    def test_invalid_add(self):
        with self.assertRaises(ValueError):
            ck.KnowledgeRegistry().add("assertion")

    def test_invalid_query_inputs(self):
        registry = ck.KnowledgeRegistry()
        for kwargs in ({"subject": "alpha"}, {"object": "beta"},
                       {"scope": None}, {"predicate": "supports"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                registry.query(**{"subject": ALPHA, "object": BETA, **kwargs})

    def test_exact_ids_no_case_substring_or_alias_matching(self):
        subject = replace(ALPHA, display_name="Alpha Runtime", aliases=("A",))
        registry = ck.KnowledgeRegistry([assertion(subject=subject)])
        for identifier in ("Alpha", "alp", "A", "Alpha Runtime"):
            with self.subTest(identifier=identifier):
                other = replace(ALPHA, canonical_id=identifier)
                self.assertIs(registry.state_for(other, BETA), STATE.UNKNOWN)
        self.assertIs(registry.state_for(ALPHA, BETA), STATE.SUPPORTED)

    def test_object_metadata_not_identity(self):
        registry = ck.KnowledgeRegistry([assertion()])
        other = replace(BETA, display_name="Different label", aliases=("B",))
        self.assertIs(registry.state_for(ALPHA, other), STATE.SUPPORTED)
        other = replace(BETA, canonical_id="Beta")
        self.assertIs(registry.state_for(ALPHA, other), STATE.UNKNOWN)

    def test_kind_is_part_of_identity(self):
        registry = ck.KnowledgeRegistry([assertion()])
        other = replace(BETA, kind=KIND.FORMAT)
        self.assertIs(registry.state_for(ALPHA, other), STATE.UNKNOWN)


class ScopeAndConflictTests(unittest.TestCase):
    def test_each_scope_field_matches_exactly(self):
        for field in fields(ck.KnowledgeScope):
            with self.subTest(field=field.name):
                scope = ck.KnowledgeScope(**{field.name: "value-a"})
                registry = ck.KnowledgeRegistry([assertion(scope=scope)])
                self.assertIs(registry.state_for(ALPHA, BETA, scope=scope), STATE.SUPPORTED)
                self.assertIs(registry.state_for(ALPHA, BETA), STATE.UNKNOWN)
                other = replace(scope, **{field.name: "value-b"})
                self.assertIs(registry.state_for(ALPHA, BETA, scope=other), STATE.UNKNOWN)

    def test_empty_scope_is_not_wildcard(self):
        registry = ck.KnowledgeRegistry([assertion()])
        scope = ck.KnowledgeScope(runtime_version="2")
        self.assertIs(registry.state_for(ALPHA, BETA, scope=scope), STATE.UNKNOWN)

    def test_versions_are_opaque_not_ranges(self):
        scope = ck.KnowledgeScope(runtime_version=">=2.0")
        registry = ck.KnowledgeRegistry([assertion(scope=scope)])
        for version in ("2.0", "10.0", "3.0"):
            other = replace(scope, runtime_version=version)
            self.assertIs(registry.state_for(ALPHA, BETA, scope=other), STATE.UNKNOWN)
        self.assertEqual(registry.entries[0].scope.runtime_version, ">=2.0")

    def test_conflict_preserves_both_sources(self):
        positive = assertion(provenance=ck.KnowledgeProvenance(source="source-a"))
        negative = assertion(state=STATE.UNSUPPORTED,
                             provenance=ck.KnowledgeProvenance(source="source-b"))
        registry = ck.KnowledgeRegistry([positive, negative])
        conflict = registry.state_for(ALPHA, BETA)
        self.assertIsInstance(conflict, ck.KnowledgeConflict)
        self.assertEqual(set(conflict.assertions), {positive, negative})
        self.assertTrue(registry.has_conflict(ALPHA, BETA))
        self.assertEqual(registry.conflicts(), (conflict,))
        self.assertNotEqual(conflict, STATE.UNKNOWN)

    def test_unknown_does_not_hide_conflict(self):
        items = [assertion(state=state) for state in STATE]
        conflict = ck.KnowledgeRegistry(items).state_for(ALPHA, BETA)
        self.assertIsInstance(conflict, ck.KnowledgeConflict)
        self.assertEqual(set(conflict.assertions), set(items))

    def test_conflict_uses_canonical_identity_not_labels(self):
        positive = assertion()
        negative = assertion(state=STATE.UNSUPPORTED,
                             subject=replace(ALPHA, display_name="Different label"))
        self.assertTrue(ck.KnowledgeRegistry([positive, negative]).has_conflict(ALPHA, BETA))

    def test_different_scopes_are_not_merged(self):
        first = ck.KnowledgeScope(platform="platform-a")
        second = ck.KnowledgeScope(platform="platform-b")
        registry = ck.KnowledgeRegistry([
            assertion(scope=first), assertion(scope=second, state=STATE.UNSUPPORTED)])
        self.assertEqual(registry.conflicts(), ())
        self.assertIs(registry.state_for(ALPHA, BETA, scope=first), STATE.SUPPORTED)
        self.assertIs(registry.state_for(ALPHA, BETA, scope=second), STATE.UNSUPPORTED)

    def test_invalid_conflicts_rejected(self):
        positive = assertion()
        negative = assertion(state=STATE.UNSUPPORTED)
        for items in ([], [positive], [positive, positive],
                      [positive, assertion(state=STATE.UNKNOWN)],
                      [positive, replace(negative, scope=ck.KnowledgeScope(variant="v"))],
                      [positive, replace(negative, object=ALPHA)], [None]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                ck.KnowledgeConflict(items)

    def test_conflict_deduplicates_and_copies(self):
        items = [assertion(), assertion(state=STATE.UNSUPPORTED), assertion()]
        conflict = ck.KnowledgeConflict(items)
        items.clear()
        self.assertEqual(len(conflict.assertions), 2)

    def test_order_independent_results_and_conflicts(self):
        items = [assertion(), assertion(state=STATE.UNSUPPORTED),
                 assertion(object=ck.KnowledgeSubject(KIND.FORMAT, "gamma")),
                 assertion(state=STATE.UNKNOWN)]
        expected = ck.KnowledgeRegistry(items)
        for ordering in permutations(items):
            registry = ck.KnowledgeRegistry(ordering)
            self.assertEqual(registry, expected)
            self.assertEqual(registry.query(ALPHA, BETA), expected.query(ALPHA, BETA))
            self.assertEqual(registry.state_for(ALPHA, BETA), expected.state_for(ALPHA, BETA))
            self.assertEqual(registry.conflicts(), expected.conflicts())
            incremental = ck.KnowledgeRegistry()
            for item in ordering:
                incremental = incremental.add(item)
            self.assertEqual(incremental, expected)


class ImmutabilityAndPurityTests(unittest.TestCase):
    def test_all_domain_objects_are_frozen(self):
        conflict = ck.KnowledgeConflict([assertion(), assertion(state=STATE.UNSUPPORTED)])
        objects = (ALPHA, ck.KnowledgeScope(), ck.KnowledgeProvenance(),
                   assertion(), conflict, ck.KnowledgeRegistry([assertion()]))
        for obj in objects:
            for field in fields(obj):
                with self.subTest(cls=type(obj), field=field.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(obj, field.name, None)

    def test_collections_are_tuples(self):
        subject = replace(ALPHA, aliases=["A"])
        registry = ck.KnowledgeRegistry([assertion(), assertion(state=STATE.UNSUPPORTED)])
        for collection in (subject.aliases, registry.entries, registry.query(ALPHA, BETA),
                           registry.conflicts(), registry.conflicts()[0].assertions):
            self.assertIsInstance(collection, tuple)
            with self.assertRaises(AttributeError):
                collection.append(None)

    def test_pure_imports_and_no_execution_calls(self):
        tree = ast.parse(Path(ck.__file__).read_text(encoding="utf-8"))
        allowed = {"__future__", "dataclasses", "enum"}
        forbidden = {"eval", "exec", "open", "__import__", "compile",
                     "system", "popen", "run", "Popen", "socket", "urlopen",
                     "write_text", "write_bytes"}
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call):
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else node.func.attr if isinstance(node.func, ast.Attribute) else None)
                self.assertNotIn(name, forbidden)

    def test_operations_have_no_external_effects(self):
        # Import patch targets before blocking exec/open used by Python's importer.
        targets = ("subprocess.run", "subprocess.Popen", "os.system",
                   "socket.socket", "socket.create_connection", "urllib.request.urlopen",
                   "builtins.open", "builtins.eval", "builtins.exec")
        patches = [patch(target, side_effect=AssertionError("external effect"))
                   for target in targets]
        # Resolve/import targets first, so this measures registry operations only.
        import subprocess
        import socket
        import urllib.request
        self.assertIsNotNone(subprocess)
        self.assertIsNotNone(socket)
        self.assertIsNotNone(urllib.request)
        before = assertion()
        with ExitStack() as stack:
            for guard in patches:
                stack.enter_context(guard)
            registry = ck.KnowledgeRegistry([before])
            conflict_registry = registry.add(assertion(state=STATE.UNSUPPORTED))
            self.assertTrue(conflict_registry.has_conflict(ALPHA, BETA))
            self.assertEqual(len(conflict_registry.conflicts()), 1)
            self.assertIs(registry.state_for(ALPHA, BETA), STATE.SUPPORTED)
        self.assertEqual(before, assertion())
        self.assertEqual(registry.entries, (before,))

    def test_no_executable_or_scoring_fields(self):
        forbidden = {"command", "shell_command", "callback", "execute", "action",
                     "score", "confidence", "trust", "estimated_memory"}
        for cls in (ck.KnowledgeSubject, ck.KnowledgeScope, ck.KnowledgeProvenance,
                    ck.KnowledgeAssertion, ck.KnowledgeConflict, ck.KnowledgeRegistry):
            self.assertFalse({field.name for field in fields(cls)} & forbidden)

    def test_registry_ships_empty_without_evaluator_coupling(self):
        self.assertEqual(ck.KnowledgeRegistry().entries, ())
        self.assertFalse(hasattr(ck, "CompatibilityResult"))
        self.assertFalse(hasattr(ck, "evaluate"))
        self.assertFalse(any(isinstance(value, (ck.KnowledgeAssertion, ck.KnowledgeRegistry))
                             for value in vars(ck).values()))


if __name__ == "__main__":
    unittest.main()
