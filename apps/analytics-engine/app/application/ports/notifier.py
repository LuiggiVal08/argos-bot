"""Notifier port: async notification dispatch to external channels."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...domain.value_objects.notification import NotificationEvent


@runtime_checkable
class Notifier(Protocol):
    async def send(self, event: NotificationEvent) -> None:
        ...
