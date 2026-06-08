"""Tests for H4-B domain VOs and use cases.

Covers IncidentSeverity, IncidentEvent, ReportIncidentUseCase,
ListIncidentsUseCase, and the infrastructure adapters.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import structlog

from app.application.ports.incident_reporter import IncidentReporter
from app.application.ports.incident_repository import IncidentRepository
from app.application.use_cases.list_incidents import ListIncidentsUseCase
from app.application.use_cases.report_incident import ReportIncidentUseCase
from app.domain.value_objects.incident import (
    IncidentEvent,
    IncidentPhase,
    IncidentSeverity,
)


class TestIncidentSeverity:
    def test_values(self) -> None:
        assert IncidentSeverity.P1.value == "P1"
        assert IncidentSeverity.P2.value == "P2"
        assert IncidentSeverity.P3.value == "P3"
        assert IncidentSeverity.P4.value == "P4"


class TestIncidentEvent:
    def test_creates_with_defaults(self) -> None:
        event = IncidentEvent(
            severity=IncidentSeverity.P2,
            source="test-detector",
            message="something happened",
        )
        assert event.severity is IncidentSeverity.P2
        assert event.source == "test-detector"
        assert event.message == "something happened"
        assert event.phase is IncidentPhase.IDENTIFIED
        assert len(event.incident_id) == 12
        assert event.metadata == {}

    def test_auto_generates_incident_id(self) -> None:
        e1 = IncidentEvent(severity=IncidentSeverity.P1, source="a", message="x")
        e2 = IncidentEvent(severity=IncidentSeverity.P1, source="a", message="x")
        assert e1.incident_id != e2.incident_id


class TestInMemoryIncidentRepository:
    @pytest.fixture
    def repo(self) -> IncidentRepository:
        from app.infrastructure.monitoring.in_memory_incident_repo import (
            InMemoryIncidentRepository,
        )
        return InMemoryIncidentRepository()

    async def test_save_and_list(self, repo: IncidentRepository) -> None:
        e1 = IncidentEvent(severity=IncidentSeverity.P1, source="s1", message="m1")
        e2 = IncidentEvent(severity=IncidentSeverity.P2, source="s2", message="m2")
        await repo.save(e1)
        await repo.save(e2)
        recent = await repo.list_recent()
        assert len(recent) == 2
        # Most recent first
        assert recent[0].incident_id == e2.incident_id
        assert recent[1].incident_id == e1.incident_id

    async def test_by_id(self, repo: IncidentRepository) -> None:
        e = IncidentEvent(severity=IncidentSeverity.P3, source="s", message="m")
        await repo.save(e)
        found = await repo.by_id(e.incident_id)
        assert found is not None
        assert found.incident_id == e.incident_id
        assert await repo.by_id("nonexistent") is None

    async def test_list_limit(self, repo: IncidentRepository) -> None:
        for i in range(10):
            await repo.save(
                IncidentEvent(
                    severity=IncidentSeverity.P4,
                    source="s",
                    message=f"m{i}",
                )
            )
        recent = await repo.list_recent(limit=3)
        assert len(recent) == 3


class TestLoggingIncidentReporter:
    @pytest.fixture
    def reporter(self) -> IncidentReporter:
        from app.infrastructure.monitoring.logging_incident_reporter import (
            LoggingIncidentReporter,
        )
        return LoggingIncidentReporter()

    async def test_declare_returns_event(
        self, reporter: IncidentReporter
    ) -> None:
        event = await reporter.declare(
            severity=IncidentSeverity.P2,
            source="test",
            message="incident test",
        )
        assert isinstance(event, IncidentEvent)
        assert event.source == "test"
        assert event.severity is IncidentSeverity.P2

    async def test_declare_includes_metadata(
        self, reporter: IncidentReporter
    ) -> None:
        event = await reporter.declare(
            severity=IncidentSeverity.P1,
            source="test",
            message="critical",
            metadata={"symbol": "BTC/USDT"},
        )
        assert event.metadata == {"symbol": "BTC/USDT"}


class TestReportIncidentUseCase:
    @pytest.fixture
    def use_case(self) -> ReportIncidentUseCase:
        reporter = AsyncMock(spec=IncidentReporter)
        repo = AsyncMock(spec=IncidentRepository)

        async def _declare(**kwargs):
            kwargs.setdefault("metadata", {})
            return IncidentEvent(**kwargs)

        reporter.declare.side_effect = _declare
        return ReportIncidentUseCase(reporter=reporter, repo=repo)

    async def test_execute_reports_and_persists(
        self, use_case: ReportIncidentUseCase
    ) -> None:
        event = await use_case.execute(
            severity=IncidentSeverity.P3,
            source="detector-x",
            message="latency spike",
        )
        assert event.source == "detector-x"
        use_case._reporter.declare.assert_awaited_once_with(
            severity=IncidentSeverity.P3,
            source="detector-x",
            message="latency spike",
            metadata=None,
        )
        use_case._repo.save.assert_awaited_once()


class TestListIncidentsUseCase:
    @pytest.fixture
    def use_case(self) -> ListIncidentsUseCase:
        repo = AsyncMock(spec=IncidentRepository)
        repo.list_recent.return_value = [
            IncidentEvent(
                severity=IncidentSeverity.P2,
                source="src",
                message="msg",
            )
        ]
        return ListIncidentsUseCase(repo=repo)

    async def test_list_recent(
        self, use_case: ListIncidentsUseCase
    ) -> None:
        events = await use_case.execute(limit=10)
        assert len(events) == 1
        use_case._repo.list_recent.assert_awaited_once_with(10)

    async def test_by_id(self, use_case: ListIncidentsUseCase) -> None:
        use_case._repo.by_id.return_value = None
        result = await use_case.by_id("abc")
        assert result is None
        use_case._repo.by_id.assert_awaited_once_with("abc")
