"""Confidence filter — final gate before execution.

Validates:
    1. Probability meets threshold
    2. Uncertainty is within limits
    3. Market regime is actionable
    4. (future) Adaptive threshold based on regime

If any condition fails → HOLD with explicit reason.
"""
from __future__ import annotations

import structlog

from ...application.ports.confidence_filter import (
    ConfidenceFilter,
    ConfidenceResult,
    FilterDecision,
)

log = structlog.get_logger()


class SignalConfidenceFilter:
    """Rule-based confidence filter for trading signals.

    Applies the invariant: uncertainty has priority over probability.
    """

    async def evaluate(
        self,
        probability: float,
        uncertainty: float,
        regime_ok: bool,
        threshold: float = 0.7,
        max_uncertainty: float = 0.15,
    ) -> ConfidenceResult:
        # Check regime first (cheapest)
        if not regime_ok:
            return ConfidenceResult(
                decision=FilterDecision.HOLD,
                reason="regime_not_actionable",
                probability=probability,
                uncertainty=uncertainty,
                regime_ok=False,
                probability_ok=probability >= threshold,
                uncertainty_ok=uncertainty <= max_uncertainty,
            )

        # Check uncertainty (has priority per invariant #34)
        uncertainty_ok = uncertainty <= max_uncertainty
        if not uncertainty_ok:
            return ConfidenceResult(
                decision=FilterDecision.HOLD,
                reason=f"uncertainty_too_high: {uncertainty:.4f} > {max_uncertainty}",
                probability=probability,
                uncertainty=uncertainty,
                regime_ok=True,
                probability_ok=probability >= threshold,
                uncertainty_ok=False,
            )

        # Check probability
        probability_ok = probability >= threshold
        if not probability_ok:
            return ConfidenceResult(
                decision=FilterDecision.HOLD,
                reason=f"probability_below_threshold: {probability:.4f} < {threshold}",
                probability=probability,
                uncertainty=uncertainty,
                regime_ok=True,
                probability_ok=False,
                uncertainty_ok=True,
            )

        # All conditions met
        return ConfidenceResult(
            decision=FilterDecision.EXECUTE,
            reason="all_conditions_met",
            probability=probability,
            uncertainty=uncertainty,
            regime_ok=True,
            probability_ok=True,
            uncertainty_ok=True,
        )
