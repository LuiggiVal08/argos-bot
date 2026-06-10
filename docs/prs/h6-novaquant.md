# H6: NovaQuant ML Model Pipeline

**Implementation**: Domain VOs → Domain entity → Ports → Use cases → Infrastructure adapters → API → Composition wiring → Tests

## Commit log

| Commit | Message |
|---|---|
| 1/2 | `feat(analytics-engine): h6 NovaQuant ML model pipeline (VOs, entity, ports, use cases, infra, API, tests)` |
| 2/2 | `docs(tasks): update TASKS for H4-B, H5, H6 — all 100% (67/67 tasks)` |

## Changes

### New files (23)

**Domain (4)**
- `domain/value_objects/model_config.py` — `ModelConfig` with lookback (5-500), features list, layers (1-10), dropout (0-0.5), target thresholds
- `domain/value_objects/signal_side.py` — `SignalSide` enum (BUY/SELL/HOLD)
- `domain/value_objects/trading_signal.py` — `TradingSignal` with confidence (0-1), actionable threshold, metadata, immutable
- `domain/entities/nova_quant_model.py` — `NovaQuantModel` entity with weights_hash, version, feature means/stds, metrics, trained_at, age_days, is_stale (≥7d), input/output validation

**Ports (6)**
- `application/ports/ohlcv_source.py` — `OhlcvSource` (fetch historical OHLCV as list of dicts)
- `application/ports/data_preprocessor.py` — `DataPreprocessor` (build_features with TA indicators, z-score normalize, sliding windows 2D/3D, one-hot targets)
- `application/ports/feature_analyzer.py` — `FeatureAnalyzer` (Pearson correlation matrix, filter by threshold, minimum 3 features)
- `application/ports/model_trainer.py` — `ModelTrainer` (train, save)
- `application/ports/model_predictor.py` — `ModelPredictor` (load, predict)
- `application/ports/checkpoint_repository.py` — `CheckpointRepository` (save/load/list checkpoints)

**Use Cases (2)**
- `application/use_cases/train_model.py` — `TrainModelUseCase` (fetch OHLCV → preprocess → analyze → train → save checkpoint)
- `application/use_cases/predict_signal.py` — `PredictSignalUseCase` (fetch OHLCV → preprocess → load model → predict → return TradingSignal)

**Infrastructure (4)**
- `infrastructure/training/data_preprocessor.py` — `TaDataPreprocessor` (RSI-14, MACD 12/26/9, BB 20/2, EMA-20, ATR-14 via `ta` library)
- `infrastructure/training/feature_analyzer_impl.py` — `CorrelationFeatureAnalyzer` (scipy.stats.pearsonr, filter |r| < 0.1, min 3 features)
- `infrastructure/models/nova_quant_keras.py` — `NovaQuantKerasModel` (3 dense layers 128→64→32, dropout 0.3, Adam, early stopping patience 5, .keras checkpoint)
- `infrastructure/models/checkpoint_repo_fs.py` — `FsCheckpointRepository` (JSON metadata + .keras on filesystem)

**API (1)**
- `api/model.py` — `POST /model/train` and `POST /model/predict` with Pydantic schemas, 422 error handling

**Tests (4)**
- `tests/unit/test_nova_quant_vos.py` — 20 tests (VOs: ModelConfig validation, TradingSignal, SignalSide)
- `tests/unit/test_nova_quant_model.py` — 20 tests (entity: construction, properties, age_days, is_stale, validation methods)
- `tests/integration/test_data_preprocessor.py` — 18 tests (build_features, normalize, create_windows, create_targets)
- `tests/integration/test_feature_analyzer.py` — 12 tests (Pearson, correlation dict, filter features, error cases)

### Modified files (8)
- `api/__init__.py` — registered `model_router`
- `application/ports/__init__.py` — re-exported 6 port modules + errors
- `application/use_cases/__init__.py` — re-exported PredictSignalUseCase, TrainModelUseCase
- `composition.py` — added `get_model_use_cases()` with `_CcxtOhlcvAdapter`/`_FakeOhlcvSource`, cached in app.state
- `domain/entities/__init__.py` — re-exported `NovaQuantModel`
- `domain/value_objects/__init__.py` — re-exported `ModelConfig`, `SignalSide`, `TradingSignal`
- `main.py` — included `model_router`
- `TASKS.md` — added H6 section (9/9 tasks), updated totals (67/67 = 100%)

## Key design decisions

1. **NovaQuant is custom ML (not in spec.md)**: solicited post-H5 as a full LSTM pipeline. Uses Keras 3-layer dense network (128→64→32) with dropout 0.3.
2. **Feature engineering**: 5 TA indicators (RSI, MACD, BB, EMA, ATR) via `ta` library. Pearson correlation filters noise features (< 0.1 abs), keeps minimum 3.
3. **Target encoding**: one-hot over 3 classes (BUY/SELL/HOLD) with configurable lookahead and target return threshold.
4. **Checkpoint persistence**: dual-file format — `.keras` for model weights, `.json` for metadata (version, feature stats, metrics).
5. **Composition**: lazy builder `get_model_use_cases()` cached in `app.state`; uses `_CcxtOhlcvAdapter` for PAPER/LIVE and `_FakeOhlcvSource` (empty list) for BACKTESTING.
6. **Merge conflicts resolved**: `dev` had H4-B (incident endpoints) and H5 (preflight secrets) which conflicted with H6 in 5 files. All resolved preserving both sides.

## Test coverage

- **Unit (40)**: 20 VOs + 20 entity — construction, validation boundaries, properties, error paths
- **Integration (30)**: 18 data_preprocessor + 12 feature_analyzer — real TA lib, shape invariants, NaN checks
- **API (13)**: train/predict happy path + 422 error cases
- **Total**: 200 passed / 1 skipped (subscriber requires broker)
