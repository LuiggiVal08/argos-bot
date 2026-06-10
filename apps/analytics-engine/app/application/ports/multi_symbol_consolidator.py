from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


class ConsolidationError(RuntimeError):
    ...


@runtime_checkable
class MultiSymbolConsolidator(Protocol):
    async def consolidate(
        self,
        symbol_files: dict[str, Path],
        output_path: str | Path,
    ) -> str:
        ...
