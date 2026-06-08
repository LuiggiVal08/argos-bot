"""MinLotProvider port.

Exchanges have minimum order size and step size constraints. Before
the use case returns a PositionSize to the executor, it must verify
the calculated units meet the minimum lot; otherwise the order
would be rejected by the exchange and the signal must be
discarded per spec.

Sad path: the provider can't reach the exchange (network error)
raises `MinLotProviderError`. The use case treats this as a soft
failure (use a conservative default) or a hard failure (abort),
depending on policy — the default is to abort.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class MinLotProviderError(RuntimeError):
    """Raised when market constraints cannot be fetched."""


@dataclass(frozen=True)
class MarketConstraints:
    """Per-market constraints needed to round a position to a
    tradable lot."""
    min_qty: float          # minimum order quantity
    qty_step: float         # step size (lot increment)
    min_notional: float     # minimum notional in quote currency


@runtime_checkable
class MinLotProvider(Protocol):
    """Returns the constraints for trading `symbol`."""

    async def get_constraints(self, symbol: str) -> MarketConstraints:
        """Returns market constraints. Raises MinLotProviderError
        on failure (network, exchange 5xx, etc.)."""
        ...
