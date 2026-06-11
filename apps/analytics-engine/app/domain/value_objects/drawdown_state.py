"""DrawdownState enum: SAFE / WARN / TRIP / HALTED.

SAFE: drawdown below 60% of the trip threshold.
WARN: drawdown between 60% of the trip threshold and the trip threshold.
TRIP: drawdown has crossed the trip threshold; trip action must run.
HALTED: trip action has already executed; the trading loop is
        suspended until manual reset.

The HALTED state is distinct from TRIP so the use case can answer
"Did we already trip?" without re-deriving from logs.
"""
from __future__ import annotations

from enum import Enum


class DrawdownState(str, Enum):
    SAFE = "SAFE"
    WARN = "WARN"
    TRIP = "TRIP"
    HALTED = "HALTED"
