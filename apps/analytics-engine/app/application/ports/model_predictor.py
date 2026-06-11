"""ModelPredictor port.

Ejecuta inferencia con el modelo entrenado. El adapter concreto
carga el checkpoint de Keras y hace el forward pass.

Sad paths:
  - PredictionError: modelo no cargado, forward pass falla
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ...domain.value_objects.trading_signal import TradingSignal


class PredictionError(RuntimeError):
    """Raised when inference fails."""


@runtime_checkable
class ModelPredictor(Protocol):
    """Predice la senal de trading para una ventana de features."""

    async def predict(
        self,
        window: np.ndarray,
        confidence_threshold: float = 0.7,
    ) -> TradingSignal:
        """Forward pass: window -> TradingSignal.

        Args:
            window: (lookback, n_features) normalizada.
            confidence_threshold: minimo para considerar accionable.

        Returns:
            TradingSignal con side, confidence, timestamp.

        Raises PredictionError si falla.
        """
        ...
