from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


class ImbalanceError(RuntimeError):
    ...


@runtime_checkable
class ClassBalancer(Protocol):
    def balance(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        ...
