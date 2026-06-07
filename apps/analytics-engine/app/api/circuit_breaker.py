"""HTTP entry points for the circuit breaker (H3)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..application.use_cases.check_drawdown import (
    CheckDrawdownError,
    CheckDrawdownResult,
    CheckDrawdownUseCase,
)
from ..application.use_cases.open_day import OpenDayError, OpenDayUseCase
from ..application.use_cases.trip_circuit_breaker import (
    TripCircuitBreakerError,
    TripCircuitBreakerUseCase,
)
from ..composition import (
    get_check_drawdown_usecase,
    get_open_day_usecase,
    get_trip_circuit_breaker_usecase,
)
from ..domain.value_objects.drawdown_state import DrawdownState


router = APIRouter(prefix="/risk", tags=["risk"])


class OpenDayRequest(BaseModel):
    force: bool = Field(
        default=False,
        description="If true, overwrites an existing snapshot for the day. "
        "Use after a trip or manual reset.",
    )


class DrawdownSnapshotOut(BaseModel):
    starting_balance: str
    current_balance: str
    drawdown_pct: str
    is_profitable: bool
    taken_at: datetime


class CheckDrawdownResponse(BaseModel):
    state: DrawdownState
    snapshot: DrawdownSnapshotOut
    intraday_pnl: str
    checked_at: datetime
    trip_action: list[str] | None = Field(
        default=None,
        description="Steps that will be (or have been) executed "
        "on TRIP. None if not TRIP.",
    )


@router.post(
    "/day/open",
    response_model=DrawdownSnapshotOut,
    summary="Open a new trading day: capture the starting balance "
    "and reset the drawdown counters.",
)
async def open_day(
    body: OpenDayRequest,
    use_case: OpenDayUseCase = Depends(get_open_day_usecase),
) -> DrawdownSnapshotOut:
    try:
        snap = await use_case.execute(force=body.force)
    except OpenDayError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return DrawdownSnapshotOut(
        starting_balance=str(snap.starting_balance),
        current_balance=str(snap.current_balance),
        drawdown_pct=str(snap.drawdown_pct),
        is_profitable=snap.is_profitable,
        taken_at=snap.taken_at,
    )


@router.post(
    "/drawdown/check",
    response_model=CheckDrawdownResponse,
    summary="Evaluate the current drawdown. On TRIP, runs the trip "
    "action and returns the resulting state (HALTED via trip).",
)
async def check_drawdown(
    use_case: CheckDrawdownUseCase = Depends(get_check_drawdown_usecase),
) -> CheckDrawdownResponse:
    try:
        result = await use_case.execute()
    except CheckDrawdownError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return CheckDrawdownResponse(
        state=result.state,
        snapshot=DrawdownSnapshotOut(
            starting_balance=str(result.snapshot.starting_balance),
            current_balance=str(result.snapshot.current_balance),
            drawdown_pct=str(result.snapshot.drawdown_pct),
            is_profitable=result.snapshot.is_profitable,
            taken_at=result.snapshot.taken_at,
        ),
        intraday_pnl=str(result.intraday_pnl),
        checked_at=result.checked_at,
        trip_action=(
            [s.value for s in result.trip_action.steps]
            if result.trip_action is not None
            else None
        ),
    )


@router.get(
    "/drawdown",
    response_model=DrawdownSnapshotOut | None,
    summary="Return the current day's snapshot, or null if no day "
    "has been opened yet. Read-only: never triggers a trip.",
)
async def get_drawdown(
    use_case: CheckDrawdownUseCase = Depends(get_check_drawdown_usecase),
) -> DrawdownSnapshotOut | None:
    try:
        snap = await use_case.load_current_snapshot()
    except CheckDrawdownError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if snap is None:
        return None
    return DrawdownSnapshotOut(
        starting_balance=str(snap.starting_balance),
        current_balance=str(snap.current_balance),
        drawdown_pct=str(snap.drawdown_pct),
        is_profitable=snap.is_profitable,
        taken_at=snap.taken_at,
    )
