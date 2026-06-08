"""CcxtMinLotProvider: implements MinLotProvider via ccxt.

Reads the market info from the exchange and returns the
minQty / stepSize / minNotional (with sensible fallbacks for
exchanges that don't provide all three).

Sad path: ccxt raises on missing market or network error →
`MinLotProviderError`.
"""
from __future__ import annotations

import ccxt.async_support as ccxt

from ...application.ports.min_lot_provider import (
    MarketConstraints,
    MinLotProvider,
    MinLotProviderError,
)


class CcxtMinLotProvider(MinLotProvider):
    # Sensible defaults when the exchange doesn't disclose the field.
    # min_qty of 0 means "no disclosed minimum"; we still flag the
    # trade as below min only when min_qty > 0 and units < min_qty.
    DEFAULT_MIN_QTY = 0.0
    DEFAULT_QTY_STEP = 1e-8
    DEFAULT_MIN_NOTIONAL = 0.0

    def __init__(self, exchange: ccxt.Exchange) -> None:
        self._exchange = exchange

    async def get_constraints(self, symbol: str) -> MarketConstraints:
        try:
            market = self._exchange.market(symbol)
        except Exception as e:
            raise MinLotProviderError(
                f"ccxt_market_lookup_failed: {symbol}: {e}"
            ) from e

        limits = (market or {}).get("limits", {}) or {}
        amount_limits = limits.get("amount", {}) or {}
        cost_limits = limits.get("cost", {}) or {}

        return MarketConstraints(
            min_qty=float(amount_limits.get("min", self.DEFAULT_MIN_QTY) or 0),
            qty_step=float(
                (market.get("precision", {}) or {}).get(
                    "amount", self.DEFAULT_QTY_STEP
                )
                or self.DEFAULT_QTY_STEP
            ),
            min_notional=float(cost_limits.get("min", self.DEFAULT_MIN_NOTIONAL) or 0),
        )
