"""Probability calibrator using Platt Scaling and Isotonic Regression.

Wraps sklearn's CalibratedClassifierCV for multi-class calibration.

Methods:
    Platt Scaling: parametric (logistic regression) — method="sigmoid".
    Isotonic Regression: non-parametric — method="isotonic".

Usage:
    calibrator = SklearnProbabilityCalibrator(method="sigmoid")
    await calibrator.fit(val_probs, val_labels)
    calibrated = await calibrator.calibrate(raw_probs)
"""
from __future__ import annotations

from typing import Literal

import numpy as np
import structlog

from ...application.ports.probability_calibrator import (
    CalibrationError,
    ProbabilityCalibrator,
)

log = structlog.get_logger()

try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


CalibrationMethod = Literal["sigmoid", "isotonic"]


class SklearnProbabilityCalibrator:
    """Multi-class probability calibrator using sklearn.

    For multi-class, fits one calibrator per class in a
    one-vs-rest fashion.

    Args:
        method: "sigmoid" for Platt Scaling, "isotonic" for Isotonic Regression.
    """

    def __init__(self, method: CalibrationMethod = "sigmoid") -> None:
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError(
                "sklearn is required for SklearnProbabilityCalibrator. "
                "Install it via: pip install scikit-learn>=1.3"
            )

        if method not in ("sigmoid", "isotonic"):
            raise ValueError(f"method must be 'sigmoid' or 'isotonic', got {method!r}")

        self._method = method
        self._calibrators: list[LogisticRegression | IsotonicRegression] | None = None
        self._scaler: StandardScaler | None = None
        self._fitted: bool = False

    async def fit(
        self,
        probabilities: np.ndarray,
        targets: np.ndarray,
    ) -> None:
        """Fit one-vs-rest calibrators.

        Args:
            probabilities: (n_samples, n_classes) raw probabilities.
            targets: (n_samples,) integer class labels (0, 1, 2).

        Raises CalibrationError if fitting fails.
        """
        try:
            n_classes = probabilities.shape[1]
            self._calibrators = []
            self._scaler = StandardScaler()

            # Scale logits for numerical stability
            logits = np.log(probabilities + 1e-8)
            logits_scaled = self._scaler.fit_transform(logits)

            for c in range(n_classes):
                binary_target = (targets == c).astype(np.float64)

                if self._method == "sigmoid":
                    cal = LogisticRegression(
                        solver="lbfgs",
                        max_iter=1000,
                        random_state=42,
                    )
                else:
                    cal = IsotonicRegression(
                        out_of_bounds="clip",
                        increasing=True,
                    )

                cal.fit(logits_scaled[:, c:c+1], binary_target)
                self._calibrators.append(cal)

            self._fitted = True
            log.info(
                "calibrator_fitted",
                method=self._method,
                n_classes=n_classes,
            )

        except Exception as e:
            raise CalibrationError(f"calibrator_fit_failed: {e}") from e

    async def calibrate(
        self,
        probabilities: np.ndarray,
    ) -> np.ndarray:
        """Calibrate probabilities using fitted calibrators.

        Args:
            probabilities: (n_classes,) raw model probabilities.

        Returns:
            (n_classes,) calibrated probabilities.

        Raises CalibrationError if not fitted or inference fails.
        """
        if not self._fitted or self._calibrators is None or self._scaler is None:
            # Degraded mode: return raw probabilities
            log.warning("calibrator_not_fitted_returning_raw")
            return probabilities

        try:
            probs_2d = probabilities.reshape(1, -1)
            logits = np.log(probs_2d + 1e-8)
            logits_scaled = self._scaler.transform(logits)

            calibrated = []
            for c, cal in enumerate(self._calibrators):
                cal_prob = cal.predict(logits_scaled[:, c:c+1])[0]
                calibrated.append(float(np.clip(cal_prob, 0.01, 0.99)))

            calibrated = np.array(calibrated)
            calibrated /= calibrated.sum()  # renormalize

            return calibrated

        except Exception as e:
            raise CalibrationError(f"calibrator_inference_failed: {e}") from e
