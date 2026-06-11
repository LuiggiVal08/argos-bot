from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from ...application.ports.multi_symbol_consolidator import (
    ConsolidationError,
)

log = structlog.get_logger()

SYMBOL_IDS: dict[str, int] = {
    "BTC/USDT": 0,
    "ETH/USDT": 1,
    "SOL/USDT": 2,
}


class ParquetMultiSymbolConsolidator:
    MIN_ROWS = 100

    async def consolidate(
        self,
        symbol_files: dict[str, Path],
        output_path: str | Path,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        parts: list[pd.DataFrame] = []
        for symbol, filepath in symbol_files.items():
            if not filepath.exists():
                raise ConsolidationError(f"file not found: {filepath}")
            df = pq.read_table(filepath).to_pandas()
            if len(df) < self.MIN_ROWS:
                log.warning("symbol_excluded_insufficient_data",
                            symbol=symbol, rows=len(df))
                continue
            sid = SYMBOL_IDS.get(symbol)
            if sid is None:
                log.warning("symbol_excluded_unknown", symbol=symbol)
                continue
            df["symbol_id"] = sid
            parts.append(df)

        if not parts:
            raise ConsolidationError("no symbols with sufficient data")

        combined = pd.concat(parts, ignore_index=True)
        combined = combined.sort_values(["symbol_id", "timestamp"]).reset_index(drop=True)

        table = pa.Table.from_pandas(combined, preserve_index=False)
        pq.write_table(table, output_path)

        log.info("consolidation_complete",
                 output=str(output_path),
                 symbols=list(symbol_files.keys()),
                 rows=len(combined))

        return str(output_path)
