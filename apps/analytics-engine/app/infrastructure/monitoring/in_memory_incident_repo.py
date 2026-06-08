"""InMemoryIncidentRepository: stores incidents in process memory."""
from __future__ import annotations

from ...application.ports.incident_repository import IncidentRepository
from ...domain.value_objects.incident import IncidentEvent


class InMemoryIncidentRepository(IncidentRepository):
    def __init__(self) -> None:
        self._events: list[IncidentEvent] = []

    async def save(self, event: IncidentEvent) -> None:
        self._events.append(event)

    async def list_recent(self, limit: int = 50) -> list[IncidentEvent]:
        return list(reversed(self._events))[:limit]

    async def by_id(self, incident_id: str) -> IncidentEvent | None:
        for event in self._events:
            if event.incident_id == incident_id:
                return event
        return None
