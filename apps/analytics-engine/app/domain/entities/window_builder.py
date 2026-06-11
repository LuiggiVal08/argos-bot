from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowConfig:
    lookback: int = 60
    stride: int = 1
    min_samples: int = 100

    def __post_init__(self) -> None:
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")
        if self.stride < 1:
            raise ValueError("stride must be >= 1")


class WindowBuilder:
    def __init__(self, config: WindowConfig | None = None) -> None:
        self._config = config or WindowConfig()

    @property
    def config(self) -> WindowConfig:
        return self._config

    def validate_length(self, n_samples: int) -> bool:
        min_required = self._config.lookback + 1
        return n_samples >= min_required

    def compute_num_windows(self, n_samples: int) -> int:
        if n_samples < self._config.lookback + 1:
            return 0
        return (n_samples - self._config.lookback) // self._config.stride + 1

    def get_window_indices(
        self,
        n_samples: int,
    ) -> list[tuple[int, int]]:
        if not self.validate_length(n_samples):
            return []
        indices: list[tuple[int, int]] = []
        for start in range(0, n_samples - self._config.lookback, self._config.stride):
            indices.append((start, start + self._config.lookback))
        return indices
