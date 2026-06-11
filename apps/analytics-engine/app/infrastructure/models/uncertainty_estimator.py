"""Monte Carlo Dropout uncertainty estimator for Keras LSTM.

Runs N forward passes with Dropout enabled at inference time
and computes mean, std, and predictive entropy.

Works with any Keras model that has Dropout layers.
Requires TensorFlow.
"""
from __future__ import annotations

import numpy as np
import structlog

from ...application.ports.uncertainty_estimator import (
    UncertaintyEstimationError,
    UncertaintyEstimator,
    UncertaintyResult,
)

log = structlog.get_logger()

try:
    import tensorflow as tf

    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False


class MCDropoutUncertaintyEstimator:
    """Monte Carlo Dropout uncertainty estimator.

    Wraps a Keras model and enables dropout at inference time
    by calling the model in training mode (training=True).

    Usage:
        estimator = MCDropoutUncertaintyEstimator(keras_model)
        result = await estimator.estimate(window, n_samples=30)
    """

    def __init__(self, model: tf.keras.Model) -> None:
        if not _TF_AVAILABLE:
            raise RuntimeError("TensorFlow is required for MCDropoutUncertaintyEstimator")

        self._model = model

    async def estimate(
        self,
        window: np.ndarray,
        n_samples: int = 30,
    ) -> UncertaintyResult:
        try:
            batch = np.expand_dims(window, axis=0)  # (1, lookback, n_features)

            # Run N stochastic forward passes (training=True enables dropout)
            predictions = []
            for _ in range(n_samples):
                probs = self._model(batch, training=True)[0].numpy()
                predictions.append(probs)

            predictions = np.array(predictions)  # (n_samples, 3)

            mean_probs = np.mean(predictions, axis=0)
            std_probs = np.std(predictions, axis=0)

            # Predictive entropy: -sum(p * log(p))
            entropy = float(
                -np.sum(mean_probs * np.log(mean_probs + 1e-8))
            )

            return UncertaintyResult(
                mean_probs=mean_probs,
                std_probs=std_probs,
                entropy=entropy,
                n_samples=n_samples,
            )

        except Exception as e:
            raise UncertaintyEstimationError(
                f"mc_dropout_failed: {e}"
            ) from e
