from __future__ import annotations

from typing import Any

from ...domain.entities.model_registry import ModelRegistry


class ListModelVersionsUseCase:
    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    async def execute(self) -> list[dict[str, Any]]:
        return [r.summary() for r in self._registry.list_records()]
