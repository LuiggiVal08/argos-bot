"""TripAction VO: the ordered sequence of steps to take on TRIP.

Per spec section 5 Historia 3 (sad path):
  1. Cancel all open orders (CCXT cancel_all).
  2. Close any active position at market price.
  3. Rewrite ENVIRONMENT_MODE = PASIVO.
  4. Halt the trading loop and log the block.

The order matters: cancel orders FIRST so the close-market
order doesn't immediately get re-queued, then close position,
then flip the env flag so the executor stops dispatching new
orders, then halt. The TripCircuitBreakerUseCase iterates over
the steps in order and dispatches each to the matching port.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TripStep(str, Enum):
    CANCEL_ORDERS = "CANCEL_ORDERS"
    CLOSE_POSITIONS = "CLOSE_POSITIONS"
    SET_PASIVO = "SET_PASIVO"
    HALT = "HALT"


@dataclass(frozen=True)
class TripAction:
    """An ordered list of steps. The order is the action order."""
    steps: tuple[TripStep, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("TripAction must have at least one step")
        # Always pin the canonical order: the use case MAY add/remove
        # observability steps, but the four core steps must be in
        # this order.
        canonical = (
            TripStep.CANCEL_ORDERS,
            TripStep.CLOSE_POSITIONS,
            TripStep.SET_PASIVO,
            TripStep.HALT,
        )
        for step in canonical:
            if step in self.steps and self.steps.index(step) != canonical.index(
                step
            ):
                raise ValueError(
                    f"step {step} must appear at position "
                    f"{canonical.index(step)} in TripAction"
                )

    @classmethod
    def canonical(cls) -> "TripAction":
        return cls(
            steps=(
                TripStep.CANCEL_ORDERS,
                TripStep.CLOSE_POSITIONS,
                TripStep.SET_PASIVO,
                TripStep.HALT,
            )
        )
