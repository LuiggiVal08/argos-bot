from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..value_objects.model_version import ModelVersion


@dataclass(frozen=True)
class ModelRecord:
    version: ModelVersion
    metrics: dict[str, float]
    feature_names: tuple[str, ...]
    training_date: str
    hyperparams: dict[str, Any]
    dataset_id: str
    is_champion: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "version": str(self.version),
            "metrics": self.metrics,
            "is_champion": self.is_champion,
            "training_date": self.training_date,
            "dataset_id": self.dataset_id,
        }


class ModelRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ModelRecord] = {}
        self._champion: ModelRecord | None = None

    def register(self, record: ModelRecord) -> None:
        key = str(record.version)
        if key in self._records:
            raise ValueError(f"version {key} already registered")
        self._records[key] = record

    def get(self, version: ModelVersion) -> ModelRecord | None:
        return self._records.get(str(version))

    def list_versions(self) -> list[ModelVersion]:
        return sorted(
            [r.version for r in self._records.values()],
            reverse=True,
        )

    def list_records(self) -> list[ModelRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: r.version,
            reverse=True,
        )

    @property
    def champion(self) -> ModelRecord | None:
        return self._champion

    def promote(self, version: ModelVersion) -> ModelRecord:
        record = self.get(version)
        if record is None:
            raise ValueError(f"version {version} not found in registry")
        if self._champion is not None:
            old_key = str(self._champion.version)
            self._records[old_key] = ModelRecord(
                version=self._champion.version,
                metrics=self._champion.metrics,
                feature_names=self._champion.feature_names,
                training_date=self._champion.training_date,
                hyperparams=self._champion.hyperparams,
                dataset_id=self._champion.dataset_id,
                is_champion=False,
            )
        self._records[str(version)] = ModelRecord(
            version=record.version,
            metrics=record.metrics,
            feature_names=record.feature_names,
            training_date=record.training_date,
            hyperparams=record.hyperparams,
            dataset_id=record.dataset_id,
            is_champion=True,
        )
        self._champion = self._records[str(version)]
        return self._champion

    def rollback(self) -> ModelRecord | None:
        if self._champion is None:
            return None
        all_records = self.list_records()
        candidates = [r for r in all_records if not r.is_champion]
        if not candidates:
            return None
        previous = candidates[0]
        self.promote(previous.version)
        return previous

    def count(self) -> int:
        return len(self._records)
