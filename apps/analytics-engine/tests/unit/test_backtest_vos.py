"""Tests unitarios para BacktestConfig, BacktestTrade, BacktestMetrics."""
from decimal import Decimal
from datetime import datetime, timezone

import pytest

from app.domain.value_objects.backtest_config import BacktestConfig
from app.domain.value_objects.backtest_trade import BacktestTrade
from app.domain.value_objects.backtest_metrics import BacktestMetrics
from app.domain.value_objects.signal_side import SignalSide


class TestBacktestConfig:
    def test_minimal_creation(self):
        cfg = BacktestConfig(strategy_id="ema_cross", symbol="BTC/USDT")
        assert cfg.strategy_id == "ema_cross"
        assert cfg.symbol == "BTC/USDT"
        assert cfg.timeframe == "1h"
        assert cfg.initial_balance == Decimal("10000")
        assert cfg.risk_pct == Decimal("0.01")
        assert cfg.max_trades == 0

    def test_custom_values(self):
        cfg = BacktestConfig(
            strategy_id="rsi_reversion",
            symbol="ETH/USDT",
            timeframe="4h",
            start="2024-01-01",
            end="2024-06-01",
            initial_balance=Decimal("50000"),
            risk_pct=Decimal("0.02"),
            max_trades=50,
        )
        assert cfg.strategy_id == "rsi_reversion"
        assert cfg.max_trades == 50
        assert cfg.risk_pct == Decimal("0.02")

    def test_negative_balance_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", initial_balance=Decimal("-100"))

    def test_zero_balance_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", initial_balance=Decimal("0"))

    def test_risk_pct_too_high_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", risk_pct=Decimal("0.03"))

    def test_risk_pct_zero_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", risk_pct=Decimal("0"))

    def test_empty_strategy_id_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="", symbol="BTC/USDT")

    def test_empty_symbol_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="")

    def test_negative_max_trades_rejected(self):
        with pytest.raises(ValueError):
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", max_trades=-1)

    def test_immutable(self):
        cfg = BacktestConfig(strategy_id="x", symbol="BTC/USDT")
        with pytest.raises(Exception):
            cfg.strategy_id = "y"  # type: ignore[misc]


class TestBacktestTrade:
    NOW = datetime.now(timezone.utc)

    def test_minimal_creation(self):
        trade = BacktestTrade(
            side=SignalSide.BUY,
            entry_time=self.NOW,
            entry_price=Decimal("50000"),
            exit_time=self.NOW,
            exit_price=Decimal("51000"),
            units=Decimal("1.0"),
            pnl=Decimal("1000"),
            pnl_pct=Decimal("2.0"),
        )
        assert trade.side == SignalSide.BUY
        assert trade.pnl == Decimal("1000")

    def test_negative_units_rejected(self):
        with pytest.raises(ValueError):
            BacktestTrade(
                side=SignalSide.SELL,
                entry_time=self.NOW,
                entry_price=Decimal("50000"),
                exit_time=self.NOW,
                exit_price=Decimal("49000"),
                units=Decimal("-1"),
                pnl=Decimal("1000"),
                pnl_pct=Decimal("2.0"),
            )

    def test_zero_entry_price_rejected(self):
        with pytest.raises(ValueError):
            BacktestTrade(
                side=SignalSide.BUY,
                entry_time=self.NOW,
                entry_price=Decimal("0"),
                exit_time=self.NOW,
                exit_price=Decimal("50000"),
                units=Decimal("1"),
                pnl=Decimal("0"),
                pnl_pct=Decimal("0"),
            )

    def test_zero_exit_price_rejected(self):
        with pytest.raises(ValueError):
            BacktestTrade(
                side=SignalSide.BUY,
                entry_time=self.NOW,
                entry_price=Decimal("50000"),
                exit_time=self.NOW,
                exit_price=Decimal("0"),
                units=Decimal("1"),
                pnl=Decimal("0"),
                pnl_pct=Decimal("0"),
            )

    def test_optional_fields_default(self):
        trade = BacktestTrade(
            side=SignalSide.BUY,
            entry_time=self.NOW,
            entry_price=Decimal("50000"),
            exit_time=self.NOW,
            exit_price=Decimal("51000"),
            units=Decimal("1.0"),
            pnl=Decimal("1000"),
            pnl_pct=Decimal("2.0"),
        )
        assert trade.entry_reason == ""
        assert trade.exit_reason == ""
        assert trade.duration_min == 0


class TestBacktestMetrics:
    def test_minimal_creation(self):
        m = BacktestMetrics(
            sharpe_ratio=1.5,
            max_drawdown_pct=10.0,
            win_rate=0.6,
            total_return_pct=Decimal("15.5"),
            total_trades=100,
        )
        assert m.sharpe_ratio == 1.5
        assert m.win_rate == 0.6
        assert m.profit_factor is None

    def test_custom_creation(self):
        m = BacktestMetrics(
            sharpe_ratio=2.0,
            max_drawdown_pct=5.0,
            win_rate=0.75,
            total_return_pct=Decimal("25.0"),
            total_trades=50,
            winning_trades=38,
            losing_trades=12,
            avg_pnl_usdt=Decimal("50"),
            final_balance=Decimal("12500"),
            volatility_pct=1.2,
            profit_factor=2.5,
        )
        assert m.winning_trades == 38
        assert m.profit_factor == 2.5

    def test_negative_trades_rejected(self):
        with pytest.raises(ValueError):
            BacktestMetrics(
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                win_rate=0.0,
                total_return_pct=Decimal("0"),
                total_trades=-1,
            )

    def test_win_rate_too_high_rejected(self):
        with pytest.raises(ValueError):
            BacktestMetrics(
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                win_rate=1.5,
                total_return_pct=Decimal("0"),
                total_trades=10,
            )

    def test_win_rate_too_low_rejected(self):
        with pytest.raises(ValueError):
            BacktestMetrics(
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                win_rate=-0.1,
                total_return_pct=Decimal("0"),
                total_trades=10,
            )

    def test_zero_trades_is_ok(self):
        m = BacktestMetrics(
            sharpe_ratio=0.0,
            max_drawdown_pct=0.0,
            win_rate=0.0,
            total_return_pct=Decimal("0"),
            total_trades=0,
        )
        assert m.total_trades == 0
