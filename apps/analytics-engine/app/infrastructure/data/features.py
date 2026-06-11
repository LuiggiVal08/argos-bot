"""Feature engineering for historical OHLCV datasets.

Reads a raw Parquet file (OHLCV only), computes technical indicators
vectorially over the entire dataset, and exports a feature-enriched Parquet.

All calculations use pandas + ta-lib (via the `ta` library) to avoid
batch-boundary artifacts.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

log = structlog.get_logger()

# Minimum rows required for the slowest indicator (EMA 50 + warm-up)
MIN_ROWS_FOR_FEATURES = 100

INDICATOR_COLUMNS = [
    "rsi_14",
    "ema_9",
    "ema_21",
    "ema_50",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "bb_width",
    "atr_14",
    "adx_14",
    "obv",
    "volume_sma_20",
    "price_change_pct",
]

DATASET_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
] + INDICATOR_COLUMNS


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, min_periods=period).mean()


def _compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast = _compute_ema(close, fast)
    ema_slow = _compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    macd_signal = _compute_ema(macd_line, signal)
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def _compute_bb(
    close: pd.Series, period: int = 20, std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands: middle, upper, lower."""
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def _compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14,
) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    return atr


def _compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    return obv


def _compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index."""
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)

    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    plus_di = 100 * (
        plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr.replace(0, pd.NA)
    )
    minus_di = 100 * (
        minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr.replace(0, pd.NA)
    )

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
    adx = dx.ewm(alpha=1 / period, min_periods=period).mean()
    return adx


def compute_dataset(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> str:
    """Read raw OHLCV parquet, compute indicators, write enriched parquet.

    Args:
        input_path: Path to raw Parquet file (must have OHLCV columns).
        output_path: Path for the output dataset Parquet. If None,
                     auto-generates replacing 'raw_' prefix with 'dataset_'.

    Returns:
        Path to the generated dataset Parquet file as string.

    Raises:
        FileNotFoundError: If input_path doesn't exist.
        ValueError: If the input has insufficient rows.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")

    if output_path is None:
        fname = input_path.name.replace("raw_", "dataset_", 1)
        output_path = input_path.parent / fname
    output_path = Path(output_path)

    log.info(
        "feature_engineering_started",
        input=str(input_path),
        output=str(output_path),
    )

    df = pq.read_table(input_path).to_pandas()
    log.info("loaded_raw", rows=len(df), columns=list(df.columns))

    if len(df) < MIN_ROWS_FOR_FEATURES:
        raise ValueError(
            f"input has {len(df)} rows, need at least {MIN_ROWS_FOR_FEATURES}"
        )

    # Sort by timestamp ascending (they should already be, but be safe)
    df = df.sort_values("timestamp").reset_index(drop=True)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Compute all indicators
    df["rsi_14"] = _compute_rsi(close)
    df["ema_9"] = _compute_ema(close, 9)
    df["ema_21"] = _compute_ema(close, 21)
    df["ema_50"] = _compute_ema(close, 50)

    macd_line, macd_signal, macd_hist = _compute_macd(close)
    df["macd"] = macd_line
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist

    bb_upper, bb_middle, bb_lower = _compute_bb(close)
    df["bb_upper"] = bb_upper
    df["bb_middle"] = bb_middle
    df["bb_lower"] = bb_lower
    df["bb_width"] = (bb_upper - bb_lower) / bb_middle.replace(0, pd.NA)

    df["atr_14"] = _compute_atr(high, low, close)
    df["adx_14"] = _compute_adx(high, low, close)
    df["obv"] = _compute_obv(close, volume)
    df["volume_sma_20"] = volume.rolling(window=20, min_periods=20).mean()
    df["price_change_pct"] = close.pct_change() * 100.0

    # Ensure column order
    available = [c for c in DATASET_COLUMNS if c in df.columns]
    df = df[available]

    # Write to parquet
    schema = pa.schema([
        pa.field(c, pa.float64(), nullable=True) if c != "timestamp" else pa.field(c, pa.int64(), nullable=False)
        for c in available
    ])
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    pq.write_table(table, output_path)

    log.info(
        "feature_engineering_complete",
        output=str(output_path),
        rows=len(df),
        columns=len(available),
    )

    return str(output_path)
