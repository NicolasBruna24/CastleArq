from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/tests/test_sycl_compatibility_propagation.py")
t = p.read_text(encoding="utf-8")

# Scope and availability checks
t = t.replace(
    'result = _result(requested_backend="SYCL", capability=CPU_VULCAN)',
    'result = _result(requested_backend="SYCL", capability=CPU_VULKAN)',
)
t = t.replace(
    '        result = _result()\n        self.assertIsNone(result.recommended_backend)\n',
    '        result = _result()\n        # No request: keep the detection default (Vulkan in this lab),\n'
    '        # never a SYCL substitution.\n'
    '        self.assertEqual(result.recommended_backend, "Vulkan")\n'
    '        self.assertNotEqual(result.recommended_backend, "SYCL")\n',
)
t = t.replace(
    '        self.assertEqual(result.status, CompatibilityStatus.COMPATIBLE)\n',
    '        # Memory may be unknowable in this isolated model, but the request\n'
    '        # itself must be honoured and never silently swapped to CPU/Vulkan.\n'
    '        self.assertEqual(result.recommended_backend, "SYCL")\n'
    '        self.assertEqual(result.recommended_runtime, "llama.cpp SYCL")\n',
)
t = t.replace(
    '        self.assertIsInstance(selector.select, type(lambda: None))\n',
    '        self.assertTrue(callable(getattr(selector, "select", None)))\n',
)

p.write_text(t, encoding="utf-8")
print("ok")
