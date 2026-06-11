"""Risk API: position-size endpoint.

POST /risk/position-size

Body:
  {
    "symbol": "BTC/USDT",
    "entry_price": "60000.00",     // decimal string
    "risk_pct": "0.01",            // optional, default 0.01
    "timeframe": "1m",             // optional, default 1m
    "atr_window": 14               // optional, default 14
  }

Response (200):
  {
    "position": { "units", "sl_distance", "entry_price",
                  "notional_value", "risk_amount", "risk_pct" },
    "constraints": { "min_qty", "qty_step", "min_notional" }
  }

Sad path (per spec §5 Historia 2):
  - 422 ComputePositionSizeError: balance or ATR unavailable.
  - 422 PositionSizeBelowMinLotError: units below market min.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..application.use_cases.compute_position_size import (
    ComputePositionSizeError,
    ComputePositionSizeUseCase,
    PositionSizeBelowMinLotError,
    PositionSizeInput,
)
from ..composition import get_compute_position_size_usecase
from ..domain.value_objects.risk_pct import (
    InvalidRiskPctError,
    MAX_RISK_PCT,
    DEFAULT_RISK_PCT,
    RiskPct,
)


router = APIRouter(prefix="/risk", tags=["risk"])


class PositionSizeRequest(BaseModel):
    symbol: str = Field(..., min_length=3, max_length=32)
    entry_price: str = Field(..., description="Decimal string in quote")
    risk_pct: str | None = Field(
        default=None,
        description=f"Decimal in (0, {MAX_RISK_PCT}]. "
        f"Default {DEFAULT_RISK_PCT}.",
    )
    timeframe: str = Field(default="1m", min_length=1, max_length=8)
    atr_window: int = Field(default=14, ge=2, le=512)


class _ConstraintsOut(BaseModel):
    min_qty: float
    qty_step: float
    min_notional: float


class _PositionOut(BaseModel):
    units: str
    sl_distance: str
    entry_price: str
    notional_value: str
    risk_amount: str
    risk_pct: str


class PositionSizeResponse(BaseModel):
    position: _PositionOut
    constraints: _ConstraintsOut


@router.post(
    "/position-size",
    response_model=PositionSizeResponse,
    summary="Compute position size so the SL distance (ATR) keeps the "
    "loss per trade at the configured risk_pct of free balance.",
)
async def compute_position_size(
    body: PositionSizeRequest,
    use_case: ComputePositionSizeUseCase = Depends(
        get_compute_position_size_usecase
    ),
) -> PositionSizeResponse:
    try:
        risk_pct = RiskPct(body.risk_pct) if body.risk_pct else RiskPct.default()
    except InvalidRiskPctError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        entry_price = Decimal(body.entry_price)
    except Exception as e:
        raise HTTPException(
            status_code=422, detail=f"entry_price_invalid: {body.entry_price}"
        ) from e

    inp = PositionSizeInput(
        symbol=body.symbol,
        entry_price=entry_price,
        risk_pct=risk_pct,
        timeframe=body.timeframe,
        atr_window=body.atr_window,
    )

    try:
        result = await use_case.execute(inp)
    except PositionSizeBelowMinLotError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ComputePositionSizeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return PositionSizeResponse(
        position=_PositionOut(**result.position.to_dict()),
        constraints=_ConstraintsOut(
            min_qty=result.constraints.min_qty,
            qty_step=result.constraints.qty_step,
            min_notional=result.constraints.min_notional,
        ),
    )
