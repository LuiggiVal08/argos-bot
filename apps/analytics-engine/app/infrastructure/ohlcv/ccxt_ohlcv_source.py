"""Default OHLCV source: fetches candles via ccxt.async_support.

The TaAtrCalculator takes any callable matching
`(symbol, timeframe, limit) -> DataFrame`. This module provides
the default CCXT-backed implementation for LIVE/PAPER modes.
"""
from __future__ import annotations

import ccxt.async_support as ccxt
import pandas as pd


async def ccxt_ohlcv_source(
    exchange: ccxt.Exchange, symbol: str, timeframe: str, limit: int
) -> pd.DataFrame:
    raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    return df
