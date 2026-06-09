"""Tests unitarios para SimpleMetricsCalculator."""
from decimal import Decimal
from datetime import datetime, timezone

import pytest

from app.domain.value_objects.backtest_trade import BacktestTrade
from app.domain.value_objects.backtest_metrics import BacktestMetrics
from app.domain.value_objects.signal_side import SignalSide
from app.domain.entities.backtest_engine import EquityPoint
from app.infrastructure.backtest.metrics_calculator import SimpleMetricsCalculator


NOW = datetime.now(timezone.utc)


def _trade(pnl: Decimal) -> BacktestTrade:
    return BacktestTrade(
        side=SignalSide.BUY,
        entry_time=NOW,
        entry_price=Decimal("50000"),
        exit_time=NOW,
        exit_price=Decimal("51000"),
        units=Decimal("1"),
        pnl=pnl,
        pnl_pct=Decimal("2.0"),
    )


def _equity_flat(balance: Decimal, points: int = 100) -> list[EquityPoint]:
    return [(NOW, balance) for _ in range(points)]


def _equity_trend(start: Decimal, end: Decimal, points: int = 100) -> list[EquityPoint]:
    step = (end - start) / points
    return [(NOW, start + Decimal(str(i)) * step) for i in range(points)]


class TestSimpleMetricsCalculator:
    def test_empty_trades(self):
        calc = SimpleMetricsCalculator()
        m = calc.compute([], _equity_flat(Decimal("10000")), Decimal("10000"))
        assert m.total_trades == 0
        assert m.sharpe_ratio == 0.0
        assert m.final_balance == Decimal("10000")

    def test_all_winning_trades(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("100")) for _ in range(10)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("11000")), Decimal("10000"))
        assert m.total_trades == 10
        assert m.winning_trades == 10
        assert m.losing_trades == 0
        assert m.win_rate == 1.0
        assert m.final_balance > Decimal("10000")

    def test_all_losing_trades(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("-100")) for _ in range(10)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("9000")), Decimal("10000"))
        assert m.total_trades == 10
        assert m.winning_trades == 0
        assert m.losing_trades == 10
        assert m.win_rate == 0.0
        assert m.final_balance < Decimal("10000")

    def test_mixed_trades(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("200")) for _ in range(7)] + [_trade(Decimal("-100")) for _ in range(3)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("11100")), Decimal("10000"))
        assert m.total_trades == 10
        assert m.winning_trades == 7
        assert m.losing_trades == 3
        assert 0.6 <= m.win_rate <= 0.8

    def test_sharpe_positive_on_upward_trend(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("50")) for _ in range(20)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("11000"), 200), Decimal("10000"))
        assert m.sharpe_ratio > 0

    def test_sharpe_zero_on_flat(self):
        calc = SimpleMetricsCalculator()
        m = calc.compute([], _equity_flat(Decimal("10000")), Decimal("10000"))
        assert m.sharpe_ratio == 0.0

    def test_max_drawdown_detected(self):
        calc = SimpleMetricsCalculator()
        # Equity that peaks then drops
        equity = _equity_trend(Decimal("10000"), Decimal("12000"), 50)
        equity += _equity_trend(Decimal("12000"), Decimal("10000"), 50)
        m = calc.compute([_trade(Decimal("100")) for _ in range(5)], equity, Decimal("10000"))
        assert m.max_drawdown_pct > 0

    def test_profit_factor_with_only_wins(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("100")) for _ in range(5)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("10500")), Decimal("10000"))
        assert m.profit_factor is None  # No losses, profit factor undefined

    def test_profit_factor_with_mixed(self):
        calc = SimpleMetricsCalculator()
        trades = [_trade(Decimal("500")) for _ in range(5)] + [_trade(Decimal("-100")) for _ in range(3)]
        m = calc.compute(trades, _equity_trend(Decimal("10000"), Decimal("12200")), Decimal("10000"))
        assert m.profit_factor is not None
        assert m.profit_factor > 1.0  # More wins than losses
