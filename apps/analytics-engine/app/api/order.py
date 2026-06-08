"""Order execution API: place bracketed orders.

POST /order/place

Places a composite order (market entry + SL + TP) via
PlaceOrderUseCase. If the SL placement fails after retry
exhaustion, an emergency market order is issued to close
the position immediately.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..application.use_cases.place_order import (
    PlaceOrderError,
    PlaceOrderUseCase,
)
from ..composition import get_place_order_usecase
from ..domain.value_objects.order import (
    OrderResult,
    OrderSide,
    OrderStatus,
)


router = APIRouter(prefix="/order", tags=["order"])


class PlaceOrderBody(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    side: OrderSide = Field(...)
    entry_amount: str = Field(..., description="Quantity in base currency")
    sl_price: str | None = Field(default=None, description="Stop loss price")
    tp_price: str | None = Field(default=None, description="Take profit price")


class OrderResultOut(BaseModel):
    id: str
    symbol: str
    side: OrderSide
    type: str
    filled_amount: str
    avg_price: str | None = None
    status: OrderStatus


class PlaceOrderResponse(BaseModel):
    succeeded: bool
    entry_order: OrderResultOut
    emergency_order: OrderResultOut | None = None


@router.post(
    "/place",
    response_model=PlaceOrderResponse,
    summary="Place a bracket order (market entry + SL + TP). "
    "On SL failure after retries, issues an emergency close.",
)
async def place_order(
    body: PlaceOrderBody,
    use_case: PlaceOrderUseCase = Depends(get_place_order_usecase),
) -> PlaceOrderResponse:
    try:
        result = await use_case.execute(
            symbol=body.symbol,
            side=body.side,
            entry_amount=Decimal(body.entry_amount),
            sl_price=Decimal(body.sl_price) if body.sl_price else None,
            tp_price=Decimal(body.tp_price) if body.tp_price else None,
        )
    except PlaceOrderError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return PlaceOrderResponse(
        succeeded=result.succeeded,
        entry_order=_to_out(result.entry_order),
        emergency_order=(
            _to_out(result.emergency_order)
            if result.emergency_order is not None
            else None
        ),
    )


def _to_out(order_result: OrderResult) -> OrderResultOut:
    return OrderResultOut(
        id=order_result.id,
        symbol=order_result.symbol,
        side=order_result.side,
        type=order_result.type.value,
        filled_amount=str(order_result.filled_amount),
        avg_price=str(order_result.avg_price) if order_result.avg_price else None,
        status=order_result.status,
    )
