"""Tests para ExecuteSignalUseCase."""
from decimal import Decimal

import pytest

from app.domain.value_objects.atr import Atr

from app.application.use_cases.execute_signal import (
    ExecuteSignalUseCase, ExecuteSignalError,
)
from app.domain.entities.signal_validator import SignalValidator
from app.domain.value_objects.execution_signal import ExecutionSignal
from app.domain.value_objects.order import OrderResult, OrderStatus, OrderType, OrderSide
from app.domain.value_objects.signal_side import SignalSide
from app.infrastructure.execution import InMemoryPositionRepository


class _MockBalanceProvider:
    async def get_free_balance(self, symbol: str) -> Decimal:
        return Decimal("10000")


class _MockAtrCalculator:
    async def get_atr(self, symbol: str, timeframe: str = "1m", window: int = 14) -> Atr:
        return Atr(500)


class _MockExchangeClient:
    async def place_composite_order(self, order) -> OrderResult:
        return OrderResult(
            id="mock-order-1",
            symbol=order.symbol,
            side=order.side,
            type=OrderType.MARKET,
            filled_amount=order.entry_amount,
            avg_price=order.entry_price or Decimal("60000"),
            status=OrderStatus.FILLED,
        )

    async def cancel_all_orders(self) -> int:
        return 0

    async def close_all_positions(self) -> list:
        return []

    async def close_position(self, symbol: str) -> None:
        pass

    async def place_emergency_market(self, symbol: str, side, amount) -> OrderResult:
        return OrderResult(
            id="mock-emergency", symbol=symbol, side=side,
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

    async def log_rejection(self, signal_id: str, reason: str) -> None:
        self.rejections.append((signal_id, reason))

    async def log_monitoring(self, pid, pnl, price) -> None:
        self.monitoring.append((pid, pnl, price))

    async def recent(self, limit=20) -> list:
        return []


class TestExecuteSignalUseCase:
    @pytest.fixture
    def use_case(self):
        return ExecuteSignalUseCase(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )

    async def test_happy_path(self, use_case):
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.85, symbol="BTC/USDT",
            price=Decimal("60000"),
        )
        result = await use_case.execute(sig)
        assert result.report.status == "FILLED"
        assert result.report.symbol == "BTC/USDT"
        assert result.position is not None
        assert result.position.units > 0

    async def test_rejected_signal(self, use_case):
        sv = SignalValidator(min_confidence=0.9)
        uc = ExecuteSignalUseCase(
            signal_validator=sv,
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.5, symbol="BTC/USDT",
            price=Decimal("60000"),
        )
        with pytest.raises(ExecuteSignalError, match="rejected"):
            await uc.execute(sig)

    async def test_circuit_breaker_halted(self):
        async def _halted() -> bool:
            return True
        uc = ExecuteSignalUseCase(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_halted,
        )
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.85, symbol="BTC/USDT",
            price=Decimal("60000"),
        )
        with pytest.raises(ExecuteSignalError, match="HALTED"):
            await uc.execute(sig)

    async def test_position_persisted(self, use_case):
        repo = InMemoryPositionRepository()
        uc = ExecuteSignalUseCase(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=repo,
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )
        sig = ExecutionSignal(
            side=SignalSide.SELL, confidence=0.85, symbol="ETH/USDT",
            price=Decimal("3000"),
        )
        result = await uc.execute(sig)
        loaded = await repo.load(result.position.position_id)
        assert loaded is not None
        assert loaded.symbol == "ETH/USDT"

    async def test_short_position(self, use_case):
        sig = ExecutionSignal(
            side=SignalSide.SELL, confidence=0.85, symbol="BTC/USDT",
            price=Decimal("60000"),
        )
        result = await use_case.execute(sig)
        assert result.report.side == OrderSide.SELL
        assert result.position.side == OrderSide.SELL


async def _not_halted() -> bool:
    return False
