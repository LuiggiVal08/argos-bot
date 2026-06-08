"""CcxtOrderClient: implements ExchangeOrderClient via ccxt.async_support.

For each symbol in the configured universe:
  - cancel_all_orders: fetches open orders and cancels each one
    (CCXT does not have a single bulk-cancel endpoint in the
    unified API).
  - close_all_positions: fetches positions and submits a
    market order on the opposite side with reduce_only=True.

Sad path: any ccxt exception (network timeout, exchange 5xx,
auth) is wrapped in `ExchangeOrderClientError`. The trip use
case catches per-symbol and records the step result; we don't
abort the whole trip on a single symbol failure.
"""
from __future__ import annotations

from decimal import Decimal

import ccxt.async_support as ccxt

from ...application.ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    PositionSummary,
)


class CcxtOrderClient(ExchangeOrderClient):
    def __init__(
        self,
        exchange: ccxt.Exchange,
        symbols: tuple[str, ...] = ("BTC/USDT",),
    ) -> None:
        self._exchange = exchange
        self._symbols = symbols

    async def cancel_all_orders(self) -> int:
        cancelled = 0
        for symbol in self._symbols:
            try:
                orders = await self._exchange.fetch_open_orders(symbol)
            except Exception as e:
                raise ExchangeOrderClientError(
                    f"fetch_open_orders_failed: {symbol}: {e}"
                ) from e
            for o in orders:
                try:
                    await self._exchange.cancel_order(o["id"], symbol)
                    cancelled += 1
                except Exception as e:
                    # Per spec: keep going on a single order's
                    # failure so the trip is at least partial.
                    # The TripResult will surface the failure.
                    raise ExchangeOrderClientError(
                        f"cancel_order_failed: {symbol} {o.get('id')}: {e}"
                    ) from e
        return cancelled

    async def close_all_positions(self) -> list[PositionSummary]:
        closed: list[PositionSummary] = []
        for symbol in self._symbols:
            try:
                positions = await self._exchange.fetch_positions([symbol])
            except Exception as e:
                raise ExchangeOrderClientError(
                    f"fetch_positions_failed: {symbol}: {e}"
                ) from e
            for p in positions:
                amt = Decimal(str(p.get("contracts") or p.get("amount") or 0))
                if amt == 0:
                    continue
                side = "buy" if (p.get("side") or "").lower() == "short" else "sell"
                try:
                    await self._exchange.create_order(
                        symbol,
                        type="market",
                        side=side,
                        amount=abs(float(amt)),
                        params={"reduceOnly": True},
                    )
                except Exception as e:
                    raise ExchangeOrderClientError(
                        f"close_position_failed: {symbol} "
                        f"{p.get('side')} {amt}: {e}"
                    ) from e
                closed.append(
                    PositionSummary(
                        symbol=symbol,
                        side=str(p.get("side") or ""),
                        quantity=amt,
                        entry_price=Decimal(str(p.get("entryPrice") or 0)),
                    )
                )
        return closed
