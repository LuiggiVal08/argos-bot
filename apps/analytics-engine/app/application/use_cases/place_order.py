"""PlaceOrderUseCase: orchestrates order placement with retry + emergency fallback.

Per spec section 5 Historia 4:
  - Happy path: place composite order (market entry + SL + TP).
  - Sad path: if SL placement fails after retry exhaustion,
    the use case catches SlPlacementError and issues an
    emergency market order to close the position immediately.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ...domain.value_objects.order import (
    CompositeOrder,
    OrderResult,
    OrderSide,
)
from ..ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    SlPlacementError,
)


class PlaceOrderError(RuntimeError):
    """Raised when the order cannot be placed and the emergency
    fallback also failed. The position may be orphaned."""


@dataclass(frozen=True)
class PlaceOrderResult:
    entry_order: OrderResult
    emergency_order: OrderResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.emergency_order is None


class PlaceOrderUseCase:
    def __init__(self, order_client: ExchangeOrderClient) -> None:
        self._orders = order_client

    async def execute(
        self,
        symbol: str,
        side: OrderSide,
        entry_amount: Decimal,
        sl_price: Decimal | None = None,
        tp_price: Decimal | None = None,
    ) -> PlaceOrderResult:
        order = CompositeOrder(
            symbol=symbol,
            side=side,
            entry_amount=entry_amount,
            sl_price=sl_price,
            tp_price=tp_price,
        )

        try:
            entry = await self._orders.place_composite_order(order)
        except SlPlacementError as e:
            # SL failed after retry — position is open but
            # unprotected. Emergency close immediately.
            entry = e.entry_order
            close_side = (
                OrderSide.SELL if side is OrderSide.BUY else OrderSide.BUY
            )
            try:
                emergency = await self._orders.place_emergency_market(
                    symbol, close_side, entry_amount
                )
            except ExchangeOrderClientError as ee:
                raise PlaceOrderError(
                    f"sl_placement_failed_and_emergency_failed: "
                    f"{symbol}: {e}; emergency: {ee}"
                ) from ee
            return PlaceOrderResult(
                entry_order=entry,
                emergency_order=emergency,
            )
        except ExchangeOrderClientError as e:
            raise PlaceOrderError(f"entry_order_failed: {symbol}: {e}") from e

        return PlaceOrderResult(entry_order=entry)
