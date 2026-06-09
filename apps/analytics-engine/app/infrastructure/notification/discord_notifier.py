"""Discord notifier: sends notifications via Discord webhook URLs."""
from __future__ import annotations

from typing import Any

import structlog

from ...domain.value_objects.notification import (
    NotificationEvent,
    NotificationSeverity,
)
from ...application.ports.notifier import Notifier

log = structlog.get_logger()

_COLORS = {
    NotificationSeverity.INFO: 0x00FF00,
    NotificationSeverity.WARN: 0xFFA500,
    NotificationSeverity.CRITICAL: 0xFF0000,
}


class DiscordNotifier(Notifier):
    def __init__(self, webhook_url: str, http_client: Any | None = None) -> None:
        self._url = webhook_url
        self._http = http_client

    async def send(self, event: NotificationEvent) -> None:
        if self._http is None:
            try:
                import httpx
                self._http = httpx.AsyncClient()
            except ImportError:
                log.warning("httpx_not_available", discord_skipped=True)
                return

        embed = {
            "title": event.title,
            "description": event.message,
            "color": _COLORS.get(event.severity, 0x808080),
            "timestamp": event.timestamp.isoformat(),
        }
        if event.symbol:
            embed["fields"] = [{"name": "Symbol", "value": event.symbol, "inline": True}]

        payload = {"embeds": [embed]}

        try:
            resp = await self._http.post(
                self._url, json=payload, timeout=10
            )
            if resp.status_code not in (200, 204):
                log.warning(
                    "discord_webhook_error",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as e:
            log.warning("discord_send_failed", error=str(e))
