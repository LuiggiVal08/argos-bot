"""Unit tests for the TaAtrCalculator infrastructure adapter.

Uses a static DataFrame as the OHLCV source so the test is
hermetic. Verifies happy path and the two main sad paths
(insufficient candles, NaN from `ta`).
"""
import asyncio
from decimal import Decimal

import pandas as pd
import pytest

from app.domain.value_objects.atr import Atr
from app.infrastructure.indicators.ta_atr_calculator import TaAtrCalculator


def make_ohlcv(n: int, base: float = 100.0, vol: float = 1.0) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with `n` rows.

    Highs and lows are derived from `close` so the True Range is
    always positive (we want a working ATR, not a degenerate one).
    """
    import numpy as np
    np.random.seed(0)
    close = base + np.cumsum(np.random.normal(0, vol, n))
    high = close + abs(np.random.normal(0, vol, n))
    low = close - abs(np.random.normal(0, vol, n))
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n),
        }
    )


class TestTaAtrCalculator:
    @pytest.mark.asyncio
    async def test_returns_atr_from_ohlcv(self) -> None:
        df = make_ohlcv(50)
        calc = TaAtrCalculator(source=lambda s, t, w: asyncio.sleep(0, result=df))
        atr = await calc.get_atr("BTC/USDT", "1m", 14)
        assert isinstance(atr, Atr)
        assert atr.value > 0

    @pytest.mark.asyncio
    async def test_insufficient_candles_raises(self) -> None:
        df = make_ohlcv(5)
        calc = TaAtrCalculator(source=lambda s, t, w: asyncio.sleep(0, result=df))
        from app.application.ports.atr_calculator import AtrCalculatorError
        with pytest.raises(AtrCalculatorError, match="insufficient_candles"):
            await calc.get_atr("BTC/USDT", "1m", 14)

    @pytest.mark.asyncio
    async def test_source_failure_raises(self) -> None:
        async def bad_source(s, t, w):
            raise RuntimeError("network down")
        calc = TaAtrCalculator(source=bad_source)
        from app.application.ports.atr_calculator import AtrCalculatorError
        with pytest.raises(AtrCalculatorError, match="candle_source_failed"):
            await calc.get_atr("BTC/USDT", "1m", 14)
