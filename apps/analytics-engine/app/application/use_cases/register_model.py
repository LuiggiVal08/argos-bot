from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ...domain.entities.model_registry import ModelRecord, ModelRegistry
from ...domain.value_objects.model_version import ModelVersion


@dataclass(frozen=True)
class RegisterModelResult:
    version: str
    success: bool
    message: str


class RegisterModelUseCase:
    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        major: int,
        minor: int,
        metrics: dict[str, float],
        feature_names: tuple[str, ...],
        hyperparams: dict[str, Any],
        dataset_id: str,
    ) -> RegisterModelResult:
        version = ModelVersion.from_datetime(major, minor)
        record = ModelRecord(
            version=version,
            metrics=metrics,
            feature_names=feature_names,
            training_date=datetime.now(timezone.utc).isoformat(),
            hyperparams=hyperparams,
            dataset_id=dataset_id,
        )
        try:
            self._registry.register(record)
            return RegisterModelResult(
                version=str(version),
                success=True,
                message=f"model {version} registered",
            )
        except ValueError as e:
            return RegisterModelResult(
                version=str(version),
                success=False,
                message=str(e),
            )
