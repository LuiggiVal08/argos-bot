from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...domain.value_objects.model_config import ModelConfig
from ...domain.value_objects.scaler_type import ScalerType
from ..ports.class_balancer import ClassBalancer
from ..ports.data_preprocessor import DataPreprocessor
from ..ports.feature_store import FeatureStore
from ..ports.multi_symbol_consolidator import (
    MultiSymbolConsolidator,
)


class BuildDatasetError(RuntimeError):
    ...


@dataclass(frozen=True)
class BuildDatasetResult:
    dataset_id: str
    n_samples: int
    n_features: int
    window_shape: tuple[int, int]
    class_counts: dict[str, int]
    feature_names: tuple[str, ...]


class BuildDatasetUseCase:
    def __init__(
        self,
        consolidator: MultiSymbolConsolidator,
        preprocessor: DataPreprocessor,
        feature_store: FeatureStore,
        balancer: ClassBalancer | None = None,
    ) -> None:
        self._consolidator = consolidator
        self._preprocessor = preprocessor
        self._store = feature_store
        self._balancer = balancer

    async def execute(
        self,
        symbol_files: dict[str, Path],
        config: ModelConfig | None = None,
        scaler_type: ScalerType = ScalerType.STANDARD,
        use_atr_labeling: bool = True,
    ) -> BuildDatasetResult:
        cfg = config or ModelConfig()
        dataset_id = f"dataset_{_ts()}"

        consolidated = await self._consolidator.consolidate(
            symbol_files, f"data/datasets/{dataset_id}_raw.parquet",
        )

        ohlcv_list = await self._read_parquet(consolidated)

        if not ohlcv_list:
            raise BuildDatasetError("no data after consolidation")

        features_raw = await self._preprocessor.build_features(
            ohlcv_list[0], cfg,
        )

        features_norm, means, stds = await self._preprocessor.normalize(
            features_raw, scaler_type=scaler_type,
        )

        atr_col = self._find_atr_column(cfg.features)
        atr_values: np.ndarray | None = None
        if use_atr_labeling and atr_col is not None:
            atr_idx = cfg.features.index(atr_col)
            atr_values = features_raw[:, atr_idx]

        targets = await self._preprocessor.create_targets(
            ohlcv_list[0], cfg, atr_values=atr_values,
        )

        min_len = min(len(features_norm), len(targets))
        features_norm = features_norm[-min_len:]
        targets = targets[-min_len:]

        windows = await self._preprocessor.create_windows(
            features_norm, cfg.lookback,
        )
        targets_aligned = targets[cfg.lookback - 1:]
        targets_aligned = targets_aligned[: len(windows)]

        if self._balancer is not None:
            windows, targets_aligned = self._balancer.balance(
                windows, targets_aligned,
            )

        await self._store.save(dataset_id, features_raw, cfg.features)

        class_counts = {
            "BUY": int(targets_aligned[:, 0].sum()),
            "SELL": int(targets_aligned[:, 1].sum()),
            "HOLD": int(targets_aligned[:, 2].sum()),
        }

        return BuildDatasetResult(
            dataset_id=dataset_id,
            n_samples=len(windows),
            n_features=features_norm.shape[1],
            window_shape=(cfg.lookback, features_norm.shape[1]),
            class_counts=class_counts,
            feature_names=cfg.features,
        )

    async def _read_parquet(
        self,
        path: str,
    ) -> list[list[dict]]:
        import pyarrow.parquet as pq
        import pandas as pd
        df = pq.read_table(path).to_pandas()
        return [df.to_dict(orient="records")]

    @staticmethod
    def _find_atr_column(features: tuple[str, ...]) -> str | None:
        for name in ("atr", "atr_14"):
            if name in features:
                return name
        return None


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
