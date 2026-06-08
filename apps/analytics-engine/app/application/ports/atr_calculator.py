"""AtrCalculator port.

The use case asks for the current ATR (Average True Range) of a
symbol over a lookback window. The concrete adapter typically
reads OHLCV from the exchange or a local cache and computes ATR
using the `ta` library.

Sad path: insufficient candles (< window), or compute failure,
raises `AtrCalculatorError`. The use case aborts the trade on
this error.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.atr import Atr


class AtrCalculatorError(RuntimeError):
    """Raised when ATR cannot be calculated (insufficient data,
    network error reading candles, etc.)."""


@runtime_checkable
class AtrCalculator(Protocol):
    """Returns the current ATR for `symbol` over the given window."""

    async def get_atr(
        self, symbol: str, timeframe: str = "1m", window: int = 14
    ) -> Atr:
        """Returns ATR. Raises AtrCalculatorError on failure or
        when the resulting value is non-positive (treated as
        a degenerate market state)."""
        ...
