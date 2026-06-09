"""ExecutionLogger port — registro de eventos de ejecución."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from decimal import Decimal

from ...domain.value_objects.execution_report import ExecutionReport


@runtime_checkable
class ExecutionLogger(Protocol):
    """Registra eventos del ciclo de ejecución.

    Los adaptadores concretos pueden escribir a structlog, archivo,
    base de datos, o cualquier sistema de logging estructurado.
    """

    async def log_execution(self, report: ExecutionReport) -> None:
        """Registra una ejecución completada."""
        ...

    async def log_rejection(self, signal_id: str, reason: str) -> None:
        """Registra una señal rechazada (sin ejecutar)."""
        ...

    async def log_monitoring(self, position_id: str, pnl: Decimal, price: Decimal) -> None:
        """Registra un snapshot de monitoreo de posición."""
        ...

    async def recent(self, limit: int = 20) -> list[dict]:
        """Retorna los eventos más recientes (para API)."""
        ...
