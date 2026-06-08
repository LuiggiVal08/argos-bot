"""LoggingIncidentReporter: reports incidents via structlog."""
from __future__ import annotations

import structlog

from ...application.ports.incident_reporter import IncidentReporter
from ...domain.value_objects.incident import (
    IncidentEvent,
    IncidentSeverity,
)


class LoggingIncidentReporter(IncidentReporter):
    def __init__(self) -> None:
        self._log = structlog.get_logger()

    async def report(self, event: IncidentEvent) -> None:
        log_fn = (
            self._log.critical
            if event.severity in (IncidentSeverity.P1, IncidentSeverity.P2)
            else self._log.error
        )
        log_fn(
            "incident",
            incident_id=event.incident_id,
            severity=event.severity.value,
            phase=event.phase.value,
            source=event.source,
            message=event.message,
            metadata=event.metadata,
            timestamp=event.timestamp.isoformat(),
        )

    async def declare(
        self,
        severity: IncidentSeverity,
        source: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> IncidentEvent:
        event = IncidentEvent(
            severity=severity,
            source=source,
            message=message,
            metadata=metadata or {},
        )
        await self.report(event)
        return event
