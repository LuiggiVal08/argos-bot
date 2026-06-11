"""PositionRepository port — persistencia de posiciones."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.live_position import LivePosition


@runtime_checkable
class PositionRepository(Protocol):
    """Persistencia de posiciones abiertas/cerradas."""

    async def save(self, position: LivePosition) -> None:
        """Persiste una posición (insert o update según position_id)."""
        ...

    async def load(self, position_id: str) -> LivePosition | None:
        """Carga una posición por ID. None si no existe."""
        ...

    async def list_open(self) -> list[LivePosition]:
        """Retorna todas las posiciones con status OPEN."""
        ...

    async def list_all(self) -> list[LivePosition]:
        """Retorna todas las posiciones (abiertas y cerradas)."""
        ...

    async def delete(self, position_id: str) -> bool:
        """Elimina una posición. True si existía."""
        ...
