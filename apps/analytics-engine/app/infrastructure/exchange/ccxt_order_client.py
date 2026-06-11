"""CcxtOrderClient: implements ExchangeOrderClient via ccxt.async_support.

For each symbol in the configured universe:
  - cancel_all_orders: fetches open orders and cancels each one.
  - close_all_positions: fetches positions and submits a
    market order on the opposite side with reduce_only=True.
  - place_composite_order: places a market entry + stop loss +
    take profit bracket order. The SL leg has retry logic.
  - place_emergency_market: fire-and-forget liquidation.
"""
from __future__ import annotations

import asyncio
import random
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt

from ...application.ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    PositionSummary,
    SlPlacementError,
)
from ...domain.value_objects.order import (
    CompositeOrder,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
)


class CcxtOrderClient(ExchangeOrderClient):
    def __init__(
        self,
        exchange: ccxt.Exchange,
        symbols: tuple[str, ...] = ("BTC/USDT",),
        max_sl_retries: int = 3,
        sl_retry_base_ms: float = 100.0,
    ) -> None:
        self._exchange = exchange
        self._symbols = symbols
        self._max_sl_retries = max_sl_retries
        self._sl_retry_base_ms = sl_retry_base_ms

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

    async def close_position(self, symbol: str) -> PositionSummary:
        """Close the active position for a single symbol in futures.
        Fetches current position and issues a reduce-only market order
        on the opposite side."""
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
                    f"close_position_failed: {symbol} {p.get('side')} {amt}: {e}"
                ) from e
            return PositionSummary(
                symbol=symbol,
                side=str(p.get("side") or ""),
                quantity=amt,
                entry_price=Decimal(str(p.get("entryPrice") or 0)),
            )
        raise ExchangeOrderClientError(
            f"no_position_found: {symbol}"
        )

    async def place_composite_order(
        self, order: CompositeOrder
    ) -> OrderResult:
        # 1. Place market entry.
        try:
            raw = await self._exchange.create_order(
                order.symbol,
                type="market",
                side=order.side.value.lower(),
                amount=abs(float(order.entry_amount)),
            )
        except Exception as e:
            raise ExchangeOrderClientError(
                f"entry_order_failed: {order.symbol}: {e}"
            ) from e

        entry_result = _to_order_result(raw, order.side)

        # 2. Place stop loss with retry.
        if order.sl_price is not None:
            sl_side = (
                OrderSide.SELL if order.side is OrderSide.BUY else OrderSide.BUY
            )
            sl_error: Exception | None = None
            for attempt in range(self._max_sl_retries):
                try:
                    await self._exchange.create_order(
                        order.symbol,
                        type="stop_market",
                        side=sl_side.value.lower(),
                        amount=abs(float(order.entry_amount)),
                        params={
                            "stopPrice": float(order.sl_price),
                            "reduceOnly": True,
                        },
                    )
                    sl_error = None
                    break
                except Exception as e:
                    sl_error = e
                    if attempt < self._max_sl_retries - 1:
                        delay = (
                            self._sl_retry_base_ms
                            * (2 ** attempt)
                            + random.uniform(0, 20)
                        )
                        await asyncio.sleep(delay / 1000)
            if sl_error is not None:
                raise SlPlacementError(
                    entry_order=entry_result,
                    message=(
                        f"sl_placement_failed after {self._max_sl_retries} retries: "
                        f"{order.symbol}: {sl_error}. Entry order {entry_result.id} "
                        f"is open. Close position immediately."
                    ),
                ) from sl_error

        # 3. Place take profit (no retry; TP failure is non-critical).
        if order.tp_price is not None:
            tp_side = (
                OrderSide.SELL if order.side is OrderSide.BUY else OrderSide.BUY
            )
            try:
                await self._exchange.create_order(
                    order.symbol,
                    type="take_profit_market",
                    side=tp_side.value.lower(),
                    amount=abs(float(order.entry_amount)),
                    params={
                        "stopPrice": float(order.tp_price),
                        "reduceOnly": True,
                    },
                )
            except Exception:
                pass

        return entry_result

    async def place_emergency_market(
        self, symbol: str, side: OrderSide, amount: Decimal
    ) -> OrderResult:
        try:
            raw = await self._exchange.create_order(
                symbol,
                type="market",
                side=side.value.lower(),
                amount=abs(float(amount)),
            )
        except Exception as e:
            raise ExchangeOrderClientError(
                f"emergency_order_failed: {symbol}: {e}"
            ) from e
        return _to_order_result(raw, side)


def _to_order_result(raw: dict[str, Any], side: OrderSide) -> OrderResult:
    raw_id = raw.get("id", "")
    order_type_raw = raw.get("type", "market") or "market"
    if "stop" in order_type_raw.lower():
        otype = OrderType.STOP_LOSS_MARKET
    elif "take_profit" in order_type_raw.lower() or "take profit" in order_type_raw.lower():
        otype = OrderType.TAKE_PROFIT_MARKET
    else:
        otype = OrderType.MARKET

    status_raw = (raw.get("status") or "new").lower()
    status_map: dict[str, OrderStatus] = {
        "new": OrderStatus.NEW,
        "open": OrderStatus.NEW,
        "partially_filled": OrderStatus.PARTIALLY_FILLED,
        "filled": OrderStatus.FILLED,
        "canceled": OrderStatus.CANCELLED,
        "cancelled": OrderStatus.CANCELLED,
        "rejected": OrderStatus.REJECTED,
        "expired": OrderStatus.EXPIRED,
    }
    status = status_map.get(status_raw, OrderStatus.NEW)

    filled = Decimal(str(raw.get("filled") or 0))
    avg_price = raw.get("price") or raw.get("average") or None
    avg = Decimal(str(avg_price)) if avg_price else None
    client_id = raw.get("clientOrderId") or ""

    return OrderResult(
        id=raw_id,
        symbol=raw.get("symbol", ""),
        side=side,
        type=otype,
        filled_amount=filled,
        avg_price=avg,
        status=status,
        client_order_id=client_id,
    )
