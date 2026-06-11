from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SystemMode(Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    SAFE_MODE = "SAFE_MODE"
    HALTED = "HALTED"


class RecoveryStrategy(Enum):
    RESTART = "RESTART"
    REBUILD_POSITIONS = "REBUILD_POSITIONS"
    REBUILD_MODELS = "REBUILD_MODELS"
    RECONNECT = "RECONNECT"
    CLEAR_STATE = "CLEAR_STATE"


class IncidentSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class IncidentEvent:
    event_type: str
    severity: IncidentSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    recovered: bool = False

    def __post_init__(self) -> None:
        from datetime import datetime, timezone
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class DisasterRecovery:
    EVENTS_MONITORED = (
        "exchange_disconnect",
        "message_bus_down",
        "inference_failure",
        "historical_corruption",
        "unexpected_restart",
        "consecutive_losses",
        "extreme_volatility",
    )

    def __init__(self) -> None:
        self._mode = SystemMode.NORMAL
        self._incidents: list[IncidentEvent] = []
        self._consecutive_failures: int = 0

    @property
    def mode(self) -> SystemMode:
        return self._mode

    def set_mode(self, mode: SystemMode) -> None:
        self._mode = mode

    def record_incident(self, event: IncidentEvent) -> None:
        self._incidents.append(event)
        if event.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = max(0, self._consecutive_failures - 1)

    def determine_mode(self) -> SystemMode:
        recent = self._incidents[-10:] if len(self._incidents) >= 10 else self._incidents
        critical_count = sum(
            1 for i in recent
            if i.severity == IncidentSeverity.CRITICAL and not i.recovered
        )
        high_count = sum(
            1 for i in recent
            if i.severity == IncidentSeverity.HIGH and not i.recovered
        )

        if critical_count >= 2 or self._consecutive_failures >= 5:
            return SystemMode.HALTED
        if critical_count >= 1 or high_count >= 3:
            return SystemMode.SAFE_MODE
        if high_count >= 1:
            return SystemMode.DEGRADED
        return SystemMode.NORMAL

    def suggest_recovery(self, event_type: str) -> RecoveryStrategy:
        mapping: dict[str, RecoveryStrategy] = {
            "exchange_disconnect": RecoveryStrategy.RECONNECT,
            "message_bus_down": RecoveryStrategy.RECONNECT,
            "inference_failure": RecoveryStrategy.RESTART,
            "historical_corruption": RecoveryStrategy.CLEAR_STATE,
            "unexpected_restart": RecoveryStrategy.REBUILD_POSITIONS,
        }
        return mapping.get(event_type, RecoveryStrategy.RESTART)

    def mark_recovered(self, event_type: str) -> None:
        for incident in self._incidents:
            if incident.event_type == event_type and not incident.recovered:
                incident.recovered = True

        self._consecutive_failures = max(
            0, self._consecutive_failures - len([
                i for i in self._incidents
                if i.event_type == event_type
            ])
        )
        self._mode = self.determine_mode()

    def report(self) -> dict[str, Any]:
        return {
            "mode": self._mode.value,
            "total_incidents": len(self._incidents),
            "consecutive_failures": self._consecutive_failures,
            "unrecovered": sum(1 for i in self._incidents if not i.recovered),
        }
