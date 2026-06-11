from __future__ import annotations

from enum import Enum


class ScalerType(Enum):
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"
