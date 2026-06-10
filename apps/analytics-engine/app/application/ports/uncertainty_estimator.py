"""Uncertainty estimator using Monte Carlo Dropout.

Runs N stochastic forward passes with Dropout enabled at inference
time and computes prediction statistics (mean, std, entropy).

Methods:
    MC Dropout: activates Dropout during inference for the Keras LSTM.
    Deep Ensembles: averages predictions from N bootstrapped models.

Reference:
    Gal & Ghahramani (2016) - Dropout as a Bayesian Approximation.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


class UncertaintyEstimationError(RuntimeError):
    """Raised when uncertainty estimation fails."""


@runtime_checkable
class UncertaintyEstimator(Protocol):
    """Estimates prediction uncertainty via stochastic forward passes."""

    async def estimate(
        self,
        window: np.ndarray,
        n_samples: int = 30,
    ) -> "UncertaintyResult":
        """Run stochastic inference and return uncertainty metrics.

        Args:
            window: (lookback, n_features) input.
            n_samples: number of stochastic forward passes.

        Returns:
            UncertaintyResult with mean_probs, std_probs, entropy.

        Raises UncertaintyEstimationError if estimation fails.
        """
        ...


from dataclasses import dataclass


@dataclass(frozen=True)
class UncertaintyResult:
    mean_probs: np.ndarray
    std_probs: np.ndarray
    entropy: float
    n_samples: int

    @property
    def max_std(self) -> float:
        return float(np.max(self.std_probs))

    @property
    def is_reliable(self, max_uncertainty: float = 0.15) -> bool:
        return self.max_std <= max_uncertainty
