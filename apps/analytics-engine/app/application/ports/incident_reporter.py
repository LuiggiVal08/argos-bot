"""Incident reporter port.

Any component (use case, adapter, detector) can report an incident
through this port. Implementations may log, store, or forward the
event to external systems.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.incident import IncidentEvent, IncidentSeverity


@runtime_checkable
class IncidentReporter(Protocol):
    async def report(self, event: IncidentEvent) -> None:
        """Persist and/or notify the incident event."""

    async def declare(
        self,
        severity: IncidentSeverity,
        source: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> IncidentEvent:
        """Convenience: construct and report an incident in one call."""
        ...
