#!/usr/bin/env python3
"""Indicator helper for the opencode `calc_indicator` tool.

Reads OHLCV from a local CSV at ./data/<symbol>_<timeframe>.csv first.
Falls back to CCXT outside LIVE mode. Refuses network fetch in LIVE.
"""
import json
import os
import pathlib
import sys

import pandas as pd
import ta


def main() -> int:
    req = json.loads(sys.argv[1])
    symbol = req["symbol"]
    timeframe = req["timeframe"]
    ind = req["indicator"]
    period = int(req["period"])

    data_path = pathlib.Path(f"./data/{symbol.replace('/', '')}_{timeframe}.csv")
    if data_path.exists():
        df = pd.read_csv(data_path)
    else:
        env = os.environ.get("ENVIRONMENT_MODE", "PAPER_TRADING")
        if env == "LIVE":
            print(
                json.dumps(
                    {
                        "error": (
                            f"no local data for {symbol} {timeframe} and "
                            "LIVE mode forbids network fetch"
                        )
                    }
                )
            )
            return 2
        try:
            import ccxt  # type: ignore
        except Exception as exc:  # pragma: no cover
            print(json.dumps({"error": f"ccxt unavailable: {exc}"}))
            return 3
        ohlcv = ccxt.binance().fetch_ohlcv(symbol, timeframe, limit=500)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])

    if ind == "rsi":
        series = ta.momentum.rsi(df["close"], period)
    elif ind == "ema":
        series = ta.trend.ema_indicator(df["close"], period)
    elif ind == "sma":
        series = ta.trend.sma_indicator(df["close"], period)
    elif ind == "macd":
        series = ta.trend.macd(df["close"])
    elif ind == "bb":
        series = ta.volatility.bollinger_mavg(df["close"], period)
    else:
        print(json.dumps({"error": f"unknown indicator {ind}"}))
        return 2

    clean = series.dropna()
    print(
        json.dumps(
            {
                "indicator": ind,
                "period": period,
                "last": float(clean.iloc[-1]),
                "n": int(clean.shape[0]),
            },
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
