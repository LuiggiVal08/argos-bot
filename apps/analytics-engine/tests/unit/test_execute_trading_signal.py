"""Tests para ExecuteTradingSignalUseCase.

Cubre:
  - HOLD → skips gracefully (no exception)
  - BUY with confidence < threshold → skips
  - BUY with confidence >= threshold → places order with SL/TP
  - ATR unavailable → skips with reason
  - ExchangeOrderGateway failure → skips with reason
  - Position persisted on success
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.use_cases.execute_trading_signal import (
    ExecuteTradingSignalUseCase,
    ExecuteSignalResult,
)
from app.application.ports.atr_calculator import AtrCalculatorError
from app.application.ports.exchange_order_gateway import (
    ExchangeOrderGatewayError,
)
from app.domain.value_objects.atr import Atr
from app.domain.value_objects.order import OrderResult, OrderSide, OrderStatus, OrderType
from app.domain.value_objects.signal_side import SignalSide
from app.domain.value_objects.trading_signal import TradingSignal
from app.infrastructure.execution import InMemoryPositionRepository


class _FixedAtrCalculator:
    def __init__(self, value: Decimal = Decimal("350")):
        self._value = value

    async def get_atr(
        self, symbol: str, timeframe: str = "1m", window: int = 14
    ) -> Atr:
        return Atr(self._value)


class _FailingAtrCalculator:
    async def get_atr(
        self, symbol: str, timeframe: str = "1m", window: int = 14
    ) -> Atr:
        raise AtrCalculatorError("no data")


class _MockGateway:
    def __init__(self):
        self.orders = []
        self.fail = False

    async def place_market_order(
        self, symbol, side, amount, sl_price=None, tp_price=None
    ) -> OrderResult:
        if self.fail:
            raise ExchangeOrderGatewayError("mock failure")
        self.orders.append(dict(
            symbol=symbol, side=side.value, amount=amount,
            sl_price=float(sl_price) if sl_price else None,
            tp_price=float(tp_price) if tp_price else None,
        ))
        return OrderResult(
            id="test-order-1", symbol=symbol, side=side,
            type=OrderType.MARKET, filled_amount=amount,
            avg_price=Decimal("60000"), status=OrderStatus.FILLED,
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


class TestExecuteTradingSignalUseCase:
    """Test the simplified TradingSignal execution use case."""

    @pytest.fixture
    def use_case(self):
        return ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            confidence_threshold=0.55,
            sl_atr_mult=2.0,
            tp_atr_mult=3.5,
        )

    async def test_hold_skips_gracefully(self, use_case):
        sig = TradingSignal(side=SignalSide.HOLD, confidence=0.9)
        result = await use_case.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is True
        assert "HOLD" in result.reason

    async def test_buy_below_threshold_skips(self, use_case):
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.3)
        result = await use_case.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is True
        assert "below threshold" in result.reason

    async def test_buy_at_threshold_places_order(self, use_case):
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.55)
        result = await use_case.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is False
        assert result.report is not None
        assert result.position is not None
        assert result.report.status == "FILLED"
        assert result.position.side == OrderSide.BUY
        assert result.position.units == Decimal("0.01")

    async def test_sl_tp_computed_correctly(self):
        atr_val = Decimal("500")
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(atr_val),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            confidence_threshold=0.55,
            sl_atr_mult=2.0,
            tp_atr_mult=3.5,
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        close = Decimal("60000")
        result = await uc.execute(sig, "BTC/USDT", close, Decimal("0.01"))
        assert result.position is not None
        expected_sl = close - (Decimal("2.0") * atr_val)
        expected_tp = close + (Decimal("3.5") * atr_val)
        assert result.position.sl_price == expected_sl
        assert result.position.tp_price == expected_tp

    async def test_atr_failure_skips(self):
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FailingAtrCalculator(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        result = await uc.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is True
        assert "ATR unavailable" in result.reason

    async def test_gateway_failure_skips(self):
        gw = _MockGateway()
        gw.fail = True
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=gw,
            atr_calculator=_FixedAtrCalculator(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        result = await uc.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is True
        assert "order failed" in result.reason

    async def test_position_persisted_on_success(self):
        repo = InMemoryPositionRepository()
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(),
            position_repo=repo,
            execution_logger=_MockLogger(),
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        result = await uc.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.position is not None
        loaded = await repo.load(result.position.position_id)
        assert loaded is not None
        assert loaded.symbol == "BTC/USDT"

    async def test_execution_logged_on_success(self):
        logger = _MockLogger()
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=logger,
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        result = await uc.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert len(logger.executions) == 1
        assert logger.executions[0].symbol == "BTC/USDT"

    async def test_rejection_logged_on_hold(self):
        logger = _MockLogger()
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(),
            position_repo=InMemoryPositionRepository(),
            execution_logger=logger,
        )
        sig = TradingSignal(side=SignalSide.HOLD, confidence=0.9)
        await uc.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert len(logger.rejections) == 1
        assert "HOLD" in logger.rejections[0][1]

    async def test_sl_clamped_to_minimum(self):
        """SL price should never go below 0.01."""
        atr_val = Decimal("100000")
        uc = ExecuteTradingSignalUseCase(
            exchange_gateway=_MockGateway(),
            atr_calculator=_FixedAtrCalculator(atr_val),
            position_repo=InMemoryPositionRepository(),
            execution_logger=_MockLogger(),
            sl_atr_mult=2.0,
        )
        sig = TradingSignal(side=SignalSide.BUY, confidence=0.85)
        close = Decimal("1000")
        result = await uc.execute(sig, "BTC/USDT", close, Decimal("0.01"))
        assert result.position is not None
        expected_sl = max(close - (Decimal("2.0") * atr_val), Decimal("0.01"))
        assert result.position.sl_price == expected_sl
        assert result.position.sl_price >= Decimal("0.01")

    async def test_non_buy_skips(self, use_case):
        """SELL is not supported by this simplified use case."""
        sig = TradingSignal(side=SignalSide.SELL, confidence=0.9)
        result = await use_case.execute(sig, "BTC/USDT", Decimal("60000"), Decimal("0.01"))
        assert result.skipped is True
        assert "unsupported" in result.reason
