"""ExchangeOrderGateway port — simplified market-order interface.

Use cases that follow a predict→execute pipeline (e.g. NovaQuant)
call this to place a single market order with optional SL/TP.

The ExchangeOrderClient port (used by the full H4 execution flow)
is more comprehensive (bracket orders, cancel-all, close-all).
This port is intentionally simpler.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from ...domain.value_objects.order import OrderResult, OrderSide


class ExchangeOrderGatewayError(RuntimeError):
    """Raised when order placement fails."""


@runtime_checkable
class ExchangeOrderGateway(Protocol):
    """Place a market entry order optionally protected by SL/TP.

    The adapter owns the retry/error-handling policy (retry 3×,
    then raise). The use case catches the error and decides what
    to do (log, alert, halt).
    """

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: Decimal,
        sl_price: Decimal | None = None,
        tp_price: Decimal | None = None,
    ) -> OrderResult:
        """Place a market order with optional stop-loss and take-profit.

        Args:
            symbol:   Trading pair, e.g. "BTC/USDT".
            side:     BUY or SELL.
            amount:   Quantity in base currency.
            sl_price: Stop-loss trigger price (optional).
            tp_price: Take-profit trigger price (optional).

        Returns:
            OrderResult with status, filled_amount, avg_price.

        Raises:
            ExchangeOrderGatewayError on infrastructure failure.
        """
        ...
