# H8: Backtesting Engine with Strategies, Metrics, and API

**Implementation**: Domain VOs → Entity → Ports → Use Case → Infrastructure strategies + metrics + reporter → API → Tests

## Commit log

| Commit | Message |
|---|---|
| 1/2 | `feat(analytics-engine): h8 backtest engine with strategies, metrics, and API` |
| 2/2 | `docs(tasks): add H8 backtest engine (76/76 tasks, 100%)` |

## Changes

### New files (20)

**Domain (4)**
- `domain/value_objects/backtest_config.py` — `BacktestConfig` with strategy_id, symbol, timeframe, initial_balance (>0), risk_pct (0-2%), max_trades
- `domain/value_objects/backtest_trade.py` — `BacktestTrade` with side, entry/exit prices, units (>0), pnl, duration
- `domain/value_objects/backtest_metrics.py` — `BacktestMetrics` with sharpe_ratio, max_drawdown_pct, win_rate, total_return, profit_factor
- `domain/entities/backtest_engine.py` — `BacktestEngine` — core loop: sequential candle processing, SignalFn callable, position entry/exit with ATR-based SL (max ATR*1.5, entry*0.005), equity curve tracking

**Ports (2)**
- `application/ports/strategy.py` — `Strategy` protocol (build → SignalFn), `StrategyRegistry` protocol
- `application/ports/backtest_reporter.py` — `BacktestReporter` (save report), `MetricsCalculator` (compute from trades + equity)

**Use Cases (1)**
- `application/use_cases/run_backtest.py` — `RunBacktestUseCase` (resolve strategy → fetch OHLCV → run engine → calc metrics → save report → return result)

**Infrastructure (6)**
- `infrastructure/strategies/ema_cross.py` — `EmaCrossStrategy` (9/21 EMA crossover trend following)
- `infrastructure/strategies/rsi_mean_reversion.py` — `RsiMeanReversionStrategy` (RSI-14, oversold 30/overbought 70, bounce detection)
- `infrastructure/strategies/registry.py` — `StrategyDictRegistry` (in-memory dict with defaults + register)
- `infrastructure/backtest/metrics_calculator.py` — `SimpleMetricsCalculator` (Sharpe anualized sqrt(365), max drawdown peak-to-valley, win rate, profit factor, volatility)
- `infrastructure/backtest/file_reporter.py` — `FileBacktestReporter` (JSON to `reports/backtest/<strategy>_<symbol>_<timestamp>.json`)

**API (1)**
- `api/backtest.py` — `POST /backtest/run` (body params: strategy_id, symbol, timeframe, initial_balance, risk_pct, max_trades), `GET /backtest/strategies` (list available strategies)

**Tests (6)**
- `tests/unit/test_backtest_vos.py` — 21 tests (BacktestConfig validation bounds, BacktestTrade, BacktestMetrics)
- `tests/unit/test_backtest_engine.py` — 8 tests (min candles, no signals, buy signal, alternation, max trades, equity curve, stop loss)
- `tests/unit/test_backtest_strategies.py` — 14 tests (EMA cross validation + signal generation, RSI validation + flat data, registry)
- `tests/unit/test_backtest_metrics.py` — 10 tests (empty, all wins, all losses, mixed, Sharpe, drawdown, profit factor)
- `tests/integration/test_backtest_endpoint.py` — 7 tests (list strategies, unknown strategy 422, invalid params 422, fake source 422)

### Modified files (8)
- `api/__init__.py` — registered `backtest_router`
- `application/ports/__init__.py` — re-exported `BacktestReporter`, `MetricsCalculator`, `Strategy`, `StrategyRegistry`
- `application/use_cases/__init__.py` — re-exported `RunBacktestUseCase`, `RunBacktestError`, `RunBacktestResult`
- `composition.py` — added `get_backtest_usecase(request)` and `get_backtest_registry(request)` via app.state
- `domain/entities/__init__.py` — added `BacktestEngine`, `BacktestError`
- `domain/value_objects/__init__.py` — added `BacktestConfig`, `BacktestTrade`, `BacktestMetrics`
- `main.py` — included `backtest_router`
- `TASKS.md` — added H8 section (9/9 tasks), updated totals (76/76 = 100%)

## Key design decisions

1. **Engine is strategy-agnostic**: `BacktestEngine` receives a `SignalFn` callable `(idx, ohlcv, config) -> (side, confidence) | None`. Strategies implement `.build(config) -> SignalFn`. This decouples strategy logic from the simulation loop.
2. **ATR-based stop loss**: `max(ATR_14 * 1.5, entry_price * 0.005)`. SL is dynamic, adapting to market volatility, with a hard minimum of 0.5% to avoid noise-triggered exits.
3. **Position sizing**: follows H2's risk model: `units = (balance * risk_pct) / 0.01 / entry_price`. 1% risk per trade by default.
4. **Composition via app.state**: unlike the initial module-level singleton approach (which caused non-deterministic tests), the backtest use case is cached in `app.state.backtest_usecase` following the same pattern as NovaQuant's `get_model_use_cases`.
5. **BACKTESTING mode**: in BACKTESTING mode, uses `_FakeOhlcvSource` (empty list) which causes an expected 422 "insufficient_candles". For real backtests, run in PAPER_TRADING mode with an exchange connected, or provide a CSV-based OhlcvSource.
6. **Strategies**: EMA crossover (9/21) for trend following and RSI mean reversion (14/30/70) for counter-trend. Both are registered in `StrategyDictRegistry` and accessible via `GET /backtest/strategies`. NovaQuant integration is a future story (H8-FU1).

## Test coverage

- **Unit (53)**: 21 VOs + 8 engine + 14 strategies + 10 metrics — validation boundaries, edge cases, exhaustive sad paths
- **Integration (11)**: 7 endpoint + 4 fixtures — HTTP contract, error handling, fake source behavior
- **Total**: 264 passed / 1 skipped (subscriber requires broker)
