from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...domain.value_objects.model_version import ModelVersion


class FileSystemModelRepository:
    BASE_DIR = Path.home() / ".argos" / "model_registry"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else self.BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        version: ModelVersion,
        metadata: dict[str, Any],
        weights: bytes,
    ) -> None:
        version_dir = self._base_dir / str(version)
        version_dir.mkdir(parents=True, exist_ok=True)
        meta_path = version_dir / "metadata.json"
        weights_path = version_dir / "model.pt"
        meta_path.write_text(json.dumps(metadata, indent=2, default=str))
        weights_path.write_bytes(weights)

    async def load(
        self,
        version: ModelVersion,
    ) -> tuple[dict[str, Any], bytes] | None:
        version_dir = self._base_dir / str(version)
        if not version_dir.exists():
            return None
        meta_path = version_dir / "metadata.json"
        weights_path = version_dir / "model.pt"
        if not meta_path.exists() or not weights_path.exists():
            return None
        metadata = json.loads(meta_path.read_text())
        weights = weights_path.read_bytes()
        return metadata, weights

    async def load_latest(self) -> tuple[dict[str, Any], bytes] | None:
        versions = await self.list_versions()
        if not versions:
            return None
        return await self.load(versions[0])

    async def list_versions(self) -> list[ModelVersion]:
        if not self._base_dir.exists():
            return []
        versions: list[ModelVersion] = []
        for child in self._base_dir.iterdir():
            if child.is_dir():
                try:
                    versions.append(ModelVersion.parse(child.name))
                except ValueError:
                    continue
        return sorted(versions, reverse=True)

    async def delete(self, version: ModelVersion) -> bool:
        version_dir = self._base_dir / str(version)
        if not version_dir.exists():
            return False
        import shutil
        shutil.rmtree(version_dir)
        return True
