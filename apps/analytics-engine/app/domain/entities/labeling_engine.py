from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Label(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class LabelingConfig:
    atr_multiplier: float = 1.5
    use_atr: bool = True
    target_return_pct: float | None = None

    def __post_init__(self) -> None:
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive")
        if self.target_return_pct is not None and self.target_return_pct <= 0:
            raise ValueError("target_return_pct must be positive")


class LabelingEngine:
    def __init__(self, config: LabelingConfig | None = None) -> None:
        self._config = config or LabelingConfig()

    @property
    def config(self) -> LabelingConfig:
        return self._config

    def classify(
        self,
        future_return_pct: float,
        atr_pct: float | None = None,
    ) -> Label:
        if atr_pct is not None and self._config.use_atr:
            if atr_pct <= 0:
                return Label.HOLD
            threshold = self._config.atr_multiplier * atr_pct
        elif self._config.target_return_pct is not None:
            threshold = self._config.target_return_pct
        else:
            return Label.HOLD

        if future_return_pct > threshold:
            return Label.BUY
        if future_return_pct < -threshold:
            return Label.SELL
        return Label.HOLD

    def classify_batch(
        self,
        future_returns: list[float],
        atr_values: list[float] | None = None,
    ) -> list[Label]:
        n = len(future_returns)
        use_atr = atr_values is not None and len(atr_values) >= n
        return [
            self.classify(
                future_returns[i],
                atr_values[i] if use_atr else None,
            )
            for i in range(n)
        ]

    def to_onehot(self, label: Label) -> tuple[float, float, float]:
        if label == Label.BUY:
            return (1.0, 0.0, 0.0)
        if label == Label.SELL:
            return (0.0, 1.0, 0.0)
        return (0.0, 0.0, 1.0)
