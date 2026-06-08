"""Incident domain VOs: severity levels and incident events.

Per spec.md §4: incidents are classified P1-P4 and flow through
4 OWASP phases (Identify → Contain → Eradicate → Recover).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class IncidentSeverity(str, Enum):
    P1 = "P1"  # Fund loss / secret leak
    P2 = "P2"  # Operations halted / drawdown > 5%
    P3 = "P3"  # Service degradation (latency > 2ms)
    P4 = "P4"  # Cosmetic / non-urgent


class IncidentPhase(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    CONTAINED = "CONTAINED"
    ERADICATED = "ERADICATED"
    RECOVERED = "RECOVERED"


@dataclass(frozen=True)
class IncidentEvent:
    severity: IncidentSeverity
    source: str
    message: str
    metadata: dict[str, str] = field(default_factory=dict)
    incident_id: str = field(default_factory=lambda: uuid4().hex[:12])
    phase: IncidentPhase = IncidentPhase.IDENTIFIED
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
