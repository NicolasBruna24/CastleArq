from pathlib import Path

p = Path("/home/brunapc/LocalAI Hub/castlearq/run_service.py")
t = p.read_text(encoding="utf-8")
old = """    capability = (
        deps.capability if deps.capability is not None else detect_llama_capability()
    )"""
new = """    capability = (
        deps.capability if deps.capability is not None else detect_llama_capability()
    )
    if requested_backend == "SYCL" and deps.capability is None:
        sycl_cap = detect_sycl_llama_capability(
            executable_path=os.environ.get("CASTLEARQ_SYCL_RUNTIME"),
            setvars_path=os.environ.get("CASTLEARQ_SYCL_SETVARS"),
        )
        if not sycl_cap.available:
            raise RunPreparationFailedError(
                "SYCL runtime is not available: " + (sycl_cap.reason or "unknown")
            )
        capability = sycl_cap"""
assert t.count(old) == 2, t.count(old)
t2 = t.replace(old, new, 1)  # only first occurrence (run_once)
p.write_text(t2, encoding="utf-8")
print("ok")
