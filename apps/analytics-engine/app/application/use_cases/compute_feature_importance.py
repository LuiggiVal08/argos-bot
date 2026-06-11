from __future__ import annotations

from dataclasses import dataclass

from ..ports.feature_importance_calculator import (
    FeatureImportanceCalculator,
)


@dataclass(frozen=True)
class FeatureImportanceResult:
    importance: dict[str, float]
    total_features: int
    top_features: list[tuple[str, float]]


class ComputeFeatureImportanceUseCase:
    def __init__(self, calculator: FeatureImportanceCalculator) -> None:
        self._calculator = calculator

    async def execute(
        self,
        feature_names: list[str],
        model_weights: bytes | None = None,
        X_sample: list[list[float]] | None = None,
    ) -> FeatureImportanceResult:
        importance = await self._calculator.compute(
            feature_names=feature_names,
            model_weights=model_weights,
            X_sample=X_sample,
        )
        sorted_features = sorted(
            importance.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return FeatureImportanceResult(
            importance=importance,
            total_features=len(importance),
            top_features=sorted_features[:10],
        )
