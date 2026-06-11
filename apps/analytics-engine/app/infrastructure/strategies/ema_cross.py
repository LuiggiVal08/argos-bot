"""Estrategia: EMA Crossover (Trend Following).

Compra cuando EMA-rapida cruza arriba de EMA-lenta.
Vende cuando EMA-rapida cruza abajo de EMA-lenta.
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.entities.backtest_engine import SignalFn


class EmaCrossStrategy:
    """Trend following strategy using EMA crossover.

    Configuracion via BacktestConfig (strategy_id='ema_cross').
    Parametros embebidos: fast_period=9, slow_period=21.
    """

    def __init__(self, fast_period: int = 9, slow_period: int = 21) -> None:
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
            )
        if fast_period < 2:
            raise ValueError(f"fast_period must be >= 2, got {fast_period}")
        self._fast = fast_period
        self._slow = slow_period

    def build(self, config: BacktestConfig) -> SignalFn:
        """Construye SignalFn para EMA crossover."""

        def signal_fn(idx: int, ohlcv: list[dict], _cfg: BacktestConfig) -> tuple[SignalSide, float] | None:
            if idx < self._slow:
                return None

            fast_ema = self._calc_ema(ohlcv, idx, self._fast)
            slow_ema = self._calc_ema(ohlcv, idx, self._slow)
            if fast_ema is None or slow_ema is None:
                return None

            prev_fast = self._calc_ema(ohlcv, idx - 1, self._fast)
            prev_slow = self._calc_ema(ohlcv, idx - 1, self._slow)

            if prev_fast is None or prev_slow is None:
                return None

            # Crossover up: BUY
            if prev_fast <= prev_slow and fast_ema > slow_ema:
                confidence = min(0.5 + abs(float(fast_ema - slow_ema) / float(slow_ema)) * 10, 0.95)
                return (SignalSide.BUY, round(confidence, 4))

            # Crossover down: SELL
            if prev_fast >= prev_slow and fast_ema < slow_ema:
                confidence = min(0.5 + abs(float(fast_ema - slow_ema) / float(slow_ema)) * 10, 0.95)
                return (SignalSide.SELL, round(confidence, 4))

            return None

        return signal_fn

    @staticmethod
    def _calc_ema(ohlcv: list[dict], idx: int, period: int) -> Decimal | None:
        """Calcula EMA simple sobre los ultimos `period` valores."""
        if idx < period - 1:
            return None
        closes = [Decimal(str(ohlcv[j]["close"])) for j in range(idx - period + 1, idx + 1)]
        if not closes:
            return None

        multiplier = Decimal("2") / Decimal(str(period + 1))
        ema = sum(closes) / Decimal(str(period))

        for price in closes[period - 1:]:
            ema = (price - ema) * multiplier + ema

        return ema if period > 1 else closes[-1]
