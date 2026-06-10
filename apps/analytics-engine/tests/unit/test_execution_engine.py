"""Tests para ExecutionEngine (Signal → Risk → Portfolio → Execution)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.use_cases.execution_engine import (
    ExecutionEngine,
    ExecutionEngineError,
    ExecutionResult,
)
from app.domain.entities.portfolio_manager import (
    PortfolioManager,
    PortfolioVerdict,
)
from app.domain.entities.position_manager import PositionManager
from app.domain.entities.risk_engine import (
    RiskEngine,
    RiskVerdict,
)
from app.domain.entities.signal_validator import SignalValidator
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.execution_signal import ExecutionSignal
from app.domain.value_objects.order import OrderResult, OrderStatus, OrderType, OrderSide
from app.domain.value_objects.signal_side import SignalSide
from app.infrastructure.execution.in_memory_position_repo import InMemoryPositionRepository


class _MockBalanceProvider:
    def __init__(self, balance: Decimal = Decimal("10000")):
        self._balance = balance

    async def get_free_balance(self, symbol: str) -> Decimal:
        return self._balance


class _MockAtrCalculator:
    def __init__(self, atr: Decimal = Decimal("500")):
        self._atr = Atr(atr)

    async def get_atr(self, symbol: str, timeframe: str = "1m", window: int = 14) -> Atr:
        return self._atr


class _MockExchangeClient:
    def __init__(self, fail: bool = False):
        self._fail = fail
        self.last_order = None

    async def place_composite_order(self, order) -> OrderResult:
        if self._fail:
            raise RuntimeError("exchange unreachable")
        self.last_order = order
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

    async def log_execution(self, report) -> None:
        self.executions.append(report)

    async def log_rejection(self, signal_id: str, reason: str) -> None:
        self.rejections.append((signal_id, reason))

    async def log_monitoring(self, pid, pnl, price) -> None:
        pass

    async def recent(self, limit=20) -> list:
        return []


async def _not_halted() -> bool:
    return False


async def _halted() -> bool:
    return True


class TestExecutionEngine:
    @pytest.fixture
    def engine(self):
        return ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )

    def _buy_signal(self, **kwargs) -> ExecutionSignal:
        params = dict(
            side=SignalSide.BUY,
            confidence=0.85,
            symbol="BTC/USDT",
            price=Decimal("60000"),
        )
        params.update(kwargs)
        return ExecutionSignal(**params)

    async def test_happy_path_buy(self, engine):
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert result.approved
        assert result.report is not None
        assert result.report.status == "FILLED"
        assert result.report.symbol == "BTC/USDT"
        assert result.position is not None
        assert result.position.units > 0
        assert result.risk_verdict == "APPROVED"
        assert result.portfolio_verdict == "APPROVED"

    async def test_happy_path_sell(self, engine):
        sig = self._buy_signal(
            side=SignalSide.SELL,
            symbol="ETH/USDT",
            price=Decimal("3000"),
        )
        result = await engine.execute(sig)
        assert result.approved
        assert result.position is not None
        assert result.position.side == OrderSide.SELL

    async def test_rejected_signal(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.9),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )
        sig = self._buy_signal(confidence=0.5)
        result = await engine.execute(sig)
        assert not result.approved
        assert "rejected" in result.reason

    async def test_circuit_breaker_halted(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_halted,
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert "HALTED" in result.reason

    async def test_risk_engine_rejects_drawdown(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(balance=Decimal("10000")),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
            risk_engine=RiskEngine(max_daily_drawdown_pct=Decimal("0.05")),
            daily_starting_balance=Decimal("20000"),
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert result.risk_verdict == RiskVerdict.REJECTED_DAILY_DRAWDOWN.value
        assert "drawdown" in result.reason.lower()

    async def test_risk_engine_rejects_consecutive_losses(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
            risk_engine=RiskEngine(max_consecutive_losses=3),
            consecutive_losses=5,
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert result.risk_verdict == RiskVerdict.REJECTED_MAX_LOSSES.value

    async def test_risk_engine_rejects_max_positions(self):
        repo = InMemoryPositionRepository()
        from app.domain.value_objects.live_position import LivePosition
        for i in range(5):
            pos = LivePosition(
                position_id=f"p{i}", symbol="BTC/USDT",
                side=OrderSide.BUY,
                units=Decimal("1"), entry_price=Decimal("60000"),
                current_price=Decimal("60000"),
                sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            )
            await repo.save(pos)

        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=repo,
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
            risk_engine=RiskEngine(max_open_positions=5, max_symbol_exposure_pct=Decimal("10")),
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert result.risk_verdict == RiskVerdict.REJECTED_MAX_POSITIONS.value

    async def test_portfolio_manager_rejects_heat(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(balance=Decimal("9000")),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
            portfolio_manager=PortfolioManager(max_heat_pct=Decimal("0.05")),
            peak_balance=Decimal("10000"),
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert result.portfolio_verdict == PortfolioVerdict.REJECTED_HEAT_CAP.value

    async def test_portfolio_manager_rejects_symbol_weight(self):
        repo = InMemoryPositionRepository()
        from app.domain.value_objects.live_position import LivePosition
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT",
            side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        await repo.save(pos)

        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(balance=Decimal("100000")),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=repo,
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
            risk_engine=RiskEngine(
                max_symbol_exposure_pct=Decimal("10"),
                max_total_exposure_pct=Decimal("10"),
            ),
            portfolio_manager=PortfolioManager(
                max_symbol_weight_pct=Decimal("0.10"),
                max_exposure_pct=Decimal("10"),
            ),
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert result.portfolio_verdict == PortfolioVerdict.REJECTED_SYMBOL_WEIGHT.value

    async def test_missing_price_rejected(self, engine):
        sig = self._buy_signal(price=None)
        result = await engine.execute(sig)
        assert not result.approved
        assert "price" in result.reason.lower()

    async def test_order_failure_rejected(self):
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(fail=True),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert not result.approved
        assert "order placement" in result.reason

    async def test_position_persisted(self, engine):
        repo = InMemoryPositionRepository()
        eng = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=repo,
            execution_logger=_MockLogger(),
            is_halted=_not_halted,
        )
        sig = self._buy_signal(symbol="SOL/USDT", price=Decimal("150"))
        result = await eng.execute(sig)
        assert result.position is not None
        loaded = await repo.load(result.position.position_id)
        assert loaded is not None
        assert loaded.symbol == "SOL/USDT"

    async def test_execution_logged(self):
        logger = _MockLogger()
        engine = ExecutionEngine(
            signal_validator=SignalValidator(min_confidence=0.0),
            balance_provider=_MockBalanceProvider(),
            atr_calculator=_MockAtrCalculator(),
            exchange_client=_MockExchangeClient(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=logger,
            is_halted=_not_halted,
        )
        sig = self._buy_signal()
        result = await engine.execute(sig)
        assert result.approved
        assert len(logger.executions) == 1
        assert len(logger.rejections) == 0

    async def test_rejection_logged(self, engine):
        sig = self._buy_signal(price=None)
        result = await engine.execute(sig)
        assert not result.approved
        assert len(engine._logger.rejections) > 0
