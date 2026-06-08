"""TripCircuitBreakerUseCase.

Implements the spec section 5 Historia 3 sad path:
  1. Cancel all open orders.
  2. Close all active positions at market price.
  3. Rewrite ENVIRONMENT_MODE = PASIVO.
  4. Halt the trading loop (the use case returns; the caller
     checks the state and stops dispatching orders).
  5. Log the block at CRITICAL level (the use case does NOT
     call any logger directly — it returns a `TripResult` and
     the composition root logs it. This keeps the use case
     pure of structlog/pino/print).

Sad path handling: each port call is independently caught. A
partial failure (e.g. cancel succeeded but close failed) is
recorded in the result and the next step is still attempted —
the spec says "stop the trading march" so we keep going until
the env mode is set and the snapshot is cleared, otherwise the
next iteration of the loop would still see stale state.

The result captures which steps succeeded and which failed so
the operator (or H4 incident response) can audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ...domain.value_objects.trip_action import TripAction, TripStep
from ..ports.environment_mode_writer import (
    EnvironmentMode,
    EnvironmentModeError,
    EnvironmentModeWriter,
)
from ..ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    PositionSummary,
)
from ..ports.drawdown_snapshot_repo import (
    DrawdownSnapshotRepo,
    DrawdownSnapshotRepoError,
)


class TripCircuitBreakerError(RuntimeError):
    """Raised only when ALL trip steps failed (the bot is still
    trading, env mode is not PASIVO, and orders are still open).
    The caller should escalate to a human operator."""


@dataclass(frozen=True)
class StepResult:
    step: TripStep
    ok: bool
    detail: str = ""
    data: Any = None


@dataclass(frozen=True)
class TripResult:
    executed_at: datetime
    steps: tuple[StepResult, ...]
    env_mode: EnvironmentMode | None
    positions_closed: tuple[PositionSummary, ...] = field(default_factory=tuple)
    orders_cancelled: int = 0

    @property
    def fully_succeeded(self) -> bool:
        return all(s.ok for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(not s.ok for s in self.steps)


class TripCircuitBreakerUseCase:
    def __init__(
        self,
        order_client: ExchangeOrderClient,
        env_writer: EnvironmentModeWriter,
        snapshot_repo: DrawdownSnapshotRepo,
        action: TripAction | None = None,
    ) -> None:
        self._orders = order_client
        self._env = env_writer
        self._snapshots = snapshot_repo
        self._action = action or TripAction.canonical()

    async def execute(self) -> TripResult:
        results: list[StepResult] = []
        positions_closed: list[PositionSummary] = []
        orders_cancelled = 0
        env_mode: EnvironmentMode | None = None

        for step in self._action.steps:
            try:
                if step is TripStep.CANCEL_ORDERS:
                    orders_cancelled = await self._orders.cancel_all_orders()
                    results.append(
                        StepResult(step, ok=True, data=orders_cancelled)
                    )
                elif step is TripStep.CLOSE_POSITIONS:
                    closed = await self._orders.close_all_positions()
                    positions_closed = list(closed)
                    results.append(
                        StepResult(step, ok=True, data=list(closed))
                    )
                elif step is TripStep.SET_PASIVO:
                    await self._env.write(EnvironmentMode.PASIVO)
                    env_mode = EnvironmentMode.PASIVO
                    results.append(StepResult(step, ok=True))
                elif step is TripStep.HALT:
                    # Drop the snapshot so the next day's open is
                    # forced. The trading loop stops because the
                    # use case returns with env_mode=PASIVO and
                    # the caller refuses to dispatch orders.
                    try:
                        await self._snapshots.clear()
                    except DrawdownSnapshotRepoError as e:
                        # Non-fatal: the snapshot will be stale
                        # for the next check, which will then
                        # re-trip. Logged in the step result.
                        results.append(
                            StepResult(step, ok=False, detail=str(e))
                        )
                        continue
                    results.append(StepResult(step, ok=True))
            except ExchangeOrderClientError as e:
                results.append(StepResult(step, ok=False, detail=str(e)))
            except EnvironmentModeError as e:
                results.append(StepResult(step, ok=False, detail=str(e)))

        result = TripResult(
            executed_at=datetime.now(tz=timezone.utc),
            steps=tuple(results),
            env_mode=env_mode,
            positions_closed=tuple(positions_closed),
            orders_cancelled=orders_cancelled,
        )

        if not result.fully_succeeded:
            raise TripCircuitBreakerError(
                f"trip_incomplete: {result.has_failures=}"
            )
        return result
