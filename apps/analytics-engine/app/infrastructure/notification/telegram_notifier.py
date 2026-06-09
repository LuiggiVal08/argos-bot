"""Telegram notifier: sends notifications via Telegram Bot API."""
from __future__ import annotations

from typing import Any

import structlog

from ...domain.value_objects.notification import (
    NotificationEvent,
    NotificationSeverity,
)
from ...application.ports.notifier import Notifier

log = structlog.get_logger()


class TelegramNotifier(Notifier):
    def __init__(
        self, bot_token: str, chat_id: str, http_client: Any | None = None
    ) -> None:
        self._token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._http = http_client

    async def send(self, event: NotificationEvent) -> None:
        if self._http is None:
            try:
                import httpx
                self._http = httpx.AsyncClient()
            except ImportError:
                log.warning("httpx_not_available", telegram_skipped=True)
                return

        emoji = {
            NotificationSeverity.INFO: "\u2705",
            NotificationSeverity.WARN: "\u26a0\ufe0f",
            NotificationSeverity.CRITICAL: "\U0001f6a8",
        }.get(event.severity, "")

        text = f"<b>{emoji} {event.title}</b>\n{event.message}"
        if event.symbol:
            text += f"\n<b>Symbol</b>: {event.symbol}"

        try:
            resp = await self._http.post(
                self._base_url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                log.warning(
                    "telegram_api_error",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as e:
            log.warning("telegram_send_failed", error=str(e))
