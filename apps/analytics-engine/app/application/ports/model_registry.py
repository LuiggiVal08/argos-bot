from __future__ import annotations

from typing import Any, Protocol

from ...domain.value_objects.model_version import ModelVersion


class ModelRepository(Protocol):
    async def save(self, version: ModelVersion, metadata: dict[str, Any], weights: bytes) -> None:
        ...

    async def load(self, version: ModelVersion) -> tuple[dict[str, Any], bytes] | None:
        ...

    async def load_latest(self) -> tuple[dict[str, Any], bytes] | None:
        ...

    async def list_versions(self) -> list[ModelVersion]:
        ...

    async def delete(self, version: ModelVersion) -> bool:
        ...
