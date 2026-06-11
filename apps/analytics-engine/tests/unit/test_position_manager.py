"""Tests for PositionManager domain entity (H30)."""
from decimal import Decimal

import pytest

from app.domain.entities.position_manager import (
    PositionAction,
    PositionDecision,
    PositionManager,
)
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.order import OrderSide


class TestPositionManager:
    def test_hold_when_far_from_sl_tp(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            atr_at_entry=Decimal("2000"),
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("61000"))
        assert decision.action == PositionAction.HOLD

    def test_sl_hit_closes(self):
        pos = LivePosition(
            position_id="p2", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("57000"))
        assert decision.action == PositionAction.CLOSE
        assert "stop_loss" in decision.reason

    def test_tp1_hit_partial_close(self):
        pos = LivePosition(
            position_id="p3", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            tp1_pct=Decimal("0.5"),
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("66000"))
        assert decision.action == PositionAction.PARTIAL_CLOSE
        assert decision.close_pct == Decimal("0.5")
        assert decision.tp_level == 1

    def test_tp2_hit_partial_close(self):
        pos = LivePosition(
            position_id="p4", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            tp2_price=Decimal("68000"),
            tp1_pct=Decimal("0.5"), tp2_pct=Decimal("0.25"),
            status="PARTIALLY_CLOSED",
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("69000"))
        assert decision.action == PositionAction.PARTIAL_CLOSE
        assert decision.close_pct == Decimal("0.25")
        assert decision.tp_level == 2

    def test_tp3_hit_full_close(self):
        pos = LivePosition(
            position_id="p5", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            tp2_price=None, tp3_price=Decimal("72000"),
            status="PARTIALLY_CLOSED",
            initial_units=Decimal("20"),
            tp2_pct=Decimal("0"),
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("73000"))
        assert decision.action == PositionAction.CLOSE
        assert "tp3" in decision.reason

    def test_break_even_activation_at_1r(self):
        pos = LivePosition(
            position_id="p6", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            atr_at_entry=Decimal("2000"),
        )
        mgr = PositionManager()
        # At entry + 2000 = exactly 1R (atr = 2000, 1 unit)
        decision = mgr.evaluate(pos, Decimal("62000"))
        assert decision.action == PositionAction.ACTIVATE_BREAK_EVEN
        assert decision.new_sl_price == Decimal("60000")
        assert "break_even" in decision.reason

    def test_trail_activated_at_2r(self):
        pos = LivePosition(
            position_id="p7", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("64000"),
            sl_price=Decimal("60000"), tp_price=Decimal("65000"),
            atr_at_entry=Decimal("2000"),
            break_even_activated=True,
        )
        mgr = PositionManager()
        # At entry + 4000 = exactly 2R (BE already activated at 1R)
        decision = mgr.evaluate(pos, Decimal("64000"), atr=Decimal("2000"))
        assert decision.action == PositionAction.ACTIVATE_TRAIL
        assert decision.new_sl_price is not None
        assert "trail" in decision.reason

    def test_trailing_sl_update(self):
        pos = LivePosition(
            position_id="p8", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("64000"),
            sl_price=Decimal("61000"), tp_price=Decimal("68000"),
            atr_at_entry=Decimal("2000"),
            trail_activated=True,
            trail_offset=Decimal("3000"),
            break_even_activated=True,
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("66000"), atr=Decimal("2000"))
        assert decision.action == PositionAction.UPDATE_SL
        # New SL should be higher: 66000 - 3000 = 63000
        assert decision.new_sl_price is not None
        assert decision.new_sl_price > Decimal("61000")

    def test_break_even_sell_side(self):
        pos = LivePosition(
            position_id="p9", symbol="BTC/USDT", side=OrderSide.SELL,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("62000"), tp_price=Decimal("57000"),
            atr_at_entry=Decimal("2000"),
        )
        mgr = PositionManager()
        # Price dropped 2000 = 1R
        decision = mgr.evaluate(pos, Decimal("58000"))
        assert decision.action == PositionAction.ACTIVATE_BREAK_EVEN
        assert decision.new_sl_price == Decimal("60000")

    def test_closed_position_returns_hold(self):
        pos = LivePosition(
            position_id="p10", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("60000"),
            current_price=Decimal("60000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
            status="CLOSED",
        )
        mgr = PositionManager()
        decision = mgr.evaluate(pos, Decimal("61000"))
        assert decision.action == PositionAction.HOLD
