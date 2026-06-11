from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScalingMethod(Enum):
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"


@dataclass(frozen=True)
class ScalingParams:
    method: ScalingMethod
    means: tuple[float, ...] | None = None
    stds: tuple[float, ...] | None = None

    def is_fitted(self) -> bool:
        return self.means is not None and self.stds is not None


class Normalizer:
    def __init__(self, params: ScalingParams | None = None) -> None:
        self._params = params or ScalingParams(method=ScalingMethod.STANDARD)

    @property
    def params(self) -> ScalingParams:
        return self._params

    def get_method_name(self) -> str:
        return self._params.method.value

    def requires_fit(self) -> bool:
        return not self._params.is_fitted()
