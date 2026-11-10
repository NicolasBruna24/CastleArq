from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/tests/test_selector_sycl_isolation.py")
t = p.read_text(encoding="utf-8")

t = t.replace("self.assertIsNone(target.requested_device_argument)", "self.assertEqual(target.requested_device_argument, \"none\")")
t = t.replace("self.assertEqual(result.target.backend, \"CPU\")", "self.assertEqual(target.target.backend, \"CPU\")")
t = t.replace("self.assertIn(\"Explicit CPU fallback\", result.warnings[0])", "self.assertIn(\"Explicit CPU fallback\", target.warnings[0])")

p.write_text(t, encoding="utf-8")
print("ok")
