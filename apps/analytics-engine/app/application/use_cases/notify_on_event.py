"""NotifyOnEvent use case: dispatches notification events via Notifier."""
from __future__ import annotations

from ...domain.value_objects.notification import NotificationEvent
from ..ports.notifier import Notifier


class NotifyOnEventUseCase:
    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    async def execute(self, event: NotificationEvent) -> None:
        await self._notifier.send(event)
