"""Incident repository port for querying past incidents."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.incident import IncidentEvent


@runtime_checkable
class IncidentRepository(Protocol):
    async def save(self, event: IncidentEvent) -> None: ...

    async def list_recent(
        self, limit: int = 50
    ) -> list[IncidentEvent]: ...

    async def by_id(self, incident_id: str) -> IncidentEvent | None: ...
