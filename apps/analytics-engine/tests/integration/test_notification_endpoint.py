"""Tests for notification HTTP endpoints."""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.composition import build_composition
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    monkeypatch.setenv("ENVIRONMENT_MODE", "BACKTESTING")
    monkeypatch.setenv("ARGOS_ENV_MODE_FILE", str(tmp_path / "env_mode.json"))
    comp = build_composition()
    app.state.composition = comp
    app.state.notify_on_event = comp.notify_on_event
    with TestClient(app) as c:
        yield c


class TestNotificationEndpoint:
    def test_status(self, client: TestClient) -> None:
        resp = client.get("/notification/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True

    def test_test_endpoint(self, client: TestClient) -> None:
        resp = client.post("/notification/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["event_type"] == "test"
