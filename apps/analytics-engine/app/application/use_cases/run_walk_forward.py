from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.walk_forward_validator import (
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardValidator,
    WindowResult,
)


@dataclass(frozen=True)
class WalkForwardSummary:
    verdict: str
    n_windows: int
    passed_windows: int
    avg_metrics: dict[str, float]
    fail_reason: str


class RunWalkForwardUseCase:
    def __init__(
        self,
        validator: WalkForwardValidator,
    ) -> None:
        self._validator = validator

    async def execute(
        self,
        n_samples: int,
        window_results: list[dict[str, float]],
    ) -> WalkForwardSummary:
        cfg = self._validator.config
        windows = self._validator.compute_windows(n_samples)
        results: list[WindowResult] = []

        for i, (tr_s, tr_e, val_e, te_e) in enumerate(windows):
            metrics = window_results[i] if i < len(window_results) else {}
            errors = self._validator.evaluate_metrics(metrics)
            passed = len(errors) == 0
            results.append(WindowResult(
                window_index=i,
                train_start=tr_s,
                train_end=tr_e,
                test_start=val_e,
                test_end=te_e,
                metrics=metrics,
                passed=passed,
            ))

        avg_metrics = {}
        if results:
            keys = results[0].metrics.keys()
            for k in keys:
                vals = [r.metrics.get(k, 0) for r in results]
                avg_metrics[k] = sum(vals) / len(vals)

        passed = sum(1 for r in results if r.passed)
        if passed == len(results) and len(results) > 0:
            verdict = "VALIDATED"
            fail_reason = ""
        else:
            verdict = "REJECTED"
            fail_reason = f"{len(results) - passed}/{len(results)} windows failed"

        return WalkForwardSummary(
            verdict=verdict,
            n_windows=len(results),
            passed_windows=passed,
            avg_metrics=avg_metrics,
            fail_reason=fail_reason,
        )
