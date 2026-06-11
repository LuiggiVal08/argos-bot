"""XGBoost-based MetaModel stacking ensemble.

Takes LSTM probabilities + XGBoost probabilities + market context
features as input and trains a lightweight XGBoost classifier as
the final stacking layer.

Architecture:
    Input: [lstm_buy, lstm_sell, lstm_hold,
            xgb_buy, xgb_sell, xgb_hold,
            adx, bbw, atr, rsi, volume]
    -> XGBoost (multi:softprob, max_depth=3, n_estimators=50)
    -> [BUY, SELL, HOLD]
"""
from __future__ import annotations

from typing import Any

import numpy as np
import structlog

from ...application.ports.meta_model import (
    MetaModel,
    MetaModelError,
    MetaModelInput,
    MetaModelTrainError,
)

log = structlog.get_logger()

try:
    import xgboost as xgb

    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False


class XGBoostMetaModel:
    """Lightweight XGBoost stacking ensemble.

    Uses shallow trees (max_depth=3, n_estimators=50) to avoid
    overfitting on the small meta-feature space.
    """

    def __init__(self) -> None:
        if not _XGB_AVAILABLE:
            raise RuntimeError("XGBoost is required for XGBoostMetaModel")

        self._model: xgb.Booster | None = None
        self._fitted: bool = False

    async def predict(
        self,
        input_data: MetaModelInput,
    ) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise MetaModelError("meta_model_not_trained")

        try:
            vector = input_data.to_vector().reshape(1, -1)
            dmatrix = xgb.DMatrix(vector)
            probs = self._model.predict(dmatrix)[0]
            return probs

        except Exception as e:
            raise MetaModelError(f"meta_model_prediction_failed: {e}") from e

    async def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> dict[str, float]:
        try:
            y_labels = np.argmax(y, axis=1)

            dtrain = xgb.DMatrix(x, label=y_labels)

            params = {
                "objective": "multi:softprob",
                "num_class": 3,
                "max_depth": 3,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "eval_metric": "mlogloss",
                "seed": 42,
            }

            model = xgb.train(
                params,
                dtrain,
                num_boost_round=50,
                verbose_eval=False,
            )

            self._model = model
            self._fitted = True

            train_preds = model.predict(dtrain)
            train_accuracy = float(np.mean(np.argmax(train_preds, axis=1) == y_labels))

            return {
                "train_accuracy": train_accuracy,
                "n_features": x.shape[1],
                "n_samples": x.shape[0],
            }

        except Exception as e:
            raise MetaModelTrainError(f"meta_model_training_failed: {e}") from e

    def is_loaded(self) -> bool:
        return self._fitted
