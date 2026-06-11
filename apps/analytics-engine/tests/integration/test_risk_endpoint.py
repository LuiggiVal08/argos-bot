"""End-to-end test for the /risk/position-size endpoint.

The composition root is built in BACKTESTING mode (so no network)
and overridden in the test to use mocks. The endpoint should
return a 200 with a PositionSize in the happy path and 422 for
both sad paths (provider error, below min lot).
"""
from decimal import Decimal
from typing import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports.atr_calculator import AtrCalculator
from app.application.ports.balance_provider import BalanceProvider
from app.application.ports.min_lot_provider import (
    MarketConstraints,
    MinLotProvider,
)
from app.application.use_cases.compute_position_size import (
    ComputePositionSizeUseCase,
)
from app.domain.entities.risk_calculator import RiskCalculator
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.risk_pct import RiskPct
from app.main import app


def _make_app(
    balance: Decimal | Exception,
    atr: Atr | Exception,
    constraints: MarketConstraints | Exception,
) -> TestClient:
    """Build a TestClient with a composition root that uses mocks.

    Overrides `app.dependency_overrides` so `Depends(...)` calls in
    the router return the test's mock-backed use case.
    """
    from app.api import risk as risk_api
    from app.composition import get_compute_position_size_usecase

    bp = AsyncMock(spec=BalanceProvider)
    if isinstance(balance, Exception):
        bp.get_free_balance.side_effect = balance
    else:
        bp.get_free_balance.return_value = balance

    ac = AsyncMock(spec=AtrCalculator)
    if isinstance(atr, Exception):
        ac.get_atr.side_effect = atr
    else:
        ac.get_atr.return_value = atr

    ml = AsyncMock(spec=MinLotProvider)
    if isinstance(constraints, Exception):
        ml.get_constraints.side_effect = constraints
    else:
        ml.get_constraints.return_value = constraints

    uc = ComputePositionSizeUseCase(
        risk_calculator=RiskCalculator(),
        balance_provider=bp,
        atr_calculator=ac,
        min_lot_provider=ml,
    )
    app.dependency_overrides[get_compute_position_size_usecase] = lambda: uc
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestRiskPositionSizeEndpoint:
    def test_happy_path(self) -> None:
        client = _make_app(
            balance=Decimal("10000"),
            atr=Atr(600),
            constraints=MarketConstraints(0.0, 1e-8, 0.0),
        )
        r = client.post(
            "/risk/position-size",
            json={
                "symbol": "BTC/USDT",
                "entry_price": "60000",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["position"]["units"] == "0.16666667"
        assert body["position"]["sl_distance"] == "600"
        assert body["position"]["risk_amount"] == "100.00"
        assert body["constraints"]["min_qty"] == 0.0

    def test_risk_pct_validation(self) -> None:
        client = _make_app(
            balance=Decimal("10000"),
            atr=Atr(600),
            constraints=MarketConstraints(0.0, 1e-8, 0.0),
        )
        r = client.post(
            "/risk/position-size",
            json={
                "symbol": "BTC/USDT",
                "entry_price": "60000",
                "risk_pct": "0.05",  # 5%, exceeds 2% cap
            },
        )
        assert r.status_code == 422
        assert "exceeds" in r.json()["detail"]

    def test_balance_provider_error_returns_422(self) -> None:
        from app.application.ports.balance_provider import BalanceProviderError

        client = _make_app(
            balance=BalanceProviderError("ccxt timeout"),
            atr=Atr(600),
            constraints=MarketConstraints(0.0, 1e-8, 0.0),
        )
        r = client.post(
            "/risk/position-size",
            json={"symbol": "BTC/USDT", "entry_price": "60000"},
        )
        assert r.status_code == 422
        assert "balance_unavailable" in r.json()["detail"]

    def test_below_min_lot_returns_422(self) -> None:
        client = _make_app(
            balance=Decimal("10000"),
            atr=Atr(600),
            constraints=MarketConstraints(
                min_qty=1.0, qty_step=1e-8, min_notional=0.0
            ),
        )
        r = client.post(
            "/risk/position-size",
            json={"symbol": "BTC/USDT", "entry_price": "60000"},
        )
        assert r.status_code == 422
        assert "min_qty" in r.json()["detail"]
