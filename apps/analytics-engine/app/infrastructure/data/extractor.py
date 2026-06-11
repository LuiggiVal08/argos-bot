"""Historical kline extractor with pagination, checkpoint, and rate-limit respct.

Downloads raw OHLCV from Binance (or any CCXT exchange) in batches of 1000
candles, persists incrementally to Parquet, and saves a JSON checkpoint so
the download can be resumed if interrupted.

Usage (via cli.py):
    python -m app.infrastructure.data.cli --symbol BTC/USDT --timeframe 5m \\
        --start 2022-01-01
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import ccxt.async_support as ccxt
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from .schema import RawKline

log = structlog.get_logger()

DEFAULT_DATA_DIR = Path("data/datasets")
DEFAULT_CHECKPOINT_DIR = Path("data/checkpoints")
CCXT_LIMIT = 1000  # max candles per fetch_ohlcv call
BATCH_SLEEP_SEC = 0.3  # pause between batches to avoid rate limits


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _checkpoint_path(
    symbol: str, timeframe: str, checkpoint_dir: Path,
) -> Path:
    safe_sym = symbol.replace("/", "_").lower()
    return checkpoint_dir / f"checkpoint_{safe_sym}_{timeframe}.json"


def _raw_parquet_path(
    symbol: str, timeframe: str, data_dir: Path,
) -> Path:
    safe_sym = symbol.replace("/", "_").lower()
    return data_dir / f"raw_{safe_sym}_{timeframe}.parquet"


def _estimate_batches(start_ms: int, end_ms: int, tf_minutes: int) -> int:
    total_minutes = (end_ms - start_ms) / 60_000
    total_candles = total_minutes / tf_minutes
    return max(1, int(total_candles // CCXT_LIMIT) + 1)


def _parse_tf_minutes(timeframe: str) -> int:
    """Convert CCXT timeframe string to minutes.

    Supports: 1m, 5m, 15m, 30m, 1h, 4h, 1d.
    """
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == "m":
        return value
    elif unit == "h":
        return value * 60
    elif unit == "d":
        return value * 1440
    else:
        raise ValueError(f"unsupported timeframe: {timeframe}")


def _to_ms(dt_str: str) -> int:
    """Parse ISO date string to milliseconds since epoch."""
    return int(datetime.fromisoformat(dt_str).timestamp() * 1000)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _serialize_timestamp(obj: Any) -> str:
    """JSON serializer for datetime objects in checkpoint."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    """Load checkpoint JSON. Returns None if file doesn't exist or is corrupt."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("checkpoint_corrupt", path=str(path), error=str(e))
        return None


def _save_checkpoint(path: Path, data: dict[str, Any]) -> None:
    """Atomically write checkpoint via temp + rename."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, default=_serialize_timestamp)
    os.replace(tmp, path)


def _append_to_parquet(
    table: pa.Table,
    parquet_path: Path,
    schema: pa.Schema,
) -> None:
    """Append a table to an existing Parquet file, or create it."""
    if parquet_path.exists():
        existing = pq.read_table(parquet_path)
        combined = pa.concat_tables([existing, table])
        pq.write_table(combined, parquet_path, schema=schema)
    else:
        pq.write_table(table, parquet_path, schema=schema)


async def download_raw_ohlcv(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    start: str,
    end: str | None = None,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    checkpoint_dir: str | Path = DEFAULT_CHECKPOINT_DIR,
    resume: bool = False,
) -> dict[str, Any]:
    """Download raw OHLCV data and persist to Parquet with checkpoint.

    Args:
        exchange: Initialized CCXT async exchange instance.
        symbol: Trading pair, e.g. "BTC/USDT".
        timeframe: Candle timeframe, e.g. "5m".
        start: ISO start date, e.g. "2022-01-01".
        end: ISO end date (defaults to now).
        data_dir: Output directory for Parquet files.
        checkpoint_dir: Directory for checkpoint JSON files.
        resume: If True, resume from checkpoint instead of start.

    Returns:
        Dict with summary: total_candles, batches, elapsed_sec, etc.

    Raises:
        RuntimeError: If the exchange is not initialized or market not found.
    """
    _ensure_dir(data_dir)
    _ensure_dir(checkpoint_dir)

    end = end or datetime.now().strftime("%Y-%m-%d")
    end_ms = _to_ms(end)
    start_ms = _to_ms(start)
    tf_min = _parse_tf_minutes(timeframe)

    safe_sym = symbol.replace("/", "_").lower()
    checkpoint_path = _checkpoint_path(symbol, timeframe, Path(checkpoint_dir))
    parquet_path = _raw_parquet_path(symbol, timeframe, Path(data_dir))
    current_since = start_ms

    # Resume logic
    if resume:
        cp = _load_checkpoint(checkpoint_path)
        if cp is not None and cp.get("status") == "in_progress":
            current_since = cp.get("last_timestamp", start_ms)
            log.info(
                "resuming_from_checkpoint",
                symbol=symbol,
                since=current_since,
                total_so_far=cp.get("total_candles", 0),
            )
        else:
            log.info("no_valid_checkpoint_for_resume, starting_fresh")
    else:
        _save_checkpoint(
            checkpoint_path,
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "status": "in_progress",
                "last_timestamp": start_ms,
                "total_candles": 0,
                "start": start,
                "end": end,
            },
        )

    # Ensure market is loaded
    try:
        await exchange.load_markets()
    except Exception as e:
        raise RuntimeError(f"failed_to_load_markets: {e}") from e

    if symbol not in exchange.markets:
        raise RuntimeError(
            f"symbol {symbol} not found in exchange markets. "
            f"Available: {list(exchange.markets.keys())[:10]}..."
        )

    # Estimate total batches for progress
    total_batches = _estimate_batches(start_ms, end_ms, tf_min)
    log.info(
        "download_started",
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        estimated_batches=total_batches,
    )

    batch_count = 0
    total_candles = 0
    start_wall = time.monotonic()
    errors: list[str] = []

    # Load existing candles from prior partial run
    if resume and parquet_path.exists():
        try:
            existing = pq.read_table(parquet_path)
            total_candles = existing.num_rows
        except Exception:
            pass

    while current_since < end_ms:
        try:
            raw_candles = await exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=current_since,
                limit=CCXT_LIMIT,
            )
        except Exception as e:
            err_msg = f"fetch_ohlcv_failed at {current_since}: {e}"
            log.warning("batch_error", error=err_msg)
            errors.append(err_msg)
            # Wait and retry once on network issues
            await exchange.sleep(2000)
            try:
                raw_candles = await exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    since=current_since,
                    limit=CCXT_LIMIT,
                )
            except Exception as e2:
                log.error("batch_retry_failed", error=str(e2))
                errors.append(f"retry_failed: {e2}")
                break

        if not raw_candles:
            log.info("no_more_candles", since=current_since)
            break

        # Convert to RawKline and validate
        rows: list[dict[str, Any]] = []
        last_ts = current_since
        for row in raw_candles:
            try:
                k = RawKline.from_ccxt(row)
                k.validate()
                rows.append({
                    "timestamp": k.timestamp,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                })
                last_ts = k.timestamp
            except ValueError as e:
                log.warning("invalid_kline_skipped", error=str(e), row=row)
                continue

        if not rows:
            current_since = last_ts + 1
            continue

        # Append to Parquet
        table = pa.Table.from_pylist(rows, schema=RawKline.ARROW_SCHEMA)
        _append_to_parquet(table, parquet_path, RawKline.ARROW_SCHEMA)

        batch_count += 1
        total_candles += len(rows)
        current_since = last_ts + 1  # +1ms to avoid duplicate

        # Save checkpoint
        _save_checkpoint(
            checkpoint_path,
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "status": "in_progress",
                "last_timestamp": current_since,
                "total_candles": total_candles,
                "batches": batch_count,
                "start": start,
                "end": end,
            },
        )

        log.info(
            "batch_downloaded",
            batch=batch_count,
            candles=len(rows),
            total=total_candles,
            since=current_since,
        )

        # Rate-limit pause
        await exchange.sleep(int(BATCH_SLEEP_SEC * 1000))

    elapsed = time.monotonic() - start_wall

    # Mark complete
    status = "complete" if current_since >= end_ms else "partial"
    _save_checkpoint(
        checkpoint_path,
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "status": status,
            "last_timestamp": current_since,
            "total_candles": total_candles,
            "batches": batch_count,
            "start": start,
            "end": end,
            "elapsed_sec": round(elapsed, 2),
            "errors": errors,
        },
    )

    summary = {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_candles": total_candles,
        "batches": batch_count,
        "elapsed_sec": round(elapsed, 2),
        "status": status,
        "errors": errors,
        "output": str(parquet_path),
    }
    log.info("download_complete", **summary)
    return summary
