from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

log = structlog.get_logger()


class ParquetFeatureStore:
    def __init__(self, base_dir: str | Path = "data/features") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        dataset_id: str,
        features: np.ndarray,
        names: tuple[str, ...],
    ) -> str:
        path = self._base / f"{dataset_id}.parquet"
        table = pa.Table.from_arrays(
            [pa.array(features[:, i], type=pa.float64()) for i in range(features.shape[1])],
            names=list(names),
        )
        pq.write_table(table, path)
        log.info("feature_store_saved", dataset_id=dataset_id, path=str(path))
        return str(path)

    async def load(
        self,
        dataset_id: str,
    ) -> tuple[np.ndarray, tuple[str, ...]] | None:
        path = self._base / f"{dataset_id}.parquet"
        if not path.exists():
            return None
        table = pq.read_table(path)
        arr = table.to_pandas().values.astype(np.float64)
        names = tuple(table.column_names)
        return arr, names
