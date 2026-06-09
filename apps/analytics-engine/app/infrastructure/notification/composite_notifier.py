"""Composite notifier: fans out notifications to multiple channels."""
from __future__ import annotations

import structlog

from ...domain.value_objects.notification import NotificationEvent
from ...application.ports.notifier import Notifier

log = structlog.get_logger()


class CompositeNotifier(Notifier):
    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    async def send(self, event: NotificationEvent) -> None:
        for notifier in self._notifiers:
            try:
                await notifier.send(event)
            except Exception as e:
                log.warning(
                    "composite_notifier_error",
                    notifier=type(notifier).__name__,
                    error=str(e),
                )
