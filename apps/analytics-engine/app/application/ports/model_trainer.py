"""ModelTrainer port.

Entrena una red LSTM con datos preprocesados y guarda el checkpoint.
El adapter concreto usa Keras/TensorFlow.

Sad paths:
  - TrainingError: fallo en el entrenamiento (convergencia, OOM, etc.)
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ...domain.value_objects.model_config import ModelConfig


class TrainingError(RuntimeError):
    """Raised when training fails."""


@runtime_checkable
class ModelTrainer(Protocol):
    """Entrena el modelo LSTM y retorna metricas + checkpoint."""

    async def train(
        self,
        config: ModelConfig,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict:
        """Entrena el modelo con early stopping.

        Args:
            config: configuracion del modelo.
            x_train: (n, lookback, n_features).
            y_train: (n, 3) one-hot.
            x_val: (n, lookback, n_features).
            y_val: (n, 3) one-hot.

        Returns:
            dict con metricas de entrenamiento:
              val_loss, val_accuracy, epochs_trained, best_epoch

        Raises TrainingError si falla.
        """
        ...
