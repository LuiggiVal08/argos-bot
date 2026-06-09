"""Notification domain VO: structured event payload for external channels."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class NotificationSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class NotificationEventType(str, Enum):
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    DRAWDOOWN_WARNING = "drawdown.warning"
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker.tripped"
    SIGNAL_REJECTED = "signal.rejected"
    ORDER_FAILED = "order.failed"
    TEST = "test"


@dataclass(frozen=True)
class NotificationEvent:
    event_type: NotificationEventType
    severity: NotificationSeverity
    title: str
    message: str
    symbol: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
