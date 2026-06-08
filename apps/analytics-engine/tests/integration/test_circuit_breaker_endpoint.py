"""End-to-end test for the H3 circuit-breaker endpoints.

The composition root is built in BACKTESTING mode and the
HTTP client drives the open → trade → check flow:
  1. POST /risk/day/open        → capture starting balance.
  2. POST /risk/drawdown/check  → SAFE (no P&L).
  3. Add a 6% loss to the journal (via the test-only backdoor).
  4. POST /risk/drawdown/check  → TRIP; trip runs; env becomes
     PASIVO; snapshot cleared.
  5. GET /risk/drawdown         → null (no day open).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.application.ports.trade_journal import TradeRecord
from app.main import app
from app.composition import build_composition


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ENVIRONMENT_MODE", "BACKTESTING")
    monkeypatch.setenv("ARGOS_ENV_MODE_FILE", str(tmp_path / "env_mode.json"))
    comp = build_composition()
    app.state.composition = comp
    with TestClient(app) as c:
        yield c


def test_open_then_safe(client: TestClient) -> None:
    r = client.post("/risk/day/open", json={"force": False})
    assert r.status_code == 200
    body = r.json()
    assert body["starting_balance"] == "10000"
    assert body["current_balance"] == "10000"
    assert body["drawdown_pct"] == "0"

    r = client.post("/risk/drawdown/check")
    assert r.status_code == 200
    assert r.json()["state"] == "SAFE"


def test_open_refuses_overwrite(client: TestClient) -> None:
    client.post("/risk/day/open", json={"force": False})
    r = client.post("/risk/day/open", json={"force": False})
    assert r.status_code == 422
    assert "snapshot_exists" in r.json()["detail"]


def test_open_with_force_resets(client: TestClient) -> None:
    client.post("/risk/day/open", json={"force": False})
    r = client.post("/risk/day/open", json={"force": True})
    assert r.status_code == 200


def test_trip_after_loss(client: TestClient) -> None:
    comp = app.state.composition
    # Open the day.
    client.post("/risk/day/open", json={"force": False})
    # Inject a 6% loss into the shared journal.
    asyncio.run(
        comp.trade_journal.add(
            TradeRecord(
                symbol="BTC/USDT",
                realized_pnl=Decimal("-600"),
                closed_at=datetime.now(tz=timezone.utc),
                reference="t-loss",
            )
        )
    )
    # Check → TRIP, trip runs.
    r = client.post("/risk/drawdown/check")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "TRIP"
    assert body["trip_action"] == [
        "CANCEL_ORDERS", "CLOSE_POSITIONS", "SET_PASIVO", "HALT"
    ]
    # The snapshot was cleared, so a fresh GET returns null.
    r = client.get("/risk/drawdown")
    assert r.status_code == 200
    assert r.json() is None


def test_check_without_open_returns_422(client: TestClient) -> None:
    r = client.post("/risk/drawdown/check")
    assert r.status_code == 422
    assert "snapshot_missing" in r.json()["detail"]


def test_get_drawdown_null_when_no_day(client: TestClient) -> None:
    r = client.get("/risk/drawdown")
    assert r.status_code == 200
    assert r.json() is None
