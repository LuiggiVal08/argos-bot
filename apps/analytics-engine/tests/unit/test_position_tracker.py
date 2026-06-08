"""Tests para PositionTracker entity."""
from decimal import Decimal

import pytest

from app.domain.entities.position_tracker import (
    PositionTracker, TrackResult, TrackerVerdict,
)
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.order import OrderSide


class TestPositionTracker:
    def test_hold_buy(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        result = PositionTracker.check(pos, Decimal("61000"))
        assert result.verdict == TrackerVerdict.HOLD
        assert result.pnl == Decimal("10000")

    def test_sl_hit_buy(self):
        pos = LivePosition(
            position_id="p2", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        result = PositionTracker.check(pos, Decimal("57000"))
        assert result.verdict == TrackerVerdict.SL_HIT
        assert result.pnl == Decimal("-30000")

    def test_tp_hit_buy(self):
        pos = LivePosition(
            position_id="p3", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        result = PositionTracker.check(pos, Decimal("66000"))
        assert result.verdict == TrackerVerdict.TP_HIT
        assert result.pnl == Decimal("60000")

    def test_sl_hit_sell(self):
        pos = LivePosition(
            position_id="p4", symbol="ETH/USDT", side=OrderSide.SELL,
            units=Decimal("5"), entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            sl_price=Decimal("3200"), tp_price=Decimal("2700"),
        )
        result = PositionTracker.check(pos, Decimal("3300"))
        assert result.verdict == TrackerVerdict.SL_HIT
        assert result.pnl == Decimal("-1500")

    def test_tp_hit_sell(self):
        pos = LivePosition(
            position_id="p5", symbol="ETH/USDT", side=OrderSide.SELL,
            units=Decimal("5"), entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            sl_price=Decimal("3200"), tp_price=Decimal("2700"),
        )
        result = PositionTracker.check(pos, Decimal("2600"))
        assert result.verdict == TrackerVerdict.TP_HIT
        assert result.pnl == Decimal("2000")

    def test_no_sl_no_tp(self):
        pos = LivePosition(
            position_id="p6", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
        )
        result = PositionTracker.check(pos, Decimal("100000"))
        assert result.verdict == TrackerVerdict.HOLD

    def test_hold_at_entry_price(self):
        pos = LivePosition(
            position_id="p7", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
        )
        result = PositionTracker.check(pos, Decimal("60000"))
        assert result.verdict == TrackerVerdict.HOLD
        assert result.pnl == Decimal("0")

    def test_track_result_frozen(self):
        pos = LivePosition(
            position_id="p8", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
        )
        result = PositionTracker.check(pos, Decimal("61000"))
        with pytest.raises(AttributeError):
            result.verdict = "INVALID"  # type: ignore
