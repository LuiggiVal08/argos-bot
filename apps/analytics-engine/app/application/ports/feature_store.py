from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class FeatureStore(Protocol):
    async def save(
        self,
        dataset_id: str,
        features: np.ndarray,
        names: tuple[str, ...],
    ) -> str:
        ...

    async def load(
        self,
        dataset_id: str,
    ) -> tuple[np.ndarray, tuple[str, ...]] | None:
        ...
