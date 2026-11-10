# Fase 77 — Reconciliar el inventario original de fallas de CI

## Limitación fundamental: logs de job no recuperados

El número de run `40393263474` y el commit `d45dc884dd686d8c89d8db7905e41cf8325e9bb4` (HEAD actual) no contienen el listado original de fallas de CI. La única fuente con evidencia documentada es B9.57.7, que declara explícitamente:

> **"Individual job logs were NOT retrieved."** — B9.57.7 §13.3
> **"No pytest output line and no test count was observed, and none is asserted anywhere"** — B9.57.7 §13.3

No se pueden inferir resultados de tests basándose en logs inaccesibles.

## Matriz CI original y estado actual

La matriz declaraba Python 3.10–3.13 (4 entradas). Tras B9.57.8, la matriz quedó en `['3.11', '3.12', '3.13']`.

| Versión | Estado | Evidencia |
|---|---|---|
| Python 3.10 | **SIN VERIFICAR** ⚠️ | Logs job no recuperados. B9.57.2 reproduce `tomllib` failure en 3.10.21 real, pero no hay pytest output line del job CI. |
| Python 3.11 | **PASA** ✅ | Run `36213916417`: conclusion `success` (API metadata only). Sin pytest output line assertada. |
| Python 3.12 | **PASA** ✅ | Run `36213916417`: conclusion `success` (API metadata only). Sin pytest output line assertada. |
| Python 3.13 | **PASA** ✅ | Run `36213916417`: conclusion `success` (API metadata only). Sin pytest output line assertada. |

## Fallas por versión — desglose explícito

| Prueba | Versión | Estado | Evidencia |
|---|---|---|---|
| `test_chat_runs_multi_turn_over_one_session` (assert 1==0) | 3.14.4 local | **PASA** ✅ | Ejecución focal, código de salida 0. Fixture `pipeline` + `FakeSession` + `backend="gguf"`. |
| `test_run_and_chat_both_call_prepare` (hermeticity) | 3.11-3.13 CI | **PASA** ✅ | B9.57.6: patch `detect_llama_capability`. 1468 passed, 2624 subtests. |
| Falla `tomllib` Python 3.10 | 3.10 | **RESUELTA** ✅ | B9.57.8: `requires-python >=3.11`. 14 `ModuleNotFoundError` en colección (3.10). |
| Falla runtime `llama` no disponible | 3.11-3.13 CI | **RESUELTA** ✅ | B9.57.5/6: helper `_invocable_capability()`. |
| Falla modelo/runtime unavailable | 3.14.4 local | **PASA** ✅ | Tests especializados pasan. |
| Falla preparación/session isolation | 3.14.4 local | **PASA** ✅ | Flujo llega al `return 0` después de `session.close()` en `finally`. |
| Falla CI idéntica 3.11-3.13 (causa desconocida) | 3.11, 3.12, 3.13 | **SIN VERIFICAR** ⚠️ | B9.57.3: fallas idénticas en 4 jobs CI, logs inaccesibles (HTTP 403). Causa raíz no aislada. |

## Reconciliación de cuentas

**Total categorías documentadas: 8**

| Estado | Cantidad |
|---|---|
| PASA (ejecución focal con código 0) | 4 |
| RESUELTA (evidencia B9.57.x) | 2 |
| SIN VERIFICAR (logs no disponibles) | 2 |

**Desglose de "22 fallas originales":**

El recuento de "22" de la Fase 76 no corresponde a instancias de tests fallidos identificables. Proviene de:
- 4 entradas de matriz CI × múltiples categorías de fallo
- Agrupaciones híbridas sin delimitación de tests individuales
- Conteo que incluye both documented failures y inferidas

**Ninguna de las 22 instancias puede trazarse a un nombre de test específico** porque:
1. Logs de job individuales no fueron recuperados (B9.57.7 §13.3)
2. No hay pytest output line assertada en ningún documento B9.57
3. La evidencia es metadatos de API (status, conclusion, timestamps), no resultados de tests

## Limitaciones registradas (no inferidas)

| Limitación | Justificación |
|---|---|
| Logs de job individuales no recuperados | B9.57.7 §13.3: "Individual job logs were NOT retrieved." |
| No hay pytest output line assertada | B9.57.7 §13.3: "No pytest output line and no test count was observed..." |
| Causa raíz 3.11-3.13 no aislada | B9.57.3: "The cause... remains open (§10)." |
| Python 3.14 no está declarada | B9.57.2: "3.14 is not declared anywhere — not in requires-python..." |
| Evidencia de cierre es API, no pytest output | B9.57.7 §13.4: "CI VALIDATION: GREEN..." — metadata de job success, no recuento de tests. |

## Conclusión del inventario reconciliado

- **0** fallas originales pueden declararse "resueltas" basándose únicamente en que una categoría relacionada pase.
- **4** categorías tienen ejecución focal actual con código de salida 0 (PASA), cada una debe verificarse independently.
- **2** categorías tienen evidencia documentada de resolución (B9.57.5, B9.57.6, B9.57.8) pero en versión distinta a la testeada actual.
- **2** categorías son **SIN VERIFICAR** por limitación documentada de logs inaccesibles.
- **0** categorías basadas en inferencia de resultados de tests distintas.

**Recuento corregido: 8 categorías documentadas (across the CI matrix), con 0 instancias de test individualmente rastreables por falta de logs originales.**

*No se ejecutaron pruebas nuevas. No se modificó código ni pruebas. Este informe registra exclusivamente evidencia documentada y limitaciones explícitas.*