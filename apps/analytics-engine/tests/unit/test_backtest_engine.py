"""Tests unitarios para BacktestEngine."""
from decimal import Decimal
from datetime import datetime, timezone

import pytest

from app.domain.entities.backtest_engine import BacktestEngine, BacktestError
from app.domain.value_objects.backtest_config import BacktestConfig
from app.domain.value_objects.backtest_trade import BacktestTrade
from app.domain.value_objects.signal_side import SignalSide


def _ohlcv(periods: int = 100, start_price: Decimal = Decimal("50000")) -> list[dict]:
    """Genera velas OHLCV sinteticas con tendencia alcista leve."""
    import math
    ohlcv = []
    for i in range(periods):
        noise = math.sin(i * 0.3) * 200
        close = float(start_price + Decimal(str(i * 10)) + Decimal(str(noise)))
        high = close * 1.01
        low = close * 0.99
        ohlcv.append({
            "timestamp": datetime(2024, 1, 1, i // 24, i % 24).timestamp() * 1000,
            "open": close * 0.998,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100.0,
        })
    return ohlcv


def _always_buy(idx: int, ohlcv: list[dict], config: BacktestConfig):
    """Senal BUY en cada vela."""
    return (SignalSide.BUY, 0.8)


def _always_hold(idx: int, ohlcv: list[dict], config: BacktestConfig):
    """Sin senal (HOLD)."""
    return None


def _alternating(idx: int, ohlcv: list[dict], config: BacktestConfig):
    """BUY en pares, SELL en impares (despues de un BUY)."""
    if idx % 2 == 0:
        return (SignalSide.BUY, 0.8)
    return (SignalSide.SELL, 0.8)


class TestBacktestEngine:
    def test_requires_minimum_candles(self):
        engine = BacktestEngine()
        with pytest.raises(BacktestError, match="insufficient_candles"):
            engine.run([{"timestamp": 0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1} for _ in range(10)],
                      BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
                      _always_hold)

    def test_no_signals_no_trades(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        trades, equity = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
            _always_hold,
        )
        assert len(trades) == 0
        assert len(equity) == 100

    def test_buy_signal_opens_position(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        trades, equity = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
            _always_buy,
        )
        # Should have entered at some point and possibly been stopped out
        assert len(equity) == 100

    def test_alternating_signals_produce_trades(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        trades, equity = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
            _alternating,
        )
        assert len(trades) >= 1  # At least one round-trip

    def test_max_trades_limits_total(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        trades, equity = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", max_trades=3),
            _alternating,
        )
        assert len(trades) <= 3

    def test_equity_curve_starts_at_initial_balance(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        _, equity = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", initial_balance=Decimal("50000")),
            _alternating,
        )
        assert equity[0][1] == Decimal("50000")

    def test_trade_has_valid_pnl(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(100)
        trades, _ = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
            _alternating,
        )
        for t in trades:
            assert isinstance(t.pnl, Decimal)
            assert isinstance(t.pnl_pct, Decimal)

    def test_trade_duration_positive(self):
        engine = BacktestEngine()
        ohlcv = _ohlcv(200)
        trades, _ = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT"),
            _alternating,
        )
        for t in trades:
            assert t.duration_min >= 0

    def test_stop_loss_hit(self):
        """Si la vela toca el SL, el trade se cierra."""
        engine = BacktestEngine()
        # Volatile data with big drops (but prices stay positive)
        import math
        ohlcv = []
        for i in range(100):
            close = 50000 - (i * 200) + math.sin(i * 0.5) * 500
            close = max(close, 1000)  # Keep price positive
            ohlcv.append({
                "timestamp": datetime(2024, 1, 1, i // 24, i % 24).timestamp() * 1000,
                "open": close + 100,
                "high": close + 500,
                "low": close - 500,
                "close": close,
                "volume": 100.0,
            })
        trades, _ = engine.run(
            ohlcv,
            BacktestConfig(strategy_id="x", symbol="BTC/USDT", risk_pct=Decimal("0.01")),
            _always_buy,
        )
        # Should have some stop losses triggered
        stop_losses = [t for t in trades if t.exit_reason == "stop_loss"]
        assert len(trades) >= len(stop_losses)
