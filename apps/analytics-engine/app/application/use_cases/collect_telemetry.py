from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.entities.telemetry_engine import (
    MetricPoint,
    TelemetryEngine,
    TelemetrySnapshot,
)


@dataclass(frozen=True)
class TelemetryResult:
    snapshot: TelemetrySnapshot
    recent_metrics: list[dict[str, Any]]


class CollectTelemetryUseCase:
    def __init__(self, telemetry: TelemetryEngine) -> None:
        self._telemetry = telemetry

    async def execute(self) -> TelemetryResult:
        snapshot = self._telemetry.snapshot()
        recent = self._telemetry.recent_points(limit=50)
        return TelemetryResult(
            snapshot=snapshot,
            recent_metrics=[
                {
                    "name": p.name,
                    "value": p.value,
                    "labels": p.labels,
                    "timestamp": p.timestamp,
                }
                for p in recent
            ],
        )


class RecordTelemetryUseCase:
    def __init__(self, telemetry: TelemetryEngine) -> None:
        self._telemetry = telemetry

    async def execute(self, point: MetricPoint) -> None:
        self._telemetry.record(point)

    async def record_all(
        self,
        data_engine: dict[str, float] | None = None,
        analytics_engine: dict[str, float] | None = None,
        execution_engine: dict[str, float] | None = None,
        training_engine: dict[str, float] | None = None,
    ) -> None:
        if data_engine:
            self._telemetry.record_data_engine(**data_engine)
        if analytics_engine:
            self._telemetry.record_analytics_engine(**analytics_engine)
        if execution_engine:
            self._telemetry.record_execution_engine(**execution_engine)
        if training_engine:
            self._telemetry.record_training_engine(**training_engine)
