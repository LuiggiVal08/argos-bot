from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    n_samples: int
    n_features: int
    window_shape: tuple[int, int]
    class_counts: dict[str, int]
    feature_names: tuple[str, ...]
    scaler_method: str
    lookback: int
    symbols: tuple[str, ...]

    def is_balanced(self, tolerance: float = 0.3) -> bool:
        total = sum(self.class_counts.values())
        if total == 0:
            return False
        max_ratio = max(v / total for v in self.class_counts.values())
        return max_ratio < 0.5 + tolerance


class DatasetValidator:
    MIN_SAMPLES = 100
    MIN_FEATURES = 5
    MAX_CLASS_IMBALANCE = 0.9

    def validate(self, metadata: DatasetMetadata) -> list[str]:
        errors: list[str] = []
        if metadata.n_samples < self.MIN_SAMPLES:
            errors.append(
                f"too few samples: {metadata.n_samples} < {self.MIN_SAMPLES}"
            )
        if metadata.n_features < self.MIN_FEATURES:
            errors.append(
                f"too few features: {metadata.n_features} < {self.MIN_FEATURES}"
            )
        total = sum(metadata.class_counts.values())
        if total > 0:
            max_ratio = max(v / total for v in metadata.class_counts.values())
            if max_ratio > self.MAX_CLASS_IMBALANCE:
                errors.append(f"class imbalance too high: {max_ratio:.2f}")
        return errors

    def is_valid(self, metadata: DatasetMetadata) -> bool:
        return len(self.validate(metadata)) == 0
