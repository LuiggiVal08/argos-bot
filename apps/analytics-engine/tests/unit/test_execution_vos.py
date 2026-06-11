"""Tests para ExecutionSignal, LivePosition, ExecutionReport VOs."""
from decimal import Decimal
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.value_objects.execution_signal import ExecutionSignal
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.execution_report import ExecutionReport
from app.domain.value_objects.order import OrderSide
from app.domain.value_objects.signal_side import SignalSide


class TestExecutionSignal:
    def test_minimal_creation(self):
        sig = ExecutionSignal(side=SignalSide.BUY, confidence=0.85, symbol="BTC/USDT")
        assert sig.side == SignalSide.BUY
        assert sig.confidence == 0.85
        assert sig.symbol == "BTC/USDT"
        assert len(sig.signal_id) == 12

    def test_rejects_hold(self):
        with pytest.raises(ValueError, match="must not be HOLD"):
            ExecutionSignal(side=SignalSide.HOLD, confidence=0.5, symbol="BTC/USDT")

    def test_rejects_low_confidence(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            ExecutionSignal(side=SignalSide.BUY, confidence=-0.1, symbol="BTC/USDT")

    def test_rejects_high_confidence(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            ExecutionSignal(side=SignalSide.SELL, confidence=1.5, symbol="BTC/USDT")

    def test_rejects_empty_symbol(self):
        with pytest.raises(ValueError, match="symbol must be a non-empty string"):
            ExecutionSignal(side=SignalSide.BUY, confidence=0.8, symbol="")

    def test_with_price(self):
        sig = ExecutionSignal(
            side=SignalSide.BUY, confidence=0.9, symbol="ETH/USDT",
            price=Decimal("3000"), strategy_id="test",
        )
        assert sig.price == Decimal("3000")
        assert sig.strategy_id == "test"


class TestLivePosition:
    def test_minimal_creation(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        assert pos.is_open
        assert pos.status == "OPEN"

    def test_rejects_zero_units(self):
        with pytest.raises(ValueError, match="units must be > 0"):
            LivePosition(
                position_id="p2", symbol="BTC/USDT", side=OrderSide.BUY,
                units=Decimal("0"), entry_price=Decimal("60000"),
                current_price=Decimal("61000"),
            )

    def test_rejects_negative_entry(self):
        with pytest.raises(ValueError, match="entry_price must be > 0"):
            LivePosition(
                position_id="p3", symbol="BTC/USDT", side=OrderSide.BUY,
                units=Decimal("1"), entry_price=Decimal("-1"),
                current_price=Decimal("61000"),
            )

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="status must be"):
            LivePosition(
                position_id="p4", symbol="BTC/USDT", side=OrderSide.BUY,
                units=Decimal("1"), entry_price=Decimal("60000"),
                current_price=Decimal("61000"), status="INVALID",
            )

    def test_pnl_pct_buy(self):
        pos = LivePosition(
            position_id="p5", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("66000"),
        )
        assert pos.pnl_pct == Decimal("0.1")

    def test_pnl_pct_sell(self):
        pos = LivePosition(
            position_id="p6", symbol="ETH/USDT", side=OrderSide.SELL,
            units=Decimal("5"), entry_price=Decimal("3000"),
            current_price=Decimal("2700"),
        )
        assert pos.pnl_pct == Decimal("0.1")

    def test_sl_hit_buy(self):
        pos = LivePosition(
            position_id="p7", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"), sl_price=Decimal("58000"),
        )
        assert pos.is_sl_hit(Decimal("57000"))
        assert not pos.is_sl_hit(Decimal("59000"))

    def test_sl_hit_sell(self):
        pos = LivePosition(
            position_id="p8", symbol="ETH/USDT", side=OrderSide.SELL,
            units=Decimal("1"), entry_price=Decimal("3000"),
            current_price=Decimal("3000"), sl_price=Decimal("3200"),
        )
        assert pos.is_sl_hit(Decimal("3300"))
        assert not pos.is_sl_hit(Decimal("3100"))

    def test_tp_hit_buy(self):
        pos = LivePosition(
            position_id="p9", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"), tp_price=Decimal("65000"),
        )
        assert pos.is_tp_hit(Decimal("66000"))
        assert not pos.is_tp_hit(Decimal("64000"))

    def test_compute_pnl_at_buy(self):
        pos = LivePosition(
            position_id="p10", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
        )
        assert pos.compute_pnl_at(Decimal("65000")) == Decimal("50000")

    def test_compute_pnl_at_sell(self):
        pos = LivePosition(
            position_id="p11", symbol="ETH/USDT", side=OrderSide.SELL,
            units=Decimal("5"), entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
        )
        assert pos.compute_pnl_at(Decimal("2700")) == Decimal("1500")

    def test_no_sl_never_hit(self):
        pos = LivePosition(
            position_id="p12", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
        )
        assert not pos.is_sl_hit(Decimal("1"))

    def test_closed_position(self):
        pos = LivePosition(
            position_id="p13", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"), status="CLOSED",
        )
        assert not pos.is_open


class TestExecutionReport:
    def test_minimal_creation(self):
        report = ExecutionReport(
            report_id="r1", signal_id="s1", symbol="BTC/USDT",
            side=OrderSide.BUY, status="FILLED", filled_qty=Decimal("10"),
        )
        assert report.status == "FILLED"
        assert report.filled_qty == Decimal("10")

    def test_rejects_negative_filled_qty(self):
        with pytest.raises(ValueError, match="filled_qty must be"):
            ExecutionReport(
                report_id="r2", signal_id="s2", symbol="BTC/USDT",
                side=OrderSide.BUY, status="FILLED",
                filled_qty=Decimal("-1"),
            )

    def test_rejects_invalid_status(self):
        with pytest.raises(ValueError, match="invalid status"):
            ExecutionReport(
                report_id="r3", signal_id="s3", symbol="BTC/USDT",
                side=OrderSide.BUY, status="INVALID", filled_qty=Decimal("0"),
            )

    def test_rejects_negative_avg_price(self):
        with pytest.raises(ValueError, match="avg_price must be"):
            ExecutionReport(
                report_id="r4", signal_id="s4", symbol="BTC/USDT",
                side=OrderSide.BUY, status="FILLED", filled_qty=Decimal("10"),
                avg_price=Decimal("-1"),
            )

    def test_with_errors(self):
        report = ExecutionReport(
            report_id="r5", signal_id="s5", symbol="BTC/USDT",
            side=OrderSide.BUY, status="FAILED", filled_qty=Decimal("0"),
            errors=["insufficient balance", "timeout"],
        )
        assert len(report.errors) == 2
