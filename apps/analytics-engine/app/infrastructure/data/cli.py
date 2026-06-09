#!/usr/bin/env python3
"""CLI entry point for the historical data extractor.

Orchestrates two phases:
  1. Download raw OHLCV with checkpoint/resume
  2. (optional) Compute technical features

Usage:
    python -m app.infrastructure.data.cli \\
        --symbol BTC/USDT --timeframe 5m --start 2022-01-01

    python -m app.infrastructure.data.cli \\
        --symbol BTC/USDT --timeframe 5m --start 2022-01-01 --features

    python -m app.infrastructure.data.cli \\
        --symbol BTC/USDT --timeframe 5m --resume
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import structlog

from .extractor import (
    DEFAULT_CHECKPOINT_DIR,
    DEFAULT_DATA_DIR,
    _checkpoint_path,
    _load_checkpoint,
    download_raw_ohlcv,
)
from .features import compute_dataset

log = structlog.get_logger()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ARGOS Historical Data Extractor — download OHLCV + compute features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m app.infrastructure.data.cli --symbol BTC/USDT --timeframe 5m --start 2022-01-01\n"
            "  python -m app.infrastructure.data.cli --symbol BTC/USDT --timeframe 5m --start 2022-01-01 --features\n"
            "  python -m app.infrastructure.data.cli --symbol BTC/USDT --timeframe 5m --resume\n"
        ),
    )

    parser.add_argument(
        "--symbol",
        default="BTC/USDT",
        help="Trading pair (default: BTC/USDT)",
    )
    parser.add_argument(
        "--timeframe",
        default="5m",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        help="Candle timeframe (default: 5m)",
    )
    parser.add_argument(
        "--start",
        default="2022-01-01",
        help="ISO start date, e.g. 2022-01-01 (default: 2022-01-01)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="ISO end date, e.g. 2026-06-09 (default: today)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for Parquet files (default: data/datasets/)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        default=None,
        help="Checkpoint directory (default: data/checkpoints/)",
    )
    parser.add_argument(
        "--features",
        action="store_true",
        help="Compute technical indicators after download (Phase 2)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted download from its checkpoint",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Binance Testnet API key (default: from BINANCE_TESTNET_API_KEY env)",
    )
    parser.add_argument(
        "--api-secret",
        default=None,
        help="Binance Testnet secret (default: from BINANCE_TESTNET_SECRET env)",
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="Use Binance Spot Testnet instead of production",
    )
    parser.add_argument(
        "--only-features",
        default=None,
        metavar="RAW_PARQUET",
        help="Skip download; only compute features from an existing raw Parquet file",
    )

    return parser


async def _run_download(args: argparse.Namespace) -> dict | None:
    """Phase 1: download raw OHLCV."""
    import ccxt.async_support as ccxt

    # Build exchange
    api_key = args.api_key or os.environ.get("BINANCE_TESTNET_API_KEY")
    api_secret = args.api_secret or os.environ.get("BINANCE_TESTNET_SECRET")

    if args.testnet:
        if not api_key or not api_secret:
            log.error(
                "testnet_requires_credentials",
                message="Set BINANCE_TESTNET_API_KEY / SECRET or use --api-key/--api-secret",
            )
            sys.exit(1)
        exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        exchange.set_sandbox_mode(True)
        log.info("using_binance_testnet")
    else:
        api_key = api_key or os.environ.get("EXCHANGE_API_KEY")
        api_secret = api_secret or os.environ.get("EXCHANGE_API_SECRET")
        exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        log.info("using_binance_production")

    data_dir = Path(args.output_dir) if args.output_dir else DEFAULT_DATA_DIR
    checkpoint_dir = Path(args.checkpoint_dir) if args.checkpoint_dir else DEFAULT_CHECKPOINT_DIR

    try:
        summary = await download_raw_ohlcv(
            exchange=exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=args.start,
            end=args.end,
            data_dir=data_dir,
            checkpoint_dir=checkpoint_dir,
            resume=args.resume,
        )
    except Exception as e:
        log.error("download_failed", error=str(e))
        return None
    finally:
        await exchange.close()

    return summary


def _run_features(
    input_path: str,
    output_dir: str | Path | None = None,
) -> str | None:
    """Phase 2: compute features on an existing raw Parquet."""
    input_path = Path(input_path)
    if not input_path.exists():
        log.error("raw_parquet_not_found", path=str(input_path))
        return None

    if output_dir:
        output_path = Path(output_dir) / input_path.name.replace("raw_", "dataset_", 1)
    else:
        output_path = None

    try:
        result = compute_dataset(
            input_path=input_path,
            output_path=output_path,
        )
        return result
    except Exception as e:
        log.error("feature_engineering_failed", error=str(e))
        return None


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── Phase 2 only (--only-features) ──────────────────────────
    if args.only_features:
        output = _run_features(args.only_features, args.output_dir)
        if output:
            print(f"\n✅ Dataset with features: {output}")
        else:
            sys.exit(1)
        return

    # ── Phase 1: download ────────────────────────────────────────
    summary = asyncio.run(_run_download(args))
    if summary is None:
        sys.exit(1)

    total = summary["total_candles"]
    elapsed = summary["elapsed_sec"]
    rate = round(total / elapsed, 0) if elapsed > 0 else 0

    print(
        f"\n{'='*50}"
        f"\n✅ Download complete"
        f"\n   Symbol:     {summary['symbol']}"
        f"\n   Timeframe:  {summary['timeframe']}"
        f"\n   Candles:    {total:,}"
        f"\n   Batches:    {summary['batches']}"
        f"\n   Elapsed:    {elapsed:.1f}s ({rate:.0f} candles/s)"
        f"\n   Status:     {summary['status']}"
        f"\n   Output:     {summary['output']}"
        f"\n   Errors:     {len(summary['errors'])}"
        f"\n{'='*50}"
    )

    if summary["errors"]:
        print("\n⚠️  Errors during download:")
        for e in summary["errors"][:5]:
            print(f"   • {e}")
        if len(summary["errors"]) > 5:
            print(f"   ... and {len(summary['errors']) - 5} more")

    # ── Phase 2: features (if --features) ────────────────────────
    if args.features and summary["total_candles"] > 0:
        raw_path = summary["output"]
        print("\n🧠 Computing technical indicators...")
        output = _run_features(raw_path, args.output_dir)
        if output:
            print(f"✅ Dataset with features: {output}")
        else:
            print("❌ Feature engineering failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
