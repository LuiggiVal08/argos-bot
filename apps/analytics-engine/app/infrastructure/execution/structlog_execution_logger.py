"""StructlogExecutionLogger — logging estructurado de ejecuciones.

Usa structlog para producir logs en JSON con trazabilidad.
Si structlog no está disponible, fallback a logging estándar.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from ...domain.value_objects.execution_report import ExecutionReport
from ...application.ports.execution_logger import ExecutionLogger

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


class StructlogExecutionLogger:
    """Logger de ejecuciones con structlog (o fallback a logging).

    Args:
        logger_name: Nombre del logger (default "execution").
    """

    def __init__(self, logger_name: str = "execution") -> None:
        if _HAS_STRUCTLOG:
            self._log = structlog.get_logger(logger_name)
        else:
            self._log = logging.getLogger(logger_name)

    def _info(self, event: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG:
            self._log.info(event, **kwargs)
        else:
            self._log.info(f"{event}: {kwargs}")

    def _warning(self, event: str, **kwargs: Any) -> None:
        if _HAS_STRUCTLOG:
            self._log.warning(event, **kwargs)
        else:
            self._log.warning(f"{event}: {kwargs}")

    async def log_execution(self, report: ExecutionReport) -> None:
        self._info(
            "execution.completed",
            report_id=report.report_id,
            signal_id=report.signal_id,
            symbol=report.symbol,
            side=report.side.value,
            status=report.status,
            filled_qty=str(report.filled_qty),
            avg_price=str(report.avg_price) if report.avg_price else None,
            pnl=str(report.pnl) if report.pnl else None,
            order_id=report.order_id,
            position_id=report.position_id,
            errors=report.errors,
        )

    async def log_rejection(self, signal_id: str, reason: str) -> None:
        self._warning(
            "execution.rejected",
            signal_id=signal_id,
            reason=reason,
        )

    async def log_monitoring(
        self, position_id: str, pnl: Decimal, price: Decimal
    ) -> None:
        self._info(
            "execution.monitoring",
            position_id=position_id,
            pnl=str(pnl),
            price=str(price),
        )

    async def recent(self, limit: int = 20) -> list[dict]:
        # En una implementación real, leería de un buffer circular o DB.
        # Por ahora retorna vacío — se puede extender con un buffer en memoria.
        return []
