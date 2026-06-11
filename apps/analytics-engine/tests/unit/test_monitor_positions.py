"""Tests para MonitorPositionsUseCase."""
from decimal import Decimal

import pytest

from app.application.use_cases.monitor_positions import (
    MonitorPositionsUseCase, MonitorResult,
)
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.order import OrderResult, OrderSide, OrderStatus, OrderType
from app.infrastructure.execution import InMemoryPositionRepository


class _MockExchangeClient:
    async def close_position(self, symbol: str) -> None:
        pass

    async def close_partial(self, symbol: str, amount: Decimal) -> None:
        pass

    async def cancel_all_orders(self) -> int:
        return 0

    async def close_all_positions(self) -> list:
        return []

    async def place_composite_order(self, order) -> OrderResult:
        return OrderResult(
            id="mock", symbol=order.symbol, side=order.side,
            type=OrderType.MARKET, filled_amount=order.entry_amount,
            status=OrderStatus.FILLED,
        )

    async def place_emergency_market(self, symbol, side, amount) -> OrderResult:
        return OrderResult(
            id="mock-em", symbol=symbol, side=side,
            type=OrderType.MARKET, filled_amount=amount,
            status=OrderStatus.FILLED,
        )


class _MockLogger:
    def __init__(self):
        self.executions = []
        self.rejections = []
        self.monitoring = []

    async def log_execution(self, report) -> None:
        self.executions.append(report)

    async def log_rejection(self, signal_id, reason) -> None:
        self.rejections.append((signal_id, reason))

    async def log_monitoring(self, pid, pnl, price) -> None:
        self.monitoring.append((pid, pnl, price))

    async def recent(self, limit=20) -> list:
        return []


class TestMonitorPositionsUseCase:
    @pytest.fixture
    def repo(self):
        return InMemoryPositionRepository()

    async def _price(self, symbol: str) -> Decimal:
        prices = {"BTC/USDT": Decimal("61000"), "ETH/USDT": Decimal("2900")}
        return prices.get(symbol, Decimal("0"))

    async def test_no_positions(self):
        uc = MonitorPositionsUseCase(
            position_repo=InMemoryPositionRepository(),
            exchange_client=_MockExchangeClient(),
            execution_logger=_MockLogger(),
            price_provider=self._price,
        )
        result = await uc.run()
        assert result.closed == 0
        assert result.held == 0

    async def test_holds_position(self, repo):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        await repo.save(pos)
        uc = MonitorPositionsUseCase(
            position_repo=repo,
            exchange_client=_MockExchangeClient(),
            execution_logger=_MockLogger(),
            price_provider=self._price,
        )
        result = await uc.run()
        assert result.closed == 0
        assert result.held == 1

    async def test_close_sl_hit(self, repo):
        pos = LivePosition(
            position_id="p2", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        await repo.save(pos)

        async def _low_price(symbol: str) -> Decimal:
            return Decimal("57000")

        uc = MonitorPositionsUseCase(
            position_repo=repo,
            exchange_client=_MockExchangeClient(),
            execution_logger=_MockLogger(),
            price_provider=_low_price,
        )
        result = await uc.run()
        assert result.closed == 1
        assert result.held == 0
        # Verify position was updated
        closed = await repo.load("p2")
        assert closed is not None
        assert closed.status == "SL_HIT"
        assert closed.realized_pnl is not None

    async def test_close_tp_hit(self, repo):
        pos = LivePosition(
            position_id="p3", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        await repo.save(pos)

        async def _high_price(symbol: str) -> Decimal:
            return Decimal("66000")

        uc = MonitorPositionsUseCase(
            position_repo=repo,
            exchange_client=_MockExchangeClient(),
            execution_logger=_MockLogger(),
            price_provider=_high_price,
        )
        result = await uc.run()
        assert result.closed == 0
        assert result.partial_closes == 1
        assert result.held == 0
        closed = await repo.load("p3")
        assert closed.status == "PARTIALLY_CLOSED"

    async def test_mixed_positions(self, repo):
        await repo.save(LivePosition(
            position_id="p4", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        ))
        await repo.save(LivePosition(
            position_id="p5", symbol="ETH/USDT", side=OrderSide.BUY,
            units=Decimal("5"), entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            sl_price=Decimal("2800"), tp_price=Decimal("3200"),
        ))

        async def _prices(symbol: str) -> Decimal:
            if symbol == "BTC/USDT":
                return Decimal("57000")  # SL hit
            return Decimal("3100")  # HOLD

        uc = MonitorPositionsUseCase(
            position_repo=repo,
            exchange_client=_MockExchangeClient(),
            execution_logger=_MockLogger(),
            price_provider=_prices,
        )
        result = await uc.run()
        assert result.closed == 1
        assert result.held == 1
