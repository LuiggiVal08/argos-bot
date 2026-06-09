"""Tests for notification domain VOs."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.value_objects.notification import (
    NotificationEvent,
    NotificationEventType,
    NotificationSeverity,
)


class TestNotificationEvent:
    def test_minimal_creation(self) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="Test",
            message="msg",
        )
        assert event.event_type == NotificationEventType.TEST
        assert event.severity == NotificationSeverity.INFO
        assert event.title == "Test"
        assert event.message == "msg"
        assert event.symbol is None
        assert event.metadata == {}
        assert isinstance(event.timestamp, datetime)

    def test_all_fields(self) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.POSITION_OPENED,
            severity=NotificationSeverity.INFO,
            title="Position Opened",
            message="BUY 0.5 BTC @ 60,000",
            symbol="BTC/USDT",
            metadata={"strategy": "ema_cross"},
        )
        assert event.symbol == "BTC/USDT"
        assert event.metadata["strategy"] == "ema_cross"

    def test_is_immutable(self) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        with pytest.raises(AttributeError):
            event.title = "changed"  # type: ignore[misc]

    def test_timestamp_is_utc(self) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.TEST,
            severity=NotificationSeverity.INFO,
            title="T",
            message="M",
        )
        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == timezone.utc

    def test_different_severities(self) -> None:
        for sev in NotificationSeverity:
            event = NotificationEvent(
                event_type=NotificationEventType.TEST,
                severity=sev,
                title="T",
                message="M",
            )
            assert event.severity == sev

    def test_all_event_types(self) -> None:
        for etype in NotificationEventType:
            event = NotificationEvent(
                event_type=etype,
                severity=NotificationSeverity.INFO,
                title="T",
                message="M",
            )
            assert event.event_type == etype
