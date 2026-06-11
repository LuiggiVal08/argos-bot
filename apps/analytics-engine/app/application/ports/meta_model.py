"""MetaModel port — stacking ensemble for final signal.

Combines LSTM probabilities, XGBoost probabilities, and market
context features (ADX, BBW, ATR, RSI, Volume) into a single
final prediction.

Operates as a lightweight classifier on top of base models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


class MetaModelError(RuntimeError):
    """Raised when MetaModel prediction fails."""


class MetaModelTrainError(RuntimeError):
    """Raised when MetaModel training fails."""


@dataclass(frozen=True)
class MetaModelInput:
    lstm_probs: np.ndarray
    xgb_probs: np.ndarray
    context: dict[str, float]

    def to_vector(self) -> np.ndarray:
        return np.concatenate([
            self.lstm_probs,
            self.xgb_probs,
            np.array([
                self.context.get("adx", 0.0),
                self.context.get("bbw", 0.0),
                self.context.get("atr", 0.0),
                self.context.get("rsi", 0.0),
                self.context.get("volume", 0.0),
            ]),
        ])

    @property
    def n_features(self) -> int:
        return len(self.lstm_probs) + len(self.xgb_probs) + 5


@runtime_checkable
class MetaModel(Protocol):
    """Stacking ensemble that combines base model outputs."""

    async def predict(
        self,
        input_data: MetaModelInput,
    ) -> np.ndarray:
        """Predict final probabilities.

        Args:
            input_data: combined LSTM + XGBoost + context features.

        Returns:
            (3,) array with calibrated probabilities [BUY, SELL, HOLD].

        Raises MetaModelError if prediction fails.
        """
        ...

    async def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> dict[str, float]:
        """Train the MetaModel on stacked features.

        Args:
            x: (n_samples, n_features) stacked feature matrix.
            y: (n_samples, 3) one-hot target labels.

        Returns:
            dict with training metrics.

        Raises MetaModelTrainError if training fails.
        """
        ...
