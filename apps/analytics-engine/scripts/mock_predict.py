#!/usr/bin/env python3
"""End-to-end mock test: load 60 real candles, run the full pipeline, print BUY/HOLD.

Usage:
    python mock_predict.py [--candles 70] [--threshold 0.55]

Pipeline (offline, no CCXT, no HTTP):
    1. Load OHLCV from Parquet dataset
    2. Compute 19 features (TaDataPreprocessor.build_features)
    3. Normalize with StandardScaler from Colab
    4. Create sliding window (lookback=60)
    5. PyTorch LSTM inference -> sigmoid prob
    6. Print BUY/HOLD + diagnostics
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent / "app"
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import numpy as np
import pandas as pd


def load_ohlcv_from_parquet(
    parquet_path: str,
    n_candles: int,
) -> list[dict]:
    """Load raw OHLCV from the Parquet dataset.
    
    Returns list[dict] with keys: timestamp, open, high, low, close, volume.
    Takes the LAST `n_candles` rows for most recent market state.
    """
    df = pd.read_parquet(parquet_path)
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
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E mock test for PyTorch LSTM")
    parser.add_argument("--candles", type=int, default=70,
                        help="number of candles to load (default 70, need > lookback=60)")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="confidence threshold (default 0.55)")
    parser.add_argument("--pt", default=str(_HERE.parent / "models" / "best_argos_lstm.pt"),
                        help="path to .pt weights")
    parser.add_argument("--pkl", default=str(_HERE.parent / "models" / "scaler_argos.pkl"),
                        help="path to .pkl scaler")
    parser.add_argument("--parquet",
                        default=str(_HERE.parent / "data" / "datasets" / "dataset_btc_usdt_5m.parquet"),
                        help="path to Parquet dataset")
    args = parser.parse_args()

    # ── 0. Validate files ─────────────────────────────────────────────
    for f in [args.pt, args.pkl, args.parquet]:
        p = Path(f)
        if not p.exists():
            print(f"  File not found: {p}")
            sys.exit(1)

    print("=" * 60)
    print("  NovaQuant PyTorch — E2E Mock Test")
    print("=" * 60)
    print(f"  Candles:     {args.candles}")
    print(f"  Threshold:   {args.threshold}")
    print(f"  Model:       {args.pt}")
    print(f"  Scaler:      {args.pkl}")
    print(f"  Data:        {args.parquet}")
    print()

    # ── 1. Load OHLCV ─────────────────────────────────────────────────
    print("[1/7] Loading OHLCV from Parquet...", end=" ")
    ohlcv = load_ohlcv_from_parquet(args.parquet, args.candles)
    print(f"{len(ohlcv)} candles loaded")
    print(f"       Range: {pd.Timestamp(ohlcv[0]['timestamp'], unit='ms')} "
          f"-> {pd.Timestamp(ohlcv[-1]['timestamp'], unit='ms')}")
    print(f"       Close: {ohlcv[0]['close']:.2f} -> {ohlcv[-1]['close']:.2f} "
          f"({(ohlcv[-1]['close']/ohlcv[0]['close']-1)*100:+.2f}%)")
    print()

    # ── 2. Build features ─────────────────────────────────────────────
    from app.infrastructure.training.data_preprocessor import TaDataPreprocessor
    from app.domain.value_objects.model_config import ModelConfig

    cfg = ModelConfig(
        lookback=60,
        confidence_threshold=args.threshold,
        layers=(128, 1),
        features=TaDataPreprocessor.FEATURE_NAMES,
    )

    preprocessor = TaDataPreprocessor()
    import asyncio
    features_raw = asyncio.run(preprocessor.build_features(ohlcv, cfg))
    print(f"[2/7] Features computed: {features_raw.shape}")
    print(f"       Shape: {features_raw.shape[0]} rows x {features_raw.shape[1]} cols")
    print(f"       NaN count: {np.isnan(features_raw).sum()}")
    print(f"       Feature range: [{features_raw.min():.4f}, {features_raw.max():.4f}]")
    print()

    # ── 3. Load scaler ────────────────────────────────────────────────
    import pickle
    with open(args.pkl, "rb") as f:
        scaler = pickle.load(f)
    feature_means = np.array(scaler.mean_, dtype=np.float64)
    feature_stds = np.array(np.sqrt(scaler.var_), dtype=np.float64)
    print(f"[3/7] Scaler loaded: {len(feature_means)} features")
    print(f"       Mean[:3]:  {feature_means[:3]}")
    print(f"       Std[:3]:   {feature_stds[:3]}")
    if len(feature_means) != features_raw.shape[1]:
        print(f"       WARNING: scaler has {len(feature_means)} features, "
              f"preprocessor has {features_raw.shape[1]}")
    print()

    # ── 4. Normalize ──────────────────────────────────────────────────
    features_norm, _, _ = asyncio.run(
        preprocessor.normalize(features_raw, tuple(feature_means), tuple(feature_stds))
    )
    print(f"[4/7] Normalized: shape={features_norm.shape}")
    print(f"       Z-score range: [{features_norm.min():.4f}, {features_norm.max():.4f}]")
    print(f"       Mean (should be ~0): {features_norm.mean():.6f}")
    print()

    # ── 5. Create windows ─────────────────────────────────────────────
    windows = asyncio.run(preprocessor.create_windows(features_norm, cfg.lookback))
    print(f"[5/7] Windows created: {windows.shape}")
    print(f"       Shape: {windows.shape[0]} windows x {windows.shape[1]} lookback "
          f"x {windows.shape[2]} features")

    last_window = windows[-1]
    print(f"       Last window: {last_window.shape}")
    print(f"       Window z-range: [{last_window.min():.4f}, {last_window.max():.4f}]")
    print()

    # ── 6. Load PyTorch model ─────────────────────────────────────────
    import torch
    from app.infrastructure.models.nova_quant_pytorch import (
        NovaQuantPyTorchModel,
        _infer_architecture,
    )

    state = torch.load(args.pt, map_location="cpu", weights_only=True)
    n_features, hidden_dim, num_layers = _infer_architecture(state)
    print(f"[6/7] PyTorch model loaded: LSTM({hidden_dim}) x{num_layers}")
    print(f"       Input features: {n_features}")
    print(f"       State dict keys: {list(state.keys())[:5]}...")

    model = NovaQuantPyTorchModel()
    model.load_checkpoint(args.pt, args.pkl, cfg)
    print(f"       Model loaded: {model.is_loaded()}")
    print()

    # ── 7. Predict ────────────────────────────────────────────────────
    print("[7/7] Running inference...")
    signal = asyncio.run(
        model.predict(last_window, confidence_threshold=args.threshold)
    )
    print()

    # ── Results ────────────────────────────────────────────────────────
    print("=" * 60)
    print("  RESULT")
    print("=" * 60)
    print(f"  Signal side:       {signal.side.value}")
    print(f"  Confidence:        {signal.confidence:.6f} ({signal.confidence*100:.2f}%)")
    print(f"  Actionable:        {signal.is_actionable()}")
    print(f"  Threshold:         {args.threshold}")
    print(f"  Model version:     {signal.model_version}")
    print(f"  Timestamp:         {signal.timestamp.isoformat()}")

    probs = signal.metadata.get("probabilities", {})
    print()
    print(f"  Probabilities:")
    print(f"    Trade:    {probs.get('trade', 'N/A')}")
    print(f"    No trade: {probs.get('no_trade', 'N/A')}")

    print()
    if signal.side.value == "BUY":
        print("  >>> BUY SIGNAL <<<")
    else:
        print("  >>> HOLD (no trade) <<<")
    print("=" * 60)

    # ── Feature diagnostics: which features contributed most? ─────────
    print()
    print("  Feature stats (last window, last step):")
    print(f"  {'Feature':<20} {'Mean':>12} {'Std':>12} {'Z-last':>12}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    last_step = last_window[-1]  # (19,)
    for i, name in enumerate(TaDataPreprocessor.FEATURE_NAMES):
        print(f"  {name:<20} {feature_means[i]:>12.4f} {feature_stds[i]:>12.4f} "
              f"{last_step[i]:>12.4f}")


if __name__ == "__main__":
    main()
