"""Integration test for the POST /order/place endpoint.

Injects mocks via dependency_overrides so we can test the
HTTP contract without touching the exchange.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.application.ports.exchange_order_client import (
    ExchangeOrderClient,
    ExchangeOrderClientError,
    SlPlacementError,
)
from app.application.use_cases.place_order import PlaceOrderUseCase
from app.domain.value_objects.order import (
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.main import app


def _mock_result(
    oid: str = "mock-entry-1",
    side: OrderSide = OrderSide.BUY,
    filled: str = "0.1",
    price: str = "60000",
) -> OrderResult:
    return OrderResult(
        id=oid,
        symbol="BTC/USDT",
        side=side,
        type=OrderType.MARKET,
        filled_amount=Decimal(filled),
        avg_price=Decimal(price),
        status=OrderStatus.FILLED,
    )


def _make_client(
    composite: OrderResult | Exception,
    emergency: OrderResult | Exception | None = None,
) -> TestClient:
    from app.composition import get_place_order_usecase

    client_mock = AsyncMock(spec=ExchangeOrderClient)

    if isinstance(composite, Exception):
        client_mock.place_composite_order.side_effect = composite
    else:
        client_mock.place_composite_order.return_value = composite

    if emergency is not None:
        if isinstance(emergency, Exception):
            client_mock.place_emergency_market.side_effect = emergency
        else:
            client_mock.place_emergency_market.return_value = emergency

    uc = PlaceOrderUseCase(order_client=client_mock)
    app.dependency_overrides[get_place_order_usecase] = lambda: uc
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class TestPlaceOrderEndpoint:
    def test_happy_path(self) -> None:
        entry = _mock_result()
        client = _make_client(composite=entry)

        r = client.post(
            "/order/place",
            json={
                "symbol": "BTC/USDT",
                "side": "BUY",
                "entry_amount": "0.1",
                "sl_price": "59000",
                "tp_price": "61000",
            },
        )

        assert r.status_code == 200
        body = r.json()
        assert body["succeeded"] is True
        assert body["entry_order"]["id"] == "mock-entry-1"
        assert body["emergency_order"] is None

    def test_minimal_order_no_sl_tp(self) -> None:
        entry = _mock_result()
        client = _make_client(composite=entry)

        r = client.post(
            "/order/place",
            json={
                "symbol": "BTC/USDT",
                "side": "BUY",
                "entry_amount": "0.1",
            },
        )

        assert r.status_code == 200
        assert r.json()["succeeded"] is True

    def test_sl_failure_triggers_emergency_in_response(self) -> None:
        entry = _mock_result()
        emergency = _mock_result(oid="emergency-1", side=OrderSide.SELL)
        client = _make_client(
            composite=SlPlacementError("SL retries exhausted", entry_order=entry),
            emergency=emergency,
        )

        r = client.post(
            "/order/place",
            json={
                "symbol": "BTC/USDT",
                "side": "BUY",
                "entry_amount": "0.1",
                "sl_price": "59000",
            },
        )

        assert r.status_code == 200
        body = r.json()
        assert body["succeeded"] is False
        assert body["emergency_order"] is not None
        assert body["emergency_order"]["id"] == "emergency-1"

    def test_entry_order_failure_returns_422(self) -> None:
        client = _make_client(
            composite=ExchangeOrderClientError("insufficient margin"),
        )

        r = client.post(
            "/order/place",
            json={
                "symbol": "BTC/USDT",
                "side": "BUY",
                "entry_amount": "0.1",
            },
        )

        assert r.status_code == 422
        assert "entry_order_failed" in r.json()["detail"]

    def test_both_fail_returns_422(self) -> None:
        entry = _mock_result()
        client = _make_client(
            composite=SlPlacementError("SL retries exhausted", entry_order=entry),
            emergency=ExchangeOrderClientError("exchange offline"),
        )

        r = client.post(
            "/order/place",
            json={
                "symbol": "BTC/USDT",
                "side": "BUY",
                "entry_amount": "0.1",
            },
        )

        assert r.status_code == 422
        assert "sl_placement_failed_and_emergency_failed" in r.json()["detail"]
