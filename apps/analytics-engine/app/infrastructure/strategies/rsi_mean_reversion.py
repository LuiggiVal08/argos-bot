"""Estrategia: RSI Mean Reversion.

Compra cuando RSI esta sobrevendido (< 30) y rebota.
Vende cuando RSI esta sobrecomprado (> 70) y cae.
"""

from __future__ import annotations

from decimal import Decimal

from ...domain.value_objects.backtest_config import BacktestConfig
from ...domain.value_objects.signal_side import SignalSide
from ...domain.entities.backtest_engine import SignalFn


class RsiMeanReversionStrategy:
    """Mean reversion strategy using RSI.

    Configuracion via BacktestConfig (strategy_id='rsi_reversion').
    Parametros: period=14, oversold=30, overbought=70.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: int = 30,
        overbought: int = 70,
    ) -> None:
        if period < 2:
            raise ValueError(f"period must be >= 2, got {period}")
        if not 0 < oversold < 50:
            raise ValueError(f"oversold must be in (0, 50), got {oversold}")
        if not 50 < overbought < 100:
            raise ValueError(f"overbought must be in (50, 100), got {overbought}")
        self._period = period
        self._oversold = oversold
        self._overbought = overbought

    def build(self, config: BacktestConfig) -> SignalFn:
        """Construye SignalFn para RSI mean reversion."""

        def signal_fn(idx: int, ohlcv: list[dict], _cfg: BacktestConfig) -> tuple[SignalSide, float] | None:
            if idx < self._period + 1:
                return None

            rsi = self._calc_rsi(ohlcv, idx, self._period)
            if rsi is None:
                return None

            prev_rsi = self._calc_rsi(ohlcv, idx - 1, self._period)
            if prev_rsi is None:
                return None

            # Oversold bounce: BUY
            if prev_rsi <= self._oversold and rsi > self._oversold:
                distance = (rsi - self._oversold) / self._oversold
                confidence = min(0.5 + distance * 2, 0.90)
                return (SignalSide.BUY, round(confidence, 4))

            # Overbought drop: SELL
            if prev_rsi >= self._overbought and rsi < self._overbought:
                distance = (self._overbought - rsi) / (100 - self._overbought)
                confidence = min(0.5 + distance * 2, 0.90)
                return (SignalSide.SELL, round(confidence, 4))

            return None

        return signal_fn

    @staticmethod
    def _calc_rsi(ohlcv: list[dict], idx: int, period: int) -> float | None:
        """Calcula RSI sobre los ultimos `period` closes."""
        if idx < period:
            return None

        closes = [Decimal(str(ohlcv[j]["close"])) for j in range(idx - period, idx + 1)]
        gains = Decimal("0")
        losses = Decimal("0")

        for j in range(1, len(closes)):
            diff = closes[j] - closes[j - 1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)

        avg_gain = gains / Decimal(str(period))
        avg_loss = losses / Decimal(str(period))

        if avg_loss == 0:
            return 100.0

        rs = float(avg_gain / avg_loss)
        return 100.0 - (100.0 / (1.0 + rs))
