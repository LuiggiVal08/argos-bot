#!/usr/bin/env python3
"""Import a PyTorch model (.pt + .pkl) into the ARGOS checkpoint repository.

This is the bridge between Colab training and the production inference pipeline.

Usage:
    # Place best_argos_lstm.pt and scaler_argos.pkl in ../models/
    python import_pytorch_model.py --version 1.0.0

    # Or specify custom paths:
    python import_pytorch_model.py \\
        --pt /path/to/best_argos_lstm.pt \\
        --pkl /path/to/scaler_argos.pkl \\
        --version 1.0.0

The script:
  1. Loads the PyTorch state_dict and sklearn scaler
  2. Infers n_features, hidden_dim, num_layers from the state_dict
  3. Builds a ModelConfig matching the 19-feature dataset
  4. Creates a NovaQuantModel domain entity
  5. Saves everything to FsCheckpointRepository (~/.novaquant/checkpoints/)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the analytics-engine package is importable
_HERE = Path(__file__).resolve().parent
_APP = _HERE.parent / "app"
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from app.domain.value_objects.model_config import ModelConfig
from app.domain.entities.nova_quant_model import NovaQuantModel
from app.infrastructure.models.checkpoint_repo_fs import FsCheckpointRepository
from app.infrastructure.models.nova_quant_pytorch import (
    NovaQuantPyTorchModel,
    _infer_architecture,
)


# 19 features en orden estricto del tensor (coincide con TaDataPreprocessor)
FEATURES_19: tuple[str, ...] = (
    "open", "high", "low", "close", "volume",
    "rsi", "ema_fast", "ema_medium", "ema_slow",
    "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_middle", "bb_lower",
    "atr", "obv", "volume_sma", "pct_change",
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import PyTorch model + scaler into ARGOS checkpoint repo",
    )
    parser.add_argument(
        "--pt",
        default=str(_HERE.parent / "models" / "best_argos_lstm.pt"),
        help="Path to best_argos_lstm.pt (default: ../models/best_argos_lstm.pt)",
    )
    parser.add_argument(
        "--pkl",
        default=str(_HERE.parent / "models" / "scaler_argos.pkl"),
        help="Path to scaler_argos.pkl (default: ../models/scaler_argos.pkl)",
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Semantic model version (default: 1.0.0)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.55,
        help="Confidence threshold for actionable signals (default: 0.55)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=60,
        help="Lookback window in candles (default: 60)",
    )
    args = parser.parse_args()

    pt_path = Path(args.pt)
    pkl_path = Path(args.pkl)

    for f in [pt_path, pkl_path]:
        if not f.exists():
            print(f"❌ File not found: {f}")
            sys.exit(1)

    print(f"📦 Loading PyTorch model from: {pt_path}")
    print(f"📦 Loading scaler from:        {pkl_path}")

    # Infer architecture from state_dict
    import torch
    state = torch.load(pt_path, map_location="cpu", weights_only=True)
    n_features, hidden_dim, num_layers = _infer_architecture(state)
    print(f"🔧 Architecture: n_features={n_features}, hidden_dim={hidden_dim}, num_layers={num_layers}")

    if n_features != 19:
        print(f"⚠️  Warning: state_dict has {n_features} features, expected 19")
        print(f"   Update FEATURES_19 tuple if your model uses a different feature set.")

    # Build config
    config = ModelConfig(
        lookback=args.lookback,
        confidence_threshold=args.confidence_threshold,
        layers=(hidden_dim, 1),
        features=FEATURES_19,
    )
    print(f"✅ ModelConfig: lookback={config.lookback}, threshold={config.confidence_threshold}")

    # Load model to get scaler stats
    pt_model = NovaQuantPyTorchModel()
    pt_model.load_checkpoint(pt_path, pkl_path, config)

    # Serialize weights
    weights_bytes = pt_model.get_weights_bytes()
    weights_hash = hashlib.sha256(weights_bytes).hexdigest()
    print(f"🔑 Weights hash: {weights_hash[:16]}...")

    # Load scaler params from pkl
    import pickle
    with open(pkl_path, "rb") as f:
        scaler = pickle.load(f)

    feature_means = tuple(float(v) for v in scaler.mean_)
    feature_stds = tuple(float(v) for v in (scaler.scale_ if hasattr(scaler, "scale_") else scaler.var_ ** 0.5))

    if len(feature_means) != n_features:
        print(f"❌ Scaler feature count ({len(feature_means)}) != model features ({n_features})")
        sys.exit(1)

    # Build domain entity
    domain_model = NovaQuantModel(
        config=config,
        model_version=args.version,
        trained_at=datetime.now(timezone.utc),
        weights_hash=weights_hash,
        feature_means=feature_means,
        feature_stds=feature_stds,
        metrics={
            "accuracy": 0.6038,
            "confidence_threshold": args.confidence_threshold,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "architecture": "LSTM",
            "framework": "pytorch",
        },
    )

    # Save to checkpoint repo (includes scaler alongside weights)
    repo = FsCheckpointRepository()
    path = await repo.save(domain_model, weights_bytes)

    # Also save scaler alongside the checkpoint
    scaler_path_v = Path(path) / "scaler.pkl"
    scaler_path_v.write_bytes(pt_model.get_scaler_bytes())

    print(f"\n✅ Model imported successfully!")
    print(f"   Version:  {args.version}")
    print(f"   Location: {path}")
    print(f"   Features: {n_features}")
    print(f"   Layers:   LSTM({hidden_dim}) x{num_layers} -> Dense(1)")
    print(f"   Ready for inference via PredictSignalUseCase")
    print(f"\n   To switch the engine to PyTorch, set:")
    print(f"   USE_PYTORCH=true")


if __name__ == "__main__":
    asyncio.run(main())
