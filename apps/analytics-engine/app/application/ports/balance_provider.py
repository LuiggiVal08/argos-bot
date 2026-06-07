"""BalanceProvider port.

The use case asks for the current free balance (margin available
for trading) in quote currency. The concrete adapter may use CCXT
in LIVE/PAPER, a mock in BACKTESTING, or any other source.

Sad path: any infrastructure error (network timeout, exchange 5xx,
auth failure, invalid 0 balance) raises `BalanceProviderError`,
which the use case converts into a critical abort per spec.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable


class BalanceProviderError(RuntimeError):
    """Raised when the balance cannot be retrieved (timeout, auth,
    5xx, network). The use case aborts the trade on this error."""


@runtime_checkable
class BalanceProvider(Protocol):
    """Returns the free margin available for trading, in quote
    currency (e.g. USDT for BTC/USDT)."""

    async def get_free_balance(self, quote: str = "USDT") -> Decimal:
        """Returns free balance. Raises BalanceProviderError on
        infrastructure failure or if the exchange returns an
        invalid (non-positive) value."""
        ...
