from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.champion_challenger import (
    ChampionChallenger,
    ModelCandidate,
)


@dataclass(frozen=True)
class ComparisonResult:
    verdict: str
    champion_info: dict | None
    challenger_info: dict | None
    message: str


class CompareChampionChallengerUseCase:
    def __init__(self, comparator: ChampionChallenger) -> None:
        self._comparator = comparator

    async def execute(
        self,
        champion: ModelCandidate,
        challenger: ModelCandidate,
    ) -> ComparisonResult:
        verdict = self._comparator.compare(champion, challenger)
        return ComparisonResult(
            verdict=verdict,
            champion_info=champion.summary(),
            challenger_info=challenger.summary(),
            message=f"comparison verdict: {verdict}",
        )
