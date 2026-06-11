"""Tests for PortfolioManager domain entity (H35)."""
from decimal import Decimal

import pytest

from app.domain.entities.portfolio_manager import (
    PortfolioDecision,
    PortfolioManager,
    PortfolioState,
    PortfolioVerdict,
)
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.order import OrderSide


class TestPortfolioManager:
    def test_approve_empty(self):
        state = PortfolioState(total_balance=Decimal("100000"))
        mgr = PortfolioManager()
        decision = mgr.assess(state)
        assert decision.verdict == PortfolioVerdict.APPROVED

    def test_reject_heat_cap(self):
        state = PortfolioState(
            total_balance=Decimal("94000"),
            peak_balance=Decimal("100000"),
        )
        mgr = PortfolioManager(max_heat_pct=Decimal("0.05"))
        decision = mgr.assess(state)
        assert decision.verdict == PortfolioVerdict.REJECTED_HEAT_CAP

    def test_approve_heat_below_cap(self):
        state = PortfolioState(
            total_balance=Decimal("98000"),
            peak_balance=Decimal("100000"),
        )
        mgr = PortfolioManager(max_heat_pct=Decimal("0.05"))
        decision = mgr.assess(state)
        assert decision.verdict == PortfolioVerdict.APPROVED

    def test_reject_total_exposure(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("60000"),
            positions=[pos],
        )
        mgr = PortfolioManager(max_exposure_pct=Decimal("0.90"))
        decision = mgr.assess(state)
        assert decision.verdict == PortfolioVerdict.REJECTED_TOTAL_EXPOSURE

    def test_reject_symbol_weight(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos],
        )
        mgr = PortfolioManager(max_symbol_weight_pct=Decimal("0.20"))
        decision = mgr.assess(state, symbol="BTC/USDT")
        assert decision.verdict == PortfolioVerdict.REJECTED_SYMBOL_WEIGHT

    def test_reject_correlation(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("0.1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos],
            correlation_matrix={
                "BTC/USDT": {"ETH/USDT": Decimal("0.85")},
            },
        )
        mgr = PortfolioManager(max_correlation=Decimal("0.70"))
        decision = mgr.assess(state, symbol="ETH/USDT")
        assert decision.verdict == PortfolioVerdict.REJECTED_CORRELATION_CAP

    def test_reject_position_limit(self):
        positions = [
            LivePosition(
                position_id=f"p{i}", symbol=f"SYM{i}/USDT",
                side=OrderSide.BUY,
                units=Decimal("0.1"), entry_price=Decimal("100"),
                current_price=Decimal("101"),
            )
            for i in range(11)
        ]
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=positions,
        )
        mgr = PortfolioManager(max_positions=10)
        decision = mgr.assess(state)
        assert decision.verdict == PortfolioVerdict.REJECTED_POSITION_LIMIT

    def test_approve_with_all_criteria_met(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("0.1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos],
            peak_balance=Decimal("100000"),
        )
        mgr = PortfolioManager()
        decision = mgr.assess(state, symbol="ETH/USDT")
        assert decision.verdict == PortfolioVerdict.APPROVED
