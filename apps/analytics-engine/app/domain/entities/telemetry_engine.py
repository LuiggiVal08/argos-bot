from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MetricPoint:
    name: str
    value: float
    labels: dict[str, str]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class TelemetrySnapshot:
    data_engine: dict[str, float] = field(default_factory=dict)
    analytics_engine: dict[str, float] = field(default_factory=dict)
    execution_engine: dict[str, float] = field(default_factory=dict)
    training_engine: dict[str, float] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def merge(self, other: TelemetrySnapshot) -> None:
        self.data_engine.update(other.data_engine)
        self.analytics_engine.update(other.analytics_engine)
        self.execution_engine.update(other.execution_engine)
        self.training_engine.update(other.training_engine)
        self.timestamp = datetime.now(timezone.utc).isoformat()


class TelemetryEngine:
    MAX_POINTS = 10000

    def __init__(self) -> None:
        self._points: list[MetricPoint] = []
        self._current = TelemetrySnapshot()

    def record(self, point: MetricPoint) -> None:
        self._points.append(point)
        if len(self._points) > self.MAX_POINTS:
            self._points.pop(0)

    def record_data_engine(
        self,
        ticks_received: float = 0,
        latency_ms: float = 0,
        msg_loss: float = 0,
        reconnections: float = 0,
    ) -> None:
        self._current.data_engine.update({
            "ticks_received": ticks_received,
            "latency_ms": latency_ms,
            "message_loss": msg_loss,
            "reconnections": reconnections,
        })

    def record_analytics_engine(
        self,
        inference_time_ms: float = 0,
        signals_generated: float = 0,
        avg_uncertainty: float = 0,
        avg_confidence: float = 0,
    ) -> None:
        self._current.analytics_engine.update({
            "inference_time_ms": inference_time_ms,
            "signals_generated": signals_generated,
            "avg_uncertainty": avg_uncertainty,
            "avg_confidence": avg_confidence,
        })

    def record_execution_engine(
        self,
        orders_sent: float = 0,
        orders_rejected: float = 0,
        slippage: float = 0,
    ) -> None:
        self._current.execution_engine.update({
            "orders_sent": orders_sent,
            "orders_rejected": orders_rejected,
            "slippage": slippage,
        })

    def record_training_engine(
        self,
        training_duration_s: float = 0,
        metrics_obtained: float = 0,
        promotions: float = 0,
    ) -> None:
        self._current.training_engine.update({
            "training_duration_s": training_duration_s,
            "metrics_obtained": metrics_obtained,
            "promotions": promotions,
        })

    def snapshot(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            data_engine=dict(self._current.data_engine),
            analytics_engine=dict(self._current.analytics_engine),
            execution_engine=dict(self._current.execution_engine),
            training_engine=dict(self._current.training_engine),
        )

    def recent_points(
        self,
        metric_name: str | None = None,
        limit: int = 100,
    ) -> list[MetricPoint]:
        if metric_name:
            filtered = [p for p in self._points if p.name == metric_name]
        else:
            filtered = list(self._points)
        return filtered[-limit:]

    def clear(self) -> None:
        self._points.clear()
        self._current = TelemetrySnapshot()
