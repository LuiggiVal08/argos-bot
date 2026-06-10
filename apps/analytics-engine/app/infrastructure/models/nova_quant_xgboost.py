"""XGBoost model for NovaQuant.

Implements ModelPredictor and ModelTrainer using XGBoost for
tabular classification (BUY/SELL/HOLD).

Architecture:
  Input: (lookback * n_features,) flattened window
    -> XGBoost (multi:softprob, max_depth=6, n_estimators=200)
    -> 3-class output [BUY, SELL, HOLD]

Uses early stopping with eval_metric=mlogloss, patience=10.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from ...application.ports.model_predictor import (
    ModelPredictor,
    PredictionError,
)
from ...application.ports.model_trainer import (
    ModelTrainer,
    TrainingError,
)
from ...domain.value_objects.model_config import ModelConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.value_objects.trading_signal import TradingSignal

try:
    import xgboost as xgb

    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False


class NovaQuantXGBoostModel(ModelTrainer, ModelPredictor):
    """XGBoost classifier for NovaQuant trading signals.

    Flattens the (lookback, n_features) window into a 1D vector
    and trains a gradient boosted tree ensemble.

    Usage:
        model = NovaQuantXGBoostModel()
        metrics = await model.train(config, x_train, y_train, x_val, y_val)
        signal = await model.predict(window)
    """

    def __init__(self) -> None:
        if not _XGB_AVAILABLE:
            raise RuntimeError(
                "XGBoost is required for NovaQuantXGBoostModel. "
                "Install it via: pip install xgboost>=2.0"
            )

        self._model: xgb.Booster | None = None
        self._config: ModelConfig | None = None

    async def train(
        self,
        config: ModelConfig,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict[str, Any]:
        """Entrena XGBoost con early stopping.

        Args:
            config: config del modelo (features, etc.).
            x_train: (n_train, lookback, n_features).
            y_train: (n_train, 3) one-hot.
            x_val: (n_val, lookback, n_features).
            y_val: (n_val, 3) one-hot.

        Returns:
            dict con metrics: val_logloss, val_accuracy, best_iteration.
        """
        try:
            self._config = config

            # Flatten windows: (n, lookback, n_features) -> (n, lookback * n_features)
            x_train_flat = x_train.reshape(x_train.shape[0], -1)
            x_val_flat = x_val.reshape(x_val.shape[0], -1)

            # Convert one-hot to class labels
            y_train_labels = np.argmax(y_train, axis=1)
            y_val_labels = np.argmax(y_val, axis=1)

            dtrain = xgb.DMatrix(x_train_flat, label=y_train_labels)
            dval = xgb.DMatrix(x_val_flat, label=y_val_labels)

            params = {
                "objective": "multi:softprob",
                "num_class": 3,
                "max_depth": 6,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "eval_metric": "mlogloss",
                "seed": 42,
            }

            evals = [(dtrain, "train"), (dval, "eval")]
            model = xgb.train(
                params,
                dtrain,
                num_boost_round=200,
                evals=evals,
                early_stopping_rounds=10,
                verbose_eval=False,
            )

            self._model = model

            # Evaluation
            train_preds = model.predict(dtrain)
            val_preds = model.predict(dval)
            train_accuracy = float(np.mean(np.argmax(train_preds, axis=1) == y_train_labels))
            val_accuracy = float(np.mean(np.argmax(val_preds, axis=1) == y_val_labels))

            best_iter = model.best_iteration if model.best_iteration is not None else 0

            return {
                "val_logloss": float(model.best_score) if hasattr(model, "best_score") and model.best_score else 0.0,
                "val_accuracy": val_accuracy,
                "train_accuracy": train_accuracy,
                "best_iteration": best_iter,
                "n_features_flat": x_train_flat.shape[1],
            }

        except Exception as e:
            raise TrainingError(f"xgboost_training_failed: {e}") from e

    async def predict(
        self,
        window: np.ndarray,
        confidence_threshold: float = 0.7,
    ) -> TradingSignal:
        if self._model is None:
            raise PredictionError("no_model_loaded: call train() or load_model() first")

        try:
            flat = window.reshape(1, -1)
            dmatrix = xgb.DMatrix(flat)
            probs = self._model.predict(dmatrix)[0]

            class_idx = int(np.argmax(probs))
            confidence = float(probs[class_idx])

            side = [SignalSide.BUY, SignalSide.SELL, SignalSide.HOLD][class_idx]

            return TradingSignal(
                side=side,
                confidence=confidence,
                timestamp=datetime.now(timezone.utc),
                model_version="xgboost_v1",
                metadata={
                    "probabilities": {
                        "buy": float(probs[0]),
                        "sell": float(probs[1]),
                        "hold": float(probs[2]),
                    }
                },
            )

        except Exception as e:
            raise PredictionError(f"xgboost_prediction_failed: {e}") from e

    def get_model(self) -> xgb.Booster | None:
        return self._model

    def load_model(self, model_bytes: bytes, config: ModelConfig) -> None:
        self._config = config
        self._model = xgb.Booster(model_file=None)
        self._model.load_model(bytearray(model_bytes))

    def is_loaded(self) -> bool:
        return self._model is not None
