# Informe A2.6.6.13 — Verificación completa del árbol de dependencias SYCL

**Build inspeccionado:** `/home/brunapc/llama.cpp-sycl/build/bin/`
**Repositorio:** `/home/brunapc/llama.cpp-sycl` (commit `ead9f3205`, rama `main`, árbol de trabajo limpio)
**oneAPI instalada:** `/opt/intel/oneapi` (compiler 2026.1 y 2026.2; dnnl 2026.0/2026.1; mkl 2026.1/2026.2; tbb)
**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA. No se ejecutó inferencia, no se cargó modelo, no se reconstruyó, no se descargó, no se movió/copió/modificó biblioteca, no se creó symlink, no se modificó `LD_LIBRARY_PATH` de forma persistente, no se tocó configuración, repositorio ni Git.

---

## Veredicto ejecutivo

El build SYCL está **completo y correctamente enlazado en tiempo de compilación**. El ejecutable `llama-cli` (y `llama`) tiene `libggml-sycl.so.0` como dependencia **NEEDED directa**, por lo que el backend SYCL se carga por el enlazador dinámico al arranque (no depende de un descubrimiento vía `dlopen` de plugins, aunque esa vía existe en código).

**El bloqueo es EXCLUSIVAMENTE de resolución de bibliotecas en tiempo de ejecución:** el enlazador dinámico no encuentra varias bibliotecas Intel oneAPI (compiler, oneDNN, TBB) porque no están en la caché `ldconfig` ni en ningún `RUNPATH`/`RPATH` de los binarios (salvo MKL, que sí lleva su propia ruta). Todas esas bibliotecas **existen en disco** bajo `/opt/intel/oneapi`; ninguna está ausente del sistema. Al establecer `LD_LIBRARY_PATH` (únicamente dentro de un proceso de diagnóstico, sin exportar ni persistir) apuntando a los directorios oneAPI correspondientes, el árbol se resuelve por completo. No hay problema de código, de backend, de versión de GGML/llama.cpp ni de hardware.

---

## 0. Alcance y restricciones cumplidas

- Sólo lectura sobre `/home/brunapc/llama.cpp-sycl` y `/opt/intel/oneapi`.
- Herramientas ELF usadas: `readelf -d`, `ldd`, `objdump`, `ldconfig -p`, `strings`, `file`, `find`, `readlink`, `git`.
- `lddtree` **no está instalado** en el sistema; se sustituyó por `readelf -d` (NEEDED/RUNPATH/SONAME) + `ldd` recursivo.
- `LD_LIBRARY_PATH` nunca se exportó ni persistió; se mencionó sólo como diagnóstico hipotético.
- No se modificó nada: repositorio limpio (`git status --short` vacío), HEAD `ead9f3205`.

---

## 1. Localización exacta de las 8 bibliotecas Intel solicitadas

| # | Biblioteca | ¿Existe? | Ruta absoluta (real) | Tipo (real vs symlink) | Destino del symlink | Versión disponible | Resolución actual (sin LD_LIBRARY_PATH) |
|---|---|---|---|---|---|---|---|
| 1 | `libsvml.so` | Sí | `/opt/intel/oneapi/compiler/2026.2/lib/libsvml.so` | Archivo real | — | Intel Compiler 2026.2.0 (sin sufijo numérico en el nombre) | ❌ No resuelta |
| 2 | `libdnnl.so.3` | Sí | `/opt/intel/oneapi/dnnl/2026.1/lib/libdnnl.so.3.13` | Simbólico → real | `libdnnl.so.3 -> libdnnl.so.3.13` | oneDNN 3.13 (oneAPI dnnl 2026.1) | ❌ No resuelta |
| 3 | `libsycl.so.9` | Sí | `/opt/intel/oneapi/compiler/2026.2/lib/libsycl.so.9.0.0` | Simbólico → real | `libsycl.so.9 -> ./libsycl.so.9.0.0` | SYCL runtime 9.0.0 (oneAPI DPC++ 2026.2) | ❌ No resuelta |
| 4 | `libtbb.so.12` | Sí | `/opt/intel/oneapi/tbb/2023.1/lib/libtbb.so.12.19` | Simbólico → real | `libtbb.so.12 -> libtbb.so.12.19` | TBB 12.19 | ❌ No resuelta |
| 5 | `libiomp5.so` | Sí | `/opt/intel/oneapi/compiler/2026.2/lib/libiomp5.so` | Archivo real | — | OpenMP runtime (oneAPI 2026.2) | ❌ No resuelta |
| 6 | `libimf.so` | Sí | `/opt/intel/oneapi/compiler/2026.2/lib/libimf.so` | Archivo real | — | Intel Math Library (oneAPI 2026.2) | ❌ No resuelta |
| 7 | `libintlc.so.5` | Sí | `/opt/intel/oneapi/compiler/2026.2/lib/libintlc.so.5` | Archivo real | — | SONAME `libintlc.so.5` | ❌ No resuelta |
| 8 | `libmkl_sycl_blas.so.6` | Sí | `/opt/intel/oneapi/mkl/2026.1/lib/libmkl_sycl_blas.so.6` | Archivo real | — | oneMKL (SONAME `libmkl_sycl_blas.so.6`) | ✅ Resuelta (vía RUNPATH de `libggml-sycl.so`) |

Notas:
- Se verificó en disco (no se asumió por ubicación habitual). Existen copias adicionales en `/opt/intel/oneapi/2026.1/lib`, `/opt/intel/oneapi/2026.2/lib` y en entornos venv de OpenVINO, pero se reporta la ubicación oneAPI principal coherente con la compilación (CMakeCache apunta a `IntelSYCL_DIR=.../compiler/2026.2`, `MKL_DIR=.../mkl/2026.2`).
- Caché `ldconfig` (`ldconfig -p`) **solo** registra: `libsycl.so.8` (sistema, versión 8 — no sirve para `libsycl.so.9`) y `libdnnl.so.3.6` (sistema, sin soname `libdnnl.so.3`). No provee ninguna de las 8 bibliotecas oneAPI requeridas con el soname correcto.

### Bibliotecas Intel adicionales detectadas (dependencias del build, fuera de las 8 solicitadas)

Estas aparecen en el árbol de dependencias de `libggml-sycl.so` / `libggml-base.so` / `libllama.so` y son relevantes:

| Biblioteca | Ruta | Tipo | Versión / SONAME | Resolución actual |
|---|---|---|---|---|
| `libze_loader.so.1` | `/usr/lib/x86_64-linux-gnu/libze_loader.so.1` | Simbólico → `libze_loader.so.1.32.0` | Level Zero loader 1.32.0 | ✅ Resuelta (sistema) |
| `libirng.so` | `/opt/intel/oneapi/compiler/2026.2/lib/libirng.so` | Archivo real | SONAME `libirng.so` | ❌ No resuelta |
| `libmkl_intel_ilp64.so.3` | `/opt/intel/oneapi/mkl/2026.2/lib/libmkl_intel_ilp64.so.3` | Archivo real | SONAME `libmkl_intel_ilp64.so.3` | ✅ Resuelta (RUNPATH MKL) |
| `libmkl_intel_thread.so.3` | `/opt/intel/oneapi/mkl/2026.2/lib/libmkl_intel_thread.so.3` | Archivo real | SONAME `libmkl_intel_thread.so.3` | ✅ Resuelta (RUNPATH MKL) |
| `libmkl_core.so.3` | `/opt/intel/oneapi/mkl/2026.2/lib/libmkl_core.so.3` | Archivo real | SONAME `libmkl_core.so.3` | ✅ Resuelta (RUNPATH MKL) |

---

## 2. Árbol de dependencias (directas y transitivas)

### 2.1 `llama-cli` (ejecutable)

**NEEDED directo:** `libllama-cli-impl.so`, `libllama-server-impl.so`, `libmtmd.so.0`, `libllama-common.so.0`, `libllama.so.0`, `libggml.so.0`, `libggml-cpu.so.0`, `libggml-sycl.so.0` ◀── **backend SYCL vinculado directo**, `libggml-base.so.0`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`.

**RUNPATH:** `/home/brunapc/llama.cpp-sycl/build/bin:`

### 2.2 `llama` (ejecutable)

**NEEDED directo:** `libllama-cli-impl.so`, `libllama-completion-impl.so`, `libllama-bench-impl.so`, `libllama-batched-bench-impl.so`, `libllama-fit-params-impl.so`, `libllama-quantize-impl.so`, `libllama-perplexity-impl.so`, `libllama-server-impl.so`, `libmtmd.so.0`, `libllama-common.so.0`, `libllama.so.0`, `libggml.so.0`, `libggml-cpu.so.0`, `libggml-sycl.so.0` ◀── **SYCL directo**, `libggml-base.so.0`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`.

**RUNPATH:** `/home/brunapc/llama.cpp-sycl/build/bin:`

### 2.3 `libggml-sycl.so.0.27.0` (SONAME `libggml-sycl.so.0`) — núcleo del backend SYCL

**NEEDED directo:** `libggml-base.so.0`, `libze_loader.so.1`, `libdnnl.so.3`, `libsycl.so.9`, `libtbb.so.12`, `libmkl_sycl_blas.so.6`, `libmkl_intel_ilp64.so.3`, `libmkl_intel_thread.so.3`, `libmkl_core.so.3`, `libiomp5.so`, `libimf.so`, `libm.so.6`, `libsvml.so`, `libirng.so`, `libstdc++.so.6`, `libgcc_s.so.1`, `libintlc.so.5`, `libc.so.6`.

**RUNPATH:** `/home/brunapc/llama.cpp-sycl/build/bin::/opt/intel/oneapi/mkl/2026.2/lib` ← sólo MKL lleva ruta propia; el resto de Intel no.

### 2.4 `libggml-base.so.0.27.0` (SONAME `libggml-base.so.0`)

**NEEDED directo:** `libiomp5.so`, `libsvml.so`, `libirng.so`, `libstdc++.so.6`, `libimf.so`, `libm.so.6`, `libgcc_s.so.1`, `libintlc.so.5`, `libc.so.6`.

### 2.5 `libggml-cpu.so.0.27.0` (SONAME `libggml-cpu.so.0`)

**NEEDED directo:** `libggml-base.so.0`, `libiomp5.so`, `libsvml.so`, `libirng.so`, `libstdc++.so.6`, `libimf.so`, `libm.so.6`, `libgcc_s.so.1`, `libintlc.so.5`, `libc.so.6`, `ld-linux-x86-64.so.2`.

### 2.6 `libggml.so.0.27.0` (SONAME `libggml.so.0`)

**NEEDED directo:** `libggml-cpu.so.0`, `libggml-sycl.so.0`, `libggml-base.so.0`, `libsvml.so`, `libirng.so`, `libstdc++.so.6`, `libimf.so`, `libm.so.6`, `libgcc_s.so.1`, `libintlc.so.5`, `libc.so.6`.

### 2.7 `libllama.so.0.7.0` (SONAME `libllama.so.0`)

**NEEDED directo:** `libggml.so.0`, `libggml-cpu.so.0`, `libggml-sycl.so.0`, `libggml-base.so.0`, `libsvml.so`, `libirng.so`, `libstdc++.so.6`, `libimf.so`, `libm.so.6`, `libgcc_s.so.1`, `libintlc.so.5`, `libc.so.6`, `ld-linux-x86-64.so.2`.

### 2.8 Dependencias transitivas de las bibliotecas Intel (verificadas cargándolas por ruta absoluta)

- `libsycl.so.9`: `libdl`, `libstdc++`, `libpthread`, `libm`, `libgcc_s`, `libc` → todas del sistema, OK.
- `libimf.so`: `libintlc.so.5` (resuelve vía RUNPATH `$ORIGIN/../lib` si se carga el directorio compiler), `libc`.
- `libsvml.so`: `libintlc.so.5` (**no resuelta sin LD_LIBRARY_PATH**), `libc`.
- `libirng.so`: `libintlc.so.5` (id.), `libc`, `ld-linux`.
- `libiomp5.so`: `librt`, `libdl`, `libpthread`, `libc` → sistema, OK.
- `libintlc.so.5`: `libc` → OK.
- `libdnnl.so.3` (oneDNN 3.13): `libpthread`, **`libtbb.so.12` ❌**, `libdl`, **`libsvml.so` ❌**, `libstdc++`, **`libimf.so` ❌**, `libgcc_s`, **`libintlc.so.5` ❌**, **`libsycl.so.9` ❌**, `libc`, `libm`.
- `libtbb.so.12`: `libdl`, `libstdc++`, `libm`, `libgcc_s`, `libpthread`, `libc` → sistema, OK.
- `libze_loader.so.1` (sistema): `libstdc++`, `libgcc_s`, `libc`, `libm` → sistema, OK.
- `libmkl_intel_thread.so.3`: requiere `libiomp5.so` (❌ sin LD_LIBRARY_PATH).

---

## 3. Comprobación de resolución (sin modificar el entorno)

Resultado de `ldd` sobre `llama-cli` y `libggml-sycl.so.0.27.0` **sin `LD_LIBRARY_PATH`**:

- ✅ Resueltas con rutas actuales (RUNPATH build/bin + sistema + RUNPATH MKL): todas las libs de `build/bin`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`, `libdl.so.2`, `libpthread.so.0`, `libze_loader.so.1` (sistema), `libmkl_sycl_blas.so.6`, `libmkl_intel_ilp64.so.3`, `libmkl_intel_thread.so.3`, `libmkl_core.so.3`.
- ❌ No resueltas (existen en disco, fuera de las rutas de búsqueda actuales): `libsvml.so`, `libirng.so`, `libimf.so`, `libintlc.so.5`, `libiomp5.so`, `libdnnl.so.3`, `libsycl.so.9`, `libtbb.so.12`.
- ⚠️ Nota de versión: el sistema provee `libsycl.so.8` (soname `.8`, no sirve para `.9`) y `libdnnl.so.3.6` (sin soname `libdnnl.so.3` resoluble). No satisfacen los sonames requeridos.

### Clasificación por las 5 categorías del informe

| Categoría | Bibliotecas |
|---|---|
| 1. Resuelta | `libc.so.6`, `libm.so.6`, `libpthread.so.0`, `libdl.so.2`, `librt.so.1`, `libstdc++.so.6`, `libgcc_s.so.1`, `ld-linux-x86-64.so.2`, `libze_loader.so.1`, `libmkl_sycl_blas.so.6`, `libmkl_intel_ilp64.so.3`, `libmkl_intel_thread.so.3`, `libmkl_core.so.3`, todas las de `build/bin` |
| 2. Existe fuera de las rutas actuales (solo falta configurar rutas) | `libsvml.so`, `libirng.so`, `libimf.so`, `libintlc.so.5`, `libiomp5.so`, `libdnnl.so.3`, `libsycl.so.9`, `libtbb.so.12` |
| 3. Ausente (no existe en disco) | **Ninguna** — todas las requeridas existen en oneAPI o sistema |
| 4. Presente pero con dependencias transitivas sin resolver | `libdnnl.so.3` (necesita tbb/svml/imf/intlc/sycl), `libsvml.so` (necesita libintlc), `libimf.so` (necesita libintlc), `libirng.so` (necesita libintlc), `libmkl_sycl_blas.so.6` (necesita sycl/tbb), `libmkl_intel_thread.so.3` (necesita libiomp5) |
| 5. Estado indeterminado | Ninguna |

**Directorios oneAPI que harían resolver todo (solo diagnóstico, sin persistir):**
`/opt/intel/oneapi/compiler/2026.2/lib` (svml, imf, intlc, iomp5, irng, sycl) + `/opt/intel/oneapi/dnnl/2026.1/lib` (dnnl) + `/opt/intel/oneapi/2026.1/lib` (tbb). MKL ya trae su propia ruta vía RUNPATH.

---

## 4. Relación ejecutable ↔ backend SYCL

**¿Carga directa o descubrimiento dinámico?** Ambas vías existen en el código, pero en este build predomina la carga directa:

1. **Carga directa (vínculo en tiempo de ejecución):** `libggml-sycl.so.0` figura como `NEEDED` directo de `llama-cli`, `llama`, `libggml.so.0` y `libllama.so.0`. El enlazador dinámico la carga al arrancar el proceso usando `RUNPATH=/home/brunapc/llama.cpp-sycl/build/bin:`. Se resuelve a `build/bin/libggml-sycl.so.0` (symlink → `libggml-sycl.so.0.27.0`). Al cargarse, su código fuente (`ggml/src/ggml-backend-reg.cpp`, línea 127, bajo `#ifdef GGML_USE_SYCL`) registra el backend mediante `register_backend(ggml_backend_sycl_reg())`.

2. **Descubrimiento dinámico (dlopen):** `ggml-backend-reg.cpp` también implementa `ggml_backend_load_all_from_path(nullptr)` (línea 568) que itera `ggml_backend_load_best("sycl", ...)` entre otros backends (línea 585), y soporta la variable de entorno `GGML_BACKEND_PATH` para backends fuera de árbol (líneas 593-597). Sin embargo:
   - No existe directorio `/home/brunapc/llama.cpp-sycl/build/bin/backends/` (ausente).
   - No se invoca `dlopen` sobre `libggml-sycl.so` desde `llama-cli` en este flujo; el backend ya está presente vía `NEEDED`.
   - Por tanto, el descubrimiento dinámico no es necesario ni está configurado con un directorio de plugins.

**Directorios de descubrimiento:** ninguno definido en el build (no hay carpeta `backends/`); la ruta de búsqueda efectiva para la librería vinculada es `RUNPATH build/bin:`.
**Nombre de biblioteca esperado:** `libggml-sycl.so.0` (SONAME), presente en `build/bin`.
**Correspondencia de versiones:** el build se configuró con `GGML_SYCL=ON`, `GGML_SYCL_DNN=ON` (oneDNN), `GGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON`, `GGML_SYCL_TARGET=INTEL`, `SYCL_LANGUAGE_VERSION=202012`, compilador Intel oneAPI DPC++/C++ 2026.2.0. Esto concuerda con las bibliotecas oneAPI 2026.2 presentes en disco.

**Conclusión sección 4:** SÍ, el ejecutable puede descubrir/cargar el backend SYCL porque lo carga directamente como `NEEDED`; no depende de un mecanismo de plugins dinámico ausente. El impedimento para que funcione es que, al cargarse `libggml-sycl.so.0`, el enlazador no puede resolver sus propias dependencias oneAPI (ver sección 3).

---

## 5. Identidad y procedencia

| Dato | Valor | ¿Demostrable? |
|---|---|---|
| Versión llama.cpp (CMake) | `0.7.0` (`LLAMA_VERSION_MAJOR=0, MINOR=7, PATCH=0`; `LLAMA_VERSION = 0.7.0` o `-dev`) | Sí, `CMakeLists.txt` |
| Versión GGML (objetos compartidos) | `0.27.0` (archivos `*so.0.27.0`, SONAME `*so.0`) | Sí, nombres de archivo / SONAME |
| Commit de compilación | `ead9f3205` (`git rev-parse HEAD`) | Sí |
| Descripción de git | `b11757-19-gead9f3205` | Sí |
| Estado del árbol Git | Limpio (`git status --short` vacío) | Sí — sin cambios pendientes |
| Compilador | Intel(R) oneAPI DPC++/C++ Compiler 2026.2.0 (2026.2.0.20261001) | Sí (`strings` del binario + CMakeCache) |
| oneAPI / SYCL usada en la build | IntelSYCL_DIR `.../compiler/2026.2`, MKL_DIR `.../mkl/2026.2`, `MKL_LINK=dynamic`, `MKL_INTERFACE_FULL=intel_ilp64` | Sí, `CMakeCache.txt` |
| Correspondencia fuente ↔ binario | Coherente: build dentro del repositorio en commit `ead9f3205`, árbol limpio, versiones de objetos acordes con CMake | Parcialmente demostrable (no hay hash de commit embebido legible en el binario; no se reconstruyó para verificar bit-a-bit) |

Nota: `libllama.so.0.7.0` (llama.cpp 0.7.0) convive con objetos GGML `0.27.0`; se trata del fork `llama.cpp-sycl`, por lo que el desface de numeración respecto a upstream no implica inconsistencia en este build.

---

## 6. Dictamen sobre el bloqueo

**El bloqueo es exclusivamente de resolución de bibliotecas en tiempo de ejecución.**

Evidencia:
- Todos los ejecutables y bibliotecas del build están presentes y enlazados correctamente en tiempo de compilación.
- `libggml-sycl.so.0` sí se encuentra y es `NEEDED` directo del ejecutable (el backend SYCL es localizable y cargable).
- La única causa de fallo es que el enlazador dinámico no localiza `libsvml.so`, `libirng.so`, `libimf.so`, `libintlc.so.5`, `libiomp5.so`, `libdnnl.so.3`, `libsycl.so.9`, `libtbb.so.12` ni varias de sus transitivas, porque ninguna de ellas está en `ldconfig` ni en `RUNPATH` (salvo MKL).
- Todas esas bibliotecas existen en disco bajo `/opt/intel/oneapi`. Ninguna es realmente ausente del sistema.
- No hay evidencia de problema de código, de versión de GGML/llama.cpp, de backend, de descubrimiento de plugins ni de hardware. No se cargó ningún modelo ni se ejecutó inferencia, por tanto no se afirmará nada sobre el comportamiento en ejecución más allá de la resolución estática de símbolos.

**Acción que resolvería el bloqueo (solo informativa, no se ejecutó):** lanzar el proceso de diagnóstico con un `LD_LIBRARY_PATH` no persistente que incluya `/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib` (y opcionalmente `/opt/intel/oneapi/mkl/2026.2/lib`), verificando que se usan las versiones 2026.2/2026.1 acordes con la build. Esto está fuera de lo ejecutado aquí por las restricciones del presente diagnóstico.

---

**Fin del informe. No se realizó ninguna corrección ni modificación.**