"""Probability calibrator port.

Calibrates model probabilities to be statistically consistent.
If calibration is unavailable, returns raw probabilities.

Methods:
    Platt Scaling: logistic regression on model outputs.
    Isotonic Regression: non-parametric calibration.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


class CalibrationError(RuntimeError):
    """Raised when probability calibration fails."""


@runtime_checkable
class ProbabilityCalibrator(Protocol):
    """Calibrates classification probabilities for reliability."""

    async def calibrate(
        self,
        probabilities: np.ndarray,
    ) -> np.ndarray:
        """Calibrate probability vector.

        Args:
            probabilities: (n_classes,) raw model probabilities.

        Returns:
            (n_classes,) calibrated probabilities summing to 1.0.

        Raises CalibrationError if calibration fails.
        """
        ...

    async def fit(
        self,
        probabilities: np.ndarray,
        targets: np.ndarray,
    ) -> None:
        """Fit calibrator on held-out validation data.

        Args:
            probabilities: (n_samples, n_classes) raw probabilities.
            targets: (n_samples,) integer class labels.

        Raises CalibrationError if fitting fails.
        """
        ...
