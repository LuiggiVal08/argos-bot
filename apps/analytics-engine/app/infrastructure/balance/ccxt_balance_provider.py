"""CcxtBalanceProvider: implements BalanceProvider via ccxt.async_support.

Wraps a single exchange instance and queries `fetch_balance` on
each call. The exchange is provided by the composition root (in
main.py) and shared across requests.

Sad path: ccxt raises `BaseError` subclasses (network, auth,
exchange error). We surface them as `BalanceProviderError` so the
use case can abort with a clean message.
"""
from __future__ import annotations

from decimal import Decimal

import ccxt.async_support as ccxt

from ...application.ports.balance_provider import (
    BalanceProvider,
    BalanceProviderError,
)


class CcxtBalanceProvider(BalanceProvider):
    def __init__(self, exchange: ccxt.Exchange) -> None:
        self._exchange = exchange

    async def get_free_balance(self, quote: str = "USDT") -> Decimal:
        try:
            data = await self._exchange.fetch_balance()
        except Exception as e:
            raise BalanceProviderError(f"ccxt_fetch_balance_failed: {e}") from e

        free = data.get("free", {}) or {}
        raw = free.get(quote)
        if raw is None:
            # Some exchanges return the total in a "total" key; fall
            # back to that if "free" is missing for the quote.
            total = data.get("total", {}) or {}
            raw = total.get(quote)
        if raw is None:
            raise BalanceProviderError(
                f"balance_missing_quote: {quote} not in exchange balance"
            )
        try:
            value = Decimal(str(raw))
        except Exception as e:
            raise BalanceProviderError(f"balance_unparseable: {raw}") from e
        if value <= 0:
            raise BalanceProviderError(
                f"balance_invalid: free {quote} = {value} (must be > 0)"
            )
        return value
