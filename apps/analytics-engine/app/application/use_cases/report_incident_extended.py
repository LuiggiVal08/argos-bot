from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.entities.disaster_recovery import (
    DisasterRecovery,
    IncidentEvent,
    IncidentSeverity,
    SystemMode,
)


@dataclass(frozen=True)
class DisasterStatus:
    mode: str
    total_incidents: int
    consecutive_failures: int
    unrecovered: int


class ReportIncidentExtendedUseCase:
    def __init__(self, recovery: DisasterRecovery) -> None:
        self._recovery = recovery

    async def execute(
        self,
        event_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> IncidentEvent:
        try:
            sev = IncidentSeverity(severity.upper())
        except ValueError:
            sev = IncidentSeverity.LOW

        event = IncidentEvent(
            event_type=event_type,
            severity=sev,
            message=message,
            details=details or {},
        )
        self._recovery.record_incident(event)
        self._recovery.set_mode(self._recovery.determine_mode())
        return event


class GetDisasterStatusUseCase:
    def __init__(self, recovery: DisasterRecovery) -> None:
        self._recovery = recovery

    async def execute(self) -> DisasterStatus:
        report = self._recovery.report()
        return DisasterStatus(
            mode=report["mode"],
            total_incidents=report["total_incidents"],
            consecutive_failures=report["consecutive_failures"],
            unrecovered=report["unrecovered"],
        )


class RecoverFromIncidentUseCase:
    def __init__(self, recovery: DisasterRecovery) -> None:
        self._recovery = recovery

    async def execute(self, event_type: str) -> dict[str, Any]:
        strategy = self._recovery.suggest_recovery(event_type)
        self._recovery.mark_recovered(event_type)
        return {
            "event_type": event_type,
            "strategy": strategy.value,
            "new_mode": self._recovery.mode.value,
        }
