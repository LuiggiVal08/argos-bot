from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.model_registry import ModelRegistry


@dataclass(frozen=True)
class RollbackResult:
    success: bool
    previous_version: str | None
    message: str


class RollbackModelUseCase:
    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    async def execute(self) -> RollbackResult:
        previous = self._registry.rollback()
        if previous is None:
            return RollbackResult(
                success=False,
                previous_version=None,
                message="no previous version available for rollback",
            )
        return RollbackResult(
            success=True,
            previous_version=str(previous.version),
            message=f"rolled back to {previous.version}",
        )
