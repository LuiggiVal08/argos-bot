"""ReportIncidentUseCase: declare an incident from anywhere in the system.

Persists the incident to the repository and notifies via the reporter
(logging, external alerts, etc).
"""
from __future__ import annotations

from ...domain.value_objects.incident import (
    IncidentEvent,
    IncidentSeverity,
)
from ..ports.incident_reporter import IncidentReporter
from ..ports.incident_repository import IncidentRepository


class ReportIncidentUseCase:
    def __init__(
        self,
        reporter: IncidentReporter,
        repo: IncidentRepository,
    ) -> None:
        self._reporter = reporter
        self._repo = repo

    async def execute(
        self,
        severity: IncidentSeverity,
        source: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> IncidentEvent:
        event = await self._reporter.declare(
            severity=severity,
            source=source,
            message=message,
            metadata=metadata,
        )
        await self._repo.save(event)
        return event
