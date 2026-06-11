from __future__ import annotations

from typing import Protocol


class FeatureImportanceCalculator(Protocol):
    async def compute(
        self,
        feature_names: list[str],
        model_weights: bytes | None = None,
        X_sample: list[list[float]] | None = None,
    ) -> dict[str, float]:
        ...
