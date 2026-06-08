"""Integration tests for /incident endpoints.

Tests the HTTP contract for declaring and listing incidents.
"""
from __future__ import annotations

from typing import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports.incident_reporter import IncidentReporter
from app.application.ports.incident_repository import IncidentRepository
from app.application.use_cases.list_incidents import ListIncidentsUseCase
from app.application.use_cases.report_incident import ReportIncidentUseCase
from app.domain.value_objects.incident import (
    IncidentEvent,
    IncidentSeverity,
)
from app.main import app


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_client() -> TestClient:
    from app.composition import (
        get_list_incidents_usecase,
        get_report_incident_usecase,
    )

    repo = AsyncMock(spec=IncidentRepository)
    reporter = AsyncMock(spec=IncidentReporter)
    report_uc = ReportIncidentUseCase(reporter=reporter, repo=repo)
    list_uc = ListIncidentsUseCase(repo=repo)

    app.dependency_overrides[get_report_incident_usecase] = lambda: report_uc
    app.dependency_overrides[get_list_incidents_usecase] = lambda: list_uc
    return TestClient(app), repo, reporter


class TestIncidentEndpoints:
    def test_declare_and_list(self) -> None:
        client, repo, reporter = _make_client()
        reporter.declare.return_value = IncidentEvent(
            severity=IncidentSeverity.P2,
            source="test-manual",
            message="manual incident",
            metadata={"reason": "test"},
        )

        # Declare
        r = client.post(
            "/incident/declare",
            json={
                "severity": "P2",
                "source": "test-manual",
                "message": "manual incident",
                "metadata": {"reason": "test"},
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "test-manual"
        assert body["severity"] == "P2"
        assert body["incident_id"] != ""

    def test_list_empty(self) -> None:
        client, repo, reporter = _make_client()
        repo.list_recent.return_value = []

        r = client.get("/incident/list")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_with_events(self) -> None:
        client, repo, reporter = _make_client()
        repo.list_recent.return_value = [
            IncidentEvent(
                severity=IncidentSeverity.P1,
                source="detector",
                message="critical event",
                metadata={"symbol": "BTC/USDT"},
            )
        ]

        r = client.get("/incident/list")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["severity"] == "P1"
        assert body[0]["source"] == "detector"

    def test_declare_returns_422_on_missing_fields(self) -> None:
        client, repo, reporter = _make_client()

        r = client.post(
            "/incident/declare",
            json={"severity": "P1"},  # missing source/message
        )
        assert r.status_code == 422
