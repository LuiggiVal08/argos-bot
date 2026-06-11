"""Tests para MockExchangeAdapter."""
from __future__ import annotations

from decimal import Decimal

from app.application.ports.exchange_order_gateway import (
    ExchangeOrderGatewayError,
)
from app.domain.value_objects.order import OrderSide, OrderStatus, OrderType
from app.infrastructure.exchange.mock_exchange_adapter import (
    MockExchangeAdapter,
)


class TestMockExchangeAdapter:
    async def test_place_market_order_returns_filled(self):
        gw = MockExchangeAdapter()
        result = await gw.place_market_order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            amount=Decimal("0.01"),
            sl_price=Decimal("59000"),
            tp_price=Decimal("65000"),
        )
        assert result.status == OrderStatus.FILLED
        assert result.side == OrderSide.BUY
        assert result.filled_amount == Decimal("0.01")
        assert result.avg_price == Decimal("60000")

    async def test_records_order(self):
        gw = MockExchangeAdapter()
        await gw.place_market_order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            amount=Decimal("0.01"),
            sl_price=Decimal("59000"),
            tp_price=Decimal("65000"),
        )
        assert len(gw.placed_orders) == 1
        order = gw.placed_orders[0]
        assert order["symbol"] == "BTC/USDT"
        assert order["side"] == "BUY"
        assert order["amount"] == Decimal("0.01")
        assert order["sl_price"] == 59000.0
        assert order["tp_price"] == 65000.0

    async def test_last_order_property(self):
        gw = MockExchangeAdapter()
        assert gw.last_order is None
        await gw.place_market_order(
            symbol="BTC/USDT", side=OrderSide.BUY, amount=Decimal("0.01")
        )
        assert gw.last_order is not None

    async def test_fail_next_raises(self):
        gw = MockExchangeAdapter()
        gw.fail_next = True
        try:
            await gw.place_market_order(
                symbol="BTC/USDT", side=OrderSide.BUY, amount=Decimal("0.01")
            )
            assert False, "expected exception"
        except ExchangeOrderGatewayError:
            pass
        assert len(gw.placed_orders) == 0

    async def test_reset_clears_state(self):
        gw = MockExchangeAdapter()
        await gw.place_market_order(
            symbol="BTC/USDT", side=OrderSide.BUY, amount=Decimal("0.01")
        )
        gw.fail_next = True
        gw.reset()
        assert len(gw.placed_orders) == 0
        assert gw.fail_next is False

    async def test_no_sl_tp_optional(self):
        gw = MockExchangeAdapter()
        result = await gw.place_market_order(
            symbol="ETH/USDT", side=OrderSide.SELL, amount=Decimal("0.1")
        )
        assert result.status == OrderStatus.FILLED
        assert result.avg_price == Decimal("60000")
