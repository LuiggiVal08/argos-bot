"""Tests for Confidence Filter (H29)."""
from __future__ import annotations

import pytest

from app.application.ports.confidence_filter import (
    ConfidenceResult,
    FilterDecision,
)
from app.infrastructure.analysis.confidence_filter import (
    SignalConfidenceFilter,
)


class TestFilterDecision:
    def test_execute_value(self):
        assert FilterDecision.EXECUTE.value == "EXECUTE"

    def test_hold_value(self):
        assert FilterDecision.HOLD.value == "HOLD"


class TestSignalConfidenceFilter:
    @pytest.fixture
    def filter(self):
        return SignalConfidenceFilter()

    async def test_all_conditions_met(self, filter):
        result = await filter.evaluate(
            probability=0.85,
            uncertainty=0.08,
            regime_ok=True,
            threshold=0.7,
            max_uncertainty=0.15,
        )
        assert result.decision == FilterDecision.EXECUTE
        assert result.probability_ok
        assert result.uncertainty_ok
        assert result.regime_ok

    async def test_low_probability(self, filter):
        result = await filter.evaluate(
            probability=0.55,
            uncertainty=0.08,
            regime_ok=True,
            threshold=0.7,
        )
        assert result.decision == FilterDecision.HOLD
        assert "probability_below_threshold" in result.reason
        assert not result.probability_ok

    async def test_high_uncertainty(self, filter):
        result = await filter.evaluate(
            probability=0.85,
            uncertainty=0.30,
            regime_ok=True,
            max_uncertainty=0.15,
        )
        assert result.decision == FilterDecision.HOLD
        assert "uncertainty_too_high" in result.reason
        assert not result.uncertainty_ok

    async def test_regime_not_actionable(self, filter):
        result = await filter.evaluate(
            probability=0.85,
            uncertainty=0.08,
            regime_ok=False,
        )
        assert result.decision == FilterDecision.HOLD
        assert "regime_not_actionable" in result.reason
        assert not result.regime_ok

    async def test_uncertainty_has_priority(self, filter):
        """Invariant #34: uncertainty has priority over probability."""
        result = await filter.evaluate(
            probability=0.95,
            uncertainty=0.30,  # exceeds max
            regime_ok=True,
            max_uncertainty=0.15,
        )
        assert result.decision == FilterDecision.HOLD
        # Should fail on uncertainty, not probability
        assert not result.uncertainty_ok
        assert result.probability_ok

    async def test_custom_thresholds(self, filter):
        result = await filter.evaluate(
            probability=0.65,
            uncertainty=0.10,
            regime_ok=True,
            threshold=0.6,
            max_uncertainty=0.20,
        )
        assert result.decision == FilterDecision.EXECUTE
