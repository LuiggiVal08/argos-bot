"""ListIncidentsUseCase: query recent incidents."""
from __future__ import annotations

from ...domain.value_objects.incident import IncidentEvent
from ..ports.incident_repository import IncidentRepository


class ListIncidentsUseCase:
    def __init__(self, repo: IncidentRepository) -> None:
        self._repo = repo

    async def execute(self, limit: int = 50) -> list[IncidentEvent]:
        return await self._repo.list_recent(limit)

    async def by_id(self, incident_id: str) -> IncidentEvent | None:
        return await self._repo.by_id(incident_id)
