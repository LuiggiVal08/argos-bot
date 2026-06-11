"""Tests for Uncertainty Estimator (H28) port."""
from __future__ import annotations

import numpy as np

from app.application.ports.uncertainty_estimator import (
    UncertaintyResult,
)


class TestUncertaintyResult:
    def test_create(self):
        result = UncertaintyResult(
            mean_probs=np.array([0.8, 0.1, 0.1]),
            std_probs=np.array([0.05, 0.02, 0.02]),
            entropy=0.5,
            n_samples=30,
        )
        assert result.n_samples == 30
        assert result.max_std == 0.05

    def test_is_reliable(self):
        result = UncertaintyResult(
            mean_probs=np.array([0.8, 0.1, 0.1]),
            std_probs=np.array([0.05, 0.02, 0.02]),
            entropy=0.5,
            n_samples=30,
        )
        assert result.is_reliable

    def test_is_not_reliable(self):
        result = UncertaintyResult(
            mean_probs=np.array([0.5, 0.3, 0.2]),
            std_probs=np.array([0.25, 0.15, 0.10]),
            entropy=1.0,
            n_samples=30,
        )
        assert not result.is_reliable
