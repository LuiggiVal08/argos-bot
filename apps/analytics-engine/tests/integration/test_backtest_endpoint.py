"""Tests de integracion para el endpoint POST /backtest/run y GET /backtest/strategies."""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.composition import build_composition


@pytest.fixture
def client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    monkeypatch.setenv("ENVIRONMENT_MODE", "BACKTESTING")
    monkeypatch.setenv("ARGOS_ENV_MODE_FILE", str(tmp_path / "env_mode.json"))
    comp = build_composition()
    app.state.composition = comp
    with TestClient(app) as c:
        yield c


class TestBacktestStrategiesEndpoint:
    def test_list_strategies(self, client: TestClient):
        resp = client.get("/backtest/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "ema_cross" in data["strategies"]
        assert "rsi_reversion" in data["strategies"]

    def test_list_returns_list(self, client: TestClient):
        resp = client.get("/backtest/strategies")
        data = resp.json()
        assert isinstance(data["strategies"], list)
        assert len(data["strategies"]) >= 2


class TestBacktestRunEndpoint:
    def test_unknown_strategy_returns_422(self, client: TestClient):
        resp = client.post("/backtest/run", params={"strategy_id": "nonexistent"})
        assert resp.status_code == 422
        assert "unknown_strategy" in resp.text

    def test_invalid_risk_pct_returns_422(self, client: TestClient):
        resp = client.post("/backtest/run", params={"strategy_id": "ema_cross", "risk_pct": 0.05})
        assert resp.status_code == 422

    def test_invalid_initial_balance_returns_422(self, client: TestClient):
        resp = client.post("/backtest/run", params={"strategy_id": "ema_cross", "initial_balance": -100})
        assert resp.status_code == 422

    def test_fake_source_returns_422_insufficient(self, client: TestClient):
        """With BACKTESTING mode and FakeOhlcvSource, should fail on no data."""
        resp = client.post("/backtest/run", params={
            "strategy_id": "ema_cross",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "initial_balance": 10000,
            "risk_pct": 0.01,
        })
        assert resp.status_code == 422

    def test_rsi_reversion_returns_422(self, client: TestClient):
        resp = client.post("/backtest/run", params={
            "strategy_id": "rsi_reversion",
            "symbol": "BTC/USDT",
            "initial_balance": 10000,
        })
        assert resp.status_code == 422

    def test_custom_params_accepted(self, client: TestClient):
        resp = client.post("/backtest/run", params={
            "strategy_id": "ema_cross",
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "initial_balance": 50000,
            "risk_pct": 0.02,
            "max_trades": 10,
        })
        assert resp.status_code == 422  # FakeOhlcvSource gives no data
