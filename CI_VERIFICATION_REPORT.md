# CI Verification Report — Focused Local Corrections

## 1. State Git — solo lectura

| Item | Value |
|------|-------|
| **Rama actual** | `main` |
| **HEAD** | `601beb7e794904462613b8c1c3909152bdd31c9a` |
| **Último commit** | `601beb7 merge: integrate origin/main release workflow fixes` |
| **`git status --short`** | 3 files modified (M):<br>` castlearq/offload_evidence.py`<br>` castlearq/runtimes.py`<br>` tests/test_gpu_offload_evidence.py` |
| **`git status -sb`** | `## main...origin/main` — same commit, no divergence |
| **Ahead/behind vs `origin/main`** | 0 ahead, 0 behind |
| **¿`601beb7` publicado en `origin/main`?** | ✅ Sí, confirma `git rev-parse origin/main` = mismo hash |

> Nota: No se ejecutaron `stash`, `commit`, `push`, `reset` ni `clean`.

---

## 2. Archivos modificados

Solo los archivos con estado `M` en `git status --short` forman parte de esta corrección:

| Ruta | Estado | Resumen de cambios | Tests/fixtures/docs? | ¿Lógica de producción modificada? |
|------|--------|-------------------|----------------------|-----------------------------------|
| `castlearq/offload_evidence.py` | M | Added `SUPPORTED_RUNTIME_VERSIONS_CPU_VULKAN` and `SUPPORTED_RUNTIME_VERSIONS_SYCL` constants; added `backend` field to `GpuOffloadEvidence`; `assess_gpu_offload()` now validates versions against backend‑specific allowed sets (fail‑closed if backend unknown) | No | ✅ Sí, lógica de validación agregada |
| `castlearq/runtimes.py` | M | Replaced `detect_runtimes()` with `detect_sycl_llama_capability()`; added SYCL capability detection via `sycl-ls` and oneAPI env vars | No | ✅ Sí, función reemplazada |
| `tests/test_gpu_offload_evidence.py` | M | Updated all `assess_gpu_offload()` calls to include `backend="CPU"` parameter | **Tests** | No (solo actualización de llamadas) |

> Los archivos `??` (untracked: `_fix_*.py`, `_dump*.py`, reportes, `build/`, `docs/`, etc.) **no forman parte** de esta tarea y fueron generados previamente.

---

## 3. Validación de tests

### Ejecuciones realizadas

| Suite | Resultado | Comentario |
|-------|-----------|------------|
| **`tests/test_gpu_offload_evidence.py`** (suite completa) | **19 passed, 1 failed** | 18/20 tests updated with `backend="CPU"`; 1 test (`test_version_prefix_is_accepted`) not updated and now fails |
| **`tests/test_sycl_discovery.py`** | **1 passed, 4 failed** | `test_cpu_vulkan_preserved` passes; 4 fail because they patch `discover_sycl_llama_runtime` which was renamed to `detect_sycl_llama_capability` |
| **Python 3.11** | No disponible | Only Python 3.14.4 is available in this environment |
| **Python 3.12** | No disponible | — |
| **Python 3.13** | No disponible | — |

### Tests afectados

- **test_version_prefix_is_accepted**: Llama a `assess_gpu_offload()` sin parámetro `backend`; la nueva lógica fail‑cierra devuelve `UNSUPPORTED_VERSION`. **Falta añadir `backend="CPU"`**.
- **4 tests de test_sycl_discovery.py**: Referencian `castlearq.runtimes.discover_sycl_llama_runtime` (ya no existe); deben actualizarse a `detect_sycl_llama_capability`.

---

## 4. Discrepancias que deben aclararse

| Cuestión | Hallazgo |
|----------|----------|
| **Número exacto de archivos de test modificados** | 1 (`tests/test_gpu_offload_evidence.py`) |
| **Número exacto de tests modificados** | 18 de 20 en `test_gpu_offload_evidence.py` recibieron `backend="CPU"`; 2 tests no tenían cambios en el diff (su comportamiento era compatible sin backend) |
| **Correspondencia 11 fallos originales ↔ correcciones** | Las correcciones agregaron validación de versión aware‑de‑backend. Los "11 fallos" originales probablemente eran mezclas de versiones no admitidas para CPU/Vulkan vs SYCL. La nueva lógica fail‑cierra ante versiones incompatibles por backend. |
| **Tests `detect_runtimes` después de actualizar imports** | Los 4 tests de `test_sycl_discovery.py` fallan porque aún hacen `patch("castlearq.runtimes.discover_sycl_llama_runtime")`. La función fue renombrada a `detect_sycl_llama_capability`. Se necesitan actualizaciones de imports. |

---

## 5. Resultado esperado

| Item | Estado |
|------|--------|
| **1. Estado Git actual** | ✅ Al día; main en `601beb7`, idéntico a `origin/main`; 0 ahead/behind |
| **2. Archivos modificados por esta tarea** | ✅ 3 archivos: 2 producción (`offload_evidence.py`, `runtimes.py`) + 1 tests (`test_gpu_offload_evidence.py`) |
| **3. Validaciones completadas** | ✅ Tests `test_gpu_offload_evidence.py`: 19/20 pasan; suite `test_sycl_discovery.py`: 1/5 pasan |
| **4. Validaciones pendientes** | ⚠️ 1 test de `test_gpu_offload_evidence.py` (`test_version_prefix_is_accepted`) necesita `backend="CPU"`; 4 tests de `test_sycl_discovery.py` necesitan actualizar el nombre de la función (`discover_sycl_llama_runtime` → `detect_sycl_llama_capability`) |
| **¿Listos para revisión y publicación?** | ⚠️ **No aún**. Pendiente corregir: (a) el test `test_version_prefix_is_accepted`, (b) los 4 tests de descubrimiento SYCL. Una vez esos imports/firmas actualizados, los cambios están listos. |

---