"""MockExchangeAdapter — no-op adapter for E2E testing.

Records every order placed via `placed_orders` list for test
assertions. Returns a FILLED OrderResult with a deterministic
avg_price so the full pipeline validates without real exchange.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ...application.ports.exchange_order_gateway import (
    ExchangeOrderGateway,
    ExchangeOrderGatewayError,
)
from ...domain.value_objects.order import OrderResult, OrderSide, OrderStatus, OrderType


@dataclass
class MockExchangeAdapter:
    placed_orders: list[dict[str, Any]] = field(default_factory=list)
    fail_next: bool = False

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: Decimal,
        sl_price: Decimal | None = None,
        tp_price: Decimal | None = None,
    ) -> OrderResult:
        if self.fail_next:
            self.fail_next = False
            raise ExchangeOrderGatewayError("mock exchange failure")

        record = dict(
            symbol=symbol,
            side=side.value,
            amount=amount,
            sl_price=float(sl_price) if sl_price else None,
            tp_price=float(tp_price) if tp_price else None,
        )
        self.placed_orders.append(record)

        return OrderResult(
            id=f"mock-{len(self.placed_orders)}",
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            filled_amount=amount,
            avg_price=Decimal("60000"),
            status=OrderStatus.FILLED,
        )

    @property
    def last_order(self) -> dict[str, Any] | None:
        return self.placed_orders[-1] if self.placed_orders else None

    def reset(self) -> None:
        self.placed_orders.clear()
        self.fail_next = False
