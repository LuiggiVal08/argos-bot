from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class WalkForwardVerdict:
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class WindowResult:
    window_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    metrics: dict[str, float]
    passed: bool


@dataclass(frozen=True)
class WalkForwardResult:
    verdict: str
    windows: tuple[WindowResult, ...] = ()
    avg_metrics: dict[str, float] = field(default_factory=dict)
    fail_reason: str = ""

    def passed_windows(self) -> int:
        return sum(1 for w in self.windows if w.passed)

    def total_windows(self) -> int:
        return len(self.windows)


@dataclass(frozen=True)
class WalkForwardConfig:
    n_windows: int = 5
    train_pct: float = 0.7
    val_pct: float = 0.15
    test_pct: float = 0.15
    min_sharpe: float = 0.5
    min_profit_factor: float = 1.1
    max_drawdown: float = 0.15

    def __post_init__(self) -> None:
        total = self.train_pct + self.val_pct + self.test_pct
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"splits must sum to 1.0, got {total}")
        if self.n_windows < 2:
            raise ValueError("n_windows must be >= 2")


class WalkForwardValidator:
    def __init__(self, config: WalkForwardConfig | None = None) -> None:
        self._config = config or WalkForwardConfig()

    @property
    def config(self) -> WalkForwardConfig:
        return self._config

    def compute_windows(self, n_samples: int) -> list[tuple[int, int, int, int]]:
        windows: list[tuple[int, int, int, int]] = []
        cfg = self._config
        window_size = n_samples // cfg.n_windows

        for i in range(cfg.n_windows):
            train_end = int((i + 1) * window_size * cfg.train_pct)
            val_end = train_end + int(window_size * cfg.val_pct)
            test_end = val_end + int(window_size * cfg.test_pct)

            train_start = i * window_size
            test_end_actual = min(test_end, n_samples)

            if test_end_actual - train_start < 10:
                continue

            windows.append((train_start, train_end, val_end, test_end_actual))

        return windows

    def evaluate_metrics(self, metrics: dict[str, float]) -> list[str]:
        errors: list[str] = []
        cfg = self._config
        if metrics.get("sharpe_ratio", 0) < cfg.min_sharpe:
            errors.append(f"sharpe {metrics.get('sharpe_ratio', 0):.2f} < {cfg.min_sharpe}")
        if metrics.get("profit_factor", 0) < cfg.min_profit_factor:
            errors.append(f"profit_factor {metrics.get('profit_factor', 0):.2f} < {cfg.min_profit_factor}")
        if metrics.get("max_drawdown", 1) > cfg.max_drawdown:
            errors.append(f"max_drawdown {metrics.get('max_drawdown', 0):.2f} > {cfg.max_drawdown}")
        return errors
