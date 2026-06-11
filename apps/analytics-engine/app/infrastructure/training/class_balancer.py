from __future__ import annotations

import numpy as np
import structlog

from ...application.ports.class_balancer import ImbalanceError

log = structlog.get_logger()

MAX_IMBALANCE_RATIO = 10.0


class WeightedLossBalancer:
    def balance(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        counts = y.sum(axis=0)
        max_count = counts.max()
        min_count = counts.min()
        if min_count == 0 or max_count / min_count > MAX_IMBALANCE_RATIO:
            raise ImbalanceError(
                f"class imbalance too high: {counts}"
            )
        return x, y


class OversamplingBalancer:
    def balance(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        counts = y.sum(axis=0).astype(int)
        max_count = counts.max()
        if max_count == 0:
            return x, y

        x_list = [x]
        y_list = [y]
        for i, cnt in enumerate(counts):
            if cnt == 0 or cnt >= max_count:
                continue
            mask = y[:, i] == 1.0
            indices = np.where(mask)[0]
            n_needed = max_count - cnt
            reps = n_needed // cnt + 1
            oversampled_x = np.tile(x[indices], (reps, 1, 1))[:n_needed]
            oversampled_y = np.tile(y[indices], (reps, 1))[:n_needed]
            x_list.append(oversampled_x)
            y_list.append(oversampled_y)

        x_out = np.concatenate(x_list, axis=0)
        y_out = np.concatenate(y_list, axis=0)

        shuffle = np.random.permutation(len(x_out))
        return x_out[shuffle], y_out[shuffle]


class UndersamplingBalancer:
    def balance(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        counts = y.sum(axis=0).astype(int)
        min_count = counts.min()
        if min_count == 0:
            raise ImbalanceError("at least one class has zero samples")

        indices: list[np.ndarray] = []
        for i, cnt in enumerate(counts):
            mask = np.where(y[:, i] == 1.0)[0]
            if cnt > min_count:
                mask = np.random.choice(mask, min_count, replace=False)
            indices.append(mask)

        keep = np.concatenate(indices)
        shuffle = np.random.permutation(len(keep))
        return x[keep][shuffle], y[keep][shuffle]
