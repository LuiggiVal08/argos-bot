from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ShadowStatus(Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EVICTED = "EVICTED"


@dataclass
class ShadowDeployment:
    model_id: str
    version: str
    deployed_at: str
    status: ShadowStatus = ShadowStatus.RUNNING
    total_predictions: int = 0
    total_agreements: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    error: str = ""

    def record_prediction(self, champion_decision: str, shadow_decision: str) -> None:
        self.total_predictions += 1
        if champion_decision == shadow_decision:
            self.total_agreements += 1

    def agreement_rate(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.total_agreements / self.total_predictions


class ShadowModelManager:
    MAX_SHADOWS = 3
    MAX_PREDICTIONS_BEFORE_EVICT = 1000

    def __init__(self) -> None:
        self._shadows: dict[str, ShadowDeployment] = {}

    @property
    def active_shadows(self) -> list[ShadowDeployment]:
        return [s for s in self._shadows.values() if s.status == ShadowStatus.RUNNING]

    def deploy(self, model_id: str, version: str) -> ShadowDeployment:
        if len(self.active_shadows) >= self.MAX_SHADOWS:
            raise RuntimeError(f"max {self.MAX_SHADOWS} shadow models already active")

        deployment = ShadowDeployment(
            model_id=model_id,
            version=version,
            deployed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._shadows[model_id] = deployment
        return deployment

    def get(self, model_id: str) -> ShadowDeployment | None:
        return self._shadows.get(model_id)

    def evict(self, model_id: str) -> None:
        dep = self._shadows.get(model_id)
        if dep is not None:
            dep.status = ShadowStatus.EVICTED

    def fail(self, model_id: str, error: str) -> None:
        dep = self._shadows.get(model_id)
        if dep is not None:
            dep.status = ShadowStatus.FAILED
            dep.error = error

    def list_all(self) -> list[ShadowDeployment]:
        return list(self._shadows.values())
