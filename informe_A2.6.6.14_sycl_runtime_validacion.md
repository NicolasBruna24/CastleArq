# Informe A2.6.6.14 — Validación de carga e inicialización del runtime SYCL

**Ejecutable inspeccionado:** `/home/brunapc/llama.cpp-sycl/build/bin/llama-cli`
**Variable de entorno (solo proceso de diagnóstico, no persistente):**
`LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib`
**Fecha del diagnóstico:** 11/01/2026
**Modalidad:** SOLO LECTURA. Sin inferencia, sin carga de modelos, sin reconstrucción, sin modificación persistente del entorno.

---

## 1. Resultado de `--version`

Comando ejecutado:
```
env LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib' /home/brunapc/llama.cpp-sycl/build/bin/llama-cli --version
```

| Campo | Valor |
|---|---|
| Código de salida | **0** (éxito) |
| Versión completa | `0.7.0-dev (build 11776, commit ead9f3205)` |
| Build / compilador | `built with IntelLLVM 2026.2.0 for Linux x86_64` |
| Errores de carga | Ninguno |
| Advertencias | Ninguna |

Salida cruda:
```
version: 0.7.0-dev (build 11776, commit ead9f3205)
built with IntelLLVM 2026.2.0 for Linux x86_64
```

**Conclusión prueba 1:** El ejecutable inicia correctamente, resuelve todas sus dependencias dinámicas con las rutas oneAPI indicadas e informa su versión, build y commit sin errores ni advertencias.

---

## 2. Resultado de `--list-devices`

Comando ejecutado:
```
env LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.2/lib:/opt/intel/oneapi/dnnl/2026.1/lib:/opt/intel/oneapi/2026.1/lib' /home/brunapc/llama.cpp-sycl/build/bin/llama-cli --list-devices
```

| Campo | Valor |
|---|---|
| Código de salida | **0** (éxito) |
| Salida cruda | `Available devices:`<br>`  SYCL0: Intel(R) Arc(TM) Pro B70 Graphics (32656 MiB, 31721 MiB free)` |
| Dispositivos detectados | 1 dispositivo |
| Backend asociado | `SYCL0` → backend SYCL (oneAPI DPC++ / Level Zero) |
| Identificación Arc Pro B70 | **Sí** — `Intel(R) Arc(TM) Pro B70 Graphics` |
| Memoria total / libre | 32656 MiB / 31721 MiB libre |
| Errores de inicialización SYCL / Level Zero | Ninguno |
| Advertencias de bibliotecas | Ninguna |

**Conclusión prueba 2:** El runtime SYCL se inicializa correctamente, el backend SYCL enumera dispositivos y detecta la **Intel Arc Pro B70** con sus características de memoria.

---

## 3. Dependencias resueltas durante la ejecución

Con el `LD_LIBRARY_PATH` limitado al proceso de diagnóstico, todas las dependencias dinámicas del ejecutable y de `libggml-sycl.so.0` se resuelven:

- Bibliotecas del propio build (`RUNPATH build/bin:`): `libllama-cli-impl.so`, `libllama-server-impl.so`, `libmtmd.so.0`, `libllama-common.so.0`, `libllama.so.0`, `libggml.so.0`, `libggml-cpu.so.0`, `libggml-sycl.so.0`, `libggml-base.so.0`.
- oneAPI compiler (`/opt/intel/oneapi/compiler/2026.2/lib`): `libsvml.so`, `libirng.so`, `libimf.so`, `libintlc.so.5`, `libiomp5.so`, `libsycl.so.9`.
- oneDNN (`/opt/intel/oneapi/dnnl/2026.1/lib`): `libdnnl.so.3`.
- TBB (`/opt/intel/oneapi/2026.1/lib`): `libtbb.so.12`.
- MKL (vía RUNPATH propio de `libggml-sycl.so`): `libmkl_sycl_blas.so.6`, `libmkl_intel_ilp64.so.3`, `libmkl_intel_thread.so.3`, `libmkl_core.so.3`.
- Sistema: `libze_loader.so.1`, `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`, `libdl.so.2`, `libpthread.so.0`, `librt.so.1`, `ld-linux-x86-64.so.2`.

No se reportó ninguna biblioteca `not found` ni símbolo no disponible durante la ejecución.

---

## 4. Errores y advertencias

- **--version:** sin errores, sin advertencias.
- **--list-devices:** sin errores, sin advertencias.
- No se observó error de biblioteca no encontrada, símbolo no disponible, incompatibilidad de ABI, error de inicialización del runtime SYCL, error del driver Level Zero, ni error de enumeración de dispositivo.

---

## 5. Confirmación de detección de la Arc Pro B70

**CONFIRMADO.** El ejecutable `llama-cli` detecta la Intel Arc Pro B70 mediante el backend SYCL:

- Dispositivo: `SYCL0: Intel(R) Arc(TM) Pro B70 Graphics`
- Memoria: 32656 MiB total, 31721 MiB libre
- Backend: SYCL (oneAPI DPC++ sobre Level Zero)

La detección se produce sin cargar modelos ni ejecutar inferencia, exclusivamente mediante el listado de dispositivos del backend SYCL.

---

## 6. Dictamen sobre la inicialización del runtime SYCL

**El runtime SYCL se inicializa correctamente.**

Evidencia:
1. `--version` finaliza con código 0 y reporta la versión, build y commit sin errores de carga.
2. `--list-devices` finaliza con código 0 y enumera correctamente el dispositivo SYCL0 (Intel Arc Pro B70), lo que demuestra que:
   - El backend SYCL se registra y carga correctamente.
   - El runtime SYCL / Level Zero (`libze_loader.so.1`) se inicializa sin errores de driver.
   - La enumeración de dispositivos funciona y expone la GPU Intel Arc Pro B70.
3. Todas las dependencias dinámicas (incluidas las de Intel oneAPI que requerían `LD_LIBRARY_PATH` en el diagnóstico estático A2.6.6.13) se resuelven cuando se proveen las rutas correctas al proceso.

No hay indicios de problema de ABI, símbolo faltante, biblioteca ausente ni fallo de inicialización del runtime. El ejecutable está listo para usar el backend SYCL con la Intel Arc Pro B70; cualquier paso posterior (carga de modelo, inferencia) queda fuera del alcance de esta fase por restricción expresa.

---

**Fin del informe. No se ejecutó inferencia ni se cargó modelo. No se modificó nada de forma persistente.**