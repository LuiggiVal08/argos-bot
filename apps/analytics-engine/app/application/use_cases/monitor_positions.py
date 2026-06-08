"""MonitorPositionsUseCase — monitorea posiciones abiertas y cierra SL/TP.

Pipeline:
  1. Cargar posiciones abiertas desde PositionRepository
  2. Para cada posición, obtener precio actual
  3. Verificar SL/TP hits via PositionTracker
  4. Si SL/TP hit: cerrar posición a mercado, loggear P&L
  5. Actualizar estado en repositorio
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable
from uuid import uuid4

from ...domain.entities.position_tracker import PositionTracker, TrackerVerdict
from ...domain.value_objects.execution_report import ExecutionReport
from ...domain.value_objects.live_position import LivePosition
from ..ports.execution_logger import ExecutionLogger
from ..ports.exchange_order_client import ExchangeOrderClient
from ..ports.position_repository import PositionRepository

PriceProvider = Callable[[str], Awaitable[Decimal]]


@dataclass(frozen=True)
class MonitorResult:
    closed: int = 0
    held: int = 0
    details: list[dict] = field(default_factory=list)


class MonitorPositionsError(RuntimeError):
    """Raised when position monitoring fails."""


class MonitorPositionsUseCase:
    """Monitorea posiciones abiertas y ejecuta cierres por SL/TP.

    Args:
        position_repo:   Repositorio de posiciones.
        exchange_client: Cliente para cerrar posiciones a mercado.
        execution_logger: Logger de eventos.
        price_provider:  Callable async que retorna el precio actual
                         de un símbolo.
    """

    def __init__(
        self,
        position_repo: PositionRepository,
        exchange_client: ExchangeOrderClient,
        execution_logger: ExecutionLogger,
        price_provider: PriceProvider,
    ) -> None:
        self._position_repo = position_repo
        self._exchange = exchange_client
        self._logger = execution_logger
        self._price_provider = price_provider

    async def run(self) -> MonitorResult:
        positions = await self._position_repo.list_open()
        if not positions:
            return MonitorResult()

        closed = 0
        held = 0
        details: list[dict] = []

        for pos in positions:
            price = await self._price_provider(pos.symbol)
            result = PositionTracker.check(pos, price)

            if result.verdict == TrackerVerdict.HOLD:
                held += 1
                await self._logger.log_monitoring(
                    pos.position_id, result.pnl, price
                )
                details.append({
                    "position_id": pos.position_id,
                    "verdict": "HOLD",
                    "pnl": str(result.pnl),
                })
                continue

            # SL or TP hit — close position
            try:
                await self._exchange.close_position(pos.symbol)
            except Exception as e:
                raise MonitorPositionsError(
                    f"failed to close {pos.position_id}: {e}"
                ) from e

            closed_pos = LivePosition(
                position_id=pos.position_id,
                symbol=pos.symbol,
                side=pos.side,
                units=pos.units,
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                sl_price=pos.sl_price,
                tp_price=pos.tp_price,
                opened_at=pos.opened_at,
                closed_at=datetime.now(timezone.utc),
                realized_pnl=result.pnl,
                status=result.verdict.value,
            )
            await self._position_repo.save(closed_pos)

            report = ExecutionReport(
                report_id=uuid4().hex[:12],
                signal_id="",
                symbol=pos.symbol,
                side=pos.side,
                status="FILLED",
                filled_qty=pos.units,
                avg_price=price,
                pnl=result.pnl,
                position_id=pos.position_id,
            )
            await self._logger.log_execution(report)
            closed += 1
            details.append({
                "position_id": pos.position_id,
                "verdict": result.verdict.value,
                "pnl": str(result.pnl),
                "price": str(price),
            })

        return MonitorResult(closed=closed, held=held, details=details)
