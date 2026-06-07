# H2: Position Sizing (≤1% del free balance)

> spec.md §5 Historia 2. Domain layer `CalculadorRiesgo` calcula
> `units = (free_balance * risk_pct) / atr`. SL dinámico a distancia
> proporcional al ATR. Sad path: CCXT timeout o balance=0 → abort;
> size < min_lot → descartar con warning.

## Summary

Institucionaliza la fórmula de sizing dentro del analytics-engine con
hexagonal estricta, agregando los dos sad paths del spec (abort por
provider error, descarte por min_lot) que el tool `risk_position_size`
no cubría.

### Domain (sin imports de application/infrastructure — invariant #8)
- `domain/value_objects/atr.py`: `Atr` (Decimal, >0, ≤18dp).
- `domain/value_objects/risk_pct.py`: `RiskPct` (Decimal, 0<x≤0.02; cap del spec).
- `domain/value_objects/position_size.py`: `PositionSize` (inmutable, dataclass frozen).
- `domain/entities/risk_calculator.py`: `RiskCalculator.calculate(balance, atr, entry, risk_pct)`.

### Application (solo ports, sin adapters — invariant #9)
- `application/ports/balance_provider.py`: `BalanceProvider` (Protocol) + `BalanceProviderError`.
- `application/ports/atr_calculator.py`: `AtrCalculator` (Protocol) + `AtrCalculatorError`.
- `application/ports/min_lot_provider.py`: `MinLotProvider` (Protocol) + `MarketConstraints`.
- `application/use_cases/compute_position_size.py`: orquesta los 3 ports + min_lot check.

### Infrastructure (ccxt, ta, pandas solo aquí — invariant #11)
- `infrastructure/balance/ccxt_balance_provider.py`: fetch via `ccxt.async_support`.
- `infrastructure/balance/mock_balance_provider.py`: para BACKTESTING y tests.
- `infrastructure/market/ccxt_min_lot_provider.py`: lee `market.limits` de ccxt.
- `infrastructure/indicators/ta_atr_calculator.py`: usa `ta.volatility.average_true_range`, fuente de candles inyectable.
- `infrastructure/ohlcv/ccxt_ohlcv_source.py`: fuente OHLCV default via ccxt.

### API + composition root
- `api/risk.py`: `POST /risk/position-size` con validación Pydantic y manejo de sad paths.
- `composition.py`: `build_composition()` selecciona adapters según `ENVIRONMENT_MODE` (BACKTESTING / PAPER / LIVE).
- `main.py`: lifespan con `build_composition()` + cierre de CCXT en shutdown.

## Commits (8)

```
ae6ed3b docs(tasks): h2 in progress and bitacora entry
b6e4c1f test(analytics-engine): h2-007 unit and integration tests for h2
89f1e2a feat(analytics-engine): h2-006 api endpoint and composition root
71d3b4f feat(analytics-engine): h2-005 infrastructure adapters for h2 ports
3e0b6cd feat(analytics-engine): h2-003 h2-004 application ports and use case
4afd218 feat(analytics-engine): h2-002 domain entity RiskCalculator
2c8b5f1 feat(analytics-engine): h2-001 domain value objects for position sizing
```

## Validation status

| Check | Result |
|---|---|
| `pytest tests/` | **43 passed, 1 skipped** (H1 broker contract test needs `ARGOS_BROKER_URL`) |
| `mypy app/ --ignore-missing-imports` | **Success: no issues found in 30 source files** |
| Hexagonal: `domain/` ⊄ `app/{application,infrastructure,api,composition,main}` | PASS |
| Hexagonal: `application/` ⊄ `app/{infrastructure,api,composition,main}` | PASS |
| `secret_scan` (manual grep) | clean (no hardcoded keys) |

## How to validate in your environment

```bash
cd apps/analytics-engine
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pip install httpx  # for testclient
.venv/bin/pytest tests/ -v
.venv/bin/mypy app/ --ignore-missing-imports

# Run the engine locally (BACKTESTING mode, no network)
ENVIRONMENT_MODE=BACKTESTING .venv/bin/python -m app.main
# In another terminal:
curl -X POST http://localhost:8000/risk/position-size \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC/USDT","entry_price":"60000"}'
```

## Sad path coverage (spec §5 Historia 2)

| Sad path | Where it fires | Surfaced as |
|---|---|---|
| CCXT timeout / network error on `fetch_balance` | `CcxtBalanceProvider.get_free_balance` | `BalanceProviderError` → `ComputePositionSizeError("balance_unavailable")` → HTTP 422 |
| Balance returns 0 or invalid | `CcxtBalanceProvider` (defensive check) | same as above |
| Insufficient candles for ATR window | `TaAtrCalculator.get_atr` | `AtrCalculatorError("insufficient_candles")` → HTTP 422 |
| NaN from `ta` library | `TaAtrCalculator` | `AtrCalculatorError("ta_returned_nan")` |
| Network error fetching market limits | `CcxtMinLotProvider.get_constraints` | `MinLotProviderError` → HTTP 422 |
| Computed `units` < `min_qty` | `ComputePositionSizeUseCase` | `PositionSizeBelowMinLotError` → HTTP 422 (spec: discard signal) |
| Computed `notional` < `min_notional` | `ComputePositionSizeUseCase` | same |
| `risk_pct` > 0.02 (spec cap) | `RiskPct` constructor | `InvalidRiskPctError` → HTTP 422 |

## Known follow-ups (not blocking H2)

- **H2-FU1 — Strategy signal integration**: H2 implements the
  calculator and a synchronous HTTP entry point. The spec's
  "Una señal de trading llega al Caso de Uso" path is wired in
  a later story (candles aggregation + signal generation).
- **H2-FU2 — ATR precision**: spec doesn't constrain ATR precision
  beyond "valid". We use 18dp to accept `ta`'s natural output. If
  exchange APIs later demand a fixed precision, tighten the VO.
- **H2-FU3 — LIVE secrets pre-flight**: composition root reads
  `EXCHANGE_API_KEY` and `EXCHANGE_API_SECRET` from env. H5 will
  add the spec's pre-flight check that aborts init when LIVE mode
  is selected without secrets.

## Checklist

- [x] Branch is `feature/h2-position-sizing` from `dev`.
- [ ] Branch pushed to `origin` (waiting for user OK per AGENTS.md §12).
- [x] All commits follow Conventional Commits.
- [x] TASKS.md H2 marked in progress (9/9 sub-tasks).
- [x] AGENTS.md invariants #1, #2, #8, #9, #11 respected.
- [ ] Manual review by maintainer.
- [ ] Manual merge to `dev` (merge commit, not squash).
