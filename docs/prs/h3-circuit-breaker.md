# H3: Circuit Breaker (5% drawdown diario)

> spec.md §5 Historia 3. Cortar operativa si la pérdida diaria ≥ 5% del
> balance de apertura UTC 00:00. Acciones: cancelar órdenes, cerrar
> posiciones a mercado, `ENVIRONMENT_MODE=PASIVO`, halt loop, log crítico.

## Resumen

8 commits conventional, 54 tests nuevos, hexagonal mantenido (PASS de
`quality_arch_lint`).

| Capa            | Archivos nuevos |
|-----------------|-----------------|
| Domain          | `domain/value_objects/drawdown_state.py`, `drawdown_snapshot.py`, `trip_action.py` · `domain/entities/circuit_breaker.py` |
| Application     | `application/ports/{trade_journal,exchange_order_client,environment_mode_writer,drawdown_snapshot_repo}.py` · `application/use_cases/{check_drawdown,trip_circuit_breaker,open_day}.py` |
| Infrastructure  | `infrastructure/journal/{in_memory_trade_journal,in_memory_snapshot_repo}.py` · `infrastructure/exchange/ccxt_order_client.py` · `infrastructure/env_mode/file_env_mode_writer.py` |
| API             | `app/api/circuit_breaker.py` (`POST /risk/day/open`, `POST /risk/drawdown/check`, `GET /risk/drawdown`) |
| Composition     | `composition.py` extendido (4 nuevos helpers FastAPI, build_composition para BACKTESTING/PAPER/LIVE) |
| Tests           | 4 archivos: 30 + 13 + 5 + 6 = 54 tests |

## Cumplimiento de invariantes duras (§2 AGENTS.md)

- **#3 Drawdown circuit breaker**: pérdida diaria ≥ 5% → halt. Implementado
  en `CircuitBreaker.evaluate` con `threshold=0.05` por default
  (`apps/analytics-engine/app/domain/entities/circuit_breaker.py:80`).
- **#4 Acciones del circuit breaker**: cancelar órdenes → cerrar posiciones
  → `ENVIRONMENT_MODE=PASIVO` → halt. Orden enforced en
  `TripAction.__post_init__` (no se puede construir un `TripAction` con
  pasos desordenados). `TripCircuitBreakerUseCase.execute` los itera en
  orden y reporta resultado por paso en `TripResult.steps`.
- **#5 `ENVIRONMENT_MODE` ∈ {BACKTESTING, PAPER_TRADING, LIVE, PASIVO}**:
  `EnvironmentMode` enum incluye los 4 valores. El trip setea `PASIVO`
  via `EnvironmentModeWriter.write`.

## Endpoints

- `POST /risk/day/open` — body `{ "force"?: bool }`. Captura el balance
  libre actual como `starting_balance` del día. 422 si ya hay snapshot y
  `force=False`. Devuelve el `DrawdownSnapshot`.
- `POST /risk/drawdown/check` — evalúa el drawdown del día y dispara el
  trip en `TRIP`. Devuelve estado, snapshot, P&L intradía y la lista de
  pasos de la acción de trip. 422 con `snapshot_missing` si no se abrió
  el día.
- `GET /risk/drawdown` — read-only: lee el snapshot actual sin evaluar
  ni disparar nada. Devuelve `null` si no hay día abierto.

## Comportamiento clave

- **HALTED es sticky**: una vez que el trip corrió y la app está en
  `PASIVO`, `CircuitBreaker.evaluate(snapshot, current_state=HALTED)`
  devuelve `HALTED` aunque el drawdown se haya recuperado. El use case
  no re-arma el breaker por accidente.
- **Orden canónico enforced**: `TripAction(steps=(CLOSE, CANCEL, ...))`
  levanta `ValueError`. La única forma de trip es cancelar primero.
- **Trip parcial**: si el primer paso (cancel) falla, los demás igual
  corren. `TripResult.steps[i].ok=False` para los que fallaron, pero el
  env mode se setea y el snapshot se limpia. `TripResult.fully_succeeded`
  es `True` solo si los 4 pasos pasaron. `TripCircuitBreakerError` se
  levanta solo si NO todos pasaron.
- **Reset diario**: `CircuitBreaker.should_reset_utc(now)` devuelve
  `True` a las `00:00:00 UTC` exactas. H3-FU1: scheduler que llame
  `OpenDayUseCase.execute()` cuando dispare.

## Adaptadores

- `InMemoryTradeJournal` / `InMemorySnapshotRepo` — BACKTESTING y tests.
- `CcxtOrderClient` — PAPER/LIVE: cancela todas las órdenes abiertas
  per-symbol, cierra todas las posiciones con `reduce_only=True`.
- `FileEnvironmentModeWriter` — escribe a `/var/lib/argos/env_mode.json`
  (override via `ARGOS_ENV_MODE_FILE`). Escritura atómica (temp + rename +
  fsync). `read()` devuelve `BACKTESTING` por default si el archivo
  falta (per spec: nunca auto-default a LIVE).

## Tests (97 passed, 1 skipped)

```
tests/integration/test_circuit_breaker_endpoint.py ......                [  6%]
tests/integration/test_risk_endpoint.py ....                             [ 10%]
tests/integration/test_ta_atr_calculator.py ...                          [  13%]
tests/test_health.py .                                                   [ 14%]
tests/test_subscriber_contract.py s                                      [ 15%]
tests/unit/test_circuit_breaker.py ..............................        [ 45%]
tests/unit/test_circuit_breaker_adapters.py .....                        [ 51%]
tests/unit/test_circuit_breaker_usecases.py .............                [ 64%]
tests/unit/test_compute_position_size_usecase.py .......                 [ 71%]
tests/unit/test_risk_calculator.py .......                               [ 78%]
tests/unit/test_value_objects.py .....................                   [100%]

97 passed, 1 skipped in 4.69s
```

El skip es el contract test del H1 contra el broker, gated en tener un
broker reachable (gated on docker / bare-metal broker, no disponible en
el sandbox).

## Bugs encontrados en esta historia

1. **`warn_ratio <= threshold` invertido en `CircuitBreaker.__init__`**:
   habría roto el constructor default (0.6 > 0.05). Corregido: `warn_ratio`
   se valida en `(0, 1]`, sin comparación con `threshold`.
2. **`Request` forward-ref en helpers de FastAPI rompe pydantic 2.13**:
   `def get_*(request: "Request")` se reemplazó por `from fastapi import
   Request` real. Bug pre-existente del H2 que no se había detectado
   porque los tests de H2 usan `app.dependency_overrides` (que
   bypassea la resolución de dep). Detectado al hacer la integración
   end-to-end de H3.
3. **`TmpFileEnvWriter` wrapper vs subclass**: el wrapper inicial no
   pasaba `isinstance(..., EnvironmentModeWriter)`. Convertido a subclass.

## Validación

- `quality_arch_lint` → **PASS** (no hay imports cruzados domain ↔
  infrastructure; no hay ccxt/ta/redis/pandas en domain/ ni application/).
- `quality_secret_scan` → 5 hits, **todos placeholders** en
  `.agents/skills/{binance-futures-signal-bot,zeroboot-vm-sandbox}/SKILL.md`
  (`your_api_key_here`, `zb_live_your_key_here`). No en código de argos.
- `pytest` → 97 passed, 1 skipped (H1 broker contract).

## Follow-ups registrados

- **H3-FU1**: scheduler UTC 00:00 que llame `OpenDayUseCase.execute()`
  y `ClearAndResetUseCase` (auto-reset diario).
- **H3-FU2**: `TradeJournal` persistente (SQLite o Redis stream) — el
  in-memory actual pierde el P&L en cada restart.
- **H3-FU3**: structured logging en `TripCircuitBreakerUseCase` (a nivel
  composition, no en el use case — la policy es mantener el use case
  puro).
- **H3-FU4**: runbook de recuperación (qué hace el operador después de
  un trip) — owner: H4 OWASP.

## Branch y merge

- Branch: `feature/h3-circuit-breaker` desde `dev` (rebaseada sobre
  el merge de H2 = `9873902`).
- 8 commits conventional:
  ```
  cd0fe84 feat(analytics-engine): h3-001 domain value objects for circuit breaker
  4da3185 feat(analytics-engine): h3-002 domain entity CircuitBreaker
  32a58a1 feat(analytics-engine): h3-003 application ports for circuit breaker
  42a9114 feat(analytics-engine): h3-004 application use cases for circuit breaker
  e078bdd feat(analytics-engine): h3-005 infrastructure adapters for circuit breaker
  231ea7c feat(analytics-engine): h3-006 api endpoints and composition wiring
  fecff05 test(analytics-engine): h3-007 unit and integration tests for h3
  fed33c6 docs(tasks): h3-006 to h3-007 in progress and h3-008 done
  ```

## Pendiente de acción humana

- Push de la rama: el agente no hace `git push` sin confirmación
  explícita (AGENTS.md §12).
- Abrir y mergear el PR en GitHub — el agente no abre ni mergea PRs.
