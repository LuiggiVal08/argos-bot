"""InMemoryPositionRepository — posiciones en memoria (tests/backtesting)."""
from __future__ import annotations

from ...domain.value_objects.live_position import LivePosition
from ...application.ports.position_repository import PositionRepository


class InMemoryPositionRepository:
    """Almacena posiciones en un dict en memoria.

    Útil para tests y modo BACKTESTING. No persiste entre reinicios.
    """

    def __init__(self) -> None:
        self._store: dict[str, LivePosition] = {}

    async def save(self, position: LivePosition) -> None:
        self._store[position.position_id] = position

    async def load(self, position_id: str) -> LivePosition | None:
        return self._store.get(position_id)

    async def list_open(self) -> list[LivePosition]:
        return [p for p in self._store.values() if p.is_open]

    async def list_all(self) -> list[LivePosition]:
        return list(self._store.values())

    async def delete(self, position_id: str) -> bool:
        return self._store.pop(position_id, None) is not None
