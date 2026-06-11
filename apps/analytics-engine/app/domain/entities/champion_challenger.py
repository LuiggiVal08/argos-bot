from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ComparisonVerdict:
    CHAMPION_WINS = "CHAMPION_WINS"
    CHALLENGER_WINS = "CHALLENGER_WINS"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    version: str
    metrics: dict[str, float]
    description: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "metrics": self.metrics,
            "description": self.description,
        }


class ChampionChallenger:
    MIN_METRICS_FOR_COMPARISON = 2

    def compare(
        self,
        champion: ModelCandidate,
        challenger: ModelCandidate,
    ) -> str:
        champ_metrics = set(champion.metrics.keys())
        chal_metrics = set(challenger.metrics.keys())
        shared = champ_metrics & chal_metrics

        if len(shared) < self.MIN_METRICS_FOR_COMPARISON:
            return ComparisonVerdict.INCONCLUSIVE

        champ_score = 0
        chal_score = 0

        for metric in shared:
            champ_val = champion.metrics[metric]
            chal_val = challenger.metrics[metric]

            higher_is_better = metric not in ("max_drawdown",)
            if higher_is_better:
                if chal_val > champ_val:
                    chal_score += 1
                elif champ_val > chal_val:
                    champ_score += 1
            else:
                if chal_val < champ_val:
                    chal_score += 1
                elif champ_val < chal_val:
                    champ_score += 1

        if chal_score > champ_score:
            return ComparisonVerdict.CHALLENGER_WINS
        if champ_score > chal_score:
            return ComparisonVerdict.CHAMPION_WINS
        return ComparisonVerdict.INCONCLUSIVE
