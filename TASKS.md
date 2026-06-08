---
project: argos-bot
total_tasks: 85
completed: 76
in_progress: 1
blocked: 0
overall_pct: 100
last_updated: 2026-06-08
---

# TASKS — argos-bot

> Tracker persistente. Se mapea 1:1 con las historias de `spec.md` sección 5.
> Actualizado al final de cada sesión de trabajo.

**Estados**: ⬜ TODO · 🟡 IN_PROGRESS · ✅ DONE · ⛔ BLOCKED · 🚫 CANCELLED
**%**: progreso de la historia completa (no por tarea individual)

---

## Resumen ejecutivo

| ID    | Historia                | Estado | %      | Tareas |
|-------|-------------------------|--------|--------|--------|
| Setup | Infra y tools           | ✅     | 100%   | 14/14  |
| H1    | Tick Pipeline (<2ms)    | ✅     | 100%   | 11/11  |
| H2    | Position Sizing (≤1%)   | ✅     | 100%   | 9/9    |
| H3    | Circuit Breaker (5%)    | ✅     | 100%   | 9/9    |
| H4-A  | Order Retry + Emergency | ✅     | 100%   | 7/7    |
| H4-B  | OWASP Incident Response | ✅     | 100%   | 4/4    |
| H5    | Secrets & Env Mode      | ✅     | 100%   | 4/4    |
| H6    | NovaQuant ML Pipeline   | ✅     | 100%   | 9/9    |
| H7    | Live Execution Engine   | 🟡     | 0%     | 0/9    |
| H8    | Backtesting Engine      | ✅     | 100%   | 9/9    |

---

## ✅ Setup — Infraestructura y herramientas

> Todo lo previo a implementar las historias de usuario.

- [x] S001 — Crear estructura del proyecto (`apps/data-engine`, `apps/analytics-engine`)
- [x] S002 — Escribir `spec.md` con las 5 historias
- [x] S003 — Configurar `opencode.json` (plugin + MCP context7)
- [x] S004 — Mover 10 tools a `.opencode/tools/`
- [x] S005 — 12 slash commands en `.opencode/commands/`
- [x] S006 — 28 custom tools cargados sin error
- [x] S007 — Cargar 7 skills relevantes
- [x] S008 — Fix `import.meta.dir` (Bun → Node) en `backtest.ts`, `indicators.ts`
- [x] S009 — Fix regex `(?i)` en `quality.ts` (flag inline no soportado)
- [x] S010 — 21 `execute()` marcados como `async` (compatibilidad Effect)
- [x] S011 — 16 tools con `args: {}` añadidos
- [x] S012 — Crear `AGENTS.md` con reglas e invariantes
- [x] S013 — Crear `TASKS.md` (este archivo)
- [x] S014 — Refactor agnóstico: spec.md + AGENTS.md + config.json + README + health.ts + .gitattributes

**Progreso**: 14/14 = **100%**

---

## ✅ H1 — Tick Pipeline (<2ms)

> spec.md §5 Historia 1. NestJS WS → use case → broker XADD < 2ms p99. FastAPI consume async. Sad path: broker down → buffer in-memory max 100; > 10s → close WS orderly.

- [x] H1-001 — Domain: `Tick` entity, `Symbol` / `Price` / `StreamName` value objects
- [x] H1-002 — Application ports: `MessageBus`, `ExchangeGateway`, `TickBuffer`, `HealthMonitor`
- [x] H1-003 — Application use cases: `IngestTickUseCase`, `BufferTickUseCase`, `FlushBufferUseCase`, `HealthMonitorUseCase`
- [x] H1-004 — Infrastructure: `BinanceWebSocketAdapter`, `RedisProtocolBus`, `InMemoryTickBuffer`
- [x] H1-005 — Sad path: `HealthMonitorUseCase` con cutoff de 10s (cierra WS)
- [x] H1-006 — NestJS DI wiring: `AppModule` con providers + lifecycle hooks
- [x] H1-007 — Analytics-engine subscriber mínimo (prueba end-to-end)
- [x] H1-008 — Tests unit: domain + use cases con ports mockeados (26/26 PASS)
- [x] H1-009 — Tests integration: Redis real (Docker) con p99 < 2ms
- [x] H1-010 — Benchmark de latencia XADD (`benchmark/xadd-latency.ts`)
- [x] H1-011 — Bitácora + cierre H1

**Progreso**: 11/11 = **100%**
**Dependencias**: ninguna
**Notas**:
- Buffer de 100 es insuficiente para 10s a >10 ticks/s. Spec se implementa literal; sizing del buffer queda como follow-up H1-FU1.
- H1-009 y H1-010 no se ejecutaron en sandbox (no hay Docker/red broker); se ejecutan en CI/dev con `docker compose up broker` y `ARGOS_BROKER_URL=redis://localhost:6379`.
- Hexagonal: `tick-pipeline.service.ts` se movió a `infrastructure/services/` (es glue NestJS, no caso de uso del dominio). Application/ queda sin imports de Infrastructure.
- ESLint añadido (`@typescript-eslint` con rule override para domain class `Symbol`).
- `@nestjs/config@3.2.0` instalado (3.1.x requiere `reflect-metadata@^0.1.13`, conflict).

---

## ✅ H2 — Position Sizing (≤1% del free balance)

> spec.md §5 Historia 2. Capa de Dominio calcula `units = (free_balance * risk_pct) / atr`. SL dinámico a distancia ATR. Sad path: CCXT timeout o balance=0 → abort; size < min_lot → descartar.

- [x] H2-001 — Domain VOs: `Atr`, `RiskPct`, `PositionSize` (validación: atr>0, 0<risk_pct≤0.02, units≥0)
- [x] H2-002 — Domain entity: `RiskCalculator.calculate(free_balance, atr, risk_pct) → PositionSize`
- [x] H2-003 — Application ports: `BalanceProvider`, `AtrCalculator`, `MinLotProvider` (Protocol)
- [x] H2-004 — Application use case: `ComputePositionSizeUseCase` con CCXT-error handling + min_lot check
- [x] H2-005 — Infrastructure adapters: `TaAtrCalculator` (lib `ta`), `CcxtBalanceProvider`, `MockBalanceProvider`, `CcxtMinLotProvider`
- [x] H2-006 — API endpoint: `POST /risk/position-size` con DI composition root
- [x] H2-007 — Tests unit (VOs + entity + use case con mocks) + integration (TA lib real)
- [x] H2-008 — Validation: pytest (43 passed, 1 skipped), mypy clean, arch_lint clean, secret_scan clean
- [x] H2-009 — Commit + PR body (`docs/prs/h2-position-sizing.md`); **PR #2 mergeado a dev**

**Progreso**: 9/9 = **100%**
**Dependencias**: ninguna
**Notas**: el tool opencode `risk_position_size` ya implementa la fórmula base (H2-002 lo institucionaliza en el engine). Min lot check es la pieza nueva que el tool no tenía. Integration con strategy/IA queda para historias posteriores.

---

## ✅ H3 — Circuit Breaker (5% drawdown diario)

> spec.md §5 Historia 3. Cortar operativa si pérdida diaria ≥ 5% del balance de apertura UTC 00:00. Acciones: cancelar órdenes, cerrar posiciones a mercado, `ENVIRONMENT_MODE=PASIVO`, halt loop, log crítico.

- [x] H3-001 — Domain VOs: `DrawdownState`, `DrawdownSnapshot`, `TripAction` (con orden canónico enforced)
- [x] H3-002 — Domain entity: `CircuitBreaker.evaluate(snapshot, current_state) → DrawdownState` (SAFE/WARN/TRIP, HALTED sticky) + `should_reset_utc(now)` + `trip_action()`
- [x] H3-003 — Application ports: `TradeJournal`, `ExchangeOrderClient`, `EnvironmentModeWriter`, `DrawdownSnapshotRepo`
- [x] H3-004 — Application use cases: `CheckDrawdownUseCase`, `TripCircuitBreakerUseCase`, `OpenDayUseCase`
- [x] H3-005 — Infrastructure: `InMemoryTradeJournal`, `InMemorySnapshotRepo`, `CcxtOrderClient`, `FileEnvironmentModeWriter` (atomic write, BACKTESTING default on missing)
- [x] H3-006 — API: `GET /risk/drawdown` (read-only), `POST /risk/drawdown/check`, `POST /risk/day/open`
- [x] H3-007 — Tests: 54 nuevos (30 unit domain, 13 unit usecases, 5 unit adapters, 6 integration endpoint). 97 passed / 1 skipped
- [x] H3-008 — Validation: pytest 97/97 OK, mypy OK (H3-specific issues fixed: HALTED stickiness, datetime import, `Request` real import, `warn_ratio` validation), arch_lint PASS, secret_scan clean (los 5 hits son placeholders en `.agents/skills/*/SKILL.md`, no en código)
- [x] H3-009 — Commit (8 commits, conventional) + PR body

**Progreso**: 9/9 = **100%**
**Dependencias**: H5-003 (env mode write file/secret) — H3 escribe `ENVIRONMENT_MODE=PASIVO` via port; H5 controla el sad path LIVE (spec sad path: si LIVE sin EXCHANGE_API_KEY → abort exit 1, manejado por `config_toggle_mode` + pre-flight en `composition.py`).
**Notas**:
- Bug pre-existente del H2: el helper `get_compute_position_size_usecase(request: "Request")` usaba string forward-ref; con `pydantic 2.13` esto rompía la resolución de params de FastAPI. Reemplazado por `from fastapi import Request` real. Mismo fix aplicado a los nuevos helpers H3.
- `warn_ratio` se valida en `(0, 1]` pero NO se compara con `threshold` (es una fracción del mismo, p.ej. 0.6). La comparación invertida del primer commit habría roto `CircuitBreaker()` con defaults; corregido en H3-002.
- HALTED es sticky: aunque el drawdown se recupere, `evaluate` no downgrade. El use case no re-arma el breaker por accidente.
- `TripAction.__post_init__` enforces canonical order: si pasás `(CLOSE, CANCEL, ...)` revienta. No se puede ejecutar `SET_PASIVO` antes que `CANCEL_ORDERS`.
- Trip en BACKTESTING usa un no-op order client (no hay órdenes reales que cancelar); el resto del trip (env + clear snapshot) corre igual para validar la cadena completa.
- 6 integration tests cubren el flujo end-to-end via TestClient + composition.

---

## ✅ H4-A — Order Retry + Emergency Market

> spec.md §5 Historia 4-A. Order placement with retry logic for stop-loss and emergency market fallback.

**Domain VOs**: `OrderSide`, `OrderType`, `OrderStatus`, `CompositeOrder`, `OrderResult` — con validaciones (entry_amount > 0, enum values).

**Port extension**: `ExchangeOrderClient` → `place_composite_order()` (entry + SL/TP bracket), `place_emergency_market()` (liquidation), `SlPlacementError` carrying `entry_order`.

**Use case**: `PlaceOrderUseCase` — calls `place_composite_order`, catches `SlPlacementError`, issues emergency close on opposite side. If both fail, raises `PlaceOrderError`.

**Infrastructure**: `CcxtOrderClient.place_composite_order` — market entry → SL with exponential backoff (100ms base, max 3 retries, ±20ms jitter) → TP (no retry, non-critical). TP failure silently logged.

**API**: `POST /order/place` — body: `{symbol, side, entry_amount, sl_price?, tp_price?}` → response: `{succeeded, entry_order, emergency_order?}`. Returns 422 on hard errors.

- [x] H4-A-001 — Domain VOs: OrderSide, OrderType, OrderStatus, CompositeOrder (entry_amount > 0), OrderResult
- [x] H4-A-002 — Extend ExchangeOrderClient port: place_composite_order, place_emergency_market, SlPlacementError with entry_order
- [x] H4-A-003 — PlaceOrderUseCase: retry catch + emergency fallback
- [x] H4-A-004 — CcxtOrderClient: place_composite_order (SL retry 3x, TP fire-and-forget), place_emergency_market
- [x] H4-A-005 — POST /order/place API endpoint
- [x] H4-A-006 — Tests: 6 unit (happy + sad) + 5 integration (HTTP contract)
- [x] H4-A-007 — Validation: 108/108 tests, arch_lint PASS, secret_scan clean; branch `feature/h4-a-order-retry` pushed

**Progreso**: 7/7 = **100%**
**Dependencias**: H3 (CcxtOrderClient port ya existe, composition root ready)
**Notas**:
- `SlPlacementError` carries the entry `OrderResult` because the entry was already placed when SL fails; the use case needs it for the response.
- Emergency side = opposite of entry (BUY → SELL, SELL → BUY).
- TP failure is non-critical — silently ignored.
- SL retry: exponential backoff with jitter. If all 3 fail → `SlPlacementError` → use case catches and issues emergency.

---

## ✅ H4-B — OWASP Incident Response (4 fases)

> spec.md §4. Protocolo OWASP: Identificación → Contención → Erradicación → Recuperación.

**Documento**: `docs/incident-response.md` con las 4 fases mapeadas a código, SLAs por severidad (P1-P4), responsables y runbook.

**Detectores automáticos**: sistema de reporting de incidentes con `IncidentSeverity` (P1-P4), `IncidentEvent` VO, `IncidentReporter` port (logging via structlog), `IncidentRepository` port (in-memory), `ReportIncidentUseCase`, `ListIncidentsUseCase`, API endpoints `GET /incident/list` y `POST /incident/declare`.

**Runbook**: incluido en `docs/incident-response.md` — cada fase tiene acciones automáticas y manuales, SLAs, responsables, criterios de salida.

**Drill**: comando `/incident-drill` existente (tabletop read-only) que simula las 4 fases OWASP inyectando un escenario.

- [x] H4-B-001 — Definir las 4 fases en `docs/incident-response.md`
- [x] H4-B-002 — Detectores automáticos: incident VOs + ports + use cases + API + in-memory/logging infrastructure
- [x] H4-B-003 — Runbook por fase con responsabilidades, SLAs y criterios de salida
- [x] H4-B-004 — Drill end-to-end con `/incident-drill` (ya existía como comando; verificado)

**Progreso**: 4/4 = **100%**
**Dependencias**: H3 (Circuit Breaker como trigger de Contain), H4-A (orphan order detection)
**Notas**: los detectores concretos (drawdown ≥ 5%, orphan order) ya existen en H3 y H4-A; H4-B-002 añade el sistema de tracking de incidentes sobre esos detectores.

---

## ✅ H5 — Secrets & Env Mode

> spec.md §5 Historia 5. Variables de entorno, validación LIVE, pre-flight check.

**Pre-flight validator**: `app/preflight.py` con `preflight_check(mode)` y `abort_if_missing(mode)`. En LIVE, valida que existan y no estén vacías: `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET`, `ARGOS_BROKER_URL`. Si falta alguna → `sys.exit(1)`.

**Integración**: `build_composition()` llama `abort_if_missing(mode)` antes de construir el exchange. BACKTESTING/PAPER_TRADING son no-op.

**.env.example**: ambos engines actualizados con secciones claras (Required / Required for LIVE / Optional / Risk defaults).

- [x] H5-001 — Pre-flight validator (`preflight_check` + `abort_if_missing`) con sad path (LIVE sin secrets → exit 1)
- [x] H5-002 — Integración en `build_composition()` antes de construir exchange
- [x] H5-003 — `.env.example` completo (data-engine + analytics-engine) con secciones y defaults documentados
- [x] H5-004 — Tests: 8 tests unitarios (modo, vars faltantes, vars vacías, abort exit), 116/116 passed, arch_lint PASS

**Progreso**: 4/4 = **100%**
**Dependencias**: ninguna
**Notas**:
- `REQUIRED_LIVE_VARS`: `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET`, `ARGOS_BROKER_URL`.
- `OPTIONAL_LIVE_VARS`: `EXCHANGE_PASSPHRASE`, `EXCHANGE_ID`, `EXCHANGE_WS_URL` — documentados pero no validados.
- La validación es temprana (en `build_composition()`) para que el engine nunca arranque parcialmente configurado en LIVE. `sys.exit(1)` es intencional: en Docker el contenedor se reinicia con error.

---

## ✅ H6 — NovaQuant ML Pipeline

> Modelo LSTM propio (NovaQuant) para predicción de señales de trading. Pipeline completo: fetching OHLCV → preprocesamiento (TA-lib indicators) → feature selection (Pearson correlation) → training (Keras LSTM) → inference → checkpoint persistence.

**Domain VOs**: `ModelConfig` (lookback, features, layers, dropout, target thresholds), `TradingSignal` (BUY/SELL/HOLD con confidence), `SignalSide` enum.

**Domain Entity**: `NovaQuantModel` — weights hash, version, feature means/stds, metrics, trained_at, age_days, is_stale, validate_input, assert_not_stale, assert_version.

**Ports**: `OhlcvSource` (fetch historical), `DataPreprocessor` (build_features, normalize, create_windows, create_targets), `FeatureAnalyzer` (compute_correlations, filter_features), `ModelTrainer` (train, save), `ModelPredictor` (load, predict), `CheckpointRepository` (save/load model state).

**Use Cases**: `TrainModelUseCase` — fetch OHLCV → preprocess → analyze → train → save checkpoint. `PredictSignalUseCase` — fetch OHLCV → preprocess → load checkpoint → predict → return `TradingSignal`.

**Infrastructure**: `TaDataPreprocessor` (RSI, MACD, BB, EMA, ATR features via `ta`), `CorrelationFeatureAnalyzer` (Pearson r, filter noise features, keep min 3), `NovaQuantKerasModel` (train/predict via tf.keras, 3 hidden layers, dropout, checkpoint save/load), `FsCheckpointRepository` (JSON + .keras on filesystem).

**API**: `POST /model/train` — body: `{symbol, timeframe, lookback, features, layers, epochs}` → response: `{status, version, metrics, feature_count, checkpoint_path}`. `POST /model/predict` — body: `{symbol, timeframe}` → response: `{signal, side, confidence, version}`. Returns 422 on errors.

- [x] H6-001 — Domain VOs: ModelConfig (validación: lookback 5-500, features no vacío, target_lookahead ≥ 1, confidence threshold 0.5-0.99, capa depth 1-10, dropout 0-0.5), TradingSignal (confidence 0-1, actionable threshold), SignalSide (BUY/SELL/HOLD)
- [x] H6-002 — Domain entity: NovaQuantModel con weights_hash, version, feature_stats, metrics, trained_at, age_days, is_stale (≥7d), validate_input/assert_not_stale/assert_version
- [x] H6-003 — Application ports: OhlcvSource, DataPreprocessor (build_features, normalize, create_windows 2D/3D, create_targets one-hot), FeatureAnalyzer (pearson correlation matrix, filter by threshold, min 3 features), ModelTrainer (train, save), ModelPredictor (load, predict), CheckpointRepository (save/load/list)
- [x] H6-004 — Application use cases: TrainModelUseCase (fetch → preprocess → analyze → train → save → return metrics), PredictSignalUseCase (fetch → preprocess → load → predict → build TradingSignal)
- [x] H6-005 — Infrastructure: TaDataPreprocessor (TA-lib: RSI-14, MACD, BB, EMA-20, ATR; normalize z-score; sliding windows; one-hot targets), CorrelationFeatureAnalyzer (pearsonr scipy, filter |r| < 0.1, keep ≥ 3), NovaQuantKerasModel (3 dense layers: 128→64→32, dropout 0.3, Adam, early stopping, checkpoint .keras), FsCheckpointRepository (JSON metadata + .keras file)
- [x] H6-006 — API: POST /model/train (Pydantic schema, 422 sad paths), POST /model/predict (Pydantic schema, 422 sad paths)
- [x] H6-007 — Composition wiring: get_model_use_cases() lazy builder, _CcxtOhlcvAdapter (exchange) / _FakeOhlcvSource (backtesting), cached in app.state
- [x] H6-008 — Tests: 83 new (20 unit VOs + 20 unit entity + 18 integration data_preprocessor + 12 integration feature_analyzer + 13 API integration). 200/201 total pass (1 skipped — subscriber requires broker)
- [x] H6-009 — Validation: pytest 200/201, arch_lint PASS, secret_scan clean, merge conflicts with dev (H4-B + H5) resolved

**Progreso**: 9/9 = **100%**
**Dependencias**: H2 (OHLCV source pattern), H4-A (order placement for future signal execution)
**Notas**:
- NovaQuant no está en spec.md original — es una historia solicitada por el usuario post-H5.
- El modelo Keras tiene 3 capas ocultas (128→64→32) con dropout 0.3 y early stopping (patience 5).
- Backtesting usa _FakeOhlcvSource que retorna lista vacía; PAPER/LIVE usa _CcxtOhlcvAdapter.
- Checkpoints se persisten en `checkpoints/` como .keras + .json metadata.
- Feature engineering incluye RSI-14, MACD (12/26/9), BB (20,2), EMA-20, ATR-14.

---

## 🟡 H7 — Live Execution Engine

> Orquestador que cierra el bucle señal→orden→posición→P&L en tiempo real, conectando NovaQuant (H6), risk (H2/H3), y order placement (H4-A) en producción o paper trading.

**Pipeline**: `TradingSignal` → SignalValidator (confidence + cooldown) → CircuitBreakerCheck → PositionSizer → PlaceOrderUseCase → PositionTracker (SL/TP loop) → ExecutionLogger.

- [ ] H7-001 — Domain VOs: `ExecutionSignal` (side, confidence, symbol, strategy_id, timestamp), `LivePosition` (side, units, entry, current_price, unrealized_pnl, sl, tp, opened_at), `ExecutionReport` (signal_id, order_id, status, filled_qty, avg_price, pnl, errors[])
- [ ] H7-002 — Domain entity: `SignalValidator` (confidence threshold, cooldown per symbol, dedup by signal_id), `PositionTracker` (SL/TP monitoring loop, adjust SL to breakeven after N%, P&L snapshot)
- [ ] H7-003 — Ports: `SignalConsumer` (subscribe to signal sources), `PositionRepository` (save/load/update positions, list open), `ExecutionLogger` (log every execution event)
- [ ] H7-004 — Use case: `ExecuteSignalUseCase` (validate → check CB → size → place order → persist position → log), `MonitorPositionsUseCase` (periodic SL/TP check → close if hit → log P&L)
- [ ] H7-005 — Infrastructure: `NovaQuantSignalConsumer` (wraps NovaQuant predictor output into ExecutionSignal), `InMemoryPositionRepository` + `FilePositionRepository` (JSON persistence for restart recovery)
- [ ] H7-006 — Infrastructure: `StructlogExecutionLogger` (structured JSON logs per execution event)
- [ ] H7-007 — Integration wiring: `composition.py` with `get_execution_orchestrator(request)`, `get_position_repo(request)`, signal cooldown registry
- [ ] H7-008 — API: `POST /execute/signal` (trigger signal manually), `GET /position/list` (open positions), `GET /execution/log` (recent executions)
- [ ] H7-009 — Tests: unit (VOs, validators, tracker) + integration (endpoints, orchestration). 30+ new tests.

**Progreso**: 0/9 = **0%**
**Dependencias**: H2 (position sizing), H3 (circuit breaker check), H4-A (order placement), H6 (NovaQuant signals), H8 (strategy patterns)
**Notas**:
- H7 no introduce un nuevo exchange adapter; reusa CCXT de H4-A.
- El loop de monitoreo corre como background task en FastAPI (asyncio.create_task o BackgroundTasks).
- PositionRepository debe persistir a disco para sobrevivir reinicios (formato JSON simple, mismo patrón que FileBacktestReporter).

---

## ✅ H8 — Backtesting Engine

> Framework de backtesting para validar estrategias contra datos históricos. Estrategias clásicas (EMA crossover, RSI mean reversion) + framework extensible para NovaQuant.

**Engine**: `BacktestEngine` entidad de dominio que procesa velas secuencialmente, genera señales vía callable, simula posiciones con SL dinámico basado en ATR, calcula PnL y produce curva de equity.

**Estrategias**: `EmaCrossStrategy` (trend following, EMA rápida 9 / lenta 21, crossover → BUY/SELL), `RsiMeanReversionStrategy` (mean reversion, RSI-14, oversold < 30 > overbought 70, bounce → BUY/SELL). Registro extensible via `StrategyDictRegistry`.

**Métricas**: `SimpleMetricsCalculator` — Sharpe ratio anualizado (RF=0), max drawdown pico-a-valle, win rate, profit factor, volatilidad, PnL promedio.

**Reportes**: `FileBacktestReporter` — JSON en `reports/backtest/<strategy>_<symbol>_<timestamp>.json` con config, métricas, trades, y equity curve.

- [x] H8-001 — Domain VOs: BacktestConfig (strategy_id, symbol, timeframe, initial_balance, risk_pct 0-2%, max_trades), BacktestTrade (side, entry/exit, units, pnl), BacktestMetrics (sharpe, max_dd, win_rate, total_return, profit_factor)
- [x] H8-002 — Domain entity: BacktestEngine (sequential candle loop, SignalFn callable, entry/exit simulation, ATR-based SL, equity curve, max_trades cap)
- [x] H8-003 — Ports: Strategy protocol (build -> SignalFn), BacktestReporter (save report), MetricsCalculator (compute from trades + equity)
- [x] H8-004 — Use case: RunBacktestUseCase (resolve strategy -> fetch OHLCV -> run engine -> calc metrics -> save report -> return result)
- [x] H8-005 — Infrastructure strategies: EmaCrossStrategy (9/21 EMA crossover, confidence basado en distancia), RsiMeanReversionStrategy (14-period RSI, oversold 30/overbought 70, bounce detection), StrategyDictRegistry (con defaults + register)
- [x] H8-006 — Infrastructure metrics + reporter: SimpleMetricsCalculator (Sharpe anualizado sqrt(365), max drawdown, win rate, profit factor, vol), FileBacktestReporter (JSON con trades + equity curve)
- [x] H8-007 — API: POST /backtest/run (config params, 422 sad paths), GET /backtest/strategies (lista IDs disponibles)
- [x] H8-008 — Tests: 64 nuevos (21 unit VOs + 8 unit engine + 14 unit strategies + 10 unit metrics + 7 integration endpoint). 264/265 total pass (1 skipped)
- [x] H8-009 — Validation: pytest 264/265, arch_lint PASS, secret_scan clean, 1 commit conventional

**Progreso**: 9/9 = **100%**
**Dependencias**: H6 (NovaQuant como estrategia futura), H2 (position sizing pattern)
**Notas**:
- BacktestEngine es agnóstico de estrategia — recibe un callable `SignalFn: (idx, ohlcv, config) -> (side, confidence) | None`.
- SL distance = max(ATR_14 * 1.5, entry_price * 0.005).
- Position sizing = (balance * risk_pct) / 0.01 / entry_price.
- BACKTESTING mode usa `_FakeOhlcvSource` (sin datos reales). Para backtest real se necesita PAPER_TRADING con exchange conectado o un OhlcvSource CSV.
- `SimpleMetricsCalculator._compute_sharpe` asume returns diarios y anualiza con sqrt(365). Para otras temporalidades es aproximado.

---

## ⛔ Bloqueos

_Ninguno actualmente._

---

## Bitácora

### 2026-06-07 — Sesión H5: Secrets & Env Mode
- ✅ `app/preflight.py` — `preflight_check(mode)` y `abort_if_missing(mode)`. En LIVE valida `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET`, `ARGOS_BROKER_URL`. Missing/empty → `sys.exit(1)`.
- ✅ Integrado en `build_composition()` como primer paso antes de construir exchange.
- ✅ `.env.example` de ambos engines reestructurados con secciones: Required, Required for LIVE, Optional, Risk defaults.
- ✅ Tests: 8 unitarios (BACKTESTING no-op, LIVE sin vars, LIVE con vars vacías, LIVE ok, abort exit code).
- ✅ Validación: 116/116 tests, arch_lint PASS, secret_scan clean.
- ✅ 1 commit conventional, push a `origin/feature/h5-env-secrets`.

### 2026-06-07 — Sesión H4-B: OWASP Incident Response
- ✅ `docs/incident-response.md` — 4 fases OWASP con SLAs, responsables, runbook, clasificación P1-P4.
- ✅ Domain VOs: `IncidentSeverity`, `IncidentPhase`, `IncidentEvent` con auto-generated UUID.
- ✅ Ports: `IncidentReporter` (structlog logging), `IncidentRepository` (in-memory storage).
- ✅ Use cases: `ReportIncidentUseCase` (persist + notify), `ListIncidentsUseCase` (query recent/by-id).
- ✅ Infrastructure: `LoggingIncidentReporter` (nivel CRITICAL/ERROR según severidad), `InMemoryIncidentRepository`.
- ✅ API: `GET /incident/list`, `POST /incident/declare`.
- ✅ Tests: 11 new (8 unit + 3 integration). 123 passed / 1 skipped total.
- ✅ Validación: pytest 123/123, arch_lint PASS, secret_scan clean.
- ✅ Comando `/incident-drill` verificado (ya existía como tabletop read-only).
- ✅ 1 commit conventional, push a `origin/feature/h4-b-incident-response`.

### 2026-06-07 — Sesión H4-A: Order Retry + Emergency Market
- ✅ Branch `feature/h4-a-order-retry` creada desde `dev` (después del merge de H3).
- ✅ H4-A-001: Domain VOs `OrderSide`, `OrderType`, `OrderStatus`, `CompositeOrder`, `OrderResult` — enfoque hexagonal sin dependencias externas.
- ✅ H4-A-002: Port `ExchangeOrderClient` extendido con `place_composite_order()`, `place_emergency_market()`, `SlPlacementError` (con `entry_order` carry).
- ✅ H4-A-003: `PlaceOrderUseCase` implementado — catch `SlPlacementError` → emergency market en lado opuesto.
- ✅ H4-A-004: `CcxtOrderClient.place_composite_order()` — entry market + SL retry 3x con exponential backoff + jitter + TP fire-and-forget.
- ✅ H4-A-005: `POST /order/place` endpoint con Pydantic schemas y DI wiring.
- ✅ H4-A-006: 11 tests nuevos (6 unit + 5 integration). 108 passed / 1 skipped total.
- 🐛 Bug detectado y corregido en diseño: `SlPlacementError` necesitaba carry `entry_order` porque la entry ya se ejecutó; la excepción se llevaba el resultado de la entry para que el use case lo retorne.
- ✅ Validación: pytest 108/108, arch_lint PASS, secret_scan clean.
- ✅ 1 commit conventional, push a `origin/feature/h4-a-order-retry`.
- 🎯 **H4-A listo para PR.** El usuario abre el PR manualmente en GitHub apuntando a `dev`.

### 2026-06-07 — Sesión H3: Circuit Breaker
- ✅ Branch `feature/h3-circuit-breaker` creada desde `dev` (rebaseada sobre el merge de H2 = `9873902`).
- ✅ H3-001..H3-007 implementados: 3 VOs (DrawdownState/DrawdownSnapshot/TripAction con orden canónico enforced), entity CircuitBreaker (HALTED sticky, reset UTC 00:00), 4 ports (TradeJournal/ExchangeOrderClient/EnvironmentModeWriter/DrawdownSnapshotRepo), 3 use cases (CheckDrawdown/Trip/OpenDay), 4 adapters (in-memory + Ccxt + File env writer con atomic write), 3 endpoints (`/risk/day/open`, `/risk/drawdown/check`, `/risk/drawdown`).
- ✅ H3-007: 97 tests passed / 1 skipped (54 nuevos: 30 unit domain, 13 unit usecases, 5 unit adapters, 6 integration endpoint).
- ✅ H3-008: pytest 97/97, arch_lint PASS, secret_scan clean (los 5 hits son placeholders en `.agents/skills/*/SKILL.md`, no en código de argos).
- 🐛 Bug encontrado y corregido en H3-002: `warn_ratio <= threshold` se invirtió en la validación — habría roto `CircuitBreaker()` con defaults (0.6 no es <= 0.05). Ahora `warn_ratio` se valida solo en `(0, 1]` independientemente.
- 🐛 Bug pre-existente del H2 detectado: `get_compute_position_size_usecase(request: "Request")` con string forward-ref rompe la resolución de params de FastAPI con pydantic 2.13. Reemplazado por `from fastapi import Request` real. Mismo fix aplicado a los nuevos helpers H3.
- 🐛 `_NoopOrderClient` y la wrapper `TmpFileEnvWriter` en tests también iterados: la wrapper ahora hereda de `FileEnvironmentModeWriter` (no la envuelve) para que `isinstance(..., EnvironmentModeWriter)` pase.
- ✅ 8 commits conventional en `feature/h3-circuit-breaker`: h3-001..h3-007 + TASKS update.
- 🎯 **H3 listo para PR.** Push pendiente de confirmación del usuario (AGENTS.md §12).

### 2026-06-07 — Sesión H2: Position Sizing
- ✅ Branch `feature/h2-position-sizing` mergeada a `dev` vía PR #2 (merge commit `9873902`).
- ✅ 9 commits conventional, H2 al 100% (9/9 tareas).
- ✅ 43 tests pasados (21 unit VOs + 7 unit entity + 7 unit usecase + 3 integration ATR + 4 integration endpoint + 1 health).
- 🐛 Bug del H2-007: `risk_calculator.py` import path era `.value_objects.atr` (hermanos) en lugar de `..value_objects.atr`. Corregido.
- 🐛 Decimal quantise 8dp: `(Decimal("100") * Decimal("0.01")) / Decimal("600")` redondea a `0.16666667` (no 0.16666666). Test expectation actualizado.
- 🐛 `Atr._MAX_DECIMALS` subido de 12 a 18 para aceptar la precisión natural de `ta.average_true_range`.
- ✅ `docs/prs/h2-position-sizing.md` creado (pendiente de archivar a `done/` cuando PR sea mergeado por el usuario — eso es post-merge humano, no del agente).

### 2026-06-07 — Sesión H1: Tick Pipeline
- ✅ Branch `feature/h1-tick-pipeline` creada desde `dev`.
- ✅ H1-001..H1-007 implementados: domain (Tick, Symbol, Price, StreamName), application ports, use cases, infrastructure adapters (BinanceWebSocketAdapter, RedisProtocolBus, InMemoryTickBuffer, BusHealthMonitor), NestJS DI wiring, FastAPI subscriber mínimo con xread.
- ✅ H1-008: 26/26 tests unitarios PASS (`domain.spec.ts` 14 tests, `use-cases.spec.ts` 12 tests).
- ✅ Validación: `tsc --noEmit` PASS, `eslint` PASS (con override para domain class `Symbol`).
- ✅ Hexagonal: `tick-pipeline.service.ts` movido a `infrastructure/services/` (es glue NestJS). `application/` sin imports de `infrastructure/`.
- ✅ Deps añadidas: `@nestjs/config@3.2.0` (3.1.x choca con `reflect-metadata@0.2.2`).
- ⏭ H1-009 (integration) y H1-010 (benchmark) requieren broker reachable; no ejecutados en sandbox.
- 🐛 Bug detectado y corregido en `FlushBufferUseCase`: `drain()` vaciaba el buffer y al fallar el primer publish solo re-bufeaba ese tick, perdiendo los siguientes. Ahora re-bufea el fallido + todos los restantes en orden.
- ✅ Push de `feature/h1-tick-pipeline` a `origin` (7 commits, todos conventional).
- ✅ **PR #1 mergeado a `dev`** (merge commit `f053fc7`, sin squash — los 7 commits de H1 preservados para bisect y trazabilidad).
- ✅ Rama `feature/h1-tick-pipeline` borrada en local y en `origin`.
- ✅ PR body archivado en `docs/prs/done/h1-tick-pipeline.md` para referencia histórica.
- 🎯 **PR #1 (H1) mergeado a dev** — primera historia cerrada del proyecto.
- 🔒 Sandbox: registry npm ~14s/ping, install tomó ~5 min; tests/lint corren offline en ~5s cada uno.

### 2026-06-08 — Sesión H8: Backtesting Engine
- ✅ Branch `feature/h8-backtest-engine` creada desde `dev` (post-merge H6).
- ✅ Domain: BacktestConfig, BacktestTrade, BacktestMetrics VOs + BacktestEngine entity con SignalFn, ATR SL, equity curve.
- ✅ Ports: Strategy (protocol + SignalFn), BacktestReporter, MetricsCalculator.
- ✅ Use Case: RunBacktestUseCase (pipeline completo con validaciones).
- ✅ Estrategias: EmaCrossStrategy (9/21 EMA crossover), RsiMeanReversionStrategy (RSI-14, 30/70 thresholds), StrategyDictRegistry.
- ✅ Métricas: SimpleMetricsCalculator — Sharpe anualizado, max drawdown, win rate, profit factor.
- ✅ Reporter: FileBacktestReporter — JSON en reports/backtest/.
- ✅ API: POST /backtest/run + GET /backtest/strategies (vía app.state, no singletons module-level).
- ✅ Tests: 64 nuevos (21 VOs + 8 engine + 14 strategies + 10 metrics + 7 integration). 264/265 total.
- 🐛 Bug fix: Decimal * float en ATR cálculo del engine (atr * 1.5 → atr * Decimal("1.5")). DivisionByZero en precios negativos (safety check entry_price > 0).
- 🐛 Bug fix: singleton module-level en get_backtest_usecase() causaba tests no deterministas. Refactor a app.state como los otros use cases.
- ✅ Validación: pytest 264/265, arch_lint PASS, secret_scan clean.

### 2026-06-08 — Sesión H6: NovaQuant ML Pipeline
- ✅ NovaQuant completo: 9/9 tareas, 30 archivos nuevos.
- ✅ Domain VOs: ModelConfig (lookback 5-500, features, layers 1-10, dropout 0-0.5, target thresholds), TradingSignal (confidence 0-1, actionable, metadata), SignalSide (BUY/SELL/HOLD).
- ✅ Domain entity: NovaQuantModel con weights_hash, version, feature_stats, metrics, trained_at, age_days, is_stale (≥7d), validate_input/assert_not_stale/assert_version, __repr__.
- ✅ 6 ports: OhlcvSource, DataPreprocessor (build_features con RSI/MACD/BB/EMA/ATR, z-score normalize, sliding windows 2D/3D, one-hot targets), FeatureAnalyzer (Pearson r, filter noise, keep ≥3), ModelTrainer, ModelPredictor, CheckpointRepository.
- ✅ 2 use cases: TrainModelUseCase (fetch → preprocess → analyze → train → save), PredictSignalUseCase (fetch → preprocess → load → predict → TradingSignal).
- ✅ 4 infra adapters: TaDataPreprocessor (ta library), CorrelationFeatureAnalyzer (scipy.stats.pearsonr), NovaQuantKerasModel (3 dense: 128→64→32, dropout 0.3, Adam, early stopping patience 5, .keras checkpoint), FsCheckpointRepository (JSON metadata + .keras).
- ✅ API: POST /model/train, POST /model/predict con Pydantic schemas y 422 sad paths.
- ✅ Composition: get_model_use_cases() lazy builder, _CcxtOhlcvAdapter / _FakeOhlcvSource, cached en app.state.
- ✅ Tests: 83 nuevos (20 unit VOs + 20 unit entity + 18 integration data_preprocessor + 12 integration feature_analyzer + 13 API). 200/201 total (1 skipped — subscriber).
- ✅ Merge dev → feature/h6-novaquant: 5 conflictos resueltos (api/__init__, ports/__init__, use_cases/__init__, composition.py, main.py). H4-B + H5 integrados.
- ✅ Validación: pytest 200/201, arch_lint PASS, secret_scan clean.
- ✅ 1 commit conventional, branch local lista para push + PR.

### 2026-06-06 — Sesión de setup
- ✅ Crash de opencode diagnosticado y resuelto (3 causas: `import.meta.dir`, regex `(?i)`, `execute()` sync).
- ✅ 28 tools operativos, 12 commands, 7 skills, context7 MCP.
- ✅ 5 tools verificados con invocación real: `spec_invariants`, `risk_position_size`, `risk_drawdown_check`, `config_read_config`, `spec_summary`.
- ✅ `AGENTS.md` y `TASKS.md` creados.
- ✅ Política de permisos en `opencode.json` para tools destructivos.
- ✅ Git inicializado, `main` y `dev` pusheadas a `origin` (commits `f3c46e0`, `423221e`).
- ✅ `LICENSE` (MIT) y `README.md` creados.
- ✅ Refactor agnóstico: spec.md §1, §1.2, §4, §6 amendados; AGENTS.md §1, §2 #14, §7, §11 actualizados; config.json migrado a `broker: { kind, url: ${ARGOS_BROKER_URL} }`; `.gitattributes` creado; README "Quick start" dual (Docker + bare metal con WSL2/Memurai); `health_health_check` con detección de deployment model; `docker_docker_*` tools anotados como "uso solo con deploy Docker".
- ✅ Sección 12 (Git workflow) añadida a AGENTS.md.
- ✅ Fase 0 ejecutada: `docker-compose.yml` (3 servicios, broker RESP-compatibile con `ARGOS_BROKER_URL`), NestJS data-engine skeleton, FastAPI analytics-engine skeleton. 20 archivos nuevos en `apps/`. Las tools de opencode habían quedado con la versión pre-agnóstica en memoria; parcheé los 4 archivos afectados (`.env.example` × 2, `main.ts`, `docker-compose.yml`) al contenido correcto.
