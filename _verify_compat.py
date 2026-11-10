import os
from castlearq.runtimes import detect_sycl_llama_capability

c = detect_sycl_llama_capability(
    executable_path=os.environ.get("CASTLEARQ_SYCL_RUNTIME", "/home/brunapc/llama.cpp-sycl/build/bin/llama-cli"),
    setvars_path=os.environ.get("CASTLEARQ_SYCL_SETVARS", "/opt/intel/oneapi/setvars.sh"),
)
print("name:", c.name)
print("supported_backends:", c.supported_backends)
print("backend_arguments:", c.backend_arguments)
print("compatibility_names:", c.compatibility_names)
print("supports_runtime_name(llama.cpp / llama.app):", c.supports_runtime_name("llama.cpp / llama.app"))
print("supports_runtime_name(llama.cpp):", c.supports_runtime_name("llama.cpp"))
