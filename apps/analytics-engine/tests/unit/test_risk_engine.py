"""Tests for RiskEngine domain entity (H32)."""
from decimal import Decimal

import pytest

from app.domain.entities.risk_engine import (
    PortfolioState,
    RiskAssessment,
    RiskEngine,
    RiskVerdict,
)
from app.domain.value_objects.live_position import LivePosition
from app.domain.value_objects.order import OrderSide


class TestRiskEngine:
    def test_approve_empty_portfolio(self):
        state = PortfolioState(
            total_balance=Decimal("10000"),
            positions=[],
            consecutive_losses=0,
        )
        engine = RiskEngine()
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.APPROVED

    def test_approve_with_open_positions(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("0.1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
            sl_price=Decimal("58000"), tp_price=Decimal("65000"),
        )
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos],
            consecutive_losses=0,
        )
        engine = RiskEngine()
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.APPROVED

    def test_reject_daily_drawdown(self):
        state = PortfolioState(
            total_balance=Decimal("94000"),
            positions=[],
            consecutive_losses=0,
            daily_starting_balance=Decimal("100000"),
        )
        engine = RiskEngine(max_daily_drawdown_pct=Decimal("0.05"))
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.REJECTED_DAILY_DRAWDOWN

    def test_approve_daily_drawdown_below_threshold(self):
        state = PortfolioState(
            total_balance=Decimal("98000"),
            positions=[],
            consecutive_losses=0,
            daily_starting_balance=Decimal("100000"),
        )
        engine = RiskEngine(max_daily_drawdown_pct=Decimal("0.05"))
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.APPROVED

    def test_reject_consecutive_losses(self):
        state = PortfolioState(
            total_balance=Decimal("10000"),
            positions=[],
            consecutive_losses=3,
        )
        engine = RiskEngine(max_consecutive_losses=3)
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.REJECTED_MAX_LOSSES
        assert assessment.current_losses == 3

    def test_reject_max_positions(self):
        pos1 = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("0.1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        pos2 = LivePosition(
            position_id="p2", symbol="ETH/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("3000"),
            current_price=Decimal("3100"),
        )
        pos3 = LivePosition(
            position_id="p3", symbol="SOL/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("150"),
            current_price=Decimal("155"),
        )
        pos4 = LivePosition(
            position_id="p4", symbol="ADA/USDT", side=OrderSide.BUY,
            units=Decimal("100"), entry_price=Decimal("0.5"),
            current_price=Decimal("0.55"),
        )
        pos5 = LivePosition(
            position_id="p5", symbol="DOT/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("20"),
            current_price=Decimal("21"),
        )
        pos6 = LivePosition(
            position_id="p6", symbol="LINK/USDT", side=OrderSide.BUY,
            units=Decimal("10"), entry_price=Decimal("15"),
            current_price=Decimal("16"),
        )

        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos1, pos2, pos3, pos4, pos5, pos6],
            consecutive_losses=0,
        )
        engine = RiskEngine(max_open_positions=5)
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.REJECTED_MAX_POSITIONS

    def test_reject_symbol_exposure(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("100000"),
            positions=[pos],
            consecutive_losses=0,
        )
        # 1 * 60000 / 100000 = 60% which exceeds 20%
        engine = RiskEngine(max_symbol_exposure_pct=Decimal("0.20"))
        assessment = engine.assess(state, symbol="BTC/USDT")
        assert assessment.verdict == RiskVerdict.REJECTED_SYMBOL_EXPOSURE
        assert assessment.symbol_exposure_pct == Decimal("0.60")

    def test_reject_total_exposure(self):
        pos = LivePosition(
            position_id="p1", symbol="BTC/USDT", side=OrderSide.BUY,
            units=Decimal("1"), entry_price=Decimal("60000"),
            current_price=Decimal("61000"),
        )
        state = PortfolioState(
            total_balance=Decimal("60000"),
            positions=[pos],
            consecutive_losses=0,
        )
        engine = RiskEngine(max_total_exposure_pct=Decimal("0.90"))
        # 1 * 60000 / 60000 = 100% > 90%
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.REJECTED_TOTAL_EXPOSURE

    def test_custom_config(self):
        state = PortfolioState(
            total_balance=Decimal("10000"),
            positions=[],
            consecutive_losses=0,
        )
        engine = RiskEngine(
            max_consecutive_losses=5,
            max_open_positions=10,
            max_symbol_exposure_pct=Decimal("0.50"),
            max_total_exposure_pct=Decimal("0.95"),
        )
        assessment = engine.assess(state)
        assert assessment.verdict == RiskVerdict.APPROVED
