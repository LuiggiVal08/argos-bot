from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.model_registry import ModelRegistry
from ...domain.entities.promotion_engine import PromotionEngine
from ...domain.value_objects.model_version import ModelVersion


@dataclass(frozen=True)
class PromotionResult:
    verdict: str
    champion_version: str | None
    message: str


class PromoteModelUseCase:
    def __init__(
        self,
        registry: ModelRegistry,
        promotion_engine: PromotionEngine,
    ) -> None:
        self._registry = registry
        self._promotion_engine = promotion_engine

    async def execute(self, challenger_version: ModelVersion) -> PromotionResult:
        challenger = self._registry.get(challenger_version)
        if challenger is None:
            return PromotionResult(
                verdict="DENIED",
                champion_version=None,
                message=f"version {challenger_version} not found in registry",
            )

        champion = self._registry.champion
        champion_metrics = champion.metrics if champion else None
        challenger_metrics = challenger.metrics

        verdict = self._promotion_engine.evaluate(champion_metrics, challenger_metrics)

        if verdict == "PROMOTE":
            promoted = self._registry.promote(challenger_version)
            return PromotionResult(
                verdict="PROMOTE",
                champion_version=str(promoted.version),
                message=f"promoted {challenger_version} to champion",
            )

        return PromotionResult(
            verdict=verdict,
            champion_version=str(champion.version) if champion else None,
            message=f"challenger {challenger_version} rejected by promotion rules",
        )
