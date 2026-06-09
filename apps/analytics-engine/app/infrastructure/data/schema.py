"""Schema definitions for raw and feature-engineered kline datasets.

RawKline: OHLCV puro como viene de CCXT.
DatasetKline: OHLCV + indicadores técnicos vectoriales (post-procesado).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import pyarrow as pa


@dataclass(frozen=True)
class RawKline:
    """Una vela OHLCV cruda, sin features.

    Corresponde 1:1 con el array que devuelve ccxt.fetch_ohlcv:
      [timestamp_ms, open, high, low, close, volume]
    """
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    ARROW_SCHEMA: ClassVar[pa.Schema] = pa.schema([
        pa.field("timestamp", pa.int64(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.float64(), nullable=False),
    ])

    @classmethod
    def from_ccxt(cls, row: list) -> RawKline:
        """Construye desde el array positional de CCXT.

        CCXT devuelve: [timestamp_ms, open, high, low, close, volume]
        """
        if len(row) < 6:
            raise ValueError(
                f"CCXT row must have at least 6 elements, got {len(row)}: {row}"
            )
        ts = int(row[0])
        # Some CCXT responses return string decimals; cast to float.
        return cls(
            timestamp=ts,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )

    def validate(self) -> None:
        """Validates invariants for a single kline.

        Raises ValueError if any field is out of bounds.
        """
        if self.timestamp <= 0:
            raise ValueError(f"timestamp must be > 0, got {self.timestamp}")
        if self.open <= 0:
            raise ValueError(f"open must be > 0, got {self.open}")
        if self.high <= 0:
            raise ValueError(f"high must be > 0, got {self.high}")
        if self.low <= 0:
            raise ValueError(f"low must be > 0, got {self.low}")
        if self.close <= 0:
            raise ValueError(f"close must be > 0, got {self.close}")
        if self.volume < 0:
            raise ValueError(f"volume must be >= 0, got {self.volume}")
        if self.high < self.low:
            raise ValueError(
                f"high ({self.high}) < low ({self.low})"
            )


@dataclass(frozen=True)
class DatasetKline:
    """Vela OHLCV con indicadores técnicos (post-feature engineering).

    Los campos opcionales son None cuando el indicador no pudo
    calcularse (warm-up period al inicio del dataset).
    """
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Technical indicators
    rsi_14: float | None = None
    ema_9: float | None = None
    ema_21: float | None = None
    ema_50: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    atr_14: float | None = None
    obv: float | None = None
    volume_sma_20: float | None = None
    price_change_pct: float | None = None

    ARROW_SCHEMA: ClassVar[pa.Schema] = pa.schema([
        pa.field("timestamp", pa.int64(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.float64(), nullable=False),
        pa.field("rsi_14", pa.float64(), nullable=True),
        pa.field("ema_9", pa.float64(), nullable=True),
        pa.field("ema_21", pa.float64(), nullable=True),
        pa.field("ema_50", pa.float64(), nullable=True),
        pa.field("macd", pa.float64(), nullable=True),
        pa.field("macd_signal", pa.float64(), nullable=True),
        pa.field("macd_hist", pa.float64(), nullable=True),
        pa.field("bb_upper", pa.float64(), nullable=True),
        pa.field("bb_middle", pa.float64(), nullable=True),
        pa.field("bb_lower", pa.float64(), nullable=True),
        pa.field("atr_14", pa.float64(), nullable=True),
        pa.field("obv", pa.float64(), nullable=True),
        pa.field("volume_sma_20", pa.float64(), nullable=True),
        pa.field("price_change_pct", pa.float64(), nullable=True),
    ])
