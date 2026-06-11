#!/usr/bin/env python3
"""E2E test: NovaQuant prediction → ExecuteTradingSignalUseCase.

Pipeline:
  1. Load candles from Parquet dataset (real market data)
  2. Build 19 features via TaDataPreprocessor.build_features
  3. Normalize with saved scaler
  4. Create sliding window
  5. Predict via NovaQuantPyTorchModel → TradingSignal
  6. Feed TradingSignal to ExecuteTradingSignalUseCase
  7. Print execution result (skipped or order placed)

Usage:
  .venv/bin/python scripts/mock_execute_signal.py

Requires:
  - import_pytorch_model.py already executed (model dir at
    ~/.novaquant/checkpoints/)
  - Parquet dataset at apps/analytics-engine/data/datasets/
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent / "app"
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import numpy as np

from app.application.ports.atr_calculator import AtrCalculator
from app.application.use_cases.execute_trading_signal import (
    ExecuteTradingSignalUseCase,
    ExecuteSignalResult,
)
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.trading_signal import TradingSignal
from app.infrastructure.exchange.mock_exchange_adapter import MockExchangeAdapter
from app.infrastructure.execution import InMemoryPositionRepository
from app.infrastructure.execution.structlog_execution_logger import (
    StructlogExecutionLogger,
)


class _FixedAtrCalculator:
    async def get_atr(
        self, symbol: str, timeframe: str = "1m", window: int = 14
    ) -> Atr:
        return Atr(Decimal("350"))


LATEST_PARQUET = _HERE.parent / "data" / "datasets" / "dataset_btc_usdt_5m.parquet"
MODEL_DIR = Path.home() / ".novaquant" / "checkpoints" / "1.0.0"


def _load_pipeline():
    """Reuse the same prediction pipeline as mock_predict.py."""
    from app.infrastructure.training.data_preprocessor import (
        TaDataPreprocessor,
    )

    preprocessor = TaDataPreprocessor()
    return preprocessor


def _load_latest_parquet(n_candles: int = 70):
    import pandas as pd
    df = pd.read_parquet(LATEST_PARQUET)
    df = df.tail(n_candles).reset_index(drop=True)
    records: list[dict] = []
    for _, row in df.iterrows():
        records.append({
            "timestamp": int(row["timestamp"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    last_close = Decimal(str(records[-1]["close"]))
    return records, df["close"].iloc[-1], last_close


def _load_model():
    import torch
    from app.infrastructure.models.nova_quant_pytorch import (
        NovaQuantPyTorchModel,
    )

    ps_path = MODEL_DIR / "weights.keras"
    pk_path = MODEL_DIR / "scaler.pkl"

    model = NovaQuantPyTorchModel()

    from app.domain.value_objects.model_config import ModelConfig
    from app.infrastructure.training.data_preprocessor import (
        TaDataPreprocessor,
    )
    cfg = ModelConfig(
        lookback=60,
        confidence_threshold=0.55,
        layers=(128, 1),
        features=TaDataPreprocessor.FEATURE_NAMES,
    )
    model.load_checkpoint(str(ps_path), str(pk_path), cfg)
    return model, cfg


async def main() -> None:
    print("=" * 60)
    print("Mock Execute Signal -- E2E Pipeline")
    print("=" * 60)

    for f in [LATEST_PARQUET, MODEL_DIR / "weights.keras", MODEL_DIR / "scaler.pkl"]:
        if not f.exists():
            print(f"  File not found: {f}")
            sys.exit(1)

    print(f"\n[1] Loading model from {MODEL_DIR} ...")
    model, cfg = _load_model()
    print(f"    Model loaded: {model.is_loaded()}")

    print(f"[2] Loading {LATEST_PARQUET.name} ...")
    ohlcv, close_series, close_price = _load_latest_parquet(70)
    print(f"    {len(ohlcv)} candles loaded")
    close_f = float(close_series)
    print(f"    Close: {close_f:.2f}")

    print("[3] Building 19 features ...")
    preprocessor = _load_pipeline()
    features_raw = await preprocessor.build_features(ohlcv, cfg)
    print(f"    Shape: {features_raw.shape[0]} rows x {features_raw.shape[1]} cols")
    print(f"    NaN: {np.isnan(features_raw).sum()}")

    print("[4] Loading and applying scaler ...")
    import pickle
    with open(MODEL_DIR / "scaler.pkl", "rb") as f:
        scaler = pickle.load(f)
    feature_means = np.array(scaler.mean_, dtype=np.float64)
    feature_stds = np.array(np.sqrt(scaler.var_), dtype=np.float64)
    features_norm, _, _ = await preprocessor.normalize(
        features_raw, tuple(feature_means), tuple(feature_stds)
    )
    print(f"    Normalized shape: {features_norm.shape}")

    print(f"[5] Creating windows (lookback={cfg.lookback}) ...")
    windows = await preprocessor.create_windows(features_norm, cfg.lookback)
    print(f"    Windows: {windows.shape[0]}")
    last_window = windows[-1]

    print("[6] Running inference ...")
    signal: TradingSignal = await model.predict(last_window, confidence_threshold=0.55)
    print(f"    Signal: {signal.side.name} @ {signal.confidence:.4f}")
    print(f"    Close: ${close_price:,.2f}")

    print("\n[7] Wiring use case with MockExchangeAdapter ...")
    mock_gateway = MockExchangeAdapter()
    atr_calc = _FixedAtrCalculator()
    position_repo = InMemoryPositionRepository()
    logger = StructlogExecutionLogger()

    use_case = ExecuteTradingSignalUseCase(
        exchange_gateway=mock_gateway,
        atr_calculator=atr_calc,
        position_repo=position_repo,
        execution_logger=logger,
        confidence_threshold=0.55,
        sl_atr_mult=2.0,
        tp_atr_mult=3.5,
    )

    print(f"[8] Executing signal on BTC/USDT, amount=0.01 ...")
    result: ExecuteSignalResult = await use_case.execute(
        signal=signal,
        symbol="BTC/USDT",
        close_price=close_price,
        amount=Decimal("0.01"),
    )

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    if result.skipped:
        print(f"  SKIPPED: {result.reason}")
    else:
        assert result.report is not None
        assert result.position is not None
        print(f"  Report:   id={result.report.report_id} "
              f"status={result.report.status}")
        print(f"  Position: id={result.position.position_id} "
              f"side={result.position.side.value} "
              f"units={result.position.units}")
        print(f"  Order:    {mock_gateway.last_order}")

    if result.skipped:
        print("\n  No order placed (HOLD or low-confidence)")
    else:
        assert mock_gateway.placed_orders, "Expected >=1 order"
        order = mock_gateway.last_order
        print(f"\n  Order placed: {order['symbol']} {order['side']} "
              f"qty={order['amount']}")
        assert order["sl_price"] is not None, "SL must be set"
        assert order["tp_price"] is not None, "TP must be set"
        assert order["sl_price"] < order["tp_price"], "SL < TP expected"
        print(f"  SL @ {order['sl_price']:.2f}, TP @ {order['tp_price']:.2f}")
        print("  All assertions passed.")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
