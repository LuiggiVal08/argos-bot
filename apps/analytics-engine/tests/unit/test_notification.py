"""Tests for notification infrastructure (LoggingNotifier, RedisNotifier)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.value_objects.notification import (
    NotificationEvent,
    NotificationEventType,
    NotificationSeverity,
)
from app.infrastructure.notification.composite_notifier import (
    CompositeNotifier,
)
from app.infrastructure.notification.logging_notifier import LoggingNotifier


class TestLoggingNotifier:
    async def test_send_does_not_raise(self) -> None:
        notifier = LoggingNotifier()
        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="Test",
            message="msg",
        )
        await notifier.send(event)


class TestRedisNotifier:
    @pytest.mark.asyncio
    async def test_send_publishes_to_stream(self) -> None:
        from app.infrastructure.notification.redis_notifier import RedisNotifier

        mock_client = AsyncMock()
        notifier = RedisNotifier(redis_url="redis://localhost:6379")
        notifier._client = mock_client

        event = NotificationEvent(
            event_type=NotificationEventType.POSITION_OPENED,
            severity=NotificationSeverity.INFO,
            title="Position Opened",
            message="BUY 0.5 BTC @ 60,000",
            symbol="BTC/USDT",
        )
        await notifier.send(event)

        mock_client.xadd.assert_awaited_once()
        call = mock_client.xadd.await_args
        assert call is not None
        pos_args = call[0]
        assert len(pos_args) >= 2
        assert pos_args[0] == "notifications:events"
        assert "p" in pos_args[1]

    @pytest.mark.asyncio
    async def test_send_handles_redis_failure(self) -> None:
        from app.infrastructure.notification.redis_notifier import RedisNotifier

        mock_client = AsyncMock()
        mock_client.xadd.side_effect = Exception("connection lost")
        notifier = RedisNotifier(redis_url="redis://localhost:6379")
        notifier._client = mock_client

        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        await notifier.send(event)
        mock_client.xadd.assert_awaited_once()


class TestCompositeNotifier:
    async def test_sends_to_all_channels(self) -> None:
        a = AsyncMock()
        b = AsyncMock()
        notifier = CompositeNotifier([a, b])

        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        await notifier.send(event)
        a.send.assert_awaited_once_with(event)
        b.send.assert_awaited_once_with(event)

    async def test_continues_on_partial_failure(self) -> None:
        class FailingNotifier:
            async def send(self, event: NotificationEvent) -> None:
                raise RuntimeError("fail")

        a = FailingNotifier()
        b = AsyncMock()
        notifier = CompositeNotifier([a, b])

        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        await notifier.send(event)
        b.send.assert_awaited_once_with(event)


class TestNotifyOnEventUseCase:
    async def test_execute_calls_notifier(self) -> None:
        from app.application.use_cases.notify_on_event import NotifyOnEventUseCase

        mock_notifier = AsyncMock()
        uc = NotifyOnEventUseCase(notifier=mock_notifier)
        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        await uc.execute(event)
        mock_notifier.send.assert_awaited_once_with(event)
