"""Confidence filter port.

Applies the final gate before a signal can be executed:

    probability >= threshold
    AND uncertainty <= max_uncertainty
    AND regime is actionable
    AND (optional) market context is valid

Returns a decision: EXECUTE or HOLD with reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class FilterDecision(Enum):
    EXECUTE = "EXECUTE"
    HOLD = "HOLD"


@dataclass(frozen=True)
class ConfidenceResult:
    decision: FilterDecision
    reason: str
    probability: float
    uncertainty: float
    regime_ok: bool
    probability_ok: bool
    uncertainty_ok: bool


@runtime_checkable
class ConfidenceFilter(Protocol):
    """Validates signal confidence before execution."""

    async def evaluate(
        self,
        probability: float,
        uncertainty: float,
        regime_ok: bool,
        threshold: float = 0.7,
        max_uncertainty: float = 0.15,
    ) -> ConfidenceResult:
        """Evaluate whether a signal meets confidence criteria.

        Args:
            probability: model confidence (0-1).
            uncertainty: max_std from uncertainty estimator.
            regime_ok: whether market regime is actionable.
            threshold: minimum probability threshold.
            max_uncertainty: maximum allowed uncertainty.

        Returns:
            ConfidenceResult with decision and diagnostics.
        """
        ...
