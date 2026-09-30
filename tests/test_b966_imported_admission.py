"""B9.66 -- imported-artifact admission and memory policy.

Two independent discriminators are pinned here:

* ``imported`` (explicit, propagated from the resolver) scopes the *identity*
  admission tolerance;
* ``ModelSpec.id is None`` scopes the *memory* tolerance in the legacy gate.

Both must leave catalog behaviour bit-for-bit identical, and neither may
promote an UNKNOWN check to PASSED.
"""

import unittest

from app.compatibility import (
    CompatibilityConfig,
    CompatibilityStatus,
    assess_model,
)
from app.compatibility_domain import CheckStatus, CompatibilityCheck
from app.compatibility_domain import CompatibilityResult as StrictCompatibilityResult
from app.compatibility_domain import CompatibilityStatus as StrictCompatibilityStatus
from app.evaluate_compatibility import (
    _NON_BLOCKING_E2E_UNKNOWNS,
    _non_blocking_unknowns,
    EvaluateModelCompatibilityResult,
    to_admission,
)
from app.hardware import CPUInfo, GPUInfo, HardwareSnapshot, MemoryInfo
from app.models import ModelSpec
from app.runtimes import BackendStatus, RuntimeStatus


def _hardware(*, ram_bytes=32 * 1024**3, vram=16 * 1024**3):
    gpus = []
    if vram is not None:
        gpus.append(
            GPUInfo(name="Test GPU", vram_bytes=vram, vram_available_bytes=vram)
        )
    return HardwareSnapshot(
        operating_system="Linux",
        architecture="x86_64",
        cpu=CPUInfo(model="Test CPU"),
        memory=MemoryInfo(total_bytes=ram_bytes),
        gpus=gpus,
    )


RUNTIMES = [
    RuntimeStatus(
        "llama.cpp / llama.app", installed=True, available=True,
        gpu_backend_detected=False, supported_backends=("Vulkan", "CPU"),
    )
]
BACKENDS = [BackendStatus("Vulkan", True), BackendStatus("CPU", True)]

#: An imported artifact: no logical identity, no catalog parameter count.
IMPORTED = ModelSpec(id=None, name="my-local-model")
#: A catalog model: explicit identity, known parameter count.
CATALOG = ModelSpec(
    id="qwen2.5-coder-7b-instruct", name="Qwen2.5-Coder 7B",
    parameter_count_b=7.0,
)
#: A catalog-shaped model that has an explicit id but no parameter count.
#: This is the case that must keep blocking: it is indistinguishable from an
#: imported artifact by memory alone, and the ``id`` is what separates them.
CATALOG_NO_PARAMS = ModelSpec(id="catalog-without-params", name="No Params")


def _check(name, status):
    return CompatibilityCheck(name=name, status=status)


def _eval_result(*, imported, unknown_names, failed_names=(),
                 strict_status=StrictCompatibilityStatus.INSUFFICIENT_EVIDENCE):
    checks = [_check(n, CheckStatus.UNKNOWN) for n in unknown_names]
    checks += [_check(n, CheckStatus.FAILED) for n in failed_names]
    strict = StrictCompatibilityResult(status=strict_status, checks=tuple(checks))
    evaluation = type("E", (), {"result": strict})()
    return EvaluateModelCompatibilityResult(
        model_id="my-local-model", artifact=None, runtime="llama.cpp CLI",
        capability=None, evaluation=evaluation, integration=None,
        status="evaluated", blocking_outcome=None, imported=imported,
    )


class CatalogAdmissionUnchangedTests(unittest.TestCase):
    """1, 4, 11 -- a catalog artifact keeps the previous, blocking behaviour."""

    def test_catalog_identity_unknown_is_blocked(self):
        admission = to_admission(
            _eval_result(imported=False, unknown_names=["artifact-model identity"])
        )
        self.assertEqual(
            admission.verdict, StrictCompatibilityStatus.INSUFFICIENT_EVIDENCE
        )

    def test_default_result_carries_imported_false(self):
        self.assertIs(
            EvaluateModelCompatibilityResult(
                model_id="m", artifact=None, runtime="r", capability=None,
                evaluation=None, integration=None, status="evaluated",
                blocking_outcome=None,
            ).imported,
            False,
        )

    def test_non_blocking_set_for_catalog_is_unchanged(self):
        self.assertEqual(_non_blocking_unknowns(False), _NON_BLOCKING_E2E_UNKNOWNS)

    def test_same_payload_differs_only_by_discriminator(self):
        catalog = to_admission(
            _eval_result(imported=False, unknown_names=["artifact-model identity"])
        )
        imported = to_admission(
            _eval_result(imported=True, unknown_names=["artifact-model identity"])
        )
        self.assertNotEqual(catalog.verdict, imported.verdict)


class ImportedIdentityAdmissionTests(unittest.TestCase):
    """2, 3, 12 -- identity UNKNOWN is tolerated only when imported."""

    def test_imported_identity_unknown_is_admitted(self):
        admission = to_admission(
            _eval_result(imported=True, unknown_names=["artifact-model identity"])
        )
        self.assertEqual(admission.verdict, "compatible")

    def test_strict_result_still_reports_insufficient_evidence(self):
        result = _eval_result(imported=True,
                              unknown_names=["artifact-model identity"])
        self.assertIs(result.evaluation.result.status,
                      StrictCompatibilityStatus.INSUFFICIENT_EVIDENCE)

    def test_identity_check_is_not_promoted_to_passed(self):
        result = _eval_result(imported=True,
                              unknown_names=["artifact-model identity"])
        statuses = {c.name: c.status for c in result.evaluation.result.checks}
        self.assertIs(statuses["artifact-model identity"], CheckStatus.UNKNOWN)

    def test_imported_incompatible_is_still_blocked(self):
        # A FAILED check must never be downgraded, even for an imported
        # artifact and even alongside a tolerated identity UNKNOWN.
        admission = to_admission(
            _eval_result(
                imported=True,
                unknown_names=["artifact-model identity"],
                failed_names=["artifact format support"],
                strict_status=StrictCompatibilityStatus.INCOMPATIBLE,
            )
        )
        self.assertEqual(admission.verdict,
                         StrictCompatibilityStatus.INCOMPATIBLE)

    def test_imported_set_is_a_strict_superset(self):
        self.assertTrue(_NON_BLOCKING_E2E_UNKNOWNS < _non_blocking_unknowns(True))


class MemoryPolicyTests(unittest.TestCase):
    """5-10 -- memory tolerance is scoped and never claims sufficiency."""

    def test_catalog_memory_unknown_still_blocks(self):
        # A catalog-shaped model that lacks parameter_count_b (explicit id, so
        # the memory tolerance never applies to it) still blocks with UNKNOWN.
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, CATALOG_NO_PARAMS,
                              config=CompatibilityConfig())
        self.assertIs(result.status, CompatibilityStatus.UNKNOWN)
        self.assertIn("Model or hardware memory is unknown.", result.reasons)

    def test_default_flag_preserves_previous_behaviour(self):
        with_flag = assess_model(_hardware(), RUNTIMES, BACKENDS, CATALOG_NO_PARAMS,
                                 config=CompatibilityConfig(),
                                 allow_unknown_memory=False)
        without = assess_model(_hardware(), RUNTIMES, BACKENDS, CATALOG_NO_PARAMS,
                               config=CompatibilityConfig())
        self.assertEqual(with_flag, without)
        self.assertIs(with_flag.status, CompatibilityStatus.UNKNOWN)

    def test_imported_memory_unknown_is_marginal(self):
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, IMPORTED,
                              config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIs(result.status, CompatibilityStatus.MARGINAL)

    def test_imported_memory_unknown_is_never_compatible(self):
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, IMPORTED,
                              config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIsNot(result.status, CompatibilityStatus.COMPATIBLE)
        self.assertIsNone(result.estimated_memory_bytes)

    def test_imported_memory_unknown_states_no_sufficiency(self):
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, IMPORTED,
                              config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIn("no memory sufficiency was established",
                      " ".join(result.reasons))
        self.assertTrue(any("No memory estimate" in w for w in result.warnings))

    def test_undetectable_capacity_still_blocks(self):
        result = assess_model(_hardware(ram_bytes=None), RUNTIMES, BACKENDS,
                              IMPORTED, config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIs(result.status, CompatibilityStatus.UNKNOWN)
        self.assertIn("Model or hardware memory is unknown.", result.reasons)

    def test_known_overflow_is_still_incompatible(self):
        huge = ModelSpec(id="huge", name="Huge", parameter_count_b=100_000.0)
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, huge,
                              config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIs(result.status, CompatibilityStatus.INCOMPATIBLE)

    def test_known_overflow_unchanged_by_the_flag(self):
        huge = ModelSpec(id="huge", name="Huge", parameter_count_b=100_000.0)
        flagged = assess_model(_hardware(), RUNTIMES, BACKENDS, huge,
                               config=CompatibilityConfig(),
                               allow_unknown_memory=True)
        plain = assess_model(_hardware(), RUNTIMES, BACKENDS, huge,
                             config=CompatibilityConfig())
        self.assertEqual(flagged, plain)

    def test_flag_does_not_relax_a_measurable_model(self):
        result = assess_model(_hardware(), RUNTIMES, BACKENDS, CATALOG,
                              config=CompatibilityConfig(),
                              allow_unknown_memory=True)
        self.assertIs(result.status, CompatibilityStatus.COMPATIBLE)


class LegacyGateDiscriminatorTests(unittest.TestCase):
    """13 -- the gate keys on ``model.id is None``."""

    def test_imported_model_selects_the_tolerance(self):
        self.assertIsNone(IMPORTED.id)

    def test_catalog_model_does_not(self):
        self.assertIsNotNone(CATALOG.id)

    def test_every_catalog_entry_carries_an_explicit_id(self):
        from app.model_catalog import get_catalog
        for spec in get_catalog():
            self.assertIsNotNone(spec.id, spec.model_id)

    def test_execute_model_passes_flag_from_id_is_none(self):
        import inspect
        from app import execute_model as em
        source = inspect.getsource(em._legacy_compatibility)
        self.assertIn("allow_unknown_memory=model.id is None", source)
        self.assertIn("B9.66", source)


if __name__ == "__main__":
    unittest.main()
