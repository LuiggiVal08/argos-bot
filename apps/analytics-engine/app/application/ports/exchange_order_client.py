"""ExchangeOrderClient port.

The trip use case calls this to:
  - cancel_all_orders(): bulk-cancel every open order on the
    exchange for the configured symbols.
  - close_all_positions(): flatten every active position with a
    market order.

Sad path: any I/O failure (CCXT timeout, exchange 5xx, auth)
raises ExchangeOrderClientError. The use case treats this as
a critical abort — partial cancellation is logged and the
halt step is still attempted.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


class ExchangeOrderClientError(RuntimeError):
    """Raised when cancel_all or close_all can't complete."""


@dataclass(frozen=True)
class PositionSummary:
    symbol: str
    side: str           # "long" or "short"
    quantity: Decimal
    entry_price: Decimal


@runtime_checkable
class ExchangeOrderClient(Protocol):
    async def cancel_all_orders(self) -> int:
        """Cancel every open order on the configured exchange.
        Returns the number of orders cancelled. Raises
        ExchangeOrderClientError on infrastructure failure."""
        ...

    async def close_all_positions(self) -> list[PositionSummary]:
        """Flatten every active position with a market order.
        Returns the list of positions that were closed. Raises
        ExchangeOrderClientError on infrastructure failure."""
        ...
