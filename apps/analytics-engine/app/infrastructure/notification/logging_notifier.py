"""Logging notifier: writes notification events to structlog."""
from __future__ import annotations

import structlog

from ...domain.value_objects.notification import NotificationEvent
from ...application.ports.notifier import Notifier

log = structlog.get_logger()


class LoggingNotifier(Notifier):
    async def send(self, event: NotificationEvent) -> None:
        log.info(
            "notification",
            event_type=event.event_type.value,
            severity=event.severity.value,
            title=event.title,
            message=event.message,
            symbol=event.symbol,
        )
